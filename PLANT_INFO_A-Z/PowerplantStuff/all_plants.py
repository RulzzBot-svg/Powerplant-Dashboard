import pandas as pd
import streamlit as st
import psycopg2


def display_all_plant(get_conn):
        st.subheader("☢️All Plants (Without Filters)")
        st.write("The table below displays all the operational powerplants without any filters, some may contain contacts")
        with get_conn() as conn:
            gen_query = """
            SELECT plantname, ownername, company_address, company_city, company_state,fuel_type_1, company_url FROM public.general_plant_info
            """
            gen_df = pd.read_sql_query(gen_query, conn)

            if not gen_df.empty:
                gen_df = gen_df.drop(columns=["plant_id","parentname"], errors="ignore")

                gen_df = gen_df.rename(columns={
                    "plantname":"Plant Name",
                    "ownername":"Owner Name",
                    "company_address":"Address",
                    "company_city":"City",
                    "company_state":"State",
                    "company_phone":"Phone Number",
                    "fuel_type_1":"Primary Fuel Type",
                    "company_url":"URL"
                })
                st.dataframe(gen_df,width="stretch", hide_index=True, height="auto")


            else:
                st.warning("No plants found :((")