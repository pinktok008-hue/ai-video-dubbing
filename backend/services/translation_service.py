"""
AI Video Dubbing Platform
Version 2.0

Translation Service
"""

from deep_translator import GoogleTranslator

from core.logger import task_log, task_error


def translate_text(
    text: str,
    target_language: str,
    source_language: str = "auto",
    task_id: str | None = None
) -> dict:
    """
    Translate text using Google Translator.

    Returns
    -------
    {
        "status": "success",
        "translated_text": "...",
        "source_language": "...",
        "target_language": "..."
    }
    """

    try:

        if not text.strip():
            return {
                "status": "error",
                "message": "Empty text."
            }

        if task_id:
            task_log(
                task_id,
                "Translation",
                f"Started ({source_language} -> {target_language})"
            )

        translator = GoogleTranslator(
            source=source_language,
            target=target_language
        )

        translated = translator.translate(text)

        if task_id:
            task_log(
                task_id,
                "Translation",
                "Completed"
            )

        return {
            "status": "success",
            "translated_text": translated,
            "source_language": source_language,
            "target_language": target_language
        }

    except Exception as e:

        if task_id:
            task_error(
                task_id,
                "Translation",
                str(e)
            )

        return {
            "status": "error",
            "message": str(e)
        }
