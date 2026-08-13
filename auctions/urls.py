from django.urls import path
from . import views

app_name = 'auctions'

urlpatterns = [
    path('', views.home, name='home'),
    path('recherche/', views.search, name='search'),
    path('enchere/<slug:slug>/', views.detail, name='detail'),
    path('api/time/', views.get_server_time, name='api_time'),
    path('api/auctions/<int:pk>/bid/', views.place_bid, name='api_place_bid'),
    path('api/auctions/<int:pk>/bids/', views.auction_bids_history, name='api_bids_history'),
    path('api/auctions/<int:pk>/watch/', views.toggle_watchlist, name='api_toggle_watchlist'),
    path('api/auctions/<int:pk>/price-block/', views.price_block, name='api_price_block'),
    path('categorie/<slug:slug>/', views.category, name='category'),
    
    # URLs pour la proposition et gestion des produits (Phase 2)
    path('compte/proposer/', views.propose_auction, name='propose_auction'),
    path('compte/mes-produits/', views.my_products, name='my_products_view'),
    path('compte/mes-produits/<int:pk>/modifier/', views.edit_auction, name='edit_auction'),
    path('compte/mes-produits/<int:pk>/supprimer/', views.delete_auction, name='delete_auction'),
]
