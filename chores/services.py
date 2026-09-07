"""Business logic that doesn't belong in views or models directly."""

from datetime import timedelta

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Chore, ChoreInstance, Person

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


def _person_with_fewest_points():
    """The Person with the lowest total (completed) points, or None if the
    household has nobody in it. Ties broken alphabetically for determinism.
    """
    return (
        Person.objects.annotate(
            total_points=Coalesce(Sum("completions__points_awarded"), 0)
        )
        .order_by("total_points", "name")
        .first()
    )


def auto_assign_overdue_instances(today=None):
    """Assign unclaimed, overdue ChoreInstances to whoever has the fewest points.

    "Overdue" means status is OPEN with a due_date strictly before today —
    a chore due today still has today to be claimed normally. Instances
    with no due_date are never overdue.

    Note: since claiming doesn't award points (only completing does), if
    several instances are overdue in the same run they will all land on
    the same person — whoever currently has the fewest points doesn't
    change until they actually complete something. That's a deliberate
    reading of "whoever currently has the lowest points," not a bug;
    fairness evens out across subsequent runs as points get awarded.

    Returns the list of instances that were assigned.
    """
    today = today or timezone.localdate()
    overdue = ChoreInstance.objects.filter(
        status=ChoreInstance.Status.OPEN, due_date__lt=today
    ).select_related("chore")

    assigned = []
    for instance in overdue:
        person = _person_with_fewest_points()
        if person is None:
            break  # nobody in the household to assign to
        instance.status = ChoreInstance.Status.CLAIMED
        instance.claimed_by = person
        instance.save()
        assigned.append(instance)

    return assigned
