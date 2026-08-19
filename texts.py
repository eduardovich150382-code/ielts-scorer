"""uz/ru UI matnlari — oddiy dict, i18n freymvorksiz (MVP, 01-hujjat: "kod
sifatiga vaqt sarflamang")."""
from __future__ import annotations

_TEXTS: dict[str, dict[str, str]] = {
    "choose_language": {
        "uz": "Assalomu alaykum! IELTS Writing esselaringizni 60 soniyada "
              "tekshirib beraman. Tilni tanlang:",
        "ru": "Здравствуйте! Я проверяю IELTS Writing эссе за 60 секунд. "
              "Выберите язык:",
    },
    "ask_target_band": {
        "uz": "Maqsad bandingiz nechchi?",
        "ru": "Какой band вы хотите получить?",
    },
    "ask_exam_date": {
        "uz": "Imtihon sanangiz? (masalan: 2026-12-15). Agar hali "
              "belgilamagan bo'lsangiz, \"O'tkazib yuborish\" tugmasini "
              "bosing.",
        "ru": "Дата экзамена? (например: 2026-12-15). Если ещё не "
              "назначена — нажмите «Пропустить».",
    },
    "skip": {"uz": "O'tkazib yuborish", "ru": "Пропустить"},
    "invalid_date": {
        "uz": "Sana formati noto'g'ri. YYYY-MM-DD ko'rinishida yuboring "
              "(masalan: 2026-12-15) yoki o'tkazib yuboring.",
        "ru": "Неверный формат даты. Отправьте в виде YYYY-MM-DD "
              "(например: 2026-12-15) или нажмите «Пропустить».",
    },
    "onboarding_done": {
        "uz": "Tayyor! Endi \"✍️ Yangi esse\" tugmasini bosing — men sizga "
              "Task 2 savolini beraman, javobingizni matn yoki rasm "
              "(qo'lyozma) sifatida yuborasiz.",
        "ru": "Готово! Нажмите «✍️ Новое эссе» — я дам вам вопрос Task 2, а "
              "вы пришлёте ответ текстом или фото (рукописный текст).",
    },
    "menu_button": {"uz": "✍️ Yangi esse", "ru": "✍️ Новое эссе"},
    "limit_reached": {
        "uz": "Bugungi bepul tekshiruvingiz tugadi. Ertaga yana urinib "
              "ko'ring, yoki cheksiz foydalanish uchun quyidagi tugmani "
              "bosing:",
        "ru": "Ваша бесплатная проверка на сегодня закончилась. Попробуйте "
              "завтра, или нажмите кнопку ниже для безлимитного доступа:",
    },
    "paywall_button": {
        "uz": "Cheksiz — 59 000 so'm/oy",
        "ru": "Безлимит — 59 000 сум/мес",
    },
    "paywall_clicked": {
        "uz": "Tez orada! Siz ro'yxatga yozildingiz 🎉",
        "ru": "Скоро! Вы записаны 🎉",
    },
    "prompt_shown": {
        "uz": "📝 Task 2 savolingiz:\n\n{body}\n\nJavobingizni matn yoki "
              "rasm (qo'lyozma) sifatida yuboring. Kamida 250 so'z, 40 "
              "daqiqa ichida yozishga harakat qiling.",
        "ru": "📝 Ваш вопрос Task 2:\n\n{body}\n\nПришлите ответ текстом или "
              "фото (рукописный текст). Минимум 250 слов, старайтесь "
              "уложиться в 40 минут.",
    },
    "no_pending_prompt": {
        "uz": "Avval \"✍️ Yangi esse\" tugmasini bosing, keyin savolga "
              "javob yuboring.",
        "ru": "Сначала нажмите «✍️ Новое эссе», затем пришлите ответ на "
              "вопрос.",
    },
    "checking": {
        "uz": "🔎 Tekshirilmoqda... (odatda 30–60 soniya)",
        "ru": "🔎 Проверяю... (обычно 30–60 секунд)",
    },
    "ocr_failed": {
        "uz": "Rasmni o'qiy olmadim. Iltimos, esseingizni matn sifatida "
              "yuboring.",
        "ru": "Не удалось распознать фото. Пожалуйста, пришлите эссе "
              "текстом.",
    },
    "scoring_failed": {
        "uz": "Kechirasiz, tekshirishda xatolik yuz berdi. Birozdan so'ng "
              "qayta urinib ko'ring.",
        "ru": "Извините, при проверке произошла ошибка. Попробуйте ещё раз "
              "чуть позже.",
    },
    "result_header": {
        "uz": "📊 Umumiy band: {overall}\n"
              "TA: {ta} · CC: {cc} · LR: {lr} · GRA: {gra}",
        "ru": "📊 Общий band: {overall}\n"
              "TA: {ta} · CC: {cc} · LR: {lr} · GRA: {gra}",
    },
    "result_errors_header": {
        "uz": "\n\n🔴 Asosiy xatolar:",
        "ru": "\n\n🔴 Основные ошибки:",
    },
    "result_error_line": {
        "uz": "• “{original}” → “{suggestion}” — {note}",
        "ru": "• “{original}” → “{suggestion}” — {note}",
    },
    "result_priorities_header": {
        "uz": "\n\n💡 Keyingi esseda e'tibor bering:",
        "ru": "\n\n💡 В следующем эссе обратите внимание:",
    },
    "needs_human_review": {
        "uz": "\n\n⚠️ Bu baho taxminiy — sizning javobingiz odatiy "
              "holatlardan farq qildi, shuning uchun ehtiyotkorlik bilan "
              "qarang.",
        "ru": "\n\n⚠️ Эта оценка приблизительная — ваш ответ отличается от "
              "типичных случаев, отнеситесь к ней с осторожностью.",
    },
    "nudge_intro": {
        "uz": "🔔 Bugungi Task 2 savoli:\n\n{body}",
        "ru": "🔔 Сегодняшний вопрос Task 2:\n\n{body}",
    },
    "nudge_answer_button": {"uz": "Javob berish", "ru": "Ответить"},
}


def t(key: str, locale: str, **kwargs) -> str:
    entry = _TEXTS.get(key)
    if entry is None:
        return key
    template = entry.get(locale) or entry.get("uz", key)
    return template.format(**kwargs) if kwargs else template
