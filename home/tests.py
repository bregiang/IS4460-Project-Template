import io
import json
from urllib import error
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Message, SkincareProfile


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


class DermatologistWorkflowTests(TestCase):
    def setUp(self):
        patient_group = Group.objects.create(name="user")
        dermatologist_group = Group.objects.create(name="dermatologist")
        self.dermatologist = User.objects.create_user(
            username="doctor",
            password="StrongPass123!",
            first_name="Drew",
        )
        self.dermatologist.groups.add(dermatologist_group)
        self.patient = User.objects.create_user(
            username="patient",
            password="StrongPass123!",
            first_name="Jordan",
            last_name="Lee",
        )
        self.patient.groups.add(patient_group)
        self.profile = SkincareProfile.objects.create(
            user=self.patient,
            skin_type="sensitive",
            concerns="Redness and dryness",
            goals="Support the skin barrier",
            allergies="Fragrance",
            notes="Prefers a short routine",
            questionnaire_responses=[
                {
                    "question": "How sensitive is your skin to new products?",
                    "answer": "I need to introduce new products slowly",
                }
            ],
            last_questionnaire_at=timezone.now(),
            ai_morning_routine="Gentle cleanser\nSoothing moisturizer\nSPF 30+",
            ai_evening_routine="Gentle cleanser\nBarrier moisturizer",
            ai_recommended_products="Fragrance-free cleanser\nCeramide moisturizer",
            ai_recommendation_explanation="These products prioritize barrier support.",
            ai_recommendation_updated_at=timezone.now(),
        )
        self.client.force_login(self.dermatologist)

    def test_dashboard_shows_summary_patient_data_and_search(self):
        response = self.client.get(reverse("dermatologist_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Total Patients")
        self.assertContains(response, "Pending Reviews")
        self.assertContains(response, "Jordan Lee")
        self.assertContains(response, "Sensitive")
        self.assertContains(response, "Pending")

        no_match = self.client.get(
            reverse("dermatologist_dashboard"), {"q": "someone else"}
        )
        self.assertNotContains(no_match, "Jordan Lee")

    def test_patient_review_displays_profile_questionnaire_and_ai_recommendation(self):
        response = self.client.get(
            reverse("dermatologist_patient", args=[self.patient.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jordan Lee")
        self.assertContains(response, "@patient")
        self.assertContains(response, "Prefers a short routine")
        self.assertNotContains(response, "Skin concerns")
        self.assertNotContains(response, "<dt class=\"col-sm-5 mb-2\">Goals</dt>")
        self.assertNotContains(response, "Allergies")
        self.assertContains(response, "Questionnaire results")
        self.assertContains(response, "I need to introduce new products slowly")
        self.assertContains(response, "AI-generated recommendation")
        self.assertContains(response, "Soothing moisturizer")
        self.assertContains(response, "These products prioritize barrier support.")

    def test_dashboard_review_link_opens_the_selected_patient_workspace(self):
        dashboard = self.client.get(reverse("dermatologist_dashboard"))
        patient_url = reverse("dermatologist_patient", args=[self.patient.pk])

        self.assertContains(dashboard, f'href="{patient_url}"')
        self.assertNotContains(
            dashboard, f'href="{reverse("dermatologist_messages")}"'
        )

        review_page = self.client.get(patient_url)
        self.assertEqual(review_page.context["patient"], self.patient)
        self.assertEqual(review_page.context["profile"], self.profile)

    def test_patient_review_handles_an_empty_profile(self):
        empty_patient = User.objects.create_user(
            username="newpatient", password="StrongPass123!"
        )
        empty_patient.groups.add(Group.objects.get(name="user"))

        response = self.client.get(
            reverse("dermatologist_patient", args=[empty_patient.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "@newpatient")
        self.assertContains(response, "Not provided")
        self.assertContains(response, "Not completed")
        self.assertNotContains(response, "<dt class=\"col-sm-5 mb-2\">Notes</dt>")
        self.assertContains(
            response,
            "No saved questionnaire responses are available for this patient.",
        )
        self.assertContains(
            response, "No generated recommendation has been saved for this patient."
        )

    def test_professional_recommendation_can_be_created_and_edited(self):
        url = reverse("dermatologist_patient", args=[self.patient.pk])
        response = self.client.post(
            url,
            {
                "action": "save_recommendation",
                "professional_notes": "Begin with a fragrance-free barrier routine.",
            },
            follow=True,
        )

        self.assertRedirects(response, url)
        self.profile.refresh_from_db()
        self.assertEqual(
            self.profile.professional_notes,
            "Begin with a fragrance-free barrier routine.",
        )
        self.assertContains(response, "Reviewed")

        self.client.post(
            url,
            {
                "action": "save_recommendation",
                "professional_notes": "Updated professional guidance.",
            },
        )
        self.profile.refresh_from_db()
        self.assertEqual(
            self.profile.professional_notes, "Updated professional guidance."
        )

    def test_dermatologist_can_view_conversation_and_send_message(self):
        Message.objects.create(
            sender=self.patient,
            recipient=self.dermatologist,
            subject="Routine question",
            body="Should I patch test first?",
        )
        url = reverse("dermatologist_patient", args=[self.patient.pk])

        response = self.client.post(
            url,
            {
                "action": "send_message",
                "subject": "Re: Routine question",
                "body": "Yes, patch test each new product.",
            },
            follow=True,
        )

        self.assertRedirects(response, url)
        self.assertContains(response, "Should I patch test first?")
        self.assertContains(response, "Yes, patch test each new product.")
        sent = Message.objects.get(
            sender=self.dermatologist, recipient=self.patient
        )
        self.assertEqual(sent.subject, "Re: Routine question")

    def test_questionnaire_and_generated_recommendation_are_saved_for_patient(self):
        self.client.force_login(self.patient)
        questionnaire_response = self.client.post(
            reverse("save_questionnaire_results"),
            data=json.dumps(
                {
                    "skin_type": "dry",
                    "responses": [
                        {
                            "question": "How does your skin feel after cleansing?",
                            "answer": "A little tight or dry",
                        }
                    ],
                }
            ),
            content_type="application/json",
        )
        recommendation_response = self.client.post(
            reverse("generate_ai_recommendation"),
            data=json.dumps(
                {
                    "profile_type": "dry",
                    "product_goal": "reduce tightness",
                    "concern_hint": "fragrance-free",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(questionnaire_response.status_code, 200)
        self.assertEqual(recommendation_response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.skin_type, "dry")
        self.assertEqual(
            self.profile.questionnaire_responses[0]["answer"],
            "A little tight or dry",
        )
        self.assertIsNotNone(self.profile.last_questionnaire_at)
        self.assertIn("Cream cleanser", self.profile.ai_morning_routine)
        self.assertTrue(self.profile.ai_recommendation_explanation)
