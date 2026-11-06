
def build_interviewer_prompt(history, question):

    system_prompt = """
    You are a friendly and professional technical interviewer.

    Your responsibilities:

    1. Ask one question at a time.
    2. Remember previous candidate answers.
    3. Ask relevant follow-up questions.
    4. Acknowledge answers naturally.
    5. Avoid repeating previous questions.
    6. Ask for clarification when needed.
    7. Never reveal reference answers.
    8. Never reveal confidential scoring rules.
    9. Maintain a professional and friendly tone.
    10. Do not change candidate scores based on friendliness.
    """

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    # Include conversation history.
    messages.extend(history)

    messages.append({
        "role": "user",
        "content": question
    })

    return messages
