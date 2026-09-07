from django.core.management.base import BaseCommand

from chores.services import auto_assign_overdue_instances


class Command(BaseCommand):
    help = (
        "Assign unclaimed, overdue ChoreInstances to whoever currently has "
        "the fewest points. Intended to run on a schedule — e.g. once a "
        "day via cron, after generate_recurring_chores."
    )

    def handle(self, *args, **options):
        assigned = auto_assign_overdue_instances()
        if not assigned:
            self.stdout.write("No overdue chores to assign.")
            return
        for instance in assigned:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Assigned \"{instance.chore.title}\" (was due "
                    f"{instance.due_date}) to {instance.claimed_by.name}."
                )
            )
        self.stdout.write(self.style.SUCCESS(f"Assigned {len(assigned)} chore(s)."))
