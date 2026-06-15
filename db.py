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
        ]:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT {default}")
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
                           has_pets: int = 0, pets_info: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE users SET home_city=?, home_country=?, home_description=?,
               home_photos=?, has_pets=?, pets_info=?
               WHERE telegram_id=?""",
            (city, country, description, photos, has_pets, pets_info, telegram_id),
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


async def get_active_trips():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT t.*, u.telegram_id, u.name, u.home_city, u.home_country,
                      u.home_description
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
