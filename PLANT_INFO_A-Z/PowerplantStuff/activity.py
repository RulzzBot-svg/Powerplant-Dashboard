import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime


def display_sales_activity(get_conn):
    st.header("🗂️ Sales / CRM Activity Log")

    current_user = st.session_state.get("username", "AFCAdmin")
    current_role = st.session_state.get("role", "admin")

    # --- Load dropdowns ---
    with get_conn() as conn:
        users_df = pd.read_sql("SELECT DISTINCT username, role FROM app_users ORDER BY username;", conn)
        user_list = users_df["username"].tolist()

        plants_df = pd.read_sql("SELECT plant_id, plantname FROM general_plant_info ORDER BY plantname;", conn)
        plant_names = plants_df["plantname"].tolist()

    # ================================================================
    # STEP 1: Select Plant and Contact
    # ================================================================
    st.subheader("Select Plant & Contact")

    plantname = st.selectbox("Plant Name:", [""] + plant_names)

    contact_list = []

    if plantname:
        try:
            with get_conn() as conn:
                contact_query = """
                    SELECT DISTINCT 
                        cont_fname || ' ' || cont_lname AS full_name, cont_fname, cont_lname
                    FROM contact_plant_info
                    WHERE plant_id = (
                        SELECT plant_id FROM general_plant_info
                        WHERE TRIM(plantname) ILIKE %s LIMIT 1
                    )
                    ORDER BY cont_lname, cont_fname;
                """
                contact_df = pd.read_sql(contact_query, conn, params=(f"%{plantname}%",))
                contact_list = contact_df["full_name"].tolist()
        except Exception as e:
            st.error(f"⚠️ Error fetching contacts: {e}")

            
    # ================================================================
    # 👤 Contact selection — hybrid input (new or existing)
    # ================================================================
    col_contact1, col_contact2 = st.columns([2, 1])

    with col_contact1:
        # Free-text name entry (kept persistent across reruns)
        contact_name = st.text_input("Contact Name (type or pick below):", value=st.session_state.get("contact_name", ""))
        st.session_state.contact_name = contact_name  # keep typed value

    with col_contact2:
        # Dropdown list of known contacts
        selected_existing = ""
        if contact_list:
            selected_existing = st.selectbox("Existing Contacts:", [""] + contact_list)

    # ✅ If a contact was chosen from dropdown, override typed name
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
        try:
            with get_conn() as conn:
                details_query = """
                    SELECT email, phone_number 
                    FROM contact_plant_info
                    WHERE cont_fname || ' ' || cont_lname ILIKE %s
                    LIMIT 1;
                """
                details_df = pd.read_sql(details_query, conn, params=(f"%{contact_name}%",))
                if not details_df.empty:
                    contact_email = details_df.loc[0, "email"] or ""
                    contact_phone = details_df.loc[0, "phone_number"] or ""
        except Exception as e:
            st.warning(f"Could not fetch contact details: {e}")
    elif contact_name:
        new_contact = True  # user typed a new name

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

        # 👇 These auto-populate or allow new entry
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
            st.text_input("Logged By:", value=current_user, disabled=True)

        submitted = st.form_submit_button("💾 Add Activity")

    # ================================================================
    # STEP 4: Insert Logic (Add new contact if needed)
    # ================================================================
    if submitted:
        if not plantname or not contact_name or not notes:
            st.warning("Please fill in at least Plant, Contact, and Notes.")
        else:
            try:
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        # --- Add new contact if it doesn't exist ---
                        cur.execute("""
                            SELECT cont_id FROM contact_plant_info 
                            WHERE cont_fname || ' ' || cont_lname ILIKE %s LIMIT 1;
                        """, (f"%{contact_name}%",))
                        existing_contact = cur.fetchone()

                        if not existing_contact:
                            first, *last = contact_name.split(" ", 1)
                            last = last[0] if last else ""
                            cur.execute("""
                                INSERT INTO contact_plant_info (
                                    cont_id, plant_id, cont_fname, cont_lname, email, phone_number
                                )
                                VALUES (
                                    gen_random_uuid(),
                                    (SELECT plant_id FROM general_plant_info WHERE plantname ILIKE %s LIMIT 1),
                                    %s, %s, %s, %s
                                );
                            """, (f"%{plantname}%", first, last, email, phone))
                            st.info(f"🆕 Added new contact '{contact_name}' to {plantname}")

                        # --- Insert the sales activity ---
                        insert_activity = """
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
                                (SELECT cont_id FROM contact_plant_info WHERE cont_fname || ' ' || cont_lname ILIKE %s LIMIT 1),
                                (SELECT plant_id FROM general_plant_info WHERE plantname ILIKE %s LIMIT 1),
                                %s,
                                %s,
                                %s,
                                %s,
                                %s
                            );
                        """
                        cur.execute(insert_activity, (
                            f"%{contact_name}%",
                            f"%{plantname}%",
                            plantname,
                            username,
                            activity_type,
                            notes,
                            follow_up
                        ))
                        conn.commit()

                st.success(f"✅ Activity for {contact_name} at {plantname} logged successfully!")

            except psycopg2.Error as e:
                st.error(f"Database error: {e.pgerror}")
            except Exception as e:
                st.error(f"Unexpected error: {str(e)}")

    # ================================================================
    # 📋 STEP 5: Display Activity Log
    # ================================================================
    st.markdown("---")
    st.subheader("Recent Activity")

    try:
        with get_conn() as conn:
            if current_role == "admin":
                act_query = """
                    SELECT 
                        a.username AS "User",
                        a.plantname AS "Plant",
                        a.activitytype AS "Contacted Via",
                        a.notes AS "Notes",
                        a.follow_up_date AS "Follow-up Date",
                        TO_CHAR(a.created_at, 'YYYY-MM-DD HH24:MI') AS "Created At"
                    FROM sales_activity a
                    ORDER BY a.created_at DESC;
                """
                df = pd.read_sql(act_query, conn)
            else:
                act_query = """
                    SELECT 
                        a.username AS "User",
                        a.plantname AS "Plant",
                        a.activitytype AS "Contacted Via",
                        a.notes AS "Notes",
                        a.follow_up_date AS "Follow-up Date",
                        TO_CHAR(a.created_at, 'YYYY-MM-DD HH24:MI') AS "Created At"
                    FROM sales_activity a
                    WHERE a.username = %s
                    ORDER BY a.created_at DESC;
                """
                df = pd.read_sql(act_query, conn, params=(current_user,))

        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("📭 No activities logged yet.")
    except psycopg2.Error as e:
        st.error(f"Database error while fetching records: {e.pgerror}")
