"""
Band deskriptorlari — O'Z SO'ZLARIMIZ bilan qayta yozilgan.

⚠ HUQUQIY: Cambridge/British Council/IDP ning rasmiy band descriptor
matnini so'zma-so'z ko'chirmang. Quyidagilar — imtihon standartining
mustaqil, qisqartirilgan tavsifi. Metodistingiz bilan ko'rib chiqing va
o'z formulirovkangizni yarating.
"""
from __future__ import annotations

RUBRICS: dict[str, dict[int, str]] = {
    # ---------------------------------------------------------------- TA
    "TA": {
        5: "Savolga qisman javob beradi; asosiy fikr bor, lekin rivojlantirilmagan "
           "yoki chetga chiqadi. Task 1 da asosiy tendensiyalar tanlanmagan yoki "
           "ma'lumot noto'g'ri o'qilgan. Pozitsiya noaniq yoki qarama-qarshi. "
           "Hajm normadan kam bo'lishi mumkin.",
        6: "Savolning barcha qismlariga javob beradi, lekin ba'zilari yuzaki. "
           "Pozitsiya bor va umuman aniq. Fikrlar tegishli, ammo dalillar umumiy, "
           "misollar kam yoki kengaytirilmagan. Task 1 da asosiy xususiyatlar "
           "qamrab olingan, ba'zi tafsilotlar noaniq.",
        7: "Savolning barcha qismlariga aniq javob beradi. Pozitsiya boshdan-oxir "
           "izchil. Asosiy fikrlar rivojlantirilgan va tegishli misollar bilan "
           "quvvatlangan, garchi ba'zilari haddan tashqari umumlashtirilgan bo'lsa ham. "
           "Task 1 da muhim xususiyatlar aniq tanlangan va taqqoslangan.",
        8: "Savolga to'liq va aniq javob. Fikrlar yaxshi rivojlantirilgan, konkret va "
           "ishonarli qo'llab-quvvatlangan. Pozitsiya kuchli va bir xil. Task 1 da "
           "ma'lumot mohirona umumlashtirilgan, muhim va ikkinchi darajali "
           "xususiyatlar ajratilgan.",
    },
    # ---------------------------------------------------------------- CC
    "CC": {
        5: "Ba'zi tashkiliylik bor, lekin fikrlar ketma-ketligi tartibsiz. "
           "Bog'lovchilar noto'g'ri yoki haddan tashqari ko'p ishlatilgan. "
           "Paragraflash yo'q yoki chalkash. Referensiya (olmoshlar, takror) "
           "noaniqlik yaratadi.",
        6: "Ma'lumot umuman izchil tartibda. Paragraflash bor, lekin har doim ham "
           "mantiqiy emas — ba'zi paragraflarda aniq asosiy fikr yo'q. Bog'lovchilar "
           "ishlatiladi, lekin mexanik yoki bir xil (Firstly, Secondly, In conclusion). "
           "Ba'zan haddan ortiq yoki yetishmaydi.",
        7: "Fikrlar mantiqiy oqadi, o'quvchi kuch sarflamaydi. Har bir paragrafda "
           "aniq asosiy fikr bor. Kohesiya vositalari moslashuvchan va tabiiy "
           "ishlatilgan, ba'zi kichik noaniqliklar bo'lishi mumkin. Referensiya aniq.",
        8: "Mantiqiy oqim uzluksiz va sezilmas. Kohesiya shu darajada tabiiyki, "
           "o'quvchi uni payqamaydi. Paragraflash mukammal. Ma'lumot va argument "
           "ustalik bilan boshqarilgan.",
    },
    # ---------------------------------------------------------------- LR
    "LR": {
        5: "Cheklangan lug'at, ammo minimal talabga javob beradi. So'z tanlash va "
           "imloda muntazam xatolar bor, ular o'quvchini qiynaydi. Takrorlanish ko'p. "
           "Kollokatsiyalar ko'pincha noto'g'ri.",
        6: "Yetarli lug'at boyligi, mavzuga moslashuvchanlik bor. Kamroq uchraydigan "
           "so'zlarni ishlatishga urinish bor, lekin aniqlik nuqsonli. So'z tanlash va "
           "imloda xatolar bor, ammo aloqani buzmaydi. Kollokatsiya xatolari seziladi.",
        7: "Yetarli darajada keng lug'at, moslashuvchan ishlatiladi. Kamroq uchraydigan "
           "so'zlar va idiomatik iboralar mavjud va odatda to'g'ri. Kollokatsiyalar "
           "asosan tabiiy. Ba'zi noaniq so'z tanlashlar va imlo xatolari bor.",
        8: "Boy va aniq lug'at, murakkab ma'nolarni erkin ifodalaydi. Kamroq "
           "uchraydigan leksika mohirona ishlatilgan. Kollokatsiyalar tabiiy. "
           "Imlo va so'z yasashda faqat kamdan-kam xato.",
    },
    # ---------------------------------------------------------------- GRA
    "GRA": {
        5: "Cheklangan tuzilmalar diapazoni; sodda gaplar ustunlik qiladi. Murakkab "
           "gaplarga urinishlar odatda xato. Grammatik va punktuatsiya xatolari "
           "chastotali va ba'zan ma'noni buzadi.",
        6: "Sodda va murakkab tuzilmalar aralashmasi. Murakkab gaplarda xatolar "
           "ko'proq. Grammatik va punktuatsiya xatolari bor, lekin aloqani kamdan-kam "
           "buzadi. Artikl, predlog, fe'l zamoni xatolari tipik.",
        7: "Murakkab tuzilmalarning yaxshi diapazoni. Gaplarning ko'pchiligi xatosiz. "
           "Ba'zi grammatik va punktuatsiya xatolari bor, lekin ular kam va "
           "tushunishni buzmaydi.",
        8: "Keng diapazon, erkin va aniq ishlatilgan. Gaplarning aksariyati mutlaqo "
           "xatosiz. Faqat kamdan-kam, tizimsiz xatolar yoki tilning nostandart, "
           "ammo maqsadli ishlatilishi.",
    },
}

# Har bir mezon uchun scorer'ga beriladigan qo'shimcha ogohlantirishlar —
# LLM tarafkashliklariga qarshi (03-hujjat, §1).
BIAS_GUARDS: dict[str, str] = {
    "TA": (
        "Esse chiroyli yozilgani BAND KO'TARMAYDI. Savolning HAR bir qismiga "
        "javob berilganini alohida tekshiring. Agar savolda ikkita savol bo'lsa "
        "(masalan 'discuss both views AND give your opinion'), ikkalasi ham "
        "bajarilganini tasdiqlang. Uzunlik o'z-o'zidan TA ni oshirmaydi."
    ),
    "CC": (
        "Ko'p bog'lovchi ishlatilishi YAXSHI EMAS. 'Firstly/Secondly/Moreover' "
        "mexanik ketma-ketligi band 6 belgisi, band 7 emas. Har paragrafda bitta "
        "aniq asosiy fikr bormi — shuni tekshiring."
    ),
    "LR": (
        "Kamdan-kam uchraydigan so'z ishlatilgani o'z-o'zidan band ko'tarmaydi — "
        "u TO'G'RI va TABIIY ishlatilgan bo'lishi kerak. 'Plethora', 'myriad' kabi "
        "o'rinsiz qo'llangan so'zlar bandNI PASAYTIRADI. Kollokatsiya xatolarini "
        "alohida sanang."
    ),
    "GRA": (
        "Xato SONI emas, xato ZICHLIGI va TA'SIRI muhim. 300 so'zli esseda 5 ta "
        "kichik artikl xatosi — band 7 ga to'sqinlik qilmaydi. Ma'noni buzuvchi "
        "2 ta xato esa qiladi. Murakkab tuzilmalar diapazonini alohida baholang."
    ),
}


def rubric_block(criterion: str) -> str:
    """Bitta mezon uchun band deskriptorlarini XML blok sifatida qaytaradi."""
    lines = [f"<band_deskriptorlari mezon=\"{criterion}\">"]
    for band in sorted(RUBRICS[criterion]):
        lines.append(f"  <band qiymat=\"{band}\">{RUBRICS[criterion][band]}</band>")
    lines.append("</band_deskriptorlari>")
    return "\n".join(lines)
