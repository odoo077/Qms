# file: base/access.py

from django.contrib.auth import get_user_model
from django.apps import apps

Employee = apps.get_model("hr", "Employee")
Department = apps.get_model("hr", "Department")

User = get_user_model()


# ============================================================
# Helper functions
# ============================================================

def get_employee(user: User):
    """
    Retrieve the HR employee record linked to this user.
    """
    if not user or not user.is_authenticated:
        return None
    try:
        return Employee.objects.get(user=user)
    except Employee.DoesNotExist:
        return None


def user_is_hr_manager(user: User) -> bool:
    """
    HR Managers have full access on HR objects.
    """
    return user.groups.filter(name="HR Managers").exists()


def is_in_same_company(user: User, company_id):
    """
    Check if user belongs to the same company.
    user.company_ids = ManyToMany on User
    """
    if not user or not user.is_authenticated:
        return False
    if not company_id:
        return False
    return company_id in list(user.company_ids)


# ============================================================
# Employee & Department visibility helpers
# ============================================================

def is_manager_of(user: User, employee: Employee) -> bool:
    """
    True if user is direct manager of employee.
    """
    emp = get_employee(user)
    if not emp:
        return False
    return employee.manager_id == emp.id


def user_is_in_manager_chain(user: User, employee: Employee) -> bool:
    """
    True if user manages any ancestor manager of the employee.
    """
    emp = get_employee(user)
    if not emp:
        return False

    current = employee.manager
    while current:
        if current.id == emp.id:
            return True
        current = current.manager

    return False
