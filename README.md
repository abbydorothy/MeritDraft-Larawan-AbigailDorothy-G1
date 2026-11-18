# MeritDraft — See who really wrote the paper

Full-stack Django (Django templates) + PostgreSQL/Supabase.
MeritDraft ties every unit of recognized contribution to an actual, reviewer-approved change made to a group's shared document.

## Features
**Standard features (Project Development 1):** registration, login/logout, role-based dashboards, user profile.

**Core feature (Project Development 2): Project Change Submission & Review**
1. A student creates a project (a group paper) with a baseline text and becomes its **Leader**.
2. Leaders add other students to the project as **Leader** or **Member** (roles are per project).
3. Any project member submits an edited version of the text and tags it **Addition** or **Revision**.
4. The system generates a word-level diff automatically.
5. Another Leader approves or rejects it. On approval the change is merged into the official text and the author earns points: **1 pt/word for additions, 0.5 pt/word for revisions**.
6. Each project has its own leaderboard. Points never carry over between projects.

## Roles
| Account role | How created | Can do |
|---|---|---|
| Student | Register form | Create projects, take part in projects (per-project role: Leader or Member) |
| Instructor | Register form | Read-only view of all projects, changes and points |
| Admin | Only an existing admin, via the Django admin panel | Everything above + user management |

To make someone an admin: log in to `/admin/` as an admin, open the user, set **Role = Admin**, save. (Only admins can edit roles there.)
To demote an admin: set the role to Student/Instructor **and** untick *Superuser status* and *Staff status*.

## Setup
```bash
python -m venv venv
venv\Scripts\activate            # Windows  (source venv/bin/activate on Mac/Linux)
pip install -r requirements.txt
cp .env.example .env             # then fill in DATABASE_URL (PostgreSQL or Supabase) and SECRET_KEY
python manage.py migrate
python manage.py createsuperuser # superusers are automatically Admins
python manage.py runserver
```
Open http://127.0.0.1:8000/

## Tests
`python manage.py test`  (needs a database user that can create a test database; with Supabase use a local Postgres instead)

## Git workflow
`main` (stable) ← `develop` (integration) ← `feature/<name>` branches, merged through Pull Requests.
