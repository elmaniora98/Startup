from django.urls import path
from . import views

app_name = 'auctions'

urlpatterns = [
    # Public URLs
    path('', views.home, name='home'),
    path('recherche/', views.search, name='search'),
    path('enchere/<slug:slug>/', views.detail, name='detail'),
    path('api/time/', views.get_server_time, name='api_time'),
    path('api/auctions/<int:pk>/bid/', views.place_bid, name='api_place_bid'),
    path('api/auctions/<int:pk>/bids/', views.auction_bids_history, name='api_bids_history'),
    path('api/auctions/<int:pk>/watch/', views.toggle_watchlist, name='api_toggle_watchlist'),
    path('api/auctions/<int:pk>/price-block/', views.price_block, name='api_price_block'),
    path('categorie/<slug:slug>/', views.category, name='category'),

    # User space (Phase 2)
    path('compte/proposer/', views.propose_auction, name='propose_auction'),
    path('compte/mes-produits/', views.my_products, name='my_products_view'),
    path('compte/mes-produits/<int:pk>/modifier/', views.edit_auction, name='edit_auction'),
    path('compte/mes-produits/<int:pk>/supprimer/', views.delete_auction, name='delete_auction'),

    # Admin dashboard (Phase 3)
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/validation/', views.validation_queue, name='validation_queue'),
    path('admin-dashboard/validation/<int:pk>/approve/', views.approve_auction, name='approve_auction'),
    path('admin-dashboard/validation/<int:pk>/reject/', views.reject_auction, name='reject_auction'),
    path('admin-dashboard/audit/', views.audit_log_view, name='audit_log'),

    # Admin advanced - Auctions management (Phase 7)
    path('admin-dashboard/encheres/', views.admin_auctions, name='admin_auctions'),
    path('admin-dashboard/encheres/<int:pk>/', views.admin_auction_detail, name='admin_auction_detail'),
    path('admin-dashboard/encheres/<int:pk>/pause/', views.pause_auction, name='pause_auction'),
    path('admin-dashboard/encheres/<int:pk>/resume/', views.resume_auction, name='resume_auction'),
    path('admin-dashboard/encheres/<int:pk>/cancel/', views.cancel_auction, name='cancel_auction'),
    path('admin-dashboard/encheres/<int:pk>/extend/', views.extend_auction, name='extend_auction'),

    # Admin advanced - Users management (Phase 7)
    path('admin-dashboard/utilisateurs/', views.admin_users, name='admin_users'),
    path('admin-dashboard/utilisateurs/<int:pk>/', views.admin_user_detail, name='admin_user_detail'),
    path('admin-dashboard/utilisateurs/<int:pk>/block/', views.block_user, name='block_user'),
    path('admin-dashboard/utilisateurs/<int:pk>/unblock/', views.unblock_user, name='unblock_user'),
    path('admin-dashboard/utilisateurs/<int:pk>/promote/', views.promote_user, name='promote_user'),
    path('admin-dashboard/utilisateurs/<int:pk>/demote/', views.demote_user, name='demote_user'),

    # Admin advanced - Categories management (Phase 7)
    path('admin-dashboard/categories/', views.admin_categories, name='admin_categories'),
    path('admin-dashboard/categories/create/', views.create_category, name='create_category'),
    path('admin-dashboard/categories/<int:pk>/edit/', views.edit_category, name='edit_category'),
    path('admin-dashboard/categories/<int:pk>/delete/', views.delete_category, name='delete_category'),
]
