from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, User


class CustomUserCreationForm(UserCreationForm):
    """Registration form with a role choice for SkinIdentifier users."""

    email = forms.EmailField(required=True)
    role = forms.ChoiceField(
        choices=[
            ("consumer", "Consumer"),
            ("dermatologist", "Dermatologist"),
            ("administrator", "Administrator"),
        ],
        required=True,
        label="Account type",
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2", "role")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            role_name = self.cleaned_data["role"]
            group, _ = Group.objects.get_or_create(name=role_name)
            user.groups.add(group)
        return user
