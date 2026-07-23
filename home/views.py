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
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from dotenv import load_dotenv

from .forms import (
    CustomUserCreationForm,
    InventoryItemForm,
    MessageForm,
    ProfessionalNoteForm,
    SkincareProfileForm,
)
from .models import InventoryItem, Message, SkincareProfile

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


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
                    return JsonResponse({"recommendation": text.strip(), "source": "gemini"})
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
            return JsonResponse({"recommendation": fallback, "source": "fallback", "error": raw_error_message, "friendly_error": friendly_error_message, "model": model})

    fallback = (
        f"For {profile_type} skin, start with a gentle cleanser, a lightweight moisturizer, and daily sunscreen. "
        f"If your goal is {product_goal}, choose fragrance-free formulas with barrier-friendly ingredients like ceramides, niacinamide, or hyaluronic acid. "
        f"{concern_hint if concern_hint else 'Keep the routine simple, patch test new products, and increase actives slowly.'}"
    )
    return JsonResponse({"recommendation": fallback, "source": "fallback", "model": model})


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
        patients = User.objects.exclude(pk=request.user.pk).filter(groups__name="user")
        return render(request, "home/dermatologist_dashboard.html", {"role": role, "profile": profile, "patients": patients})
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
    profile = get_object_or_404(SkincareProfile, user=request.user)
    return render(request, "home/skin_history.html", {"profile": profile, "role": get_user_role(request.user)})


@login_required(login_url="access_restricted")
@role_required("dermatologist")
def dermatologist_dashboard(request):
    """Provide a professional dashboard for dermatologists."""
    patients = User.objects.filter(groups__name="user")
    return render(request, "home/dermatologist_dashboard.html", {"patients": patients, "role": get_user_role(request.user)})


@login_required(login_url="access_restricted")
@role_required("dermatologist")
def dermatologist_patient_view(request, user_id):
    """Allow dermatologists to review a patient's skin profile and history."""
    patient = get_object_or_404(User, pk=user_id)
    profile = get_object_or_404(SkincareProfile, user=patient)
    messages_for_patient = Message.objects.filter(recipient=patient)
    if request.method == "POST":
        form = ProfessionalNoteForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Professional note saved.")
            return redirect("dermatologist_patient", user_id=patient.pk)
    else:
        form = ProfessionalNoteForm(instance=profile)
    return render(request, "home/dermatologist_patient.html", {"patient": patient, "profile": profile, "form": form, "messages_for_patient": messages_for_patient, "role": get_user_role(request.user)})


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


@login_required
def logout_view(request):
    """Log the user out and redirect them to the home page."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("home")
