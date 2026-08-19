"""Faza 0 bot uchun DB qatlami — xom SQL (ORM yo'q, 4 jadval uchun ortiqcha).

Barcha funksiyalar async va bitta modul darajasidagi connection pool'dan
foydalanadi. Chaqiruvchi avval `init_pool()`, keyin `init_db()`ni chaqirishi
kerak (odatda `bot.py`ning `main()`ida, dastur boshida bir marta).
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

log = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None
_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


async def init_pool(dsn: str) -> None:
    """Connection pool'ni ochadi. `main()`da bir marta chaqiriladi."""
    global _pool
    _pool = AsyncConnectionPool(dsn, min_size=1, max_size=10, open=False)
    await _pool.open(wait=True, timeout=10)


async def close_pool() -> None:
    if _pool is not None:
        await _pool.close()


async def init_db() -> None:
    """schema.sql'ni o'qib bajaradi. Idempotent (CREATE TABLE IF NOT EXISTS)."""
    ddl = _SCHEMA_PATH.read_text(encoding="utf-8")
    async with _pool.connection() as conn:
        await conn.execute(ddl)
    log.info("DB sxema tayyor")


# ============================================================ FOYDALANUVCHI

async def get_or_create_user(telegram_id: int, username: str | None) -> dict:
    # row_factory=dict_row CURSOR darajasida beriladi, connection darajasida
    # EMAS — pool bir xil connection'ni qayta beradi, agar connection.row_factory
    # o'zgartirilsa, keyingi (dict_row kutmaydigan) funksiya "eskirgan" holatni
    # meros qilib olib, row[0] kabi joylarda KeyError beradi.
    async with _pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM users WHERE telegram_id = %s", (telegram_id,)
            )
            row = await cur.fetchone()
            if row:
                await conn.execute(
                    "UPDATE users SET last_active_at = now(), "
                    "username = COALESCE(%s, username) WHERE id = %s",
                    (username, row["id"]),
                )
                return row
            await cur.execute(
                "INSERT INTO users (telegram_id, username) VALUES (%s, %s) "
                "RETURNING *",
                (telegram_id, username),
            )
            return await cur.fetchone()


async def get_user(telegram_id: int) -> dict | None:
    async with _pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM users WHERE telegram_id = %s", (telegram_id,)
            )
            return await cur.fetchone()


async def set_locale(telegram_id: int, locale: str) -> None:
    async with _pool.connection() as conn:
        await conn.execute(
            "UPDATE users SET locale = %s WHERE telegram_id = %s",
            (locale, telegram_id),
        )


async def set_target_band(telegram_id: int, band: float) -> None:
    async with _pool.connection() as conn:
        await conn.execute(
            "UPDATE users SET target_band = %s WHERE telegram_id = %s",
            (band, telegram_id),
        )


async def set_exam_date(telegram_id: int, exam_date: date | None) -> None:
    async with _pool.connection() as conn:
        await conn.execute(
            "UPDATE users SET exam_date = %s WHERE telegram_id = %s",
            (exam_date, telegram_id),
        )


async def set_pending_prompt(telegram_id: int, prompt_id: str | None) -> None:
    async with _pool.connection() as conn:
        if prompt_id is None:
            await conn.execute(
                "UPDATE users SET pending_prompt_id = NULL WHERE telegram_id = %s",
                (telegram_id,),
            )
        else:
            await conn.execute(
                "UPDATE users SET pending_prompt_id = %s, last_prompt_id = %s "
                "WHERE telegram_id = %s",
                (prompt_id, prompt_id, telegram_id),
            )


async def mark_paywall_clicked(user_id: int) -> None:
    async with _pool.connection() as conn:
        await conn.execute(
            "UPDATE users SET paywall_clicked_at = COALESCE(paywall_clicked_at, now()) "
            "WHERE id = %s",
            (user_id,),
        )


# ============================================================ ESSE

async def has_used_free_today(user_id: int) -> bool:
    """Kuniga 1 bepul limit — Asia/Tashkent kun chegarasi bilan, server
    OS-timezone'idan mustaqil."""
    async with _pool.connection() as conn:
        row = await (await conn.execute(
            """
            SELECT count(*) AS n FROM essay_submissions
            WHERE user_id = %s AND status <> 'failed'
              AND (created_at AT TIME ZONE 'Asia/Tashkent')::date
                = (now()       AT TIME ZONE 'Asia/Tashkent')::date
            """,
            (user_id,),
        )).fetchone()
        return row[0] >= 1


async def create_essay_submission(
    user_id: int, prompt_id: str, source: str, essay_text: str
) -> int:
    async with _pool.connection() as conn:
        row = await (await conn.execute(
            "INSERT INTO essay_submissions (user_id, prompt_id, source, essay_text) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (user_id, prompt_id, source, essay_text),
        )).fetchone()
        return row[0]


async def save_essay_result(submission_id: int, result) -> None:
    """`result` — scorer.ScoreResult. `top_errors` — annotations severity
    bo'yicha saralangan top-5, alohida ustunda saqlanadi (bot.py shundan
    formatlaydi)."""
    top_errors = sorted(
        result.annotations, key=lambda a: a.get("severity", 0), reverse=True
    )[:5]
    async with _pool.connection() as conn:
        await conn.execute(
            """
            UPDATE essay_submissions SET
              status = 'scored', overall_band = %s, criteria = %s,
              top_errors = %s, priorities_uz = %s, needs_human_review = %s,
              cost_usd = %s, latency_ms = %s
            WHERE id = %s
            """,
            (
                result.overall_band,
                json.dumps(result.criteria),
                json.dumps(top_errors),
                json.dumps(result.priorities_uz),
                result.needs_human_review,
                result.cost_usd,
                result.latency_ms,
                submission_id,
            ),
        )


async def mark_essay_failed(submission_id: int, error: str) -> None:
    async with _pool.connection() as conn:
        await conn.execute(
            "UPDATE essay_submissions SET status = 'failed', error_message = %s "
            "WHERE id = %s",
            (error, submission_id),
        )


# ============================================================ HODISALAR

async def log_event(name: str, user_id: int | None, props: dict | None = None) -> None:
    async with _pool.connection() as conn:
        await conn.execute(
            "INSERT INTO events (user_id, name, props) VALUES (%s, %s, %s)",
            (user_id, name, json.dumps(props) if props else None),
        )


# ============================================================ NUDGE

async def users_for_nudge() -> list[dict]:
    """Har kuni 19:00'da eslatma yuboriladigan foydalanuvchilar ro'yxati.
    MVP'da hammasi — keyinroq opt-out/faollik filtri qo'shiladi."""
    async with _pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT id, telegram_id, locale, last_prompt_id FROM users"
            )
            return await cur.fetchall()
