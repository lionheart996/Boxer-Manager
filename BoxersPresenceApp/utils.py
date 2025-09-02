# BoxersPresenceApp/utils.py
from datetime import datetime, time, timedelta
from uuid import UUID

from dateutil.rrule import rrulestr
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from BoxersPresenceApp.models import Gym, Boxer


def user_gym(request_or_user):
    """Return the gym for the current user (fallback to first gym)."""
    user = getattr(request_or_user, "user", request_or_user)
    try:
        return user.coach_profile.gym
    except Exception:
        return Gym.objects.first()

def qs_boxers_for_user(user):
    """All boxers in the user's gym."""
    return Boxer.objects.filter(gym=user_gym(user))

def qs_my_boxers(user):
    """Boxers in my gym who are enrolled in a class I coach."""
    return (Boxer.objects
            .filter(gym=user_gym(user), enrollments__template__coaches=user)
            .distinct())

def resolve_boxer(user, identifier):
    """
    Resolve a boxer by pk (int), uuid (hex), or name (case-insensitive) within the user's gym.
    Raises ValidationError if the name is ambiguous.
    """
    qs = qs_boxers_for_user(user)
    s = (identifier or "").strip()
    if not s:
        raise ValidationError("No boxer specified.")
    if s.isdigit():
        return get_object_or_404(qs, pk=int(s))
    # try UUID
    try:
        return get_object_or_404(qs, uuid=UUID(s))
    except Exception:
        pass
    # fallback by name (may be ambiguous)
    matches = list(qs.filter(name__iexact=s)[:2])
    if not matches:
        raise ValidationError(f"No boxer named '{s}' in your gym.")
    if len(matches) > 1:
        raise ValidationError(f"Multiple boxers named '{s}'. Use the Boxer's UUID.")
    return matches[0]
def expand_rrule(rrule_str: str, start_date, end_date, default_hour=18, default_minute=0, duration_minutes=60):
    """
    Expand an RRULE between start_date and end_date (inclusive).
    Supports BYDAY and respects BYHOUR/BYMINUTE if present; otherwise uses defaults.
    Returns list of (start_dt, end_dt) naive datetimes.
    """
    # Parse simple keys so we know if BYHOUR/BYMINUTE were provided
    parts = {}
    for chunk in (rrule_str or "").split(";"):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            parts[k.upper()] = v

    rule = rrulestr(rrule_str, dtstart=datetime.combine(start_date, time(0, 0)))
    window_start = datetime.combine(start_date, time(0, 0))
    window_end   = datetime.combine(end_date,   time(23, 59))

    results = []
    for dt in rule.between(window_start, window_end, inc=True):
        # If BYHOUR/BYMINUTE absent, apply defaults; otherwise keep what RRULE produced
        hour = dt.hour if "BYHOUR" in parts else default_hour
        minute = dt.minute if "BYMINUTE" in parts else default_minute
        start_dt = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        results.append((start_dt, end_dt))
    return results