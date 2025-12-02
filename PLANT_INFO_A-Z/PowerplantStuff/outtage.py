import streamlit as st
import pandas as pd
import psycopg2
import pydeck as pydeck
from datetime import date
from contextlib import contextmanager

# ============================================================
# 🔵 FRAGMENT SHIMS (for older Streamlit versions)
# ============================================================


# ---- helper to check if object is a real context manager ----
def _is_ctx_manager(obj):
    return hasattr(obj, "__enter__") and hasattr(obj, "__exit__")

# ---- MAIN fragment shim ----
try:
    candidate = getattr(st, "fragment", None)
    if candidate and _is_ctx_manager(candidate):
        fragment_ctx = candidate
    else:
        raise AttributeError
except Exception:
    @contextmanager
    def fragment_ctx(_id: str):
        yield

# ---- SIDEBAR fragment shim ----
try:
    side_candidate = getattr(st.sidebar, "fragment", None)
    if side_candidate and _is_ctx_manager(side_candidate):
        sidebar_fragment_ctx = side_candidate
    else:
        raise AttributeError
except Exception:
    @contextmanager
    def sidebar_fragment_ctx(_id: str):
        with st.sidebar:
            yield



# ============================================================
# 🔵 GLOBAL CSS — loaded once per session (cards only)
# ============================================================
@st.cache_resource
def load_outage_css():
    return """
    <style>
        .outage-card {
            border-radius: 16px;
            padding: 1.1rem;
            margin-bottom: 1rem;
            background: linear-gradient(145deg, #2b2b2b, #1f1f1f);
            box-shadow: 0 4px 12px rgba(0,0,0,0.35);
            border-left: 6px solid #6A5ACD;
            transition: all 0.25s ease;
        }
        .outage-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.55);
        }
        .soft-red {
            border-left-color:#FF6B6B !important;
            background:linear-gradient(145deg,#3b2020,#2a1a1a);
        }
        .soft-orange {
            border-left-color:#FFB347 !important;
            background:linear-gradient(145deg,#3d2c17,#2a1e10);
        }
        .soft-green {
            border-left-color:#27AE60 !important;
            background:linear-gradient(145deg,#20382a,#1a2c22);
        }
        .soft-blue {
            border-left-color:#4A90E2 !important;
            background:linear-gradient(145deg,#1e2d42,#162232);
        }
        .card-title {
            font-size:1.1rem;
            font-weight:600;
            color:#ffffff;
            margin-bottom:.35rem;
        }
        .card-text {
            font-size:0.9rem;
            color:#d2d2d2;
            margin:0.15rem 0;
        }
    </style>
    """


# ============================================================
# 🔵 CACHED QUERIES (FAST)
# ============================================================
@st.cache_data(ttl=300)
def load_upcoming_outages(_get_conn):
    """Upcoming outages for cards & sidebar."""
    with _get_conn() as conn:
        return pd.read_sql(
            """
            SELECT event_id, plant_id, plant_name, plant_state, primary_fuel,
                   start_date, end_date, duration_days, com
            FROM outtage_info
            WHERE start_date >= CURRENT_DATE
            ORDER BY start_date ASC;
            """,
            conn,
        )


@st.cache_data(ttl=300)
def load_comments(_get_conn):
    """Rows that have comments."""
    with _get_conn() as conn:
        return pd.read_sql(
            """
            SELECT event_id, plant_name, plant_state, primary_fuel,
                   start_date, end_date, duration_days, com
            FROM outtage_info
            WHERE com IS NOT NULL AND TRIM(com) <> ''
            ORDER BY start_date DESC;
            """,
            conn,
        )


@st.cache_data(ttl=300)
def load_map_outages(_get_conn):
    """Outages with lat/long for the map."""
    with _get_conn() as conn:
        return pd.read_sql(
            """
            SELECT event_id, plant_name, plant_state, primary_fuel,
                   start_date, lat, long
            FROM outtage_info
            WHERE lat IS NOT NULL AND long IS NOT NULL
              AND start_date >= CURRENT_DATE
            ORDER BY start_date ASC;
            """,
            conn,
        )


@st.cache_data(ttl=600)
def load_contacts(_get_conn, plant_id):
    """Contacts for a given plant_id (used in sidebar details)."""
    with _get_conn() as conn:
        return pd.read_sql(
            """
            SELECT cont_fname, cont_lname, email, phone_number, functional_title
            FROM contact_plant_info
            WHERE plant_id = %s;
            """,
            conn,
            params=[plant_id],
        )


@st.cache_data
def get_distinct_plants(df):
    return sorted(df["plant_name"].dropna().unique())


# ============================================================
# 🔵 URGENCY HELPERS
# ============================================================
def urgency_label(days):
    if pd.isna(days):
        return "Unknown"
    if days <= 7:
        return "Urgent (<7d)"
    if days <= 30:
        return "Upcoming (<30d)"
    return "Future (>30d)"


def urgency_color_class(days):
    if pd.isna(days):
        return "soft-blue"
    if days <= 7:
        return "soft-red"
    if days <= 30:
        return "soft-orange"
    return "soft-green"


def urgency_color_rgb(days):
    if pd.isna(days):
        return [160, 160, 180]
    if days <= 7:
        return [255, 77, 77]
    if days <= 30:
        return [255, 210, 77]
    return [77, 210, 130]


# ============================================================
# 🔵 MAIN ENTRY
# ============================================================
def display_outtages(get_conn):

    # Just card styling; your theme still rules backgrounds/colors.
    st.markdown(load_outage_css(), unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(
        ["Filter by Comments", "Upcoming Outages", "Outages Map"]
    )

    # ========================================================
    # TAB 1 — COMMENTS
    # ========================================================
    with tab1:
        df = load_comments(get_conn)

        if df.empty:
            st.info("No comments were found.")
        else:
            # 🟦 Drop event_id column safely (only if exists)
            df = df.drop(columns=["event_id"], errors="ignore")

            # 🟦 Convert to datetime (keeps original DF clean)
            df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
            df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")

            # 🟦 Display-friendly date format (mm/dd/yyyy)
            df["start_date"] = df["start_date"].dt.strftime("%m/%d/%Y")
            df["end_date"] = df["end_date"].dt.strftime("%m/%d/%Y")

            # 🟦 Today calc for days_left (use original datetime)
            today = date.today()
            df["days_left"] = df["start_date"].apply(
                lambda d: (pd.to_datetime(d).date() - today).days 
                if pd.notnull(d) else None
            )

            st.subheader("🔍 Search Comments")

            col1, col2, col3 = st.columns(3)

            with col1:
                keywords_input = st.text_input(
                    "Keywords (comma-separated):",
                    "pump, inspection",
                    key="tab1_keywords",
                )

            with col2:
                state_filter = st.selectbox(
                    "State",
                    ["All"] + sorted(df["plant_state"].dropna().unique()),
                    key="tab1_state",
                )

            with col3:
                fuel_filter = st.selectbox(
                    "Fuel Type",
                    ["All"] + sorted(df["primary_fuel"].dropna().unique()),
                    key="tab1_fuel",
                )

            keywords = [
                k.strip().lower()
                for k in keywords_input.split(",")
                if k.strip()
            ]

            filtered = df.copy()

            # Filters
            if state_filter != "All":
                filtered = filtered[filtered["plant_state"] == state_filter]

            if fuel_filter != "All":
                filtered = filtered[filtered["primary_fuel"] == fuel_filter]

            if keywords:
                filtered = filtered[
                    filtered["com"]
                    .astype(str)
                    .str.lower()
                    .apply(lambda txt: any(k in txt for k in keywords))
                ]

            if filtered.empty:
                st.warning("No matches found.")
            else:
                c1, c2, _ = st.columns(3)
                c1.metric("Matching Records", len(filtered))
                c2.metric("Unique Plants", filtered["plant_name"].nunique())

                # 🟦 Rename columns for display
                filtered = filtered.rename(columns={
                    "plant_name": "Plant Name",
                    "plant_state": "State",
                    "primary_fuel": "Fuel",
                    "duration_days": "Duration (Days)",
                    "start_date": "Start Date",
                    "end_date": "End Date",
                    "com": "Comment",
                    "days_left":"Days  Left"
                })

                # 🟦 Show results
                st.dataframe(
                    filtered,
                    use_container_width=True,
                    hide_index=True,
                )
    # ========================================================
    # TAB 2 — UPCOMING OUTAGES (CARDS + SIDEBAR)
    # ========================================================
    with tab2:
        df = load_upcoming_outages(get_conn)

        if df.empty:
            st.info("There are no upcoming outages.")
        else:
            df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
            df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")

            today = date.today()
            df["days_left"] = df["start_date"].apply(
                lambda d: (d.date() - today).days if pd.notnull(d) else None
            )

            df["Urgency"] = df["days_left"].apply(urgency_label)
            df["css_class"] = df["days_left"].apply(urgency_color_class)

            st.header("Upcoming Outages")

            col1, col2, col3 = st.columns(3)

            with col1:
                states = ["All"] + sorted(df["plant_state"].dropna().unique())
                state_filter = st.multiselect(
                    "State",
                    states,
                    default=["All"],
                    key="tab2_states"
                )

            with col2:
                fuels = ["All"] + sorted(df["primary_fuel"].dropna().unique())
                fuel_filter = st.selectbox(
                    "Fuel Type",
                    fuels,
                    key="tab2_fuel"
                )

            with col3:
                plants = ["All"] + get_distinct_plants(df)
                plant_filter = st.selectbox(
                    "Plant Name",
                    plants,
                    key="tab2_plants"
                )

            # -------------------------
            #       APPLY FILTERS
            # -------------------------
            filtered = df.copy()

            if "All" not in state_filter:
                filtered = filtered[filtered["plant_state"].isin(state_filter)]

            if fuel_filter != "All":
                filtered = filtered[filtered["primary_fuel"] == fuel_filter]

            if plant_filter != "All":
                filtered = filtered[filtered["plant_name"] == plant_filter]

            if filtered.empty:
                st.warning("No outages match your filters.")
            else:

                # ============================================================
                # ✅ PAGINATION (THIS FIXES ALL LAG)
                # ============================================================
                PAGE_SIZE = 100

                if "out_page" not in st.session_state:
                    st.session_state["out_page"] = 0

                page = st.session_state["out_page"]
                total = len(filtered)
                total_pages = (total - 1) // PAGE_SIZE + 1

                start = page * PAGE_SIZE
                end = start + PAGE_SIZE
                paged_df = filtered.iloc[start:end]

                # Pagination Controls
                colA, colB, colC = st.columns([1, 2, 1])

                with colA:
                    if st.button("⬅️ Prev", disabled=page == 0):
                        st.session_state["out_page"] -= 1
                        st.rerun()

                with colB:
                    st.markdown(
                        f"<div style='text-align:center;font-size:16px;'>"
                        f"Page {page+1} of {total_pages}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                with colC:
                    if st.button("Next ➡️", disabled=page >= total_pages - 1):
                        st.session_state["out_page"] += 1
                        st.rerun()

                # ============================================================
                # CARD RENDERING — NOW USING paged_df ONLY
                # ============================================================
                with fragment_ctx("tab2_outage_cards"):
                    cols = st.columns(3)

                    for i, row in enumerate(paged_df.itertuples()):
                        with cols[i % 3]:
                            st.markdown(
                                f"""
                                <div class="outage-card {row.css_class}">
                                    <div class="card-title">🏭 {row.plant_name}</div>
                                    <div class="card-text"><b>State:</b> {row.plant_state}</div>
                                    <div class="card-text"><b>Fuel:</b> {row.primary_fuel}</div>
                                    <div class="card-text"><b>Start:</b> {row.start_date.date()}</div>
                                    <div class="card-text"><b>End:</b> {row.end_date.date()}</div>
                                    <div class="card-text"><b>Duration:</b> {row.duration_days} days</div>
                                    <div class="card-text"><b>Note:</b> {(row.com or '')[:70]}...</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            if st.button(
                                "View",
                                key=f"btn_view_{row.event_id}",
                                use_container_width=True,
                            ):
                                st.session_state["selected_outage"] = row.event_id

                # ============================================================
                # SIDEBAR DETAILS (UNCHANGED)
                # ============================================================
                with sidebar_fragment_ctx("tab2_outage_details"):
                    if "selected_outage" in st.session_state:
                        outage_id = st.session_state["selected_outage"]
                        selected_rows = df[df["event_id"] == outage_id]

                        if not selected_rows.empty:
                            selected = selected_rows.iloc[0]

                            st.subheader(selected["plant_name"])
                            st.write(f"**State:** {selected['plant_state']}")
                            st.write(f"**Fuel:** {selected['primary_fuel']}")
                            st.write(f"**Start:** {selected['start_date'].date()}")
                            st.write(f"**End:** {selected['end_date'].date()}")
                            st.write(
                                f"**Duration:** {selected['duration_days']} days"
                            )
                            st.write("---")
                            st.write("### Notes")
                            st.write(selected["com"] or "No notes available.")

                            contacts = load_contacts(get_conn, selected["plant_id"])
                            st.write("---")
                            st.write("### 👥 Key Contacts")

                            if contacts.empty:
                                st.info("No contacts available!")
                            else:
                                for _, c in contacts.iterrows():
                                    st.markdown(
                                        f"**{c['cont_fname']} {c['cont_lname']}** — "
                                        f"{c['functional_title'] or 'N/A'}  \n"
                                        f"📧 {c['email'] or '—'}  \n"
                                        f"📞 {c['phone_number'] or '—'}"
                                    )

                            if st.button(
                                "Close details",
                                key="tab2_close_sidebar_outage",
                            ):
                                del st.session_state["selected_outage"]
                        else:
                            st.info("No outage selected.")
                    else:
                        st.caption("Select an outage card and click **View** to see details here.")








    # ========================================================
    # TAB 3 — MAP
    # ========================================================
    with tab3:
        df = load_map_outages(get_conn)

        if df.empty:
            st.info("No location-based outages found.")
        else:
            df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")

            today = date.today()
            df["days_left"] = df["start_date"].apply(
                lambda d: (d.date() - today).days if pd.notnull(d) else None
            )

            df["color"] = df["days_left"].apply(urgency_color_rgb)
            df["radius"] = df["days_left"].apply(
                lambda d: 60000 if d is not None and d <= 7
                else 40000 if d is not None and d <= 30
                else 30000
            )

            st.subheader("🗺️ Outages Map")

            layer = pydeck.Layer(
                "ScatterplotLayer",
                data=df,
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
            )

            st.pydeck_chart(
                pydeck.Deck(
                    layers=[layer],
                    initial_view_state=view_state,
                    tooltip={
                        "html": (
                            "<b>{plant_name}</b><br/>"
                            "State: {plant_state}<br/>"
                            "Fuel: {primary_fuel}<br/>"
                            "Starts in {days_left} days"
                        )
                    },
                )
            )
