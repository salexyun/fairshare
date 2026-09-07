from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import Chore, ChoreInstance, Completion, Person
from .session import PERSON_SESSION_KEY


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


class PersonPickerViewTests(TestCase):
    def setUp(self):
        self.alex = Person.objects.create(name="Alex")
        self.sam = Person.objects.create(name="Sam")

    def test_picker_lists_all_people_when_no_one_is_acting(self):
        response = self.client.get(reverse("chores:person_picker"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alex")
        self.assertContains(response, "Sam")
        self.assertNotContains(response, "You're acting as")

    def test_picker_shows_fallback_when_no_people_exist(self):
        Person.objects.all().delete()
        response = self.client.get(reverse("chores:person_picker"))
        self.assertContains(response, "No household members yet")

    def test_select_person_sets_session_and_redirects(self):
        response = self.client.post(
            reverse("chores:select_person", args=[self.alex.pk])
        )
        self.assertRedirects(response, reverse("chores:person_picker"))
        self.assertEqual(self.client.session[PERSON_SESSION_KEY], self.alex.pk)

    def test_picker_shows_acting_person_after_selection(self):
        self.client.post(reverse("chores:select_person", args=[self.alex.pk]))
        response = self.client.get(reverse("chores:person_picker"))
        self.assertContains(response, "You're acting as")
        self.assertContains(response, "Alex")

    def test_select_person_requires_post(self):
        response = self.client.get(
            reverse("chores:select_person", args=[self.alex.pk])
        )
        self.assertRedirects(response, reverse("chores:person_picker"))
        self.assertNotIn(PERSON_SESSION_KEY, self.client.session)

    def test_select_person_404s_for_unknown_person(self):
        response = self.client.post(reverse("chores:select_person", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_switch_person_clears_session(self):
        self.client.post(reverse("chores:select_person", args=[self.alex.pk]))
        response = self.client.post(reverse("chores:switch_person"))
        self.assertRedirects(response, reverse("chores:person_picker"))
        self.assertNotIn(PERSON_SESSION_KEY, self.client.session)


class ChorePoolViewTests(TestCase):
    def setUp(self):
        self.recurring = Chore.objects.create(
            title="Take out trash", points=2, recurrence=Chore.Recurrence.WEEKLY
        )
        self.one_off = Chore.objects.create(
            title="Fix leaky faucet", points=10, recurrence=Chore.Recurrence.NONE
        )

    def test_shows_fallback_when_pool_is_empty(self):
        response = self.client.get(reverse("chores:chore_pool"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No open chores")

    def test_lists_open_instances_from_recurring_and_one_off_chores(self):
        ChoreInstance.objects.create(chore=self.recurring)
        ChoreInstance.objects.create(chore=self.one_off)
        response = self.client.get(reverse("chores:chore_pool"))
        self.assertContains(response, "Take out trash")
        self.assertContains(response, "Fix leaky faucet")
        self.assertContains(response, "2")
        self.assertContains(response, "10")

    def test_excludes_claimed_and_done_instances(self):
        person = Person.objects.create(name="Alex")
        ChoreInstance.objects.create(
            chore=self.recurring, status=ChoreInstance.Status.CLAIMED, claimed_by=person
        )
        ChoreInstance.objects.create(chore=self.one_off, status=ChoreInstance.Status.DONE)
        response = self.client.get(reverse("chores:chore_pool"))
        self.assertContains(response, "No open chores")
        self.assertNotContains(response, "Take out trash")
        self.assertNotContains(response, "Fix leaky faucet")

    def test_open_instances_ordered_by_due_date(self):
        later = ChoreInstance.objects.create(
            chore=self.recurring, due_date=date.today() + timedelta(days=5)
        )
        sooner = ChoreInstance.objects.create(
            chore=self.one_off, due_date=date.today() + timedelta(days=1)
        )
        response = self.client.get(reverse("chores:chore_pool"))
        self.assertEqual(
            list(response.context["instances"]), [sooner, later]
        )


class ClaimAndCompleteViewTests(TestCase):
    def setUp(self):
        self.chore = Chore.objects.create(title="Wash dishes", points=4)
        self.instance = ChoreInstance.objects.create(chore=self.chore)
        self.alex = Person.objects.create(name="Alex")
        self.sam = Person.objects.create(name="Sam")

    def _act_as(self, person):
        self.client.post(reverse("chores:select_person", args=[person.pk]))

    # -- claim --

    def test_claim_requires_post(self):
        response = self.client.get(reverse("chores:claim_chore", args=[self.instance.pk]))
        self.assertRedirects(response, reverse("chores:chore_pool"))
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.status, ChoreInstance.Status.OPEN)

    def test_claim_requires_a_current_person(self):
        response = self.client.post(
            reverse("chores:claim_chore", args=[self.instance.pk])
        )
        self.assertRedirects(response, reverse("chores:person_picker"))
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.status, ChoreInstance.Status.OPEN)
        self.assertIsNone(self.instance.claimed_by)

    def test_claim_success(self):
        self._act_as(self.alex)
        response = self.client.post(
            reverse("chores:claim_chore", args=[self.instance.pk])
        )
        self.assertRedirects(response, reverse("chores:chore_pool"))
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.status, ChoreInstance.Status.CLAIMED)
        self.assertEqual(self.instance.claimed_by, self.alex)

    def test_claim_fails_for_already_claimed_instance(self):
        self.instance.status = ChoreInstance.Status.CLAIMED
        self.instance.claimed_by = self.sam
        self.instance.save()
        self._act_as(self.alex)
        response = self.client.post(
            reverse("chores:claim_chore", args=[self.instance.pk])
        )
        self.assertRedirects(response, reverse("chores:chore_pool"))
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.claimed_by, self.sam)

    def test_claim_404s_for_unknown_instance(self):
        self._act_as(self.alex)
        response = self.client.post(reverse("chores:claim_chore", args=[9999]))
        self.assertEqual(response.status_code, 404)

    # -- complete --

    def test_complete_requires_post(self):
        self.instance.status = ChoreInstance.Status.CLAIMED
        self.instance.claimed_by = self.alex
        self.instance.save()
        self._act_as(self.alex)
        response = self.client.get(
            reverse("chores:complete_chore", args=[self.instance.pk])
        )
        self.assertRedirects(response, reverse("chores:chore_pool"))
        self.assertFalse(Completion.objects.exists())

    def test_complete_requires_a_current_person(self):
        response = self.client.post(
            reverse("chores:complete_chore", args=[self.instance.pk])
        )
        self.assertRedirects(response, reverse("chores:person_picker"))
        self.assertFalse(Completion.objects.exists())

    def test_complete_success_awards_points_and_closes_instance(self):
        self.instance.status = ChoreInstance.Status.CLAIMED
        self.instance.claimed_by = self.alex
        self.instance.save()
        self._act_as(self.alex)
        response = self.client.post(
            reverse("chores:complete_chore", args=[self.instance.pk])
        )
        self.assertRedirects(response, reverse("chores:chore_pool"))
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.status, ChoreInstance.Status.DONE)
        completion = Completion.objects.get(instance=self.instance)
        self.assertEqual(completion.person, self.alex)
        self.assertEqual(completion.points_awarded, 4)

    def test_complete_fails_when_not_claimed_by_current_person(self):
        self.instance.status = ChoreInstance.Status.CLAIMED
        self.instance.claimed_by = self.sam
        self.instance.save()
        self._act_as(self.alex)
        response = self.client.post(
            reverse("chores:complete_chore", args=[self.instance.pk])
        )
        self.assertRedirects(response, reverse("chores:chore_pool"))
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.status, ChoreInstance.Status.CLAIMED)
        self.assertFalse(Completion.objects.exists())

    def test_complete_fails_for_still_open_instance(self):
        self._act_as(self.alex)
        response = self.client.post(
            reverse("chores:complete_chore", args=[self.instance.pk])
        )
        self.assertRedirects(response, reverse("chores:chore_pool"))
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.status, ChoreInstance.Status.OPEN)
        self.assertFalse(Completion.objects.exists())

    def test_complete_fails_for_already_done_instance(self):
        self.instance.status = ChoreInstance.Status.CLAIMED
        self.instance.claimed_by = self.alex
        self.instance.save()
        Completion.objects.create(
            instance=self.instance, person=self.alex, points_awarded=4
        )
        self.instance.status = ChoreInstance.Status.DONE
        self.instance.save()
        self._act_as(self.alex)
        response = self.client.post(
            reverse("chores:complete_chore", args=[self.instance.pk])
        )
        self.assertRedirects(response, reverse("chores:chore_pool"))
        self.assertEqual(Completion.objects.filter(instance=self.instance).count(), 1)

    # -- pool page reflects claim state --

    def test_pool_shows_claim_button_only_when_a_person_is_acting(self):
        response = self.client.get(reverse("chores:chore_pool"))
        self.assertNotContains(response, "Claim")
        self.assertContains(response, "Pick your name")

        self._act_as(self.alex)
        response = self.client.get(reverse("chores:chore_pool"))
        self.assertContains(response, "Claim")

    def test_pool_shows_only_my_claimed_chores(self):
        mine = ChoreInstance.objects.create(
            chore=self.chore, status=ChoreInstance.Status.CLAIMED, claimed_by=self.alex
        )
        theirs = ChoreInstance.objects.create(
            chore=self.chore, status=ChoreInstance.Status.CLAIMED, claimed_by=self.sam
        )
        self._act_as(self.alex)
        response = self.client.get(reverse("chores:chore_pool"))
        self.assertIn(mine, response.context["claimed_by_me"])
        self.assertNotIn(theirs, response.context["claimed_by_me"])
