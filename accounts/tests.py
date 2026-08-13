from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.db import IntegrityError
from accounts.models import User

UserModel = get_user_model()


class UserModelTest(TestCase):
    """Tests pour le modèle User"""
    
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        cls.admin = User.objects.create_user(
            username='testadmin',
            email='admin@example.com',
            password='adminpass123',
            role=User.Role.ADMIN
        )
    
    def test_user_created_with_default_role(self):
        """Un utilisateur créé sans rôle explicite a le rôle USER par défaut"""
        self.assertEqual(self.user.role, User.Role.USER)
    
    def test_user_can_be_created_with_admin_role(self):
        """Un utilisateur peut être créé avec le rôle ADMIN"""
        self.assertEqual(self.admin.role, User.Role.ADMIN)
    
    def test_is_admin_method(self):
        """La méthode is_admin retourne True pour les admins"""
        self.assertFalse(self.user.is_admin())
        self.assertTrue(self.admin.is_admin())


class CategoryModelTest(TestCase):
    """Tests pour le modèle Category"""
    
    def test_category_name_unique(self):
        """Le nom de catégorie doit être unique"""
        from auctions.models import Category
        Category.objects.create(name='Électronique', slug='electronique')
        with self.assertRaises(IntegrityError):
            Category.objects.create(name='Électronique', slug='electronique-2')
    
    def test_category_slug_unique(self):
        """Le slug de catégorie doit être unique"""
        from auctions.models import Category
        Category.objects.create(name='Électronique', slug='electronique')
        with self.assertRaises(IntegrityError):
            Category.objects.create(name='Autre', slug='electronique')
    
    def test_category_auto_slug(self):
        """Le slug est généré automatiquement s'il n'est pas fourni"""
        from auctions.models import Category
        cat = Category.objects.create(name='Art Moderne')
        self.assertEqual(cat.slug, 'art-moderne')


class AuctionModelTest(TestCase):
    """Tests pour le modèle Auction"""
    
    @classmethod
    def setUpTestData(cls):
        from auctions.models import Category
        cls.seller = User.objects.create_user('seller', 'seller@test.com', 'pass123')
        cls.category = Category.objects.create(name='Test', slug='test')
        cls.now = timezone.now()
    
    def test_auction_default_status_is_pending(self):
        """Une enchère créée a le statut PENDING par défaut"""
        from auctions.models import Auction
        auction = Auction.objects.create(
            seller=self.seller,
            category=self.category,
            title='Test Auction',
            slug='test-auction',
            description='Test',
            starting_price=10000,
            min_increment=500,
            start_at=self.now,
            end_at=self.now + timedelta(hours=1)
        )
        self.assertEqual(auction.status, Auction.Status.PENDING)
    
    def test_auction_amounts_are_integers(self):
        """Les montants sont stockés en entiers (centimes)"""
        from auctions.models import Auction
        auction = Auction.objects.create(
            seller=self.seller,
            category=self.category,
            title='Test Auction',
            slug='test-auction-2',
            description='Test',
            starting_price=10000,  # 100 €
            min_increment=500,  # 5 €
            start_at=self.now,
            end_at=self.now + timedelta(hours=1)
        )
        self.assertIsInstance(auction.starting_price, int)
        self.assertIsInstance(auction.min_increment, int)
    
    def test_auction_index_exists(self):
        """Vérifier que l'index sur (status, end_at) existe"""
        from auctions.models import Auction
        indexes = Auction._meta.indexes
        index_fields = []
        for idx in indexes:
            if hasattr(idx, 'fields'):
                index_fields.append(idx.fields)
        self.assertIn(['status', 'end_at'], index_fields)
    
    def test_auction_slug_unique(self):
        """Le slug d'une enchère doit être unique"""
        from auctions.models import Auction
        Auction.objects.create(
            seller=self.seller,
            category=self.category,
            title='Test Auction',
            slug='unique-slug',
            description='Test',
            starting_price=10000,
            min_increment=500,
            start_at=self.now,
            end_at=self.now + timedelta(hours=1)
        )
        with self.assertRaises(IntegrityError):
            Auction.objects.create(
                seller=self.seller,
                category=self.category,
                title='Another Auction',
                slug='unique-slug',
                description='Test',
                starting_price=10000,
                min_increment=500,
                start_at=self.now,
                end_at=self.now + timedelta(hours=1)
            )


class BidModelTest(TestCase):
    """Tests pour le modèle Bid"""
    
    def test_bid_creation(self):
        """Création d'une enchère liée à une auction et un user"""
        from auctions.models import Category, Auction, Bid
        seller = User.objects.create_user('seller2', 'seller2@test.com', 'pass123')
        bidder = User.objects.create_user('bidder', 'bidder@test.com', 'pass123')
        category = Category.objects.create(name='Test', slug='test')
        now = timezone.now()
        
        auction = Auction.objects.create(
            seller=seller,
            category=category,
            title='Test Auction',
            slug='test-auction-bid',
            description='Test',
            starting_price=10000,
            min_increment=500,
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(hours=1),
            status=Auction.Status.LIVE
        )
        
        bid = Bid.objects.create(auction=auction, user=bidder, amount=10500)
        
        self.assertEqual(bid.auction, auction)
        self.assertEqual(bid.user, bidder)
        self.assertEqual(bid.amount, 10500)
    
    def test_bid_ordering(self):
        """Les enchères sont ordonnées par created_at décroissant"""
        from auctions.models import Category, Auction, Bid
        seller = User.objects.create_user('seller3', 'seller3@test.com', 'pass123')
        bidder = User.objects.create_user('bidder2', 'bidder2@test.com', 'pass123')
        category = Category.objects.create(name='Test2', slug='test2')
        now = timezone.now()
        
        auction = Auction.objects.create(
            seller=seller,
            category=category,
            title='Test Auction 2',
            slug='test-auction-bid-2',
            description='Test',
            starting_price=10000,
            min_increment=500,
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(hours=1),
            status=Auction.Status.LIVE
        )
        
        bid1 = Bid.objects.create(auction=auction, user=bidder, amount=10500)
        import time
        time.sleep(0.01)
        bid2 = Bid.objects.create(auction=auction, user=bidder, amount=11000)
        
        bids = list(Bid.objects.filter(auction=auction))
        self.assertEqual(bids[0], bid2)  # Plus récent en premier
        self.assertEqual(bids[1], bid1)


class WatchlistModelTest(TestCase):
    """Tests pour le modèle Watchlist"""
    
    def test_watchlist_unique_together(self):
        """Impossible de suivre deux fois la même enchère"""
        from auctions.models import Category, Auction, Watchlist
        seller = User.objects.create_user('seller4', 'seller4@test.com', 'pass123')
        watcher = User.objects.create_user('watcher', 'watcher@test.com', 'pass123')
        category = Category.objects.create(name='Test3', slug='test3')
        now = timezone.now()
        
        auction = Auction.objects.create(
            seller=seller,
            category=category,
            title='Test Auction 3',
            slug='test-auction-watch',
            description='Test',
            starting_price=10000,
            min_increment=500,
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(hours=1),
            status=Auction.Status.LIVE
        )
        
        Watchlist.objects.create(user=watcher, auction=auction)
        
        with self.assertRaises(IntegrityError):
            Watchlist.objects.create(user=watcher, auction=auction)


class AuditLogAndNotificationTest(TestCase):
    """Tests pour les modèles AuditLog et Notification"""
    
    def test_auditlog_creation_with_json_payload(self):
        """Création d'un AuditLog avec payload JSON valide"""
        from auctions.models import AuditLog
        user = User.objects.create_user('auditor', 'auditor@test.com', 'pass123')
        
        log = AuditLog.objects.create(
            actor=user,
            action='approve',
            target_type='Auction',
            target_id='1',
            details={'reason': 'Looks good', 'adjusted_price': 10000}
        )
        
        self.assertEqual(log.actor, user)
        self.assertEqual(log.action, 'approve')
        self.assertEqual(log.details['reason'], 'Looks good')
    
    def test_notification_creation_with_json_payload(self):
        """Création d'une Notification avec payload JSON valide"""
        from auctions.models import Notification
        user = User.objects.create_user('notify_user', 'notify@test.com', 'pass123')
        
        notification = Notification.objects.create(
            user=user,
            type=Notification.Type.OUTBID,
            payload={'auction_id': 1, 'auction_title': 'Test'}
        )
        
        self.assertEqual(notification.user, user)
        self.assertEqual(notification.type, Notification.Type.OUTBID)
        self.assertEqual(notification.payload['auction_id'], 1)
