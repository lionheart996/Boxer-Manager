from rest_framework import serializers
from .models import Boxer, TestResult, Weight, BatteryTest


class BoxerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Boxer
        fields = ["id", "name", "coach"]

class TestSerializer(serializers.ModelSerializer):
    class Meta:
        model = BatteryTest
        fields = ["id", "name", "unit", "display_order", "coach", "description"]
        extra_kwargs = {"coach": {"write_only": True}}

class TestResultSerializer(serializers.ModelSerializer):
    boxer_name = serializers.CharField(source="boxer.name", read_only=True)
    test_name  = serializers.CharField(source="test.name",  read_only=True)

    class Meta:
        model = TestResult
        fields = [
            "id", "boxer", "test", "phase",
            "value1", "value2", "value3", "notes", "updated_at",
            "boxer_name", "test_name",
        ]

class WeightSerializer(serializers.ModelSerializer):
    boxer_name = serializers.CharField(source="boxer.name", read_only=True)

    class Meta:
        model = Weight
        fields = ["id","boxer","phase","kg","expected_kg","measured_at","updated_at","boxer_name"]