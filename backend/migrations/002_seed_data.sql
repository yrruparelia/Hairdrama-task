-- ============================================================
-- Migration 002: Seed / Sample Data (OPTIONAL - for local dev)
-- Run ONLY in development. DO NOT run in production.
-- ============================================================

-- Two demo users (these will be replaced by real Google OAuth users)
INSERT INTO users (id, email, name, avatar_url, google_id) VALUES
(
    '11111111-1111-1111-1111-111111111111',
    'alice@example.com',
    'Alice Dev',
    'https://ui-avatars.com/api/?name=Alice+Dev',
    'google_alice_001'
),
(
    '22222222-2222-2222-2222-222222222222',
    'bob@example.com',
    'Bob Tester',
    'https://ui-avatars.com/api/?name=Bob+Tester',
    'google_bob_002'
)
ON CONFLICT DO NOTHING;

-- Sample tasks
INSERT INTO tasks (title, description, status, priority, due_date, created_by, assigned_to) VALUES
(
    'Set up Supabase schema',
    'Create all necessary tables and run migrations on Supabase dashboard.',
    'done',
    'high',
    '2026-10-28',
    '11111111-1111-1111-1111-111111111111',
    '11111111-1111-1111-1111-111111111111'
),
(
    'Implement Google OAuth in Flask',
    'Use google-auth-oauthlib to handle the authorization code flow.',
    'in_progress',
    'high',
    '2026-10-30',
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222'
),
(
    'Build task board UI',
    'Create a Kanban-style board in Next.js with drag and drop support.',
    'todo',
    'medium',
    '2026-11-02',
    '22222222-2222-2222-2222-222222222222',
    '22222222-2222-2222-2222-222222222222'
)
ON CONFLICT DO NOTHING;
