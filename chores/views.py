from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .models import Person
from .session import clear_current_person, set_current_person


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
