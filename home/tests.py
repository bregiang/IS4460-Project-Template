from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class SkinIdentifierAuthTests(TestCase):
    """Tests for registration, login, and role-based access."""

    def test_consumer_registration_assigns_role(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "consumer1",
                "email": "consumer@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
                "role": "consumer",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(username="consumer1")
        self.assertTrue(user.groups.filter(name="consumer").exists())

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)
