"""
Formulaires pour l'application auctions.
"""
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Auction, AuctionImage
import os


class ProposeAuctionForm(forms.ModelForm):
    """
    Formulaire de proposition d'enchère.
    Les prix sont saisis en euros (décimal) et convertis en centimes (entier) à la sauvegarde.
    """
    # Champs de prix en euros (saisie utilisateur)
    starting_price_euros = forms.DecimalField(
        label="Prix de départ (€)",
        min_value=0.01,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500'})
    )
    
    min_increment_euros = forms.DecimalField(
        label="Incrément minimum (€)",
        min_value=0.01,
        max_digits=8,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500'})
    )
    
    reserve_price_euros = forms.DecimalField(
        label="Prix de réserve (optionnel, €)",
        min_value=0.01,
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500'})
    )
    
    # Dates avec widget datetime-local
    start_at = forms.DateTimeField(
        label="Date et heure de début",
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500'
        })
    )
    
    end_at = forms.DateTimeField(
        label="Date et heure de fin",
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500'
        })
    )
    
    # Upload multiple d'images - on utilise un champ simple, la gestion du multiple se fait dans clean_images
    images = forms.FileField(
        label="Images du produit (1 à 5 images, max 5 Mo chacune)",
        widget=forms.ClearableFileInput(attrs={
            'accept': '.jpg,.jpeg,.png,.webp',
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500'
        }),
        required=True
    )
    
    class Meta:
        model = Auction
        fields = ['title', 'category', 'description', 'starting_price_euros', 
                  'min_increment_euros', 'reserve_price_euros', 'start_at', 'end_at', 'images']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500', 'maxlength': 200}),
            'category': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500'}),
            'description': forms.Textarea(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500', 'rows': 5}),
        }
    
    def __init__(self, *args, seller=None, **kwargs):
        self.seller = seller
        super().__init__(*args, **kwargs)
        # Valeur par défaut pour start_at : maintenant + 1 jour
        if not self.instance.pk and 'start_at' not in self.initial:
            from datetime import timedelta
            self.initial['start_at'] = (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
    
    def clean_starting_price_euros(self):
        """Valide que le prix de départ est > 0."""
        value = self.cleaned_data.get('starting_price_euros')
        if value is not None and value <= 0:
            raise ValidationError("Le prix de départ doit être supérieur à 0.")
        return value
    
    def clean_min_increment_euros(self):
        """Valide que l'incrément minimum est > 0."""
        value = self.cleaned_data.get('min_increment_euros')
        if value is not None and value <= 0:
            raise ValidationError("L'incrément minimum doit être supérieur à 0.")
        return value
    
    def clean_reserve_price_euros(self):
        """Valide que le prix de réserve est >= prix de départ si renseigné."""
        reserve = self.cleaned_data.get('reserve_price_euros')
        starting = self.cleaned_data.get('starting_price_euros')
        
        if reserve is not None and starting is not None:
            if reserve < starting:
                raise ValidationError("Le prix de réserve doit être supérieur ou égal au prix de départ.")
        return reserve
    
    def clean(self):
        """Validations croisées sur les dates et la durée."""
        cleaned_data = super().clean()
        
        start_at = cleaned_data.get('start_at')
        end_at = cleaned_data.get('end_at')
        
        if start_at and end_at:
            # end_at doit être strictement postérieur à start_at
            if end_at <= start_at:
                raise ValidationError("La date de fin doit être postérieure à la date de début.")
            
            # start_at doit être dans le futur
            now = timezone.now()
            if start_at <= now:
                raise ValidationError("La date de début doit être dans le futur.")
            
            # Durée entre 1 heure et 30 jours
            duration = end_at - start_at
            one_hour = timezone.timedelta(hours=1)
            thirty_days = timezone.timedelta(days=30)
            
            if duration < one_hour:
                raise ValidationError("La durée de l'enchère doit être d'au moins 1 heure.")
            
            if duration > thirty_days:
                raise ValidationError("La durée de l'enchère ne peut pas dépasser 30 jours.")
        
        return cleaned_data
    
    def clean_images(self):
        """Valide les images uploadées : nombre, taille, extensions."""
        images = self.files.getlist('images')
        
        if not images or len(images) == 0:
            raise ValidationError("Vous devez uploader au moins une image.")
        
        if len(images) > 5:
            raise ValidationError("Vous ne pouvez pas uploader plus de 5 images.")
        
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
        max_size = 5 * 1024 * 1024  # 5 Mo
        
        for image in images:
            # Vérifier l'extension
            ext = os.path.splitext(image.name)[1].lower()
            if ext not in allowed_extensions:
                raise ValidationError(f"Extension non autorisée : {image.name}. Seuls jpg, jpeg, png, webp sont acceptés.")
            
            # Vérifier la taille
            if image.size > max_size:
                raise ValidationError(f"L'image {image.name} dépasse 5 Mo.")
        
        return images
    
    def save(self, commit=True, user=None):
        """
        Sauvegarde l'enchère avec conversion des prix en centimes.
        Le statut est forcé à PENDING.
        """
        instance = super().save(commit=False)
        
        # Conversion des prix en centimes
        starting_price_euros = self.cleaned_data.get('starting_price_euros')
        min_increment_euros = self.cleaned_data.get('min_increment_euros')
        reserve_price_euros = self.cleaned_data.get('reserve_price_euros')
        
        instance.starting_price = int(starting_price_euros * 100)
        instance.min_increment = int(min_increment_euros * 100)
        
        if reserve_price_euros is not None:
            instance.reserve_price = int(reserve_price_euros * 100)
        else:
            instance.reserve_price = None
        
        # Forcer le statut à PENDING
        instance.status = Auction.Status.PENDING
        
        # Définir le vendeur
        if user:
            instance.seller = user
        
        if commit:
            instance.save()
            
            # Sauvegarder les images
            images = self.files.getlist('images')
            for order, image in enumerate(images):
                AuctionImage.objects.create(
                    auction=instance,
                    image=image,
                    order=order
                )
        
        return instance
