from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, User

from .models import InventoryItem, Message, SkincareProfile


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
            role_value = self.cleaned_data["role"]
            role_map = {
                "consumer": "user",
                "user": "user",
                "dermatologist": "dermatologist",
                "administrator": "admin",
                "admin": "admin",
            }
            canonical_role = role_map.get(role_value, "user")
            group_names = [canonical_role]
            if canonical_role == "user":
                group_names.append("consumer")
            elif canonical_role == "admin":
                group_names.append("administrator")
            for group_name in group_names:
                group, _ = Group.objects.get_or_create(name=group_name)
                user.groups.add(group)
            if canonical_role == "admin":
                user.is_staff = True
                user.is_superuser = True
                user.save(update_fields=["is_staff", "is_superuser"])
        return user


class SkincareProfileForm(forms.ModelForm):
    """Collect a user's skincare profile details."""

    class Meta:
        model = SkincareProfile
        fields = ("skin_type", "concerns", "goals", "allergies", "notes")
        widgets = {
            "concerns": forms.Textarea(attrs={"rows": 3}),
            "goals": forms.Textarea(attrs={"rows": 3}),
            "allergies": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class ProfessionalNoteForm(forms.ModelForm):
    """Allow dermatologists to attach professional recommendations to a patient."""

    class Meta:
        model = SkincareProfile
        fields = ("professional_notes",)
        labels = {"professional_notes": "Professional recommendation"}
        widgets = {
            "professional_notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 7,
                    "placeholder": "Add routine guidance, product cautions, and follow-up recommendations.",
                }
            ),
        }


class MessageForm(forms.ModelForm):
    """Allow dermatologists to send secure messages to users."""

    class Meta:
        model = Message
        fields = ("recipient", "subject", "body", "professional_note")
        widgets = {
            "body": forms.Textarea(attrs={"rows": 4}),
            "professional_note": forms.Textarea(attrs={"rows": 3}),
        }


class PatientMessageForm(forms.ModelForm):
    """Send a message within a selected patient's conversation."""

    class Meta:
        model = Message
        fields = ("subject", "body")
        labels = {"body": "Message"}
        widgets = {
            "subject": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Optional subject"}
            ),
            "body": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Write a message to the patient.",
                }
            ),
        }


class InventoryItemForm(forms.ModelForm):
    """Support admin inventory management for retailer recommendations."""

    class Meta:
        model = InventoryItem
        fields = ("name", "brand", "category", "price", "retailer", "in_stock", "notes")
