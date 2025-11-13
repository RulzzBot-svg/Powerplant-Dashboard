import streamlit as st
import pandas as pd
import psycopg2
import pydeck as pydeck
from datetime import date
import json


def display_outtages(get_conn):

    tab1,tab2, tab3 = st.tabs(["Filter by Comments","Upcoming Outtages","Outtages Mapped"])

    with tab1:
            
        # ------------------------------------------------------
        # 1️⃣ Load Data
        # ------------------------------------------------------
        try:
            with get_conn() as conn:
                df = pd.read_sql("""
                    SELECT event_id, plant_name, plant_state, primary_fuel,
                        start_date, end_date, duration_days, com
                    FROM outtage_info
                    WHERE com IS NOT NULL AND TRIM(com) <> ''
                    ORDER BY start_date DESC;
                """, conn)
        except psycopg2.Error as e:
            st.error(f"Database error: {e.pgerror}")
            return

        if df.empty:
            st.info("✅ No comments found in outage logs.")
            return

        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
        df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
        df["days_left"] = (df["start_date"] - pd.Timestamp(date.today())).dt.days

        # ------------------------------------------------------
        # 2️⃣ Filters
        # ------------------------------------------------------
        st.subheader("🔍 Search & Filter")
        col1, col2, col3 = st.columns([1.6, 1, 1])

        with col1:
            keywords_input = st.text_input(
                "Enter keywords (comma-separated):",
                "pump, inspection, oil, filter"
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

        keywords = [k.strip().lower() for k in keywords_input.split(",") if k.strip()]

        filtered_df = df.copy()
        if state_filter != "All":
            filtered_df = filtered_df[filtered_df["plant_state"] == state_filter]
        if fuel_filter != "All":
            filtered_df = filtered_df[filtered_df["primary_fuel"] == fuel_filter]
        if keywords:
            filtered_df = filtered_df[
                filtered_df["com"].apply(lambda text: any(k in text.lower() for k in keywords))
            ]

        if filtered_df.empty:
            st.warning("⚠️ No matching comments found for your filters.")
            return

        # ------------------------------------------------------
        # 3️⃣ Summary Metrics
        # ------------------------------------------------------
        col1, col2, col3 = st.columns(3)
        col1.metric("Matching Records", len(filtered_df))
        col2.metric("Unique Plants", filtered_df["plant_name"].nunique())
        col3.metric(
            "Avg Duration (days)",
            round(filtered_df["duration_days"].astype(float).mean(), 1)
            if not filtered_df.empty else 0
        )

        # ------------------------------------------------------
        # 4️⃣ Add Urgency Category
        # ------------------------------------------------------
        def urgency_label(days):
            if pd.isna(days):
                return "Unknown"
            elif days <= 7:
                return "Urgent (<7d)"
            elif days <= 30:
                return "Soon (<30d)"
            else:
                return "Later (>30d)"

        filtered_df["Urgency"] = filtered_df["days_left"].apply(urgency_label)

        # ------------------------------------------------------
        # 5️⃣ Display Table
        # ------------------------------------------------------
        st.markdown("### 📋 Filtered Comments")
        filtered_df["start_date"] = filtered_df["start_date"].dt.strftime("%m/%d/%Y")
        filtered_df["end_date"] = filtered_df["end_date"].dt.strftime("%m/%d/%Y")
        st.dataframe(
            filtered_df[[
                "plant_name", "plant_state", "primary_fuel",
                "start_date","end_date", "duration_days", "Urgency", "com"
            ]].rename(columns={
                "plant_name": "Plant Name",
                "plant_state": "State",
                "primary_fuel": "Fuel",
                "start_date": "Start Date",
                "end_date":"End Date",
                "duration_days": "Duration (Days)",
                "com": "Comment"
            }),
            use_container_width=True,
            hide_index=True
        )


    with tab2:
            
        st.header("Upcoming Outtages")
        st.caption("A calm, modern overview of upcoming maintenance and outages across all plants.")

        # ------------------------------------------------------
        # Load Data
        # ------------------------------------------------------
        try:
            with get_conn() as conn:
                df = pd.read_sql("""
                    SELECT event_id, plant_id, plant_name, plant_state, primary_fuel,
                        start_date, end_date, duration_days, com
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

        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
        df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")

        # ------------------------------------------------------
        # Filters
        # ------------------------------------------------------
        col1, col2 = st.columns(2)
        with col1:
            state_filter = st.multiselect(
                "Filter by State",
                ["All States", "California", "Oregon", "Washington", "Alaska", "Hawaii",
                "Arizona", "Colorado", "Idaho", "Montana", "New Mexico", "Nevada", "Utah", "Wyoming"],
                default=["All States"]
            )
        with col2:
            fuel_filter = st.selectbox(
                "Filter by Fuel Type",
                ["All"] + sorted(df["primary_fuel"].dropna().unique().tolist())
            )

        df["plant_state"] = df["plant_state"].astype(str).str.strip().str.title()
        df["primary_fuel"] = df["primary_fuel"].astype(str).str.strip()

        if "All States" not in state_filter:
            df = df[df["plant_state"].isin(state_filter)]
        if fuel_filter != "All":
            df = df[df["primary_fuel"].str.lower() == fuel_filter.lower()]

        if df.empty:
            st.warning("⚠️ No outages match your selected filters.")
            return

        # ------------------------------------------------------
        # CSS (soft pastel cards)
        # ------------------------------------------------------
        st.markdown("""
    <style>
        /* 🌙 Dark background */
        [data-testid="stAppViewContainer"] {
            background: #0e1117;
            color: #E0E0E0 !important;
            font-family: 'Segoe UI', sans-serif;
        }

        /* Sidebar matches dark theme but readable */
        [data-testid="stSidebar"] {
            background: ##262730 !important;
            color: #f0f0f0 !important;
        }

        /* Headings */
        h1, h3, h4 {
            color: #EAEAEA !important;
            font-family: 'Segoe UI', sans-serif;
        }

        /* Pastel cards pop against dark background */
        .outage-card {
            border-radius: 16px;
            padding: 1.3rem;
            background: linear-gradient(145deg, #2a2a2a, #333333);
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
            transition: all 0.25s ease;
            border-left: 6px solid #6A5ACD;
        }
        .outage-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.55);
        }

        /* Pastel accent versions */
        .soft-red {
            border-left-color: #FF6B6B;
            background: linear-gradient(145deg, #3b2020, #2a1a1a);
        }
        .soft-orange {
            border-left-color: #FFB347;
            background: linear-gradient(145deg, #3d2c17, #2a1e10);
        }
        .soft-green {
            border-left-color: #27AE60;
            background: linear-gradient(145deg, #20382a, #1a2c22);
        }
        .soft-blue {
            border-left-color: #4A90E2;
            background: linear-gradient(145deg, #1e2d42, #162232);
        }

        /* Text in cards */
        .outage-card h4 {
            margin-bottom: 0.4rem;
            color: #FFFFFF;
        }
        .outage-card p {
            color: #D3D3D3;
            font-size: 0.9rem;
            margin: 2px 0;
        }

        /* Buttons */
        button[kind="secondary"] {
            background-color: #262730 !important;
            color: #f5f5f5 !important;
            border-radius: 6px;
            border: 0.01px solid;
            boder-color: #54555d;
        }
        button[kind="secondary"]:hover {
            background-color: #4a4a4a !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # ------------------------------------------------------
        # Card Grid Layout (Streamlit-native)
        # ------------------------------------------------------
        today = date.today()
        cols = st.columns(3)  # 3 cards per row

        for i, (_, row) in enumerate(df.iterrows()):
            days_left = None
            if pd.notnull(row["start_date"]):
                days_left = (row["start_date"].date() - today).days

            if days_left is None:
                css_class = "soft-blue"
            elif days_left <= 7:
                css_class = "soft-red"
            elif days_left <= 30:
                css_class = "soft-orange"
            else:
                css_class = "soft-green"

            with cols[i % 3]:
                with st.container(border=True):
                    st.markdown(f"""
                    <div class="outage-card {css_class}">
                        <h4>🏭 {row['plant_name']}</h4>
                        <p><b>State:</b> {row['plant_state']}</p>
                        <p><b>Fuel:</b> {row['primary_fuel']}</p>
                        <p><b>Start:</b> {row['start_date'].date() if pd.notnull(row['start_date']) else 'N/A'}</p>
                        <p><b>End:</b> {row['end_date'].date() if pd.notnull(row['end_date']) else 'N/A'}</p>
                        <p><b>Duration:</b> {row['duration_days'] or 'N/A'} days</p>
                        <p><b>Note:</b> {(row['com'] or '')[:70]}{'...' if len(str(row['com']))>70 else ''}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("View Details", key=f"btn-{row['event_id']}", use_container_width=True):
                        st.session_state["selected_outage"] = row["event_id"]

        # ------------------------------------------------------
        # Sidebar Detail View
        # ------------------------------------------------------
        if "selected_outage" in st.session_state:
            selected_id = st.session_state["selected_outage"]
            outage = df[df["event_id"] == selected_id].iloc[0].to_dict()

            st.sidebar.markdown(f"## 🏭 {outage['plant_name']}")
            st.sidebar.markdown(f"**State:** {outage['plant_state']}  \n**Fuel:** {outage['primary_fuel']}")
            st.sidebar.markdown(f"**Start:** {outage.get('start_date')}  \n**End:** {outage.get('end_date')}  \n**Duration:** {outage.get('duration_days')} days")

            try:
                with get_conn() as conn:
                    contacts = pd.read_sql("""
                        SELECT cont_fname, cont_lname, email, phone_number, functional_title
                        FROM contact_plant_info
                        WHERE plant_id = %s
                    """, conn, params=[outage["plant_id"]])
            except Exception:
                contacts = pd.DataFrame()

            st.sidebar.markdown("---")
            st.sidebar.markdown("### 👥 Key Contacts")
            if not contacts.empty:
                for _, c in contacts.iterrows():
                    st.sidebar.markdown(
                        f"**{c['cont_fname']} {c['cont_lname']}** — {c['functional_title'] or 'N/A'}  \n📧 {c['email'] or '—'}  \n📞 {c['phone_number'] or '—'}"
                    )
            else:
                st.sidebar.info("No contact info available for this plant.")

            st.sidebar.markdown("---")
            st.sidebar.markdown("### 📝 Notes")
            st.sidebar.write(outage['com'])

            if st.sidebar.button("❌ Close"):
                del st.session_state["selected_outage"]

    with tab3:

        st.markdown("<h1 style='text-align:center;color:#6A5ACD;'>🗺️ Outage Map — Upcoming Events</h1>", unsafe_allow_html=True)
        st.caption("Visual map of scheduled plant outages, color-coded by urgency.")

        # Load data
        try:
            with get_conn() as conn:
                df = pd.read_sql("""
                    SELECT event_id, plant_name, plant_state, primary_fuel, start_date, lat, long
                    FROM outtage_info
                    WHERE lat IS NOT NULL AND long IS NOT NULL
                    AND start_date >= CURRENT_DATE
                    ORDER BY start_date ASC;
                """, conn)
        except psycopg2.Error as e:
            st.error(f"Database error: {e.pgerror}")
            return

        if df.empty:
            st.info("✅ No upcoming outages found with location data.")
            return

        # ------------------------------------------------------
        # Clean and compute urgency
        # ------------------------------------------------------
        df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        df["long"] = pd.to_numeric(df["long"], errors="coerce")
        df = df.dropna(subset=["lat", "long"])

        today = date.today()
        df["days_left"] = (df["start_date"].dt.date - today).apply(lambda d: d.days if pd.notna(d) else None)

        # Assign colors based on urgency (RGB)
        def urgency_color(days):
            if days is None:
                return [180, 180, 180]
            elif days <= 7:
                return [255, 77, 77]      # red = urgent
            elif days <= 30:
                return [255, 210, 77]     # yellow = soon
            else:
                return [77, 210, 130]     # green = later

        df["color"] = df["days_left"].apply(urgency_color)
        df["radius"] = df["days_left"].apply(lambda x: 60000 if x and x <= 7 else 40000 if x and x <= 30 else 30000)

        # ------------------------------------------------------
        # PyDeck setup
        # ------------------------------------------------------
        point_layer = pydeck.Layer(
            "ScatterplotLayer",
            data=df,
            id="outages",
            get_position=["long", "lat"],
            get_color="color",
            get_radius="radius",
            pickable=True,
            auto_highlight=True,
        )

        view_state = pydeck.ViewState(
            latitude=df["lat"].mean(),
            longitude=df["long"].mean(),
            zoom=4.2,
            pitch=30,
            controller=True,
        )

        chart = pydeck.Deck(
            layers=[point_layer],
            initial_view_state=view_state,
            map_style=None,  # Use open-source map
            tooltip={
                "html": (
                    "<b>{plant_name}</b><br/>"
                    "State: {plant_state}<br/>"
                    "Fuel: {primary_fuel}<br/>"
                    "Starts in: {days_left} days"
                )
            },
        )

        # ------------------------------------------------------
        # Render interactive chart
        # ------------------------------------------------------
        st.pydeck_chart(chart)

        # ------------------------------------------------------
        # Optional — selection display (when clicking a marker)
        # ------------------------------------------------------
        st.markdown("### 🔍 View Plant Details")
        selected_plant = st.selectbox(
            "Select a plant to see more information:",
            ["None"] + sorted(df["plant_name"].unique())
        )

        if selected_plant != "None":
            outage = df[df["plant_name"] == selected_plant].iloc[0]
            st.write(f"**State:** {outage['plant_state']}")
            st.write(f"**Fuel:** {outage['primary_fuel']}")
            st.write(f"**Start Date:** {outage['start_date'].date()}")
            st.write(f"**Days Left:** {outage['days_left']} days")