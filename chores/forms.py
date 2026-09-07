from django import forms

from .models import Chore, ChoreInstance


class AddOneOffChoreForm(forms.Form):
    """Add an ad-hoc chore straight into the pool.

    Under the hood this still creates a one-off Chore (recurrence=NONE)
    plus its single ChoreInstance, but the form presents it as one step.
    """

    title = forms.CharField(max_length=200)
    points = forms.IntegerField(
        min_value=1,
        initial=1,
        help_text="Must be at least 1 (stricter than the model default).",
    )
    due_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    def save(self):
        chore = Chore.objects.create(
            title=self.cleaned_data["title"],
            points=self.cleaned_data["points"],
            recurrence=Chore.Recurrence.NONE,
        )
        return ChoreInstance.objects.create(
            chore=chore, due_date=self.cleaned_data.get("due_date")
        )
