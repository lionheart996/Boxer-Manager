from django import forms
from .models import Attendance, BatteryTest, TestResult
from datetime import date
from .models import Boxer

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
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Enter boxer name'})
        }

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
        fields = ["name", "unit", "description", "display_order"]
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
    class Meta:
        model = TestResult
        fields = ["value1", "value2", "value3", "notes"]
        widgets = {"notes": forms.TextInput(attrs={"placeholder": "Optional notes"})}

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

class HeartRateQuickForm(forms.Form):
    boxer = forms.ModelChoiceField(queryset=Boxer.objects.none(), label="Boxer")
    phase = forms.ChoiceField(choices=TestResult.PHASE_CHOICES, label="Phase")
    bpm = forms.IntegerField(min_value=30, max_value=240, label="Heart rate (bpm)")
    measured_at = forms.DateField(
        required=False,
        label="Date",
        widget=forms.DateInput(attrs={"type": "date"})
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["boxer"].queryset = Boxer.objects.filter(coach=user).order_by("name")

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