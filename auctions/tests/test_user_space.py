from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from auctions.models import Auction, Bid, Category, Notification, Watchlist
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class UserSpaceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='user', password='pass')
        cls.other = User.objects.create_user(username='other', password='pass')
        cls.category = Category.objects.create(name='Test', slug='test')
        
        cls.live_auction = Auction.objects.create(
            seller=cls.other, category=cls.category,
            title='Live', slug='live-us',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(hours=1),
            end_at=timezone.now() + timedelta(hours=1),
            status=Auction.Status.LIVE, current_price=15000
        )
        Bid.objects.create(auction=cls.live_auction, user=cls.user, amount=10000)
        Bid.objects.create(auction=cls.live_auction, user=cls.other, amount=15000)
        
        cls.won_auction = Auction.objects.create(
            seller=cls.other, category=cls.category,
            title='Won', slug='won-us',
            description='Test', starting_price=10000, min_increment=500,
            status=Auction.Status.SOLD, current_price=20000,
            winner=cls.user
        )
    
    def test_dashboard_shows_live_with_status(self):
        """Dashboard affiche les enchères LIVE avec statut"""
        self.client.login(username='user', password='pass')
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.status_code, 200)
    
    def test_overbid_button_visibility(self):
        """Bouton Surenchérir visible si surenchéri"""
        self.client.login(username='user', password='pass')
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertContains(response, 'Surenchérir')
    
    def test_won_auctions_section(self):
        """Section Remportées affiche les enchères gagnées"""
        self.client.login(username='user', password='pass')
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertContains(response, 'Won')
        self.assertContains(response, '200,00')
    
    def test_dashboard_isolation(self):
        """Dashboard n'affiche que les enchères de l'utilisateur"""
        self.client.login(username='other', password='pass')
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.status_code, 200)
    
    def test_dashboard_anonymous_redirect(self):
        """Anonyme → redirection login"""
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.status_code, 302)
    
    def test_watchlist_toggle_create_delete(self):
        """Toggle watchlist crée/supprime"""
        self.client.login(username='user', password='pass')
        
        self.client.post(
            reverse('auctions:api_toggle_watchlist', kwargs={'pk': self.live_auction.pk})
        )
        self.assertTrue(Watchlist.objects.filter(user=self.user, auction=self.live_auction).exists())
        
        self.client.post(
            reverse('auctions:api_toggle_watchlist', kwargs={'pk': self.live_auction.pk})
        )
        self.assertFalse(Watchlist.objects.filter(user=self.user, auction=self.live_auction).exists())
    
    def test_watch_button_state_reflection(self):
        """Bouton détail reflète l'état watchlist"""
        self.client.login(username='user', password='pass')
        response = self.client.get(reverse('auctions:detail', kwargs={'slug': 'live-us'}))
        self.assertContains(response, 'Suivre')
        
        Watchlist.objects.create(user=self.user, auction=self.live_auction)
        response = self.client.get(reverse('auctions:detail', kwargs={'slug': 'live-us'}))
        self.assertContains(response, 'Ne plus suivre')
    
    def test_followed_page_isolation(self):
        """Page suivis n'affiche que les enchères suivies par l'utilisateur"""
        Watchlist.objects.create(user=self.user, auction=self.live_auction)
        
        self.client.login(username='user', password='pass')
        response = self.client.get(reverse('accounts:watchlist'))
        self.assertEqual(response.status_code, 200)
        
        self.client.login(username='other', password='pass')
        response = self.client.get(reverse('accounts:watchlist'))
        self.assertEqual(response.status_code, 200)
    
    def test_watch_anonymous_redirect(self):
        """Watch anonyme → redirection login"""
        response = self.client.post(
            reverse('auctions:api_toggle_watchlist', kwargs={'pk': self.live_auction.pk})
        )
        self.assertEqual(response.status_code, 302)
    
    def test_watch_ended_auction_refused(self):
        """Watch sur enchère terminée → refusé"""
        ended = Auction.objects.create(
            seller=self.other, category=self.category,
            title='Ended', slug='ended-us',
            description='Test', starting_price=10000, min_increment=500,
            status=Auction.Status.ENDED
        )
        
        self.client.login(username='user', password='pass')
        self.client.post(
            reverse('auctions:api_toggle_watchlist', kwargs={'pk': ended.pk})
        )
        self.assertFalse(Watchlist.objects.filter(user=self.user, auction=ended).exists())
    
    def test_notification_badge_count(self):
        """Badge cloche affiche le bon nombre"""
        Notification.objects.create(user=self.user, type='OUTBID', payload={})
        Notification.objects.create(user=self.user, type='WON', payload={})
        Notification.objects.create(user=self.user, type='ENDED', payload={}, read_at=timezone.now())
        
        self.client.login(username='user', password='pass')
        response = self.client.get(reverse('auctions:home'))
        self.assertContains(response, '2')
    
    def test_notification_french_messages(self):
        """Messages de notification en français"""
        Notification.objects.create(
            user=self.user,
            type='OUTBID',
            payload={'title': 'Test', 'amount': 15000}
        )
        
        self.client.login(username='user', password='pass')
        response = self.client.get(reverse('accounts:notifications'))
        self.assertContains(response, 'surenchéri')
    
    def test_notification_isolation(self):
        """Notifications isolées par utilisateur"""
        Notification.objects.create(user=self.user, type='WON', payload={})
        
        self.client.login(username='other', password='pass')
        response = self.client.get(reverse('accounts:notifications'))
        self.assertEqual(len(response.context['notifications']), 0)
    
    def test_mark_all_as_read(self):
        """Tout marquer comme lu"""
        Notification.objects.create(user=self.user, type='OUTBID', payload={})
        Notification.objects.create(user=self.user, type='WON', payload={})
        
        self.client.login(username='user', password='pass')
        self.client.post(reverse('accounts:mark_all_as_read'))
        
        unread = Notification.objects.filter(user=self.user, read_at__isnull=True).count()
        self.assertEqual(unread, 0)
    
    def test_mark_single_as_read(self):
        """Marquer une seule notification comme lue"""
        notif = Notification.objects.create(user=self.user, type='OUTBID', payload={})
        
        self.client.login(username='user', password='pass')
        self.client.post(reverse('accounts:mark_as_read', kwargs={'pk': notif.pk}))
        
        notif.refresh_from_db()
        self.assertIsNotNone(notif.read_at)
    
    def test_notification_link_marks_read(self):
        """Cliquer sur une notification la marque lue"""
        notif = Notification.objects.create(
            user=self.user,
            type='WON',
            payload={'auction_id': self.won_auction.pk}
        )
        
        self.client.login(username='user', password='pass')
        self.client.get(reverse('accounts:notifications'))
        self.client.get(reverse('auctions:detail', kwargs={'slug': 'won-us'}))
        
        notif.refresh_from_db()
        self.assertIsNotNone(notif.read_at)
    
    def test_notifications_anonymous_redirect(self):
        """Notifications anonyme → redirection login"""
        response = self.client.get(reverse('accounts:notifications'))
        self.assertEqual(response.status_code, 302)
    
    def test_price_block_content(self):
        """price_block retourne prix, count, min suggéré"""
        response = self.client.get(
            reverse('auctions:api_price_block', kwargs={'pk': self.live_auction.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '150,00')
        self.assertContains(response, '155,00')
    
    def test_price_block_sold_state(self):
        """price_block SOLD affiche gagnant"""
        response = self.client.get(
            reverse('auctions:api_price_block', kwargs={'pk': self.won_auction.pk})
        )
        self.assertContains(response, 'Vendue')
    
    def test_price_block_scheduled_state(self):
        """price_block SCHEDULED affiche état"""
        scheduled = Auction.objects.create(
            seller=self.other, category=self.category,
            title='Scheduled', slug='scheduled-us',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=2),
            status=Auction.Status.SCHEDULED
        )
        
        response = self.client.get(
            reverse('auctions:api_price_block', kwargs={'pk': scheduled.pk})
        )
        self.assertContains(response, 'Programmée')
    
    def test_htmx_polling_attributes_conditional(self):
        """hx-trigger présent uniquement si LIVE"""
        response = self.client.get(reverse('auctions:detail', kwargs={'slug': 'live-us'}))
        self.assertContains(response, 'hx-trigger="every 3s"')
        
        response = self.client.get(reverse('auctions:detail', kwargs={'slug': 'won-us'}))
        self.assertNotContains(response, 'hx-trigger="every 3s"')
    
    def test_bids_history_fragment_standalone(self):
        """Fragment historique accessible seul"""
        response = self.client.get(
            reverse('auctions:api_bids_history', kwargs={'pk': self.live_auction.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<!DOCTYPE html>')
