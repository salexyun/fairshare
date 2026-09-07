from django.core.management.base import BaseCommand

from chores.services import generate_recurring_instances


class Command(BaseCommand):
    help = (
        "Create new ChoreInstances for active recurring Chore templates "
        "(daily/weekly) that are due for their next occurrence. Intended "
        "to run on a schedule — e.g. once a day via cron."
    )

    def handle(self, *args, **options):
        created = generate_recurring_instances()
        if not created:
            self.stdout.write("No recurring chores due for generation.")
            return
        for instance in created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created instance for \"{instance.chore.title}\" "
                    f"(due {instance.due_date})."
                )
            )
        self.stdout.write(
            self.style.SUCCESS(f"Generated {len(created)} instance(s).")
        )
