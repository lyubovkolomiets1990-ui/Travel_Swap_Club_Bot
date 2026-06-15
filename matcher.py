from datetime import datetime
from db import get_active_trips, create_match, get_existing_match

# Категорії мандрівників — значення зберігається в БД
TRAVELER_TYPES = {
    "family":        "👨‍👩‍👧 Сім'я",
    "women":         "👩 Жінки",
    "digital_nomad": "💻 Digital nomad",
    "couple":        "💑 Пара",
    "solo":          "🧳 Соло",
    "anyone":        "🌍 Будь-хто",
}

# Що шукають — кого хочуть прийняти у своє житло
LOOKING_FOR_LABELS = {
    "family":        "👨‍👩‍👧 Сім'ї",
    "women":         "👩 Жінок",
    "digital_nomad": "💻 Digital nomads",
    "couple":        "💑 Пари",
    "solo":          "🧳 Соло-мандрівників",
    "anyone":        "🌍 Будь-кого",
}


def dates_overlap(from1: str, to1: str, from2: str, to2: str) -> bool:
    fmt = "%d.%m.%Y"
    try:
        f1, t1 = datetime.strptime(from1, fmt), datetime.strptime(to1, fmt)
        f2, t2 = datetime.strptime(from2, fmt), datetime.strptime(to2, fmt)
        return f1 <= t2 and f2 <= t1
    except ValueError:
        return False


def types_compatible(a_looking_for: str, b_type: str,
                     b_looking_for: str, a_type: str) -> bool:
    """
    Матч можливий якщо:
    - A шукає тип B (або A шукає «будь-кого»)
    - B шукає тип A (або B шукає «будь-кого»)
    """
    a_ok = a_looking_for == "anyone" or a_looking_for == b_type
    b_ok = b_looking_for == "anyone" or b_looking_for == a_type
    return a_ok and b_ok


async def find_matches(new_trip: dict) -> list[dict]:
    """
    Умови матчу:
    1. A їде до міста/країни B, і B їде до міста/країни A
    2. Дати перетинаються
    3. Типи мандрівників сумісні (looking_for ↔ traveler_type)
    """
    all_trips = await get_active_trips()
    matches_found = []

    for trip in all_trips:
        if trip["id"] == new_trip.get("id"):
            continue

        # Географія
        a_goes_to_b = (
            new_trip["destination_city"].lower() == trip["home_city"].lower()
            and new_trip["destination_country"].lower() == trip["home_country"].lower()
        )
        b_goes_to_a = (
            trip["destination_city"].lower() == new_trip["home_city"].lower()
            and trip["destination_country"].lower() == new_trip["home_country"].lower()
        )
        if not (a_goes_to_b and b_goes_to_a):
            continue

        # Дати
        if not dates_overlap(
            new_trip["date_from"], new_trip["date_to"],
            trip["date_from"], trip["date_to"]
        ):
            continue

        # Тип мандрівника
        if not types_compatible(
            new_trip.get("looking_for", "anyone"),
            trip.get("traveler_type", "anyone"),
            trip.get("looking_for", "anyone"),
            new_trip.get("traveler_type", "anyone"),
        ):
            continue

        # Дублікат
        existing = await get_existing_match(new_trip["id"], trip["id"])
        if existing:
            continue

        matches_found.append(dict(trip))

    return matches_found


async def save_match(trip_id_1: int, trip_id_2: int) -> int:
    return await create_match(trip_id_1, trip_id_2)
