# ===== BATTERY TESTS =====
import io
from datetime import datetime
from datetime import date, time as dt_time
from datetime import date as Date
from decimal import InvalidOperation, Decimal
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import transaction, IntegrityError
from django.db.models import Max, Q, Subquery, OuterRef, ProtectedError, Exists, Avg
from django.db.models.functions import TruncDate
from django.forms import formset_factory
from django.http import HttpResponseBadRequest, JsonResponse, HttpResponse, HttpResponseForbidden, Http404
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, UpdateView, FormView, ListView, DetailView, CreateView
from django.views import View
from django.urls import reverse_lazy, reverse, get_resolver
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from rest_framework.exceptions import PermissionDenied

from . import models
from .models import Boxer, BatteryTest, Attendance, HeartRate, Weight, ParentProfile, ClassTemplate, \
    ClassSession, SessionAttendance, Enrollment, Gym
from .forms import BatteryTestForm, BoxerAndTestSelectForm, BoxerForm, HeartRateQuickForm, \
    WeightQuickForm, ParentSignupForm, GymForm, TestResultForm, EnrollBoxerForm, ClassCreateForm, UnenrollForm, \
    BulkBoxerForm
from .utils import expand_rrule


# --- phase helpers (ensure these exist in the file once) ---
PHASE_SYNONYMS = {
    "prep":  {"prep", "pre", "preparation", "Pre", "PRE", "Preparation"},
    "build": {"build", "mid", "Mid", "BUILD", "Build"},
    "peak":  {"peak", "before", "Before", "before tournament", "Before Tournament", "PEAK", "Peak"},
}
def normalize_phase(raw: str) -> str:
    raw = (raw or "").strip().lower()
    for canon, syns in PHASE_SYNONYMS.items():
        if raw in {s.lower() for s in syns}:
            return canon
    return "prep"
def phase_family(slug: str):
    canon = normalize_phase(slug)
    return PHASE_SYNONYMS.get(canon, {canon})

def is_parent_user(user):
    try:
        return bool(user.parent_profile)
    except ParentProfile.DoesNotExist:
        return False


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        gym = user_gym(self.request)

        # Who can you see?
        if self.request.user.is_superuser:
            boxers_qs = Boxer.objects.all()
        else:
            if gym:
                boxers_qs = Boxer.objects.filter(
                    Q(gym=gym) | Q(shared_with_gyms=gym) | Q(coaches=self.request.user)
                ).distinct()
            else:
                boxers_qs = Boxer.objects.filter(coaches=self.request.user).distinct()

        boxers_qs = boxers_qs.order_by("name")

        # Build the HR quick form and restrict its boxer queryset to what you can see
        hr_form = HeartRateQuickForm()
        if "boxer" in hr_form.fields and hasattr(hr_form.fields["boxer"], "queryset"):
            hr_form.fields["boxer"].queryset = boxers_qs

        ctx.update({
            "boxers": boxers_qs,
            "hr_form": hr_form,
        })
        return ctx

class RegisterView(FormView):
    template_name = 'login/register.html'
    form_class = UserCreationForm
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)

def _user_gym(user):
    """Return the user's gym; create/get a default if missing."""
    try:
        return user.coach_profile.gym
    except Exception:
        gym, _ = Gym.objects.get_or_create(name="Default Gym", defaults={"timezone": "Europe/Brussels"})
        return gym

class BoxerListView(LoginRequiredMixin, ListView):
    template_name = 'boxers/boxer_list.html'
    context_object_name = 'boxers'
    paginate_by = 25  # optional; remove if you don't want pagination

    def get_queryset(self):
        gym = user_gym(self.request)
        q = (self.request.GET.get("q") or "").strip()
        qs = Boxer.objects.filter(gym=gym)

        if q:
            # AND all terms; match against name OR parent_name
            for term in q.split():
                qs = qs.filter(
                    Q(name__icontains=term) |
                    Q(parent_name__icontains=term)
                )
        return qs.order_by("name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = (self.request.GET.get("q") or "").strip()
        ctx["result_count"] = self.get_queryset().count()
        ctx["form"] = BoxerForm()  # keep if you still use POST add
        return ctx

    def post(self, request, *args, **kwargs):
        form = BoxerForm(request.POST)
        if form.is_valid():
            boxer = form.save(commit=False)
            boxer.gym = user_gym(request)
            boxer.save()
            return redirect('boxer_list')
        return self.render_to_response(self.get_context_data(form=form))

class TestsListView(LoginRequiredMixin, TemplateView):
    template_name = "tests/tests_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = BatteryTestForm()
        ctx["tests"] = BatteryTest.objects.all().order_by("display_order", "name")
        return ctx

    def post(self, request, *args, **kwargs):
        form = BatteryTestForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("tests_list")
        # fall back: re-render with errors
        ctx = self.get_context_data()
        ctx["form"] = form
        return self.render_to_response(ctx)


class TestUpdateView(LoginRequiredMixin, UpdateView):
    model = BatteryTest
    form_class = BatteryTestForm
    template_name = "tests/test_edit.html"
    pk_url_kwarg = "pk"
    success_url = reverse_lazy("tests_list")

    # Don’t scope/hide tests here. Show all so the link always works.
    def get_queryset(self):
        return BatteryTest.objects.all()

    # Optional: friendlier than a plain 404
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not obj:
            messages.error(self.request, "That test doesn’t exist (maybe it was deleted).")
            raise Http404
        return obj


# views.py
class BatteryTestDeleteView(View):
    success_url = reverse_lazy("tests_list")

    def post(self, request, pk, *args, **kwargs):
        test = get_object_or_404(BatteryTest, pk=pk)
        try:
            with transaction.atomic():
                test.delete()
        except ProtectedError:
            # If your FKs are PROTECT/RESTRICT and you want to cascade in code:
            with transaction.atomic():
                TestResult.objects.filter(test=test).delete()
                test.delete()
        except IntegrityError:
            messages.error(request, "Could not delete this test due to database constraints.")
            return redirect(self.success_url)

        messages.success(request, f'“{test.name}” deleted.')
        return redirect(self.success_url)

    def get(self, request, pk, *args, **kwargs):
        # No deletes via GET; just bounce back
        return redirect(self.success_url)



# ===== RESULTS MATRIX (phase-aware) =====
# class ResultsMatrixView(LoginRequiredMixin, TemplateView):
#     template_name = 'tests_results.html'
#
#     def current_phase(self):
#         return self.request.GET.get('phase') or TestResult.PHASE_PRE
#
#     def get(self, request, *args, **kwargs):
#         phase = self.current_phase()
#         tests = BatteryTest.objects.filter(coach=request.user).order_by('display_order', 'name')
#         boxers = Boxer.objects.filter(coach=request.user).order_by('name')
#         results = {
#             (r.boxer_id, r.test_id): r
#             for r in TestResult.objects.filter(
#                 boxer__coach=request.user, test__coach=request.user, phase=phase
#             )
#         }
#         return render(request, self.template_name, {
#             'phase_form': PhaseSelectForm(initial={'phase': phase}),
#             'phase': phase,
#             'tests': tests,
#             'boxers': boxers,
#             'results': results,
#         })
#
#     def post(self, request, *args, **kwargs):
#         # Save All for selected phase
#         phase = request.GET.get('phase') or request.POST.get('phase') or TestResult.PHASE_PRE
#         tests = BatteryTest.objects.filter(coach=request.user)
#         boxers = Boxer.objects.filter(coach=request.user)
#
#         for b in boxers:
#             for t in tests:
#                 prefix = f"r-{b.id}-{t.id}-"
#                 v1 = request.POST.get(prefix + "value1")
#                 v2 = request.POST.get(prefix + "value2")
#                 v3 = request.POST.get(prefix + "value3")
#                 notes = (request.POST.get(prefix + "notes") or "").strip()
#                 if all(x in (None, '') for x in (v1, v2, v3, notes)):
#                     continue
#                 obj, _ = TestResult.objects.get_or_create(boxer=b, test=t, phase=phase)
#                 obj.value1, obj.value2, obj.value3 = v1 or None, v2 or None, v3 or None
#                 obj.notes = notes
#                 obj.save()
#
#         return redirect(f"{reverse_lazy('tests_results')}?phase={phase}")

def post(self, request, *args, **kwargs):
    # Save a single (boxer, test, phase) result from the detail form
    phase    = request.POST.get('phase') or TestResult.PHASE_PRE
    boxer_id = request.POST.get('boxer_id')
    test_id  = request.POST.get('test_id')

    try:
        boxer = get_object_or_404(Boxer, id=int(boxer_id), coach=request.user)
        test  = get_object_or_404(BatteryTest, id=int(test_id), coach=request.user)
    except (TypeError, ValueError):
        messages.error(request, "Please select a boxer and a test.")
        return redirect(f"{reverse_lazy('tests_results')}?phase={phase}")

    def parse_val(name):
        raw = (request.POST.get(name) or '').strip()
        if raw == '':
            return None
        try:
            return float(raw)
        except ValueError:
            raise ValidationError(f"{name} must be a number or blank.")

    try:
        v1 = parse_val('value1')
        v2 = parse_val('value2')
        v3 = parse_val('value3')
    except ValidationError as e:
        messages.error(request, str(e))
        return redirect(f"{reverse_lazy('tests_results')}?boxer={boxer.id}&test={test.id}&phase={phase}")

    notes = (request.POST.get('notes') or '').strip()

    obj, _ = TestResult.objects.get_or_create(boxer=boxer, test=test, phase=phase)
    obj.value1, obj.value2, obj.value3, obj.notes = v1, v2, v3, notes
    obj.save()

    messages.success(request, "Result saved.")
    return redirect(f"{reverse_lazy('tests_results')}?boxer={boxer.id}&test={test.id}&phase={phase}")


class ResultsCellSaveView(LoginRequiredMixin, View):
    """Save a single (boxer,test) cell for the selected phase."""
    def post(self, request, *args, **kwargs):
        phase = request.GET.get('phase') or request.POST.get('phase') or TestResult.PHASE_PRE
        boxer_id = request.GET.get('b') or request.POST.get('boxer_id')
        test_id  = request.GET.get('t') or request.POST.get('test_id')

        # If params are missing/invalid -> just go back to the Tests list (NO popup)
        try:
            boxer_id, test_id = int(boxer_id), int(test_id)
        except (TypeError, ValueError):
            return redirect("tests_list")

        # Do NOT filter by non-existent fields like coach=...
        # If you want to scope boxers to the current coach, use coaches=request.user (M2M).
        boxer = get_object_or_404(Boxer, id=boxer_id)  # or: id=boxer_id, coaches=request.user
        test  = get_object_or_404(BatteryTest, id=test_id)

        prefix = f"r-{boxer_id}-{test_id}-"
        v1 = request.POST.get(prefix + "value1") or None
        v2 = request.POST.get(prefix + "value2") or None
        v3 = request.POST.get(prefix + "value3") or None
        notes = (request.POST.get(prefix + "notes") or "").strip()

        obj, _ = TestResult.objects.get_or_create(boxer=boxer, test=test, phase=phase)
        obj.value1, obj.value2, obj.value3 = v1, v2, v3
        obj.notes = notes
        obj.save()

        # Always return to the Tests list (not the removed results matrix)
        return redirect("tests_list")



# ===== ONE BOXER (not phase-specific; keep simple) =====

# ===== SUMMARY (not phase-specific) =====

# ===== MANAGE BOXERS (boxer + test, show best per phase + improvement) =====
class BoxerPerformanceView(LoginRequiredMixin, FormView):
    template_name = 'tests/tests_manage_boxers.html'
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

class AttendanceListView(LoginRequiredMixin, ListView):
    model = Attendance
    template_name = "attendance/attendance_list.html"
    context_object_name = "attendances"
    paginate_by = 50

    def get_queryset(self):
        qs = (Attendance.objects
              .select_related("boxer", "boxer__gym")
              .order_by("-date", "boxer__name"))

        # Superusers see all
        if self.request.user.is_superuser:
            pass
        else:
            gym = user_gym(self.request)
            if gym:
                qs = qs.filter(
                    Q(boxer__gym=gym) |
                    Q(boxer__shared_with_gyms=gym) |
                    Q(boxer__coaches=self.request.user)
                )
            else:
                # If user has no gym, still show boxers they coach
                qs = qs.filter(boxer__coaches=self.request.user)

        # Optional filters
        date_str = self.request.GET.get("date")
        if date_str:
            qs = qs.filter(date=date_str)  # DateField expects YYYY-MM-DD

        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(boxer__name__icontains=q)

        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("today", timezone.localdate())
        ctx["q"] = self.request.GET.get("q", "")
        ctx["date"] = self.request.GET.get("date", "")
        return ctx

class MarkAttendanceView(LoginRequiredMixin, TemplateView):
    template_name = "attendance/mark_attendance.html"

    # ---------- helpers ----------
    def _target_date(self):
        d = parse_date(self.request.GET.get("date") or self.request.POST.get("date") or "")
        return d or date.today()

    def _selected_class(self, gym):
        # use class_id (NOT "class")
        cid = self.request.GET.get("class_id") or self.request.POST.get("class_id")
        if not cid:
            return None
        try:
            return ClassTemplate.objects.get(id=int(cid), gym=gym)
        except Exception:
            return None

    def _scoped_boxers_qs(self, gym, class_obj=None):
        qs = Boxer.objects.all() if self.request.user.is_superuser else Boxer.objects.filter(gym=gym)
        return qs.filter(enrollments__template=class_obj) if class_obj else qs

    def _preserve_redirect(self, class_obj, target_date):
        url = reverse("mark_attendance")
        params = []
        if class_obj:
            params.append(f"class_id={class_obj.id}")
        if target_date:
            params.append(f"date={target_date.isoformat()}")
        return url + ("?" + "&".join(params) if params else "")

    # ---------- GET ----------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        gym = user_gym(self.request)
        target_date = self._target_date()
        selected_class = self._selected_class(gym)

        classes = ClassTemplate.objects.filter(gym=gym).order_by("title")
        boxers = self._scoped_boxers_qs(gym, selected_class).order_by("name")

        present_ids = set(
            Attendance.objects.filter(
                boxer__in=boxers, date=target_date, is_present=True
            ).values_list("boxer_id", flat=True)
        )

        ctx.update({
            "date": target_date,
            "classes": classes,
            "selected_class": selected_class,
            "boxers": boxers,
            "attendance_map": present_ids,
            "class_create_form": ClassCreateForm(request=self.request),
            "enroll_form": EnrollBoxerForm(request=self.request, template=selected_class) if selected_class else None,
            "unenroll_form": UnenrollForm(),  # convenience instance if you render one
        })
        return ctx

    # ---------- POST ----------
    def post(self, request, *args, **kwargs):
        gym = user_gym(request)
        target_date = self._target_date()
        selected_class = self._selected_class(gym)
        action = request.POST.get("action")

        # A) Create class
        if action == "create_class":
            form = ClassCreateForm(request.POST, request=request)
            if form.is_valid():
                new_cls = form.save()
                return redirect(self._preserve_redirect(new_cls, target_date))
            return self.get(request, *args, **kwargs)

        # B) Enroll boxer
        if action == "enroll" and selected_class:
            form = EnrollBoxerForm(request.POST, request=request, template=selected_class)
            if form.is_valid():
                Enrollment.objects.get_or_create(template=selected_class, boxer=form.cleaned_data["boxer"])
            return redirect(self._preserve_redirect(selected_class, target_date))

        # C) Unenroll boxer  <-- REMOVE button handlers land here
        if action == "unenroll" and selected_class:
            try:
                boxer_id = int(request.POST.get("boxer_id"))
            except (TypeError, ValueError):
                return redirect(self._preserve_redirect(selected_class, target_date))
            Enrollment.objects.filter(template=selected_class, boxer_id=boxer_id).delete()
            return redirect(self._preserve_redirect(selected_class, target_date))

        # D) Save attendance
        measured_dt = datetime.combine(target_date, dt_time(hour=12, minute=0))
        if timezone.is_naive(measured_dt):
            measured_dt = timezone.make_aware(measured_dt, timezone.get_current_timezone())

        # detect excused field
        excused_field = None
        for fname in ("is_excused", "excused", "excused_absence"):
            try:
                Attendance._meta.get_field(fname)
                excused_field = fname
                break
            except Exception:
                pass

        boxer_qs = self._scoped_boxers_qs(gym, selected_class)
        for boxer in boxer_qs:
            status = request.POST.get(f"attendance_{boxer.id}")  # "Present" | "Absent" | None
            raw_weight = (request.POST.get(f"weight_{boxer.id}") or "").strip()
            has_weight_input = bool(raw_weight)
            excused_flag = f"excused_{boxer.id}" in request.POST

            mark_row = False
            is_present = False
            if status == "Present":
                is_present = True; mark_row = True
            elif status == "Absent":
                is_present = False; mark_row = True
            elif status is None and has_weight_input:
                try:
                    if float(raw_weight) > 0:
                        is_present = True; mark_row = True
                except (TypeError, ValueError):
                    pass
            if not mark_row:
                continue

            defaults = {"is_present": is_present}
            if excused_field:
                defaults[excused_field] = bool(excused_flag) and not is_present
            Attendance.objects.update_or_create(
                boxer=boxer, date=target_date, defaults=defaults
            )

            # weight handling
            if (status == "Absent") or (is_present and not has_weight_input):
                Weight.objects.filter(boxer=boxer, measured_at__date=target_date).delete()
                continue

            if is_present and has_weight_input:
                try:
                    kg = Decimal(raw_weight)
                except (InvalidOperation, ValueError):
                    kg = None
                if kg is not None:
                    with transaction.atomic():
                        existing = Weight.objects.filter(
                            boxer=boxer, measured_at__date=target_date
                        ).order_by("-measured_at").first()
                        if existing:
                            existing.kg = kg
                            existing.measured_at = measured_dt
                            existing.save(update_fields=["kg", "measured_at"])
                            Weight.objects.filter(
                                boxer=boxer, measured_at__date=target_date
                            ).exclude(pk=existing.pk).delete()
                        else:
                            Weight.objects.create(
                                boxer=boxer, kg=kg, measured_at=measured_dt
                            )

        return redirect(self._preserve_redirect(selected_class, target_date))


@login_required
def attendance_by_date(request):
    # parse ?date=YYYY-MM-DD; default to today if missing/invalid
    q = (request.GET.get("date") or "").strip()
    try:
        selected = Date.fromisoformat(q) if q else timezone.now().date()
    except ValueError:
        selected = timezone.now().date()

    # scope boxers based on current user
    gym = user_gym(request)
    if request.user.is_superuser:
        boxers_qs = Boxer.objects.all()
    elif gym:
        boxers_qs = Boxer.objects.filter(
            Q(gym=gym) | Q(shared_with_gyms=gym) | Q(coaches=request.user)
        ).distinct()
        if not boxers_qs.exists():
            boxers_qs = Boxer.objects.filter(coaches=request.user).distinct() or Boxer.objects.all()
    else:
        boxers_qs = Boxer.objects.filter(coaches=request.user).distinct() or Boxer.objects.all()

    records = (
        Attendance.objects
        .filter(boxer__in=boxers_qs, date=selected)
        .select_related("boxer")
        .order_by("boxer__name")
    )

    return render(request, "attendance/attendance_by_date.html", {
        "date": selected,                  # for display
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
    template_name = "boxers/boxer_report.html"
    context_object_name = "boxer"
    pk_url_kwarg = "boxer_id"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        boxer = self.get_object()

        # latest weight for the same calendar date as Attendance.date
        latest_weight_qs = (
            Weight.objects
            .filter(boxer=boxer, measured_at__date=OuterRef("date"))
            .order_by("-measured_at")
            .values("kg")[:1]
        )

        attendance_qs = (
            Attendance.objects
            .filter(boxer=boxer)
            .annotate(weight_kg=Subquery(latest_weight_qs))
            .order_by("date")
        )

        total = attendance_qs.count()
        present = attendance_qs.filter(is_present=True).count()
        excused = attendance_qs.filter(is_present=False, is_excused=True).count()
        absent_unexcused = attendance_qs.filter(is_present=False, is_excused=False).count()
        absent = excused + absent_unexcused

        present_pct = round((present / total) * 100, 1) if total else 0
        absent_pct = round((absent / total) * 100, 1) if total else 0
        excused_pct_of_abs = round((excused / absent) * 100, 1) if absent else 0
        excused_triplets = excused // 3
        score = present - absent_unexcused - excused_triplets

        ctx.update({
            "attendance": attendance_qs,
            "att_total": total,
            "att_present": present,
            "att_absent": absent,
            "att_excused": excused,
            "att_present_pct": present_pct,
            "att_absent_pct": absent_pct,
            "att_excused_pct_of_abs": excused_pct_of_abs,
            "att_excused_triplets": excused_triplets,
            "att_score": score,
        })
        return ctx

@login_required
def add_boxer(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Please enter a boxer name.")
            return redirect("home")

        # Create boxer without coach
        boxer = Boxer.objects.create(name=name, gym=user_gym(request))

        # Attach the current user as one of the coaches
        boxer.coaches.add(request.user)

        messages.success(
            request,
            f"You successfully added {boxer.name} to your boxers' list."
        )
        return redirect("home")

    return redirect("home")

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
    template_name = 'tests/tests_result_edit.html'

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


@login_required
def record_heart_rate(request):
    if request.method != "POST":
        return redirect("home")

    form = HeartRateQuickForm(request.POST)
    if form.is_valid():
        hr = form.save(commit=False)
        # (Optional) gate: ensure boxer is in scope of current user
        gym = user_gym(request)
        allowed = (
            request.user.is_superuser
            or (gym and hr.boxer.gym_id == getattr(gym, "id", None))
            or (gym and hr.boxer.shared_with_gyms.filter(id=gym.id).exists())
            or hr.boxer.coaches.filter(id=request.user.id).exists()
        )
        if not allowed:
            return redirect("home")
        hr.save()
    return redirect("heart_rate_summary")


class HeartRateSummaryView(LoginRequiredMixin, TemplateView):
    template_name = "heartrate/heart_rate_summary.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        gym = user_gym(self.request)

        # Scope boxers like HomeView
        if self.request.user.is_superuser:
            boxers = Boxer.objects.all()
        elif gym:
            boxers = Boxer.objects.filter(
                Q(gym=gym) | Q(shared_with_gyms=gym) | Q(coaches=self.request.user)
            ).distinct()
        else:
            boxers = Boxer.objects.filter(coaches=self.request.user).distinct()
        boxers = boxers.order_by("name")

        # Pull heart rates for those boxers
        hr_qs = HeartRate.objects.filter(boxer__in=boxers)

        # Find the latest timestamp per boxer
        latest = hr_qs.values("boxer_id").annotate(last_measured=Max("measured_at"))
        last_map = {row["boxer_id"]: row["last_measured"] for row in latest}

        # Fetch actual HeartRate rows at those timestamps
        filt = Q()
        for b_id, ts in last_map.items():
            filt |= (Q(boxer_id=b_id) & Q(measured_at=ts))
        latest_objs = hr_qs.filter(filt) if last_map else hr_qs.none()
        latest_objs = latest_objs.select_related("boxer")

        # Map boxer_id -> HeartRate object
        obj_map = {hr.boxer_id: hr for hr in latest_objs}

        # Build rows for template
        rows = []
        for boxer in boxers:
            rows.append({
                "boxer": boxer,
                "latest": obj_map.get(boxer.id),
            })

        ctx["rows"] = rows
        return ctx

def _scoped_boxers(request):
    user = request.user
    if user.is_superuser:
        return Boxer.objects.all()
    cp = getattr(user, "coachprofile", None)
    gym = getattr(cp, "gym", None)
    if gym:
        return Boxer.objects.filter(Q(coaches=user) | Q(gym=gym) | Q(shared_with_gyms=gym)).distinct()
    return Boxer.objects.filter(coaches=user).distinct()

class HeartRateDetailView(LoginRequiredMixin, DetailView):
    model = Boxer
    template_name = "heartrate/boxer_detail.html"
    pk_url_kwarg = "boxer_id"
    def get_queryset(self):
        return _scoped_boxers(self.request)

class HeartRateCreateView(LoginRequiredMixin, CreateView):
    form_class = HeartRateQuickForm
    template_name = "heartrate/heart_rate_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.boxer = get_object_or_404(_scoped_boxers(request), pk=kwargs["boxer_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["boxer"] = self.boxer
        return ctx

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.boxer = self.boxer
        obj.save()
        messages.success(self.request, f"Added {obj.bpm} bpm for {self.boxer.name}.")
        next_url = self.request.GET.get("next")
        return redirect(next_url) if next_url else redirect(
            reverse("heart_rate_detail", kwargs={"boxer_id": self.boxer.id})
        )

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
    template_name = 'weight/weight_summary.html'

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
    template_name = "weight/weight_detail.html"

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

# views.py
from .models import TestResult
from .utils import user_gym, resolve_boxer

class TestRankingView(LoginRequiredMixin, TemplateView):
    template_name = "tests/tests_rankings.html"

    def _scoped_boxers(self, user, gym):
        if user.is_superuser:
            return Boxer.objects.all()
        qs = Boxer.objects.filter(coaches=user).distinct()
        if gym:
            qs = Boxer.objects.filter(
                Q(coaches=user) | Q(gym=gym) | Q(shared_with_gyms=gym)
            ).distinct()
        return qs if qs.exists() else Boxer.objects.all()

    def _lower_is_better(self, test):
        """Return True if lower values should rank higher for this test."""
        u = (getattr(test, "unit", "") or "").strip().lower()
        # Treat seconds/time units as lower-is-better
        time_units = {
            "s", "sec", "secs", "second", "seconds",
            "ms", "millisecond", "milliseconds",
            "min", "mins", "minute", "minutes",
            "h", "hr", "hrs", "hour", "hours",
        }
        if u in time_units:
            return True
        # Distances like m, cm -> higher is better (descending)
        if u in {"m", "meter", "meters", "metre", "metres", "cm", "centimeter", "centimeters", "centimetre", "centimetres"}:
            return False
        # Default: higher is better
        return False

    def get(self, request, *args, **kwargs):
        gym = user_gym(request)
        boxers_qs = self._scoped_boxers(request.user, gym).order_by("name")

        tests = BatteryTest.objects.all().order_by("display_order", "name")

        raw_phase = (request.GET.get("phase") or "").strip().lower() or "all"
        legacy = {"pre": "prep", "mid": "build", "before": "peak"}
        raw_phase = legacy.get(raw_phase, raw_phase)

        base_phase_choices = getattr(
            TestResult, "PHASE_CHOICES",
            (("prep", "Preparation"), ("build", "Build"), ("peak", "Peak"))
        )
        valid_phases = {v for v, _ in base_phase_choices} | {"all"}
        selected_phase = raw_phase if raw_phase in valid_phases else "all"

        selected_test = None
        test_id = kwargs.get("test_id") or request.GET.get("test")
        if test_id:
            selected_test = get_object_or_404(BatteryTest, pk=int(test_id))
        else:
            exists_qs = TestResult.objects.filter(test=OuterRef("pk"), boxer__in=boxers_qs)
            if selected_phase != "all":
                exists_qs = exists_qs.filter(phase=selected_phase)
            selected_test = (
                tests.annotate(has_results=Exists(exists_qs))
                     .filter(has_results=True)
                     .first()
            )

        rows = []
        if selected_test:
            res_qs = TestResult.objects.filter(test=selected_test, boxer__in=boxers_qs)
            if selected_phase != "all":
                res_qs = res_qs.filter(phase=selected_phase)

            lower_is_better = self._lower_is_better(selected_test)

            by_boxer = {}
            for r in res_qs.select_related("boxer"):
                vals = []
                for v in (r.value1, r.value2, r.value3):
                    try:
                        if v is not None:
                            vals.append(Decimal(str(v)))
                    except Exception:
                        pass
                if not vals:
                    continue

                best = min(vals) if lower_is_better else max(vals)
                cur = by_boxer.get(r.boxer_id)
                if cur is None:
                    by_boxer[r.boxer_id] = {"boxer": r.boxer, "best": best, "phase": r.phase}
                else:
                    # keep the better result per boxer according to the rule
                    if (lower_is_better and best < cur["best"]) or (not lower_is_better and best > cur["best"]):
                        cur.update({"best": best, "phase": r.phase})

            rows = sorted(by_boxer.values(), key=lambda d: d["best"], reverse=not lower_is_better)

        phase_map = dict(base_phase_choices)
        for d in rows:
            d["phase_label"] = phase_map.get(d["phase"], d["phase"])

        ctx = {
            "tests": tests,
            "selected_test": selected_test,
            "selected_phase": selected_phase,
            "phase_choices": tuple(list(base_phase_choices) + [("all", "All phases")]),
            "rows": rows,
        }
        return self.render_to_response(ctx)



def health(request):
    return HttpResponse("ok")

def debug_urls(request):
    pats = [str(p.pattern) for p in get_resolver().url_patterns]
    return JsonResponse({"patterns": pats})

def debug_env(request):
    from django.conf import settings
    return JsonResponse({
        "ALLOWED_HOSTS": settings.ALLOWED_HOSTS,
        "CSRF_TRUSTED_ORIGINS": getattr(settings, "CSRF_TRUSTED_ORIGINS", []),
        "DEBUG": settings.DEBUG,
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


def user_can_view_boxer(user, boxer):
    """Allow superuser, the coach who owns the boxer, or a parent linked to the boxer."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or getattr(boxer, 'coach_id', None) == user.id:
        return True
    try:
        return user.parent_profile.children.filter(id=boxer.id).exists()
    except ParentProfile.DoesNotExist:
        return False


class ParentHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'parent/home.html'

    def get(self, request, *args, **kwargs):
        children = []
        try:
            profile = request.user.parent_profile  # safe: wrapped in try/except
            children = profile.children.select_related('coach').order_by('name')
        except ParentProfile.DoesNotExist:
            pass
        return render(request, self.template_name, {'children': children})


class ParentAttendanceView(LoginRequiredMixin, TemplateView):
    template_name = 'parent/attendance.html'

    def get(self, request, boxer_id, *args, **kwargs):
        boxer = get_object_or_404(Boxer, id=boxer_id)
        if not user_can_view_boxer(request.user, boxer):
            raise PermissionDenied("You cannot view this boxer.")
        records = Attendance.objects.filter(boxer=boxer).order_by('-date')
        return render(request, self.template_name, {'boxer': boxer, 'records': records})


class WeightProgressView(LoginRequiredMixin, TemplateView):
    template_name = "weight/weight_progress.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        boxer = get_object_or_404(Boxer, pk=self.kwargs["boxer_id"])

        gym = user_gym(self.request)
        allowed = (
            self.request.user.is_superuser
            or (gym and boxer.gym_id == getattr(gym, "id", None))
            or (gym and boxer.shared_with_gyms.filter(id=gym.id).exists())
            or boxer.coaches.filter(id=self.request.user.id).exists()
        )
        if not allowed:
            ctx.update({"boxer": boxer, "rows": [], "fw_error": "Not allowed"})
            return ctx

        # Take the latest entry per calendar date
        by_day = {}
        for w in Weight.objects.filter(boxer=boxer).order_by("measured_at"):
            day = w.measured_at.date()
            by_day[day] = w.kg  # later entries overwrite earlier ones

        rows = [{"date": d, "weight": by_day[d]} for d in sorted(by_day)]

        vals = [r["weight"] for r in rows if r["weight"] is not None]
        min_w = min(vals) if vals else None
        max_w = max(vals) if vals else None
        diff  = (max_w - min_w) if (min_w is not None and max_w is not None) else None

        # fighting weight unchanged...
        fw_raw = (self.request.GET.get("fighting_weight") or "").strip()
        fighting_weight, fw_error, count_above_fw = None, None, None
        if fw_raw:
            try:
                fighting_weight = Decimal(fw_raw)
                count_above_fw = sum(1 for v in vals if v is not None and v > fighting_weight)
            except (InvalidOperation, TypeError):
                fw_error = "Invalid fighting weight. Please enter a number (e.g., 72.5)."

        ctx.update({
            "boxer": boxer,
            "rows": rows,
            "min_w": min_w,
            "max_w": max_w,
            "diff": diff,
            "fighting_weight": fighting_weight,
            "count_above_fw": count_above_fw,
            "fw_error": fw_error,
        })
        return ctx

class ParentSignupView(FormView):
    template_name = 'parent/signup.html'
    form_class = ParentSignupForm
    success_url = reverse_lazy('parent_home')

    def form_valid(self, form):
        # Create the user with hashed password (UserCreationForm handles hashing)
        user = form.save()
        # Ensure it is a regular, non-staff account
        user.is_staff = False
        user.is_superuser = False
        user.save(update_fields=["is_staff", "is_superuser"])

        # Link to the selected child
        child = form.cleaned_data["child"]
        pp, _ = ParentProfile.objects.get_or_create(user=user)
        pp.children.add(child)

        # Log them in and send to parent portal
        login(self.request, user)
        return super().form_valid(form)


class CalendarView(TemplateView):
    template_name = "calendar.html"

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden()
        # You can preload templates list if you want to show a sidebar
        templates = ClassTemplate.objects.filter(gym=user_gym(request)).order_by("title")
        return render(request, self.template_name, {"templates": templates})


def _ensure_sessions_for_range(gym, start_d: date, end_d: date):
    """
    Idempotently materialize sessions for each template in [start_d, end_d].
    Unique by (template, starts_at). Keep it simple for now.
    """
    qs = ClassTemplate.objects.filter(gym=gym).filter(
        models.Q(ends_on__isnull=True) | models.Q(ends_on__gte=start_d),
        starts_on__lte=end_d,
    )
    for t in qs:
        for s_dt, e_dt in expand_rrule(t.rrule, start_d, end_d):
            ClassSession.objects.get_or_create(
                template=t,
                starts_at=s_dt,
                defaults={"gym": gym, "ends_at": e_dt},
            )


@login_required
def api_calendar_sessions(request):
    gym = user_gym(request)
    start = parse_date(request.GET.get("start"))
    end = parse_date(request.GET.get("end"))
    if not start or not end:
        return HttpResponseBadRequest("start and end (YYYY-MM-DD) required")

    _ensure_sessions_for_range(gym, start, end)
    sessions = (ClassSession.objects
                .filter(gym=gym, is_cancelled=False,
                        starts_at__date__gte=start, starts_at__date__lte=end)
                .select_related("template")
                .order_by("starts_at"))

    payload = []
    for s in sessions:
        present = SessionAttendance.objects.filter(session=s, status="present").count()
        # enrolled at that session date
        sess_day = s.starts_at.date()
        enrolled = (Enrollment.objects
                    .filter(template=s.template,
                            active_from__lte=sess_day)
                    .filter(models.Q(active_until__isnull=True) |
                            models.Q(active_until__gte=sess_day))
                    .count())
        payload.append({
            "id": s.id,
            "title": s.template.title,
            "start": s.starts_at.isoformat(),
            "end": s.ends_at.isoformat(),
            "location": s.template.location,
            "present_count": present,
            "enrolled_count": enrolled,
        })
    return JsonResponse({"sessions": payload})


@login_required
@transaction.atomic
def api_enroll(request):
    gym = user_gym(request)
    if request.method == "POST":
        # Add enrollment (roster add)
        template_id = request.POST.get("template_id")
        boxer_id = request.POST.get("boxer_id")
        effective_from = parse_date(request.POST.get("effective_from")) or date.today()

        template = get_object_or_404(ClassTemplate, id=template_id, gym=gym)
        boxer = get_object_or_404(Boxer, id=boxer_id, gym=gym)

        Enrollment.objects.create(template=template, boxer=boxer, active_from=effective_from)
        return JsonResponse({"ok": True})

    if request.method == "DELETE":
        # End enrollment (roster remove)
        template_id = request.GET.get("template_id")
        boxer_id = request.GET.get("boxer_id")
        effective_until = parse_date(request.GET.get("effective_until")) or date.today()

        e = get_object_or_404(Enrollment, template_id=template_id, boxer_id=boxer_id)
        e.active_until = effective_until
        e.save(update_fields=["active_until"])
        return JsonResponse({"ok": True})

    return HttpResponseBadRequest("POST to add, DELETE to remove")


@login_required
@transaction.atomic
def api_attendance_upsert(request):
    gym = user_gym(request)
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    session_id = request.POST.get("session_id")
    boxer_id   = request.POST.get("boxer_id")
    status     = request.POST.get("status")    # 'present' | 'absent' | 'excused' | None
    weight_raw = request.POST.get("weight")    # optional decimal

    session = get_object_or_404(ClassSession, id=session_id, gym=gym)
    boxer   = get_object_or_404(Boxer, id=boxer_id, gym=gym)

    # Upsert per-session attendance (shared across coaches)
    sa, _ = SessionAttendance.objects.get_or_create(
        session=session,
        boxer=boxer,
        defaults={"status": "present", "marked_by": request.user},
    )

    if status:
        sa.status = status

    # “weight = presence” rule + mirror into legacy daily Attendance
    if weight_raw not in (None, ""):
        try:
            weight_val = Decimal(weight_raw)
        except Exception:
            return HttpResponseBadRequest("Invalid weight")

        sa.weight = weight_val
        sa.status = "present"
        sa.marked_by = request.user

        att_date = session.starts_at.date()
        att, _ = Attendance.objects.get_or_create(
            boxer=boxer,
            date=att_date,
            defaults={"weight": weight_val, "is_present": True, "is_excused": False},
        )
        # Update existing daily record too
        att.weight = weight_val
        att.is_present = True
        att.is_excused = False
        att.save()

    sa.marked_by = request.user
    sa.save()

    return JsonResponse({
        "ok": True,
        "status": sa.status,
        "weight": str(sa.weight) if sa.weight is not None else None,
    })

class GymCreateView(LoginRequiredMixin, CreateView):
    model = Gym
    form_class = GymForm
    template_name = "gyms/gym_form.html"
    success_url = reverse_lazy("gym_list")

class GymListView(LoginRequiredMixin, ListView):
    model = Gym
    template_name = "gyms/gym_list.html"
    context_object_name = "gyms"



def _back_to_tests_list():
    return redirect("tests_list")


class TestResultCreateView(LoginRequiredMixin, CreateView):
    template_name = "tests/tests_results.html"   # your template
    form_class = TestResultForm
    success_url = reverse_lazy("tests_record")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # optional: set queryset / preselects
        form.fields["boxer"].queryset = Boxer.objects.all().order_by("name")
        form.fields["test"].queryset = BatteryTest.objects.all().order_by("display_order", "name")
        if bid := self.request.GET.get("boxer"):
            form.initial["boxer"] = bid
        if tid := self.request.GET.get("test"):
            form.initial["test"] = tid
        # make them required at the form level too
        form.fields["boxer"].required = True
        form.fields["test"].required = True
        return form

    def form_valid(self, form):
        # Read raw POST values and validate them as integers
        raw_boxer = (self.request.POST.get("boxer") or "").strip()
        raw_test  = (self.request.POST.get("test")  or "").strip()

        def to_int_or_none(s):
            try:
                return int(s)
            except Exception:
                return None

        boxer_id = to_int_or_none(raw_boxer)
        test_id  = to_int_or_none(raw_test)

        if not boxer_id:
            form.add_error("boxer", "Please select a boxer.")
        if not test_id:
            form.add_error("test", "Please select a test.")
        if form.errors:
            return self.form_invalid(form)

        # Fetch instances safely
        boxer = get_object_or_404(Boxer, pk=boxer_id)
        test  = get_object_or_404(BatteryTest, pk=test_id)

        # Attach to the model instance before saving
        form.instance.boxer = boxer
        form.instance.test  = test

        resp = super().form_valid(form)

        # Nice popup message after save
        tr = self.object
        measured = tr.value1 if tr.value1 is not None else (tr.value2 if tr.value2 is not None else tr.value3)
        unit = tr.test.unit or ""
        date_str = (tr.measured_at or tr.created_at if hasattr(tr, "created_at") else None)
        date_str = date_str.strftime("%Y-%m-%d") if date_str else ""
        messages.success(self.request, f"{tr.boxer} has scored {measured} {unit} for test - {tr.test} on this date: {date_str}")
        return resp

class BoxerTestsView(LoginRequiredMixin, TemplateView):
    template_name = "tests/boxer_tests.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        boxer = get_object_or_404(Boxer, uuid=kwargs["uuid"])
        tests = BatteryTest.objects.all().order_by("display_order", "name")

        sel_test_id = self.request.GET.get("test")
        selected_test = get_object_or_404(tests, pk=sel_test_id) if sel_test_id else tests.first()

        labels, values = [], []
        summary = []  # <-- per-date averaged rows for the text block

        if selected_test:
            qs = (
                TestResult.objects
                .filter(boxer=boxer, test=selected_test)
                .annotate(day=TruncDate("measured_at"))
                .values("day")
                .annotate(
                    avg1=Avg("value1"),
                    avg2=Avg("value2"),
                    avg3=Avg("value3"),
                )
                .order_by("day")
            )
            for row in qs:
                nums = [x for x in (row["avg1"], row["avg2"], row["avg3"]) if x is not None]
                if not nums:
                    continue
                avg = sum(nums) / len(nums)
                d = row["day"]  # a date object
                labels.append(d.strftime("%Y-%m-%d"))
                values.append(float(avg))
                summary.append({"date": d, "avg": avg})  # <-- add for text

        ctx.update({
            "boxer": boxer,
            "tests": tests,
            "selected_test": selected_test,
            "unit": (selected_test.unit if selected_test else ""),
            "labels": labels,
            "values": values,
            "summary": summary,  # <-- expose to template
            "show_text": self.request.GET.get("show") == "1",
        })
        return ctx

class BulkBoxerCreateView(LoginRequiredMixin, View):
    template_name = "boxers/bulk_add.html"

    def get(self, request):
        # show 10 empty rows
        FormSet = formset_factory(BulkBoxerForm, extra=10, can_delete=True)
        formset = FormSet()
        return render(request, self.template_name, {"formset": formset})

    def post(self, request):
        FormSet = formset_factory(BulkBoxerForm, extra=0, can_delete=True)
        formset = FormSet(request.POST)
        if not formset.is_valid():
            return render(request, self.template_name, {"formset": formset})

        gym = user_gym(request)
        created = 0

        for form in formset:
            if form.cleaned_data.get("DELETE"):
                continue
            if form.cleaned_data.get("_empty_row"):
                continue

            fn = (form.cleaned_data.get("first_name") or "").strip()
            ln = (form.cleaned_data.get("last_name") or "").strip()
            parent = (form.cleaned_data.get("parent_name") or "").strip()
            dob = form.cleaned_data.get("date_of_birth")

            name = (fn + " " + ln).strip()
            Boxer.objects.create(
                name=name,
                parent_name=parent,
                date_of_birth=dob,
                gym=gym,
            )
            created += 1

        messages.success(request, f"Added {created} boxer(s).")
        return redirect("mark_attendance")  # or 'boxer_list' if you prefer