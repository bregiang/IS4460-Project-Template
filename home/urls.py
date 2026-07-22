from django.urls import path

from . import views

urlpatterns = [
    path("", views.home_page, name="home"),
    path("skin-analysis/", views.skin_analysis_view, name="skin_analysis"),
    path("about/", views.about_page, name="about"),
    path("privacy/", views.privacy_page, name="privacy"),
    path("contact/", views.contact_page, name="contact"),
    path("recommendations/", views.recommendations_page, name="recommendations"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("profile/", views.profile_view, name="profile"),
]
