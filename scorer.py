"""
Writing scorer — asosiy pipeline.

    from scorer import score_essay
    result = score_essay(prompt_text, essay_text, task_kind="writing_t2")
"""
from __future__ import annotations

import json
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import features
from calibration import Calibrator, round_to_half
from config import (ANCHORS_PATH, CRITERIA, MODEL_PRIMARY, MODEL_ANNOTATE,
                    SC_RUNS, SC_TRIGGER_FRACTION, SCORER_VERSION)
from llm import call_json
from prompts import (ANNOTATE_SCHEMA, CRITERION_SCHEMA, SYSTEM_ANNOTATE,
                     build_criterion_system, build_criterion_user_message)

_ANCHORS: dict | None = None
_CALIBRATOR: Calibrator | None = None


def _anchors_for(criterion: str, task_kind: str, k: int = 4) -> list[dict]:
    """Band bo'yicha teng taqsimlangan anchor namunalarni tanlaydi."""
    global _ANCHORS
    if _ANCHORS is None:
        p = Path(ANCHORS_PATH)
        _ANCHORS = json.loads(p.read_text()) if p.exists() else {}

    pool = [a for a in _ANCHORS.get(task_kind, [])
            if criterion in a.get("criteria", {})]
    if not pool:
        return []

    by_band: dict[float, list[dict]] = {}
    for a in pool:
        by_band.setdefault(a["criteria"][criterion], []).append(a)

    bands = sorted(by_band)
    if len(bands) > k:                      # diapazonni qamrab olib tanlaymiz
        idx = [round(i * (len(bands) - 1) / (k - 1)) for i in range(k)]
        bands = [bands[i] for i in sorted(set(idx))]

    return [{"band": b,
             "text": random.choice(by_band[b])["text"],
             "note": random.choice(by_band[b]).get("notes", {}).get(criterion)}
            for b in bands]


def _needs_second_opinion(band: float) -> bool:
    """0.5 chegarasiga yaqin bo'lsa qayta chaqiramiz (adaptiv self-consistency)."""
    frac = abs((band * 2) - round(band * 2))
    return frac >= SC_TRIGGER_FRACTION


@dataclass
class CriterionResult:
    criterion: str
    raw_band: float
    calibrated_band: float
    runs: list[float]
    evidence: list[dict]
    ceiling_reason: str
    reasoning: str
    injection_detected: bool = False


@dataclass
class ScoreResult:
    scorer_version: str
    overall_band: float
    criteria: dict[str, float]
    raw_overall: float
    raw_criteria: dict[str, float]
    details: dict[str, CriterionResult]
    text_features: dict
    penalties: list[str]
    annotations: list[dict] = field(default_factory=list)
    upgrade_paragraph: dict | None = None
    priorities_uz: list[str] = field(default_factory=list)
    needs_human_review: bool = False
    review_reasons: list[str] = field(default_factory=list)
    latency_ms: int = 0
    cost_usd: float = 0.0

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["details"] = {k: v.__dict__ for k, v in self.details.items()}
        return d


# ---------------------------------------------------------------------------
# BOSQICH 2 — mezon bo'yicha baholash
# ---------------------------------------------------------------------------

def _score_criterion(criterion: str, prompt_text: str, essay: str,
                     feats: dict, penalties: list[str], task_kind: str,
                     model: str, self_consistency: bool) -> CriterionResult:
    system = build_criterion_system(criterion)
    user = build_criterion_user_message(
        criterion, prompt_text, essay, feats,
        _anchors_for(criterion, task_kind), penalties)

    first = call_json(system, user, model=model, schema=CRITERION_SCHEMA,
                      max_tokens=1600, temperature=0.0)
    bands = [float(first.data["band"])]

    # Adaptiv self-consistency: faqat chegara holatlarda va faqat so'ralganda
    if self_consistency and _needs_second_opinion(bands[0]):
        for _ in range(SC_RUNS - 1):
            r = call_json(system, user, model=model, schema=CRITERION_SCHEMA,
                          max_tokens=1600, temperature=0.6, use_cache=False)
            bands.append(float(r.data["band"]))

    raw = statistics.median(bands)
    cal = _get_calibrator().apply_criterion(criterion, raw)

    return CriterionResult(
        criterion=criterion,
        raw_band=raw,
        calibrated_band=cal,
        runs=bands,
        evidence=first.data.get("evidence", []),
        ceiling_reason=first.data.get("band_ceiling_reason", ""),
        reasoning=first.data.get("reasoning", ""),
        injection_detected=bool(first.data.get("prompt_injection_detected")),
    )


def _get_calibrator() -> Calibrator:
    global _CALIBRATOR
    if _CALIBRATOR is None:
        _CALIBRATOR = Calibrator.load()
    return _CALIBRATOR


# ---------------------------------------------------------------------------
# BOSQICH 3 — annotatsiya + span joylashtirish
# ---------------------------------------------------------------------------

def _resolve_spans(essay: str, annotations: list[dict]) -> list[dict]:
    """
    LLM belgi indekslarini ishonchli bermaydi. Shuning uchun u SO'ZMA-SO'Z
    parcha qaytaradi, biz uni matndan o'zimiz topamiz.
    """
    out: list[dict] = []
    used: list[tuple[int, int]] = []
    for a in annotations:
        needle = (a.get("original") or "").strip()
        if not needle:
            continue
        start = -1
        search_from = 0
        while True:
            idx = essay.find(needle, search_from)
            if idx == -1:
                break
            if not any(s <= idx < e for s, e in used):
                start = idx
                break
            search_from = idx + 1
        if start == -1:                         # topilmadi → tashlab yuboramiz
            a["_unresolved"] = True
            out.append(a)
            continue
        end = start + len(needle)
        used.append((start, end))
        a["span"] = [start, end]
        out.append(a)
    return out


def _annotate(prompt_text: str, essay: str, criteria: dict[str, float],
              max_items: int = 12) -> dict:
    system = SYSTEM_ANNOTATE.format(max_items=max_items)
    weakest = min(criteria, key=criteria.get)
    user = (f"<savol>\n{prompt_text}\n</savol>\n\n"
            f"<talaba_matni>\n{essay}\n</talaba_matni>\n\n"
            f"<bandlar>{json.dumps(criteria)}</bandlar>\n"
            f"Eng zaif mezon: {weakest}. Annotatsiyalarda shunga urg'u bering.")
    r = call_json(system, user, model=MODEL_ANNOTATE, schema=ANNOTATE_SCHEMA,
                  max_tokens=3000, temperature=0.0)
    return r.data


# ---------------------------------------------------------------------------
# ASOSIY FUNKSIYA
# ---------------------------------------------------------------------------

def score_essay(prompt_text: str, essay: str, task_kind: str = "writing_t2",
                model: str = MODEL_PRIMARY, with_annotations: bool = True,
                self_consistency: bool = True) -> ScoreResult:
    t0 = time.time()
    from llm import TRACKER
    cost_before = TRACKER.total_usd

    # --- BOSQICH 1: deterministik (bepul) --------------------------------
    f = features.extract(essay, prompt_text, task_kind)
    feats = f.to_dict()
    penalties = features.hard_penalties(f, task_kind)

    # --- BOSQICH 2: mezonlar parallel ------------------------------------
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {c: pool.submit(_score_criterion, c, prompt_text, essay,
                                  feats, penalties, task_kind, model,
                                  self_consistency)
                   for c in CRITERIA}
        details = {c: fut.result() for c, fut in futures.items()}

    raw_criteria = {c: details[c].raw_band for c in CRITERIA}
    cal_criteria = {c: details[c].calibrated_band for c in CRITERIA}

    raw_overall = round_to_half(sum(raw_criteria.values()) / len(CRITERIA))
    overall = _get_calibrator().apply_overall(
        sum(cal_criteria.values()) / len(CRITERIA))

    # --- inson tekshiruviga yuborish shartlari ---------------------------
    reasons: list[str] = []
    spread = max(cal_criteria.values()) - min(cal_criteria.values())
    if spread >= 2.0:
        reasons.append(f"Mezonlar tarqoqligi {spread} band — g'ayrioddiy profil")
    for c, d in details.items():
        if len(d.runs) > 1 and (max(d.runs) - min(d.runs)) >= 1.0:
            reasons.append(f"{c}: takroriy chaqiruvlar mos kelmadi {d.runs}")
        if d.injection_detected:
            reasons.append(f"{c}: matnda prompt-injection aniqlandi")
    if f.prompt_copy_ratio > 0.25:
        reasons.append("Savoldan ko'p ko'chirilgan — qo'lda ko'rish kerak")
    if f.word_count < 80:
        reasons.append("Matn juda qisqa — avtomatik baho ishonchsiz")

    # --- BOSQICH 3: annotatsiyalar ---------------------------------------
    annotations, upgrade, priorities = [], None, []
    if with_annotations and f.word_count >= 80:
        try:
            ann = _annotate(prompt_text, essay, cal_criteria)
            annotations = _resolve_spans(essay, ann.get("annotations", []))
            upgrade = ann.get("upgrade_paragraph")
            priorities = ann.get("top_priorities_uz", [])
        except Exception as e:                                   # noqa: BLE001
            reasons.append(f"Annotatsiya xatosi: {e}")

    return ScoreResult(
        scorer_version=SCORER_VERSION,
        overall_band=overall,
        criteria=cal_criteria,
        raw_overall=raw_overall,
        raw_criteria=raw_criteria,
        details=details,
        text_features=feats,
        penalties=penalties,
        annotations=annotations,
        upgrade_paragraph=upgrade,
        priorities_uz=priorities,
        needs_human_review=bool(reasons),
        review_reasons=reasons,
        latency_ms=int((time.time() - t0) * 1000),
        cost_usd=round(TRACKER.total_usd - cost_before, 5),
    )


if __name__ == "__main__":
    import sys
    prompt = "Some people believe that unpaid community service should be a compulsory part of high school programmes. To what extent do you agree or disagree?"
    essay = Path(sys.argv[1]).read_text() if len(sys.argv) > 1 else "..."
    res = score_essay(prompt, essay)
    print(json.dumps(res.to_dict(), indent=2, ensure_ascii=False, default=str))
