"""Commande pour traiter les changements de statut des enchères.

À exécuter régulièrement via cron (toutes les 30 secondes recommandé).
Exemple: */1 * * * * cd /path/to/project && python manage.py process_auctions
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from auctions.models import Auction, Notification, Bid
from auctions.utils import log_action


class Command(BaseCommand):
    help = "Traite les transitions de statut des enchères (SCHEDULED→LIVE, LIVE→SOLD/ENDED)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait fait sans modifier les données'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        now = timezone.now()
        
        self.stdout.write(f"Début du traitement à {now}")
        
        # Transition 1: SCHEDULED → LIVE
        scheduled_to_live = Auction.objects.filter(
            status=Auction.Status.SCHEDULED,
            start_at__lte=now
        ).select_related('seller')
        
        count_scheduled_to_live = scheduled_to_live.count()
        if dry_run:
            self.stdout.write(f"[DRY-RUN] {count_scheduled_to_live} enchères à passer en LIVE")
        else:
            for auction in scheduled_to_live:
                old_status = auction.status
                auction.status = Auction.Status.LIVE
                auction.save()
                
                # Notification au vendeur
                Notification.objects.create(
                    user=auction.seller,
                    type='AUCTION_LIVE',
                    title='Votre enchère est maintenant active',
                    message=f'"{auction.title}" est maintenant en cours.',
                    related_object=auction
                )
                
                # Notification aux watchlisteurs
                for watchlist in auction.watchlists.filter(is_active=True):
                    if watchlist.user != auction.seller:
                        Notification.objects.create(
                            user=watchlist.user,
                            type='WATCHED_AUCTION_LIVE',
                            title='Enchère suivie démarrée',
                            f'L\'enchère "{auction.title}" que vous suivez est maintenant active.',
                            related_object=auction
                        )
                
                log_action(
                    actor=None,  # Action système
                    action='STATUS_CHANGE',
                    target_type='Auction',
                    target_id=auction.id,
                    details={'from': str(old_status), 'to': 'LIVE'}
                )
                
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Auction #{auction.id} '{auction.title}' est maintenant LIVE")
                )
        
        # Transition 2: LIVE → SOLD/ENDED
        live_to_end = Auction.objects.filter(
            status=Auction.Status.LIVE,
            end_at__lte=now
        ).select_related('seller', 'highest_bid', 'highest_bid__bidder')
        
        count_live_to_end = live_to_end.count()
        if dry_run:
            self.stdout.write(f"[DRY-RUN] {count_live_to_end} enchères à clôturer")
        else:
            for auction in live_to_end:
                old_status = auction.status
                
                if auction.current_price and auction.highest_bid:
                    # Vérifier le reserve_price
                    if auction.reserve_price and auction.current_price < auction.reserve_price:
                        # Prix de réserve non atteint
                        auction.status = Auction.Status.UNSOLD
                        auction.save()
                        
                        # Notification au vendeur
                        Notification.objects.create(
                            user=auction.seller,
                            type='AUCTION_UNSOLD',
                            title='Prix de réserve non atteint',
                            message=f'"{auction.title}" n\'a pas atteint le prix minimum de {auction.reserve_price / 100:.2f}€',
                            related_object=auction
                        )
                    else:
                        # Vendu!
                        auction.status = Auction.Status.SOLD
                        auction.winner = auction.highest_bid.bidder
                        auction.save()
                        
                        # Notification au vendeur
                        Notification.objects.create(
                            user=auction.seller,
                            type='AUCTION_SOLD',
                            title='Enchère vendue!',
                            message=f'"{auction.title}" a été vendue pour {auction.current_price / 100:.2f}€',
                            related_object=auction
                        )
                        
                        # Notification au gagnant
                        if auction.highest_bid.bidder != auction.seller:
                            Notification.objects.create(
                                user=auction.highest_bid.bidder,
                                type='WON',
                                title='Vous avez gagné l\'enchère!',
                                message=f'Félicitations! Vous avez remporté "{auction.title}" pour {auction.current_price / 100:.2f}€',
                                related_object=auction
                            )
                        
                        # Notification aux autres enchérisseurs
                        bidders = set(bid.bidder for bid in auction.bids.all())
                        bidders.discard(auction.highest_bid.bidder)
                        bidders.discard(auction.seller)
                        
                        for bidder in bidders:
                            Notification.objects.create(
                                user=bidder,
                                type='OUTBID_FINAL',
                                title='Enchère terminée',
                                message=f'"{auction.title}" a été remportée par un autre enchérisseur.',
                                related_object=auction
                            )
                else:
                    # Aucune offre - terminé sans vente
                    auction.status = Auction.Status.ENDED
                    auction.save()
                    
                    # Notification au vendeur
                    Notification.objects.create(
                        user=auction.seller,
                        type='AUCTION_ENDED',
                        title='Enchère terminée sans vente',
                        message=f'"{auction.title}" s\'est terminée sans aucune offre.',
                        related_object=auction
                    )
                
                log_action(
                    actor=None,  # Action système
                    action='STATUS_CHANGE',
                    target_type='Auction',
                    target_id=auction.id,
                    details={
                        'from': str(old_status),
                        'to': str(auction.status),
                        'final_price': auction.current_price
                    }
                )
                
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Auction #{auction.id} '{auction.title}' est maintenant {auction.status}")
                )
        
        # Bonus: Notifications ENDING_SOON (5 minutes avant la fin)
        ending_soon = Auction.objects.filter(
            status=Auction.Status.LIVE,
            end_at__gt=now,
            end_at__lte=now + timedelta(minutes=5)
        ).exclude(
            pk__in=Auction.objects.filter(
                notifications__type='ENDING_SOON',
                notifications__created_at__gte=now - timedelta(hours=1)
            )
        ).distinct()
        
        count_ending_soon = ending_soon.count()
        if dry_run:
            self.stdout.write(f"[DRY-RUN] {count_ending_soon} enchères se terminent bientôt")
        else:
            for auction in ending_soon:
                # Notifier les watchlisteurs
                for watchlist in auction.watchlists.filter(is_active=True):
                    Notification.objects.create(
                        user=watchlist.user,
                        type='ENDING_SOON',
                        title='Se termine bientôt!',
                        message=f'"{auction.title}" se termine dans moins de 5 minutes!',
                        related_object=auction
                    )
                
                self.stdout.write(
                    self.style.WARNING(f"⏰ Auction #{auction.id} '{auction.title}' se termine bientôt")
                )
        
        total_processed = (count_scheduled_to_live if not dry_run else 0) + \
                         (count_live_to_end if not dry_run else 0)
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\nTraitement terminé. {total_processed} enchères traitées.\n"
                f"  - SCHEDULED→LIVE: {count_scheduled_to_live}\n"
                f"  - LIVE→SOLD/ENDED: {count_live_to_end}\n"
                f"  - Ending soon notifications: {count_ending_soon}"
            )
        )
