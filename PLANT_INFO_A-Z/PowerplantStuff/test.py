import psycopg2
import streamlit as st
import pandas as pd
import warnings
import time
from login import logout_user, show_login
from calldir import call_directory
from all_plants import display_all_plant
from activity import display_sales_activity
from PIL import Image

#ignore a warning in terminal just tells me to use sqlalchemy
warnings.filterwarnings("ignore", category=UserWarning, module="psycopg2")

#connecting

def get_conn():
    return psycopg2.connect(
    host="192.168.1.131",
    database="PowerPlantDashboard",
    user="postgres",
    password="pass123",
    port=5432
    )




# --- Authentication ---
user = show_login(get_conn)

# --- Sidebar ---
st.sidebar.markdown(f"👋 Logged in as **{user['full_name'] or user['username']}** ({user['role']})")
if st.sidebar.button("🚪 Logout"):
    logout_user()
    st.experimental_rerun()


st.set_page_config(page_title="PowerPlant Dashboard", layout="wide")
col1, col2 = st.columns([1,1.5])
with col1:
    st.markdown("# AFC Power Plant Portal")
with col2:
#    st.image("powerplant1.svg",width=80)
    st.image("powerplant.jpg", width=80)


#image = Image.open('powerplant.jpg')
#st.title("AFC Powerplant Portal")
#st.image(image, width=50)
st.write("Welcome to the internal plant intelligence and contact system.")






tab1, tab2, tab3, tab4 = st.tabs(["Search Plants By Name","Call Directory Overview","All Plants","Sales Activity"])
tab_names = ["PlantByName","Contacts","CRM"]

if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = "PlantByName"


with tab1:
    st.header("🏭 Powerplants with Contacts & Drives")

    # --- FILTERS UNDER HEADER (same visual design) ---
    with st.container():
        st.subheader("🔍 Search Filters")

        # 1st row of filters
        col1, col2, col3 = st.columns(3)
        with col1:
            plantname = st.text_input("Plant Name", key="p1")
        with col2:
            plantstate = st.text_input("Plant State (e.g., CA, TX, WA)", key="p2")
        with col3:
            plantfuel = st.text_input("Primary Fuel Type", key="p3")

        # 2nd row of filters (Drive-specific)
        col4, col5, col6 = st.columns(3)
        with col4:
            drivetype = st.text_input("Drive Type", key="d1")
        with col5:
            drivemanufacturer = st.text_input("Drive Manufacturer", key="d2")
        with col6:
            drivestartup = st.text_input("Startup Year", key="d3")

        search_btn = st.button("Search Plants", use_container_width=True)

    # --- MAIN PLANT LIST (unchanged) ---
    query = """
        SELECT DISTINCT 
            g.plant_id, 
            g.plantname, 
            g.ownername, 
            g.company_address, 
            g.company_city, 
            g.company_state, 
            g.fuel_type_1,
            COUNT(DISTINCT c.cont_id) AS contact_count,
            COUNT(DISTINCT d.drive_id) AS drive_count
        FROM general_plant_info g
        INNER JOIN contact_plant_info c ON g.plant_id = c.plant_id
        INNER JOIN plant_drive_info d ON g.plant_id = d.plant_id
        GROUP BY g.plant_id, g.plantname, g.ownername, g.company_address, g.company_city, g.company_state, g.fuel_type_1
        ORDER BY g.plantname ASC;
    """

    with get_conn() as conn:
        df = pd.read_sql_query(query, conn)

    if not df.empty:
        df = df.drop(columns=["plant_id"], errors="ignore")
        df = df.rename(columns={
            "plantname": "Plant Name",
            "ownername": "Owner Name",
            "company_address": "Address",
            "company_city": "City",
            "company_state": "State",
            "fuel_type_1": "Primary Fuel Type",
            "contact_count": "Contacts",
            "drive_count": "Drives"
        })
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ No plants found with both contact and drive info.")

    # --- JOINT FILTER LOGIC ---
    filters = []
    params = []

    # ✅ Plant filters
    if plantname:
        filters.append("g.plantname ILIKE %s")
        params.append(f"%{plantname}%")
    if plantstate:
        filters.append("g.company_state ILIKE %s")
        params.append(f"%{plantstate}%")
    if plantfuel:
        filters.append("g.fuel_type_1 ILIKE %s")
        params.append(f"%{plantfuel}%")

    # ✅ Drive filters
    if drivetype:
        filters.append("d.drive_type ILIKE %s")
        params.append(f"%{drivetype}%")
    if drivemanufacturer:
        filters.append("d.drive_manufacturer ILIKE %s")
        params.append(f"%{drivemanufacturer}%")
    if drivestartup:
        filters.append("d.drive_startup ILIKE %s")
        params.append(f"%{drivestartup}%")

    # --- EXECUTE SEARCH ---
    if search_btn:
        with get_conn() as conn:
            #Contact Query (uses same combined filters)
            contact_query = f"""
                SELECT
                    c.functional_title AS "Functional Title", 
                    c.actual_title AS "Title", 
                    c.cont_fname AS "First Name", 
                    c.cont_lname AS "Last Name", 
                    c.email AS "Email", 
                    c.phone_number AS "Phone Number",
                    g.plantname AS "Plant Name", 
                    g.company_address AS "Company Address", 
                    g.company_city  AS "City", 
                    g.company_state AS "State", 
                    g.fuel_type_1 AS "Primary Fuel Type", 
                    g.company_url AS "Company URL"
                FROM general_plant_info g
                LEFT JOIN contact_plant_info c ON g.plant_id = c.plant_id
                LEFT JOIN plant_drive_info d ON g.plant_id = d.plant_id
                {' WHERE ' + ' AND '.join(filters) if filters else ''}
                ORDER BY g.plantname
            """
            contact_df = pd.read_sql_query(contact_query, conn, params=params)

            # Drive Query
            drive_query = f"""
                SELECT 
                    d.drive_name as "Drive Name",
                    d.drive_capacity as "Drive Capacity",
                    d.drive_manufacturer as "Manufacturer",
                    d.drive_type as "Type",
                    d.drive_series as "Series",
                    d.drive_info as "Info",
                    d.drive_primary_fuel as "Primary Fuel",
                    d.drive_generator as "Generator",
                    d.generator_info as "Generator Info",
                    d.drive_status as "Status",
                    d.drive_startup as "Startup Year",
                    g.plantname as "Plant Name",
                    g.company_state as "State"
                FROM plant_drive_info d 
                JOIN general_plant_info g ON g.plant_id = d.plant_id
                {' WHERE ' + ' AND '.join(filters) if filters else ''}
                ORDER BY g.plantname
            """
            drive_df = pd.read_sql_query(drive_query, conn, params=params)

        # --- DISPLAY RESULTS ---
        if not contact_df.empty:
            st.success(f"✅ Found {len(contact_df)} matching contact records.")
            st.subheader("Plant & Contact Information")
            st.dataframe(contact_df, use_container_width=True, hide_index=True)
        else:
            st.warning("⚠️ No matching contact records found.")

        if not drive_df.empty:
            st.success(f"✅ Found {len(drive_df)} matching drive records.")
            st.subheader("Drive Information")
            st.dataframe(drive_df, use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ No matching drive records found.")


current_user = st.session_state.get("username","AFCAdmin")
current_role = st.session_state.get("role","admin")


with tab4:
    display_sales_activity(get_conn)



#CALL DIRECTORY

with tab2:
    call_directory(get_conn)

with tab3:
    display_all_plant(get_conn)



st.sidebar.caption("To reset search refresh the page! 🔄")
st.sidebar.caption("States availabe:CA, OR, WA, AK, HI, AZ, CO, ID, MT, NM,NV,UT,WY ")


st.sidebar.caption("Made by: Raul Ostorga & Oscar Ostorga")
#
#⠀⠀⠀⠀⠀⠀⠀⠀⣠⡤⠒⠛⣋⣉⡛⠲⢿⣄⣀⣠⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀
#⠀⠀⠀⠀⠀⠀⣠⠞⠁⠀⣴⣿⣿⣿⣿⣧⣀⣿⣿⣿⣿⣿⣷⠦⢤⣀⠀⠀⠀⠀
#⠀⠀⠀⠀⠀⡼⠁⠀⠀⢠⣿⣿⣿⣿⣿⣿⠿⣿⣿⣿⣿⣿⣿⠀⠀⠈⠻⣦⠀⠀
#⠀⠀⠀⠀⡼⢁⠀⣤⣶⠟⠻⢿⣿⣿⡿⠟⠀⠘⠻⠿⠿⠟⠁⠀⠀⠀⠀⠈⢷⠀
#⠀⠀⠀⣼⢳⣿⣦⡹⡅⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣴⣶⣶⣦⠀⠀⠀⠀⢸⡇
#⠀⢀⣼⡇⣿⣿⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠉⠉⠁⠀⠀⠀⠀⣸⠇
#⢠⣿⢿⡇⣿⣿⣿⣿⣿⢻⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⠏⠀
#⠀⠉⠈⣷⣿⣿⣿⣿⣿⣾⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣠⣤⠴⠞⠛⠁⠀⠀
#⠀⠀⠀⠈⠿⣿⣿⡿⢟⣼⠗⠲⠦⢤⣀⠀⠀⠀⢀⡴⠚⠉⠁⠀⠀⠀⠀⠀⠀⠀
#⢀⣤⣶⡛⢳⡮⢉⣛⣋⣁⣀⣀⣀⣀⡾⠓⠤⠤⠞⢳⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀
#⠸⣄⠈⠉⢸⡟⠉⠀⠀⠀⠀⠀⠀⠉⠙⠂⠤⠤⠤⠾⣟⣧⠀⠀⠀⠀⠀⠀⠀⠀
#⠀⢸⡇⠀⣸⣤⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⢻⡄⠀⠀⠀⠀⠀⠀⠀
#⠀⠈⠓⠲⠋⠀⠉⠉⠉⠉⠉⠉⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⣷⣄⠀⠀⠀⠀⠀⠀
#⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣏⠀⠀⠀⠀⠀⠀⠀⠀⢀⣧⣽⡄⠀⠀⠀⠀⠀
#⠀⠀⠀⠀⠀⠀⠀⠀⢀⣤⠤⠤⣿⣦⠤⠤⠤⠤⠄⠐⠒⠛⠋⠀⢹⠀⠀⠀⠀⠀
#⠀⠀⠀⠀⠀⠀⠀⠀⠈⠉⠛⠉⠉⠉⢷⣄⠀⠀⠀⠀⢀⣄⠀⠀⣼⠀⠀⠀⠀⠀
#⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢈⣛⣶⡶⠚⠛⠓⠒⠒⠛⠲⣄⠀⠀⠀
#⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡰⠼⣯⣅⣖⣀⣒⣘⣙⣦⣈⣷⣀⣸⠇⠀⠀
#
#
# Need something?









