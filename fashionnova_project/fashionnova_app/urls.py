# fashionnova_app/urls.py
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.products, name='products'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('categories/', views.categories, name='categories'),

    # Brands
    path('brands/', views.brands_view, name='brands'),
    path('brands/<slug:slug>/', views.brand_products_view, name='brand_products'),

    path('about/', views.about_view, name='about'),
    path('search/', views.search, name='search'),

    # Cart URLs
    path('cart/', views.cart, name='cart'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove-from-cart/<int:cart_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('update-cart-quantity/', views.update_cart_quantity, name='update_cart_quantity'),

    # Wishlist URLs
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('add-to-wishlist/<int:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('remove-from-wishlist/<int:wishlist_id>/', views.remove_from_wishlist_view, name='remove_from_wishlist'),
    path('move-to-cart/<int:wishlist_id>/', views.move_to_cart_view, name='move_to_cart'),
    path('clear-wishlist/', views.clear_wishlist_view, name='clear_wishlist'),
    path('move-selected-to-cart/', views.move_selected_to_cart_view, name='move_selected_to_cart'),
    path('remove-selected-wishlist/', views.remove_selected_wishlist_view, name='remove_selected_wishlist'),

    # Checkout & Orders
    path('checkout/', views.checkout, name='checkout'),
    path('orders/', views.orders_view, name='orders'),
    path('orders/<int:order_id>/', views.order_detail_view, name='order_detail'),
    path('cancel-order/<int:order_id>/', views.cancel_order_view, name='cancel_order'),
    path('track-order/<int:order_id>/', views.track_order_view, name='track_order'),
    path('reorder-items/', views.reorder_items_view, name='reorder_items'),
    path('add-reorder-to-cart/', views.add_reorder_to_cart_view, name='add_reorder_to_cart'),

    # Seller URLs
    path('seller/dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('seller/add-product/', views.add_product, name='add_product'),
    path('seller/orders/', views.seller_orders_view, name='seller_orders'),
    path('seller/add-product/', views.add_product_view, name='add_product'),
     path('seller/update-products-status/', views.update_products_status_view, name='update_products_status'),
    path('seller/delete-products/', views.delete_products_view, name='delete_products'),
    path('products/', views.products_view, name='products'),

    # M-Pesa URLs
    #path('dajaja/stk_push', views.stk_push_callback, name='stk_push_callback'),
   path('process-mpesa/<int:order_id>/', views.process_mpesa_payment, name='process_mpesa_payment'),
    path('mpesa-callback/', views.mpesa_callback, name='mpesa_callback'),

    # Authentication URLs
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='users/logout.html'), name='logout'),

    # Seller URLs
    #*path('seller/dashboard/', views.seller_dashboard, name='seller_dashboard'),
    #path('seller/add-product/', add_product_view, name='add_product'),
    #path('seller/update-products-status/', update_products_status_view, name='update_products_status'),
    #path('seller/delete-products/', delete_products_view, name='delete_products'),
    #path('seller/orders/', seller_orders_view, name='seller_orders'),
    #path('seller/update-order-status/<int:order_id>/', update_order_status_view, name='update_order_status'),
    
    # Individual product actions
    #path('seller/toggle-product/<int:product_id>/<str:action>/', toggle_product_status_view, name='toggle_product_status'),
    #path('seller/delete-product/<int:product_id>/', delete_product_view, name='delete_product'),
    #path('seller/edit-product/<int:product_id>/', edit_product_view, name='edit_product'),
    
    # Store settings
    #path('seller/save-store-settings/', save_store_settings_view, name='save_store_settings'),
]
