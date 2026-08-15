from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from auctions.models import Auction, Category, Bid
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class AuctionDetailViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(username='seller', password='pass')
        cls.other_user = User.objects.create_user(username='other', password='pass')
        cls.admin = User.objects.create_user(username='admin', password='pass', role=User.Role.ADMIN)
        cls.category = Category.objects.create(name='Test', slug='test')
        
        cls.live_auction = Auction.objects.create(
            seller=cls.seller, category=cls.category,
            title='Live Auction', slug='live-auction',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(hours=1),
            end_at=timezone.now() + timedelta(hours=1),
            status=Auction.Status.LIVE, current_price=10000
        )
        
        cls.pending_auction = Auction.objects.create(
            seller=cls.seller, category=cls.category,
            title='Pending Auction', slug='pending-auction',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=2),
            status=Auction.Status.PENDING
        )
        
        cls.rejected_auction = Auction.objects.create(
            seller=cls.seller, category=cls.category,
            title='Rejected Auction', slug='rejected-auction',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(days=2),
            end_at=timezone.now() - timedelta(days=1),
            status=Auction.Status.REJECTED,
            rejection_reason='Motif de rejet'
        )
    
    def test_live_auction_accessible_by_anonymous(self):
        """Une enchère LIVE est accessible par un anonyme"""
        response = self.client.get(reverse('auctions:detail', kwargs={'slug': 'live-auction'}))
        self.assertEqual(response.status_code, 200)
    
    def test_live_contains_title_and_iso_date(self):
        """Une enchère LIVE contient le titre et data-end-at ISO"""
        response = self.client.get(reverse('auctions:detail', kwargs={'slug': 'live-auction'}))
        self.assertContains(response, 'Live Auction')
        self.assertContains(response, 'data-end-at=')
    
    def test_live_price_displayed_in_euros(self):
        """Le prix est affiché en euros (pas en centimes)"""
        response = self.client.get(reverse('auctions:detail', kwargs={'slug': 'live-auction'}))
        self.assertContains(response, '100,00')  # 10000 centimes = 100 €
    
    def test_pending_auction_404_for_anonymous(self):
        """Une enchère PENDING retourne 404 pour un anonyme"""
        response = self.client.get(reverse('auctions:detail', kwargs={'slug': 'pending-auction'}))
        self.assertEqual(response.status_code, 404)
    
    def test_pending_auction_404_for_other_user(self):
        """Une enchère PENDING retourne 404 pour un autre utilisateur"""
        self.client.login(username='other', password='pass')
        response = self.client.get(reverse('auctions:detail', kwargs={'slug': 'pending-auction'}))
        self.assertEqual(response.status_code, 404)
    
    def test_pending_auction_200_for_seller(self):
        """Une enchère PENDING est accessible par le vendeur"""
        self.client.login(username='seller', password='pass')
        response = self.client.get(reverse('auctions:detail', kwargs={'slug': 'pending-auction'}))
        self.assertEqual(response.status_code, 200)
    
    def test_pending_auction_200_for_admin(self):
        """Une enchère PENDING est accessible par un admin"""
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('auctions:detail', kwargs={'slug': 'pending-auction'}))
        self.assertEqual(response.status_code, 200)
    
    def test_rejected_auction_404_for_anonymous(self):
        """Une enchère REJECTED retourne 404 pour un anonyme"""
        response = self.client.get(reverse('auctions:detail', kwargs={'slug': 'rejected-auction'}))
        self.assertEqual(response.status_code, 404)
    
    def test_nonexistent_slug_404(self):
        """Un slug inexistant retourne 404"""
        response = self.client.get(reverse('auctions:detail', kwargs={'slug': 'nonexistent'}))
        self.assertEqual(response.status_code, 404)
    
    def test_similar_products_same_category_only(self):
        """Les produits similaires sont de la même catégorie"""
        other_cat = Category.objects.create(name='Other', slug='other')
        other_auction = Auction.objects.create(
            seller=self.seller, category=other_cat,
            title='Other', slug='other', description='Test',
            starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(hours=1),
            end_at=timezone.now() + timedelta(hours=1),
            status=Auction.Status.LIVE
        )
        response = self.client.get(reverse('auctions:detail', kwargs={'slug': 'live-auction'}))
        similar = response.context.get('similar_auctions', [])
        self.assertNotIn(other_auction, similar)
    
    def test_similar_products_excludes_current(self):
        """Les produits similaires excluent l'enchère courante"""
        response = self.client.get(reverse('auctions:detail', kwargs={'slug': 'live-auction'}))
        similar = response.context.get('similar_auctions', [])
        self.assertNotIn(self.live_auction, similar)
    
    def test_similar_products_max_four(self):
        """Maximum 4 produits similaires"""
        for i in range(5):
            Auction.objects.create(
                seller=self.seller, category=self.category,
                title=f'Similar {i}', slug=f'similar-{i}',
                description='Test', starting_price=10000, min_increment=500,
                start_at=timezone.now() - timedelta(hours=1),
                end_at=timezone.now() + timedelta(hours=1),
                status=Auction.Status.LIVE
            )
        response = self.client.get(reverse('auctions:detail', kwargs={'slug': 'live-auction'}))
        similar = response.context.get('similar_auctions', [])
        self.assertLessEqual(len(similar), 4)
