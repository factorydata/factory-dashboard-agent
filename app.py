import io
import os
import time
import gspread
import pandas as pd
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --------------------------------------------------
# Page Config & Custom Styling (ChatGPT Theme)
# --------------------------------------------------
st.set_page_config(
    page_title="Factory Dashboard AI Agent", page_icon="🤖", layout="wide"
)

# --------------------------------------------------
# 1. Authentication System (10 Users)
# --------------------------------------------------
USER_CREDENTIALS = {
    "admin": "admin123",
    "user1": "pass123",
    "user2": "pass123",
    "user3": "pass123",
    "user4": "pass123",
    "user5": "pass123",
    "user6": "pass123",
    "user7": "pass123",
    "user8": "pass123",
    "user9": "pass123",
}


def login_screen():
    st.title("🤖 Factory Dashboard Agent - Login")
    st.subheader("অনুগ্রহ করে আপনার অ্যাকাউন্ট বিবরণ দিয়ে প্রবেশ করুন")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Log In")

        if submit:
            if (
                username in USER_CREDENTIALS
                and USER_CREDENTIALS[username] == password
            ):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.success("লগইন সফল হয়েছে!")
                st.rerun()
            else:
                st.error("ভুল ইউজারনাম অথবা পাসওয়ার্ড!")


if not st.session_state.get("authenticated", False):
    login_screen()
    st.stop()

# --------------------------------------------------
# 2. Google API Connections (From Secrets)
# --------------------------------------------------
SHEET_NAME = "Master Daily Dashboard"
ROOT_FOLDER = "Daily mail"
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


@st.cache_resource
def get_google_services():
    creds_dict = dict(st.secrets["gcp_service_account"])

    # \n ও নতুন লাইন উভয় ফরম্যাট সঠিক করা
    if "private_key" in creds_dict:
        pk = creds_dict["private_key"]
        if "\\n" in pk:
            pk = pk.replace("\\n", "\n")
        creds_dict["private_key"] = pk

    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=SCOPES
    )

    drive_service = build("drive", "v3", credentials=creds)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open(SHEET_NAME)
    return drive_service, spreadsheet


folder_mappings = [
    {"prefix": "WS", "folder_name": "WS Reports"},
    {"prefix": "Rejection", "folder_name": "Rejection Mail"},
    {"prefix": "DMS", "folder_name": "DMS Report"},
    {"prefix": "QAD", "folder_name": "QAD Reports"},
    {"prefix": "Finishing_U1", "folder_name": "Finishing Mail U1"},
    {"prefix": "Finishing_U2", "folder_name": "Finishing Mail U2"},
    {"prefix": "Habibur", "folder_name": "Habibur Reports"},
    {"prefix": "Ruhul", "folder_name": "Ruhul Amin Reports"},
    {"prefix": "NPT", "folder_name": "Non Productive Time"},
    {"prefix": "Alamgir", "folder_name": "Alamgir Reports"},
    {"prefix": "Habibur_R", "folder_name": "Habibur Rahman Reports"},
    {"prefix": "Nayem", "folder_name": "Nayem Mia Reports"},
]


def get_folder_id(drive_service, folder_name, parent_id=None):
    query = (
        f"name = '{folder_name}' and mimeType ="
        " 'application/vnd.google-apps.folder' and trashed = false"
    )
    if parent_id:
        query += f" and '{parent_id}' in parents"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get("files", [])
    return items[0]["id"] if items else None


# --------------------------------------------------
# 3. Streamlit Sidebar & Header
# --------------------------------------------------
st.sidebar.title(f"👤 {st.session_state['username']}")
if st.sidebar.button("Log Out"):
    st.session_state["authenticated"] = False
    st.rerun()

st.title("🤖 Factory Dashboard Agent")
st.caption(
    "Google Drive এর ১২টি ফোল্ডারের ফাইল এবং ম্যানুয়াল ডাটা সিঙ্কিং পোর্টাল"
)

st.markdown("---")

# --------------------------------------------------
# 4. Action Tabs Navigation
# --------------------------------------------------
tab_sync, tab_upload, tab_view