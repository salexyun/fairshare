from datetime import date, timedelta
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Chore, ChoreInstance, Completion, Person
from .services import auto_assign_overdue_instances, generate_recurring_instances
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


class AddChoreViewTests(TestCase):
    def test_get_renders_empty_form(self):
        response = self.client.get(reverse("chores:add_chore"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add a One-Off Chore")

    def test_valid_post_creates_one_off_chore_and_instance(self):
        response = self.client.post(
            reverse("chores:add_chore"),
            {"title": "Fix the fence", "points": 7, "due_date": ""},
        )
        self.assertRedirects(response, reverse("chores:chore_pool"))

        chore = Chore.objects.get(title="Fix the fence")
        self.assertEqual(chore.points, 7)
        self.assertEqual(chore.recurrence, Chore.Recurrence.NONE)

        instance = ChoreInstance.objects.get(chore=chore)
        self.assertEqual(instance.status, ChoreInstance.Status.OPEN)
        self.assertIsNone(instance.due_date)

    def test_valid_post_with_due_date(self):
        due = date.today() + timedelta(days=3)
        self.client.post(
            reverse("chores:add_chore"),
            {"title": "Water plants", "points": 1, "due_date": due.isoformat()},
        )
        instance = ChoreInstance.objects.get(chore__title="Water plants")
        self.assertEqual(instance.due_date, due)

    def test_new_chore_appears_in_open_pool(self):
        self.client.post(
            reverse("chores:add_chore"), {"title": "Sweep porch", "points": 2}
        )
        response = self.client.get(reverse("chores:chore_pool"))
        self.assertContains(response, "Sweep porch")

    def test_missing_title_does_not_create_a_chore(self):
        response = self.client.post(
            reverse("chores:add_chore"), {"title": "", "points": 3}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Chore.objects.exists())

    def test_zero_points_is_rejected_by_the_form(self):
        # Stricter than the model, which allows 0 (see
        # ChoreModelTests.test_zero_points_is_currently_allowed).
        response = self.client.post(
            reverse("chores:add_chore"), {"title": "Free chore", "points": 0}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Chore.objects.exists())


def _backdate(instance, days_ago):
    """Force an instance's created_at into the past, bypassing auto_now_add
    (QuerySet.update() skips model-level auto_now_add handling)."""
    past = timezone.now() - timedelta(days=days_ago)
    ChoreInstance.objects.filter(pk=instance.pk).update(created_at=past)
    instance.refresh_from_db()
    return instance


class GenerateRecurringInstancesTests(TestCase):
    def setUp(self):
        self.today = date(2026, 9, 7)

    def test_one_off_chore_never_generates(self):
        Chore.objects.create(title="Fix fence", recurrence=Chore.Recurrence.NONE)
        created = generate_recurring_instances(today=self.today)
        self.assertEqual(created, [])

    def test_inactive_chore_never_generates(self):
        Chore.objects.create(
            title="Dishes",
            recurrence=Chore.Recurrence.DAILY,
            is_active=False,
        )
        created = generate_recurring_instances(today=self.today)
        self.assertEqual(created, [])

    def test_daily_chore_with_no_history_generates_due_today(self):
        chore = Chore.objects.create(title="Dishes", recurrence=Chore.Recurrence.DAILY)
        created = generate_recurring_instances(today=self.today)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].chore, chore)
        self.assertEqual(created[0].due_date, self.today)

    def test_weekly_chore_with_no_history_generates_due_in_six_days(self):
        chore = Chore.objects.create(
            title="Vacuum", recurrence=Chore.Recurrence.WEEKLY
        )
        created = generate_recurring_instances(today=self.today)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].chore, chore)
        self.assertEqual(created[0].due_date, self.today + timedelta(days=6))

    def test_skips_chore_with_a_pending_open_instance(self):
        chore = Chore.objects.create(title="Dishes", recurrence=Chore.Recurrence.DAILY)
        _backdate(
            ChoreInstance.objects.create(chore=chore), days_ago=5
        )
        created = generate_recurring_instances(today=self.today)
        self.assertEqual(created, [])
        self.assertEqual(chore.instances.count(), 1)

    def test_skips_chore_with_a_pending_claimed_instance(self):
        chore = Chore.objects.create(title="Dishes", recurrence=Chore.Recurrence.DAILY)
        person = Person.objects.create(name="Alex")
        _backdate(
            ChoreInstance.objects.create(
                chore=chore,
                status=ChoreInstance.Status.CLAIMED,
                claimed_by=person,
            ),
            days_ago=5,
        )
        created = generate_recurring_instances(today=self.today)
        self.assertEqual(created, [])

    def test_daily_chore_does_not_regenerate_same_day(self):
        chore = Chore.objects.create(title="Dishes", recurrence=Chore.Recurrence.DAILY)
        _backdate(
            ChoreInstance.objects.create(chore=chore, status=ChoreInstance.Status.DONE),
            days_ago=0,
        )
        created = generate_recurring_instances(today=self.today)
        self.assertEqual(created, [])

    def test_daily_chore_regenerates_after_a_day_has_passed(self):
        chore = Chore.objects.create(title="Dishes", recurrence=Chore.Recurrence.DAILY)
        _backdate(
            ChoreInstance.objects.create(chore=chore, status=ChoreInstance.Status.DONE),
            days_ago=1,
        )
        created = generate_recurring_instances(today=self.today)
        self.assertEqual(len(created), 1)
        self.assertEqual(chore.instances.count(), 2)

    def test_weekly_chore_not_yet_due(self):
        chore = Chore.objects.create(
            title="Vacuum", recurrence=Chore.Recurrence.WEEKLY
        )
        _backdate(
            ChoreInstance.objects.create(chore=chore, status=ChoreInstance.Status.DONE),
            days_ago=6,
        )
        created = generate_recurring_instances(today=self.today)
        self.assertEqual(created, [])

    def test_weekly_chore_due_after_seven_days(self):
        chore = Chore.objects.create(
            title="Vacuum", recurrence=Chore.Recurrence.WEEKLY
        )
        _backdate(
            ChoreInstance.objects.create(chore=chore, status=ChoreInstance.Status.DONE),
            days_ago=7,
        )
        created = generate_recurring_instances(today=self.today)
        self.assertEqual(len(created), 1)


class GenerateRecurringChoresCommandTests(TestCase):
    def test_command_creates_instances_and_reports_them(self):
        chore = Chore.objects.create(title="Dishes", recurrence=Chore.Recurrence.DAILY)
        out = StringIO()
        call_command("generate_recurring_chores", stdout=out)
        self.assertEqual(chore.instances.count(), 1)
        self.assertIn("Dishes", out.getvalue())
        self.assertIn("Generated 1 instance(s).", out.getvalue())

    def test_command_reports_when_nothing_is_due(self):
        out = StringIO()
        call_command("generate_recurring_chores", stdout=out)
        self.assertIn("No recurring chores due", out.getvalue())


class AutoAssignOverdueInstancesTests(TestCase):
    def setUp(self):
        self.today = date(2026, 9, 7)
        self.chore = Chore.objects.create(title="Dishes", points=3)
        self.alex = Person.objects.create(name="Alex")
        self.sam = Person.objects.create(name="Sam")

    def test_no_instances_means_nothing_assigned(self):
        self.assertEqual(auto_assign_overdue_instances(today=self.today), [])

    def test_future_due_date_is_not_overdue(self):
        instance = ChoreInstance.objects.create(
            chore=self.chore, due_date=self.today + timedelta(days=1)
        )
        self.assertEqual(auto_assign_overdue_instances(today=self.today), [])
        instance.refresh_from_db()
        self.assertEqual(instance.status, ChoreInstance.Status.OPEN)

    def test_due_today_is_not_yet_overdue(self):
        instance = ChoreInstance.objects.create(chore=self.chore, due_date=self.today)
        self.assertEqual(auto_assign_overdue_instances(today=self.today), [])
        instance.refresh_from_db()
        self.assertEqual(instance.status, ChoreInstance.Status.OPEN)

    def test_no_due_date_is_never_overdue(self):
        ChoreInstance.objects.create(chore=self.chore, due_date=None)
        self.assertEqual(auto_assign_overdue_instances(today=self.today), [])

    def test_past_due_open_instance_gets_assigned_to_lowest_points_person(self):
        Completion.objects.create(
            instance=ChoreInstance.objects.create(
                chore=self.chore, status=ChoreInstance.Status.DONE
            ),
            person=self.alex,
            points_awarded=10,
        )
        # Sam has 0 points, Alex has 10 — Sam should get the overdue chore.
        overdue = ChoreInstance.objects.create(
            chore=self.chore, due_date=self.today - timedelta(days=1)
        )
        assigned = auto_assign_overdue_instances(today=self.today)
        self.assertEqual(assigned, [overdue])
        overdue.refresh_from_db()
        self.assertEqual(overdue.status, ChoreInstance.Status.CLAIMED)
        self.assertEqual(overdue.claimed_by, self.sam)

    def test_tied_points_broken_alphabetically(self):
        overdue = ChoreInstance.objects.create(
            chore=self.chore, due_date=self.today - timedelta(days=1)
        )
        assigned = auto_assign_overdue_instances(today=self.today)
        self.assertEqual(assigned[0].claimed_by, self.alex)  # "Alex" < "Sam"

    def test_already_claimed_instance_is_left_alone(self):
        instance = ChoreInstance.objects.create(
            chore=self.chore,
            status=ChoreInstance.Status.CLAIMED,
            claimed_by=self.sam,
            due_date=self.today - timedelta(days=1),
        )
        self.assertEqual(auto_assign_overdue_instances(today=self.today), [])
        instance.refresh_from_db()
        self.assertEqual(instance.claimed_by, self.sam)

    def test_done_instance_is_left_alone(self):
        ChoreInstance.objects.create(
            chore=self.chore,
            status=ChoreInstance.Status.DONE,
            due_date=self.today - timedelta(days=1),
        )
        self.assertEqual(auto_assign_overdue_instances(today=self.today), [])

    def test_no_people_means_nothing_can_be_assigned(self):
        Person.objects.all().delete()
        instance = ChoreInstance.objects.create(
            chore=self.chore, due_date=self.today - timedelta(days=1)
        )
        self.assertEqual(auto_assign_overdue_instances(today=self.today), [])
        instance.refresh_from_db()
        self.assertEqual(instance.status, ChoreInstance.Status.OPEN)

    def test_multiple_overdue_instances_spread_across_close_totals(self):
        # Alex (0 pts) and Sam (1 pt) start close together, so once Alex
        # provisionally "gains" this chore's 3 points, Sam becomes the
        # lower of the two for the next one.
        Completion.objects.create(
            instance=ChoreInstance.objects.create(
                chore=self.chore, status=ChoreInstance.Status.DONE
            ),
            person=self.sam,
            points_awarded=1,
        )
        first = ChoreInstance.objects.create(
            chore=self.chore, due_date=self.today - timedelta(days=2)
        )
        second = ChoreInstance.objects.create(
            chore=self.chore, due_date=self.today - timedelta(days=1)
        )
        assigned = auto_assign_overdue_instances(today=self.today)
        self.assertEqual(len(assigned), 2)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.claimed_by, self.alex)
        self.assertEqual(second.claimed_by, self.sam)

    def test_multiple_overdue_instances_stay_with_one_person_over_a_wide_gap(self):
        # Sam is way ahead, so even after Alex's provisional bump from the
        # first chore, Alex is still behind and rightly gets the second too.
        Completion.objects.create(
            instance=ChoreInstance.objects.create(
                chore=self.chore, status=ChoreInstance.Status.DONE
            ),
            person=self.sam,
            points_awarded=100,
        )
        first = ChoreInstance.objects.create(
            chore=self.chore, due_date=self.today - timedelta(days=2)
        )
        second = ChoreInstance.objects.create(
            chore=self.chore, due_date=self.today - timedelta(days=1)
        )
        assigned = auto_assign_overdue_instances(today=self.today)
        self.assertEqual(len(assigned), 2)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.claimed_by, self.alex)
        self.assertEqual(second.claimed_by, self.alex)

    def test_provisional_weighting_is_not_persisted_to_real_points(self):
        overdue = ChoreInstance.objects.create(
            chore=self.chore, due_date=self.today - timedelta(days=1)
        )
        auto_assign_overdue_instances(today=self.today)
        overdue.refresh_from_db()
        # Claiming, even via auto-assignment, must not create a Completion
        # or otherwise touch real point totals — only completing does.
        self.assertFalse(Completion.objects.filter(person=overdue.claimed_by).exists())


class AssignOverdueChoresCommandTests(TestCase):
    def test_command_assigns_and_reports(self):
        chore = Chore.objects.create(title="Dishes", points=3)
        Person.objects.create(name="Alex")
        ChoreInstance.objects.create(
            chore=chore, due_date=date.today() - timedelta(days=1)
        )
        out = StringIO()
        call_command("assign_overdue_chores", stdout=out)
        self.assertIn("Dishes", out.getvalue())
        self.assertIn("Alex", out.getvalue())
        self.assertIn("Assigned 1 chore(s).", out.getvalue())

    def test_command_reports_when_nothing_is_overdue(self):
        out = StringIO()
        call_command("assign_overdue_chores", stdout=out)
        self.assertIn("No overdue chores to assign", out.getvalue())


class LeaderboardViewTests(TestCase):
    def test_shows_fallback_when_no_people_exist(self):
        response = self.client.get(reverse("chores:leaderboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No household members yet")

    def test_person_with_no_completions_shows_zero_points(self):
        Person.objects.create(name="Alex")
        response = self.client.get(reverse("chores:leaderboard"))
        self.assertContains(response, "Alex")
        people = list(response.context["people"])
        self.assertEqual(people[0].total_points, 0)

    def test_totals_sum_multiple_completions_per_person(self):
        chore = Chore.objects.create(title="Dishes", points=3)
        alex = Person.objects.create(name="Alex")
        for _ in range(3):
            instance = ChoreInstance.objects.create(
                chore=chore, status=ChoreInstance.Status.DONE
            )
            Completion.objects.create(
                instance=instance, person=alex, points_awarded=3
            )
        response = self.client.get(reverse("chores:leaderboard"))
        people = list(response.context["people"])
        self.assertEqual(people[0].total_points, 9)

    def test_ordered_by_points_descending(self):
        chore = Chore.objects.create(title="Dishes", points=5)
        alex = Person.objects.create(name="Alex")
        sam = Person.objects.create(name="Sam")
        instance = ChoreInstance.objects.create(
            chore=chore, status=ChoreInstance.Status.DONE
        )
        Completion.objects.create(instance=instance, person=alex, points_awarded=5)
        # Sam has 0 completions and should still appear, below Alex.
        response = self.client.get(reverse("chores:leaderboard"))
        names = [person.name for person in response.context["people"]]
        self.assertEqual(names, ["Alex", "Sam"])

    def test_ties_broken_alphabetically(self):
        Person.objects.create(name="Sam")
        Person.objects.create(name="Alex")
        response = self.client.get(reverse("chores:leaderboard"))
        names = [person.name for person in response.context["people"]]
        self.assertEqual(names, ["Alex", "Sam"])


class HistoryViewTests(TestCase):
    def setUp(self):
        self.chore = Chore.objects.create(title="Dishes", points=4)
        self.alex = Person.objects.create(name="Alex")

    def test_shows_fallback_when_nothing_completed(self):
        response = self.client.get(reverse("chores:history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No chores completed yet")

    def test_lists_completion_with_person_chore_and_points(self):
        instance = ChoreInstance.objects.create(
            chore=self.chore, status=ChoreInstance.Status.DONE
        )
        Completion.objects.create(
            instance=instance, person=self.alex, points_awarded=4
        )
        response = self.client.get(reverse("chores:history"))
        self.assertContains(response, "Alex")
        self.assertContains(response, "Dishes")
        self.assertContains(response, "4")

    def test_ordered_most_recent_first(self):
        first_instance = ChoreInstance.objects.create(
            chore=self.chore, status=ChoreInstance.Status.DONE
        )
        first = Completion.objects.create(
            instance=first_instance, person=self.alex, points_awarded=4
        )
        second_instance = ChoreInstance.objects.create(
            chore=self.chore, status=ChoreInstance.Status.DONE
        )
        second = Completion.objects.create(
            instance=second_instance, person=self.alex, points_awarded=4
        )
        response = self.client.get(reverse("chores:history"))
        self.assertEqual(list(response.context["completions"]), [second, first])
