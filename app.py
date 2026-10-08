import os
import tempfile
import uuid
import requests
import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
from google import genai
from google.genai import types
from PIL import Image


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="MiniBot",
    page_icon="🤖",
    layout="centered",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>
    .stMarkdown,
    .stAlert,
    [data-testid="stChatMessageContent"] {
        overflow-wrap: anywhere;
        word-wrap: break-word;
    }

    .minibot-card {
        padding: 20px;
        border-radius: 15px;
        border: 1px solid rgba(128,128,128,0.25);
        margin-bottom: 15px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SETTINGS
# ============================================================

MODEL_NAME = "gemini-3.8-flash"
FREE_MESSAGE_LIMIT = 20

RAZORPAY_PLAN_ID = os.environ.get(
    "RAZORPAY_PLAN_ID",
    "plan_TkFyotYJk1c9fX",
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")
DATABASE_URL = os.environ.get("DATABASE_URL")


# ============================================================
# DATABASE
# ============================================================

def get_db_connection():
    if not DATABASE_URL:
        return None

    return psycopg2.connect(
        DATABASE_URL,
        connect_timeout=10,
        sslmode="require",
    )


def init_database():
    if not DATABASE_URL:
        return False, "DATABASE_URL is not configured."

    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS minibot_users (
                    id SERIAL PRIMARY KEY,
                    user_key TEXT UNIQUE NOT NULL,
                    email TEXT,
                    name TEXT,
                    premium BOOLEAN NOT NULL DEFAULT FALSE,
                    razorpay_subscription_id TEXT,
                    razorpay_status TEXT,
                    premium_until TIMESTAMPTZ,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

        connection.commit()
        return True, None

    except Exception as error:
        if connection:
            connection.rollback()

        return False, str(error)

    finally:
        if connection:
            connection.close()


def get_user(user_key):
    if not DATABASE_URL:
        return None

    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM minibot_users
                WHERE user_key = %s
                """,
                (user_key,),
            )

            return cursor.fetchone()

    except Exception:
        return None

    finally:
        if connection:
            connection.close()


def create_or_update_user(user_key, email=None, name=None):
    if not DATABASE_URL:
        return None

    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO minibot_users
                    (user_key, email, name)
                VALUES
                    (%s, %s, %s)
                ON CONFLICT (user_key)
                DO UPDATE SET
                    email = COALESCE(EXCLUDED.email, minibot_users.email),
                    name = COALESCE(EXCLUDED.name, minibot_users.name),
                    updated_at = NOW()
                """,
                (user_key, email, name),
            )

        connection.commit()

    except Exception:
        if connection:
            connection.rollback()

    finally:
        if connection:
            connection.close()

    return get_user(user_key)


def save_subscription(user_key, subscription_id, status="created"):
    if not DATABASE_URL:
        return False

    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE minibot_users
                SET
                    razorpay_subscription_id = %s,
                    razorpay_status = %s,
                    updated_at = NOW()
                WHERE user_key = %s
                """,
                (subscription_id, status, user_key),
            )

        connection.commit()
        return True

    except Exception:
        if connection:
            connection.rollback()

        return False

    finally:
        if connection:
            connection.close()


# ============================================================
# DATABASE STARTUP
# ============================================================

database_ok, database_error = init_database()

if not database_ok:
    st.warning(
        "MiniBot database is not connected yet. "
        "AI features can still run, but Premium status cannot "
        "be stored permanently."
    )


# ============================================================
# USER IDENTITY
# ============================================================
# Google login can be connected later. For now we use a session
# identity so the database layer can be tested safely.
# This does NOT pretend that an anonymous session is a permanent
# customer identity.

if "minibot_session_id" not in st.session_state:
    st.session_state.minibot_session_id = str(uuid.uuid4())

USER_KEY = st.session_state.minibot_session_id

USER_EMAIL = None
USER_NAME = None

try:
    if hasattr(st, "user") and st.user.is_logged_in:
        USER_EMAIL = getattr(st.user, "email", None)
        USER_NAME = getattr(st.user, "name", None)

        if USER_EMAIL:
            USER_KEY = f"google:{USER_EMAIL.lower()}"
except Exception:
    pass


if database_ok:
    db_user = create_or_update_user(
        USER_KEY,
        USER_EMAIL,
        USER_NAME,
    )
else:
    db_user = None


# ============================================================
# GEMINI CONNECTION
# ============================================================

if not GEMINI_API_KEY:
    st.error("MiniBot is not connected to its AI service yet.")
    st.info("Add GEMINI_API_KEY to the Render environment variables.")
    st.stop()

try:
    client = genai.Client(
        api_key=GEMINI_API_KEY
    )
except Exception as error:
    st.error("MiniBot could not connect to the AI service.")
    st.code(str(error))
    st.stop()


# ============================================================
# SESSION STATE
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "message_count" not in st.session_state:
    st.session_state.message_count = 0

if "uploaded_file_name" not in st.session_state:
    st.session_state.uploaded_file_name = None


# Premium is read from the database.
# Never activate Premium merely because a payment button was clicked.

premium_from_database = bool(
    db_user and db_user.get("premium") is True
)

st.session_state.premium = premium_from_database


# ============================================================
# MINI BOT INSTRUCTIONS
# ============================================================

SYSTEM_INSTRUCTION = """
You are MiniBot, a friendly and highly useful Student AI Assistant.

Your purpose is to help students learn, understand concepts, study
from documents, practice questions, prepare for exams, and organize
their study.

PERSONALITY:
- Friendly
- Patient
- Encouraging
- Clear
- Helpful
- Never unnecessarily complicated

MAIN FEATURES:

1. CONCEPT EXPLANATION
Explain difficult topics in simple language.
Use step-by-step explanations.
Give examples when useful.

2. PROBLEM SOLVING
For numerical questions:
- Show the important steps.
- Explain formulas.
- Substitute values clearly.
- Give the final answer with units when appropriate.

3. STUDY NOTES
When the user provides study material:
- Identify important concepts.
- Organize information with headings.
- Use bullet points.
- Highlight formulas and definitions.
- Do not invent information.

4. PDF STUDY
When a PDF is uploaded:
- Read the document carefully.
- Answer questions using the document.
- Summarize it when requested.
- Create notes when requested.
- Create questions from the document when requested.

5. PRACTICE QUESTIONS
Create:
- Multiple choice questions
- Short-answer questions
- Conceptual questions
- Numerical questions when appropriate

Use the user's provided study material when available.

6. QUIZ MODE
When the user asks for Quiz Mode:
- Ask one question at a time.
- Wait for the user's answer.
- Tell the user whether it is correct.
- Explain the answer briefly.
- Continue to the next question.
- Keep track of score during the conversation.

7. STUDY PLANS
When asked for a study plan:
- Ask for exam date or available days if necessary.
- Divide topics into realistic sections.
- Include revision.
- Include practice.
- Include breaks when appropriate.
- Prioritize important topics.

8. IMAGES AND DIAGRAMS
When an image is provided:
- Analyze it carefully.
- Explain diagrams step by step.
- Read visible text when possible.
- Do not pretend to see information that is unclear.

IMPORTANT RULES:
- Use simple language.
- Teach the reasoning, not just the answer.
- Never deliberately invent facts.
- If information is uncertain, say so.
- Stay focused on the user's question.
- Do not unnecessarily repeat the entire conversation.
- Be concise unless the user asks for detail.
"""


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ MiniBot")

    st.write("### 🎓 AI Study Assistant")

    st.caption(
        "Learn smarter. Practice better. Prepare faster."
    )

    st.divider()

    # --------------------------------------------------------
    # FREE PLAN
    # --------------------------------------------------------

    st.write("### 🆓 Free Plan")

    st.write("✅ AI tutoring")
    st.write("✅ PDF study help")
    st.write("✅ Image & diagram analysis")
    st.write("✅ Practice questions")
    st.write("✅ Quiz Mode")
    st.write("✅ Study planning")

    if st.session_state.premium:
        st.success("💎 Premium Active")
        st.caption("Premium status is stored in the database.")
    else:
        st.caption(
            f"💬 {FREE_MESSAGE_LIMIT} free messages per session"
        )

    st.divider()

    # --------------------------------------------------------
    # PREMIUM
    # --------------------------------------------------------

    st.write("### 💎 Premium")

    st.caption("₹99/month")

    st.write(
        "Unlock unlimited AI study messages and premium "
        "study features."
    )

    if not st.session_state.premium:

        if st.button(
            "💎 Get Premium",
            use_container_width=True,
        ):

            if not DATABASE_URL:
                st.error(
                    "Database is not connected. "
                    "Premium cannot be activated safely yet."
                )

            elif (
                not RAZORPAY_KEY_ID
                or not RAZORPAY_KEY_SECRET
            ):
                st.warning("Razorpay is not connected yet.")

                st.info(
                    "Add RAZORPAY_KEY_ID and "
                    "RAZORPAY_KEY_SECRET to Render."
                )

            else:

                with st.spinner(
                    "Creating your Premium subscription..."
                ):

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

                        if response.status_code in (
                            200,
                            201,
                        ):

                            data = response.json()

                            subscription_url = data.get(
                                "short_url"
                            )

                            subscription_id = data.get(
                                "id"
                            )

                            if subscription_id:
                                save_subscription(
                                    USER_KEY,
                                    subscription_id,
                                    "created",
                                )

                            if subscription_url:

                                st.success(
                                    "Subscription created."
                                )

                                st.link_button(
                                    "💳 Continue to Payment",
                                    subscription_url,
                                    use_container_width=True,
                                )

                                st.caption(
                                    "Complete the Razorpay payment. "
                                    "Premium will only be activated "
                                    "after payment verification."
                                )

                            else:

                                st.error(
                                    "Razorpay did not return "
                                    "a payment link."
                                )

                                st.code(response.text)

                        else:

                            st.error(
                                "Razorpay could not create "
                                "the subscription."
                            )

                            st.code(response.text)

                    except Exception as error:

                        st.error(
                            "Razorpay connection failed."
                        )

                        st.code(str(error))

    else:

        st.success(
            "Premium features are available."
        )

    st.divider()

    # --------------------------------------------------------
    # MESSAGE COUNTER
    # --------------------------------------------------------

    if st.session_state.premium:

        st.write("💬 Messages: Unlimited")

    else:

        st.write(
            f"💬 Messages used: "
            f"{st.session_state.message_count}/"
            f"{FREE_MESSAGE_LIMIT}"
        )

    st.divider()

    # --------------------------------------------------------
    # CLEAR CHAT
    # --------------------------------------------------------

    if st.button(
        "🗑️ Clear Chat",
        use_container_width=True,
    ):

        st.session_state.messages = []
        st.session_state.message_count = 0
        st.session_state.uploaded_file_name = None

        st.rerun()


# ============================================================
# MAIN PAGE
# ============================================================

st.title("🤖 MiniBot")

st.markdown(
    "## 👋 Welcome to MiniBot!"
)

st.info(
    "🎓 Study smarter with AI — understand concepts, "
    "study from PDFs, practice with quizzes, and "
    "prepare for exams."
)


# ============================================================
# FEATURE CARDS
# ============================================================

st.markdown(
    """
    <div class="minibot-card">

    ### 🧠 Your AI Study Assistant

    MiniBot helps you understand concepts, study from PDFs,
    practice questions, analyze diagrams, create quizzes,
    and organize your study.

    </div>
    """,
    unsafe_allow_html=True,
)


st.write("### ✨ What MiniBot can do")

col1, col2 = st.columns(2)

with col1:
    st.write("🧠 Explain difficult topics")
    st.write("📄 Study from PDFs")
    st.write("📝 Create practice questions")

with col2:
    st.write("🎯 Interactive Quiz Mode")
    st.write("📅 Create study plans")
    st.write("🖼️ Understand diagrams")


st.divider()


# ============================================================
# DISPLAY PREVIOUS MESSAGES
# ============================================================

for message in st.session_state.messages:

    with st.chat_message(
        message["role"]
    ):

        st.markdown(
            message["content"]
        )


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
        "pdf",
    ],
)


# ============================================================
# DISPLAY IMAGE
# ============================================================

if uploaded_file is not None:

    if uploaded_file.type.startswith(
        "image/"
    ):

        try:

            image = Image.open(
                uploaded_file
            )

            st.image(
                image,
                caption="Uploaded image",
                use_container_width=True,
            )

        except Exception:

            st.error(
                "Could not read this image."
            )


# ============================================================
# CHAT INPUT
# ============================================================

user_message = st.chat_input(
    "💬 Ask MiniBot anything..."
)


if user_message:

    # --------------------------------------------------------
    # FREE LIMIT
    # --------------------------------------------------------

    if (
        not st.session_state.premium
        and st.session_state.message_count
        >= FREE_MESSAGE_LIMIT
    ):

        st.warning(
            "🛑 You have reached the 20-message "
            "Free Plan limit for this session."
        )

        st.info(
            "💎 Upgrade to Premium for unlimited messages."
        )

        st.stop()

    # --------------------------------------------------------
    # COUNT MESSAGE
    # --------------------------------------------------------

    st.session_state.message_count += 1

    # --------------------------------------------------------
    # SAVE USER MESSAGE
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # BUILD CONVERSATION
    # --------------------------------------------------------

    conversation_parts = []

    conversation_parts.append(
        SYSTEM_INSTRUCTION
    )

    conversation_parts.append(
        "\nCURRENT CONVERSATION:\n"
    )

    recent_messages = (
        st.session_state.messages[-20:]
    )

    for message in recent_messages:

        if message["role"] == "user":

            conversation_parts.append(
                f"User: {message['content']}"
            )

        elif message["role"] == "assistant":

            conversation_parts.append(
                f"MiniBot: {message['content']}"
            )

    conversation_parts.append(
        f"\n\nUser's latest question:\n{user_message}"
    )

    conversation_parts.append(
        "\n\nAnswer the user's latest question."
    )

    conversation_text = "\n\n".join(
        conversation_parts
    )

    contents = [
        conversation_text
    ]

    # --------------------------------------------------------
    # IMAGE
    # --------------------------------------------------------

    if uploaded_file is not None:

        if uploaded_file.type.startswith(
            "image/"
        ):

            try:

                image = Image.open(
                    uploaded_file
                )

                contents.append(
                    image
                )

            except Exception:
                pass

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    if uploaded_file is not None:

        if uploaded_file.type == "application/pdf":

            temp_path = None

            try:

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".pdf",
                ) as temp_pdf:

                    temp_pdf.write(
                        uploaded_file.getvalue()
                    )

                    temp_path = temp_pdf.name

                pdf_file = client.files.upload(
                    file=temp_path
                )

                contents.append(
                    pdf_file
                )

            except Exception as error:

                st.error(
                    "MiniBot could not process "
                    "the uploaded PDF."
                )

                st.code(
                    str(error)
                )

                st.stop()

            finally:

                if (
                    temp_path
                    and os.path.exists(temp_path)
                ):

                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass

    # --------------------------------------------------------
    # GENERATE AI RESPONSE
    # --------------------------------------------------------

    with st.chat_message(
        "assistant"
    ):

        with st.spinner(
            "MiniBot is thinking..."
        ):

            try:

                response = (
                    client.models.generate_content(
                        model=MODEL_NAME,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            temperature=0.7,
                            max_output_tokens=4096,
                        ),
                    )
                )

                answer = response.text

                if not answer:

                    answer = (
                        "I couldn't generate a response "
                        "this time. Please try again."
                    )

            except Exception as error:

                answer = (
                    "❌ MiniBot encountered an error "
                    "while generating the answer."
                )

                st.error(
                    str(error)
                )

        st.markdown(
            answer
        )

    # --------------------------------------------------------
    # SAVE ASSISTANT RESPONSE
    # --------------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
        }
    )
