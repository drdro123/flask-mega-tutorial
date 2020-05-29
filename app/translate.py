import json

from flask import current_app
import requests
from flask_babel import _


def translate(text, target_language):
    if not current_app.config.get("LANGUAGE_API_KEY"):
        return "Configuration error"

    url = "https://translate.yandex.net/api/v1.5/tr.json/translate"

    body = {
        "key": current_app.config["LANGUAGE_API_KEY"],
        "text": text,
        "lang": target_language,
    }
    r = requests.post(url, data=body)

    if r.status_code != 200:
        return "Connection error."
    return json.loads(r.content.decode("utf-8-sig"))
