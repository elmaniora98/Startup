from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    
    class Meta:
        verbose_name_plural = "Catégories"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Auction(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente de validation"
        REJECTED = "REJECTED", "Rejeté"
        SCHEDULED = "SCHEDULED", "Programmée"
        LIVE = "LIVE", "En cours"
        PAUSED = "PAUSED", "En pause"
        ENDED = "ENDED", "Terminée"
        SOLD = "SOLD", "Vendue"
        CANCELLED = "CANCELLED", "Annulée"

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="auctions"
    )
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="won_auctions"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    starting_price = models.PositiveIntegerField()  # centimes
    min_increment = models.PositiveIntegerField()  # centimes
    reserve_price = models.PositiveIntegerField(null=True, blank=True)
    buy_now_price = models.PositiveIntegerField(null=True, blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    current_price = models.PositiveIntegerField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    anti_snipe_minutes = models.PositiveIntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "end_at"]),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_current_price_euros(self):
        """Retourne le prix actuel en euros (float)"""
        if self.current_price:
            return self.current_price / 100
        return self.starting_price / 100

    def is_live(self):
        return self.status == self.Status.LIVE

    def can_bid(self):
        return self.status == self.Status.LIVE


class AuctionImage(models.Model):
    auction = models.ForeignKey(
        Auction,
        on_delete=models.CASCADE,
        related_name="images"
    )
    image = models.ImageField(upload_to="auctions/")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Image {self.order} - {self.auction.title}"


class Bid(models.Model):
    auction = models.ForeignKey(
        Auction,
        on_delete=models.CASCADE,
        related_name="bids"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    amount = models.PositiveIntegerField()  # centimes
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["auction", "-amount"]),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.amount}c sur {self.auction.title}"

    def get_amount_euros(self):
        return self.amount / 100


class Watchlist(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    auction = models.ForeignKey(
        Auction,
        on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ("user", "auction")

    def __str__(self):
        return f"{self.user.username} suit {self.auction.title}"


class Notification(models.Model):
    class Type(models.TextChoices):
        OUTBID = "OUTBID", "Surenchéri"
        WON = "WON", "Gagné"
        ENDING_SOON = "ENDING_SOON", "Bientôt terminé"
        APPROVED = "APPROVED", "Approuvé"
        REJECTED = "REJECTED", "Rejeté"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications"
    )
    type = models.CharField(max_length=30, choices=Type.choices)
    payload = models.JSONField(default=dict)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.type}] {self.user.username}"

    def is_unread(self):
        return self.read_at is None


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    action = models.CharField(max_length=50)
    target_type = models.CharField(max_length=50)
    target_id = models.CharField(max_length=50)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} par {self.actor} sur {self.target_type}#{self.target_id}"
