from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from auctions.models import Auction, Bid, Category, Notification, Watchlist
from django.utils import timezone
from datetime import timedelta
from io import StringIO

User = get_user_model()

class ProcessAuctionsCommandTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(username='seller', password='pass')
        cls.bidder = User.objects.create_user(username='bidder', password='pass')
        cls.watcher = User.objects.create_user(username='watcher', password='pass')
        cls.category = Category.objects.create(name='Test', slug='test')
    
    def test_scheduled_starts_when_time_comes(self):
        """SCHEDULED dont start_at est atteint → LIVE"""
        auction = Auction.objects.create(
            seller=self.seller, category=self.category,
            title='Scheduled', slug='scheduled-1',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(minutes=1),
            end_at=timezone.now() + timedelta(hours=1),
            status=Auction.Status.SCHEDULED
        )
        
        call_command('process_auctions')
        
        auction.refresh_from_db()
        self.assertEqual(auction.status, Auction.Status.LIVE)
    
    def test_scheduled_waits_if_start_in_future(self):
        """SCHEDULED dont start_at est futur → reste SCHEDULED"""
        auction = Auction.objects.create(
            seller=self.seller, category=self.category,
            title='Scheduled Future', slug='scheduled-2',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() + timedelta(hours=1),
            end_at=timezone.now() + timedelta(hours=2),
            status=Auction.Status.SCHEDULED
        )
        
        call_command('process_auctions')
        
        auction.refresh_from_db()
        self.assertEqual(auction.status, Auction.Status.SCHEDULED)
    
    def test_live_with_bids_ends_sold(self):
        """LIVE avec Bids dont end_at est atteint → SOLD + winner"""
        auction = Auction.objects.create(
            seller=self.seller, category=self.category,
            title='Live With Bids', slug='live-bids',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(hours=2),
            end_at=timezone.now() - timedelta(minutes=1),
            status=Auction.Status.LIVE,
            current_price=15000
        )
        Bid.objects.create(auction=auction, user=self.bidder, amount=15000)
        
        call_command('process_auctions')
        
        auction.refresh_from_db()
        self.assertEqual(auction.status, Auction.Status.SOLD)
        self.assertEqual(auction.winner, self.bidder)
    
    def test_live_without_bids_ends_ended(self):
        """LIVE sans Bids dont end_at est atteint → ENDED"""
        auction = Auction.objects.create(
            seller=self.seller, category=self.category,
            title='Live No Bids', slug='live-no-bids',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(hours=2),
            end_at=timezone.now() - timedelta(minutes=1),
            status=Auction.Status.LIVE
        )
        
        call_command('process_auctions')
        
        auction.refresh_from_db()
        self.assertEqual(auction.status, Auction.Status.ENDED)
        self.assertIsNone(auction.winner)
    
    def test_reserve_price_not_met_ends_ended(self):
        """Réserve non atteinte → ENDED même avec des bids"""
        auction = Auction.objects.create(
            seller=self.seller, category=self.category,
            title='Reserve Not Met', slug='reserve-not-met',
            description='Test', starting_price=10000, min_increment=500,
            reserve_price=20000,
            start_at=timezone.now() - timedelta(hours=2),
            end_at=timezone.now() - timedelta(minutes=1),
            status=Auction.Status.LIVE,
            current_price=15000
        )
        Bid.objects.create(auction=auction, user=self.bidder, amount=15000)
        
        call_command('process_auctions')
        
        auction.refresh_from_db()
        self.assertEqual(auction.status, Auction.Status.ENDED)
        self.assertIsNone(auction.winner)
    
    def test_reserve_price_met_ends_sold(self):
        """Réserve atteinte → SOLD"""
        auction = Auction.objects.create(
            seller=self.seller, category=self.category,
            title='Reserve Met', slug='reserve-met',
            description='Test', starting_price=10000, min_increment=500,
            reserve_price=15000,
            start_at=timezone.now() - timedelta(hours=2),
            end_at=timezone.now() - timedelta(minutes=1),
            status=Auction.Status.LIVE,
            current_price=20000
        )
        Bid.objects.create(auction=auction, user=self.bidder, amount=20000)
        
        call_command('process_auctions')
        
        auction.refresh_from_db()
        self.assertEqual(auction.status, Auction.Status.SOLD)
        self.assertEqual(auction.winner, self.bidder)
    
    def test_paused_auction_not_closed(self):
        """PAUSED n'est pas clôturé même si end_at atteint"""
        auction = Auction.objects.create(
            seller=self.seller, category=self.category,
            title='Paused', slug='paused',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(hours=2),
            end_at=timezone.now() - timedelta(minutes=1),
            status=Auction.Status.PAUSED
        )
        
        call_command('process_auctions')
        
        auction.refresh_from_db()
        self.assertEqual(auction.status, Auction.Status.PAUSED)
    
    def test_cancelled_auction_not_closed(self):
        """CANCELLED n'est pas clôturé"""
        auction = Auction.objects.create(
            seller=self.seller, category=self.category,
            title='Cancelled', slug='cancelled',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(hours=2),
            end_at=timezone.now() - timedelta(minutes=1),
            status=Auction.Status.CANCELLED
        )
        
        call_command('process_auctions')
        
        auction.refresh_from_db()
        self.assertEqual(auction.status, Auction.Status.CANCELLED)
    
    def test_winner_receives_won_notification(self):
        """Le gagnant reçoit une notification WON"""
        auction = Auction.objects.create(
            seller=self.seller, category=self.category,
            title='Won', slug='won-lc',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(hours=2),
            end_at=timezone.now() - timedelta(minutes=1),
            status=Auction.Status.LIVE,
            current_price=15000
        )
        Bid.objects.create(auction=auction, user=self.bidder, amount=15000)
        
        call_command('process_auctions')
        
        self.assertTrue(
            Notification.objects.filter(
                user=self.bidder,
                type='WON'
            ).exists()
        )
    
    def test_seller_and_watchers_notified(self):
        """Vendeur et suiveurs sont notifiés à la clôture"""
        auction = Auction.objects.create(
            seller=self.seller, category=self.category,
            title='Notified', slug='notified-lc',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(hours=2),
            end_at=timezone.now() - timedelta(minutes=1),
            status=Auction.Status.LIVE
        )
        Watchlist.objects.create(user=self.watcher, auction=auction)
        
        call_command('process_auctions')
        
        self.assertTrue(
            Notification.objects.filter(
                user=self.seller,
                type='ENDED'
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.watcher,
                type='ENDED'
            ).exists()
        )
    
    def test_ending_soon_notification_created(self):
        """ENDING_SOON créée pour les enchères se terminant dans < 1h"""
        auction = Auction.objects.create(
            seller=self.seller, category=self.category,
            title='Ending Soon', slug='ending-soon-lc',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(hours=1),
            end_at=timezone.now() + timedelta(minutes=30),
            status=Auction.Status.LIVE
        )
        Watchlist.objects.create(user=self.watcher, auction=auction)
        
        call_command('process_auctions')
        
        self.assertTrue(
            Notification.objects.filter(
                user=self.watcher,
                type='ENDING_SOON'
            ).exists()
        )
    
    def test_ending_soon_not_duplicated_on_second_run(self):
        """ENDING_SOON n'est pas dupliquée si la commande est relancée"""
        auction = Auction.objects.create(
            seller=self.seller, category=self.category,
            title='No Duplicate', slug='no-duplicate-lc',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(hours=1),
            end_at=timezone.now() + timedelta(minutes=30),
            status=Auction.Status.LIVE
        )
        Watchlist.objects.create(user=self.watcher, auction=auction)
        
        call_command('process_auctions')
        call_command('process_auctions')
        
        count = Notification.objects.filter(
            user=self.watcher,
            type='ENDING_SOON'
        ).count()
        self.assertEqual(count, 1)
    
    def test_sniped_auction_not_closed_prematurely(self):
        """Enchère prolongée par anti-sniping n'est pas clôturée"""
        auction = Auction.objects.create(
            seller=self.seller, category=self.category,
            title='Sniped', slug='sniped-lc',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(hours=1),
            end_at=timezone.now() + timedelta(minutes=5),
            status=Auction.Status.LIVE
        )
        
        call_command('process_auctions')
        
        auction.refresh_from_db()
        self.assertEqual(auction.status, Auction.Status.LIVE)
    
    def test_command_is_idempotent(self):
        """Deux exécutions consécutives ne créent pas de doublons"""
        auction = Auction.objects.create(
            seller=self.seller, category=self.category,
            title='Idempotent', slug='idempotent-lc',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(hours=2),
            end_at=timezone.now() - timedelta(minutes=1),
            status=Auction.Status.LIVE,
            current_price=15000  # Prix actuel > starting_price pour que ce soit SOLD
        )
        Bid.objects.create(auction=auction, user=self.bidder, amount=15000)
        
        call_command('process_auctions')
        call_command('process_auctions')
        
        count = Notification.objects.filter(
            user=self.bidder,
            type='WON'
        ).count()
        self.assertEqual(count, 1)
    
    def test_command_output_summary(self):
        """La commande affiche un résumé"""
        Auction.objects.create(
            seller=self.seller, category=self.category,
            title='Summary', slug='summary-lc',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(minutes=1),
            end_at=timezone.now() + timedelta(hours=1),
            status=Auction.Status.SCHEDULED
        )
        
        out = StringIO()
        call_command('process_auctions', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Démarrées', output)
    
    def test_api_time_returns_iso_json(self):
        """GET /api/time/ retourne du JSON avec server_time ISO"""
        from django.urls import reverse
        response = self.client.get(reverse('auctions:api_time'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        data = response.json()
        self.assertIn('server_time', data)
        from datetime import datetime
        datetime.fromisoformat(data['server_time'].replace('Z', '+00:00'))
