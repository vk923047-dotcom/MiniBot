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
