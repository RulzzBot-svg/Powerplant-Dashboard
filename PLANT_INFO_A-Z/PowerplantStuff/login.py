import streamlit as st
import extra_streamlit_components as stx
import psycopg2
from datetime import datetime, timedelta

# 🔹 Create cookie manager once
if "cookie_manager" not in st.session_state:
    st.session_state.cookie_manager = stx.CookieManager(key="crm_cookie_manager")

def get_cookie_manager():
    if "cookie_manager" not in st.session_state or st.session_state.cookie_manager is None:
        st.session_state.cookie_manager = stx.CookieManager(key="crm_cookie_manager")
    return st.session_state.cookie_manager


# ------------------------------------------------------------
# 🔹 Database-based user authentication
# ------------------------------------------------------------
def authenticate_user(get_conn, username, password):
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT username, full_name, role 
                FROM app_users
                WHERE username = %s 
                  AND password_hash = %s
            """, (username, password))
            user = cur.fetchone()
            if user:
                return {"username": user[0], "full_name": user[1], "role": user[2]}
    except psycopg2.Error as e:
        st.error(f"Database error during login: {e.pgerror}")
    return None


# ------------------------------------------------------------
# 🔹 Save login in cookies + session
# ------------------------------------------------------------
def save_login(user, remember=False):
    cookie = get_cookie_manager()
    st.session_state.username = user["username"]
    st.session_state.role = user["role"]
    st.session_state.full_name = user["full_name"]

    expires = datetime.now() + timedelta(days=7 if remember else 1)
    cookie.set("username", user["username"], expires_at=expires)
    cookie.set("role", user["role"], expires_at=expires)
    cookie.set("full_name", user["full_name"], expires_at=expires)


# ------------------------------------------------------------
# 🔹 Try restoring session from cookie
# ------------------------------------------------------------
def restore_login():
    cookie = get_cookie_manager()
    cookies = cookie.get_all()
    if cookies and "username" in cookies:
        st.session_state.username = cookies["username"]
        st.session_state.role = cookies.get("role", "sales")
        st.session_state.full_name = cookies.get("full_name", "")
        return True
    return False


# ------------------------------------------------------------
# 🔹 Logout clears session and cookies
# ------------------------------------------------------------
def logout_user():
    cookie = get_cookie_manager()
    for key in ["username", "role", "full_name"]:
        cookie.delete(key)
        if key in st.session_state:
            del st.session_state[key]


# ------------------------------------------------------------
# 🔹 Main login form UI component
# ------------------------------------------------------------
def show_login(get_conn):
    # Check existing session
    if "username" in st.session_state:
        return {
            "username": st.session_state.username,
            "role": st.session_state.role,
            "full_name": st.session_state.get("full_name", "")
        }

    if restore_login():
        return {
            "username": st.session_state.username,
            "role": st.session_state.role,
            "full_name": st.session_state.get("full_name", "")
        }

    st.title("🔐 AFC CRM Login")

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        remember = st.checkbox("Remember me", value=True)
        submit = st.form_submit_button("Login")

    if submit:
        user = authenticate_user(get_conn, username, password)
        if user:
            save_login(user, remember)
            st.success(f"✅ Welcome, {user['full_name'] or user['username']}!")
            st.experimental_rerun()
        else:
            st.error("Invalid username or password.")
    st.stop()
