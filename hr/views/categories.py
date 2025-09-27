# hr/views/categories.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from ..models import EmployeeCategory
from ..forms import EmployeeCategoryForm

class CategoryListView(LoginRequiredMixin, ListView):
    model = EmployeeCategory
    template_name = "hr/categories/category_list.html"
    context_object_name = "categories"
    paginate_by = 20
    ordering = ("name",)

    def get_queryset(self):
        qs = super().get_queryset().order_by(*self.ordering)
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q)
        return qs

class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = EmployeeCategory
    form_class = EmployeeCategoryForm
    template_name = "hr/categories/category_form.html"
    success_url = reverse_lazy("hr:category_list")

class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = EmployeeCategory
    form_class = EmployeeCategoryForm
    template_name = "hr/categories/category_form.html"
    success_url = reverse_lazy("hr:category_list")

class CategoryDetailView(LoginRequiredMixin, DetailView):
    model = EmployeeCategory
    template_name = "hr/categories/category_detail.html"
    context_object_name = "category"

class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = EmployeeCategory
    template_name = "hr/categories/category_confirm_delete.html"
    success_url = reverse_lazy("hr:category_list")
