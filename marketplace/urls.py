from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    # Auth
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    # Onboarding
    path('seller-onboard/', views.seller_onboard, name='seller_onboard'),
    # Profiles
    path('profile/', views.profile, name='profile'),
    path('profile/customer/', views.customer_profile, name='customer_profile'),
    path('profile/seller/', views.seller_profile, name='seller_profile'),
    path('profile/admin/', views.admin_profile, name='admin_profile'),
    # Products
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('product/<int:product_id>/edit/', views.edit_product, name='edit_product'),
    path('product/<int:product_id>/add-to-cart/', views.add_to_cart, name='add_to_cart'),
    path('product/<int:product_id>/wishlist/', views.toggle_wishlist, name='toggle_wishlist'),
    # Brands
    path('brands/', views.brands_list, name='brands'),
    path('brand/<int:brand_id>/', views.brand_detail, name='brand_detail'),
    path('brand/<int:brand_id>/follow/', views.follow_brand, name='follow_brand'),
    # Categories & Deals
    path('categories/', views.categories, name='categories'),
    path('deals/', views.deals, name='deals'),
    # Cart
    path('cart/', views.cart, name='cart'),
    path('cart/update/<int:item_id>/', views.update_cart, name='update_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    # Checkout & Escrow
    path('checkout/', views.checkout, name='checkout'),
    path('order/<int:order_id>/confirm/', views.confirm_delivery, name='confirm_delivery'),
    path('order/<int:order_id>/ship/', views.mark_order_shipped, name='mark_order_shipped'),
    # Order management
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('order/<int:order_id>/cancel/', views.cancel_order, name='cancel_order'),
    path('order/<int:order_id>/dispute/', views.dispute_order, name='dispute_order'),
    path('order/<int:order_id>/enquiry/', views.send_enquiry, name='send_enquiry'),
    path('order/<int:order_id>/reply/', views.reply_enquiry, name='reply_enquiry'),
    # Paystack
    path('paystack/initiate/', views.paystack_initiate, name='paystack_initiate'),
    path('paystack/verify/', views.paystack_verify, name='paystack_verify'),
    path('paystack/webhook/', views.paystack_webhook, name='paystack_webhook'),
    # Pro upgrade
    path('upgrade/initiate/', views.upgrade_initiate, name='upgrade_initiate'),
    path('upgrade/verify/', views.upgrade_verify, name='upgrade_verify'),
    # Hub / Cross-Docking
    path('hub/', views.hub_dashboard, name='hub_dashboard'),
    path('master-order/<int:master_id>/confirm/', views.confirm_master_delivery, name='confirm_master_delivery'),
    # Support Chat
    path('support/', views.support_chat, name='support_chat'),
    path('support/reply/', views.support_reply, name='support_reply'),
    # University/Area API
    path('api/universities/', views.universities_list, name='universities_list'),
    path('api/campus-areas/', views.get_campus_areas, name='get_campus_areas'),
    # PWA offline page
    path('offline/', views.offline_page, name='offline'),
    # Wishlist
    path('wishlist/', views.wishlist, name='wishlist'),
    # Notifications
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:notif_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/<int:notif_id>/delete/', views.delete_notification, name='delete_notification'),
]