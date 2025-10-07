# base/views/__init__.py
# أعِد تصدير كل ما تريد استخدامه خارج الحزمة
from .company_views import CompanySwitchView
from .partner_views import PartnerListView, PartnerDetailView, PartnerCreateView, PartnerUpdateView
from .user_views import (
    register_view, activate_view, activation_sent_view, activation_failed_view, resend_activation_view,
    login_view, logout_view, profile_view, edit_profile_view,
    password_change_view, password_change_done_view,
)
from .dashboard import HomeView  # NEW

__all__ = [
    # company
    "CompanySwitchView",
    # partners
    "PartnerListView", "PartnerDetailView", "PartnerCreateView", "PartnerUpdateView",
    # users/auth
    "register_view", "activate_view", "activation_sent_view", "activation_failed_view", "resend_activation_view",
    "login_view", "logout_view", "profile_view", "edit_profile_view",
    "password_change_view", "password_change_done_view",
    # dashboards
    "HomeView",   # الجديد الذي سنربطه على الجذر
]
