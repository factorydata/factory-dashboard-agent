import io
import os
import warnings
import pandas as pd
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google import genai

warnings.filterwarnings("ignore")

# --------------------------------------------------
# 1. Page Config & Login
# --------------------------------------------------
st.set_page_config(page_title="Factory AI Assistant", page_icon="🤖", layout="wide")

USER_CREDENTIALS = {"admin": "admin123", "user1": "pass123"}

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🤖 Factory Dashboard Agent - Login")
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Log In"):
            if u in USER_CREDENTIALS and USER_CREDENTIALS[u] == p:
                st.session_state["authenticated"] = True
                st.session_state["username"] = u
                st.rerun()
            else:
                st.error("ভুল ইউজারনাম অথবা পাসওয়ার্ড!")
    st.stop()

st.sidebar.title(f"👤 {st.session_state['username']}")
if st.sidebar.button("Log Out"):
    st.session_state["authenticated"] = False
    st.rerun()

# --------------------------------------------------
# 2. Google Drive & Gemini AI Setup
# --------------------------------------------------
ROOT_FOLDER = "Daily mail"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

@st.cache_resource
def get_drive_service():
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in creds_dict and "\\n" in creds_dict["private_key"]:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)

@st.cache_resource
def get_ai_client():
    api_key = st.secrets.get("GEMINI_API_KEY")
    return genai.Client(api_key=api_key) if api_key else None

def search_files_in_drive(drive_service, query_text):
    """গুগল ড্রাইভের সব ফোল্ডার ও সাবফোল্ডারে নাম ধরে ফাইল খোঁজা"""
    query = f"mimeType != 'application/vnd.google-apps.folder' and trashed = false and name contains '{query_text}'"
    results = drive_service.files().list(q=query, fields="files(id, name, createdTime)").execute()
    return results.get("files", [])

def read_excel_from_drive(drive_service, file_id):
    """গুগল ড্রাইভ থেকে এক্সেল বা সিএসভি পড়ে টেক্সট আকারে রূপান্তর করা"""
    request = drive_service.files().get_media(fileId=file_id)
    fstream = io.BytesIO()
    downloader = MediaIoBaseDownload(fstream, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fstream.seek(0)
    
    try:
        excel_file = pd.ExcelFile(fstream, engine="openpyxl")
        summary_text = ""
        for sheet in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet).fillna("")
            summary_text += f"\n--- Sheet: {sheet} ---\n"
            summary_text += df.to_string(index=False)
        return summary_text
    except Exception:
        fstream.seek(0)
        df = pd.read_csv(fstream).fillna("")
        return df.to_string(index=False)

# --------------------------------------------------
# 3. AI Assistant Main Interface
# --------------------------------------------------
st.title("🤖 Direct AI Factory Data Assistant")
st.caption("ড্রাইভের ফাইল বা মেইলের ডাটা নিয়ে সরাসরি প্রশ্ন করুন (যেমন: 'DMS রিপোর্ট অনুযায়ী JKL-U2-1 এর ironman কতজন?')")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "হ্যালো! ড্রাইভে থাকা যেকোনো ফাইল/রিপোর্ট সম্পর্কিত প্রশ্ন লিখুন, আমি ফাইল স্ক্যান করে নিখুঁত উত্তর দিচ্ছি।"}
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("আপনার প্রশ্ন লিখুন..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("গুগল ড্রাইভ থেকে প্রাসঙ্গিক ফাইল পড়া ও AI বিশ্লেষণ চলছে..."):
            try:
                drive_service = get_drive_service()
                ai_client = get_ai_client()

                if not ai_client:
                    st.error("❌ Gemini API Key পাওয়া যায়নি! Streamlit Secrets-এ GEMINI_API_KEY সেট করুন।")
                    st.stop()

                # Keywords বের করা
                keywords = [w for w in prompt.split() if len(w) > 2]
                found_files = []
                
                for kw in keywords:
                    files = search_files_in_drive(drive_service, kw)
                    for f in files:
                        if f not in found_files:
                            found_files.append(f)

                if not found_files:
                    # যদি নির্দিষ্ট ফাইল না পায়, ড্রাইভে থাকা রিসেন্ট ফাইল স্ক্যান
                    results = drive_service.files().list(
                        q="mimeType != 'application/vnd.google-apps.folder' and trashed = false",
                        pageSize=5,
                        fields="files(id, name)"
                    ).execute()
                    found_files = results.get("files", [])

                context_data = ""
                scanned_names = []
                for f in found_files[:3]:  # প্রথম ৩টি প্রাসঙ্গিক ফাইল লোড
                    scanned_names.append(f["name"])
                    content = read_excel_from_drive(drive_service, f["id"])
                    context_data += f"\n\n=== File: {f['name']} ===\n{content[:15000]}" # Truncated safety

                system_prompt = f"""
                You are an expert Factory Data Analyst. Answer the user's query in Bengali accurately based strictly on the provided file data context below.
                
                User Query: {prompt}
                
                Scanned Files Context:
                {context_data}
                """

                response = ai_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=system_prompt,
                )

                final_answer = f"📄 **স্ক্যান করা ফাইলসমূহ:** `{', '.join(scanned_names)}` \n\n" + response.text
                st.markdown(final_answer)
                st.session_state.messages.append({"role": "assistant", "content": final_answer})

            except Exception as e:
                err = f"❌ সমস্যা হয়েছে: {e}"
                st.markdown(err)
                st.session_state.messages.append({"role": "assistant", "content": err})
