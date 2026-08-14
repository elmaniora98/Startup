"""Context processors pour injecter des données dans tous les templates."""

from auctions.models import Notification


def unread_count(request):
    """
    Injecte le nombre de notifications non lues dans le contexte.
    Disponible dans tous les templates via {{ unread_count }}.
    """
    if request.user.is_authenticated:
        count = Notification.objects.filter(
            user=request.user,
            read_at__isnull=True
        ).count()
        return {'unread_count': count}
    return {'unread_count': 0}
