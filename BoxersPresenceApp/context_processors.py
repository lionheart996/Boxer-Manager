from .models import ParentProfile

def role_flags(request):
    is_parent = False
    if getattr(request, "user", None) and request.user.is_authenticated:
        try:
            # accessing reverse OneToOne safely
            request.user.parent_profile
            is_parent = True
        except ParentProfile.DoesNotExist:
            pass
    return {"is_parent": is_parent}