"""Services métier pour le système d'enchères."""

from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from auctions.models import Bid, Auction, Notification
from auctions.utils import log_action


class BidError(Exception):
    """Exception personnalisée pour les erreurs d'enchères."""
    pass


@transaction.atomic
def place_bid(user, auction, amount_cents):
    """
    Place une enchère sur une vente aux enchères.
    
    Args:
        user: L'utilisateur qui place l'enchère (User)
        auction: L'enchère cible (Auction)
        amount_cents: Le montant en centimes (int)
    
    Returns:
        Bid: L'objet Bid créé
    
    Raises:
        BidError: Si l'enchère ne peut pas être placée
    """
    # Verrouillage de ligne pour éviter les conditions de course
    auction = Auction.objects.select_for_update().get(pk=auction.pk)
    
    # Vérification 1: L'enchère doit être LIVE
    if auction.status != Auction.Status.LIVE:
        raise BidError(f"Cette enchère n'est pas active (statut: {auction.get_status_display()})")
    
    # Vérification 2: On ne peut pas enchérir sur son propre produit
    if user == auction.seller:
        raise BidError("Vous ne pouvez pas enchérir sur votre propre produit")
    
    # Vérification 3: L'utilisateur ne doit pas être bloqué
    if not user.is_active:
        raise BidError("Votre compte est bloqué")
    
    # Vérification 4: Montant minimum
    current_price = auction.current_price or auction.starting_price
    min_increment = auction.min_increment or 100  # 1€ par défaut
    
    if auction.current_price is None:
        # Premier bid: doit être >= starting_price
        if amount_cents < auction.starting_price:
            raise BidError(f"L'offre minimale est de {auction.starting_price / 100:.2f}€")
    else:
        # Bids suivants: doit être >= current_price + min_increment
        min_bid = current_price + min_increment
        if amount_cents < min_bid:
            raise BidError(f"L'offre minimale est de {min_bid / 100:.2f}€")
    
    # Récupérer l'ancien meilleur enchérisseur pour notification
    old_highest_bidder = None
    if auction.highest_bid:
        old_highest_bidder = auction.highest_bid.bidder
    
    # Créer le nouveau bid
    bid = Bid.objects.create(
        auction=auction,
        bidder=user,
        amount=amount_cents
    )
    
    # Mettre à jour l'enchère
    auction.current_price = amount_cents
    auction.highest_bid = bid
    
    # Anti-sniping: si moins de 3 minutes, prolonger de 3 minutes
    now = timezone.now()
    time_remaining = auction.end_at - now
    if time_remaining <= timedelta(minutes=3):
        auction.end_at = now + timedelta(minutes=3)
        log_action(
            actor=user,
            action='ANTI_SNIPING',
            target_type='Auction',
            target_id=auction.id,
            details={'new_end_at': str(auction.end_at)}
        )
    
    auction.save()
    
    # Notification au vendeur
    Notification.objects.create(
        user=auction.seller,
        type='NEW_BID',
        title='Nouvelle enchère',
        message=f'{user.username} a enchéri {amount_cents / 100:.2f}€ sur "{auction.title}"',
        related_object=bid
    )
    
    # Notification OUTBID à l'ancien meilleur enchérisseur
    if old_highest_bidder and old_highest_bidder != user:
        Notification.objects.create(
            user=old_highest_bidder,
            type='OUTBID',
            title='Enchère dépassée',
            message=f'Votre offre sur "{auction.title}" a été dépassée.',
            related_object=bid
        )
    
    # Log de l'action
    log_action(
        actor=user,
        action='PLACE_BID',
        target_type='Auction',
        target_id=auction.id,
        details={
            'amount': amount_cents,
            'auction': auction.title,
            'previous_price': current_price
        }
    )
    
    return bid


def get_auction_stats(auction):
    """
    Retourne les statistiques d'une enchère.
    
    Args:
        auction: L'objet Auction
    
    Returns:
        dict: Statistiques (nombre de bids, prix actuel, temps restant, etc.)
    """
    now = timezone.now()
    time_remaining = auction.end_at - now if auction.end_at > now else timedelta(0)
    
    return {
        'bid_count': auction.bids.count(),
        'current_price': auction.current_price or auction.starting_price,
        'highest_bidder': auction.highest_bid.bidder if auction.highest_bid else None,
        'time_remaining_seconds': int(time_remaining.total_seconds()),
        'is_ending_soon': time_remaining <= timedelta(minutes=5),
        'watchers_count': auction.watchlists.filter(is_active=True).count(),
    }


def cancel_auction(auction, admin_user, reason=None):
    """
    Annule une enchère (réservé aux admins).
    
    Args:
        auction: L'objet Auction à annuler
        admin_user: L'admin qui annule
        reason: Raison de l'annulation (optionnel)
    
    Returns:
        Auction: L'enchère modifiée
    """
    if auction.status in [Auction.Status.SOLD, Auction.Status.CANCELLED]:
        raise BidError(f"Cette enchère ne peut plus être annulée (statut: {auction.get_status_display()})")
    
    old_status = auction.status
    auction.status = Auction.Status.CANCELLED
    auction.save()
    
    # Notifier tous les enchérisseurs
    bidders = set(bid.bidder for bid in auction.bids.all())
    bidders.add(auction.seller)
    
    for bidder in bidders:
        Notification.objects.create(
            user=bidder,
            type='AUCTION_CANCELLED',
            title='Enchère annulée',
            message=f'L\'enchère "{auction.title}" a été annulée.' + (f' Raison: {reason}' if reason else ''),
            related_object=auction
        )
    
    log_action(
        actor=admin_user,
        action='CANCEL_AUCTION',
        target_type='Auction',
        target_id=auction.id,
        details={
            'old_status': old_status,
            'reason': reason
        }
    )
    
    return auction
