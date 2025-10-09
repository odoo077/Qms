# skills/views/employee_skills.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.db.models import Q
from django.apps import apps

from skills.models import HrEmployeeSkill
from skills.forms import EmployeeSkillForm


class EmployeeSkillListView(LoginRequiredMixin, ListView):
    """
    قائمة مهارات الموظفين مع فلاتر:
    - q: بحث نصي في اسم الموظف/المهارة/النوع
    - employee, skill_type, skill
    - on_date: لإظهار النشط في تاريخ معيّن (افتراضيًا يعرض الكل)
    """
    model = HrEmployeeSkill
    template_name = "skills/employee_skills/employee_skill_list.html"
    context_object_name = "records"
    paginate_by = 20
    ordering = ("employee__name", "skill_type__name", "skill__name", "valid_from", "id")

    def get_queryset(self):
        qs = (HrEmployeeSkill.objects
              .select_related("employee", "skill_type", "skill", "skill_level")
              .order_by(*self.ordering))

        q = self.request.GET.get("q")
        emp = self.request.GET.get("employee")
        st = self.request.GET.get("skill_type")
        sk = self.request.GET.get("skill")
        on_date = self.request.GET.get("on_date")  # YYYY-MM-DD

        if q:
            qs = qs.filter(
                Q(employee__name__icontains=q)
                | Q(skill__name__icontains=q)
                | Q(skill_type__name__icontains=q)
                | Q(skill_level__name__icontains=q)
            )
        if emp:
            qs = qs.filter(employee_id=emp)
        if st:
            qs = qs.filter(skill_type_id=st)
        if sk:
            qs = qs.filter(skill_id=sk)
        if on_date:
            try:
                from datetime import datetime
                d = datetime.strptime(on_date, "%Y-%m-%d").date()
                qs = qs.filter(valid_from__lte=d).filter(Q(valid_to__isnull=True) | Q(valid_to__gte=d))
            except Exception:
                pass

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        Employee = apps.get_model("hr", "Employee")
        from skills.models import HrSkillType, HrSkill
        ctx["employees"] = Employee.objects.order_by("name")
        ctx["skill_types"] = HrSkillType.objects.order_by("name")
        ctx["skills"] = HrSkill.objects.order_by("skill_type__name", "name")
        ctx["page_title"] = "Employee Skills"
        return ctx


class EmployeeSkillCreateView(LoginRequiredMixin, CreateView):
    model = HrEmployeeSkill
    form_class = EmployeeSkillForm
    template_name = "skills/employee_skills/employee_skill_form.html"
    success_url = reverse_lazy("skills:employee_skill_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Add Employee Skill"
        return ctx


class EmployeeSkillUpdateView(LoginRequiredMixin, UpdateView):
    """
    مهم: EmployeeSkillForm.save() يُطبّق versioning:
    - لا يكتب In-place. يغلق القديم وينشئ سجلًا جديدًا.
    - UpdateView سيستبدل instance بالتسجيل الجديد (أعدنا form.instance).
    """
    model = HrEmployeeSkill
    form_class = EmployeeSkillForm
    template_name = "skills/employee_skills/employee_skill_form.html"
    success_url = reverse_lazy("skills:employee_skill_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Edit Employee Skill"
        return ctx


class EmployeeSkillDetailView(LoginRequiredMixin, DetailView):
    model = HrEmployeeSkill
    template_name = "skills/employee_skills/employee_skill_detail.html"
    context_object_name = "record"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        rec = self.object
        ctx["page_title"] = f"{rec.employee.name} · {rec.skill.name}"
        return ctx


class EmployeeSkillDeleteView(LoginRequiredMixin, DeleteView):
    model = HrEmployeeSkill
    template_name = "skills/employee_skills/employee_skill_confirm_delete.html"
    success_url = reverse_lazy("skills:employee_skill_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Delete Employee Skill"
        return ctx
