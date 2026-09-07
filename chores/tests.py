from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Chore, ChoreInstance, Completion, Person


class PersonModelTests(TestCase):
    def test_str_returns_name(self):
        person = Person.objects.create(name="Alex")
        self.assertEqual(str(person), "Alex")

    def test_name_must_be_unique(self):
        Person.objects.create(name="Alex")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Person.objects.create(name="Alex")

    def test_default_ordering_is_by_name(self):
        Person.objects.create(name="Charlie")
        Person.objects.create(name="Alex")
        Person.objects.create(name="Bailey")
        self.assertEqual(
            list(Person.objects.values_list("name", flat=True)),
            ["Alex", "Bailey", "Charlie"],
        )


class ChoreModelTests(TestCase):
    def test_defaults(self):
        chore = Chore.objects.create(title="Dishes")
        self.assertEqual(chore.points, 1)
        self.assertEqual(chore.recurrence, Chore.Recurrence.NONE)
        self.assertTrue(chore.is_active)

    def test_str_returns_title(self):
        chore = Chore.objects.create(title="Dishes")
        self.assertEqual(str(chore), "Dishes")

    def test_default_ordering_is_by_title(self):
        Chore.objects.create(title="Vacuum")
        Chore.objects.create(title="Dishes")
        self.assertEqual(
            list(Chore.objects.values_list("title", flat=True)),
            ["Dishes", "Vacuum"],
        )

    def test_recurrence_rejects_invalid_choice(self):
        chore = Chore(title="Dishes", recurrence="monthly")
        with self.assertRaises(ValidationError):
            chore.full_clean()

    def test_zero_points_is_currently_allowed(self):
        # PositiveIntegerField allows 0 in Django. This documents current
        # behavior; revisit with MinValueValidator(1) if zero-point
        # chores turn out to be undesirable.
        chore = Chore(title="Free chore", points=0)
        chore.full_clean()  # should not raise
        chore.save()
        self.assertEqual(chore.points, 0)


class ChoreInstanceModelTests(TestCase):
    def setUp(self):
        self.chore = Chore.objects.create(title="Dishes", points=3)
        self.person = Person.objects.create(name="Alex")

    def test_defaults(self):
        instance = ChoreInstance.objects.create(chore=self.chore)
        self.assertEqual(instance.status, ChoreInstance.Status.OPEN)
        self.assertIsNone(instance.claimed_by)

    def test_str_includes_chore_title_and_status(self):
        instance = ChoreInstance.objects.create(chore=self.chore)
        self.assertEqual(str(instance), "Dishes (Open)")

    def test_deleting_chore_cascades_to_instances(self):
        instance = ChoreInstance.objects.create(chore=self.chore)
        self.chore.delete()
        self.assertFalse(ChoreInstance.objects.filter(pk=instance.pk).exists())

    def test_deleting_claimed_person_sets_claimed_by_null(self):
        instance = ChoreInstance.objects.create(
            chore=self.chore,
            claimed_by=self.person,
            status=ChoreInstance.Status.CLAIMED,
        )
        self.person.delete()
        instance.refresh_from_db()
        self.assertIsNone(instance.claimed_by)
        # The instance itself must survive the person's deletion.
        self.assertTrue(ChoreInstance.objects.filter(pk=instance.pk).exists())

    def test_default_ordering_by_due_date(self):
        later = ChoreInstance.objects.create(
            chore=self.chore, due_date=date.today() + timedelta(days=2)
        )
        sooner = ChoreInstance.objects.create(
            chore=self.chore, due_date=date.today() + timedelta(days=1)
        )
        self.assertEqual(list(ChoreInstance.objects.all()), [sooner, later])


class CompletionModelTests(TestCase):
    def setUp(self):
        self.chore = Chore.objects.create(title="Dishes", points=5)
        self.person = Person.objects.create(name="Alex")
        self.instance = ChoreInstance.objects.create(
            chore=self.chore,
            claimed_by=self.person,
            status=ChoreInstance.Status.CLAIMED,
        )

    def test_str_format(self):
        completion = Completion.objects.create(
            instance=self.instance, person=self.person, points_awarded=5
        )
        self.assertEqual(str(completion), "Alex completed Dishes")

    def test_one_completion_per_instance(self):
        Completion.objects.create(
            instance=self.instance, person=self.person, points_awarded=5
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Completion.objects.create(
                    instance=self.instance, person=self.person, points_awarded=5
                )

    def test_points_awarded_is_a_snapshot(self):
        completion = Completion.objects.create(
            instance=self.instance, person=self.person, points_awarded=self.chore.points
        )
        self.chore.points = 99
        self.chore.save()
        completion.refresh_from_db()
        self.assertEqual(completion.points_awarded, 5)

    def test_deleting_person_cascades_and_deletes_completion(self):
        completion = Completion.objects.create(
            instance=self.instance, person=self.person, points_awarded=5
        )
        # Documents current behavior: unlike ChoreInstance.claimed_by
        # (SET_NULL), removing a Person erases their completion history.
        self.person.delete()
        self.assertFalse(Completion.objects.filter(pk=completion.pk).exists())

    def test_deleting_instance_cascades_to_completion(self):
        completion = Completion.objects.create(
            instance=self.instance, person=self.person, points_awarded=5
        )
        self.instance.delete()
        self.assertFalse(Completion.objects.filter(pk=completion.pk).exists())

    def test_default_ordering_is_most_recent_first(self):
        chore2 = Chore.objects.create(title="Vacuum", points=2)
        instance2 = ChoreInstance.objects.create(chore=chore2, claimed_by=self.person)
        first = Completion.objects.create(
            instance=self.instance, person=self.person, points_awarded=5
        )
        second = Completion.objects.create(
            instance=instance2, person=self.person, points_awarded=2
        )
        self.assertEqual(list(Completion.objects.all()), [second, first])
