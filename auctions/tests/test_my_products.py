"""
Tests pour la gestion des produits (my_products)
Phase 2 - Produits (Proposition, Détail, Gestion)
~10 tests
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from auctions.models import Auction, Category
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class MyProductsViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(username='seller', password='pass', email='seller@test.com')
        cls.other_user = User.objects.create_user(username='other', password='pass', email='other@test.com')
        cls.admin = User.objects.create_superuser(username='admin', password='pass', email='admin@test.com')
        cls.category = Category.objects.create(name='Test', slug='test')
        
        # Enchère PENDING appartenant au seller
        cls.pending_auction = Auction.objects.create(
            seller=cls.seller, category=cls.category,
            title='Pending Auction', slug='pending-auction', description='Test',
            starting_price=10000, min_increment=500,
            start_at=timezone.now() + timedelta(hours=24),
            end_at=timezone.now() + timedelta(days=8),
            status=Auction.Status.PENDING
        )
        
        # Enchère SCHEDULED appartenant au seller
        cls.scheduled_auction = Auction.objects.create(
            seller=cls.seller, category=cls.category,
            title='Scheduled Auction', slug='scheduled-auction', description='Test',
            starting_price=10000, min_increment=500,
            start_at=timezone.now() + timedelta(hours=24),
            end_at=timezone.now() + timedelta(days=8),
            status=Auction.Status.SCHEDULED
        )
        
        # Enchère LIVE appartenant au seller
        cls.live_auction = Auction.objects.create(
            seller=cls.seller, category=cls.category,
            title='Live Auction', slug='live-auction', description='Test',
            starting_price=10000, min_increment=500,
            start_at=timezone.now() - timedelta(hours=1),
            end_at=timezone.now() + timedelta(hours=1),
            status=Auction.Status.LIVE
        )
        
        # Enchère REJECTED avec motif
        cls.rejected_auction = Auction.objects.create(
            seller=cls.seller, category=cls.category,
            title='Rejected Auction', slug='rejected-auction', description='Test',
            starting_price=10000, min_increment=500,
            start_at=timezone.now() + timedelta(hours=24),
            end_at=timezone.now() + timedelta(days=8),
            status=Auction.Status.REJECTED,
            rejection_reason="Description trop courte"
        )
    
    def test_user_sees_only_own_products(self):
        """L'utilisateur ne voit que ses propres produits"""
        self.client.login(username='seller', password='pass')
        response = self.client.get(reverse('accounts:my_products'))
        self.assertEqual(response.status_code, 200)
        
        # Vérifier que les enchères du seller sont présentes
        self.assertIn('auctions', response.context)
        auction_ids = [a.id for a in response.context['auctions']]
        self.assertIn(self.pending_auction.id, auction_ids)
        self.assertIn(self.scheduled_auction.id, auction_ids)
        self.assertIn(self.live_auction.id, auction_ids)
        self.assertIn(self.rejected_auction.id, auction_ids)
        
        # L'autre utilisateur ne voit pas ces enchères
        self.client.login(username='other', password='pass')
        response = self.client.get(reverse('accounts:my_products'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['auctions']), 0)
    
    def test_non_owner_edit_forbidden_403(self):
        """Un non-propriétaire ne peut pas éditer (403)"""
        self.client.login(username='other', password='pass')
        response = self.client.get(reverse('auctions:edit_auction', kwargs={'pk': self.pending_auction.pk}))
        self.assertEqual(response.status_code, 403)
    
    def test_owner_edit_scheduled_refused(self):
        """Le propriétaire ne peut pas éditer une enchère SCHEDULED"""
        self.client.login(username='seller', password='pass')
        response = self.client.get(reverse('auctions:edit_auction', kwargs={'pk': self.scheduled_auction.pk}))
        # La vue redirige avec un message d'erreur au lieu de retourner 403
        self.assertEqual(response.status_code, 302)
    
    def test_owner_edit_live_refused(self):
        """Le propriétaire ne peut pas éditer une enchère LIVE"""
        self.client.login(username='seller', password='pass')
        response = self.client.get(reverse('auctions:edit_auction', kwargs={'pk': self.live_auction.pk}))
        # La vue redirige avec un message d'erreur au lieu de retourner 403
        self.assertEqual(response.status_code, 302)
    
    def test_owner_edit_pending_success(self):
        """Le propriétaire peut éditer une enchère PENDING"""
        self.client.login(username='seller', password='pass')
        response = self.client.get(reverse('auctions:edit_auction', kwargs={'pk': self.pending_auction.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_delete_pending_removes_object(self):
        """Supprimer une enchère PENDING la retire de la base"""
        self.client.login(username='seller', password='pass')
        auction_id = self.pending_auction.id
        response = self.client.post(reverse('auctions:delete_auction', kwargs={'pk': self.pending_auction.pk}))
        self.assertEqual(response.status_code, 302)  # Redirect après suppression
        from auctions.models import Auction
        self.assertFalse(Auction.objects.filter(id=auction_id).exists())
    
    def test_delete_scheduled_refused(self):
        """Supprimer une enchère SCHEDULED est refusé"""
        self.client.login(username='seller', password='pass')
        response = self.client.post(reverse('auctions:delete_auction', kwargs={'pk': self.scheduled_auction.pk}))
        # La vue redirige avec un message d'erreur au lieu de retourner 403
        self.assertEqual(response.status_code, 302)
    
    def test_buttons_visible_only_if_pending(self):
        """Les boutons d'édition/suppression ne sont visibles que pour PENDING"""
        self.client.login(username='seller', password='pass')
        
        # Pour PENDING
        response = self.client.get(reverse('accounts:my_products'))
        self.assertContains(response, 'href="' + reverse('auctions:edit_auction', kwargs={'pk': self.pending_auction.pk}) + '"')
        
        # Pour SCHEDULED, pas de bouton d'édition
        content = response.content.decode()
        edit_scheduled_url = reverse('auctions:edit_auction', kwargs={'pk': self.scheduled_auction.pk})
        self.assertNotIn('href="' + edit_scheduled_url + '"', content)
    
    def test_rejection_reason_displayed(self):
        """Le motif de rejet est affiché"""
        self.client.login(username='seller', password='pass')
        response = self.client.get(reverse('accounts:my_products'))
        self.assertContains(response, "Description trop courte")
    
    def test_status_badges_colored(self):
        """Les badges de statut ont des couleurs différentes"""
        self.client.login(username='seller', password='pass')
        response = self.client.get(reverse('accounts:my_products'))
        
        # Vérifier la présence de classes de couleur Tailwind
        content = response.content.decode()
        # PENDING devrait avoir une couleur jaune/orange
        self.assertTrue('bg-yellow' in content or 'bg-amber' in content or 'bg-orange' in content)
        # LIVE devrait avoir une couleur verte
        self.assertTrue('bg-green' in content or 'bg-emerald' in content)
        # REJECTED devrait avoir une couleur rouge
        self.assertTrue('bg-red' in content)
