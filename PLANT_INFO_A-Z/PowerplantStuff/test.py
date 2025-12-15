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
from PIL import Image
from pandas import ExcelWriter
import xlsxwriter
from st_aggrid import AgGrid, GridOptionsBuilder
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(__file__)
LOGO_PATH = os.path.join(BASE_DIR, "powerplant1.svg")

# ------------------------------------------------------
# Streamlit config (should be one of the first calls)
# ------------------------------------------------------
st.set_page_config(
    page_title="PowerPlant Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ignore a warning in terminal just tells me to use sqlalchemy
warnings.filterwarnings("ignore", category=UserWarning, module="psycopg2")

# ------------------------------------------------------
# DB connection
# ------------------------------------------------------
conn = psycopg2.connect(os.environ["DATABASE_URL"])
def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])

# ------------------------------------------------------
# CACHED LOADERS for Plant Search tab
# ------------------------------------------------------
@st.cache_data(ttl=900)
def load_filter_data():
    """
    Load plant names, fuel types, and manufacturers and drive types for dropdowns.
    Tables: general_plant_info, plant_drive_info (mostly static).
    """
    with get_conn() as conn:
        plant_names = pd.read_sql(
            "SELECT DISTINCT plantname FROM general_plant_info "
            "WHERE plantname IS NOT NULL ORDER BY plantname;",
            conn
        )
        fuel_types = pd.read_sql(
            "SELECT DISTINCT fuel_type_1 FROM general_plant_info "
            "WHERE fuel_type_1 IS NOT NULL ORDER BY fuel_type_1;",
            conn
        )
        manufacturers = pd.read_sql(
            "SELECT DISTINCT drive_manufacturer FROM plant_drive_info "
            "WHERE drive_manufacturer IS NOT NULL ORDER BY drive_manufacturer;",
            conn
        )
        drive_types = pd.read_sql(
            "SELECT DISTINCT drive_info FROM plant_drive_info "
            "WHERE drive_info IS NOT NULL ORDER BY drive_info;",
            conn
        )

    plant_option = ["All"] + plant_names["plantname"].dropna().tolist()
    fuel_options = ["All"] + fuel_types["fuel_type_1"].dropna().tolist()
    manufacturer_options = ["All"] + manufacturers["drive_manufacturer"].dropna().tolist()
    drive_info_options = ["All"] + drive_types["drive_info"].dropna().tolist()

    return plant_option, fuel_options, manufacturer_options, drive_info_options


@st.cache_data(ttl=120)
def load_main_plant_summary():
    """
    Load the main plant list with contact & drive counts.
    Uses contact_plant_info (changes more often), so TTL is short.
    """
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
        df = df.rename(columns={
            "plantname": "Plant Name",
            "ownername": "Owner Name",
            "company_city": "City",
            "company_state": "State",
            "fuel_type_1": "Primary Fuel",
            "contact_count": "Contacts",
            "drive_count": "Drives"
        })

    return df

# ------------------------------------------------------
# LOGIN
# ------------------------------------------------------
if st.session_state.get("logged_out"):
    st.session_state.clear()
    


user = show_login(get_conn)

# --- Sidebar ---
st.sidebar.markdown(f"👋 Logged in as **{user['full_name'] or user['username']}** ({user['role']})")
if st.sidebar.button("🚪 Logout"):
    logout_user()
    
# ------------------------------------------------------
# HEADER
# ------------------------------------------------------
col1, col2 = st.columns([1, 1.5])
with col1:
    st.markdown("# AFC Power Plant Portal")
with col2:
    st.image(LOGO_PATH, width=80)

st.write("Welcome to the internal plant intelligence and contact system.")

# ------------------------------------------------------
# FAKE TABS (RADIO) WITH SOFT-PASTEL STYLE
# ------------------------------------------------------
st.markdown(
    """
    <style>
    /* Container for the radio (our fake tabs) */
    div[data-testid="stHorizontalBlock"] > div[role="radiogroup"] {
        display: flex;
        gap: 0.5rem;
        align-items: center;
    }

    /* Each radio option label */
    div[role="radiogroup"] > label {
        border-radius: 999px; /* pill shape */
        padding: 0.4rem 0.9rem;
        border: 1px solid #444;
        background: #1b1e27;
        cursor: pointer;
        transition: all 0.2s ease;
        font-size: 0.9rem;
        color: #e0e0e0;
    }

    /* Make the little native radio circle invisible */
    div[role="radiogroup"] > label > div:first-child {
        display: none;
    }

    /* Selected tab */
    div[role="radiogroup"] > label[data-selected="true"] {
        background: linear-gradient(135deg, #6A5ACD, #4A90E2);
        border-color: #6A5ACD;
        color: #ffffff;
        box-shadow: 0 0 8px rgba(106, 90, 205, 0.6);
    }

    /* Hover effect */
    div[role="radiogroup"] > label:hover {
        border-color: #4A90E2;
        box-shadow: 0 0 6px rgba(74, 144, 226, 0.4);
    }
    </style>
    """,
    unsafe_allow_html=True
)

tab = st.radio(
    "Navigation",
    [
        "Search Plants By Name",
        "Call Directory Overview",
        "All Plants",
        "Sales Activity",
        "Outtages",
    ],
    horizontal=True,
    key="main_nav",
)

# Hide the "Navigation" label visually to look more like tabs
st.markdown(
    """
    <style>
    label[for="main_nav"] {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ------------------------------------------------------
# TAB 1 FUNCTION: Search Plants By Name
# ------------------------------------------------------
def tab_search_plants():
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
        state_list = [
            "All",
            "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL",
            "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA",
            "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE",
            "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
            "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
            "VA", "WA", "WV", "WI", "WY"
        ]

        # Fetch distinct values for dropdowns (CACHED)
        try:
            plant_option, fuel_options, manufacturer_options, drive_info_options = load_filter_data()
        except Exception as e:
            st.error(f"Error loading dropdown data: {e}")
            plant_option, fuel_options, manufacturer_options = ["All"], ["All"], ["All"]

        # 1st row (Plant filters)
        col1, col2, col3 = st.columns(3)
        with col1:
            plantname = st.selectbox("Plant Name", plant_option, key="p1")
        with col2:
            plantstate = st.selectbox("Plant State", state_list, key="p2")
        with col3:
            plantfuel = st.selectbox("Primary Fuel Type", fuel_options, key="p3")

        # 2nd row (Drive filters)
        col4, col5, col6 = st.columns(3)
        with col4:
            drive_info = st.selectbox("Drive Type",drive_info_options,key="d1")
        with col5:
            drivemanufacturer = st.selectbox("Drive Manufacturer", manufacturer_options, key="d2")
        with col6:
            drivestartup = st.text_input("Startup Year", key="d3")

        search_btn = st.button("Search Plants", use_container_width=True)

    # --- MAIN PLANT LIST (CACHED) ---

        df = load_main_plant_summary()

        if "contacted_status" not in st.session_state:
            st.session_state.contacted_status = {pid: False for pid in df["plant_id"]}

        df["Contacted"] = df["plant_id"].map(st.session_state.contacted_status)

        with st.form(key="editor_form", clear_on_submit=False):
            edited_df = st.data_editor(
                df.drop(columns=["plant_id"]),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Contacted": st.column_config.CheckboxColumn("Contacted")
                },
                key="plant_editor"
            )

            submitted = st.form_submit_button("Save Changes")

        if submitted:
            for pid, val in zip(df["plant_id"], edited_df["Contacted"]):
                st.session_state.contacted_status[pid] = val

        st.write(f"**Total contacted: {sum(st.session_state.contacted_status.values())}**")



##here last lol
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
    plant_filters = []
    plant_params = []

    drive_filters = []
    drive_params = []

    # ✅ Plant filters
    if plantname and plantname != "All":
        plant_filters.append("g.plantname ILIKE %s")
        plant_params.append(f"%{plantname}%")
    if plantstate and plantstate != "All":
        plant_filters.append("g.company_state = %s")
        plant_params.append(plantstate)
    if plantfuel and plantfuel != "All":
        plant_filters.append("g.fuel_type_1 = %s")
        plant_params.append(plantfuel)

    # ✅ Drive filters
    if drive_info and drive_info.strip() != "All":
        drive_filters.append("d.drive_info = %s")
        drive_params.append(drive_info)
    if drivemanufacturer and drivemanufacturer != "All":
        drive_filters.append("d.drive_manufacturer = %s")
        drive_params.append(drivemanufacturer)
    if drivestartup and drivestartup.strip() != "":
        drive_filters.append("d.drive_startup ILIKE %s")
        drive_params.append(f"%{drivestartup}%")

    # --- EXECUTE SEARCH ---
    if search_btn:
        with get_conn() as conn:
            # Contact Query (plant filters only)
            contact_query = f"""
                SELECT DISTINCT
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
                {' WHERE ' + ' AND '.join(plant_filters) if plant_filters else ''}
                ORDER BY g.plantname;
            """
            contact_df = pd.read_sql_query(contact_query, conn, params=plant_params)

            # Drive Query (plant + drive filters)
            drive_query = f"""                 
                SELECT
                    g.plantname AS "Plant Name",
                    d.drive_name AS "Drive Name",
                    d.drive_capacity AS "Drive Capacity",
                    d.drive_manufacturer AS "Manufacturer",
                    d.drive_type AS "Type",
                    d.drive_series AS "Series",
                    d.drive_info AS "Info",
                    d.drive_primary_fuel AS "Primary Fuel",
                    d.drive_startup AS "Startup Year",
                    g.company_state AS "State"
                FROM plant_drive_info d
                JOIN general_plant_info g ON g.plant_id = d.plant_id
                { 'WHERE ' + ' AND '.join(plant_filters + drive_filters) 
                    if (plant_filters or drive_filters) else '' }
                ORDER BY g.plantname
            """
            drive_df = pd.read_sql_query(drive_query, conn, params=plant_params + drive_params)

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
        
            col1, col2, col3 = st.columns([1, 1, 1])

            with col1:
                if not contact_df.empty:
                    st.download_button(
                        label="Download Contacts CSV",
                        data=contact_df.to_csv(index=False).encode("utf-8"),
                        file_name=f"{plantname}_plant_contact_results_{plantstate}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            with col2:
                if not drive_df.empty:
                    st.download_button(
                        label="Download Drive CSV",
                        data=drive_df.to_csv(index=False).encode("utf-8"),
                        file_name=f"{plantname}_drive_info_{plantfuel}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            with col3:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                    if not contact_df.empty:
                        contact_df.to_excel(writer, sheet_name="Contacts", index=False)
                    if not drive_df.empty:
                        drive_df.to_excel(writer, sheet_name="Drive", index=False)
                
                buffer.seek(0)

                st.download_button(
                    label="Download Contact & Driver Information",
                    data=buffer,
                    file_name=f"{plantname}_info.xlsx",
                    mime="application/vnd.openxmlformats-officedocuments.spreadsheetml.sheet",
                    use_container_width=True
                )

# ------------------------------------------------------
# USER CONTEXT (still available if needed)
# ------------------------------------------------------
current_user = st.session_state.get("username", "AFCAdmin")
current_role = st.session_state.get("role", "admin")

# ------------------------------------------------------
# ROUTE TO SELECTED TAB
# ------------------------------------------------------
if tab == "Search Plants By Name":
    tab_search_plants()

elif tab == "Call Directory Overview":
    # this function draws its own layout
    call_directory(get_conn)

elif tab == "All Plants":
    display_all_plant(get_conn)

elif tab == "Sales Activity":
    display_sales_activity(get_conn)

elif tab == "Outtages":
    display_outtages(get_conn)

# ------------------------------------------------------
# FOOTER
# ------------------------------------------------------
st.sidebar.caption("To reset search refresh the page! 🔄")
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
# Need something?