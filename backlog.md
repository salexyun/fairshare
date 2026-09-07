# FairShare — Build Backlog

_Derived from [`_docs/plan.md`](_docs/plan.md). Small, roughly sequential
MVP backlog — each task builds on the last._

1. **Data model: Person, Chore, ChoreInstance, Completion**
   Define core models in `chores/models.py`: `Person` (name), `Chore`
   (title, point value, recurrence rule or one-off), `ChoreInstance` (a
   single occurrence in the pool — status: open/claimed/done, claimed_by,
   due date), `Completion` (who completed which instance, when, points
   awarded). Register in admin, generate and run migrations.

2. **Person picker ("honor system" identity)**
   Landing view where someone picks their name from the household's
   `Person` list to act as. Store the choice in the session — no
   password, per plan's no-login decision.

3. **Chore pool view**
   Page listing open `ChoreInstance`s (from both recurring templates and
   one-off chores) with point values, so anyone can see what's available.

4. **Claim and complete actions**
   "Claim" sets `claimed_by` + status on a `ChoreInstance`; "Done" creates
   a `Completion`, awards points, and closes the instance. Self-report
   only, no approval step.

5. **Add one-off chore**
   Simple form to add an ad-hoc `ChoreInstance` (title, points, optional
   due date) directly into the pool.

6. **Recurring chore templates + auto-regeneration**
   `Chore` templates with a recurrence rule (daily/weekly) and a
   scheduled job (management command, run via cron or Django management
   command) that generates new `ChoreInstance`s on schedule.

7. **Overdue auto-assignment**
   Management command/job that finds unclaimed instances past due and
   assigns them to whichever `Person` currently has the lowest point
   total.

8. **Leaderboard view**
   Page showing running point totals per person, computed from
   `Completion` records, sorted descending.

9. **History log view**
   Chronological list of completions (who did what, when, points
   earned) — supports the fairness view alongside the leaderboard.

10. **Basic styling + mobile-friendly layout**
    Shared base template, responsive layout so the pool/leaderboard work
    well on both desktop and mobile browsers per the plan's interface
    requirement.

11. **Deployment**
    Deploy the small server + shared database (per plan, ruling out
    local-only storage) so the household can access one synced instance
    from multiple devices.
