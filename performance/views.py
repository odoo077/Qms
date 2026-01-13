# performance/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages

from base.views import (
    BaseScopedListView,
    BaseScopedDetailView,
    BaseScopedCreateView,
    BaseScopedUpdateView,
    BaseScopedDeleteView,
    ConfirmDeleteMixin,
    apply_search_filters,
)

from . import models as m
from . import forms as f
from . import services as svc
from django import forms
from base.company_context import get_current_company_object
from base.models import Company
from hr.models import Employee
from django.db.models import Q


# ============================================================
# Evaluation Parameters
# ============================================================

class EvaluationParameterListView(LoginRequiredMixin, BaseScopedListView):
    model = m.EvaluationParameter
    template_name = "performance/evaluationparameter_list.html"
    paginate_by = 24

    def get_queryset(self):
        base_qs = super().get_queryset()
        qs = base_qs.order_by("name", "code")
        qs = apply_search_filters(
            self.request,
            qs,
            search_fields=["name", "code"],
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # بدون نظام صلاحيات: السماح بالزر طالما المستخدم مسجّل
        ctx["can_add_parameter"] = True
        return ctx


class EvaluationParameterCreateView(
    LoginRequiredMixin,
    BaseScopedCreateView,
):
    model = m.EvaluationParameter
    form_class = f.EvaluationParameterForm
    template_name = "performance/evaluationparameter_form.html"
    success_url = reverse_lazy("performance:parameter_list")


class EvaluationParameterUpdateView(
    LoginRequiredMixin,
    BaseScopedUpdateView,
):
    model = m.EvaluationParameter
    form_class = f.EvaluationParameterForm
    template_name = "performance/evaluationparameter_form.html"
    success_url = reverse_lazy("performance:parameter_list")


class EvaluationParameterDetailView(LoginRequiredMixin, BaseScopedDetailView):
    model = m.EvaluationParameter
    template_name = "performance/evaluationparameter_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # بدون صلاحيات: السماح دائمًا بعرض زر التعديل
        ctx["can_edit_object"] = True
        return ctx


class EvaluationParameterDeleteView(
    LoginRequiredMixin,
    ConfirmDeleteMixin,
    BaseScopedDeleteView,
):
    model = m.EvaluationParameter
    back_url_name = "performance:parameter_list"
    object_label_field = "name"














# ------------------------------------------------------------
# Evaluation Types (Configuration)
# ------------------------------------------------------------

class EvaluationTypeListView(LoginRequiredMixin, BaseScopedListView):
    """
    قائمة أنواع التقييم (Monthly / Quarterly ... إلخ)
    """
    model = m.EvaluationType
    template_name = "performance/evaluationtype_list.html"
    paginate_by = 25
    ordering = ["company", "sequence", "name"]

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.select_related("company")


class EvaluationTypeDetailView(LoginRequiredMixin, BaseScopedDetailView):
    """
    عرض نوع التقييم + خطوات الموافقات المرتبطة به.
    """
    model = m.EvaluationType
    template_name = "performance/evaluationtype_detail.html"

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.select_related("company").prefetch_related("approval_steps")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = ctx.get("object")
        steps = []
        if obj:
            steps = list(obj.approval_steps.filter(active=True).order_by("sequence"))
        ctx["steps"] = steps
        return ctx


class EvaluationTypeCreateView(
    LoginRequiredMixin,
    BaseScopedCreateView,
):
    """
    إنشاء نوع تقييم جديد.
    """
    model = m.EvaluationType
    form_class = f.EvaluationTypeForm
    template_name = "performance/evaluationtype_form.html"
    success_url = reverse_lazy("performance:evaluation_type_list")


class EvaluationTypeUpdateView(
    LoginRequiredMixin,
    BaseScopedUpdateView,
):
    """
    تعديل نوع تقييم.
    """
    model = m.EvaluationType
    form_class = f.EvaluationTypeForm
    template_name = "performance/evaluationtype_form.html"
    success_url = reverse_lazy("performance:evaluation_type_list")


class EvaluationTypeDeleteView(
    LoginRequiredMixin,
    ConfirmDeleteMixin,
    BaseScopedDeleteView,
):
    """
    حذف نوع تقييم.
    """
    model = m.EvaluationType
    back_url_name = "performance:evaluation_type_list"
    object_label_field = "name"


class EvaluationApprovalStepCreateView(
    LoginRequiredMixin,
    BaseScopedCreateView,
):
    """
    إنشاء خطوة موافقة جديدة لنوع تقييم معيّن.
    يتم تمرير evaluation_type عبر الـ URL (type_pk).
    """
    model = m.EvaluationApprovalStep
    form_class = f.EvaluationApprovalStepForm
    template_name = "performance/evaluationapprovalstep_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.evaluation_type = get_object_or_404(
            m.EvaluationType, pk=kwargs.get("type_pk")
        )
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial["evaluation_type"] = self.evaluation_type
        initial["company"] = self.evaluation_type.company
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # جعل الشركة ونوع التقييم ثابتين (غير قابلين للتغيير من الفورم)
        if "evaluation_type" in form.fields:
            form.fields["evaluation_type"].initial = self.evaluation_type
            form.fields["evaluation_type"].disabled = True
        if "company" in form.fields and self.evaluation_type.company_id:
            form.fields["company"].initial = self.evaluation_type.company
            form.fields["company"].disabled = True
        return form

    def form_valid(self, form):
        # ضمان ربط الخطوة بنفس الشركة ونفس نوع التقييم
        form.instance.evaluation_type = self.evaluation_type
        if not form.instance.company_id:
            form.instance.company = self.evaluation_type.company
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["evaluation_type"] = self.evaluation_type
        return ctx

    def get_success_url(self):
        return reverse_lazy(
            "performance:evaluation_type_detail",
            kwargs={"pk": self.evaluation_type.pk},
        )





















class EvaluationApprovalStepUpdateView(
    LoginRequiredMixin,
    BaseScopedUpdateView,
):
    """
    تعديل خطوة موافقة موجودة.
    """
    model = m.EvaluationApprovalStep
    form_class = f.EvaluationApprovalStepForm
    template_name = "performance/evaluationapprovalstep_form.html"

    def dispatch(self, request, *args, **kwargs):
        # نحصل على النوع من خلال الكائن نفسه لضمان التوافق
        self.evaluation_type = get_object_or_404(
            m.EvaluationType, pk=kwargs.get("type_pk")
        )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        # نقيّد الخطوات على نفس نوع التقييم
        qs = super().get_queryset()
        return qs.filter(evaluation_type=self.evaluation_type)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # تثبيت الحقول Company & EvaluationType
        if "evaluation_type" in form.fields:
            form.fields["evaluation_type"].disabled = True
        if "company" in form.fields:
            form.fields["company"].disabled = True
        return form

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["evaluation_type"] = self.evaluation_type
        return ctx

    def get_success_url(self):
        return reverse_lazy(
            "performance:evaluation_type_detail",
            kwargs={"pk": self.evaluation_type.pk},
        )


class EvaluationApprovalStepDeleteView(
    LoginRequiredMixin,
    BaseScopedDeleteView,
):
    """
    حذف خطوة موافقة.
    نستخدم confirm_delete.html العام، مع العودة إلى صفحة نوع التقييم.
    """
    model = m.EvaluationApprovalStep
    template_name = "partials/confirm_delete.html"

    def get_queryset(self):
        # نضمن أن الخطوة مرتبطة بنفس النوع الممرَّر في URL
        type_pk = self.kwargs.get("type_pk")
        return super().get_queryset().filter(evaluation_type_id=type_pk)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        step = ctx.get("object")
        etype_id = step.evaluation_type_id if step else None
        ctx["object_label"] = step.name if step else "Approval Step"
        if etype_id:
            ctx["back_url"] = reverse_lazy(
                "performance:evaluation_type_detail",
                kwargs={"pk": etype_id},
            )
        return ctx

    def get_success_url(self):
        etype_id = self.object.evaluation_type_id
        return reverse_lazy(
            "performance:evaluation_type_detail",
            kwargs={"pk": etype_id},
        )


# ------------------------------------------------------------
# Bulk Evaluation Creation Form (non-model)
# ------------------------------------------------------------
class EvaluationBulkCreateForm(forms.Form):
    company = forms.ModelChoiceField(
        queryset=Company.objects.none(),
        required=True,
        label="Company",
    )
    evaluation_type = forms.ModelChoiceField(
        queryset=m.EvaluationType.objects.none(),
        required=False,
        label="Evaluation Type",
        help_text="Optional. If set, all created evaluations will use this type.",
    )
    template = forms.ModelChoiceField(
        queryset=m.EvaluationTemplate.objects.none(),
        required=False,
        label="Template",
        help_text="Optional. If set, all created evaluations will use this template.",
    )
    date_start = forms.DateField(
        label="Start Date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_end = forms.DateField(
        label="End Date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    employees = forms.ModelMultipleChoiceField(
        queryset=Employee.objects.none(),
        required=True,
        label="Employees",
        widget=forms.SelectMultiple(
            attrs={
                "size": 12,
            }
        ),
        help_text="Select one or more employees to create evaluations for.",
    )

    def __init__(self, *args, **kwargs):
        """
        - تقييد الشركات حسب الشركة الحالية فقط.
        - عند اختيار الشركة نقيّد:
          - EvaluationType
          - EvaluationTemplate
          - Employees
        """
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # جميع الشركات (بدون ACL)
        self.fields["company"].queryset = Company.objects.all()

        # اختيار الشركة الحالية إن وُجدت
        current = get_current_company_object()
        if current:
            self.fields["company"].initial = current

        # تحديد الشركة المستخدمة لتصفية باقي الحقول
        company_id = None
        if self.is_bound:
            company_id = self.data.get("company") or self.initial.get("company")
        elif current:
            company_id = current.pk

        if company_id:
            self.fields["evaluation_type"].queryset = (
                m.EvaluationType.objects.filter(company_id=company_id, active=True)
                .order_by("sequence", "name")
            )
            self.fields["template"].queryset = (
                m.EvaluationTemplate.objects.filter(company_id=company_id, active=True)
                .order_by("name")
            )
            self.fields["employees"].queryset = (
                Employee.objects.filter(company_id=company_id, active=True)
                .order_by("name")
            )
        else:
            self.fields["evaluation_type"].queryset = m.EvaluationType.objects.none()
            self.fields["template"].queryset = m.EvaluationTemplate.objects.none()
            self.fields["employees"].queryset = Employee.objects.none()


















# ============================================================
# Evaluation Templates
# ============================================================

class EvaluationTemplateListView(LoginRequiredMixin, BaseScopedListView):
    model = m.EvaluationTemplate
    template_name = "performance/evaluationtemplate_list.html"
    paginate_by = 24

    def get_queryset(self):
        base_qs = super().get_queryset()
        qs = (
            base_qs.select_related("company")
            .prefetch_related("parameters")
            .order_by("name")
        )
        qs = apply_search_filters(
            self.request,
            qs,
            search_fields=["name", "company__name"],
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # زر الإضافة متاح للجميع (بدون صلاحيات)
        ctx["can_add_template"] = True
        return ctx


class EvaluationTemplateCreateView(
    LoginRequiredMixin,
    BaseScopedCreateView,
):
    model = m.EvaluationTemplate
    form_class = f.EvaluationTemplateForm
    template_name = "performance/evaluationtemplate_form.html"
    success_url = reverse_lazy("performance:template_list")


class EvaluationTemplateUpdateView(
    LoginRequiredMixin,
    BaseScopedUpdateView,
):
    model = m.EvaluationTemplate
    form_class = f.EvaluationTemplateForm
    template_name = "performance/evaluationtemplate_form.html"
    success_url = reverse_lazy("performance:template_list")


class EvaluationTemplateDetailView(LoginRequiredMixin, BaseScopedDetailView):
    model = m.EvaluationTemplate
    template_name = "performance/evaluationtemplate_detail.html"

    def get_queryset(self):
        base_qs = super().get_queryset()
        return base_qs.select_related("company").prefetch_related("parameters")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # السماح دائمًا بالتعديل (بدون ACL)
        ctx["can_edit_object"] = True
        return ctx


class EvaluationTemplateDeleteView(
    LoginRequiredMixin,
    ConfirmDeleteMixin,
    BaseScopedDeleteView,
):
    model = m.EvaluationTemplate
    back_url_name = "performance:template_list"
    object_label_field = "name"

























# ============================================================
# Evaluations
# ============================================================

class EvaluationListView(LoginRequiredMixin, BaseScopedListView):
    """
    قائمة التقييمات مع فلاتر احترافية:
    - Company / Employee / Evaluation Type / State / Period / Free text
    """
    model = m.Evaluation
    template_name = "performance/evaluation_list.html"
    paginate_by = 24

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("company", "employee", "evaluation_type", "template")
        )

        request = self.request
        company_id = request.GET.get("company") or None
        employee_id = request.GET.get("employee") or None
        eval_type_id = request.GET.get("type") or None
        state = request.GET.get("state") or None
        from_date = request.GET.get("from_date") or None
        to_date = request.GET.get("to_date") or None
        q = request.GET.get("q") or None

        if company_id:
            qs = qs.filter(company_id=company_id)
        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        if eval_type_id:
            qs = qs.filter(evaluation_type_id=eval_type_id)
        if state:
            qs = qs.filter(state=state)

        if from_date:
            qs = qs.filter(date_end__gte=from_date)
        if to_date:
            qs = qs.filter(date_start__lte=to_date)

        if q:
            qs = qs.filter(
                Q(employee__name__icontains=q)
                | Q(evaluation_type__name__icontains=q)
                | Q(template__name__icontains=q)
                | Q(overall_rating__icontains=q)
            )

        return qs.order_by("-date_end", "-id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        request = self.request
        company_id = request.GET.get("company") or ""
        employee_id = request.GET.get("employee") or ""
        eval_type_id = request.GET.get("type") or ""
        state = request.GET.get("state") or ""
        from_date = request.GET.get("from_date") or ""
        to_date = request.GET.get("to_date") or ""
        q = request.GET.get("q") or ""

        # بدون ACL: نعرض كل الشركات المتاحة عبر الـ scope
        companies = Company.objects.all()

        employees_qs = Employee.objects.filter(active=True)
        eval_types_qs = m.EvaluationType.objects.filter(active=True)

        if company_id:
            employees_qs = employees_qs.filter(company_id=company_id)
            eval_types_qs = eval_types_qs.filter(company_id=company_id)
        else:
            employees_qs = employees_qs.filter(company__in=companies)
            eval_types_qs = eval_types_qs.filter(company__in=companies)

        ctx.update(
            {
                "companies": companies.order_by("name"),
                "employees_filter": employees_qs.order_by("name"),
                "evaluation_types_filter": eval_types_qs.order_by("sequence", "name"),
                "states": m.Evaluation.STATE,
                "current_filters": {
                    "company": company_id,
                    "employee": employee_id,
                    "type": eval_type_id,
                    "state": state,
                    "from_date": from_date,
                    "to_date": to_date,
                    "q": q,
                },
            }
        )
        return ctx


class EvaluationCreateView(
    LoginRequiredMixin,
    BaseScopedCreateView,
):
    model = m.Evaluation
    form_class = f.EvaluationForm
    template_name = "performance/evaluation_form.html"
    success_url = reverse_lazy("performance:evaluation_list")


class EvaluationUpdateView(LoginRequiredMixin, BaseScopedUpdateView):
    model = m.Evaluation
    form_class = f.EvaluationForm
    template_name = "performance/evaluation_form.html"
    success_url = reverse_lazy("performance:evaluation_list")

    def get_queryset(self):
        base_qs = super().get_queryset()
        return base_qs.select_related("company", "employee", "template")


class EvaluationDetailView(LoginRequiredMixin, BaseScopedDetailView):
    model = m.Evaluation
    template_name = "performance/evaluation_detail.html"

    def get_queryset(self):
        base_qs = super().get_queryset()
        # نضيف evaluation_type و current_approver لتحسين الأداء في التفاصيل
        return base_qs.select_related(
            "company",
            "employee",
            "template",
            "evaluation_type",
            "current_approver",
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = ctx.get("object")

        # السماح دائمًا بالتعديل والحذف (بدون صلاحيات)
        ctx["can_edit_object"] = True
        ctx["can_delete_object"] = True

        # خطوات الـ Workflow
        steps = []
        if obj and obj.evaluation_type:
            steps = list(
                obj.evaluation_type.approval_steps.filter(active=True).order_by("sequence")
            )

        ctx["workflow_steps"] = steps
        ctx["current_step"] = obj.current_step if obj else 0
        ctx["current_approver"] = obj.current_approver if obj else None

        # يمكن تقديم التقييم دائمًا ما دام في draft
        ctx["can_submit"] = bool(obj and obj.state == "draft")

        # الموافقة/الرفض متاحة دائمًا (بدون صلاحيات)
        ctx["can_approve_step"] = True
        ctx["can_reject_step"] = True

        return ctx















class EvaluationDeleteView(
    LoginRequiredMixin,
    ConfirmDeleteMixin,
    BaseScopedDeleteView,
):
    model = m.Evaluation
    back_url_name = "performance:evaluation_list"
    object_label_field = "display_name"


# ------------------------------------------------------------
# My Evaluations (Employee self-service)
# ------------------------------------------------------------
class MyEvaluationListView(LoginRequiredMixin, BaseScopedListView):
    """
    قائمة التقييمات الخاصة بالمستخدم الحالي (الموظف المرتبط به).
    - أفضل ممارسة: الموظف لا يرى إلا تقييماته فقط.
    """
    model = m.Evaluation
    template_name = "performance/my_evaluations.html"
    paginate_by = 20

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("company", "employee", "evaluation_type", "template")
        )

        user = self.request.user
        # نحاول إيجاد الموظف المرتبط بالمستخدم
        employee = (
            Employee.objects.filter(user=user, active=True)
            .select_related("company")
            .first()
        )
        if not employee:
            # لا يوجد Employee مرتبط → لا توجد تقييمات
            return qs.none()

        return qs.filter(employee=employee).order_by("-date_end", "-id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["is_self_view"] = True
        return ctx


# ------------------------------------------------------------
# Evaluation Workflow Actions
# ------------------------------------------------------------

@login_required
def evaluation_submit_view(request, pk):
    """
    تقديم التقييم لأول مرة:
    - مسموح فقط إذا كان التقييم في حالة draft
    """
    evaluation = get_object_or_404(m.Evaluation, pk=pk)

    if evaluation.state != "draft":
        messages.warning(request, "لا يمكن تقديم هذا التقييم لأنه ليس في حالة مسودة.")
        return redirect("performance:evaluation_detail", pk=pk)

    svc.submit_evaluation(evaluation, request.user)
    messages.success(request, "تم تقديم التقييم وبدء سير الموافقات.")
    return redirect("performance:evaluation_detail", pk=pk)


@login_required
def evaluation_approve_step_view(request, pk):
    """
    اعتماد الخطوة الحالية في الـ Workflow.
    """
    evaluation = get_object_or_404(m.Evaluation, pk=pk)

    ok = svc.approve_step(evaluation, request.user)
    if not ok:
        messages.error(request, "تعذر اعتماد هذه الخطوة.")
        return redirect("performance:evaluation_detail", pk=pk)

    if evaluation.state == "approved":
        messages.success(request, "تم اعتماد التقييم نهائيًا.")
    else:
        messages.success(request, "تم اعتماد الخطوة والانتقال إلى الخطوة التالية.")

    return redirect("performance:evaluation_detail", pk=pk)


@login_required
def evaluation_reject_step_view(request, pk):
    """
    رفض الخطوة الحالية:
    - يعيد التقييم للخطوة السابقة حسب منطق reject_step في الموديل
    """
    evaluation = get_object_or_404(m.Evaluation, pk=pk)

    ok = svc.reject_step(evaluation, request.user)
    if not ok:
        messages.error(request, "تعذر رفض هذه الخطوة.")
        return redirect("performance:evaluation_detail", pk=pk)

    messages.success(request, "تمت إعادة التقييم إلى الخطوة السابقة.")
    return redirect("performance:evaluation_detail", pk=pk)

















# ------------------------------------------------------------
# Bulk Evaluation Creation View
# ------------------------------------------------------------
@login_required
def evaluation_bulk_create_view(request):
    """
    إنشاء تقييمات جماعية لمجموعة موظفين لنفس الفترة ونفس النوع/القالب.
    - يراعي UniqueConstraint (employee, date_start, date_end) باستخدام get_or_create
    - لا يضبط الـ workflow إلا بعد عملية submit (كما هو منطق أفضل الممارسات)
    """
    if request.method == "POST":
        form = EvaluationBulkCreateForm(request.POST, request=request)
        if form.is_valid():
            company = form.cleaned_data["company"]
            evaluation_type = form.cleaned_data.get("evaluation_type")
            template = form.cleaned_data.get("template")
            date_start = form.cleaned_data["date_start"]
            date_end = form.cleaned_data["date_end"]
            employees = form.cleaned_data["employees"]

            created_count = 0
            skipped_count = 0

            for emp in employees:
                obj, created = m.Evaluation.objects.get_or_create(
                    company=company,
                    employee=emp,
                    date_start=date_start,
                    date_end=date_end,
                    defaults={
                        "evaluation_type": evaluation_type,
                        "template": template,
                        # state يبقى default = draft
                    },
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1

            if created_count:
                messages.success(
                    request,
                    f"{created_count} evaluation(s) created successfully.",
                )
            if skipped_count:
                messages.info(
                    request,
                    f"{skipped_count} evaluation(s) already existed for the same period and were skipped.",
                )

            return redirect("performance:evaluation_list")
    else:
        form = EvaluationBulkCreateForm(request=request)

    return render(
        request,
        "performance/evaluation_bulk_create.html",
        {
            "form": form,
        },
    )


# ============================================================
# Objectives
# ============================================================

class ObjectiveListView(LoginRequiredMixin, BaseScopedListView):
    model = m.Objective
    template_name = "performance/objective_list.html"
    paginate_by = 24

    def get_queryset(self):
        base_qs = super().get_queryset()
        qs = (
            base_qs
            .select_related("target_employee", "target_department", "reviewer")
            .order_by("title")
        )
        qs = apply_search_filters(
            self.request,
            qs,
            search_fields=[
                "title",
                "code",
                "target_employee__name",
                "target_department__name",
            ],
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_objective"] = True
        return ctx


class ObjectiveCreateView(
    LoginRequiredMixin,
    BaseScopedCreateView,
):
    model = m.Objective
    form_class = f.ObjectiveForm
    template_name = "performance/objective_form.html"
    success_url = reverse_lazy("performance:objective_list")


class ObjectiveUpdateView(LoginRequiredMixin, BaseScopedUpdateView):
    model = m.Objective
    form_class = f.ObjectiveForm
    template_name = "performance/objective_form.html"
    success_url = reverse_lazy("performance:objective_list")


class ObjectiveDetailView(LoginRequiredMixin, BaseScopedDetailView):
    model = m.Objective
    template_name = "performance/objective_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_edit_object"] = True
        return ctx


class ObjectiveDeleteView(
    LoginRequiredMixin,
    ConfirmDeleteMixin,
    BaseScopedDeleteView,
):
    model = m.Objective
    back_url_name = "performance:objective_list"
    object_label_field = "title"


# ============================================================
# KPIs
# ============================================================

class KPIListView(LoginRequiredMixin, BaseScopedListView):
    model = m.KPI
    template_name = "performance/kpi_list.html"
    paginate_by = 24

    def get_queryset(self):
        base_qs = super().get_queryset()
        qs = base_qs.select_related("objective").order_by("name")
        qs = apply_search_filters(
            self.request,
            qs,
            search_fields=["name", "objective__title"],
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_kpi"] = True
        return ctx




class KPICreateView(
    LoginRequiredMixin,
    BaseScopedCreateView,
):
    model = m.KPI
    form_class = f.KPIForm
    template_name = "performance/kpi_form.html"
    success_url = reverse_lazy("performance:kpi_list")


class KPIUpdateView(LoginRequiredMixin, BaseScopedUpdateView):
    model = m.KPI
    form_class = f.KPIForm
    template_name = "performance/kpi_form.html"
    success_url = reverse_lazy("performance:kpi_list")


class KPIDetailView(LoginRequiredMixin, BaseScopedDetailView):
    model = m.KPI
    template_name = "performance/kpi_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_edit_object"] = True
        return ctx


class KPIDeleteView(
    LoginRequiredMixin,
    ConfirmDeleteMixin,
    BaseScopedDeleteView,
):
    model = m.KPI
    back_url_name = "performance:kpi_list"
    object_label_field = "name"


# ============================================================
# Tasks
# ============================================================


class TaskListView(LoginRequiredMixin, BaseScopedListView):
    model = m.Task
    template_name = "performance/task_list.html"
    paginate_by = 24

    def get_queryset(self):
        base_qs = super().get_queryset()
        qs = (
            base_qs
            .select_related("objective", "kpi", "assignee")
            .order_by("title")
        )
        qs = apply_search_filters(
            self.request,
            qs,
            search_fields=[
                "title",
                "objective__title",
                "kpi__name",
                "assignee__name",
            ],
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_add_task"] = True
        return ctx


class TaskCreateView(
    LoginRequiredMixin,
    BaseScopedCreateView,
):
    model = m.Task
    form_class = f.TaskForm
    template_name = "performance/task_form.html"
    success_url = reverse_lazy("performance:task_list")


class TaskUpdateView(LoginRequiredMixin, BaseScopedUpdateView):
    model = m.Task
    form_class = f.TaskForm
    template_name = "performance/task_form.html"
    success_url = reverse_lazy("performance:task_list")


class TaskDetailView(LoginRequiredMixin, BaseScopedDetailView):
    model = m.Task
    template_name = "performance/task_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_edit_object"] = True
        return ctx


class TaskDeleteView(
    LoginRequiredMixin,
    ConfirmDeleteMixin,
    BaseScopedDeleteView,
):
    model = m.Task
    back_url_name = "performance:task_list"
    object_label_field = "title"
