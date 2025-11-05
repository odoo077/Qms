# base/urls.py
from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views

from .views import (
    CompanySwitchView,
    PartnerListView, PartnerDetailView, PartnerCreateView, PartnerUpdateView,
    register_view, activate_view, activation_sent_view, activation_failed_view, resend_activation_view,
    login_view, logout_view, profile_view, edit_profile_view,
    password_change_view, password_change_done_view, HomeView, UserDetailView, UserListView, UserUpdateView,
    CompanyDetailView, CompanyCreateView, CompanyListView, CompanyUpdateView,
)


app_name = "base"

urlpatterns = [

    path("", HomeView.as_view(), name="home"),

    # Company
    path("company/switch/",   CompanySwitchView.as_view(),   name="company_switch"),

    # Partners
    path("partners/", PartnerListView.as_view(),   name="partner_list"),
    path("partners/new/", PartnerCreateView.as_view(), name="partner_create"),
    path("partners/<int:pk>/",      PartnerDetailView.as_view(), name="partner_detail"),
    path("partners/<int:pk>/edit/", PartnerUpdateView.as_view(), name="partner_edit"),

    # Users/Auth
    path("users/register/",            register_view,           name="register"),
    path("users/activate/<uidb64>/<token>/", activate_view,     name="activate"),
    path("users/activation-sent/",     activation_sent_view,    name="activation_sent"),
    path("users/activation-failed/",   activation_failed_view,  name="activation_failed"),
    path("users/resend-activation/",   resend_activation_view,  name="resend_activation"),

    path("users/login/",   login_view,  name="login"),
    path("users/logout/",  logout_view, name="logout"),

    path("users/profile/",      profile_view,      name="profile"),
    path("users/profile/edit/", edit_profile_view, name="edit_profile"),

    # Password change (logged-in)
    path("users/password-change/",       password_change_view,      name="password_change"),
    path("users/password-change/done/",  password_change_done_view, name="password_change_done"),

    # Password reset (built-ins)
    path(
        "users/password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="base/users/password_reset.html",
            email_template_name="base/users/emails/password_reset_email.txt",
            html_email_template_name="base/users/emails/password_reset_email.html",
            subject_template_name="base/users/emails/password_reset_subject.txt",
            success_url=reverse_lazy("base:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "users/password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="base/users/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "users/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="base/users/password_reset_confirm.html",
            success_url=reverse_lazy("base:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "users/reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="base/users/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),

    # Users
    path("users/", UserListView.as_view(), name="user_list"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="user_detail"),
    path("users/<int:pk>/edit/", UserUpdateView.as_view(), name="user_edit"),

    # Companies
    path("companies/", CompanyListView.as_view(), name="company_list"),
    path("companies/new/", CompanyCreateView.as_view(), name="company_create"),
    path("companies/<int:pk>/", CompanyDetailView.as_view(), name="company_detail"),
    path("companies/<int:pk>/edit/", CompanyUpdateView.as_view(), name="company_edit"),


]
