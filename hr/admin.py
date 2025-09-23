from django.contrib import admin
from .models import Department, Employee, EmployeeCategory, ContractType, WorkLocation, Job

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("complete_name", "company", "manager", "active")
    list_filter = ("company", "active")
    search_fields = ("name", "complete_name")

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "department", "job", "manager", "active")
    list_filter = ("company", "department", "job", "active")
    search_fields = ("name", "work_email", "work_phone", "mobile_phone")
    filter_horizontal = ("categories",)

admin.site.register(EmployeeCategory)
admin.site.register(ContractType)
admin.site.register(WorkLocation)
@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "department", "no_of_employee", "expected_employees", "active")
    list_filter = ("company", "department", "active")
    search_fields = ("name",)
