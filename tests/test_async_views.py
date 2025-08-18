import pytest
from django.contrib.auth.models import User
from django.test import AsyncClient, Client
from asgiref.sync import sync_to_async
from BoxersPresenceApp.models import Boxer

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_async_boxers_search():
    user = await sync_to_async(User.objects.create_user)(username="coach", password="x")
    await sync_to_async(Boxer.objects.create)(name="Manny", coach=user)
    await sync_to_async(Boxer.objects.create)(name="Mayweather", coach=user)

    # login on sync client in a thread, copy cookies
    sync_client = Client()
    await sync_to_async(sync_client.login)(username="coach", password="x")

    async_client = AsyncClient()
    async_client.cookies = sync_client.cookies

    resp = await async_client.get('/async/boxers-search/?q=man')
    assert resp.status_code == 200
    names = [r["name"] for r in resp.json()["results"]]
    assert "Manny" in names