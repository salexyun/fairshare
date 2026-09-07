from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AddOneOffChoreForm
from .models import ChoreInstance, Completion, Person
from .services import people_with_total_points
from .session import clear_current_person, get_current_person, set_current_person


def person_picker(request):
    """Landing page: pick who you are. Honor system — no password."""
    people = Person.objects.all()
    return render(request, "chores/person_picker.html", {"people": people})


def select_person(request, person_id):
    """Set the acting person for this session."""
    if request.method != "POST":
        return redirect("chores:person_picker")
    person = get_object_or_404(Person, pk=person_id)
    set_current_person(request, person)
    messages.success(request, f"You're now acting as {person.name}.")
    return redirect("chores:person_picker")


def switch_person(request):
    """Forget the acting person for this session, so someone else can pick."""
    if request.method == "POST":
        clear_current_person(request)
    return redirect("chores:person_picker")


def chore_pool(request):
    """Shared pool of open chores — recurring and one-off alike — anyone can see."""
    current_person = get_current_person(request)
    instances = ChoreInstance.objects.filter(
        status=ChoreInstance.Status.OPEN
    ).select_related("chore")
    claimed_by_me = ChoreInstance.objects.none()
    if current_person:
        claimed_by_me = ChoreInstance.objects.filter(
            status=ChoreInstance.Status.CLAIMED, claimed_by=current_person
        ).select_related("chore")
    return render(
        request,
        "chores/chore_pool.html",
        {"instances": instances, "claimed_by_me": claimed_by_me},
    )


def claim_chore(request, instance_id):
    """Claim an open chore instance from the pool. Self-report, no approval."""
    if request.method != "POST":
        return redirect("chores:chore_pool")
    current_person = get_current_person(request)
    if not current_person:
        messages.error(request, "Pick your name before claiming a chore.")
        return redirect("chores:person_picker")
    instance = get_object_or_404(ChoreInstance, pk=instance_id)
    if instance.status != ChoreInstance.Status.OPEN:
        messages.error(request, "That chore isn't open to claim anymore.")
        return redirect("chores:chore_pool")
    instance.status = ChoreInstance.Status.CLAIMED
    instance.claimed_by = current_person
    instance.save()
    messages.success(request, f'You claimed "{instance.chore.title}".')
    return redirect("chores:chore_pool")


def complete_chore(request, instance_id):
    """Mark a claimed chore instance done and award its points. Self-report."""
    if request.method != "POST":
        return redirect("chores:chore_pool")
    current_person = get_current_person(request)
    if not current_person:
        messages.error(request, "Pick your name before completing a chore.")
        return redirect("chores:person_picker")
    instance = get_object_or_404(ChoreInstance, pk=instance_id)
    if (
        instance.status != ChoreInstance.Status.CLAIMED
        or instance.claimed_by_id != current_person.id
    ):
        messages.error(request, "You can only mark done a chore you've claimed.")
        return redirect("chores:chore_pool")
    points = instance.chore.points
    Completion.objects.create(
        instance=instance, person=current_person, points_awarded=points
    )
    instance.status = ChoreInstance.Status.DONE
    instance.save()
    messages.success(
        request, f'Nice work — "{instance.chore.title}" done (+{points} pts).'
    )
    return redirect("chores:chore_pool")


def add_chore(request):
    """Add an ad-hoc one-off chore straight into the pool."""
    if request.method == "POST":
        form = AddOneOffChoreForm(request.POST)
        if form.is_valid():
            instance = form.save()
            messages.success(request, f'Added "{instance.chore.title}" to the pool.')
            return redirect("chores:chore_pool")
    else:
        form = AddOneOffChoreForm()
    return render(request, "chores/add_chore.html", {"form": form})


def leaderboard(request):
    """Running point totals per person, most points first."""
    people = people_with_total_points().order_by("-total_points", "name")
    return render(request, "chores/leaderboard.html", {"people": people})
