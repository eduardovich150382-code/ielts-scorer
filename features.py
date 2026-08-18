"""
BOSQICH 1 — deterministik xususiyatlar.

LLM'dan so'z sanashni SO'RAMANG. Bu yerda hisoblangan hamma narsa bepul,
tez va 100% aniq. LLM faqat sifatiy baho uchun ishlatiladi.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, asdict

# Band 6 talabalari haddan tashqari ko'p ishlatadigan mexanik bog'lovchilar
MECHANICAL_LINKERS = {
    "firstly", "secondly", "thirdly", "lastly", "finally", "moreover",
    "furthermore", "in addition", "in conclusion", "to sum up", "all in all",
    "on the other hand", "as a result", "therefore", "however", "besides",
    "nowadays", "in my opinion", "to conclude",
}

# Rasmiy yozuvda tavsiya etilmaydigan qisqartmalar
CONTRACTIONS = re.compile(
    r"\b(?:don't|can't|won't|isn't|aren't|didn't|doesn't|it's|I'm|they're|we're|"
    r"you're|there's|that's|wasn't|weren't|hasn't|haven't|shouldn't|couldn't|"
    r"wouldn't|let's)\b", re.I)

SUBORDINATORS = {
    "although", "though", "whereas", "while", "because", "since", "unless",
    "whilst", "despite", "whether", "if", "when", "whenever", "which", "who",
    "whom", "whose", "that", "as", "after", "before", "until",
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "been", "being", "it", "its", "this",
    "that", "these", "those", "as", "at", "by", "from", "has", "have", "had",
    "not", "no", "so", "than", "then", "there", "their", "they", "we", "you",
    "i", "he", "she", "his", "her", "our", "your", "my", "me", "him", "them",
    "will", "would", "can", "could", "should", "may", "might", "must", "do",
    "does", "did", "if", "which", "who", "what", "when", "where", "how", "all",
    "more", "most", "some", "any", "such", "only", "also", "into", "about",
}

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])")


@dataclass
class TextFeatures:
    word_count: int
    under_minimum: bool
    paragraph_count: int
    sentence_count: int
    mean_sentence_len: float
    sentence_len_sd: float
    long_sentences: int          # > 40 so'z — ehtimol run-on
    short_sentences: int         # < 8 so'z
    type_token_ratio: float      # leksik xilma-xillik (uzunlikka normallashtirilgan)
    hapax_ratio: float           # bir marta uchragan so'zlar ulushi
    mechanical_linker_count: int
    mechanical_linker_density: float   # 100 so'zga
    distinct_linkers: int
    subordinator_ratio: float    # murakkab tuzilma proksi-ko'rsatkichi
    contraction_count: int
    prompt_overlap: float        # savol bilan mazmunli so'z qoplanishi (TA signali)
    prompt_copy_ratio: float     # savoldan so'zma-so'z ko'chirish (⚠ TA jazosi)
    repeated_word_top: list[tuple[str, int]]
    avg_word_length: float

    def to_dict(self) -> dict:
        return asdict(self)


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def _sentences(text: str) -> list[str]:
    parts = [s.strip() for s in _SENT_RE.split(text.strip()) if s.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def _ngrams(tokens: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def extract(essay: str, prompt: str, task_kind: str = "writing_t2") -> TextFeatures:
    from config import MIN_WORDS

    words = _words(essay)
    lower = [w.lower() for w in words]
    wc = len(words)
    sents = _sentences(essay)
    sent_lens = [len(_words(s)) for s in sents] or [0]

    mean_len = sum(sent_lens) / len(sent_lens)
    variance = sum((x - mean_len) ** 2 for x in sent_lens) / len(sent_lens)

    # TTR uzunlikka bog'liq — root TTR ishlatamiz (Guiraud indeksi)
    uniq = set(lower)
    ttr = len(uniq) / math.sqrt(wc) if wc else 0.0
    freq: dict[str, int] = {}
    for w in lower:
        freq[w] = freq.get(w, 0) + 1
    hapax = sum(1 for c in freq.values() if c == 1) / len(freq) if freq else 0.0

    text_low = essay.lower()
    linker_hits = [lk for lk in MECHANICAL_LINKERS if lk in text_low]
    linker_count = sum(text_low.count(lk) for lk in linker_hits)

    subord = sum(1 for w in lower if w in SUBORDINATORS)

    # Prompt bilan solishtirish
    prompt_words = {w.lower() for w in _words(prompt)} - STOPWORDS
    essay_content = [w for w in lower if w not in STOPWORDS]
    overlap = (len(prompt_words & set(essay_content)) / len(prompt_words)
               if prompt_words else 0.0)

    # So'zma-so'z ko'chirish: 6-gramm mosligi
    p_grams = _ngrams([w.lower() for w in _words(prompt)], 6)
    e_grams = _ngrams(lower, 6)
    copy_ratio = (len(p_grams & e_grams) / len(e_grams)) if e_grams else 0.0

    content_freq = {w: c for w, c in freq.items() if w not in STOPWORDS and c > 2}
    top_rep = sorted(content_freq.items(), key=lambda kv: -kv[1])[:5]

    paragraphs = [p for p in re.split(r"\n\s*\n", essay.strip()) if p.strip()]

    return TextFeatures(
        word_count=wc,
        under_minimum=wc < MIN_WORDS.get(task_kind, 250),
        paragraph_count=len(paragraphs),
        sentence_count=len(sents),
        mean_sentence_len=round(mean_len, 1),
        sentence_len_sd=round(math.sqrt(variance), 1),
        long_sentences=sum(1 for x in sent_lens if x > 40),
        short_sentences=sum(1 for x in sent_lens if 0 < x < 8),
        type_token_ratio=round(ttr, 3),
        hapax_ratio=round(hapax, 3),
        mechanical_linker_count=linker_count,
        mechanical_linker_density=round(linker_count / wc * 100, 2) if wc else 0.0,
        distinct_linkers=len(linker_hits),
        subordinator_ratio=round(subord / wc, 3) if wc else 0.0,
        contraction_count=len(CONTRACTIONS.findall(essay)),
        prompt_overlap=round(overlap, 3),
        prompt_copy_ratio=round(copy_ratio, 3),
        repeated_word_top=top_rep,
        avg_word_length=round(sum(len(w) for w in words) / wc, 2) if wc else 0.0,
    )


def hard_penalties(f: TextFeatures, task_kind: str) -> list[str]:
    """
    LLM'ga TOPSHIRILMAYDIGAN qat'iy qoidalar. Bular deterministik bo'lishi shart —
    LLM ularni ba'zan e'tiborsiz qoldiradi.
    """
    from config import MIN_WORDS

    out = []
    minimum = MIN_WORDS.get(task_kind, 250)
    if f.under_minimum:
        deficit = (minimum - f.word_count) / minimum
        out.append(
            f"HAJM YETISHMAYDI: {f.word_count}/{minimum} so'z "
            f"({deficit:.0%} kam). TA bandi kamida 1.0 pasaytirilsin."
        )
    if f.prompt_copy_ratio > 0.15:
        out.append(
            f"SAVOLDAN KO'CHIRISH: matnning {f.prompt_copy_ratio:.0%} qismi savol "
            "bilan bir xil. Ko'chirilgan qism baholanmaydi."
        )
    if f.paragraph_count < 3 and f.word_count > 150:
        out.append(
            f"PARAGRAFLASH: atigi {f.paragraph_count} paragraf. CC bandi 6 dan "
            "yuqori bo'la olmaydi."
        )
    if f.prompt_overlap < 0.15 and f.word_count > 100:
        out.append(
            "MAVZUDAN CHETLASHISH EHTIMOLI: esse savol leksikasi bilan deyarli "
            "kesishmaydi. TA ni sinchiklab tekshiring."
        )
    return out
