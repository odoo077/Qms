from django.urls import path
from .views import tailwind_test, home, uploaddata, EmployeeProfile, emp_dashboard
urlpatterns = [
    # ... other urls ...
    path('tailwind-test/', tailwind_test, name='tailwind_test'),
    path('home/', home, name='home'),
    path('upload/', uploaddata, name='uploaddata'),
    path('eprofile/', EmployeeProfile, name='eprofile'),
    path('emp_dashboard/', emp_dashboard, name='emp_dashboard'),
]
