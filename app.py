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
    # Streamlit Secrets থেকে credentials পড়া এবং \n ঠিক করা
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    
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
# 4. Action Tabs (ChatGPT Style Navigation)
# --------------------------------------------------
tab_sync, tab_upload, tab_view = st.tabs(
    ["🔄 Auto Drive Sync", "📤 Manual File Upload", "📊 View Dashboard"]
)

# Tab 1: Google Drive Sync
with tab_sync:
    st.subheader("ড্রাইভ ফাইল প্রসেসিং")
    st.write("Google Drive-এর ১২টি ফোল্ডার স্ক্যান করে ড্যাশবোর্ডে সিঙ্ক করুন।")

    if st.button("🚀 Start Drive Sync", type="primary"):
        try:
            drive_service, spreadsheet = get_google_services()
            main_folder_id = get_folder_id(drive_service, ROOT_FOLDER)

            if not main_folder_id:
                st.error(f"❌ Drive-এ '{ROOT_FOLDER}' ফোল্ডারটি পাওয়া যায়নি!")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()

                total_folders = len(folder_mappings)
                total_files_processed = 0
                updated_tabs_count = 0

                for idx, item in enumerate(folder_mappings):
                    status_text.text(f"Scanning folder: {item['folder_name']}...")
                    progress_bar.progress((idx + 1) / total_folders)

                    sub_folder_id = get_folder_id(
                        drive_service, item["folder_name"], parent_id=main_folder_id
                    )
                    if not sub_folder_id:
                        continue

                    files_list = (
                        drive_service.files()
                        .list(
                            q=f"'{sub_folder_id}' in parents and trashed = false",
                            fields="files(id, name)",
                        )
                        .execute()
                        .get("files", [])
                    )

                    file_index = 1
                    processed_ids = []

                    for f in files_list:
                        fname, fid = f["name"], f["id"]
                        if not (
                            fname.endswith(".xlsx")
                            or fname.endswith(".xls")
                            or fname.endswith(".csv")
                        ):
                            continue

                        try:
                            request = drive_service.files().get_media(fileId=fid)
                            fstream = io.BytesIO()
                            downloader = MediaIoBaseDownload(fstream, request)
                            done = False
                            while not done:
                                _, done = downloader.next_chunk()
                            fstream.seek(0)

                            if fname.endswith(".csv"):
                                sheets_dict = {"Sheet1": pd.read_csv(fstream)}
                            else:
                                excel_file = pd.ExcelFile(fstream, engine="openpyxl")
                                sheets_dict = {
                                    sheet: excel_file.parse(sheet)
                                    for sheet in excel_file.sheet_names
                                }

                            sheet_count = len(sheets_dict)

                            for s_idx, (s_name, df) in enumerate(
                                sheets_dict.items(), start=1
                            ):
                                target_tab_name = (
                                    f"{item['prefix']}_{file_index}"
                                    if sheet_count == 1
                                    else f"{item['prefix']}_{file_index}_S{s_idx}"
                                )

                                df = df.fillna("")
                                values = [df.columns.astype(str).