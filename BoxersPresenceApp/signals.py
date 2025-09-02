from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import CoachProfile, Gym


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_update_coach_profile(sender, instance, created, **kwargs):
    if created:
        # Create profile once on first user creation
        profile, _ = CoachProfile.objects.get_or_create(user=instance)
        # Optional: attach a default gym only on initial creation
        default_gym, _ = Gym.get_or_create(name="Default Gym") if hasattr(Gym, "objects") else (None, False)
        if default_gym and profile.gym is None:
            profile.gym = default_gym
            profile.save()
    else:
        # Do NOT create-on-update; only save if it exists
        try:
            instance.coach_profile.save()
        except CoachProfile.DoesNotExist:
            # Leave creation to the admin inline the user is submitting
            pass