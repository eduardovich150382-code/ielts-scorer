"""Faza 0 — Telegram bot entrypoint.

Scope (docs/01-mvp-prd.md): /start (til+maqsad band+imtihon sana) -> savol
ko'rsatish -> esse (matn/rasm) qabul qilish -> mavjud `scorer.score_essay()`
bilan baholash -> band+top-5 xato -> kuniga 1 bepul limit -> paywall tugmasi
(click log, hali sotib olinmaydi) -> har kuni 19:00 Task-2 savoli eslatmasi.

Ishga tushirish: `.env.example`ni `.env`ga nusxalab to'ldiring, so'ng
`python bot.py`.
"""
from __future__ import annotations

# Eslatma: .env config.py import qilinganda avtomatik yuklanadi (config.py
# ning o'zida load_dotenv() bor) — bu yerda alohida chaqirish shart emas.
# scorer.py (pastda import qilinadi) -> llm.py -> config.py zanjiri buni
# ta'minlaydi, `main()`dagi os.environ["BOT_TOKEN"] kabi o'qishlardan oldin.

import asyncio
import logging
import os
from datetime import date, datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

import db
import ocr
import prompts_bank
import texts
from scheduler import setup_scheduler
from scorer import score_essay

log = logging.getLogger(__name__)
router = Router()

TARGET_BANDS = [5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5]


class Onboarding(StatesGroup):
    waiting_exam_date = State()


# ============================================================ YORDAMCHILAR

def _menu_keyboard(locale: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=texts.t("menu_button", locale))]],
        resize_keyboard=True,
    )


def _paywall_keyboard(locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=texts.t("paywall_button", locale), callback_data="paywall_click"
        )
    ]])


def _is_menu_button(text: str) -> bool:
    return text in (texts.t("menu_button", "uz"), texts.t("menu_button", "ru"))


def _format_result(result, locale: str) -> str:
    c = result.criteria
    out = texts.t(
        "result_header", locale,
        overall=result.overall_band,
        ta=c.get("TA"), cc=c.get("CC"), lr=c.get("LR"), gra=c.get("GRA"),
    )
    top_errors = sorted(
        result.annotations, key=lambda a: a.get("severity", 0), reverse=True
    )[:5]
    if top_errors:
        out += texts.t("result_errors_header", locale)
        for a in top_errors:
            note = a.get("note_uz") if locale == "uz" else a.get("note_en", a.get("note_uz", ""))
            out += "\n" + texts.t(
                "result_error_line", locale,
                original=a.get("original", ""), suggestion=a.get("suggestion", ""),
                note=note,
            )
    if result.priorities_uz:
        out += texts.t("result_priorities_header", locale)
        for p in result.priorities_uz:
            out += f"\n• {p}"
    if result.needs_human_review:
        out += texts.t("needs_human_review", locale)
    return out


async def _run_scoring(message: Message, user: dict, prompt: dict, essay_text: str, source: str) -> None:
    locale = user["locale"]
    submission_id = await db.create_essay_submission(user["id"], prompt["id"], source, essay_text)
    status_msg = await message.answer(texts.t("checking", locale))
    try:
        result = await asyncio.to_thread(
            score_essay, prompt["body"], essay_text, task_kind="writing_t2"
        )
    except Exception as exc:
        log.exception("score_essay xato (submission_id=%s)", submission_id)
        await db.mark_essay_failed(submission_id, str(exc))
        await status_msg.edit_text(texts.t("scoring_failed", locale))
        return

    await db.save_essay_result(submission_id, result)
    await db.set_pending_prompt(message.chat.id, None)
    await db.log_event(
        "essay_scored", user["id"],
        {"submission_id": submission_id, "overall_band": result.overall_band,
         "cost_usd": result.cost_usd},
    )
    await status_msg.edit_text(
        _format_result(result, locale), reply_markup=_paywall_keyboard(locale)
    )


async def _send_prompt(target: Message, telegram_id: int, locale: str, prompt: dict) -> None:
    """`target` — javob yuboriladigan Message (oddiy xabar yoki callback.message)."""
    await db.set_pending_prompt(telegram_id, prompt["id"])
    await target.answer(texts.t("prompt_shown", locale, body=prompt["body"]))


# ============================================================ ONBOARDING

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await db.get_or_create_user(message.chat.id, message.from_user.username)
    await db.log_event("start", None, {"telegram_id": message.chat.id})
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang:uz"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
    ]])
    await message.answer(texts.t("choose_language", "uz"), reply_markup=kb)


@router.callback_query(F.data.startswith("lang:"))
async def on_language_chosen(callback: CallbackQuery) -> None:
    locale = callback.data.split(":", 1)[1]
    await db.set_locale(callback.message.chat.id, locale)
    await db.log_event("lang_set", None, {"telegram_id": callback.message.chat.id, "locale": locale})
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(b), callback_data=f"band:{b}") for b in TARGET_BANDS[:4]],
        [InlineKeyboardButton(text=str(b), callback_data=f"band:{b}") for b in TARGET_BANDS[4:]],
    ])
    await callback.message.edit_text(texts.t("ask_target_band", locale), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("band:"))
async def on_band_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    band = float(callback.data.split(":", 1)[1])
    telegram_id = callback.message.chat.id
    await db.set_target_band(telegram_id, band)
    user = await db.get_user(telegram_id)
    locale = user["locale"]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=texts.t("skip", locale), callback_data="skip_exam_date")
    ]])
    await callback.message.edit_text(texts.t("ask_exam_date", locale), reply_markup=kb)
    await state.set_state(Onboarding.waiting_exam_date)
    await callback.answer()


async def _finish_onboarding(chat_id: int, locale: str, state: FSMContext, answer) -> None:
    await state.clear()
    await answer(texts.t("onboarding_done", locale), reply_markup=_menu_keyboard(locale))


@router.callback_query(F.data == "skip_exam_date")
async def on_skip_exam_date(callback: CallbackQuery, state: FSMContext) -> None:
    telegram_id = callback.message.chat.id
    await db.set_exam_date(telegram_id, None)
    user = await db.get_user(telegram_id)
    await _finish_onboarding(telegram_id, user["locale"], state, callback.message.answer)
    await callback.answer()


@router.message(Onboarding.waiting_exam_date, F.text)
async def on_exam_date_text(message: Message, state: FSMContext) -> None:
    user = await db.get_user(message.chat.id)
    locale = user["locale"]
    try:
        exam_date = datetime.strptime(message.text.strip(), "%Y-%m-%d").date()
        if exam_date < date.today():
            raise ValueError("o'tmishdagi sana")
    except ValueError:
        await message.answer(texts.t("invalid_date", locale))
        return
    await db.set_exam_date(message.chat.id, exam_date)
    await _finish_onboarding(message.chat.id, locale, state, message.answer)


# ============================================================ ESSE OQIMI

@router.message(Command("submit"))
@router.message(F.text.func(_is_menu_button))
async def cmd_submit(message: Message) -> None:
    user = await db.get_or_create_user(message.chat.id, message.from_user.username)
    locale = user["locale"]
    if await db.has_used_free_today(user["id"]):
        await message.answer(texts.t("limit_reached", locale), reply_markup=_paywall_keyboard(locale))
        return
    prompt = prompts_bank.pick_prompt(exclude_id=user.get("last_prompt_id"))
    await _send_prompt(message, message.chat.id, locale, prompt)


@router.callback_query(F.data == "paywall_click")
async def on_paywall_click(callback: CallbackQuery) -> None:
    user = await db.get_user(callback.message.chat.id)
    locale = user["locale"] if user else "uz"
    if user:
        await db.mark_paywall_clicked(user["id"])
        await db.log_event("paywall_click", user["id"])
    await callback.answer(texts.t("paywall_clicked", locale), show_alert=True)


@router.callback_query(F.data.startswith("nudge_answer:"))
async def on_nudge_answer(callback: CallbackQuery) -> None:
    prompt_id = callback.data.split(":", 1)[1]
    prompt = prompts_bank.get_prompt(prompt_id)
    user = await db.get_or_create_user(callback.message.chat.id, callback.from_user.username)
    locale = user["locale"]
    await db.log_event("nudge_click", user["id"], {"prompt_id": prompt_id})
    if await db.has_used_free_today(user["id"]):
        # Nudge kunlik limitni chetlab o'tish yo'li bo'lmasligi kerak —
        # cmd_submit bilan bir xil tekshiruv.
        await callback.message.answer(
            texts.t("limit_reached", locale), reply_markup=_paywall_keyboard(locale)
        )
        await callback.answer()
        return
    if prompt is None:
        prompt = prompts_bank.pick_prompt(exclude_id=user.get("last_prompt_id"))
    await _send_prompt(callback.message, callback.message.chat.id, locale, prompt)
    await callback.answer()


@router.message(F.photo)
async def on_photo(message: Message) -> None:
    user = await db.get_or_create_user(message.chat.id, message.from_user.username)
    locale = user["locale"]
    if not user.get("pending_prompt_id"):
        await message.answer(texts.t("no_pending_prompt", locale))
        return
    prompt = prompts_bank.get_prompt(user["pending_prompt_id"])
    file = await message.bot.get_file(message.photo[-1].file_id)
    buf = await message.bot.download_file(file.file_path)
    essay_text = ocr.extract_text_from_image(buf.read())
    if essay_text is None:
        await message.answer(texts.t("ocr_failed", locale))
        return
    await _run_scoring(message, user, prompt, essay_text, source="photo")


@router.message(F.text)
async def on_text(message: Message) -> None:
    """Umumiy matn handler — faqat yuqoridagi aniqroq handlerlar (buyruqlar,
    menyu tugmasi, onboarding sana) mos kelmagan xabarlar shu yerga tushadi,
    ya'ni esse matni deb qaraladi."""
    user = await db.get_or_create_user(message.chat.id, message.from_user.username)
    locale = user["locale"]
    if not user.get("pending_prompt_id"):
        await message.answer(texts.t("no_pending_prompt", locale))
        return
    prompt = prompts_bank.get_prompt(user["pending_prompt_id"])
    await _run_scoring(message, user, prompt, message.text, source="text")


# ============================================================ ENTRYPOINT

async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    bot_token = os.environ["BOT_TOKEN"]
    dsn = os.environ["DATABASE_URL"]

    await db.init_pool(dsn)
    await db.init_db()

    bot = Bot(token=bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    sched = setup_scheduler(bot)
    sched.start()

    try:
        await dp.start_polling(bot)
    finally:
        sched.shutdown(wait=False)
        await db.close_pool()


if __name__ == "__main__":
    # psycopg async rejimi Windows'ning standart ProactorEventLoop'ini
    # qo'llab-quvvatlamaydi — SelectorEventLoop kerak. Unix'da bu allaqachon
    # standart, shuning uchun platformalar bo'yicha shart yozishga hojat yo'q.
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
