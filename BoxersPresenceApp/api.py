from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Avg, Max, Min
from .models import Boxer, BatteryTest, TestResult, Weight
from .serializers import (
    BoxerSerializer, TestSerializer, TestResultSerializer, WeightSerializer
)

class IsCoach(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    def has_object_permission(self, request, view, obj):
        coach = getattr(obj, "coach", None)
        if coach is None and hasattr(obj, "boxer"):
            coach = getattr(obj.boxer, "coach", None)
        return coach == request.user

class BoxerViewSet(viewsets.ModelViewSet):
    serializer_class = BoxerSerializer
    permission_classes = [IsCoach]
    def get_queryset(self):
        return Boxer.objects.filter(coach=self.request.user).order_by("name")
    def perform_create(self, serializer):
        serializer.save(coach=self.request.user)

class TestViewSet(viewsets.ModelViewSet):
    serializer_class = TestSerializer
    permission_classes = [IsCoach]
    def get_queryset(self):
        return BatteryTest.objects.filter(coach=self.request.user).order_by("display_order", "name")
    def perform_create(self, serializer):
        serializer.save(coach=self.request.user)

class TestResultViewSet(viewsets.ModelViewSet):
    serializer_class = TestResultSerializer
    permission_classes = [IsCoach]
    def get_queryset(self):
        return (TestResult.objects
                .filter(boxer__coach=self.request.user)
                .select_related("boxer", "test"))

    @action(detail=False, methods=["get"])
    def summary(self, request):
        qs = self.get_queryset()
        data = qs.values("test__name", "phase").annotate(avg_value1=Avg("value1"))
        return Response(list(data))

class WeightViewSet(viewsets.ModelViewSet):
    serializer_class = WeightSerializer
    permission_classes = [IsCoach]
    def get_queryset(self):
        return Weight.objects.filter(boxer__coach=self.request.user).select_related("boxer")