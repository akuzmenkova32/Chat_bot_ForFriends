import re
from typing import List, Tuple, Dict
from datetime import datetime, timedelta

# Simple heuristics parser. Works with free-form Russian inputs.
DAY_WORDS = {
    "пн": "monday", "пон": "monday", "понедельник": "monday",
    "вт": "tuesday", "вторник": "tuesday", "втo": "tuesday",
    "ср": "wednesday", "среда": "wednesday",
    "чт": "thursday", "четверг": "thursday",
    "пт": "friday", "пятница": "friday",
    "сб": "saturday", "суббота": "saturday",
    "вс": "sunday", "воскресенье": "sunday",
}

def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def extract_time_place_format(text: str) -> Tuple[List[str], List[str], List[str]]:
    text = text.lower()
    times, places, formats = [], [], []

    # crude split by lines / semicolons
    parts = re.split(r"[\n;]+", text)
    for p in parts:
        p = normalize_whitespace(p)
        if not p:
            continue

        # detect explicit time/date hints
        if re.search(r"\b(сегодня|завтра|послезавтра|пн|вт|ср|чт|пт|сб|вс|\d{1,2}[./]\d{1,2})\b", p) or re.search(r"\b\d{1,2}:\d{2}\b", p):
            times.append(p)
            continue

        # detect common format keywords
        if re.search(r"\b(бар|паб|дом|кино|прогулк|настолк|вечеринк|клуб|кафе|ресторан|пикник)\b", p):
            formats.append(p)
            continue

        # otherwise treat as place candidate
        places.append(p)

    return uniq(times), uniq(places), uniq(formats)

def uniq(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        x = normalize_whitespace(x)
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out

def format_options(opts: List[str], letters=None) -> str:
    letters = letters or "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "\n".join([f"{letters[i]}) {o}" for i, o in enumerate(opts)])

def parse_hours(arg: str):
    m = re.search(r"(\d{1,2})\s*ч", arg)
    if m:
        return int(m.group(1))
    try:
        return int(arg)
    except:
        return None
