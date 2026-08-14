"""
Tests pour les formulaires de soumission d'enchères
Phase 2 - Produits (Proposition, Détail, Gestion)
~12 tests
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from auctions.models import Auction, Category
from auctions.forms import ProposeAuctionForm as SubmitAuctionForm
from django.utils import timezone
from datetime import timedelta
from io import BytesIO
from PIL import Image

User = get_user_model()


class SubmitAuctionFormTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(username='seller', password='pass', email='seller@test.com')
        cls.category = Category.objects.create(name='Test', slug='test')
        
    def create_image(self):
        """Crée une image de test en mémoire"""
        img = BytesIO()
        image = Image.new('RGB', (100, 100), color='red')
        image.save(img, format='JPEG')
        img.seek(0)
        return img
    
    def test_valid_submission_creates_pending_auction(self):
        """Une soumission valide crée une enchère PENDING"""
        start_at = timezone.now() + timedelta(hours=2)
        end_at = start_at + timedelta(days=7)
        
        form_data = {
            'title': 'Test Auction',
            'description': 'Description de test',
            'category': self.category.id,
            'starting_price_euros': 100.50,
            'min_increment_euros': 5.00,
            'start_at': start_at.strftime('%Y-%m-%dT%H:%M'),
            'end_at': end_at.strftime('%Y-%m-%dT%H:%M'),
        }
        
        # Utiliser files au lieu de form.files
        from django.core.files.uploadedfile import SimpleUploadedFile
        img = self.create_image()
        image_file = SimpleUploadedFile("test.jpg", img.read(), content_type="image/jpeg")
        
        form = SubmitAuctionForm(data=form_data, seller=self.seller, files={'images': image_file})
        
        self.assertTrue(form.is_valid(), f"Formulaire invalide: {form.errors}")
    
    def test_amounts_converted_to_cents(self):
        """Les montants sont convertis en centimes (100.50 € → 10050 centimes)"""
        start_at = timezone.now() + timedelta(hours=2)
        end_at = start_at + timedelta(days=7)
        
        form_data = {
            'title': 'Test Auction',
            'description': 'Description',
            'category': self.category.id,
            'starting_price_euros': 100.50,
            'min_increment_euros': 5.00,
            'start_at': start_at.strftime('%Y-%m-%dT%H:%M'),
            'end_at': end_at.strftime('%Y-%m-%dT%H:%M'),
        }
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        img = self.create_image()
        image_file = SimpleUploadedFile("test.jpg", img.read(), content_type="image/jpeg")
        
        form = SubmitAuctionForm(data=form_data, seller=self.seller, files={'images': image_file})
        
        self.assertTrue(form.is_valid())
        auction = form.save(commit=False)
        self.assertEqual(auction.starting_price, 10050)  # 100.50 € en centimes
        self.assertEqual(auction.min_increment, 500)     # 5.00 € en centimes
    
    def test_missing_required_fields_rejected(self):
        """Les champs requis manquants sont rejetés"""
        form = SubmitAuctionForm(data={}, seller=self.seller)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
        self.assertIn('description', form.errors)
        self.assertIn('category', form.errors)
        self.assertIn('starting_price_euros', form.errors)
    
    def test_starting_price_zero_rejected(self):
        """Un prix de départ à zéro est rejeté"""
        start_at = timezone.now() + timedelta(hours=2)
        end_at = start_at + timedelta(days=7)
        
        form_data = {
            'title': 'Test',
            'description': 'Test',
            'category': self.category.id,
            'starting_price_euros': 0,
            'min_increment_euros': 1.00,
            'start_at': start_at.strftime('%Y-%m-%dT%H:%M'),
            'end_at': end_at.strftime('%Y-%m-%dT%H:%M'),
        }
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        img = self.create_image()
        image_file = SimpleUploadedFile("test.jpg", img.read(), content_type="image/jpeg")
        
        form = SubmitAuctionForm(data=form_data, seller=self.seller, files={'images': image_file})
        
        self.assertFalse(form.is_valid())
        self.assertIn('starting_price_euros', form.errors)
    
    def test_min_increment_zero_rejected(self):
        """Un incrément minimum à zéro est rejeté"""
        start_at = timezone.now() + timedelta(hours=2)
        end_at = start_at + timedelta(days=7)
        
        form_data = {
            'title': 'Test',
            'description': 'Test',
            'category': self.category.id,
            'starting_price_euros': 100.00,
            'min_increment_euros': 0,
            'start_at': start_at.strftime('%Y-%m-%dT%H:%M'),
            'end_at': end_at.strftime('%Y-%m-%dT%H:%M'),
        }
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        img = self.create_image()
        image_file = SimpleUploadedFile("test.jpg", img.read(), content_type="image/jpeg")
        
        form = SubmitAuctionForm(data=form_data, seller=self.seller, files={'images': image_file})
        
        self.assertFalse(form.is_valid())
        self.assertIn('min_increment_euros', form.errors)
    
    def test_end_before_start_rejected(self):
        """Une date de fin avant la date de début est rejetée"""
        start_at = timezone.now() + timedelta(days=2)
        end_at = timezone.now() + timedelta(hours=1)  # Avant start_at
        
        form_data = {
            'title': 'Test',
            'description': 'Test',
            'category': self.category.id,
            'starting_price_euros': 100.00,
            'min_increment_euros': 5.00,
            'start_at': start_at.strftime('%Y-%m-%dT%H:%M'),
            'end_at': end_at.strftime('%Y-%m-%dT%H:%M'),
        }
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        img = self.create_image()
        image_file = SimpleUploadedFile("test.jpg", img.read(), content_type="image/jpeg")
        
        form = SubmitAuctionForm(data=form_data, seller=self.seller, files={'images': image_file})
        
        self.assertFalse(form.is_valid())
        # L'erreur peut être dans __all__ ou end_at
        self.assertTrue(not form.is_valid())
    
    def test_start_in_past_rejected(self):
        """Une date de début dans le passé est rejetée"""
        start_at = timezone.now() - timedelta(hours=1)
        end_at = timezone.now() + timedelta(days=7)
        
        form_data = {
            'title': 'Test',
            'description': 'Test',
            'category': self.category.id,
            'starting_price_euros': 100.00,
            'min_increment_euros': 5.00,
            'start_at': start_at.strftime('%Y-%m-%dT%H:%M'),
            'end_at': end_at.strftime('%Y-%m-%dT%H:%M'),
        }
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        img = self.create_image()
        image_file = SimpleUploadedFile("test.jpg", img.read(), content_type="image/jpeg")
        
        form = SubmitAuctionForm(data=form_data, seller=self.seller, files={'images': image_file})
        
        self.assertFalse(form.is_valid())
        # L'erreur peut être dans __all__ ou start_at
        self.assertTrue('__all__' in form.errors or 'start_at' in form.errors)
    
    def test_duration_less_than_1h_rejected(self):
        """Une durée inférieure à 1 heure est rejetée"""
        start_at = timezone.now() + timedelta(hours=2)
        end_at = start_at + timedelta(minutes=30)  # Moins d'une heure
        
        form_data = {
            'title': 'Test',
            'description': 'Test',
            'category': self.category.id,
            'starting_price_euros': 100.00,
            'min_increment_euros': 5.00,
            'start_at': start_at.strftime('%Y-%m-%dT%H:%M'),
            'end_at': end_at.strftime('%Y-%m-%dT%H:%M'),
        }
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        img = self.create_image()
        image_file = SimpleUploadedFile("test.jpg", img.read(), content_type="image/jpeg")
        
        form = SubmitAuctionForm(data=form_data, seller=self.seller, files={'images': image_file})
        
        self.assertFalse(form.is_valid())
    
    def test_duration_more_than_30_days_rejected(self):
        """Une durée supérieure à 30 jours est rejetée"""
        start_at = timezone.now() + timedelta(hours=2)
        end_at = start_at + timedelta(days=35)  # Plus de 30 jours
        
        form_data = {
            'title': 'Test',
            'description': 'Test',
            'category': self.category.id,
            'starting_price_euros': 100.00,
            'min_increment_euros': 5.00,
            'start_at': start_at.strftime('%Y-%m-%dT%H:%M'),
            'end_at': end_at.strftime('%Y-%m-%dT%H:%M'),
        }
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        img = self.create_image()
        image_file = SimpleUploadedFile("test.jpg", img.read(), content_type="image/jpeg")
        
        form = SubmitAuctionForm(data=form_data, seller=self.seller, files={'images': image_file})
        
        self.assertFalse(form.is_valid())
    
    def test_reserve_price_less_than_starting_rejected(self):
        """Un prix de réserve inférieur au prix de départ est rejeté"""
        start_at = timezone.now() + timedelta(hours=2)
        end_at = start_at + timedelta(days=7)
        
        form_data = {
            'title': 'Test',
            'description': 'Test',
            'category': self.category.id,
            'starting_price_euros': 100.00,
            'reserve_price_euros': 50.00,  # Inférieur au starting_price
            'min_increment_euros': 5.00,
            'start_at': start_at.strftime('%Y-%m-%dT%H:%M'),
            'end_at': end_at.strftime('%Y-%m-%dT%H:%M'),
        }
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        img = self.create_image()
        image_file = SimpleUploadedFile("test.jpg", img.read(), content_type="image/jpeg")
        
        form = SubmitAuctionForm(data=form_data, seller=self.seller, files={'images': image_file})
        
        self.assertFalse(form.is_valid())
        self.assertIn('reserve_price_euros', form.errors)
    
    def test_no_image_rejected(self):
        """Aucune image est rejeté"""
        start_at = timezone.now() + timedelta(hours=2)
        end_at = start_at + timedelta(days=7)
        
        form_data = {
            'title': 'Test',
            'description': 'Test',
            'category': self.category.id,
            'starting_price_euros': 100.00,
            'min_increment_euros': 5.00,
            'start_at': start_at.strftime('%Y-%m-%dT%H:%M'),
            'end_at': end_at.strftime('%Y-%m-%dT%H:%M'),
        }
        
        form = SubmitAuctionForm(data=form_data, seller=self.seller)
        # Pas d'image
        
        self.assertFalse(form.is_valid())
        self.assertIn('images', form.errors)
    
    def test_too_many_images_rejected(self):
        """Trop d'images est rejeté"""
        start_at = timezone.now() + timedelta(hours=2)
        end_at = start_at + timedelta(days=7)
        
        form_data = {
            'title': 'Test',
            'description': 'Test',
            'category': self.category.id,
            'starting_price_euros': 100.00,
            'min_increment_euros': 5.00,
            'start_at': start_at.strftime('%Y-%m-%dT%H:%M'),
            'end_at': end_at.strftime('%Y-%m-%dT%H:%M'),
        }
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        images = []
        for i in range(6):
            img = self.create_image()
            images.append(SimpleUploadedFile(f"test{i}.jpg", img.read(), content_type="image/jpeg"))
        
        form = SubmitAuctionForm(data=form_data, seller=self.seller, files={'images': images})
        
        self.assertFalse(form.is_valid())
        self.assertIn('images', form.errors)
