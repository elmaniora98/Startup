from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        USER = "USER", "Utilisateur"
        ADMIN = "ADMIN", "Administrateur"
    
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.USER
    )
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    
    def is_admin(self):
        return self.role == self.Role.ADMIN
    
    def is_seller(self):
        return self.role == self.Role.USER
