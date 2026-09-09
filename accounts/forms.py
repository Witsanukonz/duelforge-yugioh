from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class AccountSignupForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        help_text="Used only for account recovery.",
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].help_text = "Demo: use any password you like."

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class DemoPasswordResetRequestForm(forms.Form):
    email = forms.EmailField(label="Account email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        matches = list(
            get_user_model().objects.filter(
                email__iexact=email,
                is_active=True,
            ).order_by("pk")[:2]
        )
        if not matches:
            raise forms.ValidationError("No account was found with this email.")
        if len(matches) > 1:
            raise forms.ValidationError(
                "This email belongs to more than one account. Contact the administrator."
            )
        self.user = matches[0]
        return email
