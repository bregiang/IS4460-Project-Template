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
    professional_notes = models.TextField(blank=True)
    questionnaire_responses = models.JSONField(default=list, blank=True)
    last_questionnaire_at = models.DateTimeField(null=True, blank=True)
    ai_morning_routine = models.TextField(blank=True)
    ai_evening_routine = models.TextField(blank=True)
    ai_recommended_products = models.TextField(blank=True)
    ai_recommendation_explanation = models.TextField(blank=True)
    ai_recommendation_updated_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s skincare profile"


class Message(models.Model):
    """Store secure in-app messages between users and dermatologists."""

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_messages")
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    professional_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.sender} -> {self.recipient}: {self.subject or 'conversation'}"


class InventoryItem(models.Model):
    """Represents a product available for retailer recommendations and admin inventory management."""

    CATEGORY_CHOICES = [
        ("cleanser", "Cleanser"),
        ("serum", "Serum"),
        ("moisturizer", "Moisturizer"),
        ("sunscreen", "Sunscreen"),
        ("mask", "Mask"),
        ("treatment", "Treatment"),
    ]

    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    retailer = models.CharField(max_length=100)
    in_stock = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
