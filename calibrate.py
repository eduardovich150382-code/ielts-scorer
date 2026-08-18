#!/usr/bin/env python3
"""
Kalibrlash CLI.

    # 1. Baseline: kalibrlashsiz o'lchash
    python calibrate.py evaluate --no-calibration

    # 2. Mapping'ni moslash (train/test bo'linishi bilan)
    python calibrate.py fit --holdout 0.3

    # 3. CI darvozasi — MAE yomonlashsa exit code 1
    python calibrate.py gate

    # 4. Prompt o'zgarishlarini taqqoslash
    python calibrate.py evaluate --tag "anchors qo'shildi"
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import metrics as M
from calibration import Calibrator, round_to_half
from config import (CRITERIA, GOLDEN_SET_PATH, MAE_REGRESSION_TOLERANCE,
                    MODEL_PRIMARY, SCORER_VERSION)

HISTORY_PATH = Path("data/calibration_history.jsonl")


# ---------------------------------------------------------------------------
def load_golden(path: str = GOLDEN_SET_PATH) -> list[dict]:
    p = Path(path)
    if not p.exists():
        sys.exit(f"❌ Oltin to'plam topilmadi: {path}\n"
                 f"   data/golden_set.example.json dan nusxa oling.")
    data = json.loads(p.read_text())
    bad = [d["id"] for d in data
           if not d.get("true_overall") or not d.get("essay")]
    if bad:
        sys.exit(f"❌ To'liqsiz yozuvlar: {bad}")
    print(f"✓ Oltin to'plam: {len(data)} namuna")

    bands = sorted({d["true_overall"] for d in data})
    print(f"  Band diapazoni: {bands[0]} – {bands[-1]}")
    if bands[-1] - bands[0] < 2.0:
        print("  ⚠ OGOHLANTIRISH: diapazon tor. Kalibrlash ishonchsiz bo'ladi.\n"
              "    4.5 dan 8.5 gacha namunalar qo'shing.")
    return data


# ---------------------------------------------------------------------------
def run_scorer(golden: list[dict], workers: int = 4,
               self_consistency: bool = False) -> list[dict]:
    """Butun oltin to'plamni baholaydi. Kesh tufayli qayta ishga tushirish arzon."""
    from llm import TRACKER
    from scorer import score_essay

    results: list[dict] = []
    t0 = time.time()

    def one(item: dict) -> dict:
        r = score_essay(item["prompt"], item["essay"],
                        task_kind=item.get("task_kind", "writing_t2"),
                        model=MODEL_PRIMARY,
                        with_annotations=False,          # kalibrlashda kerak emas
                        self_consistency=self_consistency)
        return {
            "id": item["id"],
            "true_overall": float(item["true_overall"]),
            "true_criteria": {k: float(v) for k, v in item.get("true_criteria", {}).items()},
            "raw_overall": r.raw_overall,
            "raw_criteria": r.raw_criteria,
            "cal_overall": r.overall_band,
            "cal_criteria": r.criteria,
            "needs_review": r.needs_human_review,
            "word_count": r.text_features["word_count"],
        }

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(one, it): it["id"] for it in golden}
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                results.append(fut.result())
            except Exception as e:                          # noqa: BLE001
                print(f"  ✗ {futs[fut]}: {e}")
            print(f"\r  baholandi {i}/{len(golden)}", end="", flush=True)

    print(f"\n  {time.time() - t0:.0f}s | {TRACKER.report()}")
    return results


# ---------------------------------------------------------------------------
def report(results: list[dict], use_calibrated: bool, title: str) -> M.Metrics:
    key_o = "cal_overall" if use_calibrated else "raw_overall"
    key_c = "cal_criteria" if use_calibrated else "raw_criteria"

    true = [r["true_overall"] for r in results]
    pred = [r[key_o] for r in results]
    overall = M.compute(true, pred)

    per_crit = {}
    for c in CRITERIA:
        pairs = [(r["true_criteria"][c], r[key_c][c]) for r in results
                 if c in r.get("true_criteria", {}) and c in r.get(key_c, {})]
        if len(pairs) >= 5:
            per_crit[c] = M.compute([p[0] for p in pairs], [p[1] for p in pairs])

    breakdown = M.by_band_breakdown(true, pred)
    print(M.format_report(overall, per_crit, breakdown, title))

    worst = sorted(results, key=lambda r: -abs(r[key_o] - r["true_overall"]))[:5]
    print("\n  Eng katta xatolar (bularni QO'LDA ko'ring):")
    for r in worst:
        print(f"    {r['id']:<16} haqiqiy {r['true_overall']}  "
              f"bashorat {r[key_o]}  farq {r[key_o] - r['true_overall']:+.1f}")
    return overall


# ---------------------------------------------------------------------------
def cmd_evaluate(args) -> None:
    golden = load_golden()
    results = run_scorer(golden, args.workers, args.self_consistency)

    m_raw = report(results, False, f"KALIBRLASHSIZ (xom) — {SCORER_VERSION}")
    if not args.no_calibration:
        report(results, True, f"KALIBRLANGAN — {SCORER_VERSION}")

    Path("data").mkdir(exist_ok=True)
    Path("data/last_run.json").write_text(json.dumps(results, indent=2))

    HISTORY_PATH.parent.mkdir(exist_ok=True)
    with HISTORY_PATH.open("a") as fh:
        fh.write(json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "scorer_version": SCORER_VERSION,
            "tag": args.tag,
            "n": len(results),
            "raw": m_raw.to_dict(),
        }) + "\n")
    print(f"\n✓ Tarixga yozildi: {HISTORY_PATH}")


def cmd_fit(args) -> None:
    """
    ⚠ MUHIM: mapping'ni moslash va uni baholash BIR XIL ma'lumotda bo'lmasin.
    Holdout bo'linishi majburiy, aks holda o'zingizni aldayasiz.
    """
    import random

    golden = load_golden()
    results = run_scorer(golden, args.workers, args.self_consistency)

    random.seed(42)
    random.shuffle(results)
    split = int(len(results) * (1 - args.holdout))
    train, test = results[:split], results[split:]
    print(f"\n  train={len(train)}  holdout={len(test)}")

    if len(train) < 20:
        print("  ⚠ Train to'plami juda kichik (<20). Mapping ishonchsiz bo'ladi.")

    cal = Calibrator.fit(train, method=args.method)
    print(f"  Mapping: {cal.describe()}")

    for r in test:
        r["cal_overall"] = cal.apply_overall(
            sum(cal.apply_criterion(c, r["raw_criteria"][c], do_round=False)
                for c in CRITERIA) / len(CRITERIA))
        r["cal_criteria"] = {c: cal.apply_criterion(c, r["raw_criteria"][c])
                             for c in CRITERIA}

    m_before = report(test, False, "HOLDOUT — kalibrlashdan OLDIN")
    m_after = report(test, True, "HOLDOUT — kalibrlashdan KEYIN")

    delta = m_before.mae - m_after.mae
    print(f"\n  MAE yaxshilanishi: {delta:+.3f}")
    if delta <= 0:
        print("  ⚠ Kalibrlash YORDAM BERMADI. Mapping saqlanmaydi.\n"
              "    Sabab: yetarli ma'lumot yo'q yoki tarafkashlik chiziqli emas.\n"
              "    Avval promptni yaxshilang (anchor esselar qo'shing).")
        if not args.force:
            return

    cal.save()
    print(f"  ✓ Saqlandi: data/calibration.json")


def cmd_gate(args) -> None:
    """CI darvozasi: oldingi eng yaxshi natijadan yomonlashsa — bloklaydi."""
    golden = load_golden()
    results = run_scorer(golden, args.workers, False)
    true = [r["true_overall"] for r in results]
    pred = [r["cal_overall"] for r in results]
    current = M.compute(true, pred)

    per_crit = {}
    for c in CRITERIA:
        pairs = [(r["true_criteria"][c], r["cal_criteria"][c]) for r in results
                 if c in r.get("true_criteria", {})]
        if len(pairs) >= 5:
            per_crit[c] = M.compute([p[0] for p in pairs], [p[1] for p in pairs])
    print(M.format_report(current, per_crit,
                          M.by_band_breakdown(true, pred), "CI DARVOZASI"))

    best = None
    if HISTORY_PATH.exists():
        rows = [json.loads(l) for l in HISTORY_PATH.read_text().splitlines() if l.strip()]
        if rows:
            best = min(r["raw"]["mae"] for r in rows)

    ok, fails = current.passes()
    if best is not None and current.mae > best + MAE_REGRESSION_TOLERANCE:
        print(f"\n❌ REGRESSIYA: MAE {current.mae:.3f} > eng yaxshi {best:.3f} "
              f"+ {MAE_REGRESSION_TOLERANCE}")
        sys.exit(1)
    if not ok:
        print("\n❌ Maqsad ko'rsatkichlariga yetmadi")
        sys.exit(1)
    print("\n✅ Darvozadan o'tdi")


def cmd_history(args) -> None:
    if not HISTORY_PATH.exists():
        sys.exit("Tarix bo'sh.")
    rows = [json.loads(l) for l in HISTORY_PATH.read_text().splitlines() if l.strip()]
    print(f"{'sana':<20} {'versiya':<14} {'n':>4} {'MAE':>7} {'±0.5':>7} {'QWK':>7}  izoh")
    print("-" * 80)
    for r in rows:
        m = r["raw"]
        print(f"{r['ts']:<20} {r['scorer_version']:<14} {r['n']:>4} "
              f"{m['mae']:>7.3f} {m['within_half']:>6.1%} {m['qwk']:>7.3f}  "
              f"{r.get('tag') or ''}")


# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="IELTS Writing scorer kalibrlash")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name, fn in [("evaluate", cmd_evaluate), ("fit", cmd_fit),
                     ("gate", cmd_gate), ("history", cmd_history)]:
        p = sub.add_parser(name)
        p.set_defaults(func=fn)
        if name != "history":
            p.add_argument("--workers", type=int, default=4)
            p.add_argument("--self-consistency", action="store_true",
                           help="Chegara holatlarda 3× chaqiruv (qimmat)")
        if name == "evaluate":
            p.add_argument("--no-calibration", action="store_true")
            p.add_argument("--tag", default="", help="Bu o'zgarish nima edi?")
        if name == "fit":
            p.add_argument("--holdout", type=float, default=0.3)
            p.add_argument("--method", default="auto",
                           choices=["auto", "linear", "isotonic"])
            p.add_argument("--force", action="store_true")

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
