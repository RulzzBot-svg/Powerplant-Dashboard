import pandas as pd
import streamlit as st
import psycopg2



def call_directory(get_conn):

        st.subheader("📞 Call Directory")

        with st.container():
            st.subheader("Search Filters")

            col1, col2, col3 = st.columns(3)
            with col1:
                state=st.text_input("State")
            with col2:
                role = st.text_input("Title/Role")
            with col3:
                fuel = st.text_input("Primary Fuel Type")
            
            search_btn = st.button("Search Contacts", width="stretch")

        filters = []
        params = []

        if state:
            filters.append("g.company_state ILIKE %s")
            params.append(f"{state}%")
        if role:
            filters.append("c.functional_title ILIKE %s")
            params.append(f"{role}%")
        if fuel:
            filters.append("g.fuel_type_1 ILIKE %s")
            params.append(f"{fuel}%")

        if search_btn:
            contact_query = F"""
                SELECT 
                    g.plantname AS "Plant Name",
                    g.company_state AS "State",
                    g.fuel_type_1 AS "Primary Fuel Type",
                    c.functional_title AS "Title",
                    c.cont_fname AS "First Name",
                    c.cont_lname AS "Last Name",
                    c.email AS "Email",
                    c.phone_number AS "Phone Number"
                FROM general_plant_info g
                JOIN contact_plant_info c ON g.plant_id = c.plant_id
                {' WHERE '+' AND '.join(filters)if filters else ''}
                ORDER BY g.plantname
                """
            with get_conn() as conn:
                call_df = pd.read_sql_query(contact_query, conn, params=params)

            if not call_df.empty:
                st.dataframe(call_df,width="stretch", hide_index=True)
            else:
                st.warning("Nothing found LOL")
