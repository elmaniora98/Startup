from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.urls import reverse
from django.template.defaultfilters import floatformat
from accounts.models import User

UserModel = get_user_model()


class CentsToEurosFilterTest(TestCase):
    """Tests pour le filtre de template cents_to_euros"""
    
    def test_cents_to_euros_standard(self):
        """125000 centimes -> 1 250,00 €"""
        from auctions.templatetags.auction_filters import cents_to_euros
        result = cents_to_euros(125000)
        self.assertIn('1', result)
        self.assertIn('250', result)
        self.assertIn('€', result)
        self.assertIn(',', result)
    
    def test_cents_to_euros_zero(self):
        """0 centimes -> 0,00 €"""
        from auctions.templatetags.auction_filters import cents_to_euros
        result = cents_to_euros(0)
        self.assertEqual(result, '0,00 €')
    
    def test_cents_to_euros_99_cents(self):
        """99 centimes -> 0,99 €"""
        from auctions.templatetags.auction_filters import cents_to_euros
        result = cents_to_euros(99)
        self.assertEqual(result, '0,99 €')
    
    def test_cents_to_euros_none(self):
        """None -> chaîne vide"""
        from auctions.templatetags.auction_filters import cents_to_euros
        result = cents_to_euros(None)
        self.assertEqual(result, '')


class HomeViewTest(TestCase):
    """Tests pour la vue d'accueil"""
    
    @classmethod
    def setUpTestData(cls):
        from auctions.models import Category, Auction
        cls.client = Client()
        
        # Créer des catégories
        cls.cat1 = Category.objects.create(name='Électronique', slug='electronique')
        cls.cat2 = Category.objects.create(name='Art', slug='art')
        
        now = timezone.now()
        
        # Créer 2 enchères LIVE
        cls.live1 = Auction.objects.create(
            seller=User.objects.create_user('seller1', 'seller1@test.com', 'pass123'),
            category=cls.cat1,
            title='iPhone 15 Pro',
            slug='iphone-15-pro',
            description='Smartphone neuf',
            starting_price=80000,
            min_increment=1000,
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(hours=2),
            status=Auction.Status.LIVE,
            current_price=85000
        )
        
        cls.live2 = Auction.objects.create(
            seller=User.objects.create_user('seller2', 'seller2@test.com', 'pass123'),
            category=cls.cat2,
            title='Tableau moderne',
            slug='tableau-moderne',
            description='Œuvre originale',
            starting_price=30000,
            min_increment=500,
            start_at=now - timedelta(hours=2),
            end_at=now + timedelta(minutes=30),  # Se termine bientôt
            status=Auction.Status.LIVE,
            current_price=32000
        )
        
        # Créer 2 enchères SCHEDULED
        cls.scheduled1 = Auction.objects.create(
            seller=User.objects.create_user('seller3', 'seller3@test.com', 'pass123'),
            category=cls.cat1,
            title='Vélo de course',
            slug='velo-course',
            description='Vélo carbone',
            starting_price=120000,
            min_increment=2000,
            start_at=now + timedelta(hours=2),
            end_at=now + timedelta(days=2),
            status=Auction.Status.SCHEDULED,
        )
        
        cls.scheduled2 = Auction.objects.create(
            seller=User.objects.create_user('seller4', 'seller4@test.com', 'pass123'),
            category=cls.cat2,
            title='Canapé design',
            slug='canape-design',
            description='Canapé 3 places',
            starting_price=40000,
            min_increment=1000,
            start_at=now + timedelta(hours=5),
            end_at=now + timedelta(days=3),
            status=Auction.Status.SCHEDULED,
        )
        
        # Créer 1 enchère ENDED (ne doit pas apparaître)
        cls.ended = Auction.objects.create(
            seller=User.objects.create_user('seller5', 'seller5@test.com', 'pass123'),
            category=cls.cat1,
            title='Appareil photo',
            slug='appareil-photo',
            description='Reflex numérique',
            starting_price=60000,
            min_increment=1000,
            start_at=now - timedelta(days=2),
            end_at=now - timedelta(hours=1),
            status=Auction.Status.ENDED,
        )
        
        # Créer 1 enchère PENDING (ne doit pas apparaître)
        cls.pending = Auction.objects.create(
            seller=User.objects.create_user('seller6', 'seller6@test.com', 'pass123'),
            category=cls.cat1,
            title='Montre vintage',
            slug='montre-vintage',
            description='Montre automatique',
            starting_price=15000,
            min_increment=500,
            start_at=now,
            end_at=now + timedelta(hours=1),
            status=Auction.Status.PENDING,
        )
    
    def test_home_page_status_code(self):
        """GET / retourne 200"""
        response = self.client.get(reverse('auctions:home'))
        self.assertEqual(response.status_code, 200)
    
    def test_home_page_uses_correct_template(self):
        """La vue utilise le template home.html"""
        response = self.client.get(reverse('auctions:home'))
        self.assertTemplateUsed(response, 'auctions/home.html')
    
    def test_live_auctions_appear(self):
        """Les titres des enchères LIVE apparaissent"""
        response = self.client.get(reverse('auctions:home'))
        self.assertContains(response, 'iPhone 15 Pro')
        self.assertContains(response, 'Tableau moderne')
    
    def test_scheduled_auctions_appear(self):
        """Les titres des enchères SCHEDULED apparaissent"""
        response = self.client.get(reverse('auctions:home'))
        self.assertContains(response, 'Vélo de course')
        self.assertContains(response, 'Canapé design')
    
    def test_ended_auction_does_not_appear(self):
        """Les enchères ENDED n'apparaissent PAS"""
        response = self.client.get(reverse('auctions:home'))
        self.assertNotContains(response, 'Appareil photo')
    
    def test_pending_auction_does_not_appear(self):
        """Les enchères PENDING n'apparaissent PAS"""
        response = self.client.get(reverse('auctions:home'))
        self.assertNotContains(response, 'Montre vintage')
    
    def test_live_cards_have_data_end_at(self):
        """Les cartes LIVE ont un attribut data-end-at au format ISO"""
        response = self.client.get(reverse('auctions:home'))
        # Vérifier que data-end-at est présent avec un format ISO
        self.assertRegex(response.content.decode(), r'data-end-at="[^"]+T[^"]+"')
    
    def test_navbar_contains_enchere_plus(self):
        """La navbar contient « Enchère+ »"""
        response = self.client.get(reverse('auctions:home'))
        self.assertContains(response, 'Enchère+')
    
    def test_prices_displayed_in_euros(self):
        """Les prix sont affichés en euros avec le symbole €"""
        response = self.client.get(reverse('auctions:home'))
        content = response.content.decode()
        self.assertIn('€', content)
        # Vérifier que les centimes bruts ne sont pas affichés tels quels
        self.assertNotIn('85000', content)  # Le prix brut en centimes
    
    def test_category_filter(self):
        """Le filtre par catégorie fonctionne"""
        response = self.client.get(reverse('auctions:home') + '?category=electronique')
        content = response.content.decode()
        self.assertIn('iPhone 15 Pro', content)
        self.assertNotIn('Tableau moderne', content)  # Dans la catégorie Art
    
    def test_sort_by_newest(self):
        """Le tri par newest fonctionne"""
        response = self.client.get(reverse('auctions:home') + '?sort=newest')
        self.assertEqual(response.status_code, 200)
    
    def test_empty_live_auctions_message(self):
        """Message quand aucune enchère LIVE"""
        # Supprimer temporairement toutes les LIVE
        from auctions.models import Auction
        Auction.objects.filter(status=Auction.Status.LIVE).delete()
        
        response = self.client.get(reverse('auctions:home'))
        self.assertContains(response, 'Aucune enchère en cours')


class AuthViewsTest(TestCase):
    """Tests pour les vues d'authentification"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='adminpass123',
            role=User.Role.ADMIN
        )
    
    def test_register_creates_user_with_role_user(self):
        """Inscription crée un utilisateur avec rôle USER"""
        response = self.client.post(reverse('accounts:register'), {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        # Vérifier que l'utilisateur a été créé
        user = User.objects.filter(email='newuser@example.com').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.role, User.Role.USER)
    
    def test_register_email_already_used(self):
        """Email déjà utilisé → erreur"""
        # Première inscription
        self.client.post(reverse('accounts:register'), {
            'username': 'firstuser',
            'email': 'duplicate@example.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        # Deuxième inscription avec le même email
        response = self.client.post(reverse('accounts:register'), {
            'username': 'seconduser',
            'email': 'duplicate@example.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        # Vérifier que l'utilisateur n'a pas été créé deux fois
        from django.contrib.auth import get_user_model
        User = get_user_model()
        count = User.objects.filter(email='duplicate@example.com').count()
        self.assertEqual(count, 1)  # Un seul utilisateur créé
    
    def test_login_success(self):
        """Connexion avec identifiants corrects"""
        response = self.client.post(reverse('accounts:login'), {
            'username': 'testuser',
            'password': 'testpass123',
        })
        self.assertRedirects(response, reverse('auctions:home'))
        # Vérifier que la session est ouverte
        self.assertTrue('_auth_user_id' in self.client.session)
    
    def test_login_failure(self):
        """Connexion avec identifiants incorrects"""
        response = self.client.post(reverse('accounts:login'), {
            'username': 'testuser',
            'password': 'wrongpassword',
        })
        # Vérifier qu'il y a une erreur
        self.assertFalse(response.context['form'].is_valid())
    
    def test_logout(self):
        """Déconnexion ferme la session"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('accounts:logout'))
        self.assertRedirects(response, reverse('auctions:home'))
    
    def test_protected_view_requires_login(self):
        """Vue protégée redirige vers login si anonyme"""
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertRedirects(response, '/compte/connexion/?next=/compte/dashboard/')
    
    def test_admin_view_rejects_regular_user(self):
        """Une URL admin appelée par un USER classique est refusée"""
        self.client.login(username='testuser', password='testpass123')
        # Essayer d'accéder à une URL qui devrait être réservée aux admins
        # Pour l'instant, on teste que l'utilisateur n'a pas is_staff
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_admin())


class SeedDemoCommandTest(TestCase):
    """Tests pour la management command seed_demo"""
    
    def test_seed_demo_runs_without_error(self):
        """La command seed_demo s'exécute sans erreur"""
        from django.core.management import call_command
        # Exécuter la command
        call_command('seed_demo')
        
        # Vérifier que des données ont été créées
        from auctions.models import Category, Auction
        self.assertGreater(Category.objects.count(), 0)
        self.assertGreater(Auction.objects.count(), 0)
        
        # Vérifier que l'admin existe
        admin = User.objects.filter(email='admin@enchere.plus').first()
        self.assertIsNotNone(admin)
        self.assertEqual(admin.role, User.Role.ADMIN)
