import html
import re

import requests


TRANSLATION_URL = "https://api.mymemory.translated.net/get"
TRANSLATION_CHUNK_SIZE = 450


class TranslationError(Exception):
    pass


def split_translation_chunks(text, max_length=TRANSLATION_CHUNK_SIZE):
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []

    chunks = []
    for paragraph in normalized.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        sentences = re.split(r"(?<=[.!?])\s+", paragraph)
        current = ""
        for sentence in sentences:
            while len(sentence) > max_length:
                if current:
                    chunks.append(current)
                    current = ""
                split_at = sentence.rfind(" ", 0, max_length)
                if split_at <= 0:
                    split_at = max_length
                chunks.append(sentence[:split_at].strip())
                sentence = sentence[split_at:].strip()

            candidate = f"{current} {sentence}".strip()
            if current and len(candidate) > max_length:
                chunks.append(current)
                current = sentence
            else:
                current = candidate
        if current:
            chunks.append(current)
    return chunks


def translate_description(text, *, session=None):
    chunks = split_translation_chunks(text)
    if not chunks:
        return ""

    http = session or requests.Session()
    translated_chunks = []
    for chunk in chunks:
        try:
            response = http.get(
                TRANSLATION_URL,
                params={"q": chunk, "langpair": "en|th"},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise TranslationError("Thai translation service is unavailable.") from error

        translated = payload.get("responseData", {}).get("translatedText", "")
        if payload.get("responseStatus") != 200 or not translated:
            raise TranslationError("Thai translation could not be completed.")
        translated_chunks.append(html.unescape(translated).strip())

    translation = "\n".join(translated_chunks).strip()
    return translation.strip(" '\"“”‘’").strip()
