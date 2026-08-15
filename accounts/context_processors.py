from accounts.models import CustomUser


def unread_count(request):
    """Context processor pour le nombre de notifications non lues."""
    if request.user.is_authenticated:
        count = request.user.notifications.filter(read_at__isnull=True).count()
        return {'unread_count': count}
    return {'unread_count': 0}
