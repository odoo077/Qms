"""
URL configuration for Qms project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# Qms/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [

    # ضمّن جميع مسارات تطبيق base (partners/، users/، ...)
    path("", include(("base.urls", "base"), namespace="base")),

    path("base/", RedirectView.as_view(pattern_name="base:home", permanent=False)),
    # باقي التطبيقات
    path("employees/", include(("employees.urls", "employees"), namespace="employees")),
    # لوحة الإدارة
    path("admin/", admin.site.urls),
]

# Helpers أثناء التطوير
if settings.DEBUG:
    # Live reload (django_browser_reload)
    urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]

    # تقديم الملفات الثابتة وملفات الميديا في التطوير
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

