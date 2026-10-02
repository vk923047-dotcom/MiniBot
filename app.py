
import streamlit as st
from google import genai
from PIL import Image
import tempfile
import os


# ============================================================
# MINI BOT SETTINGS
# ============================================================

st.set_page_config(
    page_title="MiniBot",
    page_icon="🤖",
    layout="centered"
)


# ============================================================
# GEMINI CLIENT
# ============================================================

try:
    client = genai.Client(
        api_key=st.secrets["GEMINI_API_KEY"]
    )
except Exception:
    st.error(
        "MiniBot is not connected to its AI service yet."
    )
    st.stop()


# ============================================================
# MINI BOT HEADER
# ============================================================

st.title("🤖 MiniBot")

st.subheader(
    "Your Personal AI Assistant"
)

st.write(
    "👋 Hello! I'm MiniBot. "
    "Ask me anything and I'll do my best to help you."
)


# ============================================================
# CHAT MEMORY
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []


# ============================================================
# DISPLAY PREVIOUS MESSAGES
# ============================================================

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(
            message["content"]
        )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ MiniBot")

    if st.button(
        "🗑️ Clear Chat",
        use_container_width=True
    ):

        st.session_state.messages = []

        st.rerun()


    st.divider()

    st.write(
        "MiniBot can:"
    )

    st.write("💬 Answer questions")
    st.write("🧠 Help you learn")
    st.write("🖼️ Understand images")
    st.write("📄 Read PDFs")
    st.write("💡 Brainstorm ideas")


# ============================================================
# FILE UPLOAD
# ============================================================

uploaded_file = st.file_uploader(
    "📎 Upload an image or PDF",
    type=[
        "png",
        "jpg",
        "jpeg",
        "webp",
        "pdf"
    ]
)


# ============================================================
# SHOW UPLOADED IMAGE
# ============================================================

if uploaded_file is not None:

    if uploaded_file.type.startswith(
        "image/"
    ):

        image = Image.open(
            uploaded_file
        )

        st.image(
            image,
            caption="Uploaded image",
            use_container_width=True
        )


# ============================================================
# CHAT FUNCTION
# ============================================================

user_message = st.chat_input(
    "💬 Type your message..."
)


if user_message:

    # --------------------------------------------------------
    # SAVE USER MESSAGE
    # --------------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_message
        }
    )


    # --------------------------------------------------------
    # DISPLAY USER MESSAGE
    # --------------------------------------------------------

    with st.chat_message("user"):

        st.markdown(
            user_message
        )


    # --------------------------------------------------------
    # BUILD CONVERSATION
    # --------------------------------------------------------

    conversation = """
You are MiniBot, a friendly and helpful personal AI assistant.

Personality:
- Friendly
- Patient
- Helpful
- Clear
- Encouraging

Rules:
1. Use simple language.
2. Explain difficult things step by step.
3. Help the user learn.
4. Keep answers reasonably concise.
5. Remember the current conversation.
6. Never make up information.
7. If you are unsure, clearly say so.

"""


    for message in st.session_state.messages:

        role = message["role"]

        content = message["content"]

        if role == "user":

            conversation += (
                f"User: {content}\n"
            )

        elif role == "assistant":

            conversation += (
                f"MiniBot: {content}\n"
            )


    conversation += (
        "MiniBot:"
    )


    # --------------------------------------------------------
    # PREPARE GEMINI CONTENT
    # --------------------------------------------------------

    contents = [
        conversation
    ]


    # --------------------------------------------------------
    # HANDLE IMAGE
    # --------------------------------------------------------

    if uploaded_file is not None:

        if uploaded_file.type.startswith(
            "image/"
        ):

            image = Image.open(
                uploaded_file
            )

            contents.append(
                image
            )


    # --------------------------------------------------------
    # HANDLE PDF
    # --------------------------------------------------------

    if uploaded_file is not None:

        if uploaded_file.type == "application/pdf":

            temp_pdf = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".pdf"
            )

            temp_pdf.write(
                uploaded_file.getvalue()
            )

            temp_pdf.close()


            try:

                pdf_file = client.files.upload(
                    file=temp_pdf.name
                )

                contents.append(
                    pdf_file
                )

            finally:

                if os.path.exists(
                    temp_pdf.name
                ):

                    os.remove(
                        temp_pdf.name
                    )


    # --------------------------------------------------------
    # ASK GEMINI
    # --------------------------------------------------------

    with st.chat_message("assistant"):

        with st.spinner(
            "MiniBot is thinking..."
        ):

            try:

                response = client.models.generate_content(

                    model="gemini-3.5-flash-lite",

                    contents=contents
                )


                answer = response.text


            except Exception as e:

                answer = (
                    "❌ Something went wrong.\n\n"
                    f"{e}"
                )


        st.markdown(
            answer
        )


    # --------------------------------------------------------
    # SAVE MINI BOT RESPONSE
    # --------------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer
        }
    )
