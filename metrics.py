"""Kalibrlash metrikalari (03-hujjat, §4)."""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

from config import BAND_MIN, BAND_STEP, TARGETS


def _to_index(bands: np.ndarray) -> np.ndarray:
    """4.0..9.0 (0.5 qadam) -> 0..10 butun indeks (QWK uchun)."""
    return np.rint((bands - BAND_MIN) / BAND_STEP).astype(int)


def quadratic_weighted_kappa(true: np.ndarray, pred: np.ndarray,
                             n_classes: int = 11) -> float:
    """
    QWK — tasodifiy kelishuvni hisobga oladi. Ordinal baholash uchun standart.
    sklearn'siz, chunki n_classes ni majburlashimiz kerak (kam ma'lumotda
    ba'zi sinflar umuman uchramaydi va sklearn matritsani qisqartiradi).
    """
    t, p = _to_index(true), _to_index(pred)
    t = np.clip(t, 0, n_classes - 1)
    p = np.clip(p, 0, n_classes - 1)

    O = np.zeros((n_classes, n_classes))
    for a, b in zip(t, p):
        O[a, b] += 1

    w = np.zeros((n_classes, n_classes))
    for i in range(n_classes):
        for j in range(n_classes):
            w[i, j] = ((i - j) ** 2) / ((n_classes - 1) ** 2)

    hist_t = np.bincount(t, minlength=n_classes)
    hist_p = np.bincount(p, minlength=n_classes)
    E = np.outer(hist_t, hist_p).astype(float)
    E = E * (O.sum() / E.sum()) if E.sum() else E

    denom = (w * E).sum()
    if denom == 0:
        # Degenerativ holat: barcha haqiqiy bandlar bir xil (dispersiya nol).
        # QWK matematik aniqlanmagan. Agar kelishuv mukammal bo'lsa 1.0,
        # aks holda 0.0 qaytaramiz — 0.0 ni "yomon model" deb o'qimang,
        # bu oltin to'plamingizda diapazon yo'qligini bildiradi.
        return 1.0 if (w * O).sum() == 0 else 0.0
    return float(1 - (w * O).sum() / denom)


@dataclass
class Metrics:
    n: int
    mae: float
    rmse: float
    within_half: float
    within_one: float
    qwk: float
    bias: float
    exact: float
    sd_of_error: float

    def to_dict(self) -> dict:
        return asdict(self)

    def passes(self) -> tuple[bool, list[str]]:
        fails = []
        if self.mae > TARGETS["mae"]:
            fails.append(f"MAE {self.mae:.3f} > {TARGETS['mae']}")
        if self.within_half < TARGETS["within_half"]:
            fails.append(f"±0.5 {self.within_half:.1%} < {TARGETS['within_half']:.0%}")
        if self.within_one < TARGETS["within_one"]:
            fails.append(f"±1.0 {self.within_one:.1%} < {TARGETS['within_one']:.0%}")
        if self.qwk < TARGETS["qwk"]:
            fails.append(f"QWK {self.qwk:.3f} < {TARGETS['qwk']}")
        if abs(self.bias) > TARGETS["abs_bias"]:
            fails.append(f"|bias| {abs(self.bias):.3f} > {TARGETS['abs_bias']}")
        return (not fails), fails


def compute(true: list[float], pred: list[float]) -> Metrics:
    t, p = np.asarray(true, dtype=float), np.asarray(pred, dtype=float)
    err = p - t
    return Metrics(
        n=len(t),
        mae=float(np.mean(np.abs(err))),
        rmse=float(np.sqrt(np.mean(err ** 2))),
        within_half=float(np.mean(np.abs(err) <= 0.5)),
        within_one=float(np.mean(np.abs(err) <= 1.0)),
        qwk=quadratic_weighted_kappa(t, p),
        bias=float(np.mean(err)),           # musbat = AI saxiy
        exact=float(np.mean(np.abs(err) < 1e-9)),
        sd_of_error=float(np.std(err)),
    )


def by_band_breakdown(true: list[float], pred: list[float]) -> dict:
    """Qaysi band diapazonida xato ko'p? Diapazon siqilishini shu ochib beradi."""
    t, p = np.asarray(true, float), np.asarray(pred, float)
    out = {}
    for lo, hi, label in [(0, 5.5, "≤5.5"), (5.5, 6.5, "6.0-6.5"),
                          (6.5, 7.5, "7.0-7.5"), (7.5, 10, "≥8.0")]:
        m = (t >= lo) & (t < hi)
        if m.sum() == 0:
            continue
        e = p[m] - t[m]
        out[label] = {"n": int(m.sum()),
                      "mae": round(float(np.mean(np.abs(e))), 3),
                      "bias": round(float(np.mean(e)), 3)}
    return out


def format_report(overall: Metrics, per_criterion: dict[str, Metrics],
                  breakdown: dict, title: str = "") -> str:
    ok, fails = overall.passes()
    L = []
    if title:
        L += [f"\n{'=' * 62}", f" {title}", "=" * 62]
    L += [
        f"n = {overall.n}",
        "",
        f"  MAE                {overall.mae:.3f}   (maqsad ≤ {TARGETS['mae']})",
        f"  RMSE               {overall.rmse:.3f}",
        f"  ±0.5 band ichida   {overall.within_half:.1%}   (maqsad ≥ {TARGETS['within_half']:.0%})",
        f"  ±1.0 band ichida   {overall.within_one:.1%}   (maqsad ≥ {TARGETS['within_one']:.0%})",
        f"  Aniq moslik        {overall.exact:.1%}",
        f"  QWK                {overall.qwk:.3f}   (maqsad ≥ {TARGETS['qwk']})",
        f"  Bias               {overall.bias:+.3f}   ({'saxiy' if overall.bias > 0 else 'qattiq'})",
        f"  Xato SD            {overall.sd_of_error:.3f}",
        "",
        "  Mezon bo'yicha:",
    ]
    for c, m in per_criterion.items():
        L.append(f"    {c:<4} MAE {m.mae:.3f}  bias {m.bias:+.3f}  "
                 f"±0.5 {m.within_half:.0%}")
    L += ["", "  Haqiqiy band diapazoni bo'yicha:"]
    for label, d in breakdown.items():
        L.append(f"    {label:<8} n={d['n']:<4} MAE {d['mae']:.3f}  bias {d['bias']:+.3f}")
    L += ["", f"  NATIJA: {'✅ O‘TDI' if ok else '❌ O‘TMADI'}"]
    for f_ in fails:
        L.append(f"          ✗ {f_}")
    return "\n".join(L)
