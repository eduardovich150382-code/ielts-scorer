"""Kunlik 19:00 (Asia/Tashkent) Task-2 savoli eslatmasi.

Ichki APScheduler ishlatiladi (tashqi cron emas) — $5 VPS'da bot allaqachon
bitta uzoq ishlaydigan jarayon, alohida cron/autentifikatsiya ortiqcha
harakatlanuvchi qism bo'lardi (01-hujjat, 16-haftalik reja bilan mos ravishda
"kod sifatiga vaqt sarflamang" tamoyili)."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import db
import prompts_bank
import texts

log = logging.getLogger(__name__)

TASHKENT_TZ = "Asia/Tashkent"


async def send_daily_nudge(bot: Bot) -> None:
    users = await db.users_for_nudge()
    log.info("Kunlik nudge: %d foydalanuvchiga yuborilmoqda", len(users))
    for user in users:
        prompt = prompts_bank.pick_prompt(exclude_id=user.get("last_prompt_id"))
        locale = user.get("locale") or "uz"
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=texts.t("nudge_answer_button", locale),
                callback_data=f"nudge_answer:{prompt['id']}",
            )
        ]])
        try:
            await bot.send_message(
                user["telegram_id"],
                texts.t("nudge_intro", locale, body=prompt["body"]),
                reply_markup=kb,
            )
            await db.log_event(
                "nudge_sent", user["id"], {"prompt_id": prompt["id"]}
            )
        except TelegramForbiddenError:
            # Foydalanuvchi botni bloklagan — jim o'tkazib yuboriladi.
            continue
        except Exception:
            log.exception("Nudge yuborishda xato (user_id=%s)", user["id"])


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TASHKENT_TZ)
    scheduler.add_job(
        send_daily_nudge,
        trigger=CronTrigger(hour=19, minute=0, timezone=TASHKENT_TZ),
        args=[bot],
        id="daily_nudge",
        misfire_grace_time=3600,  # VPS qisqa vaqt o'chsa ham o'tkazib yubormaslik
        replace_existing=True,
    )
    return scheduler
