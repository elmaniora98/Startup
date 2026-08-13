from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('inscription/', views.register, name='register'),
    path('connexion/', views.login_view, name='login'),
    path('deconnexion/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('mes-produits/', views.my_products, name='my_products'),
    path('suivis/', views.watchlist, name='watchlist'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/mark-read/<int:pk>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
]
