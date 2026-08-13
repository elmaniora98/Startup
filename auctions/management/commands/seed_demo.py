"""
Management command pour générer des données de démo pour Enchère+
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.utils.text import slugify
from accounts.models import User
from auctions.models import Category, Auction, AuctionImage, Bid
import os


class Command(BaseCommand):
    help = 'Génère des données de démo pour Enchère+'

    def handle(self, *args, **options):
        # Nettoyer les anciennes données
        self.stdout.write('Nettoyage des anciennes données...')
        AuctionImage.objects.all().delete()
        Bid.objects.all().delete()
        Auction.objects.all().delete()
        User.objects.exclude(is_superuser=True).delete()
        Category.objects.all().delete()

        self.stdout.write('Création des données de démo...')

        # Créer l'admin
        admin, created = User.objects.get_or_create(
            email='admin@enchere.plus',
            defaults={
                'username': 'admin',
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin.set_password('admin123')
            admin.save()
            self.stdout.write(self.style.SUCCESS('✓ Admin créé: admin@enchere.plus / admin123'))
        else:
            admin.set_password('admin123')
            admin.save()
            self.stdout.write('✓ Admin existe déjà (mot de passe réinitialisé)')

        # Créer les utilisateurs normaux
        users_data = [
            ('user1@test.fr', 'user1', 'test1234'),
            ('user2@test.fr', 'user2', 'test1234'),
        ]
        users = []
        for email, username, password in users_data:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={'username': username, 'role': User.Role.USER}
            )
            if created:
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.SUCCESS(f'✓ Utilisateur créé: {email} / test1234'))
            else:
                user.set_password(password)
                user.save()
                self.stdout.write(f'✓ Utilisateur existe déjà: {email}')
            users.append(user)

        # Créer les catégories
        categories_data = [
            ('Électronique', 'electronique'),
            ('Art', 'art'),
            ('Mode', 'mode'),
            ('Maison', 'maison'),
            ('Sport', 'sport'),
        ]
        categories = {}
        for name, slug in categories_data:
            cat, _ = Category.objects.get_or_create(slug=slug, defaults={'name': name})
            categories[slug] = cat
            self.stdout.write(f'✓ Catégorie: {name}')

        now = timezone.now()

        # Données pour les enchères LIVE (3)
        live_auctions_data = [
            {
                'title': 'iPhone 15 Pro Max 256GB',
                'description': 'Smartphone Apple dernier cri, état neuf, jamais utilisé. Livré avec boîte et accessoires d\'origine.',
                'category': categories['electronique'],
                'starting_price': 80000,  # 800 €
                'min_increment': 1000,  # 10 €
                'start_at': now - timedelta(hours=2),
                'end_at': now + timedelta(hours=3),
                'status': Auction.Status.LIVE,
                'seller': users[0],
            },
            {
                'title': 'Tableau moderne Abstraction Bleue',
                'description': 'Œuvre originale d\'un artiste contemporain. Huile sur toile, 100x80cm. Signée et datée.',
                'category': categories['art'],
                'starting_price': 30000,  # 300 €
                'min_increment': 500,  # 5 €
                'start_at': now - timedelta(hours=5),
                'end_at': now + timedelta(minutes=30),  # Se termine bientôt !
                'status': Auction.Status.LIVE,
                'seller': users[1],
            },
            {
                'title': 'Montre de luxe vintage',
                'description': 'Montre automatique des années 70, entièrement révisée. Cadran argenté, bracelet cuir.',
                'category': categories['mode'],
                'starting_price': 15000,  # 150 €
                'min_increment': 500,  # 5 €
                'start_at': now - timedelta(hours=1),
                'end_at': now + timedelta(hours=6),
                'status': Auction.Status.LIVE,
                'seller': users[0],
            },
        ]

        for data in live_auctions_data:
            # Générer un slug unique
            base_slug = slugify(data['title'])
            slug = base_slug
            counter = 1
            while Auction.objects.filter(slug=slug).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            
            auction = Auction.objects.create(slug=slug, **data)
            
            # Créer quelques enchères
            bid_amounts = [
                data['starting_price'] + data['min_increment'] * i 
                for i in range(1, 4)
            ]
            for amount in bid_amounts:
                bidder = users[amount % len(users)]
                Bid.objects.create(auction=auction, user=bidder, amount=amount)
            
            # Mettre à jour le prix actuel
            auction.current_price = bid_amounts[-1] if bid_amounts else None
            auction.save()
            
            self.stdout.write(self.style.SUCCESS(f'✓ Enchère LIVE créée: {data["title"]}'))

        # Données pour les enchères SCHEDULED (2)
        scheduled_auctions_data = [
            {
                'title': 'Vélo de course carbone',
                'description': 'Vélo de route haut de gamme, cadre carbone, groupe Shimano Ultegra. Taille M.',
                'category': categories['sport'],
                'starting_price': 120000,  # 1200 €
                'min_increment': 2000,  # 20 €
                'start_at': now + timedelta(hours=2),
                'end_at': now + timedelta(days=2),
                'status': Auction.Status.SCHEDULED,
                'seller': users[1],
            },
            {
                'title': 'Canapé design scandinave',
                'description': 'Canapé 3 places en tissu gris clair, style scandinave. Excellent état, acheté il y a 6 mois.',
                'category': categories['maison'],
                'starting_price': 40000,  # 400 €
                'min_increment': 1000,  # 10 €
                'start_at': now + timedelta(hours=5),
                'end_at': now + timedelta(days=3),
                'status': Auction.Status.SCHEDULED,
                'seller': users[0],
            },
        ]

        for data in scheduled_auctions_data:
            # Générer un slug unique
            base_slug = slugify(data['title'])
            slug = base_slug
            counter = 1
            while Auction.objects.filter(slug=slug).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            
            auction = Auction.objects.create(slug=slug, **data)
            self.stdout.write(self.style.SUCCESS(f'✓ Enchère SCHEDULED créée: {data["title"]}'))

        # Créer une enchère ENDED (1)
        ended_title = 'Appareil photo reflex numérique'
        base_slug = slugify(ended_title)
        slug = base_slug
        counter = 1
        while Auction.objects.filter(slug=slug).exists():
            slug = f'{base_slug}-{counter}'
            counter += 1
        
        ended_auction = Auction.objects.create(
            slug=slug,
            title=ended_title,
            description='Canon EOS 90D avec objectif 18-135mm. Très bon état, peu servi.',
            category=categories['electronique'],
            starting_price=60000,  # 600 €
            min_increment=1000,  # 10 €
            start_at=now - timedelta(days=2),
            end_at=now - timedelta(hours=1),
            status=Auction.Status.ENDED,
            current_price=85000,  # 850 €
            seller=users[0],
            winner=users[1],
        )
        Bid.objects.create(auction=ended_auction, user=users[1], amount=85000)
        self.stdout.write(self.style.SUCCESS('✓ Enchère ENDED créée'))

        # Créer des images placeholder pour les enchères
        self.stdout.write('\nCréation des images placeholder...')
        
        # Créer un dossier pour les images placeholder
        placeholder_dir = os.path.join('media', 'auctions')
        os.makedirs(placeholder_dir, exist_ok=True)
        
        # Pour chaque enchère sans image, créer un placeholder
        for auction in Auction.objects.all():
            if not auction.images.exists():
                # Créer un fichier placeholder simple
                filename = f'placeholder_{auction.id}.png'
                filepath = os.path.join(placeholder_dir, filename)
                
                # Image PNG 1x1 pixel blanc (minimaliste)
                with open(filepath, 'wb') as f:
                    # En-tête PNG minimal
                    f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82')
                
                AuctionImage.objects.create(auction=auction, image=f'auctions/{filename}', order=0)
                self.stdout.write(f'  → Placeholder ajouté à: {auction.title}')

        self.stdout.write('\n' + self.style.SUCCESS('Données de démo créées avec succès !'))
        self.stdout.write('\nVous pouvez maintenant tester la page d\'accueil avec:')
        self.stdout.write('  python manage.py runserver')
        self.stdout.write('\nPuis accédez à http://localhost:8000/')
