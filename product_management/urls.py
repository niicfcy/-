from django.urls import path
from . import views

app_name = 'product_management'

urlpatterns = [
    path('products/', views.product_list, name='product_list'),
    path('add_to_cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove_from_cart/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('update_cart/<int:product_id>/', views.update_cart, name='update_cart'),
    path('view_cart/', views.view_cart, name='view_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/process/', views.process_checkout, name='process_checkout'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('order_history/', views.order_history, name='order_history'),
    path('profile/', views.profile_view, name='profile'),
    path('change_password/', views.change_password, name='change_password'),
    path('search/', views.search_products, name='search'),
]