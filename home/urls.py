from django.urls import path

from . import views

urlpatterns = [
    path("", views.home_page, name="home"),
    path("access-restricted/", views.access_restricted_view, name="access_restricted"),
    path("skin-analysis/", views.skin_analysis_view, name="skin_analysis"),
    path("ai-recommendation/", views.generate_ai_recommendation, name="generate_ai_recommendation"),
    path("about/", views.about_page, name="about"),
    path("privacy/", views.privacy_page, name="privacy"),
    path("contact/", views.contact_page, name="contact"),
    path("recommendations/", views.recommendations_page, name="recommendations"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("profile/", views.profile_view, name="profile"),
    path("skin-history/", views.skin_history_view, name="skin_history"),
    path("dermatologist-dashboard/", views.dermatologist_dashboard, name="dermatologist_dashboard"),
    path("dermatologist-patient/<int:user_id>/", views.dermatologist_patient_view, name="dermatologist_patient"),
    path("create-profile/<int:user_id>/", views.create_profile_for_user, name="create_profile_for_user"),
    path("dermatologist-messages/", views.dermatologist_messages, name="dermatologist_messages"),
    path("send-message/<int:user_id>/", views.send_message_to_patient, name="send_message"),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("inventory-management/", views.inventory_management, name="inventory_management"),
    path("messages/", views.user_messages, name="user_messages"),
]
