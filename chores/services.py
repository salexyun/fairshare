"""Business logic that doesn't belong in views or models directly."""

from datetime import timedelta

from django.utils import timezone

from .models import Chore, ChoreInstance

RECURRENCE_INTERVALS = {
    Chore.Recurrence.DAILY: timedelta(days=1),
    Chore.Recurrence.WEEKLY: timedelta(days=7),
}

PENDING_STATUSES = [ChoreInstance.Status.OPEN, ChoreInstance.Status.CLAIMED]


def generate_recurring_instances(today=None):
    """Create a new ChoreInstance for each active recurring Chore that's due.

    A chore is due when it has no pending (open/claimed) instance already
    sitting in the pool, and either it's never had an instance or its most
    recent one was created a full interval ago or more. This intentionally
    generates at most one catch-up instance per chore per run, rather than
    backfilling every missed period.

    `today` can be passed explicitly for deterministic testing; defaults
    to the current local date.
    """
    today = today or timezone.localdate()
    created = []

    recurring_chores = Chore.objects.filter(
        is_active=True, recurrence__in=RECURRENCE_INTERVALS
    )
    for chore in recurring_chores:
        if chore.instances.filter(status__in=PENDING_STATUSES).exists():
            continue

        interval = RECURRENCE_INTERVALS[chore.recurrence]
        last_instance = chore.instances.order_by("-created_at").first()
        if last_instance is not None:
            next_due = last_instance.created_at.date() + interval
            if next_due > today:
                continue

        due_date = today + interval - timedelta(days=1)
        created.append(ChoreInstance.objects.create(chore=chore, due_date=due_date))

    return created
