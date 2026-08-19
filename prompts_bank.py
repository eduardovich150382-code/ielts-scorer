"""Faza-0 bot uchun Task 2 savollar banki.

Barcha savollar **original** — Cambridge yoki boshqa rasmiy IELTS nashridan
ko'chirilmagan (04-hujjat, §7 huquqiy eslatmasi: "Kontent: har bir savol
source='original' bo'lsin"). Faza 1'da (02-hujjat, `prompts` jadvali) shu
ro'yxat DB'ga ko'chiriladi va 150+ tagacha kengaytiriladi; Faza 0'da 15-20 ta
yetarli — bot bir xil savolni tez-tez qaytarmasligi uchun shuncha xilma-xillik
kifoya.
"""
from __future__ import annotations

import random

BANK: list[dict] = [
    {"id": "t2-001", "topic": "education",
     "body": "Some people believe that unpaid community service should be a "
             "compulsory part of high school programmes. To what extent do "
             "you agree or disagree?"},
    {"id": "t2-002", "topic": "environment",
     "body": "Many countries are encouraging citizens to use bicycles "
             "instead of cars for short trips. Discuss the advantages and "
             "disadvantages of this approach."},
    {"id": "t2-003", "topic": "technology",
     "body": "Some people think that children should start learning a "
             "foreign language using apps and computer software rather than "
             "with a human teacher. To what extent do you agree or disagree?"},
    {"id": "t2-004", "topic": "work",
     "body": "In many countries, more and more people are choosing to work "
             "from home instead of commuting to an office. What are the "
             "advantages and disadvantages of this trend?"},
    {"id": "t2-005", "topic": "health",
     "body": "Some people believe that the government should be responsible "
             "for people's health, while others think individuals should "
             "take responsibility for their own health. Discuss both views "
             "and give your opinion."},
    {"id": "t2-006", "topic": "urbanization",
     "body": "As cities grow larger, many young people are moving away from "
             "small towns and villages. What are the causes of this trend, "
             "and what solutions can you suggest?"},
    {"id": "t2-007", "topic": "media",
     "body": "Nowadays, most people get their news from social media rather "
             "than newspapers or television. Do the advantages of this "
             "change outweigh the disadvantages?"},
    {"id": "t2-008", "topic": "government",
     "body": "Some people think that governments should spend money on "
             "public transport rather than building new roads. To what "
             "extent do you agree or disagree?"},
    {"id": "t2-009", "topic": "crime",
     "body": "Some people believe that prisons are the best way to deal "
             "with criminals, while others believe that education and "
             "training are more effective. Discuss both views and give your "
             "own opinion."},
    {"id": "t2-010", "topic": "family",
     "body": "In some cultures, children are expected to take care of their "
             "elderly parents, while in others this is seen as the "
             "government's responsibility. Discuss both views and give your "
             "opinion."},
    {"id": "t2-011", "topic": "globalization",
     "body": "As international travel becomes cheaper and more common, "
             "some people worry that local traditions and cultures are "
             "disappearing. To what extent do you agree or disagree?"},
    {"id": "t2-012", "topic": "education",
     "body": "Some people believe that university education should be free "
             "for all students, while others think students should pay for "
             "their own education. Discuss both views and give your "
             "opinion."},
    {"id": "t2-013", "topic": "technology",
     "body": "Many jobs that used to be done by humans are now performed by "
             "machines and artificial intelligence. What problems does this "
             "cause, and what solutions can you suggest?"},
    {"id": "t2-014", "topic": "environment",
     "body": "Some people think that individuals can do little to protect "
             "the environment, and that only governments and large "
             "companies can make a real difference. To what extent do you "
             "agree or disagree?"},
    {"id": "t2-015", "topic": "lifestyle",
     "body": "In many countries, people are working longer hours than ever "
             "before. What are the causes of this, and what effects does it "
             "have on individuals and society?"},
    {"id": "t2-016", "topic": "advertising",
     "body": "Some people believe that advertising aimed at children should "
             "be banned. To what extent do you agree or disagree?"},
    {"id": "t2-017", "topic": "tourism",
     "body": "Tourism is growing rapidly in many parts of the world. What "
             "are the advantages and disadvantages of this growth for local "
             "communities?"},
    {"id": "t2-018", "topic": "food",
     "body": "In recent years, fast food has become increasingly popular in "
             "many countries. What are the causes of this, and what "
             "measures could be taken to encourage healthier eating habits?"},
]

_BY_ID = {p["id"]: p for p in BANK}


def get_prompt(prompt_id: str) -> dict | None:
    return _BY_ID.get(prompt_id)


def pick_prompt(exclude_id: str | None = None) -> dict:
    """Tasodifiy savol tanlaydi. `exclude_id` berilsa (odatda foydalanuvchining
    oxirgi savoli), imkon qadar ketma-ket takrorlanmaydi."""
    candidates = [p for p in BANK if p["id"] != exclude_id] or BANK
    return random.choice(candidates)
