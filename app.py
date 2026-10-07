import os
import tempfile

import requests
import streamlit as st
from google import genai
from PIL import Image


st.set_page_config(
    page_title="MiniBot",
    page_icon="🤖",
    layout="centered",
)


st.markdown(
    """
    <style>
    .stMarkdown, .stAlert {
        overflow-wrap: anywhere;
        word-wrap: break-word;
    }

    [data-testid="stChatMessageContent"] {
        overflow-wrap: anywhere;
        word-wrap: break-word;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------
# Gemini AI
# -----------------------------

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    st.error("MiniBot is not connected to its AI service yet.")
    st.info("Add GEMINI_API_KEY to the Render environment variables.")
    st.stop()

try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error("MiniBot could not connect to the AI service.")
    st.code(str(e))
    st.stop()


# -----------------------------
# Razorpay
# -----------------------------

RAZORPAY_PLAN_ID = "plan_TkFyotYJk1c9fX"
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")


# -----------------------------
# Main page
# -----------------------------

st.title("🤖 MiniBot")

st.markdown("## 👋 Welcome to MiniBot!")

st.info(
    "🎓 Study smarter with AI — understand concepts, study from PDFs, "
    "practice with quizzes, and prepare for exams."
)

st.markdown("### Your AI Study Assistant")

st.write("### ✨ What MiniBot can do")
st.write("🧠 Explain difficult topics")
st.write("📄 Turn PDFs into study notes")
st.write("📝 Generate practice questions")
st.write("🎯 Interactive Quiz Mode")
st.write("📅 Create study plans")
st.write("🖼️ Understand images & diagrams")

st.markdown(
    """
    **MiniBot can help you:**

    🧠 Understand difficult concepts  
    📄 Study from your PDFs and notes  
    📝 Create study notes and practice questions  
    🎯 Take interactive quizzes  
    📅 Build study plans  
    🖼️ Understand diagrams and images
    """
)

st.divider()


# -----------------------------
# Session state
# -----------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "message_count" not in st.session_state:
    st.session_state.message_count = 0

MAX_MESSAGES = 20


# -----------------------------
# Sidebar
# -----------------------------

with st.sidebar:

    st.header("⚙️ MiniBot")

    st.info(
        "🔐 Google login will be added after the main chatbot is working."
    )

    st.divider()

    st.write("### ✨ What MiniBot can do")
    st.write("🧠 Explain difficult topics")
    st.write("📄 Turn PDFs into study notes")
    st.write("📝 Generate practice questions")
    st.write("🎯 Interactive Quiz Mode")
    st.write("📅 Create study plans")
    st.write("🖼️ Understand images & diagrams")

    st.divider()

    st.write("### 🆓 Free Plan")
    st.write("✅ AI tutoring")
    st.write("✅ PDF study help")
    st.write("✅ Practice questions")
    st.write("✅ Quiz Mode")
    st.write("✅ Study planning")
    st.caption("💬 20 messages per session")

    st.divider()

    st.write("### 💎 Premium")
    st.caption("₹99/month")

    st.write(
        "Unlock unlimited messages and premium study features."
    )

    if st.button(
        "💎 Get Premium",
        use_container_width=True
    ):

        if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:

            st.warning(
                "⚠️ Razorpay payment setup needs to be connected."
            )

            st.info(
                "Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET "
                "to the Render environment variables."
            )

        else:

            try:

                subscription_data = {
                    "plan_id": RAZORPAY_PLAN_ID,
                    "total_count": 12,
                    "customer_notify": 1,
                }

                response = requests.post(
                    "https://api.razorpay.com/v1/subscriptions",
                    auth=(
                        RAZORPAY_KEY_ID,
                        RAZORPAY_KEY_SECRET,
                    ),
                    json=subscription_data,
                    timeout=20,
                )

                if response.status_code in (200, 201):

                    subscription = response.json()

                    subscription_link = subscription.get(
                        "short_url"
                    )

                    if subscription_link:

                        st.success(
                            "✅ Your Premium subscription is ready!"
                        )

                        st.link_button(
                            "💳 Continue to ₹99/month Premium",
                            subscription_link,
                            use_container_width=True,
                        )

                    else:

                        st.error(
                            "Razorpay did not return a subscription link."
                        )

                        st.code(
                            response.text
                        )

                else:

                    st.error(
                        "❌ Could not create the subscription."
                    )

                    st.code(
                        response.text
                    )

            except Exception as e:

                st.error(
                    "❌ Razorpay connection failed."
                )

                st.code(
                    str(e)
                )

    st.divider()

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
# Display previous messages
# -----------------------------

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(
            message["content"]
        )


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
        "pdf",
    ],
)


# -----------------------------
# Display uploaded image
# -----------------------------

if uploaded_file is not None:

    if uploaded_file.type.startswith("image/"):

        image = Image.open(
            uploaded_file
        )

        st.image(
            image,
            caption="Uploaded image",
            use_container_width=True,
        )


# -----------------------------
# Chat input
# -----------------------------

user_message = st.chat_input(
    "💬 Type your message..."
)


if user_message:

    # -------------------------
    # Check message limit
    # -------------------------

    if st.session_state.message_count >= MAX_MESSAGES:

        st.warning(
            "🛑 You have reached the 20-message "
            "free limit for this session."
        )

        st.info(
            "💎 More messages are available with Premium."
        )

        st.stop()


    # -------------------------
    # Count message
    # -------------------------

    st.session_state.message_count += 1


    # -------------------------
    # Save user message
    # -------------------------

    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_message,
        }
    )

    with st.chat_message("user"):

        st.markdown(
            user_message
        )


    # -------------------------
    # MiniBot instructions
    # -------------------------

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
- Creating personalized study plans and revision schedules
- Explaining diagrams and images
- Revision and study planning
- Brainstorming ideas for projects

When a student uploads a PDF:
- Read the PDF carefully.
- Identify important concepts and information.
- Create clear, organized study notes when requested.
- Use headings and bullet points.
- Highlight important formulas, definitions, and key points.
- Keep notes focused on useful study material.
- If the PDF contains important examples, include them briefly.
- Do not invent information that is not present in the PDF.

When the student asks for practice questions:
- Create questions based on the provided study material.
- Cover important topics.
- Mix short-answer, conceptual, and multiple-choice questions when appropriate.
- Provide answers when requested.
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
    - Keep track of progress during the current conversation.
12. During Quiz Mode:
    - Keep track of questions asked.
    - Keep track of correct answers.
    - Show the current question number.
    - Show the current score after checking each answer.
    - When the quiz is finished, show the final score.
    - Give a short encouraging message at the end.
13. When the student asks for a study plan:
    - Ask for the exam date or number of days available if it is not provided.
    - Use uploaded study material when available.
    - Divide the material into manageable daily sections.
    - Include study, revision, and practice time.
    - Keep the plan realistic and achievable.
    - Prioritize important topics.
    - Include short breaks when appropriate.
"""


    # -------------------------
    # Add previous messages
    # -------------------------

    for message in st.session_state.messages:

        role = message["role"]
        content = message["content"]

        if role == "user":

            conversation += (
                f"\nUser: {content}\n"
            )

        elif role == "assistant":

            conversation += (
                f"\nMiniBot: {content}\n"
            )


    conversation += "\nMiniBot:"


    contents = [
        conversation
    ]


    # -------------------------
    # Add image
    # -------------------------

    if uploaded_file is not None:

        if uploaded_file.type.startswith("image/"):

            image = Image.open(
                uploaded_file
            )

            contents.append(
                image
            )


    # -------------------------
    # Add PDF
    # -------------------------

    if uploaded_file is not None:

        if uploaded_file.type == "application/pdf":

            temp_pdf = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".pdf",
            )

            try:

                temp_pdf.write(
                    uploaded_file.getvalue()
                )

                temp_pdf.close()

                pdf_file = client.files.upload(
                    file=temp_pdf.name
                )

                contents.append(
                    pdf_file
                )

            finally:

                try:
                    temp_pdf.close()
                except Exception:
                    pass

                if os.path.exists(
                    temp_pdf.name
                ):

                    os.remove(
                        temp_pdf.name
                    )


    # -------------------------
    # Generate answer
    # -------------------------

    with st.chat_message("assistant"):

        with st.spinner(
            "MiniBot is thinking..."
        ):

            try:

                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=contents,
                )

                answer = response.text

                if not answer:

                    answer = (
                        "I could not generate a response. "
                        "Please try again."
                    )

            except Exception as e:

                answer = (
                    "❌ Something went wrong while "
                    "generating the answer.\n\n"
                    f"{e}"
                )

        st.markdown(
            answer
        )


    # -------------------------
    # Save assistant answer
    # -------------------------

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
        }
    )
