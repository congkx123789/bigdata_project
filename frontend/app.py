import streamlit as st
import requests
import os
import pandas
from minio import Minio
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Large-Scale AI Document System", layout="wide")

# Configuration
INGESTION_URL = os.getenv("INGESTION_URL", "http://localhost:8001")
RAG_URL = os.getenv("RAG_URL", "http://localhost:8002") # Assume RAG service is on 8002
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "password123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "documents")

# MinIO Client
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

# Sidebar
st.sidebar.title("AI Document System")
page = st.sidebar.radio("Navigation", ["Dashboard", "AI Chat"])

if page == "Dashboard":
    st.header("Document Dashboard")
    
    # 1. Upload Section
    st.subheader("Upload Documents")
    uploaded_file = st.file_uploader("Choose a file (PDF, Image, DOCX, TXT)", type=["pdf", "png", "jpg", "jpeg", "docx", "txt"])
    
    if uploaded_file is not None:
        if st.button("Upload to System"):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            try:
                response = requests.post(f"{INGESTION_URL}/upload", files=files)
                if response.status_code == 200:
                    st.success(f"Successfully uploaded {uploaded_file.name}")
                else:
                    st.error(f"Upload failed: {response.text}")
            except Exception as e:
                st.error(f"Error connecting to Ingestion Service: {str(e)}")

    st.divider()
    
    # 2. Document List
    st.subheader("Files in Storage")
    try:
        objects = minio_client.list_objects(MINIO_BUCKET)
        file_list = []
        for obj in objects:
            file_list.append({
                "Filename": obj.object_name,
                "Size (KB)": round(obj.size / 1024, 2),
                "Last Modified": obj.last_modified
            })
        
        if file_list:
            df = pandas.DataFrame(file_list)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No files uploaded yet.")
    except Exception as e:
        st.error(f"Error connecting to MinIO: {str(e)}")

elif page == "AI Chat":
    st.header("AI Knowledge Chat")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "source" in message:
                with st.expander("Show Trích dẫn (Citations)"):
                    st.text(message["source"])

    # Chat Input
    if prompt := st.chat_input("Hỏi về tài liệu của bạn..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response from RAG Service
        with st.chat_message("assistant"):
            try:
                # For this demo, we'll try to call the RAG service if it's running
                # Replace with actual API call to your RAG service
                # response = requests.post(f"{RAG_URL}/ask", json={"question": prompt})
                # data = response.json()
                
                st.info("RAG Service integration in progress. Simulating response...")
                answer = "Đây là câu trả lời demo cho câu hỏi của bạn. Hệ thống đang bóc tách ngữ cảnh từ tài liệu."
                source = "Citations: [File_A.pdf, Trang 5]"
                
                st.markdown(answer)
                with st.expander("Show Trích dẫn (Citations)"):
                    st.text(source)
                
                st.session_state.messages.append({"role": "assistant", "content": answer, "source": source})
            except Exception as e:
                st.error(f"Error connecting to RAG Service: {str(e)}")
