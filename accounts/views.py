from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse
from .forms import RegisterForm, LoginForm
from auctions.models import Auction, Watchlist, Notification


def register(request):
    """Inscription d'un nouvel utilisateur"""
    if request.user.is_authenticated:
        return redirect('auctions:home')
    
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = user.Role.USER  # Par défaut, rôle USER
            user.save()
            login(request, user)
            messages.success(request, 'Compte créé avec succès ! Bienvenue sur Enchère+.')
            return redirect('auctions:home')
    else:
        form = RegisterForm()
    
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    """Connexion utilisateur"""
    if request.user.is_authenticated:
        return redirect('auctions:home')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Heureux de vous revoir, {user.username} !')
            return redirect('auctions:home')
    else:
        form = LoginForm()
    
    return render(request, 'registration/login.html', {'form': form})


def logout_view(request):
    """Déconnexion utilisateur"""
    logout(request)
    messages.info(request, 'Vous avez été déconnecté.')
    return redirect('auctions:home')


@login_required
def dashboard(request):
    """Tableau de bord utilisateur"""
    # Mes enchères en cours (où j'enchéris)
    my_bids = Auction.objects.filter(
        bids__user=request.user
    ).distinct().filter(
        status__in=[Auction.Status.LIVE, Auction.Status.SCHEDULED]
    )
    
    # Mes produits vendus/en cours
    my_auctions = Auction.objects.filter(seller=request.user)
    
    # Mes gains
    won_auctions = Auction.objects.filter(winner=request.user, status=Auction.Status.SOLD)
    
    # Watchlist
    watchlist_items = Watchlist.objects.filter(user=request.user).select_related('auction')
    
    context = {
        'my_bids': my_bids,
        'my_auctions': my_auctions,
        'won_auctions': won_auctions,
        'watchlist_items': watchlist_items,
    }
    
    return render(request, 'accounts/dashboard.html', context)


@login_required
def my_products(request):
    """Liste des produits soumis par l'utilisateur"""
    auctions = Auction.objects.filter(seller=request.user).order_by('-created_at')
    return render(request, 'accounts/my_products.html', {'auctions': auctions})


@login_required
def watchlist(request):
    """Liste des enchères suivies"""
    watchlist_items = Watchlist.objects.filter(user=request.user).select_related('auction').order_by('-id')
    return render(request, 'accounts/watchlist.html', {'watchlist_items': watchlist_items})


@login_required
def notifications(request):
    """Liste des notifications"""
    unread_count = Notification.objects.filter(user=request.user, read_at__isnull=True).count()
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:50]
    return render(request, 'accounts/notifications.html', {
        'notifications': notifications,
        'unread_count': unread_count,
    })


@login_required
def mark_notification_read(request, pk):
    """Marquer une notification comme lue"""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.read_at = timezone.now()
    notification.save()
    
    if request.headers.get('HX-Request'):
        return HttpResponse('')
    
    return redirect('accounts:notifications')


@login_required
def mark_all_notifications_read(request):
    """Marquer toutes les notifications comme lues"""
    Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
    
    if request.headers.get('HX-Request'):
        return HttpResponse('')
    
    return redirect('accounts:notifications')

