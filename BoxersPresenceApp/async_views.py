from django.http import JsonResponse, HttpRequest
from asgiref.sync import sync_to_async
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from .models import Boxer

@login_required
@require_GET
async def boxers_search(request: HttpRequest):
    """?q=abc — returns your boxers whose name contains q (case-insensitive)."""
    q = request.GET.get("q", "").strip()
    user = request.user

    def _query():
        qs = Boxer.objects.filter(coach=user)
        if q:
            qs = qs.filter(name__icontains=q)
        return list(qs.order_by("name").values("id", "name"))

    results = await sync_to_async(_query, thread_sensitive=True)()
    return JsonResponse({"results": results})