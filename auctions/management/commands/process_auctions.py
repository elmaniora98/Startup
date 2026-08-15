from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from auctions.models import Auction, Bid, Notification, Watchlist
from django.db import transaction
from django.db.models import Q

class Command(BaseCommand):
    help = "Gère le cycle de vie des enchères (SCHEDULED → LIVE → SOLD/ENDED)"

    def handle(self, *args, **options):
        now = timezone.now()
        
        # Démarrer les enchères SCHEDULED dont le start_at est atteint
        scheduled_to_live = Auction.objects.filter(
            status=Auction.Status.SCHEDULED,
            start_at__lte=now
        )
        for auction in scheduled_to_live:
            auction.status = Auction.Status.LIVE
            auction.save()
            self.stdout.write(f"Démarrées : {auction.title}")
        
        # Clôturer les enchères LIVE dont le end_at est atteint
        live_to_close = Auction.objects.filter(
            status=Auction.Status.LIVE,
            end_at__lte=now
        )
        
        for auction in live_to_close:
            with transaction.atomic():
                # Vérifier si le prix de réserve est atteint
                if auction.reserve_price and (auction.current_price or 0) < auction.reserve_price:
                    auction.status = Auction.Status.ENDED
                    auction.save()
                    self.stdout.write(f"Terminée (réserve non atteinte) : {auction.title}")
                elif (auction.current_price or 0) > auction.starting_price:
                    # Il y a eu des enchères → VENDU
                    highest_bid = Bid.objects.filter(auction=auction).order_by('-amount').first()
                    if highest_bid:
                        auction.status = Auction.Status.SOLD
                        auction.winner = highest_bid.user
                        auction.save()
                        
                        # Notification au gagnant
                        Notification.objects.create(
                            user=highest_bid.user,
                            type='WON',
                            payload={'auction_id': auction.pk, 'title': auction.title}
                        )
                        self.stdout.write(f"Vendue : {auction.title} à {highest_bid.user.username}")
                else:
                    # Pas d'enchères → TERMINÉE
                    auction.status = Auction.Status.ENDED
                    auction.save()
                    self.stdout.write(f"Terminée (sans enchères) : {auction.title}")
                
                # Notifier le vendeur et les suiveurs
                Notification.objects.create(
                    user=auction.seller,
                    type='ENDED',
                    payload={'auction_id': auction.pk, 'title': auction.title}
                )
                
                watchers = Watchlist.objects.filter(auction=auction)
                for watcher in watchers:
                    Notification.objects.create(
                        user=watcher.user,
                        type='ENDED',
                        payload={'auction_id': auction.pk, 'title': auction.title}
                    )
        
        # Notifications ENDING_SOON pour les enchères se terminant dans < 1h
        ending_soon = Auction.objects.filter(
            status=Auction.Status.LIVE,
            end_at__gt=now,
            end_at__lte=now + timedelta(hours=1)
        )
        
        for auction in ending_soon:
            watchers = Watchlist.objects.filter(auction=auction)
            for watcher in watchers:
                # Éviter les doublons - vérifier par titre d'enchère dans le payload
                existing_count = Notification.objects.filter(
                    user=watcher.user,
                    type='ENDING_SOON',
                    payload__icontains=f'"title": "{auction.title}"'
                ).count()
                
                if existing_count == 0:
                    Notification.objects.create(
                        user=watcher.user,
                        type='ENDING_SOON',
                        payload={'auction_id': auction.pk, 'title': auction.title}
                    )
        
        self.stdout.write(self.style.SUCCESS("Cycle de vie traité avec succès"))
