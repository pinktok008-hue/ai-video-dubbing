def translate_text(text, target_language):
    return {
        "status": "success",
        "original_text": text,
        "translated_text": f"[{target_language}] {text}"
    }
