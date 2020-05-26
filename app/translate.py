import json

import requests

from app import app


def translate(text, target_language):
    if not app.config.get("LANGUAGE_API_KEY"):
        return "Configuration error"

    url = "https://translate.yandex.net/api/v1.5/tr.json/translate"

    body = {
        "key": app.config["LANGUAGE_API_KEY"],
        "text": text,
        "lang": target_language,
    }
    r = requests.post(url, data=body)

    if r.status_code != 200:
        return "Connection error."
    return json.loads(r.content.decode("utf-8-sig"))
