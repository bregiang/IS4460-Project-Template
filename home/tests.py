import io
import json
from urllib import error
from unittest.mock import patch

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
        self.assertContains(response, "Facial skin mapping")
        self.assertContains(response, "How each step supports your skin")

    def test_skin_analysis_page_includes_ai_recommendation_assistant(self):
        response = self.client.get(reverse("skin_analysis"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI routine coach")
        self.assertContains(response, "Generate AI plan")

    def test_ai_recommendation_endpoint_returns_json_payload(self):
        response = self.client.post(
            reverse("generate_ai_recommendation"),
            data=json.dumps({"profile_type": "dry", "product_goal": "reduce tightness", "concern_hint": "fragrance-free only"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("recommendation", data)
        self.assertIn("source", data)
        self.assertIn(data["source"], {"gemini", "fallback"})
        self.assertTrue(isinstance(data["recommendation"], str) and bool(data["recommendation"].strip()))

    def test_ai_recommendation_endpoint_returns_gemini_branch_when_http_call_succeeds(self):
        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(self._payload).encode("utf-8")

            def __iter__(self):
                yield self.read()

        fake_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "A tailored serum and moisturizer plan."}]
                    }
                }
            ]
        }

        with patch("home.views.urllib_request.urlopen", return_value=FakeResponse(fake_payload)) as mocked_urlopen:
            response = self.client.post(
                reverse("generate_ai_recommendation"),
                data=json.dumps({"profile_type": "sensitive", "product_goal": "calm irritation", "concern_hint": "fragrance-free only"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["source"], "gemini")
        self.assertEqual(data["recommendation"], "A tailored serum and moisturizer plan.")
        mocked_urlopen.assert_called_once()

    def test_ai_recommendation_sends_user_role_in_gemini_payload(self):
        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(self._payload).encode("utf-8")

            def __iter__(self):
                yield self.read()

        fake_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "A tailored serum and moisturizer plan."}]
                    }
                }
            ]
        }

        with patch("home.views.urllib_request.urlopen", return_value=FakeResponse(fake_payload)) as mocked_urlopen:
            self.client.post(
                reverse("generate_ai_recommendation"),
                data=json.dumps({"profile_type": "dry", "product_goal": "hydration", "concern_hint": "fragrance-free only"}),
                content_type="application/json",
            )

        request = mocked_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["contents"][0]["role"], "user")
        self.assertIn("at least 120 words", payload["contents"][0]["parts"][0]["text"])
        self.assertIn("do not start with a greeting", payload["contents"][0]["parts"][0]["text"])

    def test_ai_recommendation_endpoint_falls_back_when_http_call_errors(self):
        with patch.dict("os.environ", {"GEMINI_MODEL": "gemini-2.5-flash"}, clear=False), patch(
            "home.views.urllib_request.urlopen", side_effect=Exception("boom")
        ):
            response = self.client.post(
                reverse("generate_ai_recommendation"),
                data=json.dumps({"profile_type": "oily", "product_goal": "control shine", "concern_hint": "lightweight only"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["source"], "fallback")
        self.assertEqual(data["model"], "gemini-2.5-flash")
        self.assertIn("gentle cleanser", data["recommendation"])
        self.assertIn("moisturizer", data["recommendation"])

    def test_ai_recommendation_endpoint_reports_model_name_on_unsupported_model_error(self):
        payload = json.dumps({"error": {"status": "NOT_FOUND", "message": "models/gemini-3.5-flash is not found"}}).encode("utf-8")
        http_error = error.HTTPError(
            url="https://example.test",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=io.BytesIO(payload),
        )

        with patch.dict("os.environ", {"GEMINI_MODEL": "gemini-3.5-flash"}, clear=False), patch(
            "home.views.urllib_request.urlopen", side_effect=http_error
        ):
            response = self.client.post(
                reverse("generate_ai_recommendation"),
                data=json.dumps({"profile_type": "dry", "product_goal": "hydration", "concern_hint": "fragrance-free only"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["source"], "fallback")
        self.assertIn("gemini-3.5-flash", data["error"])
        self.assertNotIn("The Gemini model name is not supported", data["error"])

    def test_homepage_includes_botanical_and_skin_mapping_visuals(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "botanical-art")
        self.assertContains(response, "Example facial skin analysis map")
        self.assertNotContains(response, "How each step supports your skin")

    def test_profile_page_shows_a_personalized_skin_report(self):
        user = User.objects.create_user(username="profileuser2", password="StrongPass123!")
        self.client.force_login(user)

        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Skin Profile")
        self.assertContains(response, "Area-by-area balance")
        self.assertContains(response, "skin-map-visual")
        self.assertNotContains(response, "How each step supports your skin")

    def test_ritual_visuals_are_not_rendered_on_recommendations(self):
        user = User.objects.create_user(username="recommendationvisuals", password="StrongPass123!")
        self.client.force_login(user)

        response = self.client.get(reverse("recommendations"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "How each step supports your skin")
        for retailer in (
            "Sephora",
            "Ulta Beauty",
            "Dermstore",
            "Target",
            "CVS Pharmacy",
            "Amazon",
            "Walmart",
            "Bluemercury",
        ):
            self.assertContains(response, f"retailer: '{retailer}'")
        self.assertContains(response, "Official brand storefront")
        self.assertContains(response, 'rel="noopener noreferrer external"')
        self.assertEqual(response.content.decode().count("url: 'https://"), 14)

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
