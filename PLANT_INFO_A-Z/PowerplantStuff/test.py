import sys, os
import io
from activity import display_sales_activity
from all_plants import display_all_plant
from calldir import call_directory
from login import logout_user, show_login
from outtage import display_outtages
import psycopg2
import streamlit as st
import pandas as pd
import warnings
import time
from PIL import Image
from pandas import ExcelWriter
import xlsxwriter





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
    st.image("powerplant1.svg",width=80)


#image = Image.open('powerplant.jpg')
#st.title("AFC Powerplant Portal")
#st.image(image, width=50)
st.write("Welcome to the internal plant intelligence and contact system.")






tab1, tab2, tab3, tab4, tab5 = st.tabs(["Search Plants By Name","Call Directory Overview","All Plants","Sales Activity", "Outtages"])




with tab1:
    st.header("🏭 Powerplants with Contacts & Drives")
    
    help_btn = st.popover("❓ Help")
    with help_btn:
        st.markdown("""
    ℹ️ **How to Use This Tab**

    - **Filter** plants using the dropdowns below (State,Fuel Type,Drive Type,Manufacturer,Start up year)
    - **Copy** a plant of your interest and **paste** on **Plant Name** to get detailed information on them.
    - **Check off** plants once you've contacted them.
    - Use the **Export** button to save your contacted list as a CSV.

    _Tip:_ Check the contact columns to see which plants have the most amount of contacts.

        """)

    # --- FILTERS UNDER HEADER ---
    with st.container():
        st.subheader("🔍 Search Filters")

        # Predefined state list
        state_list = ["All", "CA", "OR", "WA", "AK", "HI", "AZ", "CO", "ID", "MT", "NM", "NV", "UT", "WY"]

        # Fetch distinct values for dropdowns
        with get_conn() as conn:
            try:
                fuel_types = pd.read_sql("SELECT DISTINCT fuel_type_1 FROM general_plant_info WHERE fuel_type_1 IS NOT NULL ORDER BY fuel_type_1;", conn)
                fuel_options = ["All"] + fuel_types["fuel_type_1"].dropna().tolist()

                manufacturers = pd.read_sql("SELECT DISTINCT drive_manufacturer FROM plant_drive_info WHERE drive_manufacturer IS NOT NULL ORDER BY drive_manufacturer;", conn)
                manufacturer_options = ["All"] + manufacturers["drive_manufacturer"].dropna().tolist()
            except Exception as e:
                st.error(f"Error loading dropdown data: {e}")
                fuel_options, manufacturer_options = ["All"], ["All"]

        # 1st row (Plant filters)
        col1, col2, col3 = st.columns(3)
        with col1:
            plantname = st.text_input("Plant Name", key="p1")
        with col2:
            plantstate = st.selectbox("Plant State", state_list, key="p2")
        with col3:
            plantfuel = st.selectbox("Primary Fuel Type", fuel_options, key="p3")

        # 2nd row (Drive filters)
        col4, col5, col6 = st.columns(3)
        with col4:
            drivetype = st.text_input("Drive Type", key="d1")
        with col5:
            drivemanufacturer = st.selectbox("Drive Manufacturer", manufacturer_options, key="d2")
        with col6:
            drivestartup = st.text_input("Startup Year", key="d3")

        search_btn = st.button("Search Plants", use_container_width=True)


    # --- MAIN PLANT LIST ---
    query = """
        SELECT DISTINCT 
            g.plant_id, 
            g.plantname, 
            g.ownername, 
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

    if df.empty:
        st.warning("empty table boi")
    else:
        df = df.rename(columns={
            "plantname": "Plant Name",
            "ownername": "Owner Name",
            "company_city": "City",
            "company_state": "State",
            "fuel_type_1": "Primary Fuel Type",
            "contact_count": "Contacts",
            "drive_count": "Drives"
        })
        if "contacted_status" not in st.session_state:
            st.session_state.contacted_status = {pid: False for pid in df["plant_id"]}
        
        df["Contacted"] = df["plant_id"].apply(lambda pid: st.session_state.contacted_status.get(pid, False))

        edited_df = st.data_editor(
            df.drop(columns=["plant_id"]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Contacted":st.column_config.CheckboxColumn(
                    "Contacted", help="Mark if you already contacted this plant", default=False
                )
            },
            key="plant_table_editor"
        )

        for pid,contacted in zip(df["plant_id"],edited_df["Contacted"]):
            st.session_state.contacted_status[pid] = contacted

        total_contacted = sum(st.session_state.contacted_status.values())
        st.markdown(f"**{total_contacted} plants are marked as contacted**")

        if st.button("📤 Export Contacted Plants"):
            contacted_df = df[df["plant_id"].isin(
                [pid for pid, val in st.session_state.contacted_status.items() if val]
            )][["Plant Name", "State", "Primary Fuel Type"]]
            st.download_button(
                "Download Contacted Plants (CSV)",
                data=contacted_df.to_csv(index=False).encode("utf-8"),
                file_name="contacted_plants.csv",
                mime="text/csv",
            )

    # --- JOINT FILTER LOGIC ---
    filters = []
    params = []

    # ✅ Plant filters
    if plantname:
        filters.append("g.plantname ILIKE %s")
        params.append(f"%{plantname}%")
    if plantstate and plantstate != "All":
        filters.append("g.company_state = %s")
        params.append(plantstate)
    if plantfuel and plantfuel != "All":
        filters.append("g.fuel_type_1 = %s")
        params.append(plantfuel)

    # ✅ Drive filters
    if drivetype:
        filters.append("d.drive_type ILIKE %s")
        params.append(f"%{drivetype}%")
    if drivemanufacturer and drivemanufacturer != "All":
        filters.append("d.drive_manufacturer = %s")
        params.append(drivemanufacturer)
    if drivestartup:
        filters.append("d.drive_startup ILIKE %s")
        params.append(f"%{drivestartup}%")

    # --- EXECUTE SEARCH ---
    if search_btn:
        with get_conn() as conn:
            #Contact Query (uses same combined filters)
            contact_query = f"""
                SELECT
                    g.plantname AS "Plant Name", 
                    c.functional_title AS "Functional Title", 
                    c.actual_title AS "Title", 
                    c.cont_fname AS "First Name", 
                    c.cont_lname AS "Last Name", 
                    c.email AS "Email", 
                    c.phone_number AS "Phone Number",
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
                    g.plantname as "Plant Name",
                    d.drive_name as "Drive Name",
                    d.drive_capacity as "Drive Capacity",
                    d.drive_manufacturer as "Manufacturer",
                    d.drive_type as "Type",
                    d.drive_series as "Series",
                    d.drive_info as "Info",
                    d.drive_primary_fuel as "Primary Fuel",
                    d.drive_startup as "Startup Year",
                    g.company_state as "State"
                FROM plant_drive_info d 
                JOIN general_plant_info g ON g.plant_id = d.plant_id
                {' WHERE ' + ' AND '.join(filters) if filters else ''}
                ORDER BY g.plantname ASC;
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

        if not contact_df.empty or not drive_df.empty:
            st.markdown("---")
            st.subheader("Export Results")
        
            col1, col2, col3 = st.columns([1,1,1])

            with col1:
                if not contact_df.empty:
                    st.download_button(
                        label="Download Contacts CSV",
                        data=contact_df.to_csv(index=False).encode("utf-8"),
                        file_name="plant_contact_results.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            with col2:
                if not drive_df.empty:
                    st.download_button(
                        label="Download Drive CSV",
                        data=drive_df.to_csv(index=False).encode("utf-8"),
                        file_name="drive_info.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            with col3:
                buffer = io.BytesIO()
                with ExcelWriter(buffer, engine="xlsxwriter") as writer:
                    if not contact_df.empty:
                        contact_df.to_excel(writer, sheet_name="Contacts", index=False)
                    if not drive_df.empty:
                        drive_df.to_excel(writer,sheet_name="Drive",index=False)
                    writer.close()
                st.download_button(label="Download Contact & Drive CSV",
                                   data=buffer.getvalue(),
                                   file_name="contact_drive_info.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   use_container_width=True
                )




current_user = st.session_state.get("username","AFCAdmin")
current_role = st.session_state.get("role","admin")




#CALL DIRECTORY

with tab2:
    call_directory(get_conn)

with tab3:
    display_all_plant(get_conn)

with tab4:
    display_sales_activity(get_conn)

with tab5:
    display_outtages(get_conn)


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









