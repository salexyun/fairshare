# Household Chores Tool — Scope Plan

_Drafted 2026-09-07_

## Summary

A web app for managing shared household chores across a small group of
people (2-6), with claim-based assignment, point-based fairness tracking,
and no login required.

## Scope Decisions

- **Users:** One shared household, 2-6 people. No login — people pick their
  name to act (honor system).
- **Interface:** Web app (shared page, works on desktop/mobile browsers).
- **Chores:** Support both:
  - Recurring chores (daily/weekly templates that auto-regenerate)
  - One-off ad-hoc chores (added as needed)
  - Each chore has a point value.
- **Assignment:** Chores sit in a shared pool. People claim what they'll
  do. System tracks per-person point totals to help balance workload
  fairness over time.
- **Overdue handling:** If a chore goes unclaimed/overdue, it is
  auto-assigned to whoever currently has the lowest points.
- **Completion:** Self-report only — person clicks "done," no photo proof
  or peer approval required.
- **Fairness view:** A leaderboard of running point totals per person,
  plus a history log of who completed what chore and when.
- **Backend:** Small server + shared database, so everyone's view stays in
  sync across devices/people in real time (local-only browser storage was
  ruled out since it wouldn't sync across housemates).

## Out of Scope (for this version)

- Multiple households / household switching
- Full user accounts (email/password or SSO login)
- Photo proof or peer confirmation for completed chores
- Chat bot / CLI / native mobile app interfaces

## Next Steps

- Tech stack and architecture planning
- Data model design (chores, people, points, history)
- UI/UX design for the web app
