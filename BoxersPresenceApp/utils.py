# BoxersPresenceApp/utils.py
from datetime import datetime, time, timedelta, date
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

IBA_WEIGHT_CLASSES = {
    # ---------------- MEN ----------------
    ("M", "JUNIOR"): [
        ("Pinweight", 44.0, 46.0),
        ("Light Flyweight", 46.0, 48.0),
        ("Flyweight", 48.0, 50.0),
        ("Light Bantamweight", 50.0, 52.0),
        ("Bantamweight", 52.0, 54.0),
        ("Featherweight", 54.0, 57.0),
        ("Lightweight", 57.0, 60.0),
        ("Light Welterweight", 60.0, 63.0),
        ("Welterweight", 63.0, 66.0),
        ("Light Middleweight", 66.0, 70.0),
        ("Middleweight", 70.0, 75.0),
        ("Light Heavyweight", 75.0, 80.0),
        ("Heavyweight", 80.0, 999.0),
    ],
    ("M", "YOUTH"): [
        ("Minimumweight", 46.0, 48.0),
        ("Flyweight", 48.0, 51.0),
        ("Bantamweight", 51.0, 54.0),
        ("Featherweight", 54.0, 57.0),
        ("Lightweight", 57.0, 60.0),
        ("Light Welterweight", 60.0, 63.5),
        ("Welterweight", 63.5, 67.0),
        ("Light Middleweight", 67.0, 71.0),
        ("Middleweight", 71.0, 75.0),
        ("Light Heavyweight", 75.0, 80.0),
        ("Cruiserweight", 80.0, 86.0),
        ("Heavyweight", 86.0, 92.0),
        ("Super Heavyweight", 92.0, 999.0),
    ],
    ("M", "ELITE"): [  # same as Youth
        ("Minimumweight", 46.0, 48.0),
        ("Flyweight", 48.0, 51.0),
        ("Bantamweight", 51.0, 54.0),
        ("Featherweight", 54.0, 57.0),
        ("Lightweight", 57.0, 60.0),
        ("Light Welterweight", 60.0, 63.5),
        ("Welterweight", 63.5, 67.0),
        ("Light Middleweight", 67.0, 71.0),
        ("Middleweight", 71.0, 75.0),
        ("Light Heavyweight", 75.0, 80.0),
        ("Cruiserweight", 80.0, 86.0),
        ("Heavyweight", 86.0, 92.0),
        ("Super Heavyweight", 92.0, 999.0),
    ],

    # ---------------- WOMEN ----------------
    ("F", "JUNIOR"): [
        ("Pinweight", 44.0, 46.0),
        ("Light Flyweight", 46.0, 48.0),
        ("Flyweight", 48.0, 50.0),
        ("Light Bantamweight", 50.0, 52.0),
        ("Bantamweight", 52.0, 54.0),
        ("Featherweight", 54.0, 57.0),
        ("Lightweight", 57.0, 60.0),
        ("Light Welterweight", 60.0, 63.0),
        ("Welterweight", 63.0, 66.0),
        ("Light Middleweight", 66.0, 70.0),
        ("Middleweight", 70.0, 75.0),
        ("Light Heavyweight", 75.0, 80.0),
        ("Heavyweight", 80.0, 999.0),
    ],
    ("F", "YOUTH"): [
        ("Minimumweight", 45.0, 48.0),
        ("Flyweight", 48.0, 50.0),
        ("Bantamweight", 50.0, 52.0),
        ("Featherweight", 52.0, 54.0),
        ("Lightweight", 54.0, 57.0),
        ("Light Welterweight", 57.0, 60.0),
        ("Welterweight", 60.0, 63.0),
        ("Light Middleweight", 63.0, 66.0),
        ("Middleweight", 66.0, 70.0),
        ("Light Heavyweight", 70.0, 75.0),
        ("Heavyweight", 75.0, 81.0),
        ("Super Heavyweight", 81.0, 999.0),
    ],
    ("F", "ELITE"): [  # same as Youth
        ("Minimumweight", 45.0, 48.0),
        ("Flyweight", 48.0, 50.0),
        ("Bantamweight", 50.0, 52.0),
        ("Featherweight", 52.0, 54.0),
        ("Lightweight", 54.0, 57.0),
        ("Light Welterweight", 57.0, 60.0),
        ("Welterweight", 60.0, 63.0),
        ("Light Middleweight", 63.0, 66.0),
        ("Middleweight", 66.0, 70.0),
        ("Light Heavyweight", 70.0, 75.0),
        ("Heavyweight", 75.0, 81.0),
        ("Super Heavyweight", 81.0, 999.0),
    ],
}


def calc_age(dob):
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def age_band(age):
    if age is None:
        return None
    if 15 <= age <= 16:
        return "JUNIOR"
    if 17 <= age <= 18:
        return "YOUTH"
    if age >= 19:
        return "ELITE"
    return None


def olympic_weight_class(kg, gender_code, age):
    """
    Returns the IBA (Olympic) weight class label.

    Example outputs:
        "Lightweight (57–60kg)"
        "Below minimum"
        "Super Heavyweight (92kg+)"
    """

    if kg is None:
        return None  # no weight recorded

    # Unspecified gender defaults to Male
    gender = "M" if gender_code in (None, "U") else gender_code

    # Determine the correct age group (Junior / Youth / Elite)
    band = age_band(age)
    if not band:
        return None  # too young or unknown age

    # Get all classes for gender/age band
    classes = IBA_WEIGHT_CLASSES.get((gender, band))
    if not classes:
        return None

    # Too light
    if kg < classes[0][1]:
        return "Below minimum"

    # Too heavy
    if kg > classes[-1][2]:
        # use lower bound of last class for proper "+"
        top_class_name, top_low, _ = classes[-1]
        return f"{top_class_name} ({int(top_low)}kg+)"

    # Find the right range
    for name, low, high in classes:
        if low <= kg <= high:
            if high >= 999:  # last open-ended class
                return f"{name} ({int(low)}kg+)"
            else:
                return f"{name} ({int(low)}–{int(high)}kg)"

    return None
