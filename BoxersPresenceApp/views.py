# ===== BATTERY TESTS =====
import io
from datetime import date
from datetime import date as Date

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.http import HttpResponseBadRequest, JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, UpdateView, DeleteView, FormView, ListView, DetailView, CreateView
from django.views import View
from django.urls import reverse_lazy, reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from .models import Boxer, BatteryTest, TestResult, Attendance, HeartRate, Weight
from .forms import BatteryTestForm, PhaseSelectForm, BoxerAndTestSelectForm, BoxerForm, HeartRateQuickForm, \
    WeightQuickForm


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Always add both forms
        ctx["hr_form"] = HeartRateQuickForm(user=self.request.user)
        ctx["weight_form"] = WeightQuickForm(user=self.request.user)
        # DEBUG: prove this exact class ran
        ctx["dbg_view"] = f"{self.__class__.__module__}.{self.__class__.__name__}"
        ctx["dbg_has_weight_form"] = "yes" if "weight_form" in ctx else "no"
        return ctx
class RegisterView(FormView):
    template_name = 'register.html'
    form_class = UserCreationForm
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)

class BoxerListView(LoginRequiredMixin, ListView):
    template_name = 'boxer_list.html'
    context_object_name = 'boxers'

    def get_queryset(self):
        return Boxer.objects.filter(coach=self.request.user).order_by('name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = BoxerForm()  # Add empty form
        return ctx

    def post(self, request, *args, **kwargs):
        form = BoxerForm(request.POST)
        if form.is_valid():
            boxer = form.save(commit=False)
            boxer.coach = request.user
            boxer.save()
            return redirect('boxer_list')
        # If form is invalid, re-render with errors
        return self.render_to_response(self.get_context_data(form=form))

class BoxerCreateView(LoginRequiredMixin, CreateView):
    model = Boxer
    form_class = BoxerForm
    template_name = 'boxer_form.html'
    success_url = reverse_lazy('boxer_list')

    def form_valid(self, form):
        form.instance.coach = self.request.user
        return super().form_valid(form)

class TestsListView(LoginRequiredMixin, TemplateView):
    """List tests for this coach and create a new one."""
    template_name = 'tests_list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['tests'] = BatteryTest.objects.filter(coach=self.request.user).order_by('display_order', 'name')
        ctx['form'] = BatteryTestForm()
        return ctx

    def post(self, request, *args, **kwargs):
        form = BatteryTestForm(request.POST)
        if form.is_valid():
            test = form.save(commit=False)
            test.coach = request.user
            test.save()
            return redirect('tests_list')
        tests = BatteryTest.objects.filter(coach=request.user).order_by('display_order', 'name')
        return render(request, self.template_name, {'tests': tests, 'form': form})


class TestUpdateView(LoginRequiredMixin, UpdateView):
    model = BatteryTest
    form_class = BatteryTestForm
    template_name = 'test_edit.html'
    success_url = reverse_lazy('tests_list')

    def get_queryset(self):
        return BatteryTest.objects.filter(coach=self.request.user)


class TestDeleteView(LoginRequiredMixin, DeleteView):
    model = BatteryTest
    template_name = 'test_confirm_delete.html'
    success_url = reverse_lazy('tests_list')

    def get_queryset(self):
        return BatteryTest.objects.filter(coach=self.request.user)


# ===== RESULTS MATRIX (phase-aware) =====
class ResultsMatrixView(LoginRequiredMixin, TemplateView):
    template_name = 'tests_results.html'

    def current_phase(self):
        return self.request.GET.get('phase') or TestResult.PHASE_PRE

    def get(self, request, *args, **kwargs):
        phase = self.current_phase()
        tests = BatteryTest.objects.filter(coach=request.user).order_by('display_order', 'name')
        boxers = Boxer.objects.filter(coach=request.user).order_by('name')
        results = {
            (r.boxer_id, r.test_id): r
            for r in TestResult.objects.filter(
                boxer__coach=request.user, test__coach=request.user, phase=phase
            )
        }
        return render(request, self.template_name, {
            'phase_form': PhaseSelectForm(initial={'phase': phase}),
            'phase': phase,
            'tests': tests,
            'boxers': boxers,
            'results': results,
        })

    def post(self, request, *args, **kwargs):
        # Save All for selected phase
        phase = request.GET.get('phase') or request.POST.get('phase') or TestResult.PHASE_PRE
        tests = BatteryTest.objects.filter(coach=request.user)
        boxers = Boxer.objects.filter(coach=request.user)

        for b in boxers:
            for t in tests:
                prefix = f"r-{b.id}-{t.id}-"
                v1 = request.POST.get(prefix + "value1")
                v2 = request.POST.get(prefix + "value2")
                v3 = request.POST.get(prefix + "value3")
                notes = (request.POST.get(prefix + "notes") or "").strip()
                if all(x in (None, '') for x in (v1, v2, v3, notes)):
                    continue
                obj, _ = TestResult.objects.get_or_create(boxer=b, test=t, phase=phase)
                obj.value1, obj.value2, obj.value3 = v1 or None, v2 or None, v3 or None
                obj.notes = notes
                obj.save()

        return redirect(f"{reverse_lazy('tests_results')}?phase={phase}")


class ResultsCellSaveView(LoginRequiredMixin, View):
    """Save a single (boxer,test) cell for the selected phase."""
    def post(self, request, *args, **kwargs):
        phase = request.GET.get('phase') or request.POST.get('phase') or TestResult.PHASE_PRE
        boxer_id = request.GET.get('b') or request.POST.get('boxer_id')
        test_id  = request.GET.get('t') or request.POST.get('test_id')

        try:
            boxer_id, test_id = int(boxer_id), int(test_id)
        except (TypeError, ValueError):
            return redirect(f"{reverse_lazy('tests_results')}?phase={phase}")

        boxer = get_object_or_404(Boxer, id=boxer_id, coach=request.user)
        test  = get_object_or_404(BatteryTest, id=test_id, coach=request.user)

        prefix = f"r-{boxer_id}-{test_id}-"
        v1 = request.POST.get(prefix + "value1")
        v2 = request.POST.get(prefix + "value2")
        v3 = request.POST.get(prefix + "value3")
        notes = (request.POST.get(prefix + "notes") or "").strip()

        obj, _ = TestResult.objects.get_or_create(boxer=boxer, test=test, phase=phase)
        obj.value1, obj.value2, obj.value3 = v1 or None, v2 or None, v3 or None
        obj.notes = notes
        obj.save()

        return redirect(f"{reverse_lazy('tests_results')}?phase={phase}")


# ===== ONE BOXER (not phase-specific; keep simple) =====
class BoxerTestsView(LoginRequiredMixin, TemplateView):
    template_name = 'boxer_tests.html'

    def get(self, request, boxer_id, *args, **kwargs):
        boxer = get_object_or_404(Boxer, id=boxer_id, coach=request.user)
        tests = BatteryTest.objects.filter(coach=request.user).order_by('display_order', 'name')
        results = {r.test_id: r for r in TestResult.objects.filter(boxer=boxer)}
        return render(request, self.template_name, {'boxer': boxer, 'tests': tests, 'results': results})

    def post(self, request, boxer_id, *args, **kwargs):
        boxer = get_object_or_404(Boxer, id=boxer_id, coach=request.user)
        tests = BatteryTest.objects.filter(coach=request.user).order_by('display_order', 'name')
        for test in tests:
            prefix = f"r-{test.id}-"
            v1 = request.POST.get(prefix + "value1")
            v2 = request.POST.get(prefix + "value2")
            v3 = request.POST.get(prefix + "value3")
            notes = (request.POST.get(prefix + "notes") or "").strip()
            if all(x in (None, '') for x in (v1, v2, v3, notes)):
                continue
            obj, _ = TestResult.objects.get_or_create(boxer=boxer, test=test)
            obj.value1, obj.value2, obj.value3 = v1 or None, v2 or None, v3 or None
            obj.notes = notes
            obj.save()
        return redirect('boxer_tests', boxer_id=boxer.id)


# ===== SUMMARY (not phase-specific) =====
class BoxerResultsSummaryView(LoginRequiredMixin, TemplateView):
    template_name = 'tests_summary.html'

    def current_phase(self):
        return self.request.GET.get('phase') or TestResult.PHASE_PRE

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        phase = self.current_phase()

        tests  = list(BatteryTest.objects
                      .filter(coach=self.request.user)
                      .order_by('display_order', 'name'))
        boxers = list(Boxer.objects
                      .filter(coach=self.request.user)
                      .order_by('name'))

        # Only results for the selected phase
        results_map = {
            (r.boxer_id, r.test_id): r
            for r in TestResult.objects.filter(
                boxer__coach=self.request.user,
                test__coach=self.request.user,
                phase=phase
            )
        }

        rows = []
        for b in boxers:
            cells = [results_map.get((b.id, t.id)) for t in tests]
            rows.append({"boxer": b, "cells": cells})

        ctx.update({
            "phase": phase,
            "phase_form": PhaseSelectForm(initial={"phase": phase}),
            "tests": tests,
            "rows": rows,
        })
        return ctx


# ===== MANAGE BOXERS (boxer + test, show best per phase + improvement) =====
class BoxerPerformanceView(LoginRequiredMixin, FormView):
    template_name = 'tests_manage_boxers.html'
    form_class = BoxerAndTestSelectForm
    success_url = reverse_lazy('tests_manage_boxers')

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw['user'] = self.request.user
        return kw

    def form_valid(self, form):
        boxer = form.cleaned_data['boxer']
        test  = form.cleaned_data['test']

        def best_for(phase):
            tr = TestResult.objects.filter(boxer=boxer, test=test, phase=phase).first()
            if not tr:
                return None
            vals = [v for v in (tr.value1, tr.value2, tr.value3) if v is not None]
            if not vals:
                return None
            unit = (test.unit or '').strip().lower()
            return min(vals) if unit == 's' else max(vals)

        pre    = best_for(TestResult.PHASE_PRE)
        mid    = best_for(TestResult.PHASE_MID)
        before = best_for(TestResult.PHASE_BEFORE)

        improvement_text = None
        if pre is not None and before is not None:
            unit = (test.unit or '').strip().lower()
            if unit == 's':
                diff = pre - before      # positive = improved (faster)
                improved = diff > 0
            else:
                diff = before - pre      # positive = improved (greater)
                improved = diff > 0
            if diff == 0:
                improvement_text = f"{boxer.name} has no change before the tournament."
            elif improved:
                improvement_text = f"{boxer.name} has improved by {abs(diff)} {test.unit} before the tournament."
            else:
                improvement_text = f"{boxer.name} is now worse by {abs(diff)} {test.unit}."

        ctx = self.get_context_data(
            form=form, boxer=boxer, test=test,
            pre=pre, mid=mid, before=before,
            improvement_text=improvement_text
        )
        return self.render_to_response(ctx)


# ===== DELETE BOXER =====

@login_required
@require_POST
def delete_boxer(request, pk):
    if request.user.is_superuser:
        qs = Boxer.objects.all()
    else:
        qs = Boxer.objects.filter(coach=request.user)

    boxer = get_object_or_404(qs, pk=pk)
    name = boxer.name
    boxer.delete()
    messages.success(request, f"Deleted boxer: {name}")
    return redirect("boxer_list")

class AttendanceListView(LoginRequiredMixin, TemplateView):
    template_name = 'attendance_list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['boxers'] = Boxer.objects.filter(coach=self.request.user).order_by('name')
        ctx['attendance_records'] = Attendance.objects.filter(
            boxer__coach=self.request.user
        ).order_by('-date')
        return ctx

class MarkAttendanceView(LoginRequiredMixin, TemplateView):
    template_name = 'mark_attendance.html'

    def get(self, request, *args, **kwargs):
        boxers = Boxer.objects.filter(coach=request.user).order_by('name')
        return render(request, self.template_name, {
            'boxers': boxers,
            'today': timezone.now().date(),
        })

    def post(self, request, *args, **kwargs):
        # date
        date_str = (request.POST.get('date') or '').strip()
        try:
            att_date = date.fromisoformat(date_str) if date_str else timezone.now().date()
        except ValueError:
            att_date = timezone.now().date()

        # how many rows came from the form
        try:
            total = int(request.POST.get('total_boxers', '0'))
        except ValueError:
            total = 0

        saved = 0
        for i in range(1, total + 1):
            boxer_id = request.POST.get(f'boxer_id_{i}')
            attendance = request.POST.get(f'attendance_{i}')  # "Present" or "Absent"
            excused = request.POST.get(f'excused_{i}') == 'on'

            if not boxer_id or not attendance:
                continue  # skip incomplete rows

            # make sure this boxer belongs to the current coach
            boxer = get_object_or_404(Boxer, id=boxer_id, coach=request.user)

            Attendance.objects.create(
                boxer=boxer,
                date=att_date,
                is_present=(attendance == 'Present'),
                is_excused=(attendance != 'Present' and excused),
            )
            saved += 1

        messages.success(request, f"Saved {saved} attendance record(s) for {att_date}.")
        return redirect('attendance_list')


@login_required
def attendance_by_date(request):
    # read ?date=YYYY-MM-DD; default to today if missing/invalid
    q = (request.GET.get("date") or "").strip()
    try:
        selected = Date.fromisoformat(q) if q else timezone.now().date()
    except ValueError:
        selected = timezone.now().date()

    records = (
        Attendance.objects
        .filter(boxer__coach=request.user, date=selected)
        .select_related("boxer")
        .order_by("boxer__name")
    )

    return render(request, "attendance_by_date.html", {
        "date": selected,          # for display
        "date_value": selected.isoformat(),  # for input value
        "records": records,
    })
@login_required
@require_POST
def delete_attendance(request, attendance_id):
    record = get_object_or_404(Attendance, id=attendance_id, boxer__coach=request.user)
    record.delete()
    messages.success(request, "Attendance record deleted.")
    return redirect('attendance_list')

class BoxerReportView(LoginRequiredMixin, DetailView):
    model = Boxer
    template_name = 'boxer_report.html'
    context_object_name = 'boxer'
    pk_url_kwarg = 'boxer_id'

    def get_queryset(self):
        # Only allow the logged-in coach to access their own boxers
        return Boxer.objects.filter(coach=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        boxer = ctx['boxer']

        records = (Attendance.objects
                   .filter(boxer=boxer)
                   .order_by('-date'))

        total = records.count()
        present = records.filter(is_present=True).count()
        absent = total - present
        excused = records.filter(is_present=False, is_excused=True).count()
        unexcused = records.filter(is_present=False, is_excused=False).count()

        def pct(part, whole):
            return round((part / whole) * 100, 2) if whole else 0

        ctx.update({
            'records': records,
            'total': total,
            'present_pct': pct(present, total),
            'absent_pct': pct(absent, total),
            'excused_pct': pct(excused, absent),
            'unexcused_pct': pct(unexcused, absent),
        })
        return ctx

@require_POST
@login_required
def add_boxer(request):
    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Please enter a boxer name.")
        return redirect(request.META.get("HTTP_REFERER", "boxer_list"))
    Boxer.objects.create(name=name, coach=request.user)
    messages.success(request, f"Added boxer “{name}”.")
    return redirect("boxer_list")


@login_required
@require_POST
def summary_result_save(request):
    # Parse required ids + phase
    try:
        boxer_id = int(request.POST.get('boxer_id'))
        test_id  = int(request.POST.get('test_id'))
        phase    = request.POST.get('phase') or TestResult.PHASE_PRE
    except (TypeError, ValueError):
        return HttpResponseBadRequest("Invalid parameters")

    # Ownership checks
    boxer = get_object_or_404(Boxer, id=boxer_id, coach=request.user)
    test  = get_object_or_404(BatteryTest, id=test_id, coach=request.user)

    # Parse optional numeric fields
    def parse_val(name):
        raw = (request.POST.get(name) or '').strip()
        if raw == '':
            return None
        try:
            return float(raw)
        except ValueError:
            raise ValidationError(f"{name} must be a number or blank.")

    notes = (request.POST.get('notes') or '').strip()
    try:
        v1 = parse_val('value1')
        v2 = parse_val('value2')
        v3 = parse_val('value3')
    except ValidationError as e:
        messages.error(request, str(e))
        return redirect(request.META.get('HTTP_REFERER', reverse('tests_summary')) + f'?phase={phase}')

    # Create/update and save
    obj, created = TestResult.objects.get_or_create(boxer=boxer, test=test, phase=phase)
    obj.value1, obj.value2, obj.value3, obj.notes = v1, v2, v3, notes
    obj.save()

    messages.success(request, "Result saved.")
    return redirect(reverse('tests_summary') + f'?phase={phase}')

@login_required
@require_POST
def summary_result_delete(request):
    try:
        boxer_id = int(request.POST.get('boxer_id'))
        test_id  = int(request.POST.get('test_id'))
        phase    = (request.POST.get('phase') or TestResult.PHASE_PRE)
    except Exception:
        return HttpResponseBadRequest("Invalid parameters")

    boxer = get_object_or_404(Boxer, id=boxer_id, coach=request.user)
    test  = get_object_or_404(BatteryTest, id=test_id, coach=request.user)

    TestResult.objects.filter(boxer=boxer, test=test, phase=phase).delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})

    messages.success(request, "Result deleted.")
    return redirect(reverse('tests_summary') + f'?phase={phase}')


class TestResultEditView(LoginRequiredMixin, TemplateView):
    """Tiny page to edit a single cell (useful if you don't want inline inputs)."""
    template_name = 'tests_result_edit.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        request = self.request
        boxer_id = int(request.GET.get('boxer'))
        test_id  = int(request.GET.get('test'))
        phase    = request.GET.get('phase') or TestResult.PHASE_PRE
        boxer = get_object_or_404(Boxer, id=boxer_id, coach=request.user)
        test  = get_object_or_404(BatteryTest, id=test_id, coach=request.user)
        result = TestResult.objects.filter(boxer=boxer, test=test, phase=phase).first()
        ctx.update({'boxer': boxer, 'test': test, 'phase': phase, 'result': result})
        return ctx

    def post(self, request, *args, **kwargs):
        # Reuse the save logic (handles both JSON and regular form posts)
        return summary_result_save(request)

@login_required
def record_heart_rate(request):
    if request.method != "POST":
        return redirect("home")

    form = HeartRateQuickForm(request.POST, user=request.user)
    if not form.is_valid():
        messages.error(request, "Please correct the heart rate form.")
        return redirect("home")

    boxer = form.cleaned_data["boxer"]
    # safety: ensure the boxer belongs to the logged-in coach
    boxer = get_object_or_404(Boxer, id=boxer.id, coach=request.user)

    phase = form.cleaned_data["phase"]
    bpm = form.cleaned_data["bpm"]
    measured_at = form.cleaned_data["measured_at"] or timezone.now().date()

    obj, created = HeartRate.objects.get_or_create(
        boxer=boxer, phase=phase,
        defaults={"bpm": bpm, "measured_at": measured_at}
    )
    if not created:
        obj.bpm = bpm
        obj.measured_at = measured_at
        obj.save()

    messages.success(request, f"Saved {boxer.name} – {dict(TestResult.PHASE_CHOICES).get(phase, phase)}: {bpm} bpm.")
    return redirect("home")


class HeartRateSummaryView(LoginRequiredMixin, TemplateView):
    template_name = 'heart_rate_summary.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Load boxers for this coach
        boxers = list(Boxer.objects.filter(coach=self.request.user).order_by('name'))

        # Load heart rates for this coach (all phases)
        hrs = HeartRate.objects.filter(boxer__coach=self.request.user)

        # Build a fast lookup: {(boxer_id, phase): HeartRate}
        hr_map = {(hr.boxer_id, hr.phase): hr for hr in hrs}

        # Build rows the template can render without filters
        rows = []
        for b in boxers:
            rows.append({
                "boxer": b,
                "pre":    hr_map.get((b.id, TestResult.PHASE_PRE)),
                "mid":    hr_map.get((b.id, TestResult.PHASE_MID)),
                "before": hr_map.get((b.id, TestResult.PHASE_BEFORE)),
            })

        ctx.update({"rows": rows})
        return ctx

class HeartRateDetailView(LoginRequiredMixin, TemplateView):
    template_name = "heart_rate_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        boxer = get_object_or_404(Boxer, id=self.kwargs["boxer_id"], coach=self.request.user)
        hrs = { (hr.phase): hr for hr in HeartRate.objects.filter(boxer=boxer) }
        ctx.update({
            "boxer": boxer,
            "pre":    hrs.get(TestResult.PHASE_PRE),
            "mid":    hrs.get(TestResult.PHASE_MID),
            "before": hrs.get(TestResult.PHASE_BEFORE),
        })
        return ctx

@login_required
def record_weight(request):
    if request.method != "POST":
        return redirect("home")

    form = WeightQuickForm(request.POST, user=request.user)
    if not form.is_valid():
        messages.error(request, "Please correct the weight form.")
        return redirect("home")

    boxer = get_object_or_404(Boxer, id=form.cleaned_data["boxer"].id, coach=request.user)
    phase = form.cleaned_data["phase"]
    kg = form.cleaned_data["kg"]
    expected_kg = form.cleaned_data.get("expected_kg")
    measured_at = form.cleaned_data.get("measured_at") or timezone.now().date()

    obj, created = Weight.objects.get_or_create(
        boxer=boxer, phase=phase,
        defaults={"kg": kg, "expected_kg": expected_kg, "measured_at": measured_at}
    )
    if not created:
        obj.kg = kg
        obj.expected_kg = expected_kg
        obj.measured_at = measured_at
        obj.save()

    phase_label = dict(TestResult.PHASE_CHOICES).get(phase, phase)
    messages.success(request, f"Saved {boxer.name} — {phase_label}: {kg} kg (expected: {expected_kg or 'n/a'}).")
    return redirect("home")

class WeightSummaryView(LoginRequiredMixin, TemplateView):
    template_name = 'weight_summary.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        boxers = list(Boxer.objects.filter(coach=self.request.user).order_by('name'))
        weights = Weight.objects.filter(boxer__coach=self.request.user)
        wmap = {(w.boxer_id, w.phase): w for w in weights}
        rows = []
        for b in boxers:
            rows.append({
                "boxer": b,
                "pre":    wmap.get((b.id, TestResult.PHASE_PRE)),
                "mid":    wmap.get((b.id, TestResult.PHASE_MID)),
                "before": wmap.get((b.id, TestResult.PHASE_BEFORE)),
            })
        ctx["rows"] = rows
        return ctx

class WeightDetailView(LoginRequiredMixin, TemplateView):
    template_name = "weight_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        boxer = get_object_or_404(Boxer, id=self.kwargs["boxer_id"], coach=self.request.user)
        weights = {w.phase: w for w in Weight.objects.filter(boxer=boxer)}
        ctx.update({
            "boxer": boxer,
            "pre":    weights.get(TestResult.PHASE_PRE),
            "mid":    weights.get(TestResult.PHASE_MID),
            "before": weights.get(TestResult.PHASE_BEFORE),
        })
        return ctx

class TestRankingView(LoginRequiredMixin, TemplateView):
    template_name = "tests_rankings.html"

    def get_tests(self):
        return list(BatteryTest.objects
                    .filter(coach=self.request.user)
                    .order_by("display_order", "name"))

    def get_selected_test(self, tests):
        tid = self.kwargs.get("test_id")
        if tid:
            return get_object_or_404(BatteryTest, id=tid, coach=self.request.user)
        return tests[0] if tests else None

    def get_phase_choices(self):
        # [('all','All phases'), ('pre','Pre'), ('mid','Mid'), ('before','Before tournament'), ...]
        return [('all', 'All phases')] + list(TestResult.PHASE_CHOICES)

    def get_selected_phase(self):
        phase = self.request.GET.get("phase", "all")
        allowed = {k for k, _ in self.get_phase_choices()}
        return phase if phase in allowed else "all"

    @staticmethod
    def lower_is_better(unit: str) -> bool:
        unit = (unit or "").strip().lower()
        return unit in {"s", "sec", "secs", "second", "seconds", "ms", "min", "mins", "minute", "minutes"}

    def get(self, request, *args, **kwargs):
        tests = self.get_tests()
        selected_test = self.get_selected_test(tests)
        selected_phase = self.get_selected_phase()
        phase_map = dict(TestResult.PHASE_CHOICES)

        rows = []
        if selected_test:
            qs = (TestResult.objects
                  .filter(test=selected_test, boxer__coach=request.user)
                  .select_related("boxer"))

            # Filter by phase if a specific one is chosen
            if selected_phase != "all":
                qs = qs.filter(phase=selected_phase)

            best_map = {}  # boxer_id -> {"boxer": Boxer, "best": Decimal, "phase": str}
            lower_better = self.lower_is_better(selected_test.unit)

            def better(a, b):
                if a is None: return b
                if b is None: return a
                return min(a, b) if lower_better else max(a, b)

            for r in qs:
                for val in (r.value1, r.value2, r.value3):
                    if val is None:
                        continue
                    cur = best_map.get(r.boxer_id)
                    if not cur:
                        best_map[r.boxer_id] = {"boxer": r.boxer, "best": val, "phase": r.phase}
                    else:
                        new_best = better(cur["best"], val)
                        if new_best != cur["best"]:
                            cur["best"] = new_best
                            cur["phase"] = r.phase

            rows = list(best_map.values())
            rows.sort(key=lambda x: x["best"], reverse=not lower_better)

            # Attach human labels for display
            for rec in rows:
                if selected_phase == "all":
                    rec["phase_label"] = phase_map.get(rec["phase"], rec["phase"])
                else:
                    rec["phase_label"] = phase_map.get(selected_phase, selected_phase)

        ctx = {
            "tests": tests,
            "selected_test": selected_test,
            "rows": rows,
            "phase_choices": self.get_phase_choices(),
            "selected_phase": selected_phase,
        }
        return render(request, self.template_name, ctx)


def debug_env(request):
    return JsonResponse({
        "ALLOWED_HOSTS": settings.ALLOWED_HOSTS,
        "CSRF_TRUSTED_ORIGINS": settings.CSRF_TRUSTED_ORIGINS,
    })

@staff_member_required
def export_fixture(request):
    buf = io.StringIO()
    call_command(
        "dumpdata",
        "--natural-foreign", "--natural-primary",
        "-e", "contenttypes", "-e", "auth.permission", "-e", "admin.logentry", "-e", "sessions",
        stdout=buf,
    )
    data = buf.getvalue()
    resp = HttpResponse(data, content_type="application/json")
    resp["Content-Disposition"] = 'attachment; filename="render_dump.json"'
    return resp

# tiny health check to confirm routing quickly
def health(request):
    return HttpResponse("ok")