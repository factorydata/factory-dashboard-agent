import io
import os
import time
import warnings
import gspread
import pandas as pd
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Deprecation warnings ও UserWarnings সাপ্রেস করার জন্য
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# --------------------------------------------------
# Page Config & Custom Styling
# --------------------------------------------------
st.set_page_config(
    page_title="Factory Dashboard AI Agent", page_icon="🤖", layout="wide"
)

# --------------------------------------------------
# 1. Authentication System
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
# 4. Action Tabs Navigation (With AI Assistant)
# --------------------------------------------------
tab_sync, tab_upload, tab_view, tab_chat = st.tabs(
    [
        "🔄 Auto Drive Sync",
        "📤 Manual File Upload",
        "📊 View Dashboard",
        "💬 AI Assistant",
    ]
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
                                    sheet: pd.read_excel(excel_file, sheet_name=sheet)
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

                                df = df.astype(object).fillna("")
                                values = [df.columns.astype(str).tolist()] + df.astype(
                                    str
                                ).values.tolist()

                                try:
                                    worksheet = spreadsheet.worksheet(target_tab_name)
                                except gspread.exceptions.WorksheetNotFound:
                                    worksheet = spreadsheet.add_worksheet(
                                        title=target_tab_name,
                                        rows=max(len(values) + 20, 100),
                                        cols=max(len(values[0]) + 10, 20),
                                    )

                                worksheet.clear()
                                worksheet.update(values=values, range_name="A1")
                                updated_tabs_count += 1
                                time.sleep(1)

                            processed_ids.append(fid)
                            total_files_processed += 1

                        except Exception as err:
                            st.warning(f"Error processing {fname}: {err}")

                        file_index += 1

                    for pid in processed_ids:
                        try:
                            drive_service.files().update(
                                fileId=pid, body={"trashed": True}
                            ).execute()
                        except Exception:
                            pass

                status_text.text("Sync complete!")
                st.success(
                    f"✅ **Sync Successful!** Processed {total_files_processed} files"
                    f" and updated {updated_tabs_count} tabs."
                )

        except Exception as e:
            st.error(f"❌ Error during sync: {e}")

# Tab 2: Manual Excel/CSV Upload
with tab_upload:
    st.subheader("ম্যানুয়াল এক্সেল/সিএসভি আপলোড")
    uploaded_file = st.file_uploader(
        "এক্সেল অথবা সিএসভি ফাইল সিলেক্ট বা ড্র্যাগ করুন",
        type=["xlsx", "xls", "csv"],
    )
    custom_prefix = st.text_input("ট্যাব প্রিফিক্স (Prefix Name)", value="MANUAL")

    if uploaded_file and st.button("📤 Upload & Sync to Sheet"):
        try:
            _, spreadsheet = get_google_services()
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
                sheets_dict = {"Sheet1": df}
            else:
                excel_file = pd.ExcelFile(uploaded_file, engine="openpyxl")
                sheets_dict = {
                    sheet: pd.read_excel(excel_file, sheet_name=sheet)
                    for sheet in excel_file.sheet_names
                }

            for s_name, df in sheets_dict.items():
                tab_title = f"{custom_prefix}_{s_name}"
                df = df.astype(object).fillna("")
                values = [df.columns.astype(str).tolist()] + df.astype(
                    str
                ).values.tolist()

                try:
                    worksheet = spreadsheet.worksheet(tab_title)
                except gspread.exceptions.WorksheetNotFound:
                    worksheet = spreadsheet.add_worksheet(
                        title=tab_title,
                        rows=max(len(values) + 20, 100),
                        cols=max(len(values[0]) + 10, 20),
                    )

                worksheet.clear()
                worksheet.update(values=values, range_name="A1")

            st.success(f"✅ '{uploaded_file.name}' সফলভাবে মাস্টার শিটে আপলোড হয়েছে!")
        except Exception as e:
            st.error(f"❌ আপলোডে সমস্যা হয়েছে: {e}")

# Tab 3: Data Viewer
with tab_view:
    st.subheader("মাস্টার ড্যাশবোর্ড ডাটা ভিউয়ার")
    if st.button("🔄 Refresh Tabs List"):
        try:
            _, spreadsheet = get_google_services()
            worksheets = spreadsheet.worksheets()
            st.session_state["tab_names"] = [ws.title for ws in worksheets]
        except Exception as e:
            st.error(f"❌ ট্যাব লিস্ট লোড করতে সমস্যা: {e}")

    tab_names = st.session_state.get("tab_names", [])
    if tab_names:
        selected_tab = st.selectbox("ড্যাশবোর্ডের ট্যাব সিলেক্ট করুন:", tab_names)
        if selected_tab:
            try:
                _, spreadsheet = get_google_services()
                ws = spreadsheet.worksheet(selected_tab)
                all_values = ws.get_all_values()

                if all_values:
                    df_view = pd.DataFrame(all_values)
                    st.dataframe(df_view, use_container_width=True)
                else:
                    st.info("এই ট্যাবে কোনো ডাটা নেই।")
            except Exception as e:
                st.error(f"❌ ডাটা প্রদর্শন করতে সমস্যা: {e}")

# Tab 4: AI Data Assistant Chatbot
with tab_chat:
    st.subheader("💬 AI Data Assistant")
    st.caption("আপনার ড্যাশবোর্ড ও মাস্টার গুগল শিটের ডাটা নিয়ে কথা বলুন বা খুঁজুন।")

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "হ্যালো! আমি আপনার ড্যাশবোর্ড AI অ্যাসিস্ট্যান্ট। আপনি মাস্টার শিটের ডাটা সম্পর্কিত যেকোনো প্রশ্ন জিজ্ঞাসা করতে পারেন (যেমন: 'মোট কতটি শিট আছে?', 'WS_1 ট্যাবের ডাটা সার্চ করো' ইত্যাদি)।",
            }
        ]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("এখানে আপনার প্রশ্ন লিখুন..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("গুগল শিটের ডাটা স্ক্যান করা হচ্ছে..."):
                try:
                    _, spreadsheet = get_google_services()
                    worksheets = spreadsheet.worksheets()
                    sheet_titles = [ws.title for ws in worksheets]

                    query = prompt.lower()
                    matched_tab = None
                    for t in sheet_titles:
                        if t.lower() in query:
                            matched_tab = t
                            break

                    if matched_tab:
                        ws = spreadsheet.worksheet(matched_tab)
                        vals = ws.get_all_values()
                        total_rows = len(vals)
                        response = f"📊 **ট্যাব সার্চ ফলাফল:**\n\nআপনি **'{matched_tab}'** ট্যাবটির কথা উল্লেখ করেছেন। এই ট্যাবে মোট **{total_rows}** টি রো (Row) ডাটা পাওয়া গেছে।\n\nপ্রথম ৫টি রো-এর নমুনা:\n"
                        sample_df = pd.DataFrame(vals[:6])
                        st.markdown(response)
                        st.dataframe(sample_df, use_container_width=True)
                        st.session_state.messages.append(
                            {"role": "assistant", "content": response}
                        )
                    else:
                        response = f"🔍 **ড্যাশবোর্ড সামারি:**\n\nবর্তমানে আপনার মাস্টার ড্যাশবোর্ডে মোট **{len(sheet_titles)}টি** সক্রিয় শিট/ট্যাব রয়েছে।\n\n**উপলব্ধ ট্যাবসমূহ:**\n`" + "`, `" .join(sheet_titles[:15]) + "`"
                        if len(sheet_titles) > 15:
                            response += f" এবং আরও {len(sheet_titles) - 15}টি।"
                        response += "\n\n💡 *টিপস:* যেকোনো নির্দিষ্ট ট্যাবের ডাটা দেখতে প্রশ্নে ট্যাবের নাম উল্লেখ করুন (যেমন: `WS_1_S15` বা `Rejection_1`)।"
                        st.markdown(response)
                        st.session_state.messages.append(
                            {"role": "assistant", "content": response}
                        )

                except Exception as e:
                    err_msg = f"❌ ডাটা বিশ্লেষণে সমস্যা হয়েছে: {e}"
                    st.markdown(err_msg)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": err_msg}
                    )
