import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime


def display_sales_activity(get_conn):
    st.header("🗂️ Customer Interaction History")

    help_btn = st.popover("❓ Help")
    with help_btn:
        st.markdown("""
        ℹ️ **How to Use This Tab**
        - Once you've ended the call, you log the interaction!  
        - **Look** for the plant name (you can type, it autofills!).
        - **If** the plant has contact info a small rectangle will show up on the right, if not then fill out the form.
        - **Try** to leave a follow up date, it can be next week or a specific date like 12/15.
        - **Provide** a summary of what the chat was about, how the conversation felt or if theres more potential with that client.
        - _Tip:_ Try to be as detailed as possible.
        """)

    current_user = st.session_state.get("username", "AFCAdmin")
    current_role = st.session_state.get("role", "admin")

    # ================================================================
    #  CACHED LOADERS  (big performance gain)
    # ================================================================

    @st.cache_data(ttl=300)
    def load_users_and_plants():
        with get_conn() as conn:
            users = pd.read_sql("SELECT DISTINCT username, role FROM app_users ORDER BY username;", conn)
            plants = pd.read_sql("SELECT plant_id, plantname FROM general_plant_info ORDER BY plantname;", conn)
        return users, plants

    users_df, plants_df = load_users_and_plants()
    user_list = users_df["username"].tolist()
    plant_names = plants_df["plantname"].tolist()

    @st.cache_data
    def load_contacts_for_plant(plantname):
        """Load contacts for a plant (cached)."""
        with get_conn() as conn:
            query = """
                SELECT DISTINCT 
                    cont_fname || ' ' || cont_lname AS full_name, 
                    cont_fname, 
                    cont_lname
                FROM contact_plant_info
                WHERE plant_id = (
                    SELECT plant_id FROM general_plant_info
                    WHERE TRIM(plantname) ILIKE %s LIMIT 1
                )
                ORDER BY cont_lname, cont_fname;
            """
            df = pd.read_sql(query, conn, params=(f"%{plantname}%",))
        return df

    @st.cache_data
    def load_contact_details(contact_name):
        """Fetch email + phone for an existing contact."""
        with get_conn() as conn:
            details_query = """
                SELECT email, phone_number 
                FROM contact_plant_info
                WHERE cont_fname || ' ' || cont_lname ILIKE %s
                LIMIT 1;
            """
            df = pd.read_sql(details_query, conn, params=(f"%{contact_name}%",))
        return df

    # ================================================================
    # STEP 1: Select Plant & Contact
    # ================================================================
    st.subheader("Select Plant & Contact")

    plantname = st.selectbox("Plant Name:", [""] + plant_names)

    if plantname:
        contact_df = load_contacts_for_plant(plantname)
        contact_list = contact_df["full_name"].tolist()
    else:
        contact_list = []

    # ================================================================
    # Contact selection — hybrid input
    # ================================================================
    col_contact1, col_contact2 = st.columns([2, 1])

    with col_contact1:
        contact_name = st.text_input("Contact Name (type or pick below):", 
                                     value=st.session_state.get("contact_name", ""))
        st.session_state.contact_name = contact_name

    with col_contact2:
        selected_existing = ""
        if contact_list:
            selected_existing = st.selectbox("Existing Contacts:", [""] + contact_list)

    if selected_existing:
        contact_name = selected_existing
        st.session_state.contact_name = contact_name

    new_contact = False
    contact_email = ""
    contact_phone = ""

    # ================================================================
    # STEP 2: Auto-populate contact details
    # ================================================================
    if contact_name and contact_name in contact_list:
        details_df = load_contact_details(contact_name)
        if not details_df.empty:
            contact_email = details_df.loc[0, "email"] or ""
            contact_phone = details_df.loc[0, "phone_number"] or ""
    elif contact_name:
        new_contact = True

    # ================================================================
    # STEP 3: Add Activity Form
    # ================================================================
    with st.form("add_activity", clear_on_submit=True):
        st.subheader("Add New Activity")

        col1, col2 = st.columns(2)
        with col1:
            activity_type = st.selectbox("Contacted Via:", ["Call", "Email", "Text", "Meeting", "Other"])
        with col2:
            follow_up = st.text_input("Follow-up Date or Note (e.g. 'Next Monday')")

        col3, col4 = st.columns(2)
        with col3:
            email = st.text_input("Email:", value=contact_email)
        with col4:
            phone = st.text_input("Phone Number:", value=contact_phone)

        notes = st.text_area("Notes / Summary")

        if current_role == "admin":
            username = st.selectbox("Logged By:", user_list)
        else:
            username = current_user

        submitted = st.form_submit_button("💾 Add Activity")

    # ================================================================
    # STEP 4: Insert Logic
    # ================================================================
    if submitted:
        if not plantname or not contact_name or not notes:
            st.warning("Please fill in at least Plant, Contact, and Notes.")
        else:
            try:
                with get_conn() as conn:
                    with conn.cursor() as cur:

                        # Insert new contact if needed
                        cur.execute("""
                            SELECT cont_id FROM contact_plant_info 
                            WHERE cont_fname || ' ' || cont_lname ILIKE %s LIMIT 1;
                        """, (f"%{contact_name}%",))
                        existing_contact = cur.fetchone()

                        if not existing_contact:
                            first, *last = contact_name.split(" ", 1)
                            last = last[0] if last else ""
                            contact_id = f"{first} {last}".strip()

                            cur.execute("""
                                INSERT INTO contact_plant_info (
                                    cont_id, plant_id, cont_fname, cont_lname, email, phone_number
                                )
                                VALUES (
                                    %s,
                                    (SELECT plant_id FROM general_plant_info WHERE plantname ILIKE %s LIMIT 1),
                                    %s, %s, %s, %s
                                );
                            """, (contact_id, f"%{plantname}%", first, last, email, phone))
                            st.info(f"🆕 Added new contact '{contact_name}' to {plantname}")

                        # Insert activity
                        cur.execute("""
                            INSERT INTO sales_activity (
                                cont_id,
                                plant_id,
                                plantname,
                                username,
                                activitytype,
                                notes,
                                follow_up_date
                            )
                            VALUES (
                                (SELECT cont_id FROM contact_plant_info 
                                 WHERE cont_fname || ' ' || cont_lname ILIKE %s LIMIT 1),
                                (SELECT plant_id FROM general_plant_info 
                                 WHERE plantname ILIKE %s LIMIT 1),
                                %s, %s, %s, %s, %s
                            );
                        """, (f"%{contact_name}%", f"%{plantname}%", plantname,
                              username, activity_type, notes, follow_up))

                        conn.commit()

                st.success(f"✅ Activity for {contact_name} at {plantname} logged successfully!")

            except psycopg2.Error as e:
                st.error(f"Database error: {e.pgerror}")
            except Exception as e:
                st.error(f"Unexpected error: {str(e)}")

    # ================================================================
    # STEP 5: Display Activity Log
    # ================================================================
    st.markdown("---")
    st.subheader("Recent Activity")

    @st.cache_data(ttl=120)
    def load_activity_log(role, user):
        with get_conn() as conn:
            if role == "admin":
                query = """
                    SELECT 
                        a.username AS "User",
                        COALESCE(c.cont_fname || ' ' || c.cont_lname, a.cont_id::text) AS "Contact",
                        a.plantname AS "Plant",
                        a.activitytype AS "Contacted Via",
                        a.notes AS "Notes",
                        a.follow_up_date AS "Follow-up Date",
                        TO_CHAR(a.created_at, 'YYYY-MM-DD HH24:MI') AS "Created At"
                    FROM sales_activity a
                    LEFT JOIN contact_plant_info c ON a.cont_id = c.cont_id
                    ORDER BY a.created_at DESC;
                """
                return pd.read_sql(query, conn)
            else:
                query = """
                    SELECT 
                        a.username AS "User",
                        a.cont_id AS "Contact",
                        a.plantname AS "Plant",
                        a.activitytype AS "Contacted Via",
                        a.notes AS "Notes",
                        a.follow_up_date AS "Follow-up Date",
                        TO_CHAR(a.created_at, 'YYYY-MM-DD HH24:MI') AS "Created At"
                    FROM sales_activity a
                    WHERE a.username = %s
                    ORDER BY a.created_at DESC;
                """
                return pd.read_sql(query, conn, params=(user,))

    try:
        df = load_activity_log(current_role, current_user)
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("📭 No activities logged yet.")
    except psycopg2.Error as e:
        st.error(f"Database error while fetching records: {e.pgerror}")
