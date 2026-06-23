import aiosqlite
from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                name TEXT,
                home_city TEXT,
                home_country TEXT,
                home_description TEXT,
                home_photos TEXT DEFAULT '',
                has_pets INTEGER DEFAULT 0,
                pets_info TEXT DEFAULT '',
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                destination_city TEXT NOT NULL,
                destination_country TEXT NOT NULL,
                date_from TEXT NOT NULL,
                date_to TEXT NOT NULL,
                guests_count INTEGER DEFAULT 2,
                looking_for TEXT DEFAULT 'anyone',
                traveler_type TEXT DEFAULT 'anyone',
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id_1 INTEGER NOT NULL,
                trip_id_2 INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trip_id_1) REFERENCES trips(id),
                FOREIGN KEY (trip_id_2) REFERENCES trips(id)
            )
        """)
        # Відгуки після завершення обміну
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                reviewer_id INTEGER NOT NULL,
                reviewee_id INTEGER NOT NULL,
                cleanliness INTEGER NOT NULL CHECK(cleanliness BETWEEN 1 AND 5),
                communication INTEGER NOT NULL CHECK(communication BETWEEN 1 AND 5),
                rule_following INTEGER NOT NULL CHECK(rule_following BETWEEN 1 AND 5),
                overall INTEGER NOT NULL CHECK(overall BETWEEN 1 AND 5),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (match_id) REFERENCES matches(id),
                FOREIGN KEY (reviewer_id) REFERENCES users(id),
                FOREIGN KEY (reviewee_id) REFERENCES users(id),
                UNIQUE(match_id, reviewer_id)
            )
        """)
        # Лайки — збережені хости
        await db.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_user_id) REFERENCES users(id),
                FOREIGN KEY (to_user_id) REFERENCES users(id),
                UNIQUE(from_user_id, to_user_id)
            )
        """)
        # Додаємо нові поля якщо їх ще немає (для існуючих БД)
        for col, default in [
            ("home_photos", "''"),
            ("has_pets", "0"),
            ("pets_info", "''"),
            ("extra_info", "''"),
        ]:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT {default}")
            except Exception:
                pass
        try:
            await db.execute("ALTER TABLE matches ADD COLUMN reminder_sent INTEGER DEFAULT 0")
        except Exception:
            pass
        await db.commit()
    print("✅ База даних ініціалізована")


async def get_user(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            return await cursor.fetchone()


async def create_user(telegram_id: int, name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, name) VALUES (?, ?)",
            (telegram_id, name),
        )
        await db.commit()


async def update_user_home(telegram_id: int, city: str, country: str,
                           description: str, photos: str = "",
                           has_pets: int = 0, pets_info: str = "",
                           extra_info: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE users SET home_city=?, home_country=?, home_description=?,
               home_photos=?, has_pets=?, pets_info=?, extra_info=?
               WHERE telegram_id=?""",
            (city, country, description, photos, has_pets, pets_info, extra_info, telegram_id),
        )
        await db.commit()


async def create_trip(user_id: int, dest_city: str, dest_country: str,
                      date_from: str, date_to: str, guests: int,
                      looking_for: str = "anyone", traveler_type: str = "anyone") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO trips (user_id, destination_city, destination_country,
               date_from, date_to, guests_count, looking_for, traveler_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, dest_city, dest_country, date_from, date_to,
             guests, looking_for, traveler_type),
        )
        await db.commit()
        return cursor.lastrowid


async def update_trip_dates(trip_id: int, date_from: str, date_to: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE trips SET date_from=?, date_to=? WHERE id=?",
            (date_from, date_to, trip_id),
        )
        await db.commit()


async def mark_trip_completed(trip_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE trips SET status='completed' WHERE id=?", (trip_id,)
        )
        await db.commit()


async def get_trip_by_id(trip_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM trips WHERE id=?", (trip_id,)
        ) as cursor:
            return await cursor.fetchone()


async def mark_expired_trips_completed() -> int:
    """Позначає 'completed' усі активні поїздки де date_to вже минула.
    Поїздки з гнучкими датами ('гнучко') не торкаємось — вони не мають дедлайну."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, date_to FROM trips WHERE status='active' AND date_to != 'гнучко'"
        ) as cursor:
            rows = await cursor.fetchall()

        from datetime import datetime
        today = datetime.now().date()
        fmt = "%d.%m.%Y"
        expired_ids = []
        for row in rows:
            try:
                date_to = datetime.strptime(row["date_to"], fmt).date()
                if date_to < today:
                    expired_ids.append(row["id"])
            except ValueError:
                continue

        for trip_id in expired_ids:
            await db.execute("UPDATE trips SET status='completed' WHERE id=?", (trip_id,))
        await db.commit()
        return len(expired_ids)


async def get_trips_ending_tomorrow() -> list:
    """Активні поїздки де date_to — це завтра (для попередження за 1 день)"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT t.*, u.telegram_id, u.name
               FROM trips t JOIN users u ON t.user_id = u.id
               WHERE t.status='active' AND t.date_to != 'гнучко'"""
        ) as cursor:
            rows = await cursor.fetchall()

        from datetime import datetime, timedelta
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        fmt = "%d.%m.%Y"
        result = []
        for row in rows:
            try:
                date_to = datetime.strptime(row["date_to"], fmt).date()
                if date_to == tomorrow:
                    result.append(row)
            except ValueError:
                continue
        return result


async def get_active_trips():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT t.*, u.telegram_id, u.name, u.home_city, u.home_country,
                      u.home_description, u.home_photos, u.has_pets, u.pets_info,
                      u.extra_info
               FROM trips t JOIN users u ON t.user_id = u.id
               WHERE t.status = 'active'"""
        ) as cursor:
            return await cursor.fetchall()


async def create_match(trip_id_1: int, trip_id_2: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO matches (trip_id_1, trip_id_2) VALUES (?, ?)",
            (trip_id_1, trip_id_2),
        )
        await db.commit()
        return cursor.lastrowid


async def get_match(match_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM matches WHERE id = ?", (match_id,)
        ) as cursor:
            return await cursor.fetchone()


async def update_match_status(match_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE matches SET status=? WHERE id=?", (status, match_id)
        )
        await db.commit()


async def get_user_trips(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT t.* FROM trips t
               JOIN users u ON t.user_id = u.id
               WHERE u.telegram_id = ? AND t.status = 'active'
               ORDER BY t.created_at DESC""",
            (telegram_id,),
        ) as cursor:
            return await cursor.fetchall()


async def get_existing_match(trip_id_1: int, trip_id_2: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM matches WHERE
               (trip_id_1=? AND trip_id_2=?) OR (trip_id_1=? AND trip_id_2=?)""",
            (trip_id_1, trip_id_2, trip_id_2, trip_id_1),
        ) as cursor:
            return await cursor.fetchone()


# ── Відгуки ──────────────────────────────────────────────────────────────────

async def create_review(match_id: int, reviewer_id: int, reviewee_id: int,
                        cleanliness: int, communication: int,
                        rule_following: int, overall: int, comment: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO reviews
               (match_id, reviewer_id, reviewee_id, cleanliness,
                communication, rule_following, overall, comment)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (match_id, reviewer_id, reviewee_id, cleanliness,
             communication, rule_following, overall, comment),
        )
        await db.commit()


async def get_review(match_id: int, reviewer_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM reviews WHERE match_id=? AND reviewer_id=?",
            (match_id, reviewer_id),
        ) as cursor:
            return await cursor.fetchone()


async def get_both_reviews(match_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM reviews WHERE match_id=?", (match_id,)
        ) as cursor:
            return await cursor.fetchall()


async def get_user_rating(user_db_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT
                 AVG(cleanliness)    AS cleanliness,
                 AVG(communication)  AS communication,
                 AVG(rule_following) AS rule_following,
                 AVG(overall)        AS overall,
                 COUNT(*)            AS total
               FROM reviews WHERE reviewee_id=?""",
            (user_db_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row or not row["total"]:
                return {}
            avg = (row["cleanliness"] + row["communication"] +
                   row["rule_following"] + row["overall"]) / 4
            return {
                "cleanliness":    round(row["cleanliness"], 1),
                "communication":  round(row["communication"], 1),
                "rule_following": round(row["rule_following"], 1),
                "overall":        round(row["overall"], 1),
                "average":        round(avg, 1),
                "total":          row["total"],
            }


# ── Лайки ────────────────────────────────────────────────────────────────────

async def _get_user_id_by_tg(db, telegram_id: int):
    async with db.execute(
        "SELECT id FROM users WHERE telegram_id=?", (telegram_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else None


async def add_like(from_telegram_id: int, to_telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        from_id = await _get_user_id_by_tg(db, from_telegram_id)
        to_id = await _get_user_id_by_tg(db, to_telegram_id)
        if from_id and to_id:
            await db.execute(
                "INSERT OR IGNORE INTO likes (from_user_id, to_user_id) VALUES (?, ?)",
                (from_id, to_id),
            )
            await db.commit()


async def remove_like(from_telegram_id: int, to_telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        from_id = await _get_user_id_by_tg(db, from_telegram_id)
        to_id = await _get_user_id_by_tg(db, to_telegram_id)
        if from_id and to_id:
            await db.execute(
                "DELETE FROM likes WHERE from_user_id=? AND to_user_id=?",
                (from_id, to_id),
            )
            await db.commit()


async def get_liked_users(from_telegram_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT u.* FROM users u
               JOIN likes l ON l.to_user_id = u.id
               JOIN users u2 ON l.from_user_id = u2.id
               WHERE u2.telegram_id = ?
               ORDER BY l.created_at DESC""",
            (from_telegram_id,),
        ) as cursor:
            return await cursor.fetchall()


# ── Блокування місяців (календар доступності) ────────────────────────────────

async def init_calendar_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blocked_months (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                month INTEGER NOT NULL,
                year INTEGER NOT NULL,
                reason TEXT DEFAULT '',
                UNIQUE(telegram_id, month, year)
            )
        """)
        await db.commit()


async def block_month(telegram_id: int, month: int, year: int, reason: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO blocked_months (telegram_id, month, year, reason) VALUES (?,?,?,?)",
            (telegram_id, month, year, reason),
        )
        await db.commit()


async def unblock_month(telegram_id: int, month: int, year: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM blocked_months WHERE telegram_id=? AND month=? AND year=?",
            (telegram_id, month, year),
        )
        await db.commit()


async def get_blocked_months(telegram_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM blocked_months WHERE telegram_id=? ORDER BY year, month",
            (telegram_id,),
        ) as cursor:
            return await cursor.fetchall()


async def is_month_blocked(telegram_id: int, month: int, year: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM blocked_months WHERE telegram_id=? AND month=? AND year=?",
            (telegram_id, month, year),
        ) as cursor:
            return await cursor.fetchone() is not None


async def get_pending_matches() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM matches WHERE status='pending' ORDER BY created_at",
        ) as cursor:
            return await cursor.fetchall()


async def mark_reminder_sent(match_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE matches SET reminder_sent=1 WHERE id=?", (match_id,)
        )
        await db.commit()


async def get_all_users_with_home() -> list:
    """Всі користувачі у кого є профіль з житлом"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT u.*,
                t.id as trip_id,
                t.destination_city,
                t.destination_country,
                t.date_from,
                t.date_to,
                t.guests_count,
                t.looking_for,
                t.traveler_type
               FROM users u
               LEFT JOIN trips t ON t.user_id = u.id AND t.status = 'active'
               WHERE u.home_city IS NOT NULL AND u.home_city != ''
               GROUP BY u.id
               ORDER BY t.date_from ASC, u.registered_at DESC"""
        ) as cursor:
            return await cursor.fetchall()


# ── Перегляди в browse (щоб не показувати повторно) ──────────────────────────

async def init_views_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS browse_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                viewer_telegram_id INTEGER NOT NULL,
                viewed_telegram_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(viewer_telegram_id, viewed_telegram_id)
            )
        """)
        await db.commit()


async def mark_viewed(viewer_tg_id: int, viewed_tg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO browse_views (viewer_telegram_id, viewed_telegram_id) VALUES (?, ?)",
            (viewer_tg_id, viewed_tg_id),
        )
        await db.commit()


async def get_viewed_ids(viewer_tg_id: int) -> set:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT viewed_telegram_id FROM browse_views WHERE viewer_telegram_id=?",
            (viewer_tg_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return {r[0] for r in rows}


async def delete_user_profile(telegram_id: int):
    """Повністю видаляє користувача і всі пов'язані дані: поїздки, лайки, перегляди, відгуки."""
    user = await get_user(telegram_id)
    if not user:
        return False
    user_db_id = user["id"]

    async with aiosqlite.connect(DB_PATH) as db:
        # Видаляємо поїздки і пов'язані матчі
        cursor = await db.execute("SELECT id FROM trips WHERE user_id=?", (user_db_id,))
        trip_ids = [row[0] for row in await cursor.fetchall()]

        for trip_id in trip_ids:
            await db.execute(
                "DELETE FROM matches WHERE trip_id_1=? OR trip_id_2=?",
                (trip_id, trip_id),
            )
        await db.execute("DELETE FROM trips WHERE user_id=?", (user_db_id,))

        # Видаляємо лайки де користувач учасник (за telegram_id)
        await db.execute(
            "DELETE FROM likes WHERE from_user_id=? OR to_user_id=?",
            (user_db_id, user_db_id),
        )

        # Видаляємо історію переглядів browse
        await db.execute(
            "DELETE FROM browse_views WHERE viewer_telegram_id=? OR viewed_telegram_id=?",
            (telegram_id, telegram_id),
        )

        # Видаляємо заблоковані місяці календаря
        await db.execute(
            "DELETE FROM blocked_months WHERE telegram_id=?",
            (telegram_id,),
        )

        # Видаляємо відгуки де користувач учасник
        await db.execute(
            "DELETE FROM reviews WHERE reviewer_id=? OR reviewee_id=?",
            (user_db_id, user_db_id),
        )

        # Видаляємо сам профіль
        await db.execute("DELETE FROM users WHERE telegram_id=?", (telegram_id,))
        await db.commit()

    return True


async def get_all_known_cities() -> list:
    """Всі унікальні міста (домашні і призначення) для нечіткого пошуку схожості"""
    async with aiosqlite.connect(DB_PATH) as db:
        cities = set()
        async with db.execute("SELECT DISTINCT home_city FROM users WHERE home_city IS NOT NULL AND home_city != ''") as cursor:
            for row in await cursor.fetchall():
                cities.add(row[0])
        async with db.execute("SELECT DISTINCT destination_city FROM trips WHERE destination_city IS NOT NULL AND destination_city != ''") as cursor:
            for row in await cursor.fetchall():
                cities.add(row[0])
        return list(cities)
