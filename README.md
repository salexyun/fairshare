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

- Python
- Django
- [uv](https://docs.astral.sh/uv/) for Python version, virtual env, and
  package management
- (data model, deployment, and front-end approach TBD — see
  [`_docs/plan.md`](_docs/plan.md) Next Steps)

## Getting Started

> Project scaffolding is not yet in place. Once the Django project exists,
> this section will cover local setup, migrations, and running the dev
> server.

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/)
installed locally. uv manages the virtual env and dependencies from
`pyproject.toml`/`uv.lock` — no manual `venv`/`pip` steps.

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

## Status

Early planning stage — see [`_docs/plan.md`](_docs/plan.md) for scope and
next steps.
