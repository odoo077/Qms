from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import User, Partner, Company, PartnerCategory, Currency

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "company", "active", "is_staff", "is_superuser")
    search_fields = ("email", "name")

@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ("display_name", "company_type", "type", "company", "active")
    search_fields = ("name", "email", "phone")
    list_filter = ("company_type", "type", "active")

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "currency", "active")
    search_fields = ("name", "vat", "company_registry")
    list_filter = ("active",)

admin.site.register(PartnerCategory)
admin.site.register(Currency)
