# HairDrama Task Manager

A full-stack task management application with Google OAuth, email notifications, and a Kanban board UI.

## 🔗 Live URLs

| Service | URL |
|---------|-----|
| Frontend | `https://hairdrama-tasks.vercel.app` *(deploy to update)* |
| Backend API | `https://hairdrama-tasks-api.railway.app` *(deploy to update)* |
| Supabase | `https://your-project-ref.supabase.co` |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER'S BROWSER                           │
│                   Next.js (TypeScript) on Vercel                │
│   ┌──────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│   │Login Page│  │ Task Board   │  │ Task Detail + Comments   │ │
│   │(OAuth)   │  │ (Kanban)     │  │ + Activity Log           │ │
│   └────┬─────┘  └──────┬───────┘  └───────────┬──────────────┘ │
└────────│───────────────│──────────────────────│────────────────┘
         │ HTTPS         │  REST API (JWT)       │
         ▼               ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Flask API on Railway/Render                   │
│   ┌──────────────┐  ┌────────────────┐  ┌────────────────────┐ │
│   │ /auth/google │  │ /api/tasks     │  │ /api/users         │ │
│   │ /auth/callbk │  │ CRUD + filters │  │ list all users     │ │
│   │ /auth/me     │  │ activity logs  │  │                    │ │
│   └──────┬───────┘  └───────┬────────┘  └────────────────────┘ │
│          │                  │                                   │
│          │     ┌────────────┴────────────┐                      │
│          │     │   Email Service         │                      │
│          │     │   Gmail SMTP            │                      │
│          │     └─────────────────────────┘                      │
└──────────│──────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│         External Services                                       │
│   ┌────────────────────┐    ┌─────────────────────────────────┐ │
│   │  Google OAuth 2.0  │    │  Supabase (PostgreSQL)          │ │
│   │  accounts.google   │    │  users, tasks, comments, logs   │ │
│   └────────────────────┘    └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Auth Flow (OAuth 2.0 Authorization Code Flow)

```
1. User clicks "Login with Google"
2. Frontend → GET /auth/google  (Flask)
3. Flask builds Google authorization URL → 302 redirect to Google
4. User logs in on Google's page, grants permissions
5. Google → GET /auth/callback?code=XXX  (Flask)
6. Flask exchanges code for id_token + access_token
7. Flask verifies id_token with Google's public keys
8. Flask upserts user into Supabase (create or update)
9. Flask issues a signed JWT (HS256, 24h expiry)
10. Flask → 302 redirect to frontend with ?token=JWT
11. Frontend stores JWT in localStorage
12. All subsequent API calls include: Authorization: Bearer <JWT>
```

---

## 🗄️ Database Schema

```sql
users          — Google OAuth users (id, email, name, avatar_url, google_id)
tasks          — Tasks with status/priority/due_date, FK to creator and assignee
task_comments  — Comments on tasks, FK to task and user
activity_logs  — Immutable audit trail of all task changes (JSONB meta field)
```

See [`backend/migrations/`](backend/migrations/) for the full SQL.

---

## 📧 Email Notifications

| Trigger | Recipient | When |
|---------|-----------|------|
| Task created | Assignee | New task is assigned to them |
| Task completed | Creator | Task status changes to `done` |
| Task reassigned | New assignee | `assigned_to` field changes |

Implemented via Gmail SMTP with App Password in [`backend/app/services/email_service.py`](backend/app/services/email_service.py).

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- A [Supabase](https://supabase.com) project
- A [Google Cloud Console](https://console.cloud.google.com) project with OAuth 2.0 credentials

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/hairdrama-tasks.git
cd hairdrama-tasks
```

### 2. Set up Supabase
1. Create a new Supabase project
2. Go to **SQL Editor**
3. Run `backend/migrations/001_initial_schema.sql`
4. (Optional) Run `backend/migrations/002_seed_data.sql` for sample data

### 3. Backend setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt
cp .env.example .env
# Edit .env with your real credentials

python run.py
# → Flask running on http://localhost:5000
```

### 4. Frontend setup
```bash
cd frontend
npm install
cp .env.example .env.local
# Edit .env.local with NEXT_PUBLIC_API_URL=http://localhost:5000

npm run dev
# → Next.js running on http://localhost:3000
```

---

## 🌍 Deployment

### Backend → Railway
1. Create a new Railway project → deploy from GitHub
2. Set all env vars from `.env.example` in Railway's Variables tab
3. Railway auto-detects `requirements.txt` and starts with gunicorn

### Frontend → Vercel
1. Import the GitHub repo into Vercel
2. Set root directory to `frontend`
3. Add `NEXT_PUBLIC_API_URL` env var pointing to your Railway URL

### Database → Supabase
Already hosted — just run the migrations once.

---

## 📁 Project Structure

```
hairdrama-tasks/
├── backend/
│   ├── app/
│   │   ├── __init__.py          # App factory + CORS + blueprints
│   │   ├── config.py            # Centralised config from env vars
│   │   ├── routes/
│   │   │   ├── auth.py          # Google OAuth 2.0 flow + JWT
│   │   │   ├── tasks.py         # Task CRUD + email triggers
│   │   │   └── users.py         # User listing
│   │   └── services/
│   │       ├── supabase_client.py  # Supabase singleton
│   │       └── email_service.py    # Gmail SMTP notifications
│   ├── migrations/
│   │   ├── 001_initial_schema.sql  # Tables, indexes, triggers
│   │   └── 002_seed_data.sql       # Dev seed data
│   ├── .env.example
│   ├── requirements.txt
│   └── run.py
│
└── frontend/
    ├── src/
    │   ├── app/                 # Next.js App Router pages
    │   ├── components/          # Reusable UI components
    │   ├── context/             # AuthContext (JWT state)
    │   ├── lib/                 # API client (axios)
    │   └── types/               # TypeScript interfaces
    ├── .env.example
    └── package.json
```

---

## ⚙️ Tech Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Frontend | Next.js 14 + TypeScript | SSR, App Router, type safety |
| Backend | Flask (Python) | Lightweight, flexible, easy to explain |
| Database | Supabase (PostgreSQL) | Managed DB + instant REST API |
| Auth | Google OAuth 2.0 | Secure, industry-standard |
| Email | Gmail SMTP | Simple, no extra service needed |
| Deploy (FE) | Vercel | Zero-config Next.js deployment |
| Deploy (BE) | Railway | Simple Python deployment with env vars |

---

## 👨‍💻 Author

Built for HairDrama internship assignment.
