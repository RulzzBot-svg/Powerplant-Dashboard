import streamlit as st
import pandas as pd
import psycopg2
import datetime


def display_outtage_comments(get_conn):
    st.header("🧾 Outtage")

    
    # ======================================================
    # 1️⃣ LOAD DATA
    # ======================================================

    tab1,tab2 = st.tabs(["Search","Upcoming Outtages"])
    with tab1:
        try:
            with get_conn() as conn:
                df = pd.read_sql("""
                    SELECT 
                        event_id ,
                        plant_name,
                        plant_state,
                        primary_fuel,
                        start_date,
                        end_date,
                        duration_days,
                        com
                    FROM outtage_info
                    WHERE com IS NOT NULL AND TRIM(com) <> ''
                """, conn)
        except psycopg2.Error as e:
            st.error(f"Database error: {e.pgerror}")
            return

        if df.empty:
            st.warning("⚠️ No outage comments found in database.")
            return
        

        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce").dt.strftime("%Y-%m-%d")



        # ======================================================
        # 2️⃣ FILTER CONTROLS
        # ======================================================
        st.markdown("### 🔍 Search & Filter")

        col1, col2, col3 = st.columns([1.5, 1, 1])
        with col1:
            keywords_input = st.text_input(
                "Enter maintenance keywords (comma-separated):",
                "lube, filter, inspection, oil"
            )
        with col2:
            state_filter = st.selectbox(
                "Filter by State:",
                ["All"] + sorted(df["plant_state"].dropna().unique().tolist())
            )
        with col3:
            fuel_filter = st.selectbox(
                "Filter by Fuel Type:",
                ["All"] + sorted(df["primary_fuel"].dropna().unique().tolist())
            )

        # ======================================================
        # 3️⃣ FILTER LOGIC
        # ======================================================
        filtered_df = df.copy()

        # Apply optional state and fuel filters
        if state_filter != "All":
            filtered_df = filtered_df[filtered_df["plant_state"] == state_filter]
        if fuel_filter != "All":
            filtered_df = filtered_df[filtered_df["primary_fuel"] == fuel_filter]

        # Apply keyword search
        if keywords_input:
            keywords = [kw.strip().lower() for kw in keywords_input.split(",") if kw.strip()]
            mask = filtered_df["com"].apply(lambda text: any(kw in text.lower() for kw in keywords))
            filtered_df = filtered_df[mask]

        # ======================================================
        # 4️⃣ DISPLAY RESULTS
        # ======================================================
        st.markdown("### 📄 Matching Comments")
        st.caption(f"Showing {len(filtered_df)} matching records")

        if not filtered_df.empty:
            filtered_df = filtered_df.rename(columns={
                "plant_name":"Plant Name",
                "plant_state":"Plant State",
                "primary_fuel":"Primary Fuel",
                "start_date":"Start Date",
                "end_date":"End Date",
                "duration_days":"Duration (Days)",
                "com":"Comments"
                })
            st.dataframe(
                filtered_df[["Plant Name", "Plant State", "Primary Fuel", "Start Date","End Date", "Duration (Days)", "Comments"]],
                use_container_width=True, hide_index=True
            )

        st.caption("💡 Tip: Try terms like 'pump', 'filter', 'inspection', or 'oil' to find relevant maintenance logs.")


    with tab2:
        st.header("Upcoming outtages")

        try:
            with get_conn() as conn:
                df = pd.read_sql("""
                    SELECT 
                        event_id,
                        plant_name,
                        plant_state,
                        primary_fuel,
                        start_date,
                        end_date,
                        duration_days,
                        com
                    FROM outtage_info
                    WHERE start_date >= CURRENT_DATE
                    ORDER BY start_date ASC;
                """, conn)
        except psycopg2.Error as e:
            st.error(f"Database error: {e.pgerror}")
            return

        if df.empty:
            st.info("✅ No upcoming outages found.")
            return

        # Clean up and format dates
        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
        df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
        df["duration_days"] = pd.to_numeric(df["duration_days"], errors="coerce")

        # ------------------------------------------------------
        # Filters
        # ------------------------------------------------------
        col1, col2 = st.columns([1, 1])
        with col1:
            state_filter = st.selectbox("Filter by State", ["All"] + sorted(df["plant_state"].dropna().unique().tolist()))
        with col2:
            fuel_filter = st.selectbox("Filter by Primary Fuel", ["All"] + sorted(df["primary_fuel"].dropna().unique().tolist()))

        if state_filter != "All":
            df = df[df["plant_state"] == state_filter]
        if fuel_filter != "All":
            df = df[df["primary_fuel"] == fuel_filter]

        if df.empty:
            st.warning("No matching outages with the selected filters.")
            return

        # ------------------------------------------------------
        # Stats Overview
        # ------------------------------------------------------
        soonest = df["start_date"].min().strftime("%Y-%m-%d")
        st.metric("Next Outage Date", soonest)
        st.metric("Total Upcoming Outages", len(df))
        st.divider()

        # ------------------------------------------------------
        # Card-based Display
        # ------------------------------------------------------
        st.markdown("### 🧭 Upcoming Outage Schedule")

        today = datetime.datetime.now().date()
        for _, row in df.iterrows():
            start = row["start_date"].date() if pd.notnull(row["start_date"]) else None
            end = row["end_date"].date() if pd.notnull(row["end_date"]) else None
            days_left = (start - today).days if start else None

            # Color code urgency
            if days_left is not None:
                if days_left <= 7:
                    color = "#F1948A"      # 🔴 urgent
                elif days_left <= 30:
                    color = "#F7DC6F"      # 🟡 soon
                else:
                    color = "#82E0AA"      # 🟢 later
            else:
                color = "#D7DBDD"

            with st.container():
                st.markdown(
                    f"""
                    <div style="background-color:{color};padding:15px;border-radius:12px;margin-bottom:10px;
                                box-shadow:0 2px 5px rgba(0,0,0,0.1);">
                        <h4 style="margin:0;">🏭 {row['plant_name']} ({row['plant_state']})</h4>
                        <p style="margin:5px 0;font-size:14px;">
                            <b>Fuel:</b> {row['primary_fuel'] or 'N/A'} &nbsp;|&nbsp;
                            <b>Start:</b> {start or 'N/A'} &nbsp;–&nbsp;
                            <b>End:</b> {end or 'N/A'} &nbsp;|&nbsp;
                            <b>Duration:</b> {row['duration_days'] or 'N/A'} days
                        </p>
                        <p style="margin-top:8px;color:#333;font-size:13px;">
                            <b>Notes:</b> {row['com'][:250]}{'...' if len(str(row['com'])) > 250 else ''}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        st.caption("Color Legend: 🔴 = within 7 days | 🟡 = within 30 days | 🟢 = later this year")