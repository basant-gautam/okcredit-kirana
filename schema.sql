-- ============================================================
-- Stationary Shop AI — Supabase Database Schema
-- Run this once in the Supabase SQL Editor
-- (Dashboard → SQL Editor → New Query → Paste → Run)
-- ============================================================

-- Enable Row Level Security (RLS) globally
-- (RLS policies below ensure users can only touch their own rows)

-- ──────────────────────────────────────────────────────────────
-- TABLE: inventory
-- Stores each user's product catalogue and current stock levels.
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.inventory (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    item_name       TEXT        NOT NULL,
    stock           INTEGER     NOT NULL DEFAULT 0,
    avg_daily_sale  NUMERIC(8,2) NOT NULL DEFAULT 1,
    reorder         INTEGER     NOT NULL DEFAULT 10,
    price           NUMERIC(10,2) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, item_name)          -- prevent duplicate items per user
);

ALTER TABLE public.inventory ENABLE ROW LEVEL SECURITY;

-- RLS policies
CREATE POLICY "inventory: users manage own rows"
    ON public.inventory
    FOR ALL
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Index for fast per-user queries
CREATE INDEX IF NOT EXISTS idx_inventory_user_id ON public.inventory(user_id);


-- ──────────────────────────────────────────────────────────────
-- TABLE: sales_history
-- Append-only log of every sale transaction.
-- Used by PredictionEngine to train Random Forest models.
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.sales_history (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    date        DATE        NOT NULL,
    item_name   TEXT        NOT NULL,
    units_sold  INTEGER     NOT NULL DEFAULT 0,
    day_of_week SMALLINT    NOT NULL,   -- 0=Mon … 6=Sun
    month       SMALLINT    NOT NULL,   -- 1–12
    is_weekend  SMALLINT    NOT NULL DEFAULT 0,  -- 0 or 1
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.sales_history ENABLE ROW LEVEL SECURITY;

-- RLS policies
CREATE POLICY "sales_history: users manage own rows"
    ON public.sales_history
    FOR ALL
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Indexes for fast per-user + per-item queries
CREATE INDEX IF NOT EXISTS idx_sales_user_id   ON public.sales_history(user_id);
CREATE INDEX IF NOT EXISTS idx_sales_item_name ON public.sales_history(user_id, item_name);
CREATE INDEX IF NOT EXISTS idx_sales_date      ON public.sales_history(user_id, date DESC);
