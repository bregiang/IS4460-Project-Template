from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group
from django.shortcuts import redirect, render

from .forms import CustomUserCreationForm, SkincareProfileForm
from .models import SkincareProfile


def home_page(request):
    """Render the landing page for the SkinIdentifier product."""
    return render(request, "home/home.html")


def skin_analysis_view(request):
    """Render the interactive skin analysis quiz and result experience."""
    return render(request, "home/skin_analysis.html")


def register_view(request):
    """Allow new users to create an account and select a role."""
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful. Welcome to SkinIdentifier.")
            return redirect("dashboard")
    else:
        form = CustomUserCreationForm()

    return render(request, "home/register.html", {"form": form})


def login_view(request):
    """Authenticate users with Django's built-in login form."""
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "You are now logged in.")
            return redirect("dashboard")
    else:
        form = AuthenticationForm()

    return render(request, "home/login.html", {"form": form})


@login_required
def dashboard_view(request):
    """Display a role-aware dashboard for the authenticated user."""
    user_groups = list(request.user.groups.values_list("name", flat=True))
    role = user_groups[0] if user_groups else "member"
    profile = SkincareProfile.objects.filter(user=request.user).first()
    return render(request, "home/dashboard.html", {"role": role, "profile": profile})


@login_required
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

    return render(request, "home/profile.html", {"form": form, "profile": profile})


@login_required
def logout_view(request):
    """Log the user out and redirect them to the home page."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("home")
