from .session import get_current_person as _get_current_person


def current_person(request):
    """Make the acting person available to every template as {{ current_person }}."""
    return {"current_person": _get_current_person(request)}
