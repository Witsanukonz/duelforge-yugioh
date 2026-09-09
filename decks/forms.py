from django import forms

from .models import Deck


class DeckForm(forms.ModelForm):
    class Meta:
        model = Deck
        fields = (
            "name",
            "description",
            "deck_type",
            "format",
            "ban_list",
            "is_public",
        )

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Deck name cannot be blank.")
        return name
