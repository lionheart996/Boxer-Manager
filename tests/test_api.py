import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from BoxersPresenceApp.models import Boxer, BatteryTest, TestResult

@pytest.mark.django_db
def test_api_requires_auth():
    client = APIClient()
    resp = client.get('/api/boxers/')
    assert resp.status_code in (401, 403)

@pytest.mark.django_db
def test_boxer_crud_list_and_create():
    user = User.objects.create_user(username="coach", password="x")
    client = APIClient()
    client.login(username="coach", password="x")
    resp = client.post('/api/boxers/', {"name": "Rocky"})
    assert resp.status_code == 201, resp.content
    resp = client.get('/api/boxers/')
    assert resp.status_code == 200
    assert any(row["name"] == "Rocky" for row in resp.json())

@pytest.mark.django_db
def test_results_summary_endpoint():
    user = User.objects.create_user(username="coach", password="x")
    client = APIClient()
    client.login(username="coach", password="x")

    boxer = Boxer.objects.create(name="Frazier", coach=user)
    t = BatteryTest.objects.create(name="Pushups", coach=user, unit="reps")

    TestResult.objects.create(boxer=boxer, test=t, phase=TestResult.PHASE_PRE,     value1=30)
    TestResult.objects.create(boxer=boxer, test=t, phase=TestResult.PHASE_BEFORE, value1=45)

    resp = client.get('/api/results/summary/')
    assert resp.status_code == 200
    payload = resp.json()
    assert any(row["test__name"] == "Pushups" for row in payload)