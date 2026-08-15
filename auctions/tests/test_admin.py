from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from accounts.models import User
from auctions.models import Auction, Category, AuditLog, Notification
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class AdminAccessTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='admin', email='admin@enchere.plus', password='admin123', role=User.Role.ADMIN)
        cls.user = User.objects.create_user(username='user', email='user@test.fr', password='test1234', role=User.Role.USER)
        cls.staff_user = User.objects.create_user(username='staff', email='staff@test.fr', password='test1234', is_staff=True, role=User.Role.USER)
        cls.category = Category.objects.create(name='Test', slug='test')
    def test_anonymous_redirected(self):
        for url_name in ['auctions:admin_dashboard', 'auctions:validation_queue', 'auctions:audit_log']:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 302)
    def test_user_forbidden(self):
        self.client.login(username='user', password='test1234')
        for url_name in ['auctions:admin_dashboard', 'auctions:validation_queue', 'auctions:audit_log']:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 403)
    def test_admin_ok(self):
        self.client.login(username='admin', password='admin123')
        for url_name in ['auctions:admin_dashboard', 'auctions:validation_queue', 'auctions:audit_log']:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200)
    def test_staff_not_admin_forbidden(self):
        self.client.login(username='staff', password='test1234')
        for url_name in ['auctions:admin_dashboard', 'auctions:validation_queue', 'auctions:audit_log']:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 403)

class ValidationQueueTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='admin', email='admin@enchere.plus', password='admin123', role=User.Role.ADMIN)
        cls.seller = User.objects.create_user(username='seller', email='seller@test.fr', password='test1234', role=User.Role.USER)
        cls.category = Category.objects.create(name='Test', slug='test')
        now = timezone.now()
        cls.pending1 = Auction.objects.create(seller=cls.seller, category=cls.category, title='Pending 1', slug='pending-1', description='Test', starting_price=10000, min_increment=500, start_at=now+timedelta(days=2), end_at=now+timedelta(days=3), status=Auction.Status.PENDING, created_at=now-timedelta(days=2))
        cls.pending2 = Auction.objects.create(seller=cls.seller, category=cls.category, title='Pending 2', slug='pending-2', description='Test', starting_price=20000, min_increment=1000, start_at=now+timedelta(days=2), end_at=now+timedelta(days=3), status=Auction.Status.PENDING, created_at=now-timedelta(days=1))
        cls.live = Auction.objects.create(seller=cls.seller, category=cls.category, title='Live', slug='live-1', description='Test', starting_price=10000, min_increment=500, start_at=now-timedelta(hours=1), end_at=now+timedelta(hours=1), status=Auction.Status.LIVE)
    def test_only_pending(self):
        self.client.login(username='admin', password='admin123')
        response = self.client.get(reverse('auctions:validation_queue'))
        self.assertContains(response, 'Pending 1')
        self.assertNotContains(response, 'Live')
    def test_badge_count(self):
        self.client.login(username='admin', password='admin123')
        response = self.client.get(reverse('auctions:validation_queue'))
        self.assertEqual(response.context['pending_count'], 2)

class ApproveAuctionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='admin', email='admin@enchere.plus', password='admin123', role=User.Role.ADMIN)
        cls.seller = User.objects.create_user(username='seller', email='seller@test.fr', password='test1234', role=User.Role.USER)
        cls.category = Category.objects.create(name='Test', slug='test')
        now = timezone.now()
        cls.pending = Auction.objects.create(seller=cls.seller, category=cls.category, title='To Approve', slug='to-approve', description='Test', starting_price=10000, min_increment=500, start_at=now+timedelta(days=1), end_at=now+timedelta(days=2), status=Auction.Status.PENDING)
    def test_valid_approval(self):
        self.client.login(username='admin', password='admin123')
        now = timezone.now()
        # Utiliser le format Z à la fin pour ISO 8601
        start_at = (now+timedelta(days=2)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        end_at = (now+timedelta(days=3)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        response = self.client.post(reverse('auctions:approve_auction', kwargs={'pk': self.pending.id}), {'start_at': start_at, 'end_at': end_at}, follow=True)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Auction.Status.SCHEDULED)
    def test_creates_audit_log(self):
        self.client.login(username='admin', password='admin123')
        now = timezone.now()
        start_at = (now+timedelta(days=2)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        end_at = (now+timedelta(days=3)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        self.client.post(reverse('auctions:approve_auction', kwargs={'pk': self.pending.id}), {'start_at': start_at, 'end_at': end_at})
        self.assertEqual(AuditLog.objects.filter(action='APPROVE_AUCTION').count(), 1)
    def test_creates_notification(self):
        self.client.login(username='admin', password='admin123')
        now = timezone.now()
        start_at = (now+timedelta(days=2)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        end_at = (now+timedelta(days=3)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        self.client.post(reverse('auctions:approve_auction', kwargs={'pk': self.pending.id}), {'start_at': start_at, 'end_at': end_at})
        self.assertEqual(Notification.objects.filter(user=self.seller, type='APPROVED').count(), 1)
    def test_end_before_start_error(self):
        self.client.login(username='admin', password='admin123')
        now = timezone.now()
        response = self.client.post(reverse('auctions:approve_auction', kwargs={'pk': self.pending.id}), {'start_at': (now+timedelta(days=3)).isoformat(), 'end_at': (now+timedelta(days=2)).isoformat()}, follow=True)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Auction.Status.PENDING)
    def test_start_in_past_error(self):
        self.client.login(username='admin', password='admin123')
        now = timezone.now()
        response = self.client.post(reverse('auctions:approve_auction', kwargs={'pk': self.pending.id}), {'start_at': (now-timedelta(days=1)).isoformat(), 'end_at': (now+timedelta(days=1)).isoformat()}, follow=True)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Auction.Status.PENDING)
    def test_cannot_approve_non_pending(self):
        self.pending.status = Auction.Status.LIVE
        self.pending.save()
        self.client.login(username='admin', password='admin123')
        now = timezone.now()
        response = self.client.post(reverse('auctions:approve_auction', kwargs={'pk': self.pending.id}), {'start_at': (now+timedelta(days=2)).isoformat(), 'end_at': (now+timedelta(days=3)).isoformat()}, follow=True)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Auction.Status.LIVE)
    def test_self_approval_forbidden(self):
        now = timezone.now()
        self.pending.seller = self.admin
        self.pending.save()
        self.client.login(username='admin', password='admin123')
        response = self.client.post(reverse('auctions:approve_auction', kwargs={'pk': self.pending.id}), {'start_at': (now+timedelta(days=2)).isoformat(), 'end_at': (now+timedelta(days=3)).isoformat()}, follow=True)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Auction.Status.PENDING)

class RejectAuctionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='admin', email='admin@enchere.plus', password='admin123', role=User.Role.ADMIN)
        cls.seller = User.objects.create_user(username='seller', email='seller@test.fr', password='test1234', role=User.Role.USER)
        cls.category = Category.objects.create(name='Test', slug='test')
        now = timezone.now()
        cls.pending = Auction.objects.create(seller=cls.seller, category=cls.category, title='To Reject', slug='to-reject', description='Test', starting_price=10000, min_increment=500, start_at=now+timedelta(days=1), end_at=now+timedelta(days=2), status=Auction.Status.PENDING)
    def test_valid_rejection(self):
        self.client.login(username='admin', password='admin123')
        response = self.client.post(reverse('auctions:reject_auction', kwargs={'pk': self.pending.id}), {'rejection_reason': 'Cette enchere ne respecte pas les criteres de qualite.'}, follow=True)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Auction.Status.REJECTED)
    def test_creates_audit_log(self):
        self.client.login(username='admin', password='admin123')
        self.client.post(reverse('auctions:reject_auction', kwargs={'pk': self.pending.id}), {'rejection_reason': 'Cette enchere ne respecte pas les criteres de qualite.'})
        self.assertEqual(AuditLog.objects.filter(action='REJECT_AUCTION').count(), 1)
    def test_creates_notification(self):
        self.client.login(username='admin', password='admin123')
        reason = 'Cette enchere ne respecte pas les criteres de qualite.'
        self.client.post(reverse('auctions:reject_auction', kwargs={'pk': self.pending.id}), {'rejection_reason': reason})
        notif = Notification.objects.filter(user=self.seller, type='REJECTED').first()
        self.assertEqual(notif.payload['reason'], reason)
    def test_empty_reason_error(self):
        self.client.login(username='admin', password='admin123')
        response = self.client.post(reverse('auctions:reject_auction', kwargs={'pk': self.pending.id}), {'rejection_reason': ''}, follow=True)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Auction.Status.PENDING)
    def test_short_reason_error(self):
        self.client.login(username='admin', password='admin123')
        response = self.client.post(reverse('auctions:reject_auction', kwargs={'pk': self.pending.id}), {'rejection_reason': 'Court'}, follow=True)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Auction.Status.PENDING)
    def test_cannot_reject_non_pending(self):
        self.pending.status = Auction.Status.LIVE
        self.pending.save()
        self.client.login(username='admin', password='admin123')
        response = self.client.post(reverse('auctions:reject_auction', kwargs={'pk': self.pending.id}), {'rejection_reason': 'Motif'}, follow=True)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Auction.Status.LIVE)

class AuditLogViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='admin', email='admin@enchere.plus', password='admin123', role=User.Role.ADMIN)
        cls.user = User.objects.create_user(username='user', email='user@test.fr', password='test1234', role=User.Role.USER)
        cls.category = Category.objects.create(name='Test', slug='test')
        now = timezone.now()
        auction = Auction.objects.create(seller=cls.user, category=cls.category, title='Test', slug='test', description='Test', starting_price=10000, min_increment=500, start_at=now+timedelta(days=1), end_at=now+timedelta(days=2), status=Auction.Status.PENDING)
        from auctions.utils import log_action
        log_action(actor=cls.admin, action='APPROVE_AUCTION', target_type='Auction', target_id=auction.id, details={'test': 'data'})
    def test_page_displays_entries(self):
        self.client.login(username='admin', password='admin123')
        response = self.client.get(reverse('auctions:audit_log'))
        self.assertContains(response, 'APPROVE_AUCTION')
    def test_json_payload(self):
        for log in AuditLog.objects.all():
            self.assertIsInstance(log.details, dict)
    def test_access_denied(self):
        response = self.client.get(reverse('auctions:audit_log'))
        self.assertEqual(response.status_code, 302)
        self.client.login(username='user', password='test1234')
        response = self.client.get(reverse('auctions:audit_log'))
        self.assertEqual(response.status_code, 403)
