-- ============================================================
-- Migration 001: Initial Schema
-- Project: HairDrama Task Manager
-- Run this in Supabase SQL Editor
-- ============================================================

-- Enable UUID generation (Supabase has this by default, but safe to ensure)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- TABLE: users
-- Stores Google OAuth users. google_id links back to Google's
-- unique user identifier. We also store avatar for UI display.
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    name        VARCHAR(255),
    avatar_url  TEXT,
    google_id   VARCHAR(255) UNIQUE,        -- Google's "sub" field from ID token
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABLE: tasks
-- Core task entity. Each task has a creator and an assignee.
-- Status follows: todo -> in_progress -> done
-- Priority: low | medium | high
-- ============================================================
CREATE TABLE IF NOT EXISTS tasks (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title        VARCHAR(255) NOT NULL,
    description  TEXT,
    status       VARCHAR(50)  NOT NULL DEFAULT 'todo'    CHECK (status IN ('todo', 'in_progress', 'done')),
    priority     VARCHAR(50)  NOT NULL DEFAULT 'medium'  CHECK (priority IN ('low', 'medium', 'high')),
    due_date     DATE,
    created_by   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    assigned_to  UUID REFERENCES users(id) ON DELETE SET NULL,  -- nullable: task may be unassigned
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABLE: task_comments
-- Users can leave comments on any task (threaded discussion).
-- Cascades delete when the parent task is removed.
-- ============================================================
CREATE TABLE IF NOT EXISTS task_comments (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id    UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABLE: activity_logs
-- Immutable audit trail. Every important action is recorded
-- here (task created, status changed, reassigned, etc.)
-- action_type examples: 'task_created', 'status_changed',
--                       'assigned', 'comment_added'
-- meta is a JSONB blob for flexible extra data per action.
-- ============================================================
CREATE TABLE IF NOT EXISTS activity_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id     UUID REFERENCES tasks(id) ON DELETE CASCADE,
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    action_type VARCHAR(100) NOT NULL,
    meta        JSONB DEFAULT '{}',        -- e.g. {"old_status": "todo", "new_status": "done"}
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- Speed up the most frequent query patterns:
--   - List tasks assigned to a user
--   - List tasks created by a user
--   - Filter tasks by status
--   - Fetch logs for a specific task
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to  ON tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_tasks_created_by   ON tasks(created_by);
CREATE INDEX IF NOT EXISTS idx_tasks_status        ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_activity_task_id    ON activity_logs(task_id);
CREATE INDEX IF NOT EXISTS idx_comments_task_id    ON task_comments(task_id);

-- ============================================================
-- FUNCTION + TRIGGER: auto-update updated_at on tasks & users
-- Whenever a row in tasks or users is updated, Postgres
-- automatically sets updated_at = NOW() via this trigger.
-- ============================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- Supabase uses PostgreSQL RLS. We disable it here because
-- our Flask backend uses the service_role key (bypasses RLS).
-- If you ever expose Supabase directly to the frontend,
-- enable RLS and add appropriate policies.
-- ============================================================
ALTER TABLE users         DISABLE ROW LEVEL SECURITY;
ALTER TABLE tasks         DISABLE ROW LEVEL SECURITY;
ALTER TABLE task_comments DISABLE ROW LEVEL SECURITY;
ALTER TABLE activity_logs DISABLE ROW LEVEL SECURITY;
