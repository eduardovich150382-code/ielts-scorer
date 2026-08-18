"""Konfiguratsiya. Barcha sozlamalar shu yerda — kodda hardcode qilmang."""
from __future__ import annotations

import os

# ---------------------------------------------------------------- versiyalash
# ⚠ Har qanday prompt/rubrika/model o'zgarishida SCORER_VERSION ni oshiring.
# Busiz kalibrlash ma'nosiz bo'lib qoladi (02-hujjat, evaluations.model_version).
SCORER_VERSION = "scorer-v1.0"

# ---------------------------------------------------------------- modellar
MODEL_PRIMARY = os.getenv("SCORER_MODEL", "claude-sonnet-5")
MODEL_CHEAP = os.getenv("SCORER_MODEL_CHEAP", "claude-haiku-4-5-20251001")
MODEL_ANNOTATE = os.getenv("ANNOTATE_MODEL", "claude-sonnet-5")

# 1M token uchun USD. O'z shartnoma narxlaringiz bilan almashtiring.
PRICING = {
    "claude-sonnet-5": {"in": 3.00, "out": 15.00},
    "claude-haiku-4-5-20251001": {"in": 1.00, "out": 5.00},
}

# ---------------------------------------------------------------- baholash
CRITERIA = ("TA", "CC", "LR", "GRA")
CRITERION_NAMES = {
    "TA": "Task Achievement / Task Response",
    "CC": "Coherence and Cohesion",
    "LR": "Lexical Resource",
    "GRA": "Grammatical Range and Accuracy",
}

BAND_MIN, BAND_MAX, BAND_STEP = 4.0, 9.0, 0.5

# Self-consistency: qimmat, shuning uchun ADAPTIV.
# Faqat mezon bandi shu chegaralarga yaqin bo'lsa qayta chaqiramiz.
SC_RUNS = 3
SC_TRIGGER_FRACTION = 0.25   # .25 yoki .75 ga yaqin → chegara holati

# Task turlari
TASK_KINDS = ("writing_t2", "writing_t1_academic", "writing_t1_general")
MIN_WORDS = {"writing_t2": 250, "writing_t1_academic": 150, "writing_t1_general": 150}

# ---------------------------------------------------------------- kalibrlash
CALIBRATION_PATH = os.getenv("CALIBRATION_PATH", "data/calibration.json")
GOLDEN_SET_PATH = os.getenv("GOLDEN_SET_PATH", "data/golden_set.json")
ANCHORS_PATH = os.getenv("ANCHORS_PATH", "data/anchors.json")
CACHE_DIR = os.getenv("SCORER_CACHE", "cache")

# CI darvozasi: MAE shu qiymatdan ko'p yomonlashsa, deploy bloklanadi.
MAE_REGRESSION_TOLERANCE = 0.05

# Maqsad ko'rsatkichlar (03-hujjat, §4)
TARGETS = {
    "mae": 0.40,          # ≤
    "within_half": 0.85,  # ≥
    "within_one": 0.97,   # ≥
    "qwk": 0.75,          # ≥
    "abs_bias": 0.15,     # ≤
}
