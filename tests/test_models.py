import pytest
from django.contrib.auth.models import User
from BoxersPresenceApp.models import Boxer, BatteryTest, TestResult, Weight

@pytest.mark.django_db
def test_create_boxer_str():
    coach = User.objects.create_user(username="coach1", password="x")
    b = Boxer.objects.create(name="Ali", coach=coach)
    assert str(b) == "Ali"

@pytest.mark.django_db
def test_unique_test_per_coach():
    coach = User.objects.create_user(username="coach2", password="x")
    BatteryTest.objects.create(name="Sprint", coach=coach, unit="s")
    with pytest.raises(Exception):
        BatteryTest.objects.create(name="Sprint", coach=coach, unit="s")

@pytest.mark.django_db
def test_weight_unique_per_phase():
    coach = User.objects.create_user(username="coach3", password="x")
    boxer = Boxer.objects.create(name="Tyson", coach=coach)
    Weight.objects.create(boxer=boxer, phase=TestResult.PHASE_PRE, kg=80)
    with pytest.raises(Exception):
        Weight.objects.create(boxer=boxer, phase=TestResult.PHASE_PRE, kg=81)