from django.contrib.auth.models import User
from django.db import models


class SkincareProfile(models.Model):
    """Store a user's skincare preferences for future analysis."""

    SKIN_TYPE_CHOICES = [
        ("normal", "Normal"),
        ("dry", "Dry"),
        ("oily", "Oily"),
        ("combination", "Combination"),
        ("sensitive", "Sensitive"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="skincare_profile")
    skin_type = models.CharField(max_length=20, choices=SKIN_TYPE_CHOICES, blank=True)
    concerns = models.TextField(blank=True)
    goals = models.TextField(blank=True)
    allergies = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s skincare profile"
