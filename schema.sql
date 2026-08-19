-- Faza 0 Telegram bot uchun minimal sxema.
-- Nomlar/shakl 02-hujjatdagi to'liq sxemaga ataylab yaqin (users, events) —
-- Faza 1 web MVP'ga o'tishda merge qilish osonroq bo'lsin uchun.
-- Farq: id BIGSERIAL (02-hujjatda UUID), attempts/writing_responses/evaluations
-- uchburchagi o'rniga bitta denormallashtirilgan essay_submissions.

CREATE TABLE IF NOT EXISTS users (
  id                 BIGSERIAL PRIMARY KEY,
  telegram_id        BIGINT UNIQUE NOT NULL,
  username           TEXT,
  locale             TEXT NOT NULL DEFAULT 'uz',      -- 'uz' | 'ru'
  target_band        NUMERIC(2,1),
  exam_date          DATE,
  pending_prompt_id  TEXT,                             -- prompts_bank.py dagi id
  last_prompt_id     TEXT,                             -- ketma-ket takrorlanmasin
  paywall_clicked_at TIMESTAMPTZ,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_active_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS essay_submissions (
  id                 BIGSERIAL PRIMARY KEY,
  user_id            BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  prompt_id          TEXT NOT NULL,
  source             TEXT NOT NULL,                    -- 'text' | 'photo'
  essay_text         TEXT NOT NULL,
  status             TEXT NOT NULL DEFAULT 'scoring',   -- scoring|scored|failed
  overall_band       NUMERIC(2,1),
  criteria           JSONB,                             -- {"TA":..,"CC":..,"LR":..,"GRA":..}
  top_errors         JSONB,                             -- top-5 annotatsiya (severity bo'yicha)
  priorities_uz      JSONB,                             -- 3 ta umumiy maslahat
  needs_human_review BOOLEAN NOT NULL DEFAULT false,
  cost_usd           NUMERIC(8,5),
  latency_ms         INT,
  error_message      TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_essay_user_time ON essay_submissions(user_id, created_at);

-- Kuniga 1 bepul limitni Asia/Tashkent kun chegarasi bilan hisoblash uchun
-- ishlatiladigan asosiy indeks — yuqoridagisi yetarli (user_id, created_at).

CREATE TABLE IF NOT EXISTS events (
  id         BIGSERIAL PRIMARY KEY,
  user_id    BIGINT REFERENCES users(id) ON DELETE SET NULL,
  name       TEXT NOT NULL,     -- start|lang_set|essay_submitted|essay_scored|
                                 -- paywall_click|nudge_sent|nudge_click
  props      JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_name_time ON events(name, created_at);
