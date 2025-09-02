import datetime
from time import time
import datetime as dt
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date

from .models import Attendance, BatteryTest, TestResult, Gym, HeartRate, Enrollment, ClassTemplate
from datetime import date
from .models import Boxer
from .utils import user_gym


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['boxer', 'date', 'is_present', 'is_excused']
        widgets = {
            'date': forms.SelectDateWidget(),
        }


class BoxerForm(forms.ModelForm):
    class Meta:
        model = Boxer
        fields = ['name', 'date_of_birth']

class MultiAttendanceForm(forms.Form):
    date = forms.DateField(widget=forms.SelectDateWidget())

    def __init__(self, *args, **kwargs):
        boxers = kwargs.pop('boxers')
        super().__init__(*args, **kwargs)
        self.boxers = boxers

        for boxer in boxers:
            self.fields[f'present_{boxer.id}'] = forms.BooleanField(
                required=False,
                label='',
                widget=forms.CheckboxInput()
            )
            self.fields[f'excused_{boxer.id}'] = forms.BooleanField(
                required=False,
                label='',
                widget=forms.CheckboxInput()
            )


class DateSelectionForm(forms.Form):
    date = forms.ChoiceField(
        label="Select a date",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        dates = Attendance.objects.order_by('-date').values_list('date', flat=True).distinct()
        self.fields['date'].choices = [
            (d.strftime('%Y-%m-%d'), d.strftime('%Y-%m-%d')) for d in dates
        ]

class BatteryTestForm(forms.ModelForm):
    class Meta:
        model = BatteryTest
        fields = ["name", "display_order", "unit", "description"]
        help_texts = {
            "name": "Example: Agility – Illinois",
            "unit": "Required. Example: s, m, reps (brackets are added automatically).",
        }

    def clean_unit(self):
        unit = (self.cleaned_data.get("unit") or "").strip()
        if not unit:
            raise forms.ValidationError("A measurement unit is required.")
        if "[" in unit or "]" in unit:
            raise forms.ValidationError("Do not include brackets in the unit; they will be added automatically.")
        return unit


class TestResultForm(forms.ModelForm):
    measured_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )

    class Meta:
        model = TestResult
        fields = ["boxer", "test", "measured_at", "value1", "value2", "value3", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"placeholder": "Optional notes"})}

    # make sure boxer and test are required
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["boxer"].required = True
        self.fields["test"].required = True


class PhaseSelectForm(forms.Form):
    phase = forms.ChoiceField(
        choices=TestResult.PHASE_CHOICES,
        initial=TestResult.PHASE_PRE,
        label="Phase"
    )

class BoxerSelectForm(forms.Form):
    boxer = forms.ModelChoiceField(queryset=Boxer.objects.none(), label="Select a boxer")
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['boxer'].queryset = Boxer.objects.filter(coach=user).order_by('name')

class BoxerAndTestSelectForm(forms.Form):
    boxer = forms.ModelChoiceField(queryset=Boxer.objects.none(), label="Select a boxer")
    test  = forms.ModelChoiceField(queryset=BatteryTest.objects.none(), label="Select a test")
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['boxer'].queryset = Boxer.objects.filter(coach=user).order_by('name')
            self.fields['test'].queryset  = BatteryTest.objects.filter(coach=user).order_by('display_order','name')

class HeartRateQuickForm(forms.ModelForm):
    measured_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )
    class Meta:
        model = HeartRate
        fields = ["measured_at", "bpm", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Optional notes"})}

    def clean_measured_at(self):
        return self.cleaned_data.get("measured_at") or timezone.now()

class WeightQuickForm(forms.Form):
    boxer = forms.ModelChoiceField(queryset=Boxer.objects.none(), label="Boxer")
    phase = forms.ChoiceField(choices=TestResult.PHASE_CHOICES, label="Phase")
    kg = forms.DecimalField(min_value=0, max_digits=6, decimal_places=2, label="Weight (kg)")
    expected_kg = forms.DecimalField(min_value=0, max_digits=6, decimal_places=2, required=False, label="Expected (kg)")
    measured_at = forms.DateField(required=False, label="Date", widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["boxer"].queryset = Boxer.objects.filter(coach=user).order_by("name")


class ParentSignupForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email")
    child = forms.ModelChoiceField(
        queryset=Boxer.objects.all().order_by('name'),
        label="Select your child (boxer)"
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

class GymForm(forms.ModelForm):
    class Meta:
        model = Gym
        fields = ["name", "location"]

class ClassCreateForm(forms.ModelForm):
    class Meta:
        model = ClassTemplate
        fields = ["title", "description"]  # name + optional description

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.gym = user_gym(self.request)
        if commit:
            obj.save()
        return obj


class ClassEditForm(forms.ModelForm):
    class Meta:
        model = ClassTemplate
        fields = ["title"]  # rename only


class ClassDeleteForm(forms.Form):
    class_id = forms.IntegerField(widget=forms.HiddenInput)


class ClassSelectForm(forms.Form):
    cls = forms.ModelChoiceField(
        queryset=ClassTemplate.objects.none(),
        required=False,
        label="Class"
    )
    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        gym = user_gym(request)
        self.fields["cls"].queryset = ClassTemplate.objects.filter(gym=gym).order_by("title")


class EnrollBoxerForm(forms.Form):
    boxer = forms.ModelChoiceField(queryset=Boxer.objects.none(), label="Add boxer to this class")
    def __init__(self, *args, request=None, template=None, **kwargs):
        super().__init__(*args, **kwargs)
        gym = user_gym(request)
        enrolled_ids = Enrollment.objects.filter(template=template).values_list("boxer_id", flat=True)
        self.fields["boxer"].queryset = Boxer.objects.filter(gym=gym).exclude(id__in=enrolled_ids).order_by("name")


class UnenrollForm(forms.Form):
    boxer_id = forms.IntegerField(widget=forms.HiddenInput)

class BulkBoxerForm(forms.Form):
    first_name   = forms.CharField(label="Name", required=False)
    last_name    = forms.CharField(label="Family name", required=False)
    parent_name  = forms.CharField(label="Parent", required=False)
    date_of_birth = forms.DateField(
        label="Birthday", required=False,
        widget=forms.DateInput(attrs={"type": "date"})
    )

    def clean(self):
        cleaned = super().clean()
        fn  = (cleaned.get("first_name") or "").strip()
        ln  = (cleaned.get("last_name") or "").strip()
        par = (cleaned.get("parent_name") or "").strip()
        dob = cleaned.get("date_of_birth")

        # If the entire row is blank -> mark as empty; NO error
        if not fn and not ln and not par and not dob:
            cleaned["_empty_row"] = True
            return cleaned

        # If there’s any data, require at least one of first/last name
        if not fn and not ln:
            raise forms.ValidationError("Please provide at least a Name or a Family name.")

        cleaned["_empty_row"] = False
        return cleaned