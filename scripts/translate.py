"""Translate locales/<source>.json into target languages using DeepL."""
import json
import os
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


def translate(texts, lang):
    code = DEEPL_CODES.get(lang, lang.upper())
    r = requests.post(
        URL,
        headers={"Authorization": f"DeepL-Auth-Key {KEY}"},
        json={"text": texts, "source_lang": SOURCE.upper(), "target_lang": code},
        timeout=60,
    )
    r.raise_for_status()
    return [t["text"] for t in r.json()["translations"]]


def main():
    if not KEY:
        sys.exit("DEEPL_API_KEY is not set")
    src = json.loads((DIR / f"{SOURCE}.json").read_text(encoding="utf-8"))
    keys = list(src)
    for lang in (t.strip() for t in TARGETS if t.strip()):
        out = dict(zip(keys, translate([src[k] for k in keys], lang)))
        (DIR / f"{lang}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"wrote {lang}.json")


if __name__ == "__main__":
    main()
