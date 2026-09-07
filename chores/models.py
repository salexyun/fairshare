from django.db import models


class Person(models.Model):
    """A member of the household. No login — people just pick their name."""

    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "people"

    def __str__(self):
        return self.name


class Chore(models.Model):
    """A chore definition: either a recurring template or a one-off task."""

    class Recurrence(models.TextChoices):
        NONE = "none", "One-off"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    points = models.PositiveIntegerField(default=1)
    recurrence = models.CharField(
        max_length=10, choices=Recurrence.choices, default=Recurrence.NONE
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Recurring templates can be deactivated without deleting history.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class ChoreInstance(models.Model):
    """A single occurrence of a chore sitting in the shared pool."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLAIMED = "claimed", "Claimed"
        DONE = "done", "Done"

    chore = models.ForeignKey(
        Chore, on_delete=models.CASCADE, related_name="instances"
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.OPEN
    )
    claimed_by = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="claimed_instances",
    )
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date", "created_at"]
        verbose_name_plural = "chore instances"

    def __str__(self):
        return f"{self.chore.title} ({self.get_status_display()})"


class Completion(models.Model):
    """Record of a person finishing a chore instance (self-reported)."""

    instance = models.OneToOneField(
        ChoreInstance, on_delete=models.CASCADE, related_name="completion"
    )
    person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="completions"
    )
    points_awarded = models.PositiveIntegerField(
        help_text="Snapshot of the chore's point value at completion time."
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-completed_at"]

    def __str__(self):
        return f"{self.person.name} completed {self.instance.chore.title}"
