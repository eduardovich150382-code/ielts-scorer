# IELTS Writing Scorer + Kalibrlash

03-hujjatdagi arxitekturaning ishlaydigan implementatsiyasi.

```
config.py       Sozlamalar, versiyalash, maqsad metrikalar
rubrics.py      Band deskriptorlari (o'z so'zlarimizda) + tarafkashlik guard'lari
features.py     BOSQICH 1 — deterministik xususiyatlar (bepul, LLM'siz)
prompts.py      Mezon bo'yicha prompt'lar + annotatsiya prompt'i
llm.py          LLM adapteri: retry, tool-use JSON, xarajat hisobi, disk keshi
scorer.py       Asosiy pipeline (3 bosqich)
calibration.py  Post-hoc mapping: fit / apply / save
metrics.py      MAE, ±0.5, ±1.0, QWK, bias, band bo'yicha taqsimot
calibrate.py    CLI: evaluate / fit / gate / history
test_offline.py 55 ta test — API kalitisiz ishlaydi
```

## O'rnatish

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...

cp data/golden_set.example.json data/golden_set.json
cp data/anchors.example.json    data/anchors.json

python test_offline.py       # API'siz mantiqiy testlar (55 ta)
```

## Ish tartibi (03-hujjat, §7)

```bash
# 1. BASELINE — hech narsa o'zgartirmasdan, hozirgi holatni o'lchang
python calibrate.py evaluate --no-calibration --tag "baseline"

# 2. Promptni yaxshilang (anchor qo'shing, rubrikani aniqlashtiring),
#    har o'zgarishdan keyin qayta o'lchang
python calibrate.py evaluate --tag "4 ta anchor qo'shildi"
python calibrate.py history          # yaxshilanish ko'rinadimi?

# 3. Prompt yaxshilanishi to'xtaganda — mapping'ni moslang
python calibrate.py fit --holdout 0.3

# 4. Har deploy oldidan
python calibrate.py gate             # regressiya bo'lsa exit 1
```

**Tartib muhim.** Avval prompt, keyin mapping. Yomon prompt'ni mapping tuzatmaydi
— u faqat tizimli siljishni to'g'rilaydi, tasodifiy shovqinni emas.

---

## ⚠️ Beshta xato — buni qilmang

**1. Mapping'ni moslagan ma'lumotda baholash.**
`fit` majburiy holdout bo'linishi qiladi. Uni chetlab o'tmang — aks holda
o'zingizni aldayasiz va production'da MAE ikki barobar yomon chiqadi.

**2. Diapazonsiz oltin to'plam.**
Faqat 6.0–6.5 esselar yig'sangiz, kalibrlash ishlamaydi va QWK 0 chiqadi.
**4.5 dan 8.5 gacha** teng taqsimlangan namunalar kerak. Kod buni tekshiradi
va ogohlantiradi.

**3. `SCORER_VERSION` ni oshirmaslik.**
Prompt yoki rubrikani o'zgartirdingizmi — versiyani oshiring. Aks holda eski
mapping yangi prompt'ga qo'llaniladi va band'lar jimgina buziladi.

**4. 4 mezonni bitta chaqiruvda so'rash.**
Bu halo effektini keltirib chiqaradi — hamma mezon bir xil ball oladi.
Kod har mezonni alohida chaqiradi (parallel, shuning uchun sekin emas).

**5. Annotatsiya span'larini LLM'dan so'rash.**
LLM belgi indekslarini ishonchli bermaydi. Kod so'zma-so'z parcha so'raydi va
span'ni `str.find` bilan o'zi hisoblaydi (`_resolve_spans`). Topilmagan
annotatsiya `_unresolved` deb belgilanadi — UI'da uni ko'rsatmang.

---

## Anchor esselar — birinchi $300 sarfingiz

Kod anchor'siz ham ishlaydi, lekin **MAE sezilarli yomon bo'ladi**.
Metodistingizga band bo'yicha 4–5 ta esse baholatib oling
(`data/anchors.json`). Bu eng yuqori ROI'li sarfingiz.

`_anchors_for()` band diapazonini qamrab olib tanlaydi — bir xil band'dagi
4 ta namunani bermaydi.

---

## Xarajat nazorati

```python
from llm import TRACKER
print(TRACKER.report())   # chaqiruv=48 (kesh=32) jami=$0.4210
```

- **Disk keshi** (`cache/`) — kalibrlashni 20 marta qayta ishga tushirsangiz
  ham bir marta to'laysiz. `temperature=0` bo'lganda avtomatik ishlaydi.
- **Adaptiv self-consistency** — 3× chaqiruv faqat band 0.5 chegarasiga yaqin
  bo'lganda. `--self-consistency` bayrog'i bilan yoqiladi.
- Kalibrlashda annotatsiya o'chirilgan (`with_annotations=False`) — kerak emas,
  narxni ~40% kamaytiradi.
- Har `ScoreResult` da `cost_usd` bor → `evaluations.cost_usd` ga yozing
  (02-hujjatdagi sxema).

---

## Inson tekshiruviga yuborish

`needs_human_review=True` bo'lganda UI'da band'ni "taxminiy" deb ko'rsating.
Shartlar:
- mezonlar tarqoqligi ≥ 2.0 band (g'ayrioddiy profil)
- takroriy chaqiruvlar ≥ 1.0 band farq qildi
- matnda prompt-injection aniqlandi
- savoldan 25%+ ko'chirilgan
- matn 80 so'zdan qisqa

Faza 1'da bu holatlarni faqat belgilang. Faza 4'da inson navbatiga ulang.

---

## Speaking uchun

Bir xil arxitektura ishlaydi: `features.py` o'rniga prosodiya metrikalari
(WPM, pauza, filler), `rubrics.py` da FC/LR/GRA/P mezonlari, qolgan hamma
narsa — `calibration.py`, `metrics.py`, `calibrate.py` — o'zgarishsiz.
