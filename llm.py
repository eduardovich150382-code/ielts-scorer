"""
LLM adapteri: retry, JSON majburlash, xarajat hisobi, disk keshi.

Kesh MUHIM: kalibrlash skriptini 20 marta qayta ishga tushirasiz.
Keshsiz har safar to'liq narx to'laysiz.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from config import CACHE_DIR, PRICING


@dataclass
class LLMResult:
    data: dict
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cached: bool = False
    raw_text: str = ""

    @property
    def cost_usd(self) -> float:
        p = PRICING.get(self.model)
        if not p:
            return 0.0
        return (self.input_tokens * p["in"] + self.output_tokens * p["out"]) / 1_000_000


@dataclass
class CostTracker:
    calls: int = 0
    cached_calls: int = 0
    total_usd: float = 0.0
    by_model: dict = field(default_factory=dict)

    def add(self, r: LLMResult) -> None:
        self.calls += 1
        if r.cached:
            self.cached_calls += 1
            return
        self.total_usd += r.cost_usd
        self.by_model[r.model] = self.by_model.get(r.model, 0.0) + r.cost_usd

    def report(self) -> str:
        return (f"chaqiruv={self.calls} (kesh={self.cached_calls}) "
                f"jami=${self.total_usd:.4f} " +
                " ".join(f"{m}=${c:.4f}" for m, c in self.by_model.items()))


TRACKER = CostTracker()


def _cache_key(system: str, user: str, model: str, schema: dict | None) -> str:
    h = hashlib.sha256()
    for part in (system, user, model, json.dumps(schema or {}, sort_keys=True)):
        h.update(part.encode())
    return h.hexdigest()[:32]


def _cache_read(key: str) -> dict | None:
    p = Path(CACHE_DIR) / f"{key}.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            p.unlink(missing_ok=True)
    return None


def _cache_write(key: str, payload: dict) -> None:
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
    (Path(CACHE_DIR) / f"{key}.json").write_text(json.dumps(payload))


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    return t.strip()


def _extract_json(text: str) -> dict:
    """LLM ba'zan JSON atrofida matn qo'shadi. Qat'iy, keyin bardoshli parsing."""
    t = _strip_fences(text)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    start, depth = t.find("{"), 0
    if start == -1:
        raise ValueError(f"JSON topilmadi: {text[:200]!r}")
    for i in range(start, len(t)):
        if t[i] == "{":
            depth += 1
        elif t[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(t[start:i + 1])
    raise ValueError(f"JSON to'liq emas: {text[:200]!r}")


_client = None


def _get_client():
    global _client
    if _client is None:
        from anthropic import Anthropic          # lazy import
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def call_json(
    system: str,
    user: str,
    model: str,
    schema: dict | None = None,
    max_tokens: int = 1500,
    temperature: float = 0.0,
    use_cache: bool = True,
    max_retries: int = 4,
) -> LLMResult:
    """LLM'ni chaqiradi va JSON obyekt qaytaradi."""
    key = _cache_key(system, user, model, schema)
    if use_cache and temperature == 0.0:
        hit = _cache_read(key)
        if hit is not None:
            r = LLMResult(data=hit["data"], model=model, cached=True,
                          raw_text=hit.get("raw", ""))
            TRACKER.add(r)
            return r

    tools = None
    tool_choice = None
    if schema:
        # Tool-use = ishonchli strukturaviy chiqish. JSON so'rashdan ancha barqaror.
        tools = [{"name": "submit", "description": "Natijani qaytaring",
                  "input_schema": schema}]
        tool_choice = {"type": "tool", "name": "submit"}

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            t0 = time.time()
            kwargs = dict(model=model, max_tokens=max_tokens,
                          temperature=temperature,
                          system=system,
                          messages=[{"role": "user", "content": user}])
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = tool_choice

            resp = _get_client().messages.create(**kwargs)
            latency = int((time.time() - t0) * 1000)

            data, raw = None, ""
            for block in resp.content:
                if getattr(block, "type", None) == "tool_use":
                    data = block.input
                    raw = json.dumps(block.input)
                    break
                if getattr(block, "type", None) == "text":
                    raw += block.text
            if data is None:
                data = _extract_json(raw)

            r = LLMResult(data=data, model=model,
                          input_tokens=resp.usage.input_tokens,
                          output_tokens=resp.usage.output_tokens,
                          latency_ms=latency, raw_text=raw)
            if use_cache and temperature == 0.0:
                _cache_write(key, {"data": data, "raw": raw})
            TRACKER.add(r)
            return r

        except Exception as e:                       # noqa: BLE001
            last_err = e
            if attempt == max_retries - 1:
                break
            time.sleep(min(2 ** attempt, 8))

    raise RuntimeError(f"LLM chaqiruvi {max_retries} urinishdan keyin muvaffaqiyatsiz: {last_err}")
