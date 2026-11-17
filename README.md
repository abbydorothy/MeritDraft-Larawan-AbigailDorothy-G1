# MeritDraft — See who really wrote the paper

Django full-stack app (Django templates) with PostgreSQL/Supabase.
**Phase 1: Account Feature** — registration, login/logout, role-based dashboards (Student, Admin), user profile.

## Setup
```bash
python -m venv venv
venv\Scripts\activate          # Windows   (source venv/bin/activate on Mac/Linux)
pip install -r requirements.txt
cp .env.example .env           # then fill in DATABASE_URL (PostgreSQL or Supabase)
python manage.py migrate
python manage.py createsuperuser   # superusers are automatically given the Admin role
python manage.py runserver
```
Open http://127.0.0.1:8000/

## Roles
**Account roles (global)**

| Role | How created | Dashboard |
|---|---|---|
| Student | Register form | /dashboard/student/ |
| Admin | `createsuperuser` or Django admin | /dashboard/admin/ |

**Project roles (per project)** — Leader or Member — are assigned through project membership
(added in the project-setup phase), so one student can be a Leader in one project and a Member in another.

Opening another role's dashboard by URL returns a 403 page; logged-out users are sent to the login page.

## Tests
`python manage.py test`
