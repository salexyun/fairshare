"""Honor-system identity: no login, just a name picked into the session.

Per _docs/plan.md, there is no password/account system — a person picks
their name and the choice is remembered for their browser session.
"""

from .models import Person

PERSON_SESSION_KEY = "person_id"


def get_current_person(request):
    """Return the Person acting in this session, or None if nobody's picked."""
    person_id = request.session.get(PERSON_SESSION_KEY)
    if not person_id:
        return None
    return Person.objects.filter(pk=person_id).first()


def set_current_person(request, person):
    request.session[PERSON_SESSION_KEY] = person.pk


def clear_current_person(request):
    request.session.pop(PERSON_SESSION_KEY, None)
