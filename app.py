

import streamlit as st
from google import genai
from PIL import Image
import tempfile
import os

st.set_page_config(
    page_title="MiniBot",
    page_icon="🤖",
    layout="centered"
)

try:
    client = genai.Client(
        api_key=st.secrets["GEMINI_API_KEY"]
    )
except Exception:
    st.error(
        "MiniBot is not connected to its AI service yet."
    )
    st.stop()

st.title("🤖 MiniBot")

st.subheader(
    "Your Personal AI Assistant"
)

st.write(
    "👋 Hello! I'm MiniBot. "
    "Ask me anything and I'll do my best to help you."
)

# -----------------------------
# Chat memory
# -----------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

# -----------------------------
# Message limit
# -----------------------------

MAX_MESSAGES = 20

if "message_count" not in st.session_state:
    st.session_state.message_count = 0

# -----------------------------
# Display previous messages
# -----------------------------

for message in st.session_state.messages:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# -----------------------------
# Sidebar
# -----------------------------

with st.sidebar:

    st.header("⚙️ MiniBot")

    st.write(
        f"💬 Messages used: "
        f"{st.session_state.message_count}/{MAX_MESSAGES}"
    )

    if st.button(
        "🗑️ Clear Chat",
        use_container_width=True
    ):
        st.session_state.messages = []
        st.session_state.message_count = 0
        st.rerun()

    st.divider()

    st.write("MiniBot can:")

    st.write("💬 Answer questions")
    st.write("🧠 Help you learn")
    st.write("🖼️ Understand images")
    st.write("📄 Read PDFs")
    st.write("💡 Brainstorm ideas")

# -----------------------------
# File upload
# -----------------------------

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

if uploaded_file is not None:

    if uploaded_file.type.startswith("image/"):

        image = Image.open(uploaded_file)

        st.image(
            image,
            caption="Uploaded image",
            use_container_width=True
        )

# -----------------------------
# Chat input
# -----------------------------

user_message = st.chat_input(
    "💬 Type your message..."
)

if user_message:

    # Check message limit
    if st.session_state.message_count >= MAX_MESSAGES:

        st.warning(
            "🛑 You have reached the 20-message "
            "free limit for this session."
        )

        st.info(
            "💎 More messages can be available "
            "in a future premium version."
        )

        st.stop()

    # Count this message
    st.session_state.message_count += 1

    # Save user message
    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_message
        }
    )

    with st.chat_message("user"):
        st.markdown(user_message)

    # -----------------------------
    # Build conversation
    # -----------------------------
    conversation = """
You are MiniBot, a friendly and helpful Student AI Assistant.

Your main purpose is to help students learn and understand subjects.

Personality:
- Friendly
- Patient
- Encouraging
- Clear
- Supportive

You can help students with:
- Explaining difficult concepts
- Step-by-step problem solving
- Summarizing study material and PDFs
- Creating clear study notes
- Generating practice questions from study material
- Creating quizzes with answers for revision
- Creating practice questions and answers
- Explaining diagrams and images
- Revision and study planning
- Brainstorming ideas for projects

When a student uploads a PDF:
- Read the provided PDF carefully.
- Identify the important concepts and information.
- Create clear, organized study notes when requested.
- Use headings and bullet points.
- Highlight important formulas, definitions, and key points.
- Keep the notes focused on what is useful for studying.
- If the PDF contains important examples, include them briefly.
- Do not invent information that is not present in the PDF.

When the student asks for practice questions:
- Create questions based on the provided study material.
- Cover the important topics.
- Mix short-answer, conceptual, and multiple-choice questions when appropriate.
- Provide answers when the student asks for them.
- Do not create questions based on information that is not in the provided material.


Rules:
1. Use simple language whenever possible.
2. Explain difficult topics step by step.
3. Teach the reasoning, not just the final answer.
4. Give examples when they make a concept easier.
5. Keep answers reasonably concise.
6. Remember the current conversation.
7. Never make up information.
8. If you are unsure, clearly say so.
9. For calculations, show the important steps.
10. Encourage the student to understand the topic rather than simply copy an answer.
11. When the student asks for Quiz Mode:
    - Ask one question at a time.
    - Wait for the student's answer before revealing the correct answer.
    - Tell the student whether the answer is correct.
    - Briefly explain the correct answer.
    - Then ask the next question.
    - Keep track of the student's progress during the current conversation.
    12. During Quiz Mode:
    - Keep track of the number of questions asked.
    - Keep track of the student's correct answers.
    - Show the current question number when asking each question.
    - Show the current score after checking each answer.
    - When the quiz is finished, show the final score as correct answers out of total questions.
    - Give a short encouraging message at the end.
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

    conversation += "MiniBot:"

    contents = [
        conversation
    ]

    # -----------------------------
    # Image
    # -----------------------------

    if uploaded_file is not None:

        if uploaded_file.type.startswith("image/"):

            image = Image.open(uploaded_file)

            contents.append(image)

    # -----------------------------
    # PDF
    # -----------------------------

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

                contents.append(pdf_file)

            finally:

                if os.path.exists(
                    temp_pdf.name
                ):

                    os.remove(
                        temp_pdf.name
                    )

    # -----------------------------
    # Generate answer
    # -----------------------------

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

        st.markdown(answer)

    # -----------------------------
    # Save assistant answer
    # -----------------------------

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer
        }
    )
