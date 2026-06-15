import os
from groq import Groq

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

def translate_text(text, target_language):

    prompt = f"""
Translate the following text into {target_language}.

Text:
{text}

Return only the translated text.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    translated_text = (
        response.choices[0]
        .message
        .content
    )

    return {
        "status": "success",
        "original_text": text,
        "translated_text": translated_text
    }
