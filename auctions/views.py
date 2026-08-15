from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.http.response import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction, models
from django.db.models import Count
from django.core.cache import cache
from django.contrib import messages
from django.utils.text import slugify
from datetime import timedelta
import json

from .models import Auction, Bid, Watchlist, Category, Notification, AuditLog
from .forms import ProposeAuctionForm


def error_404(request, exception):
    return render(request, 'errors/404.html', status=404)


def error_500(request):
    return render(request, 'errors/500.html', status=500)


def home(request):
    """Page d'accueil - grille des enchères LIVE et SCHEDULED"""
    category_slug = request.GET.get('category', '')
    sort_by = request.GET.get('sort', 'ending')

    live_filter = {'status': Auction.Status.LIVE}
    scheduled_filter = {'status': Auction.Status.SCHEDULED}

    if category_slug:
        live_filter['category__slug'] = category_slug
        scheduled_filter['category__slug'] = category_slug

    live_auctions = Auction.objects.filter(**live_filter)\
        .select_related('category')\
        .prefetch_related('images')\
        .annotate(bid_count=Count('bids'))\
        .order_by('end_at' if sort_by == 'ending' else '-created_at')

    scheduled_auctions = Auction.objects.filter(**scheduled_filter)\
        .select_related('category')\
        .prefetch_related('images')\
        .order_by('start_at')

    categories = Category.objects.all()

    unread_count = 0
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(user=request.user, read_at__isnull=True).count()

    context = {
        'live_auctions': live_auctions,
        'scheduled_auctions': scheduled_auctions,
        'categories': categories,
        'unread_count': unread_count,
        'selected_category': category_slug,
        'selected_sort': sort_by,
    }
    return render(request, 'auctions/home.html', context)


def search(request):
    """Recherche d'enchères"""
    query = request.GET.get('q', '')
    category_slug = request.GET.get('category', '')
    status = request.GET.get('status', 'LIVE')

    auctions = Auction.objects.filter(status=status).select_related('category').prefetch_related('images')

    if query:
        auctions = auctions.filter(title__icontains=query)

    if category_slug:
        auctions = auctions.filter(category__slug=category_slug)

    categories = Category.objects.all()

    unread_count = 0
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(user=request.user, read_at__isnull=True).count()

    context = {
        'auctions': auctions,
        'categories': categories,
        'query': query,
        'selected_category': category_slug,
        'selected_status': status,
        'unread_count': unread_count,
    }
    return render(request, 'auctions/search.html', context)


def detail(request, slug):
    """Page de détail d'une enchère"""
    auction = get_object_or_404(
        Auction.objects.select_related('seller', 'category', 'winner').prefetch_related('images', 'bids__user'),
        slug=slug
    )

    # Règles d'accès : PENDING, REJECTED, CANCELLED visibles uniquement par le vendeur et les admins
    if auction.status in [Auction.Status.PENDING, Auction.Status.REJECTED, Auction.Status.CANCELLED]:
        if not request.user.is_authenticated:
            return render(request, 'errors/404.html', status=404)
        if request.user != auction.seller and request.user.role != request.user.Role.ADMIN:
            return render(request, 'errors/404.html', status=404)

    # Historique des enchères (top 10)
    bids = auction.bids.select_related('user').order_by('-amount', '-created_at')[:10]

    # Enchères similaires (même catégorie, LIVE ou SCHEDULED, excluant l'enchère courante)
    similar_auctions = Auction.objects.filter(
        category=auction.category,
        status__in=[Auction.Status.LIVE, Auction.Status.SCHEDULED]
    ).exclude(pk=auction.pk).prefetch_related('images')[:4]

    # Vérifier si l'utilisateur suit cette enchère
    is_watching = False
    if request.user.is_authenticated:
        is_watching = Watchlist.objects.filter(user=request.user, auction=auction).exists()
        
        # Marquer les notifications liées à cette enchère comme lues
        Notification.objects.filter(
            user=request.user,
            payload__auction_id=auction.id,
            read_at__isnull=True
        ).update(read_at=timezone.now())

    # Calcul du minimum pour la prochaine enchère
    min_next_bid = auction.starting_price
    if auction.current_price:
        min_next_bid = auction.current_price + auction.min_increment

    unread_count = 0
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(user=request.user, read_at__isnull=True).count()

    context = {
        'auction': auction,
        'bids': bids,
        'similar_auctions': similar_auctions,
        'is_watching': is_watching,
        'min_next_bid': min_next_bid,
        'unread_count': unread_count,
    }
    return render(request, 'auctions/detail.html', context)


def category(request, slug):
    """Page de catégorie"""
    category_obj = get_object_or_404(Category, slug=slug)
    auctions = Auction.objects.filter(category=category_obj, status=Auction.Status.LIVE).prefetch_related('images')

    unread_count = 0
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(user=request.user, read_at__isnull=True).count()

    context = {
        'category': category_obj,
        'auctions': auctions,
        'unread_count': unread_count,
    }
    return render(request, 'auctions/category.html', context)


def get_server_time(request):
    """API: Retourne l'heure serveur pour synchronisation du compte à rebours"""
    return JsonResponse({
        'server_time': timezone.now().isoformat()
    })


@login_required
@transaction.atomic
def place_bid(request, pk):
    """API: Placer une enchère"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    auction = Auction.objects.select_for_update().get(pk=pk)

    if auction.status != Auction.Status.LIVE:
        return JsonResponse({'error': "Cette enchère n'est pas en cours"}, status=400)

    if auction.seller == request.user:
        return JsonResponse({'error': 'Vous ne pouvez pas enchérir sur votre propre produit'}, status=400)

    if timezone.now() >= auction.end_at:
        auction.status = Auction.Status.ENDED
        auction.save()
        return JsonResponse({'error': 'Cette enchère est terminée'}, status=400)

    try:
        data = json.loads(request.body)
        amount = int(data.get('amount', 0))
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Montant invalide'}, status=400)

    min_bid = auction.starting_price
    if auction.current_price:
        min_bid = auction.current_price + auction.min_increment

    if amount < min_bid:
        return JsonResponse({
            'error': f'Le montant minimum est de {min_bid} centimes ({min_bid/100:.2f} €)',
            'min_bid': min_bid
        }, status=400)

    cache_key = f'bid_rate_limit_{request.user.id}'
    current_count = cache.get(cache_key, 0)
    if current_count >= 10:
        return JsonResponse({'error': 'Trop de tentatives. Veuillez patienter.'}, status=429)
    cache.set(cache_key, current_count + 1, 60)

    bid = Bid.objects.create(auction=auction, user=request.user, amount=amount)

    auction.current_price = amount
    auction.save()

    time_remaining = auction.end_at - timezone.now()
    if time_remaining.total_seconds() < auction.anti_snipe_minutes * 60:
        auction.end_at += timedelta(minutes=auction.anti_snipe_minutes)
        auction.save()

    previous_bidders = Bid.objects.filter(auction=auction).exclude(user=request.user).values_list('user', flat=True).distinct()
    for bidder_id in previous_bidders[:5]:
        Notification.objects.create(
            user_id=bidder_id,
            type=Notification.Type.OUTBID,
            payload={'auction_id': auction.id, 'auction_title': auction.title}
        )

    return JsonResponse({
        'success': True,
        'new_price': amount,
        'new_price_display': f'{amount/100:.2f} €',
        'end_at': auction.end_at.isoformat(),
        'bid_count': auction.bids.count()
    })


def auction_bids_history(request, pk):
    """API: Historique des enchères (fragment HTMX)"""
    auction = get_object_or_404(Auction, pk=pk)
    bids = auction.bids.select_related('user').order_by('-amount', '-created_at')[:20]

    context = {'bids': bids, 'auction': auction}
    return render(request, 'auctions/fragments/bids_history.html', context)


@login_required
def toggle_watchlist(request, pk):
    """API: Suivre/ne plus suivre une enchère"""
    auction = get_object_or_404(Auction, pk=pk)

    watchlist_item, created = Watchlist.objects.get_or_create(user=request.user, auction=auction)

    if not created:
        watchlist_item.delete()
        return JsonResponse({'watching': False})

    return JsonResponse({'watching': True})


def price_block(request, pk):
    """API: Bloc prix actuel (fragment HTMX pour polling)"""
    auction = get_object_or_404(Auction, pk=pk)
    bid_count = auction.bids.count()

    context = {'auction': auction, 'bid_count': bid_count}
    return render(request, 'auctions/fragments/price_block.html', context)


@login_required
def propose_auction(request):
    """Formulaire de proposition d'enchère"""
    if request.method == 'POST':
        form = ProposeAuctionForm(request.POST, request.FILES)
        if form.is_valid():
            auction = form.save(user=request.user)
            
            # Générer un slug unique
            base_slug = slugify(auction.title)
            slug = base_slug
            counter = 2
            while Auction.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            auction.slug = slug
            auction.save()
            
            messages.success(request, 'Votre produit a bien été soumis. Il sera examiné par un administrateur d\'Enchère+ avant publication.')
            return redirect('accounts:my_products')
    else:
        form = ProposeAuctionForm()

    return render(request, 'auctions/propose.html', {'form': form})


@login_required
def my_products(request):
    """Liste des produits soumis par l'utilisateur"""
    auctions = Auction.objects.filter(seller=request.user).order_by('-created_at')
    return render(request, 'accounts/my_products.html', {'auctions': auctions})


@login_required
def edit_auction(request, pk):
    """Modification d'une enchère (uniquement si PENDING)"""
    auction = get_object_or_404(Auction, pk=pk)
    
    # Vérifier que l'utilisateur est le propriétaire
    if auction.seller != request.user:
        return HttpResponseForbidden("Vous n'êtes pas autorisé à modifier cette enchère.")
    
    if auction.status != Auction.Status.PENDING:
        messages.error(request, 'Vous ne pouvez modifier que les enchères en attente de validation.')
        return redirect('accounts:my_products')
    
    if request.method == 'POST':
        form = ProposeAuctionForm(request.POST, request.FILES, instance=auction)
        if form.is_valid():
            auction = form.save(commit=False)
            auction.status = Auction.Status.PENDING
            
            starting_price_euros = form.cleaned_data.get('starting_price_euros')
            min_increment_euros = form.cleaned_data.get('min_increment_euros')
            reserve_price_euros = form.cleaned_data.get('reserve_price_euros')
            
            auction.starting_price = int(starting_price_euros * 100)
            auction.min_increment = int(min_increment_euros * 100)
            
            if reserve_price_euros is not None:
                auction.reserve_price = int(reserve_price_euros * 100)
            
            auction.save()
            
            # Gérer les nouvelles images
            images = request.FILES.getlist('images')
            existing_order = auction.images.count()
            for image in images:
                AuctionImage.objects.create(
                    auction=auction,
                    image=image,
                    order=existing_order
                )
                existing_order += 1
            
            messages.success(request, 'Votre enchère a été modifiée avec succès.')
            return redirect('accounts:my_products')
    else:
        # Initialiser le formulaire avec les valeurs existantes converties en euros
        initial_data = {
            'starting_price_euros': auction.starting_price / 100,
            'min_increment_euros': auction.min_increment / 100,
        }
        if auction.reserve_price:
            initial_data['reserve_price_euros'] = auction.reserve_price / 100
        form = ProposeAuctionForm(instance=auction, initial=initial_data)

    return render(request, 'auctions/propose.html', {'form': form, 'editing': True, 'auction': auction})


@login_required
def delete_auction(request, pk):
    """Suppression d'une enchère (uniquement si PENDING)"""
    auction = get_object_or_404(Auction, pk=pk)
    
    # Vérifier que l'utilisateur est le propriétaire
    if auction.seller != request.user:
        return HttpResponseForbidden("Vous n'êtes pas autorisé à supprimer cette enchère.")
    
    if auction.status != Auction.Status.PENDING:
        messages.error(request, 'Vous ne pouvez supprimer que les enchères en attente de validation.')
        return redirect('accounts:my_products')
    
    if request.method == 'POST':
        auction.delete()
        messages.success(request, 'Votre enchère a été supprimée.')
        return redirect('accounts:my_products')

    return render(request, 'auctions/delete_confirm.html', {'auction': auction})


# =============================================================================
# VUES ADMIN
# =============================================================================

from auctions.decorators import admin_required
from auctions.utils import log_action
from auctions.models import AuditLog


@admin_required
def admin_dashboard(request):
    """Tableau de bord admin avec statistiques"""
    from accounts.models import User
    from auctions.models import Bid
    
    pending_count = Auction.objects.filter(status=Auction.Status.PENDING).count()
    live_count = Auction.objects.filter(status=Auction.Status.LIVE).count()
    user_count = User.objects.count()
    bid_count = Bid.objects.count()
    
    context = {
        'pending_count': pending_count,
        'live_count': live_count,
        'user_count': user_count,
        'bid_count': bid_count,
    }
    
    return render(request, 'admin/dashboard.html', context)


@admin_required
def validation_queue(request):
    """File d'attente des enchères en attente de validation"""
    pending_auctions = Auction.objects.filter(
        status=Auction.Status.PENDING
    ).select_related('seller', 'category').prefetch_related('images').order_by('created_at')
    
    pending_count = pending_auctions.count()
    
    context = {
        'pending_auctions': pending_auctions,
        'pending_count': pending_count,
    }
    
    return render(request, 'admin/validation_queue.html', context)


@admin_required
def approve_auction(request, pk):
    """Approbation d'une enchère avec ajustement des dates"""
    auction = get_object_or_404(Auction, pk=pk)
    
    # Vérifier que l'enchère est toujours PENDING
    if auction.status != Auction.Status.PENDING:
        messages.error(request, f"Cette enchère n'est plus en attente (statut actuel : {auction.get_status_display()}).")
        return redirect('validation_queue')
    
    # Vérifier que l'admin n'est pas le vendeur
    if auction.seller == request.user:
        messages.error(request, "Vous ne pouvez pas valider votre propre soumission.")
        return redirect('validation_queue')
    
    if request.method == 'POST':
        start_at_str = request.POST.get('start_at')
        end_at_str = request.POST.get('end_at')
        
        if not start_at_str or not end_at_str:
            messages.error(request, "Les dates de début et de fin sont obligatoires.")
            return redirect('validation_queue')
        
        from django.utils import timezone
        from datetime import timedelta
        
        try:
            start_at = timezone.make_aware(timezone.datetime.fromisoformat(start_at_str.replace('Z', '+00:00')))
            end_at = timezone.make_aware(timezone.datetime.fromisoformat(end_at_str.replace('Z', '+00:00')))
        except (ValueError, TypeError):
            messages.error(request, "Format de date invalide.")
            return redirect('validation_queue')
        
        # Validations
        now = timezone.now()
        duration = end_at - start_at
        
        if end_at <= start_at:
            messages.error(request, "La date de fin doit être postérieure à la date de début.")
            return redirect('validation_queue')
        
        if start_at < now:
            messages.error(request, "La date de début doit être dans le futur.")
            return redirect('validation_queue')
        
        if duration < timedelta(hours=1):
            messages.error(request, "La durée minimale est de 1 heure.")
            return redirect('validation_queue')
        
        if duration > timedelta(days=30):
            messages.error(request, "La durée maximale est de 30 jours.")
            return redirect('validation_queue')
        
        # Mise à jour de l'enchère
        auction.start_at = start_at
        auction.end_at = end_at
        auction.status = Auction.Status.SCHEDULED
        auction.save()
        
        # Créer la notification pour le vendeur
        Notification.objects.create(
            user=auction.seller,
            type='APPROVED',
            payload={
                'auction_id': auction.id,
                'auction_title': auction.title,
                'start_at': str(start_at),
                'end_at': str(end_at),
            }
        )
        
        # Journaliser dans l'AuditLog
        log_action(
            actor=request.user,
            action='APPROVE_AUCTION',
            target_type='Auction',
            target_id=auction.id,
            details={
                'start_at': str(start_at),
                'end_at': str(end_at),
                'title': auction.title,
                'seller': auction.seller.username,
            }
        )
        
        messages.success(request, f"L'enchère '{auction.title}' a été approuvée et programmée.")
        return redirect('validation_queue')
    
    return redirect('validation_queue')


@admin_required
def reject_auction(request, pk):
    """Rejet d'une enchère avec motif obligatoire"""
    auction = get_object_or_404(Auction, pk=pk)
    
    # Vérifier que l'enchère est toujours PENDING
    if auction.status != Auction.Status.PENDING:
        messages.error(request, f"Cette enchère n'est plus en attente (statut actuel : {auction.get_status_display()}).")
        return redirect('validation_queue')
    
    # Vérifier que l'admin n'est pas le vendeur
    if auction.seller == request.user:
        messages.error(request, "Vous ne pouvez pas rejeter votre propre soumission.")
        return redirect('validation_queue')
    
    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason', '').strip()
        
        if len(rejection_reason) < 10:
            messages.error(request, "Le motif de rejet doit contenir au moins 10 caractères.")
            return redirect('validation_queue')
        
        # Mise à jour de l'enchère
        auction.status = Auction.Status.REJECTED
        auction.rejection_reason = rejection_reason
        auction.save()
        
        # Créer la notification pour le vendeur
        Notification.objects.create(
            user=auction.seller,
            type='REJECTED',
            payload={
                'auction_id': auction.id,
                'auction_title': auction.title,
                'reason': rejection_reason,
            }
        )
        
        # Journaliser dans l'AuditLog
        log_action(
            actor=request.user,
            action='REJECT_AUCTION',
            target_type='Auction',
            target_id=auction.id,
            details={
                'motif': rejection_reason,
                'title': auction.title,
                'seller': auction.seller.username,
            }
        )
        
        messages.success(request, f"L'enchère '{auction.title}' a été rejetée.")
        return redirect('validation_queue')
    
    return redirect('validation_queue')


@admin_required
def audit_log_view(request):
    """Journal d'audit paginé"""
    from django.core.paginator import Paginator
    
    audit_logs = AuditLog.objects.select_related('actor').order_by('-created_at')
    
    paginator = Paginator(audit_logs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    pending_count = Auction.objects.filter(status=Auction.Status.PENDING).count()
    
    context = {
        'audit_logs': page_obj,
        'page_obj': page_obj,
        'pending_count': pending_count,
    }
    
    return render(request, 'admin/audit_log.html', context)
