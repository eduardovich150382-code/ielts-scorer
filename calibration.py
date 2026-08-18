"""
Post-hoc kalibrlash mapping'i.

LLM tizimli tarafkashligini PROMPTDA tuzatishga urinmang — u beqaror.
Matematik tuzating: raw_band -> calibrated_band.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from config import BAND_MAX, BAND_MIN, BAND_STEP, CALIBRATION_PATH, SCORER_VERSION


def round_to_half(x: float) -> float:
    return float(np.clip(round(x * 2) / 2, BAND_MIN, BAND_MAX))


class Calibrator:
    """Mezon bo'yicha va umumiy band uchun mapping saqlaydi."""

    def __init__(self, mapping: dict | None = None):
        self.mapping = mapping or {}

    # ------------------------------------------------------------------ fit
    @staticmethod
    def _fit_one(raw: np.ndarray, true: np.ndarray, method: str = "linear") -> dict:
        """
        linear   — kam ma'lumotda (n < 80) barqarorroq
        isotonic — ko'p ma'lumotda (n >= 80) egri chiziqli tarafkashlikni tuzatadi
        """
        if len(raw) < 10:
            return {"method": "identity", "warning": f"n={len(raw)} < 10"}

        # Xavfsizlik 1: dispersiyasiz ma'lumotga mapping moslab bo'lmaydi
        if np.std(raw) < 0.1 or np.std(true) < 0.1:
            return {"method": "identity",
                    "warning": "dispersiya juda kichik — oltin to'plamda "
                               "band diapazoni yo'q"}

        # Xavfsizlik 2: korrelyatsiya zaif bo'lsa, mapping shovqinni kuchaytiradi
        r = float(np.corrcoef(raw, true)[0, 1])
        if not np.isfinite(r) or abs(r) < 0.3:
            return {"method": "identity",
                    "warning": f"korrelyatsiya r={r:.2f} juda zaif — "
                               "avval promptni yaxshilang, kalibrlash yordam bermaydi"}

        if method == "isotonic" and len(raw) >= 80:
            from sklearn.isotonic import IsotonicRegression
            iso = IsotonicRegression(y_min=BAND_MIN, y_max=BAND_MAX,
                                     out_of_bounds="clip")
            iso.fit(raw, true)
            grid = np.arange(BAND_MIN, BAND_MAX + 1e-9, 0.25)
            return {"method": "isotonic",
                    "x": grid.tolist(),
                    "y": iso.predict(grid).tolist()}

        # Chiziqli: true ≈ a * raw + b
        a, b = np.polyfit(raw, true, 1)
        # Xavfsizlik: nishab mantiqsiz bo'lsa, identity'ga qайt
        if not (0.4 <= a <= 1.8):
            return {"method": "identity", "warning": f"nishab={a:.2f} rad etildi"}
        return {"method": "linear", "a": float(a), "b": float(b)}

    @classmethod
    def fit(cls, records: list[dict], method: str = "auto") -> "Calibrator":
        """
        records: [{"raw_overall":6.5,"true_overall":6.0,
                   "raw_criteria":{...},"true_criteria":{...}}, ...]
        """
        from config import CRITERIA

        m = method
        if method == "auto":
            m = "isotonic" if len(records) >= 80 else "linear"

        mapping: dict = {"scorer_version": SCORER_VERSION,
                         "n_samples": len(records), "method": m, "criteria": {}}

        raw = np.array([r["raw_overall"] for r in records], dtype=float)
        true = np.array([r["true_overall"] for r in records], dtype=float)
        mapping["overall"] = cls._fit_one(raw, true, m)

        for c in CRITERIA:
            pairs = [(r["raw_criteria"].get(c), r["true_criteria"].get(c))
                     for r in records
                     if r.get("raw_criteria", {}).get(c) is not None
                     and r.get("true_criteria", {}).get(c) is not None]
            if len(pairs) >= 10:
                cr = np.array([p[0] for p in pairs], dtype=float)
                ct = np.array([p[1] for p in pairs], dtype=float)
                mapping["criteria"][c] = cls._fit_one(cr, ct, m)
            else:
                mapping["criteria"][c] = {"method": "identity"}

        return cls(mapping)

    # ---------------------------------------------------------------- apply
    @staticmethod
    def _apply_one(spec: dict, value: float) -> float:
        method = spec.get("method", "identity")
        if method == "identity":
            return value
        if method == "linear":
            return spec["a"] * value + spec["b"]
        if method == "isotonic":
            return float(np.interp(value, spec["x"], spec["y"]))
        return value

    def apply_overall(self, raw: float, do_round: bool = True) -> float:
        v = self._apply_one(self.mapping.get("overall", {}), raw)
        return round_to_half(v) if do_round else float(np.clip(v, BAND_MIN, BAND_MAX))

    def apply_criterion(self, criterion: str, raw: float,
                        do_round: bool = True) -> float:
        spec = self.mapping.get("criteria", {}).get(criterion, {})
        v = self._apply_one(spec, raw)
        return round_to_half(v) if do_round else float(np.clip(v, BAND_MIN, BAND_MAX))

    # ------------------------------------------------------------------- io
    def save(self, path: str = CALIBRATION_PATH) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.mapping, indent=2))

    @classmethod
    def load(cls, path: str = CALIBRATION_PATH) -> "Calibrator":
        p = Path(path)
        if not p.exists():
            return cls({})            # kalibrlanmagan → identity
        data = json.loads(p.read_text())
        if data.get("scorer_version") != SCORER_VERSION:
            print(f"⚠  Kalibrlash {data.get('scorer_version')} uchun, "
                  f"joriy versiya {SCORER_VERSION}. QAYTA KALIBRLANG.")
        return cls(data)

    def describe(self) -> str:
        o = self.mapping.get("overall", {})
        if o.get("method") == "linear":
            return f"overall: {o['a']:.3f}·raw + {o['b']:+.3f} (n={self.mapping.get('n_samples')})"
        return f"overall: {o.get('method', 'identity')} (n={self.mapping.get('n_samples')})"
