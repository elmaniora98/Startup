from functools import wraps
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from accounts.models import User


def admin_required(view_func):
    """
    Décorateur qui vérifie que l'utilisateur est authentifié
    et possède le rôle ADMIN (et non simplement is_staff).
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request.user, 'role') or request.user.role != User.Role.ADMIN:
            return HttpResponseForbidden("Accès réservé aux administrateurs Enchère+.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
