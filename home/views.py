import json
import os
from pathlib import Path
from urllib import error, request as urllib_request
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group, User
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from dotenv import load_dotenv

from .forms import (
    CustomUserCreationForm,
    InventoryItemForm,
    MessageForm,
    PatientMessageForm,
    ProfessionalNoteForm,
    SkincareProfileForm,
)
from .models import InventoryItem, Message, SkincareProfile

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


ROUTINE_DETAILS = {
    "normal": {
        "morning": "Gentle cleanser\nLightweight moisturizer\nBroad-spectrum SPF 30+",
        "evening": "Gentle cleanser\nHydrating serum\nLightweight moisturizer",
        "products": "Mild gel or cream cleanser\nHyaluronic acid serum\nLight moisturizer\nBroad-spectrum sunscreen",
    },
    "dry": {
        "morning": "Cream cleanser or water rinse\nHydrating serum\nRich moisturizer\nBroad-spectrum SPF 30+",
        "evening": "Cream cleanser\nBarrier-support serum\nCeramide-rich moisturizer",
        "products": "Cream cleanser\nHyaluronic acid or glycerin serum\nCeramide moisturizer\nMoisturizing sunscreen",
    },
    "oily": {
        "morning": "Gentle gel cleanser\nNiacinamide serum\nOil-free moisturizer\nBroad-spectrum SPF 30+",
        "evening": "Gentle gel cleanser\nSalicylic acid treatment two to three times weekly\nLightweight moisturizer",
        "products": "Gentle gel cleanser\nNiacinamide serum\nSalicylic acid treatment\nOil-free moisturizer\nNon-comedogenic sunscreen",
    },
    "combination": {
        "morning": "Gentle foaming cleanser\nLight hydrating serum\nLightweight moisturizer\nBroad-spectrum SPF 30+",
        "evening": "Gentle cleanser\nTargeted treatment on the T-zone\nMoisturizer, layered more generously on dry areas",
        "products": "Balanced foaming cleanser\nHydrating serum\nLight lotion\nTargeted BHA treatment\nLightweight sunscreen",
    },
    "sensitive": {
        "morning": "Fragrance-free gentle cleanser or water rinse\nSoothing moisturizer\nMineral or sensitive-skin SPF 30+",
        "evening": "Fragrance-free gentle cleanser\nCalming serum\nBarrier-support moisturizer",
        "products": "Fragrance-free cleanser\nCentella, oat, or panthenol serum\nBarrier moisturizer\nSensitive-skin sunscreen",
    },
}


def save_recommendation_for_user(request, profile_type, recommendation):
    """Persist the application's latest generated routine for an authenticated user."""
    if not request.user.is_authenticated:
        return
    details = ROUTINE_DETAILS.get(profile_type, ROUTINE_DETAILS["normal"])
    profile, _ = SkincareProfile.objects.get_or_create(user=request.user)
    profile.skin_type = profile_type if profile_type in ROUTINE_DETAILS else profile.skin_type
    profile.ai_morning_routine = details["morning"]
    profile.ai_evening_routine = details["evening"]
    profile.ai_recommended_products = details["products"]
    profile.ai_recommendation_explanation = recommendation
    profile.ai_recommendation_updated_at = timezone.now()
    profile.save()


def patient_dashboard_context(request):
    """Build the searchable patient review summary used by dermatologist dashboards."""
    query = request.GET.get("q", "").strip()
    patients = (
        User.objects.filter(groups__name="user")
        .select_related("skincare_profile")
        .distinct()
        .order_by("first_name", "last_name", "username")
    )
    if query:
        patients = patients.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(username__icontains=query)
        )

    patient_rows = []
    for patient in patients:
        try:
            profile = patient.skincare_profile
        except SkincareProfile.DoesNotExist:
            profile = None
        patient_rows.append(
            {
                "user": patient,
                "profile": profile,
                "is_reviewed": bool(profile and profile.professional_notes.strip()),
            }
        )

    all_profiles = SkincareProfile.objects.filter(user__groups__name="user").distinct()
    total_patients = (
        User.objects.filter(groups__name="user").distinct().count()
    )
    reviewed_patients = sum(
        1 for notes in all_profiles.values_list("professional_notes", flat=True) if notes.strip()
    )
    return {
        "patient_rows": patient_rows,
        "total_patients": total_patients,
        "reviewed_patients": reviewed_patients,
        "pending_reviews": total_patients - reviewed_patients,
        "search_query": query,
        "role": get_user_role(request.user),
    }


def home_page(request):
    """Render the landing page for the SkinIdentifier product."""
    return render(request, "home/home.html")


def skin_analysis_view(request):
    """Render the interactive skin analysis quiz and result experience."""
    return render(request, "home/skin_analysis.html")


def generate_ai_recommendation(request):
    """Use Gemini to turn a skin-analysis result into a personalized product recommendation plan."""
    if request.method != "POST":
        return JsonResponse({"error": "Only POST requests are supported."}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}

    profile_type = (payload.get("profile_type") or "normal").strip().lower() or "normal"
    concern_hint = (payload.get("concern_hint") or "").strip()
    product_goal = (payload.get("product_goal") or "balanced routine").strip() or "balanced routine"

    prompt = (
        f"You are a skincare retail advisor. Create a complete, practical product recommendation plan for a user with {profile_type} skin. "
        f"Their stated goal is {product_goal}. "
        "Write a full answer with 3 product categories, using clear reasons and one calming ingredient for each. "
        "Format it as plain text with 3 numbered sections, short paragraphs, and bullet points using hyphens. "
        "Do not use markdown bold markers, asterisks, or tables. "
        "Make the plan feel helpful and retail-ready, use at least 120 words, and do not start with a greeting or stop halfway through. "
        f"If the user added details, use them: {concern_hint or 'No extra details provided.'}"
    )

    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    timeout_seconds = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "20"))
    max_output_tokens = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "260"))

    if api_key:
        try:
            gemini_payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": max_output_tokens,
                },
            }
            req = urllib_request.Request(
                f"https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent",
                data=json.dumps(gemini_payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                },
                method="POST",
            )
            with urllib_request.urlopen(req, timeout=timeout_seconds) as response:
                result = json.load(response)
            candidates = result.get("candidates") or []
            if candidates:
                parts = candidates[0].get("content", {}).get("parts") or []
                text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
                if text.strip():
                    recommendation = text.strip()
                    save_recommendation_for_user(request, profile_type, recommendation)
                    return JsonResponse({"recommendation": recommendation, "source": "gemini"})
        except Exception as exc:
            raw_error_message = str(exc)
            friendly_error_message = f"The Gemini request failed while using model '{model}'. Please verify the model name, API key, and Gemini API access for your Google project."
            if isinstance(exc, error.HTTPError):
                try:
                    raw_error_message = exc.read().decode("utf-8", errors="ignore")
                except Exception:
                    raw_error_message = str(exc)

                try:
                    payload = json.loads(raw_error_message)
                    error_info = payload.get("error", {})
                    status = error_info.get("status", "")
                    message = error_info.get("message", "")
                    raw_error_message = message or raw_error_message
                    if status == "UNAUTHENTICATED" or "invalid authentication credentials" in message.lower():
                        friendly_error_message = (
                            f"Your Gemini API key is not being accepted for model '{model}'. "
                            "Please verify the key and make sure the Gemini API is enabled for the Google project."
                        )
                    elif status == "PERMISSION_DENIED" or "blocked" in message.lower():
                        friendly_error_message = (
                            f"The Gemini API is blocked for model '{model}'. "
                            "Please check the project permissions and API enablement."
                        )
                    elif "not found" in message.lower() or "model" in message.lower():
                        friendly_error_message = (
                            f"The Gemini request failed while using model '{model}'. "
                            "The model or endpoint may be unsupported for this project, so please verify the model name and Gemini API enablement."
                        )
                    elif message:
                        friendly_error_message = f"The Gemini request failed while using model '{model}': {message}"
                except Exception:
                    friendly_error_message = f"The Gemini request failed while using model '{model}': {raw_error_message}"
            fallback = (
                f"For {profile_type} skin, start with a gentle cleanser, a lightweight moisturizer, and daily sunscreen. "
                f"If your goal is {product_goal}, choose fragrance-free formulas with barrier-friendly ingredients like ceramides, niacinamide, or hyaluronic acid. "
                f"{concern_hint if concern_hint else 'Keep the routine simple, patch test new products, and increase actives slowly.'}"
            )
            save_recommendation_for_user(request, profile_type, fallback)
            return JsonResponse({"recommendation": fallback, "source": "fallback", "error": raw_error_message, "friendly_error": friendly_error_message, "model": model})

    fallback = (
        f"For {profile_type} skin, start with a gentle cleanser, a lightweight moisturizer, and daily sunscreen. "
        f"If your goal is {product_goal}, choose fragrance-free formulas with barrier-friendly ingredients like ceramides, niacinamide, or hyaluronic acid. "
        f"{concern_hint if concern_hint else 'Keep the routine simple, patch test new products, and increase actives slowly.'}"
    )
    save_recommendation_for_user(request, profile_type, fallback)
    return JsonResponse({"recommendation": fallback, "source": "fallback", "model": model})


def save_questionnaire_results(request):
    """Save a signed-in user's completed questionnaire for later professional review."""
    if request.method != "POST":
        return JsonResponse({"error": "Only POST requests are supported."}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({"saved": False, "error": "Sign in to save results."}, status=401)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"saved": False, "error": "Invalid questionnaire data."}, status=400)

    responses = payload.get("responses")
    skin_type = str(payload.get("skin_type") or "").strip().lower()
    if not isinstance(responses, list) or not responses or len(responses) > 50:
        return JsonResponse({"saved": False, "error": "Questionnaire responses are required."}, status=400)

    cleaned_responses = []
    for response in responses:
        if not isinstance(response, dict):
            return JsonResponse({"saved": False, "error": "Invalid questionnaire response."}, status=400)
        question = str(response.get("question") or "").strip()[:500]
        answer = str(response.get("answer") or "").strip()[:500]
        if not question or not answer:
            return JsonResponse({"saved": False, "error": "Every response needs a question and answer."}, status=400)
        cleaned_responses.append({"question": question, "answer": answer})

    profile, _ = SkincareProfile.objects.get_or_create(user=request.user)
    profile.questionnaire_responses = cleaned_responses
    profile.last_questionnaire_at = timezone.now()
    if skin_type in ROUTINE_DETAILS:
        profile.skin_type = skin_type
    profile.save()
    return JsonResponse({"saved": True})


def about_page(request):
    """Render the polished informational about page."""
    return render(request, "home/about.html")


def privacy_page(request):
    """Render the privacy policy page."""
    return render(request, "home/privacy.html")


def contact_page(request):
    """Render the contact page with a simple form layout."""
    return render(request, "home/contact.html")


def get_safe_redirect_url(request, default_url):
    """Return a safe relative redirect target from the request."""
    next_url = request.POST.get("next") or request.GET.get("next")
    if not next_url:
        return default_url

    parsed = urlparse(next_url)
    if parsed.scheme or parsed.netloc:
        return default_url
    return next_url


def access_restricted_view(request):
    """Render a branded page for users who need to sign in first."""
    next_url = request.GET.get("next", "")
    return render(request, "home/access_restricted.html", {"next_url": next_url})


@login_required(login_url="access_restricted")
def recommendations_page(request):
    """Render personalized third-party retailer skincare recommendations."""
    profile = None
    skin_type = "combination"
    concerns = "hydration"
    goals = "balanced skincare"

    if request.user.is_authenticated:
        profile = SkincareProfile.objects.filter(user=request.user).first()
        if profile:
            skin_type = profile.skin_type or skin_type
            concerns = profile.concerns or concerns
            goals = profile.goals or goals

    profile_context = {
        "skin_type": skin_type,
        "concerns": concerns,
        "goals": goals,
    }
    return render(request, "home/recommendations.html", {"profile_context": profile_context})


def get_user_role(user):
    """Return the highest-priority role name for a user."""
    if not user.is_authenticated:
        return "guest"
    if user.groups.filter(name="admin").exists():
        return "admin"
    if user.groups.filter(name="dermatologist").exists():
        return "dermatologist"
    return "user"


def role_required(*roles):
    """Decorate views to require a specific role or roles."""

    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, "Please log in to access this page.")
                redirect_url = reverse("access_restricted")
                if request.get_full_path() not in {"/", ""}:
                    redirect_url = f"{redirect_url}?next={request.get_full_path()}"
                return redirect(redirect_url)
            if get_user_role(request.user) not in roles:
                messages.error(request, "You do not have access to that area.")
                return redirect("dashboard")
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def register_view(request):
    """Allow new users to create an account and select a role."""
    next_url = get_safe_redirect_url(request, reverse("dashboard"))
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Ensure a SkincareProfile is created for every new user
            SkincareProfile.objects.get_or_create(user=user)
            login(request, user)
            messages.success(request, "Registration successful. Welcome to SkinIdentifier.")
            return redirect(next_url)
    else:
        form = CustomUserCreationForm()

    return render(request, "home/register.html", {"form": form, "next_url": next_url})


def login_view(request):
    """Authenticate users with Django's built-in login form."""
    next_url = get_safe_redirect_url(request, reverse("dashboard"))
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "You are now logged in.")
            return redirect(next_url)
    else:
        form = AuthenticationForm()

    return render(request, "home/login.html", {"form": form, "next_url": next_url})


@login_required(login_url="access_restricted")
def dashboard_view(request):
    """Display a role-aware dashboard for the authenticated user."""
    role = get_user_role(request.user)
    profile = SkincareProfile.objects.filter(user=request.user).first()
    if role == "dermatologist":
        return render(
            request,
            "home/dermatologist_dashboard.html",
            patient_dashboard_context(request),
        )
    if role == "admin":
        user_accounts = User.objects.all()
        inventory_items = InventoryItem.objects.all()
        return render(request, "home/admin_dashboard.html", {"role": role, "profile": profile, "user_accounts": user_accounts, "inventory_items": inventory_items})
    return render(request, "home/dashboard.html", {"role": role, "profile": profile})


@login_required(login_url="access_restricted")
def profile_view(request):
    """Allow authenticated users to create or update their skincare profile."""
    profile, _ = SkincareProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = SkincareProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your skincare profile has been saved.")
            return redirect("profile")
    else:
        form = SkincareProfileForm(instance=profile)

    return render(request, "home/profile.html", {"form": form, "profile": profile, "role": get_user_role(request.user)})


@login_required(login_url="access_restricted")
def skin_history_view(request):
    """Show a secure skin-history view for the current user or a patient when viewed by a dermatologist."""
    # Ensure a profile exists for the requesting user instead of raising 404
    try:
        profile, _ = SkincareProfile.objects.get_or_create(user=request.user)
    except Exception:
        return render(request, "home/profile_missing.html", {"user_obj": request.user, "role": get_user_role(request.user)})

    return render(request, "home/skin_history.html", {"profile": profile, "role": get_user_role(request.user)})


@login_required(login_url="access_restricted")
@role_required("dermatologist")
def dermatologist_dashboard(request):
    """Provide a professional dashboard for dermatologists."""
    return render(
        request,
        "home/dermatologist_dashboard.html",
        patient_dashboard_context(request),
    )


@login_required(login_url="access_restricted")
@role_required("admin", "dermatologist")
def dermatologist_patient_view(request, user_id):
    """Allow dermatologists and admins to review a patient's skin profile and history."""
    patient = get_object_or_404(
        User.objects.filter(groups__name="user").distinct(), pk=user_id
    )
    # Create the patient's SkincareProfile if it does not exist to avoid 404s
    try:
        profile, created = SkincareProfile.objects.get_or_create(user=patient)
    except Exception:
        return render(request, "home/profile_missing.html", {"user_obj": patient, "role": get_user_role(request.user)})

    if created:
        messages.info(request, "A skincare profile was created for this patient.")
    conversation = Message.objects.filter(
        Q(sender=request.user, recipient=patient)
        | Q(sender=patient, recipient=request.user)
    ).order_by("created_at")
    if request.method == "POST":
        action = request.POST.get("action", "save_recommendation")
        if action == "send_message":
            form = ProfessionalNoteForm(instance=profile)
            message_form = PatientMessageForm(request.POST)
            if message_form.is_valid():
                patient_message = message_form.save(commit=False)
                patient_message.sender = request.user
                patient_message.recipient = patient
                patient_message.save()
                messages.success(request, "Message sent successfully.")
                return redirect("dermatologist_patient", user_id=patient.pk)
        else:
            form = ProfessionalNoteForm(request.POST, instance=profile)
            message_form = PatientMessageForm()
            if form.is_valid():
                form.save()
                messages.success(request, "Professional recommendation saved.")
                return redirect("dermatologist_patient", user_id=patient.pk)
    else:
        form = ProfessionalNoteForm(instance=profile)
        message_form = PatientMessageForm()
    return render(
        request,
        "home/dermatologist_patient.html",
        {
            "patient": patient,
            "profile": profile,
            "form": form,
            "message_form": message_form,
            "conversation": conversation,
            "is_reviewed": bool(profile.professional_notes.strip()),
            "role": get_user_role(request.user),
        },
    )


@login_required(login_url="access_restricted")
@role_required("dermatologist")
def dermatologist_messages(request):
    """Show messages sent by dermatologists to patients."""
    sent_messages = Message.objects.filter(sender=request.user)
    return render(request, "home/dermatologist_messages.html", {"sent_messages": sent_messages, "role": get_user_role(request.user)})


@login_required(login_url="access_restricted")
@role_required("dermatologist")
def send_message_to_patient(request, user_id=None):
    """Send a secure message to a user from a dermatologist."""
    patient = get_object_or_404(User, pk=user_id) if user_id else None
    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.save()
            messages.success(request, "Message sent successfully.")
            return redirect("dermatologist_messages")
    else:
        initial = {"recipient": patient} if patient else {}
        form = MessageForm(initial=initial)
    return render(request, "home/send_message.html", {"form": form, "patient": patient, "role": get_user_role(request.user)})


@login_required(login_url="access_restricted")
@role_required("admin")
def admin_dashboard(request):
    """Provide an administrative control panel for superusers."""
    user_accounts = User.objects.all()
    inventory_items = InventoryItem.objects.all()
    all_messages = Message.objects.all()
    return render(request, "home/admin_dashboard.html", {"user_accounts": user_accounts, "inventory_items": inventory_items, "messages": all_messages, "role": get_user_role(request.user)})


@login_required(login_url="access_restricted")
@role_required("admin")
def inventory_management(request):
    """Allow administrators to manage product inventory and retailer listings."""
    items = InventoryItem.objects.all()
    if request.method == "POST":
        form = InventoryItemForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Inventory item saved.")
            return redirect("inventory_management")
    else:
        form = InventoryItemForm()
    return render(request, "home/inventory_management.html", {"items": items, "form": form, "role": get_user_role(request.user)})


@login_required(login_url="access_restricted")
def user_messages(request):
    """Allow standard users to see messages from dermatologists."""
    if get_user_role(request.user) == "admin":
        return redirect("admin_dashboard")
    messages_received = Message.objects.filter(recipient=request.user)
    return render(request, "home/user_messages.html", {"messages_received": messages_received, "role": get_user_role(request.user)})


@login_required(login_url="access_restricted")
@role_required("admin", "dermatologist")
def create_profile_for_user(request, user_id):
    """Create a SkincareProfile for another user (admin/dermatologist action)."""
    patient = get_object_or_404(User, pk=user_id)
    profile, created = SkincareProfile.objects.get_or_create(user=patient)
    if created:
        messages.success(request, "Skincare profile created for the user.")
    else:
        messages.info(request, "User already has a skincare profile.")
    return redirect("dermatologist_patient", user_id=patient.pk)


@login_required
def logout_view(request):
    """Log the user out and redirect them to the home page."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("home")
