from django.urls import path
from .views import tailwind_test, home, uploaddata
urlpatterns = [
    # ... other urls ...
    path('tailwind-test/', tailwind_test, name='tailwind_test'),
    path('home/', home, name='home'),
    path('upload/', uploaddata, name='uploaddata'),
]
