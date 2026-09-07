from django.contrib import admin

from .models import Chore, ChoreInstance, Completion, Person


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]


@admin.register(Chore)
class ChoreAdmin(admin.ModelAdmin):
    list_display = ["title", "points", "recurrence", "is_active", "created_at"]
    list_filter = ["recurrence", "is_active"]
    search_fields = ["title"]


@admin.register(ChoreInstance)
class ChoreInstanceAdmin(admin.ModelAdmin):
    list_display = ["chore", "status", "claimed_by", "due_date", "created_at"]
    list_filter = ["status", "due_date"]
    search_fields = ["chore__title"]
    autocomplete_fields = ["chore", "claimed_by"]


@admin.register(Completion)
class CompletionAdmin(admin.ModelAdmin):
    list_display = ["instance", "person", "points_awarded", "completed_at"]
    list_filter = ["completed_at"]
    search_fields = ["person__name", "instance__chore__title"]
    autocomplete_fields = ["instance", "person"]
