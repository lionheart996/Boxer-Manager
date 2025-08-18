import pytest
from django.test import Client

@pytest.mark.django_db
def test_home_requires_login():
    c = Client()
    resp = c.get('/')
    assert resp.status_code in (301, 302)  # redirect to login
