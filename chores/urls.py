from django.urls import path

from . import views

app_name = "chores"

urlpatterns = [
    path("", views.person_picker, name="person_picker"),
    path("people/<int:person_id>/select/", views.select_person, name="select_person"),
    path("switch/", views.switch_person, name="switch_person"),
    path("pool/", views.chore_pool, name="chore_pool"),
    path("instances/<int:instance_id>/claim/", views.claim_chore, name="claim_chore"),
    path(
        "instances/<int:instance_id>/complete/",
        views.complete_chore,
        name="complete_chore",
    ),
    path("chores/add/", views.add_chore, name="add_chore"),
    path("leaderboard/", views.leaderboard, name="leaderboard"),
    path("history/", views.history, name="history"),
]
