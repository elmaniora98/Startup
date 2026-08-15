from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from auctions.models import Auction, Category, AuditLog, Watchlist, Notification
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class AdminAdvancedTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='admin', password='pass', role=User.Role.ADMIN)
        cls.user = User.objects.create_user(username='user', password='pass')
        cls.category = Category.objects.create(name='Test', slug='test')
        
        cls.live_auction = Auction.objects.create(
            seller=cls.user, category=cls.category,
            title='Live', slug='live-adv',
            description='Test', starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(hours=1),
            end_at=timezone.now() + timedelta(hours=1),
            status=Auction.Status.LIVE
        )
        
        cls.paused_auction = Auction.objects.create(
            seller=cls.user, category=cls.category,
            title='Paused', slug='paused-adv',
            description='Test', starting_price=10000, min_increment=500,
            status=Auction.Status.PAUSED
        )
    
    def test_pause_auction_valid_and_invalid(self):
        """Pause LIVE → PAUSED, autres statuts refusés"""
        self.client.login(username='admin', password='pass')
        
        self.client.post(
            reverse('auctions:pause_auction', kwargs={'pk': self.live_auction.pk})
        )
        self.live_auction.refresh_from_db()
        self.assertEqual(self.live_auction.status, Auction.Status.PAUSED)
        
        response = self.client.post(
            reverse('auctions:pause_auction', kwargs={'pk': self.paused_auction.pk})
        )
        self.assertEqual(response.status_code, 302)
    
    def test_resume_auction_valid_and_invalid(self):
        """Resume PAUSED → LIVE"""
        self.client.login(username='admin', password='pass')
        
        self.client.post(
            reverse('auctions:resume_auction', kwargs={'pk': self.paused_auction.pk})
        )
        self.paused_auction.refresh_from_db()
        self.assertEqual(self.paused_auction.status, Auction.Status.LIVE)
        
        response = self.client.post(
            reverse('auctions:resume_auction', kwargs={'pk': self.live_auction.pk})
        )
        self.assertEqual(response.status_code, 302)
    
    def test_cancel_auction_notifies_watchers(self):
        """Cancel notifie les suiveurs"""
        Watchlist.objects.create(user=self.user, auction=self.live_auction)
        
        self.client.login(username='admin', password='pass')
        self.client.post(
            reverse('auctions:cancel_auction', kwargs={'pk': self.live_auction.pk})
        )
        
        self.live_auction.refresh_from_db()
        self.assertEqual(self.live_auction.status, Auction.Status.CANCELLED)
        
        self.assertTrue(
            Notification.objects.filter(
                user=self.user,
                type='ENDED'
            ).exists()
        )
    
    def test_extend_auction_adds_minutes(self):
        """Extend ajoute les minutes"""
        original_end = self.live_auction.end_at
        
        self.client.login(username='admin', password='pass')
        self.client.post(
            reverse('auctions:extend_auction', kwargs={'pk': self.live_auction.pk}),
            {'minutes': 60}
        )
        
        self.live_auction.refresh_from_db()
        self.assertGreater(self.live_auction.end_at, original_end + timedelta(minutes=59))
    
    def test_extend_auction_invalid_minutes(self):
        """Extend avec minutes invalides → refusé"""
        self.client.login(username='admin', password='pass')
        
        response = self.client.post(
            reverse('auctions:extend_auction', kwargs={'pk': self.live_auction.pk}),
            {'minutes': 0}
        )
        self.assertEqual(response.status_code, 302)
        
        response = self.client.post(
            reverse('auctions:extend_auction', kwargs={'pk': self.live_auction.pk}),
            {'minutes': 2000}
        )
        self.assertEqual(response.status_code, 302)
    
    def test_extend_auction_ended_refused(self):
        """Extend sur ENDED → refusé"""
        ended = Auction.objects.create(
            seller=self.user, category=self.category,
            title='Ended', slug='ended-adv',
            description='Test', starting_price=10000, min_increment=500,
            status=Auction.Status.ENDED
        )
        
        self.client.login(username='admin', password='pass')
        response = self.client.post(
            reverse('auctions:extend_auction', kwargs={'pk': ended.pk}),
            {'minutes': 60}
        )
        self.assertEqual(response.status_code, 302)
    
    def test_auction_actions_permissions(self):
        """Actions refusées à USER et anonyme"""
        self.client.login(username='user', password='pass')
        response = self.client.post(
            reverse('auctions:pause_auction', kwargs={'pk': self.live_auction.pk})
        )
        self.assertEqual(response.status_code, 403)
        
        self.client.logout()
        response = self.client.post(
            reverse('auctions:pause_auction', kwargs={'pk': self.live_auction.pk})
        )
        self.assertEqual(response.status_code, 302)
    
    def test_auctions_list_status_filter(self):
        """Filtre par statut fonctionne"""
        self.client.login(username='admin', password='pass')
        
        response = self.client.get(reverse('auctions:admin_auctions') + '?status=LIVE')
        self.assertEqual(response.status_code, 200)
    
    def test_users_list_shows_counts(self):
        """Liste utilisateurs affiche compteurs"""
        Auction.objects.create(
            seller=self.user, category=self.category,
            title='User Auction', slug='user-auction-aa',
            description='Test', starting_price=10000, min_increment=500,
            status=Auction.Status.SOLD
        )
        
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('auctions:admin_users'))
        self.assertEqual(response.status_code, 200)
    
    def test_block_user_deactivates_account(self):
        """Block → is_active=False"""
        self.client.login(username='admin', password='pass')
        self.client.post(
            reverse('auctions:block_user', kwargs={'pk': self.user.pk})
        )
        
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        
        success = self.client.login(username='user', password='pass')
        self.assertFalse(success)
    
    def test_unblock_user_activates_account(self):
        """Unblock → is_active=True"""
        self.user.is_active = False
        self.user.save()
        
        self.client.login(username='admin', password='pass')
        self.client.post(
            reverse('auctions:unblock_user', kwargs={'pk': self.user.pk})
        )
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
    
    def test_promote_demote_user_role(self):
        """Promote USER → ADMIN, Demote ADMIN → USER"""
        self.client.login(username='admin', password='pass')
        
        self.client.post(
            reverse('auctions:promote_user', kwargs={'pk': self.user.pk})
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.ADMIN)
        
        self.client.post(
            reverse('auctions:demote_user', kwargs={'pk': self.user.pk})
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.USER)
    
    def test_admin_cannot_block_self(self):
        """Admin ne peut pas se bloquer lui-même"""
        self.client.login(username='admin', password='pass')
        self.client.post(
            reverse('auctions:block_user', kwargs={'pk': self.admin.pk})
        )
        
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
    
    def test_user_actions_logged_audit(self):
        """Actions utilisateurs journalisées dans AuditLog"""
        self.client.login(username='admin', password='pass')
        self.client.post(
            reverse('auctions:block_user', kwargs={'pk': self.user.pk})
        )
        
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.admin,
                action='BLOCK_USER',
                target_type='User',
                target_id=self.user.id
            ).exists()
        )
    
    def test_create_category_auto_slug(self):
        """Création catégorie avec slug auto"""
        self.client.login(username='admin', password='pass')
        self.client.post(
            reverse('auctions:create_category'),
            {'name': 'Nouvelle Catégorie'}
        )
        
        self.assertTrue(Category.objects.filter(name='Nouvelle Catégorie').exists())
        cat = Category.objects.get(name='Nouvelle Catégorie')
        self.assertEqual(cat.slug, 'nouvelle-categorie')
    
    def test_edit_category_name_persists(self):
        """Modification catégorie persistée"""
        self.client.login(username='admin', password='pass')
        self.client.post(
            reverse('auctions:edit_category', kwargs={'pk': self.category.pk}),
            {'name': 'Catégorie Modifiée'}
        )
        
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, 'Catégorie Modifiée')
    
    def test_delete_empty_category_success(self):
        """Suppression catégorie vide → succès"""
        empty_cat = Category.objects.create(name='Empty', slug='empty-aa')
        
        self.client.login(username='admin', password='pass')
        self.client.post(
            reverse('auctions:delete_category', kwargs={'pk': empty_cat.pk})
        )
        
        self.assertFalse(Category.objects.filter(pk=empty_cat.pk).exists())
    
    def test_delete_category_with_auctions_refused(self):
        """Suppression catégorie avec enchères → refusé"""
        self.client.login(username='admin', password='pass')
        self.client.post(
            reverse('auctions:delete_category', kwargs={'pk': self.category.pk})
        )
        
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
    
    def test_dashboard_status_counts_accurate(self):
        """Compteurs par statut exacts"""
        Auction.objects.create(
            seller=self.user, category=self.category,
            title='Pending', slug='pending-stat-aa',
            description='Test', starting_price=10000, min_increment=500,
            status=Auction.Status.PENDING
        )
        
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('auctions:admin_dashboard'))
        
        self.assertEqual(response.context['pending_count'], 1)
    
    def test_dashboard_revenue_calculation(self):
        """Volume d'affaires = somme des SOLD"""
        Auction.objects.create(
            seller=self.user, category=self.category,
            title='Sold', slug='sold-rev-aa',
            description='Test', starting_price=10000, min_increment=500,
            status=Auction.Status.SOLD, current_price=20000
        )
        
        self.client.login(username='admin', password='pass')
        response = self.client.get(reverse('auctions:admin_dashboard'))
        
        self.assertGreaterEqual(response.context['total_revenue'], 20000)
    
    def test_dashboard_stats_access_denied(self):
        """Stats refusées aux non-admins"""
        self.client.login(username='user', password='pass')
        response = self.client.get(reverse('auctions:admin_dashboard'))
        self.assertEqual(response.status_code, 403)
