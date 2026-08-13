from auctions.models import AuditLog


def log_action(actor, action, target_type, target_id, details=None):
    """
    Fonction utilitaire pour journaliser une action dans l'AuditLog.
    
    Args:
        actor: L'utilisateur qui a effectué l'action (peut être None)
        action: Le nom de l'action (ex: APPROVE_AUCTION, REJECT_AUCTION)
        target_type: Le type de cible (ex: Auction, User)
        target_id: L'ID de la cible
        details: Un dictionnaire JSON avec les détails de l'action
    """
    if details is None:
        details = {}
    
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        details=details
    )
