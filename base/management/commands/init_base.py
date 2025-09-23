# base/management/commands/init_base.py
from __future__ import annotations

from typing import Any
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from django.apps import apps

# Import directly from concrete modules to avoid any circulars
from base.models.company import Currency, Company
from base.models.partner import Partner
from base.models.user import User


class Command(BaseCommand):
    help = "Initialize base data: currency, company, partner, and a superuser linked to both."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="admin@admin.iq",
                            help="Admin email (also the login/USERNAME_FIELD).")
        parser.add_argument("--password", default="admin",
                            help="Admin password.")
        parser.add_argument("--name", default="Administrator",
                            help="Admin display name.")
        parser.add_argument("--company", default="Your Company",
                            help="Default company name to create/use.")
        parser.add_argument("--currency-code", default="IQD",
                            help="Currency code (e.g., IQD, USD).")
        parser.add_argument("--currency-name", default="Iraqi Dinar",
                            help="Currency descriptive name.")
        parser.add_argument("--force", action="store_true",
                            help="Update/link even if records already exist.")

    def _assert_auth_user_model(self):
        # Ensure we’re using the custom user model (base.User)
        auth_user_model = settings.AUTH_USER_MODEL
        # Expected to be "base.User"
        if auth_user_model.lower() != "base.user":
            raise CommandError(
                f"AUTH_USER_MODEL is '{auth_user_model}', expected 'base.User'. "
                "Set AUTH_USER_MODEL='base.User' in settings.py before first migrate."
            )
        # also ensure the model is loaded
        model = apps.get_model(auth_user_model)
        if model is not User:
            raise CommandError(
                "AUTH_USER_MODEL points to a different class than base.models.user.User."
            )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any):
        self._assert_auth_user_model()

        email = options["email"].strip().lower()
        password = options["password"]
        admin_name = options["name"].strip()
        company_name = options["company"].strip()

        ccy_code = options["currency_code"].strip().upper()
        ccy_name = options["currency_name"].strip()
        force = options["force"]

        # 1) Currency
        currency, created_currency = Currency.objects.get_or_create(
            code=ccy_code,
            defaults={"name": ccy_name or ccy_code},
        )
        if not created_currency and ccy_name and force and currency.name != ccy_name:
            currency.name = ccy_name
            currency.save(update_fields=["name"])
        self.stdout.write(self.style.SUCCESS(
            f"Currency: {currency.code} ({'created' if created_currency else 'existing'})"
        ))

        # 2) Company
        company, created_company = Company.objects.get_or_create(
            name=company_name,
            defaults={"currency": currency},
        )
        if not created_company and force and company.currency_id != currency.id:
            company.currency = currency
            company.save(update_fields=["currency"])
        self.stdout.write(self.style.SUCCESS(
            f"Company: {company.name} ({'created' if created_company else 'existing'})"
        ))

        # 3) Partner (admin user’s card)
        # Try to reuse a partner with same email, or create a new one
        partner = Partner.objects.filter(email=email).first()
        if partner is None:
            partner = Partner.objects.create(
                name=admin_name or email,
                is_company=False,
                company=company,
                email=email,
                active=True,
            )
            partner_status = "created"
        else:
            # keep it active and ensure linked company if force
            if force:
                updates = {}
                if not partner.active:
                    partner.active = True
                    updates["active"] = True
                if partner.company_id != company.id:
                    partner.company = company
                    updates["company"] = company
                if updates:
                    partner.save()
            partner_status = "existing"
        self.stdout.write(self.style.SUCCESS(
            f"Partner: {partner.display_name} ({partner_status})"
        ))

        # 4) Superuser (Django staff + superuser), Odoo-style links
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_superuser(
                email=email,
                password=password,
                partner=partner,
                company=company,
                name=admin_name or email,
                is_staff=True,
            )
            user.companies.add(company)  # enforce default ∈ allowed
            user_status = "created"
        else:
            # Ensure linkage & permissions
            changed = False
            if force:
                if user.partner_id != partner.id:
                    user.partner = partner
                    changed = True
                if user.company_id != company.id:
                    user.company = company
                    changed = True
                if not user.companies.filter(pk=company.pk).exists():
                    user.companies.add(company)
                if not user.is_staff:
                    user.is_staff = True
                    changed = True
                if not user.is_superuser:
                    user.is_superuser = True
                    changed = True
                if password:
                    user.set_password(password)
                    changed = True
                if changed:
                    user.full_clean()
                    user.save()
            user_status = "existing"

        # Final echo
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("✔ Initialization complete"))
        self.stdout.write(f" Admin email: {email}")
        self.stdout.write(f" Company:     {company.name}")
        self.stdout.write(f" Currency:    {currency.code}")
        self.stdout.write(f" User:        {user.display_name} ({user_status})")
