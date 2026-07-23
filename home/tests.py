from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from .models import SkincareProfile


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

    def test_dashboard_redirects_to_access_restricted_page_for_anonymous_users(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("access_restricted"), response.url)
        self.assertIn("/dashboard/", response.url)

    def test_profile_page_redirects_to_access_restricted_page_for_anonymous_users(self):
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("access_restricted"), response.url)
        self.assertIn("/profile/", response.url)

    def test_login_accepts_forwarded_github_host(self):
        user = User.objects.create_user(username="forwardeduser", password="StrongPass123!")

        response = self.client.post(
            reverse("login"),
            {"username": "forwardeduser", "password": "StrongPass123!"},
            HTTP_HOST="8001-forwarded.app.github.dev",
            follow=True,
        )

        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(response.context["user"].is_authenticated)

    def test_login_redirects_back_to_original_page_when_next_is_supplied(self):
        user = User.objects.create_user(username="returninguser", password="StrongPass123!")

        response = self.client.post(
            reverse("login"),
            {"username": user.username, "password": "StrongPass123!", "next": "/profile/"},
            follow=True,
        )

        self.assertRedirects(response, reverse("profile"))

    def test_authenticated_user_can_save_skincare_profile(self):
        user = User.objects.create_user(username="profileuser", password="StrongPass123!")
        self.client.force_login(user)

        response = self.client.post(
            reverse("profile"),
            {
                "skin_type": "combination",
                "concerns": "Dry patches and sensitivity",
                "goals": "Hydration and barrier support",
                "allergies": "Fragrance",
                "notes": "Prefers lightweight products",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("profile"))
        profile = SkincareProfile.objects.get(user=user)
        self.assertEqual(profile.skin_type, "combination")
        self.assertEqual(profile.concerns, "Dry patches and sensitivity")
        self.assertEqual(profile.goals, "Hydration and barrier support")
        self.assertEqual(profile.allergies, "Fragrance")
        self.assertEqual(profile.notes, "Prefers lightweight products")

    def test_skin_analysis_page_is_available(self):
        response = self.client.get(reverse("skin_analysis"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Skin Analysis")

    def test_profile_page_shows_a_personalized_skin_report(self):
        user = User.objects.create_user(username="profileuser2", password="StrongPass123!")
        self.client.force_login(user)

        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Skin Profile")

    def test_recommendations_page_redirects_anonymous_users_to_access_restricted_page(self):
        response = self.client.get(reverse("recommendations"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("access_restricted"), response.url)
        self.assertIn("/recommendations/", response.url)

    def test_access_restricted_page_renders_branded_copy(self):
        response = self.client.get(reverse("access_restricted"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Oops! You do not have permission to reach this page.")
        self.assertContains(response, "Log In")
        self.assertContains(response, "Create Account")

    def test_user_cannot_access_dermatologist_dashboard(self):
        user = User.objects.create_user(username="plainuser", password="StrongPass123!")
        self.client.force_login(user)

        response = self.client.get(reverse("dermatologist_dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("dashboard", response.url)

    def test_dermatologist_can_access_dermatologist_dashboard(self):
        group, _ = Group.objects.get_or_create(name="dermatologist")
        user = User.objects.create_user(username="doctor", password="StrongPass123!")
        user.groups.add(group)
        self.client.force_login(user)

        response = self.client.get(reverse("dermatologist_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dermatologist Dashboard")

    def test_admin_can_access_admin_dashboard(self):
        group, _ = Group.objects.get_or_create(name="admin")
        user = User.objects.create_user(username="adminuser", password="StrongPass123!")
        user.groups.add(group)
        self.client.force_login(user)

        response = self.client.get(reverse("admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin Dashboard")
