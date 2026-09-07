# FairShare

A web app for managing shared household chores across a small group of
people (2–6), with claim-based assignment and point-based fairness
tracking — no login required.

## Why

Most chore-tracking tools either rigidly assign tasks or rely on
after-the-fact arguments about who did more. FairShare puts chores in a
shared pool that anyone can claim, tracks running point totals per
person, and auto-assigns overdue chores to whoever is currently behind —
so the group stays balanced without anyone having to referee it.

## Features

- **Shared chore pool** — recurring chores (daily/weekly templates that
  auto-regenerate) and one-off ad-hoc chores, each worth a point value.
- **Claim-based assignment** — people pick their name and claim chores
  from the pool; no fixed rotation.
- **Fairness tracking** — running point totals per person, with overdue
  chores auto-assigned to whoever currently has the lowest points.
- **Self-report completion** — click "done," no photo proof or peer
  approval required.
- **Leaderboard & history** — running point totals plus a log of who
  completed what and when.
- **No login** — one shared household (2–6 people), honor-system
  identity, real-time sync across devices via a shared backend.

See [`_docs/plan.md`](_docs/plan.md) for the full scope decisions and
what's intentionally out of scope for this version.

## Tech Stack

- Python + Django, server-rendered templates (no separate frontend)
- SQLite for local development
- [uv](https://docs.astral.sh/uv/) for Python version, virtual env, and
  package management
- Deployment target: TBD — see [`backlog.md`](backlog.md) task #11

## Getting Started

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/)
installed locally. uv manages the virtual env and dependencies from
`pyproject.toml`/`uv.lock` — no manual `venv`/`pip` steps.

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser   # for /admin access
uv run python manage.py runserver
```

Then visit `http://127.0.0.1:8000/`. There's no sign-up flow — add your
household's people and any chores via `/admin` first, then people pick
their name from the list to act (honor system, no password).

Two management commands drive the automated parts and are meant to run
on a schedule (e.g. cron) in a real deployment:

```bash
uv run python manage.py generate_recurring_chores  # regenerate due recurring chores
uv run python manage.py assign_overdue_chores       # auto-assign overdue chores
```

## Status

Core app is built end-to-end: data model, person picker, chore pool
(claim/complete/add one-off), recurring chore generation, overdue
auto-assignment, leaderboard, history log, and responsive styling.
See [`backlog.md`](backlog.md) for the full task list — deployment
(task #11) is the remaining item.
