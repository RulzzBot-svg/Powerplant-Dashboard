import streamlit as st
import extra_streamlit_components as stx
import psycopg2
from datetime import datetime, timedelta

# ------------------------------------------------------------
# 🔹 Cookie Manager Init
# ------------------------------------------------------------
if "cookie_manager" not in st.session_state:
    st.session_state.cookie_manager = stx.CookieManager(key="crm_cookie_manager")

def get_cookie_manager():
    if "cookie_manager" not in st.session_state or st.session_state.cookie_manager is None:
        st.session_state.cookie_manager = stx.CookieManager(key="crm_cookie_manager")
    return st.session_state.cookie_manager


# ------------------------------------------------------------
# 🔹 Get all usernames from DB (no password needed)
# ------------------------------------------------------------
def get_all_users(get_conn):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT username, full_name, role FROM app_users ORDER BY username;")
        rows = cur.fetchall()
        users = [
            {"username": r[0], "full_name": r[1], "role": r[2]}
            for r in rows
        ]
        return users


# ------------------------------------------------------------
# 🔹 Save login in cookies + session
# ------------------------------------------------------------
def save_login(user, remember=False):
    cookie = get_cookie_manager()
    
    st.session_state.username = user["username"]
    st.session_state.role = user["role"]
    st.session_state.full_name = user["full_name"]

    expires = datetime.now() + timedelta(days=7 if remember else 1)

    cookie.set(
        "username",
        user["username"],
        expires_at=expires,
        key=f"set_username_{user['username']}"
    )

    cookie.set(
        "role",
        user["role"],
        expires_at=expires,
        key=f"set_role_{user['username']}"
    )

    cookie.set(
        "full_name",
        user["full_name"],
        expires_at=expires,
        key=f"set_fullname_{user['username']}"
    )


# ------------------------------------------------------------
# 🔹 Restore login from cookies
# ------------------------------------------------------------
def restore_login():
    cookie = get_cookie_manager()
    cookies = cookie.get_all()

    if cookies and "username" in cookies and "role" in cookies:
        st.session_state.username = cookies["username"]
        st.session_state.role = cookies["role"]
        st.session_state.full_name = cookies.get("full_name", "")
        return True
    return False


# ------------------------------------------------------------
# 🔹 Logout clears session and cookies
# ------------------------------------------------------------
def logout_user():
    cookie = get_cookie_manager()
    timestamp = datetime.now().timestamp()
    for key in ["username", "role", "full_name"]:
        cookie.delete(key,
                      key=f"del_{key}_{timestamp}")
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.logged_out = True

# ------------------------------------------------------------
# 🔹 MAIN LOGIN UI (NO PASSWORDS, JUST A DROPDOWN)
# ------------------------------------------------------------
def show_login(get_conn):
    # If already logged in
    if "username" in st.session_state:
        return {
            "username": st.session_state.username,
            "role": st.session_state.role,
            "full_name": st.session_state.full_name,
        }

    # Try loading from cookies
    if restore_login():
        return {
            "username": st.session_state.username,
            "role": st.session_state.role,
            "full_name": st.session_state.full_name,
        }

    st.title("🔐 AFC CRM Login")
    st.subheader("Select your user to continue")

    users = get_all_users(get_conn)
    username_list = [u["username"] for u in users]

    selected_user = st.selectbox("Choose User:", username_list)
    remember = st.checkbox("Remember me", value=True)

    if st.button("Login"):
        # Lookup user info
        user = next((u for u in users if u["username"] == selected_user), None)

        if user:
            save_login(user, remember)
            st.success(f"Welcome, {user['full_name']}!")
        else:
            st.error("Unexpected error: user not found.")

    st.stop()
