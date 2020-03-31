import json
import os
from collections import defaultdict
from copy import copy
from typing import Dict

from jinja2 import Template

CACHE = None
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


def localize(message: str, lang: str, **kwargs) -> str:
    lang = lang or "en"
    template = Template(message)
    result = template.render(**localizations_for(lang))
    if kwargs:
        template = Template(result)
        result = template.render(**kwargs)
    return result


def localizations_for(lang: str) -> Dict[str, str]:
    if CACHE is None:
        _populate_cache()
    return CACHE[lang]


def _populate_cache():
    global CACHE
    CACHE = defaultdict(dict)
    with open(os.path.join(__location__, "drill_content/translations.json")) as f:
        data = f.read()
        raw_translations = json.loads(data)
        for entry in raw_translations["instructions"]:
            CACHE[entry["language"]][entry["label"]] = entry["translation"]
