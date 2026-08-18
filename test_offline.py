#!/usr/bin/env python3
"""
Offline testlar — API kaliti va internetsiz ishlaydi.

    python test_offline.py

Bu testlar LLM'ni MOCK qiladi. Ular tekshiradi:
  - deterministik xususiyatlar to'g'ri hisoblanadimi
  - qat'iy jazolar ishlaydimi
  - metrikalar to'g'rimi (ma'lum javoblarga qarshi)
  - kalibrlash mapping'i tarafkashlikni tuzatadimi
  - annotatsiya span'lari matnda to'g'ri joylashadimi
"""
from __future__ import annotations

import json
import sys

import numpy as np

import features
import metrics as M
from calibration import Calibrator, round_to_half

PASS, FAIL = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


# ============================================================ 1. FEATURES
print("\n[1] Deterministik xususiyatlar")

PROMPT = ("Some people believe that unpaid community service should be a "
          "compulsory part of high school programmes. To what extent do you "
          "agree or disagree?")

WEAK = """Nowadays community service is very important topic. Firstly, I think
students must do it because it is good for society. Secondly, it help them to
learn new skills. Moreover, it is good for their future job.

However, some people don't agree with this idea. In conclusion, I strongly
believe that community service should be compulsory in school."""

STRONG = """The proposition that secondary schools should mandate unpaid community
work has gained considerable traction among educational policymakers. While
critics reasonably question whether compulsion undermines the spirit of
volunteering, I would argue that the developmental benefits substantially
outweigh this philosophical objection.

The most compelling case for mandatory service rests on its capacity to expose
adolescents to social realities they would otherwise never encounter. A student
from an affluent suburb who spends forty hours in a food bank acquires an
understanding of structural poverty that no classroom discussion could replicate.
This experiential dimension is precisely what conventional curricula struggle to
deliver.

Detractors contend that coerced altruism is a contradiction in terms, and that
students who resent the obligation will derive nothing from it. This objection
carries some weight, yet it overlooks how frequently initial reluctance gives way
to genuine engagement once young people witness the tangible impact of their
contribution.

On balance, therefore, the case for compulsory service is persuasive, provided
schools retain flexibility in how students fulfil the requirement."""

fw = features.extract(WEAK, PROMPT, "writing_t2")
fs = features.extract(STRONG, PROMPT, "writing_t2")

check("so'z hisobi ishlaydi", 50 < fw.word_count < 100, f"{fw.word_count}")
check("zaif matnda mexanik bog'lovchilar aniqlanadi",
      fw.mechanical_linker_density > fs.mechanical_linker_density,
      f"zaif={fw.mechanical_linker_density} kuchli={fs.mechanical_linker_density}")
check("kuchli matnda leksik xilma-xillik yuqori",
      fs.type_token_ratio > fw.type_token_ratio,
      f"{fs.type_token_ratio} vs {fw.type_token_ratio}")
check("qisqartmalar aniqlanadi (don't)", fw.contraction_count >= 1)
check("murakkab tuzilma nisbati kuchli matnda yuqori",
      fs.subordinator_ratio > fw.subordinator_ratio)
check("prompt qoplanishi hisoblanadi", 0 < fs.prompt_overlap <= 1.0,
      f"{fs.prompt_overlap}")
check("paragraf sanog'i to'g'ri", fs.paragraph_count == 4, f"{fs.paragraph_count}")

# Savoldan ko'chirish aniqlanishi
COPIED = PROMPT + " " + PROMPT + " I agree with this statement completely."
fc = features.extract(COPIED, PROMPT, "writing_t2")
check("savoldan ko'chirish aniqlanadi", fc.prompt_copy_ratio > 0.3,
      f"{fc.prompt_copy_ratio}")

# ============================================================ 2. PENALTIES
print("\n[2] Qat'iy jazolar")

pw = features.hard_penalties(fw, "writing_t2")
ps = features.hard_penalties(fs, "writing_t2")

check("qisqa esse jazolanadi", any("HAJM" in p for p in pw))
# Kam paragraf jazosi faqat matn yetarlicha uzun bo'lganda ishlaydi
long_two_para = features.extract(
    ("Community service is important for students today. " * 20) +
    "\n\n" + ("Therefore I agree with the statement completely. " * 5),
    PROMPT, "writing_t2")
check("kam paragraf jazolanadi (uzun matnda)",
      any("PARAGRAF" in p for p in features.hard_penalties(long_two_para, "writing_t2")),
      f"paragraflar={long_two_para.paragraph_count} sozlar={long_two_para.word_count}")
check("qisqa matnda paragraf jazosi ISHLAMAYDI (to'g'ri xatti-harakat)",
      not any("PARAGRAF" in p for p in pw))
check("ko'chirish jazolanadi",
      any("KO'CHIRISH" in p for p in features.hard_penalties(fc, "writing_t2")))

off_topic = features.extract(
    "I love pizza very much. Pizza is delicious food. " * 20, PROMPT, "writing_t2")
check("mavzudan chetlashish aniqlanadi",
      any("CHETLASHISH" in p for p in features.hard_penalties(off_topic, "writing_t2")))

# ============================================================ 3. METRICS
print("\n[3] Metrikalar")

check("mukammal bashoratda MAE=0",
      M.compute([6.0, 7.0, 5.5], [6.0, 7.0, 5.5]).mae == 0.0)
check("mukammal bashoratda QWK=1",
      abs(M.compute([5.0, 6.0, 7.0, 8.0], [5.0, 6.0, 7.0, 8.0]).qwk - 1.0) < 1e-6)

m = M.compute([6.0, 6.0, 6.0, 6.0], [6.5, 6.5, 6.5, 6.5])
check("bias saxiylikni to'g'ri ko'rsatadi", abs(m.bias - 0.5) < 1e-9, f"{m.bias}")
check("±0.5 to'liq qamrov", m.within_half == 1.0)
check("MAE to'g'ri", abs(m.mae - 0.5) < 1e-9)

m2 = M.compute([5.0, 6.0, 7.0, 8.0], [6.5, 6.5, 6.5, 6.5])
check("diapazon siqilishi past QWK beradi", m2.qwk < 0.3, f"QWK={m2.qwk:.3f}")

bd = M.by_band_breakdown([5.0, 5.5, 6.0, 7.0, 8.0], [6.0, 6.0, 6.0, 6.5, 6.5])
check("band bo'yicha taqsimot ishlaydi", "≤5.5" in bd and "≥8.0" in bd)
check("past bandda saxiylik ko'rinadi", bd["≤5.5"]["bias"] > 0)
check("yuqori bandda qattiqlik ko'rinadi", bd["≥8.0"]["bias"] < 0)

# Dispersiyasiz to'plam: QWK aniqlanmagan, mukammal kelishuvda 1.0
check("dispersiyasiz mukammal kelishuvda QWK=1",
      M.compute([6.0] * 20, [6.0] * 20).qwk == 1.0)
check("dispersiyasiz nomukammal kelishuvda QWK=0",
      M.compute([6.0] * 20, [7.0] * 20).qwk == 0.0)
# Realistik to'plam darvozadan o'tishi kerak
real_true = [4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0] * 3
real_pred = [t + (0.5 if i % 4 == 0 else 0.0) for i, t in enumerate(real_true)]
targets_ok, fails = M.compute(real_true, real_pred).passes()
check("realistik yaxshi natija darvozadan o'tadi", targets_ok, str(fails))

# ============================================================ 4. CALIBRATION
print("\n[4] Kalibrlash")

check("round_to_half 6.3 -> 6.5", round_to_half(6.3) == 6.5)
check("round_to_half 6.2 -> 6.0", round_to_half(6.2) == 6.0)
check("round_to_half chegarani ushlaydi", round_to_half(11.0) == 9.0)

# Sun'iy saxiy scorer: har doim +0.5 band beradi
rng = np.random.default_rng(7)
true_bands = rng.choice([4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0], size=120)
raw_bands = np.clip(true_bands + 0.5 + rng.normal(0, 0.2, 120), 4.0, 9.0)

records = [{"raw_overall": float(r), "true_overall": float(t),
            "raw_criteria": {c: float(r) for c in ("TA", "CC", "LR", "GRA")},
            "true_criteria": {c: float(t) for c in ("TA", "CC", "LR", "GRA")}}
           for r, t in zip(raw_bands, true_bands)]

split = 84
cal = Calibrator.fit(records[:split], method="linear")
test = records[split:]

before = M.compute([r["true_overall"] for r in test],
                   [round_to_half(r["raw_overall"]) for r in test])
after = M.compute([r["true_overall"] for r in test],
                  [cal.apply_overall(r["raw_overall"]) for r in test])

check("kalibrlash MAE ni yaxshilaydi", after.mae < before.mae,
      f"oldin={before.mae:.3f} keyin={after.mae:.3f}")
check("kalibrlash bias ni kamaytiradi", abs(after.bias) < abs(before.bias),
      f"oldin={before.bias:+.3f} keyin={after.bias:+.3f}")
check("kalibrlangan MAE maqsadga yetadi", after.mae <= 0.40, f"{after.mae:.3f}")

# Izotonik variant
cal_iso = Calibrator.fit(records[:split], method="isotonic")
check("izotonik mapping yasaladi (n>=80)",
      cal_iso.mapping["overall"]["method"] == "isotonic")

# Xavfsizlik: mantiqsiz nishab rad etiladi
# Dispersiyasiz raw (scorer hammaga 6.0 beradi) -> mapping rad etiladi
flat = [{"raw_overall": 6.0, "true_overall": float(4 + i * 0.3),
         "raw_criteria": {}, "true_criteria": {}} for i in range(15)]
cal_flat = Calibrator.fit(flat, method="linear")
check("dispersiyasiz scorer uchun mapping rad etiladi",
      cal_flat.mapping["overall"]["method"] == "identity",
      str(cal_flat.mapping["overall"]))

# Shovqinli, korrelyatsiyasiz ma'lumot -> mapping rad etiladi
rng2 = np.random.default_rng(3)
noise = [{"raw_overall": float(rng2.choice([5.0,6.0,7.0,8.0])),
          "true_overall": float(rng2.choice([5.0,6.0,7.0,8.0])),
          "raw_criteria": {}, "true_criteria": {}} for _ in range(60)]
cal_noise = Calibrator.fit(noise, method="linear")
check("korrelyatsiyasiz ma'lumotda mapping rad etiladi",
      cal_noise.mapping["overall"]["method"] == "identity",
      str(cal_noise.mapping["overall"].get("warning")))

# Kam ma'lumot -> identity
cal_tiny = Calibrator.fit(records[:5], method="linear")
check("kam ma'lumotda identity qaytaradi",
      cal_tiny.mapping["overall"]["method"] == "identity")

# ============================================================ 5. SPANS
print("\n[5] Annotatsiya span'lari")

import scorer as S

text = "It help them to learn new skills. Moreover it help them a lot."
anns = [
    {"original": "It help them to learn", "suggestion": "It helps them to learn"},
    {"original": "Moreover it help", "suggestion": "Moreover, it helps"},
    {"original": "BU MATNDA YO'Q", "suggestion": "x"},
]
resolved = S._resolve_spans(text, anns)

check("birinchi span topildi", resolved[0].get("span") == [0, 21],
      str(resolved[0].get("span")))
check("ikkinchi span topildi (takroriy so'z bo'lsa ham)",
      resolved[1].get("span") is not None)
check("span'lar kesishmaydi",
      resolved[0]["span"][1] <= resolved[1]["span"][0])
check("topilmagan parcha belgilanadi", resolved[2].get("_unresolved") is True)
check("span matndan to'g'ri parchani beradi",
      text[resolved[0]["span"][0]:resolved[0]["span"][1]] == "It help them to learn")

# ============================================================ 6. SC TRIGGER
print("\n[6] Adaptiv self-consistency")

check("6.5 chegara emas -> qayta chaqiruv yo'q", not S._needs_second_opinion(6.5))
check("6.25 chegara -> qayta chaqiruv bor", S._needs_second_opinion(6.25))
check("6.0 chegara emas", not S._needs_second_opinion(6.0))

# ============================================================ 7. PROMPTS
print("\n[7] Prompt yig'ilishi")

from prompts import build_criterion_system, build_criterion_user_message

sys_p = build_criterion_system("CC")
check("system promptda mezon nomi bor", "Coherence" in sys_p)
check("system promptda injection himoyasi bor",
      "prompt_injection_detected" in sys_p)
check("system promptda tarafkashlik ogohlantirishi bor",
      "Firstly/Secondly" in sys_p)
check("boshqa mezon rubrikasi qo'shilmagan",
      "Task Achievement" not in sys_p.split("<band_deskriptorlari")[1])

user_p = build_criterion_user_message(
    "CC", PROMPT, WEAK, fw.to_dict(),
    [{"band": 6.0, "text": "namuna", "note": "izoh"}], pw)
check("user promptda talaba matni teglangan", "<talaba_matni>" in user_p)
check("user promptda statistika bor", "avtomatik_statistika" in user_p)
check("user promptda qat'iy qoidalar bor", "qat_iy_qoidalar" in user_p)
check("user promptda anchor bor", "anchor_namunalar" in user_p)

# ============================================================ 8. JSON PARSE
print("\n[8] JSON parsing bardoshliligi")

from llm import _extract_json

check("toza JSON", _extract_json('{"band": 6.5}')["band"] == 6.5)
check("markdown fence", _extract_json('```json\n{"band": 7}\n```')["band"] == 7)
check("atrofdagi matn",
      _extract_json('Mana javob:\n{"band": 6.0}\nRahmat')["band"] == 6.0)
check("ichma-ich obyekt",
      _extract_json('{"a":{"b":{"c":1}}}')["a"]["b"]["c"] == 1)

# ============================================================
print(f"\n{'=' * 50}")
print(f"  O'TDI: {PASS}   O'TMADI: {FAIL}")
print("=" * 50)
sys.exit(1 if FAIL else 0)
