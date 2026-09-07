from django.urls import path

from . import views

app_name = "chores"

urlpatterns = [
    path("", views.person_picker, name="person_picker"),
    path("people/<int:person_id>/select/", views.select_person, name="select_person"),
    path("switch/", views.switch_person, name="switch_person"),
    path("pool/", views.chore_pool, name="chore_pool"),
]
