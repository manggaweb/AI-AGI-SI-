"""Translate locales/<source>.json into target languages using DeepL."""
import json
import os
import re
import sys
from pathlib import Path

import requests

SOURCE = os.environ.get("SOURCE_LANG", "en")
TARGETS = os.environ.get("TARGET_LANGS", "zh-CN,ja,fr,de").split(",")
DIR = Path(os.environ.get("LOCALES_DIR", "locales"))
KEY = os.environ.get("DEEPL_API_KEY")
URL = os.environ.get(
    "DEEPL_API_URL",
    "https://api-free.deepl.com/v2/translate"
    if (KEY or "").endswith(":fx")
    else "https://api.deepl.com/v2/translate",
)
DEEPL_CODES = {"zh-CN": "ZH"}
LANGUAGE_CODE = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z]{2,4})?")
MAX_TEXTS_PER_REQUEST = 50
MAX_REQUEST_BODY_BYTES = 128 * 1024


def request_body(texts, lang):
    """Build the exact JSON bytes sent to DeepL."""
    payload = {
        "text": texts,
        "source_lang": SOURCE.upper(),
        "target_lang": DEEPL_CODES.get(lang, lang.upper()),
    }
    return json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def batch_texts(texts, lang):
    """Yield batches that stay within DeepL's item and body-size limits."""
    batch = []
    for text in texts:
        if not isinstance(text, str):
            raise ValueError("Locale values must be strings")

        candidate = [*batch, text]
        if (
            len(candidate) <= MAX_TEXTS_PER_REQUEST
            and len(request_body(candidate, lang)) <= MAX_REQUEST_BODY_BYTES
        ):
            batch = candidate
            continue

        if batch:
            yield batch
            batch = []

        if len(request_body([text], lang)) > MAX_REQUEST_BODY_BYTES:
            raise ValueError(
                "A single locale value exceeds DeepL's request-size limit"
            )
        batch = [text]

    if batch:
        yield batch


def translate(texts, lang):
    translated = []
    for batch in batch_texts(texts, lang):
        response = requests.post(
            URL,
            headers={
                "Authorization": f"DeepL-Auth-Key {KEY}",
                "Content-Type": "application/json",
            },
            data=request_body(batch, lang),
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        translations = (
            payload.get("translations") if isinstance(payload, dict) else None
        )
        if not isinstance(translations, list) or len(translations) != len(batch):
            raise RuntimeError(
                f"DeepL returned an invalid translation count for {lang}"
            )
        for translation in translations:
            if not isinstance(translation, dict) or not isinstance(
                translation.get("text"), str
            ):
                raise RuntimeError(
                    f"DeepL returned an invalid translation for {lang}"
                )
            translated.append(translation["text"])
    return translated


def validate_language_code(value, name):
    if not LANGUAGE_CODE.fullmatch(value):
        raise ValueError(f"{name} is not a valid language code: {value!r}")
    return value


def load_source():
    validate_language_code(SOURCE, "SOURCE_LANG")
    source_path = DIR / f"{SOURCE}.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise ValueError(f"{source_path} must contain a JSON object")
    return source


def main():
    if not KEY:
        sys.exit("DEEPL_API_KEY is not set")

    source = load_source()
    keys = list(source)
    languages = list(
        dict.fromkeys(
            validate_language_code(target.strip(), "TARGET_LANGS")
            for target in TARGETS
            if target.strip()
        )
    )
    if not languages:
        raise ValueError("TARGET_LANGS must contain at least one language code")

    outputs = {}
    values = [source[key] for key in keys]
    for lang in languages:
        translated = translate(values, lang)
        outputs[lang] = dict(zip(keys, translated, strict=True))

    for lang, output in outputs.items():
        (DIR / f"{lang}.json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {lang}.json")


if __name__ == "__main__":
    main()
