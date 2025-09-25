from django.shortcuts import render

# Create your views here.


def tailwind_test(request):
    return render(request, 'employees/tailwind_test.html')


def home(request):
    return render(request, 'employees/home.html')


def uploaddata(request):
    return render(request, 'employees/uploaddata.html')


def EmployeeProfile(request):
    return render(request, 'employees/e_profile.html')


def emp_dashboard(request):
    ctx = {
        "headcount": 123,
        "active_today": 108,
        "late_arrivals": 7,
        "pto_today": 4,
        "todays_attendance": [
            # dicts/objects with name, dept, check_in, status…
        ],
    }
    return render(request, "employees/emp_dashboard.html", ctx)
