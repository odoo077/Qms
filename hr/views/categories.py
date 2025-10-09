# hr/views/categories.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.db.models import Q

from ..models import EmployeeCategory
from ..forms import EmployeeCategoryForm


class CategoryListView(LoginRequiredMixin, ListView):
    """
    عرض قائمة تصنيفات الموظفين (Employee Categories)
    """
    model = EmployeeCategory
    template_name = "hr/categories/category_list.html"
    context_object_name = "categories"
    paginate_by = 20
    ordering = ("name",)

    def get_queryset(self):
        qs = EmployeeCategory.objects.order_by(*self.ordering)
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Employee Categories"
        return ctx


class CategoryCreateView(LoginRequiredMixin, CreateView):
    """
    إنشاء تصنيف جديد للموظفين.
    """
    model = EmployeeCategory
    form_class = EmployeeCategoryForm
    template_name = "hr/categories/category_form.html"
    success_url = reverse_lazy("hr:category_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Create Category"
        return ctx


class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    """
    تعديل تصنيف موظفين موجود.
    """
    model = EmployeeCategory
    form_class = EmployeeCategoryForm
    template_name = "hr/categories/category_form.html"
    success_url = reverse_lazy("hr:category_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Edit Category"
        return ctx


class CategoryDetailView(LoginRequiredMixin, DetailView):
    """
    عرض تفاصيل تصنيف الموظفين.
    """
    model = EmployeeCategory
    template_name = "hr/categories/category_detail.html"
    context_object_name = "category"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        category = self.object
        ctx["page_title"] = f"Category: {category.name}"
        return ctx


class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    """
    حذف تصنيف موظفين.
    """
    model = EmployeeCategory
    template_name = "hr/categories/category_confirm_delete.html"
    success_url = reverse_lazy("hr:category_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Delete Category"
        return ctx
