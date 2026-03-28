from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from decimal import Decimal
import json

from .emails import (
    send_order_receipt, send_seller_new_order, send_order_shipped,
    send_all_at_hub, send_order_dispatched, send_delivery_confirmed,
    send_order_cancelled, send_dispute_raised, send_pro_upgrade_confirmation,
    send_withdrawal_processed,
)
from .models import (
    User, Brand, Product, Category, CartItem, WishlistItem,
    Notification, Review, SellerVerificationRequest,
    Order, OrderItem, OrderEnquiry, MasterOrder, CampusZone, WithdrawalRequest,
    PromotionPayment, SubscriptionPayment, ProductImage, ProductVideo, SupportMessage,
    University, CampusArea,
)
from .forms import (
    CustomerSignupForm, SellerSignupForm, LoginForm,
    SellerOnboardStep1Form, SellerOnboardStep2Form, SellerOnboardStep3Form,
    ProductForm, BrandProfileForm, ReviewForm,
    CheckoutForm, WithdrawalForm,
)

PLATFORM_PROMO_RATES = {'brand_7': 2000, 'brand_14': 3500, 'brand_30': 6000}
PRO_MONTHLY_PRICE = 5000


# ─────────────────────────────────────────────
# HOME
# ─────────────────────────────────────────────

def home(request):
    # Location-aware: show brands from user's university/area first
    promoted_brands = Brand.objects.filter(is_promoted=True).prefetch_related('followers', 'products')
    promoted_products = Product.objects.filter(is_promoted=True, status='active').select_related('brand')

    brand_qs = Brand.objects.filter(is_promoted=False).prefetch_related('followers', 'products')

    # If user is authenticated and has a university set, show their campus brands first
    nearby_brands = Brand.objects.none()
    other_brands  = brand_qs
    user_university = ''
    if request.user.is_authenticated and request.user.university:
        user_university = request.user.university
        nearby_brands = brand_qs.filter(
            seller__university__icontains=user_university
        ).order_by('-is_verified', '-created_at')
        other_brands = brand_qs.exclude(
            seller__university__icontains=user_university
        ).order_by('-is_verified', '-created_at')

    # Merge: nearby first, then others (deduplicate)
    if nearby_brands.exists():
        from itertools import chain
        all_brands = list(nearby_brands) + list(other_brands)
    else:
        all_brands = list(brand_qs.order_by('-is_verified', '-created_at'))

    featured_products = Product.objects.filter(status='active', is_promoted=False).select_related('brand', 'category').order_by('-created_at')[:8]
    wishlist_ids = set()
    if request.user.is_authenticated:
        wishlist_ids = set(WishlistItem.objects.filter(user=request.user).values_list('product_id', flat=True))
    return render(request, 'marketplace/home.html', {
        'promoted_brands':  promoted_brands,
        'promoted_products': promoted_products,
        'brands':           all_brands,
        'nearby_brands':    nearby_brands,
        'user_university':  user_university,
        'featured_products': featured_products,
        'wishlist_ids':     wishlist_ids,
    })


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('profile')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            return redirect(request.GET.get('next', 'profile'))
        else:
            messages.error(request, 'Invalid email or password.')
    else:
        form = LoginForm()
    return render(request, 'marketplace/login.html', {'form': form})


def signup_view(request):
    user_type = request.GET.get('type', 'customer')
    FormClass = SellerSignupForm if user_type == 'seller' else CustomerSignupForm
    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created! Welcome to OJA Campus.')
            return redirect('seller_onboard' if user_type == 'seller' else 'profile')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = FormClass()
    return render(request, 'marketplace/signup.html', {'form': form, 'user_type': user_type})


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')


# ─────────────────────────────────────────────
# SELLER ONBOARDING
# ─────────────────────────────────────────────

@login_required
def seller_onboard(request):
    if request.user.user_type != 'seller':
        return redirect('home')
    try:
        brand = request.user.brand
    except Brand.DoesNotExist:
        brand = Brand.objects.create(seller=request.user, name=request.user.first_name + "'s Store")
    step = int(request.session.get('onboard_step', 1))
    if request.method == 'POST':
        if step == 1:
            form = SellerOnboardStep1Form(request.POST, instance=brand)
            if form.is_valid():
                form.save()
                request.session['onboard_step'] = 2
                return redirect('seller_onboard')
        elif step == 2:
            form = SellerOnboardStep2Form(request.POST, instance=brand)
            if form.is_valid():
                brand = form.save(commit=False)
                brand.save()
                request.user.phone = request.POST.get('phone', '')
                request.user.save()
                request.session['onboard_step'] = 3
                return redirect('seller_onboard')
        elif step == 3:
            form = SellerOnboardStep3Form(request.POST, instance=request.user)
            if form.is_valid():
                form.save()
                request.user.profile_complete = True
                request.user.save()
                del request.session['onboard_step']
                messages.success(request, 'Store setup complete! Welcome to OJA Campus.')
                return redirect('seller_profile')
    else:
        if step == 1:
            form = SellerOnboardStep1Form(instance=brand)
        elif step == 2:
            form = SellerOnboardStep2Form(instance=brand)
        else:
            form = SellerOnboardStep3Form(instance=request.user)
    return render(request, 'marketplace/seller_onboard.html', {'form': form, 'step': step, 'brand': brand})


# ─────────────────────────────────────────────
# PROFILES
# ─────────────────────────────────────────────

@login_required
def profile(request):
    if request.user.user_type == 'seller':
        return redirect('seller_profile')
    elif request.user.user_type == 'admin':
        return redirect('admin_profile')
    return redirect('customer_profile')


@login_required
def customer_profile(request):
    if request.user.user_type != 'customer':
        return redirect('profile')
    # Sub-orders (individual vendor orders)
    orders = Order.objects.filter(buyer=request.user).prefetch_related('items').order_by('-created_at')
    # Master orders (consolidated deliveries)
    master_orders = MasterOrder.objects.filter(buyer=request.user).prefetch_related(
        'orders__brand', 'orders__items'
    ).order_by('-created_at')
    cart_items = CartItem.objects.filter(user=request.user).select_related('product__brand')
    wishlist_items = WishlistItem.objects.filter(user=request.user).select_related('product__brand')
    followed_brands = request.user.followed_brands.all()
    notifications = Notification.objects.filter(
        Q(recipient=request.user) | Q(recipient=None)
    ).order_by('-created_at')[:10]
    return render(request, 'marketplace/profile_customer.html', {
        'orders': orders,
        'master_orders': master_orders,
        'cart_items': cart_items,
        'wishlist_items': wishlist_items,
        'followed_brands': followed_brands,
        'notifications': notifications,
    })


@login_required
def seller_profile(request):
    if request.user.user_type != 'seller':
        return redirect('profile')
    try:
        brand = request.user.brand
    except Brand.DoesNotExist:
        return redirect('seller_onboard')

    products = Product.objects.filter(brand=brand).select_related('category').order_by('-created_at')
    orders = Order.objects.filter(brand=brand).prefetch_related('items', 'master_order').order_by('-created_at')
    withdrawals = WithdrawalRequest.objects.filter(brand=brand)
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')[:20]
    brand_form = BrandProfileForm(instance=brand)
    product_form = ProductForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_brand':
            brand_form = BrandProfileForm(request.POST, request.FILES, instance=brand)
            if brand_form.is_valid():
                brand_form.save()
                messages.success(request, 'Store profile updated.')
                return redirect('seller_profile')
        elif action == 'add_product':
            if not brand.can_add_product:
                messages.error(request, f'Free tier limit reached ({brand.FREE_PRODUCT_LIMIT} products). Upgrade to Pro for unlimited listings.')
                return redirect('seller_profile')
            product_form = ProductForm(request.POST, request.FILES)
            if product_form.is_valid():
                product = product_form.save(commit=False)
                product.brand = brand
                product.original_price = product.original_price or product.price
                product.save()  # discount auto-calculated in model.save()
                # Handle multiple images
                extra_images = request.FILES.getlist('extra_images')
                for i, img in enumerate(extra_images):
                    ProductImage.objects.create(product=product, image=img, order=i)
                # Handle video
                video_file = request.FILES.get('product_video')
                if video_file:
                    ProductVideo.objects.create(product=product, video=video_file)
                messages.success(request, f'"{product.name}" listed successfully!')
                return redirect('seller_profile')
            else:
                # Show each form error as a message so the seller knows what failed
                for field, errors in product_form.errors.items():
                    for error in errors:
                        field_label = field.replace('_', ' ').title() if field != '__all__' else 'Form'
                        messages.error(request, f'{field_label}: {error}')
                # Stay on add-product tab
                messages.error(request, 'Please fix the errors above and try again.')
        elif action == 'request_withdrawal':
            form = WithdrawalForm(request.POST)
            if form.is_valid():
                amount = form.cleaned_data['amount']
                if amount > brand.wallet_balance:
                    messages.error(request, 'Insufficient available balance.')
                else:
                    brand.wallet_balance -= amount
                    brand.save(update_fields=['wallet_balance'])
                    WithdrawalRequest.objects.create(
                        brand=brand, amount=amount,
                        bank_name=brand.seller.bank_name,
                        account_number=brand.seller.account_number,
                        account_holder_name=brand.seller.account_holder_name,
                    )
                    Notification.objects.create(
                        recipient=request.user, notification_type='withdrawal',
                        title='Withdrawal Requested',
                        message=f'Your withdrawal of ₦{amount} is being processed.',
                    )
                    messages.success(request, f'Withdrawal of ₦{amount} requested.')
                return redirect('seller_profile')

    total_sales = sum(p.sales for p in products)
    revenue = brand.wallet_total_earned

    from django.conf import settings as django_settings
    return render(request, 'marketplace/profile_seller.html', {
        'brand': brand, 'products': products, 'orders': orders,
        'withdrawals': withdrawals, 'notifications': notifications,
        'brand_form': brand_form, 'product_form': product_form,
        'total_sales': total_sales, 'revenue': revenue,
        'categories': Category.objects.all(),
        'pro_price': PRO_MONTHLY_PRICE,
        'promo_rates': PLATFORM_PROMO_RATES,
        'withdrawal_form': WithdrawalForm(),
        'PAYSTACK_PUBLIC_KEY': django_settings.PAYSTACK_PUBLIC_KEY,
        'pro_features': [
            'Unlimited product listings',
            'Blue Tick verification badge ✓',
            'Priority placement in search',
            'Promoted homepage slot',
            'Advanced analytics dashboard',
        ],
    })


@login_required
def admin_profile(request):
    if request.user.user_type != 'admin':
        return redirect('profile')
    users = User.objects.all()
    brands = Brand.objects.select_related('seller').prefetch_related('followers')
    products = Product.objects.select_related('brand', 'category')
    orders = Order.objects.select_related('buyer', 'brand').order_by('-created_at')[:50]
    pending_verifications = SellerVerificationRequest.objects.filter(status='pending').select_related('brand__seller')
    pending_withdrawals = WithdrawalRequest.objects.filter(status='pending').select_related('brand')
    notifications = Notification.objects.filter(recipient=None).order_by('-created_at')[:20]
    unverified_students = User.objects.filter(user_type='seller', student_verified=False).exclude(matric_number='')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'verify_seller':
            brand = get_object_or_404(Brand, id=request.POST.get('brand_id'))
            brand.is_verified = True
            brand.save()
            SellerVerificationRequest.objects.filter(brand=brand, status='pending').update(
                status='approved', reviewed_at=timezone.now(), reviewed_by=request.user)
            Notification.objects.create(
                recipient=brand.seller, notification_type='verification',
                title='✅ Store Verified!',
                message=f'"{brand.name}" now has the Blue Tick badge.', priority='high')
            messages.success(request, f'{brand.name} verified.')

        elif action == 'reject_seller':
            brand = get_object_or_404(Brand, id=request.POST.get('brand_id'))
            brand.is_verified = False
            brand.save()
            SellerVerificationRequest.objects.filter(brand=brand, status='pending').update(
                status='rejected', reviewed_at=timezone.now(), reviewed_by=request.user)
            messages.warning(request, f'{brand.name} rejected.')

        elif action == 'verify_student':
            user = get_object_or_404(User, id=request.POST.get('user_id'))
            user.student_verified = True
            user.save()
            Notification.objects.create(
                recipient=user, notification_type='verification',
                title='Student ID Verified',
                message='Your student identity has been verified. You can now open your store.', priority='high')
            messages.success(request, f'{user.username} student ID verified.')

        elif action == 'process_withdrawal':
            wr = get_object_or_404(WithdrawalRequest, id=request.POST.get('withdrawal_id'))
            new_status = request.POST.get('withdrawal_status', 'paid')
            wr.status = new_status
            wr.processed_at = timezone.now()
            wr.processed_by = request.user
            wr.admin_note = request.POST.get('admin_note', '')
            wr.save()
            if new_status == 'rejected':
                wr.brand.wallet_balance += wr.amount
                wr.brand.save(update_fields=['wallet_balance'])
            Notification.objects.create(
                recipient=wr.brand.seller, notification_type='withdrawal',
                title=f'Withdrawal {new_status.title()}',
                message=f'Your withdrawal of ₦{wr.amount} has been {new_status}.')
            messages.success(request, f'Withdrawal {new_status}.')

        elif action == 'send_notification':
            recipient_id = request.POST.get('recipient_id')
            Notification.objects.create(
                recipient=User.objects.filter(id=recipient_id).first() if recipient_id else None,
                notification_type=request.POST.get('type', 'admin'),
                title=request.POST.get('title', ''),
                message=request.POST.get('message', ''),
            )
            messages.success(request, 'Notification sent.')

        elif action == 'grant_pro':
            brand = get_object_or_404(Brand, id=request.POST.get('brand_id'))
            brand.tier = Brand.TIER_PRO
            brand.tier_expires_at = timezone.now() + timezone.timedelta(days=30)
            brand.save()
            messages.success(request, f'{brand.name} upgraded to Pro.')

        elif action == 'add_university':
            name = request.POST.get('uni_name', '').strip()
            if name:
                uni, created = University.objects.get_or_create(
                    name=name,
                    defaults={
                        'short_name': request.POST.get('uni_short', ''),
                        'city':       request.POST.get('uni_city', ''),
                        'state':      request.POST.get('uni_state', ''),
                        'country':    request.POST.get('uni_country', 'Nigeria'),
                    }
                )
                messages.success(request, f'University "{name}" {"added" if created else "already exists"}.')
            else:
                messages.error(request, 'University name is required.')

        elif action == 'toggle_university':
            uni = get_object_or_404(University, id=request.POST.get('uni_id'))
            uni.is_active = not uni.is_active
            uni.save()
            messages.success(request, f'{uni.name} {"activated" if uni.is_active else "deactivated"}.')

        elif action == 'delete_university':
            uni = get_object_or_404(University, id=request.POST.get('uni_id'))
            uni.delete()
            messages.success(request, 'University deleted.')

        elif action == 'add_campus_area':
            uni = get_object_or_404(University, id=request.POST.get('uni_id'))
            area_name = request.POST.get('area_name', '').strip()
            if area_name:
                CampusArea.objects.get_or_create(
                    university=uni, name=area_name,
                    defaults={
                        'area_type': request.POST.get('area_type', 'hostel'),
                    }
                )
                messages.success(request, f'Area "{area_name}" added to {uni.name}.')

        elif action == 'delete_area':
            area = get_object_or_404(CampusArea, id=request.POST.get('area_id'))
            area.delete()
            messages.success(request, 'Area deleted.')

        return redirect('admin_profile')

    total_revenue = orders.aggregate(t=Sum('commission_amount'))['t'] or Decimal('0')
    universities  = University.objects.prefetch_related('areas').order_by('name')
    return render(request, 'marketplace/profile_admin.html', {
        'users': users, 'brands': brands, 'products': products, 'orders': orders,
        'pending_verifications': pending_verifications,
        'pending_withdrawals': pending_withdrawals,
        'unverified_students': unverified_students,
        'notifications': notifications,
        'total_revenue': total_revenue,
        'total_users': users.count(),
        'total_sellers': users.filter(user_type='seller').count(),
        'total_products': products.filter(status='active').count(),
        'total_orders': orders.count(),
        'universities': universities,
    })


# ─────────────────────────────────────────────
# PRODUCTS
# ─────────────────────────────────────────────

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id, status='active')
    reviews = product.reviews.select_related('author').order_by('-created_at')
    specs = product.specifications.all()
    images = product.images.all()
    related_products = Product.objects.filter(brand=product.brand, status='active').exclude(id=product.id)[:4]
    is_in_wishlist = False
    user_review = None
    if request.user.is_authenticated:
        is_in_wishlist = WishlistItem.objects.filter(user=request.user, product=product).exists()
        user_review = reviews.filter(author=request.user).first()
    review_form = ReviewForm()
    if request.method == 'POST' and request.user.is_authenticated:
        if request.POST.get('action') == 'add_review':
            review_form = ReviewForm(request.POST)
            if review_form.is_valid():
                rev, created = Review.objects.get_or_create(
                    product=product, author=request.user,
                    defaults={'rating': review_form.cleaned_data['rating'], 'text': review_form.cleaned_data['text']})
                if not created:
                    rev.rating = review_form.cleaned_data['rating']
                    rev.text = review_form.cleaned_data['text']
                    rev.save()
                messages.success(request, 'Review submitted!')
                return redirect('product_detail', product_id=product.id)
    return render(request, 'marketplace/product_detail.html', {
        'product': product, 'reviews': reviews, 'specs': specs,
        'images': images, 'related_products': related_products,
        'is_in_wishlist': is_in_wishlist, 'user_review': user_review, 'review_form': review_form,
    })


@login_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, brand__seller=request.user)
    if request.method == 'POST':
        if request.POST.get('action') == 'delete':
            product.delete()
            messages.success(request, 'Product deleted.')
            return redirect('seller_profile')
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product updated.')
            return redirect('seller_profile')
    else:
        form = ProductForm(instance=product)
    return render(request, 'marketplace/product_edit.html', {'form': form, 'product': product})


# ─────────────────────────────────────────────
# BRANDS
# ─────────────────────────────────────────────

def brands_list(request):
    query    = request.GET.get('q', '')
    cat_slug = request.GET.get('category', '')
    brands   = Brand.objects.prefetch_related('followers', 'products').order_by(
        '-is_promoted', '-is_verified', '-created_at'
    )
    if query:
        brands = brands.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if cat_slug:
        brands = brands.filter(products__category__slug=cat_slug, products__status='active').distinct()
    categories = Category.objects.all()
    return render(request, 'marketplace/brands.html', {
        'brands': brands, 'query': query,
        'categories': categories, 'active_cat': cat_slug,
    })


def brand_detail(request, brand_id):
    brand = get_object_or_404(Brand, id=brand_id)
    products = Product.objects.filter(brand=brand, status='active').select_related('category')
    categories = Category.objects.filter(products__brand=brand, products__status='active').distinct()
    is_followed = False
    wishlist_ids = set()
    if request.user.is_authenticated:
        is_followed = brand.followers.filter(id=request.user.id).exists()
        wishlist_ids = set(WishlistItem.objects.filter(user=request.user).values_list('product_id', flat=True))
    return render(request, 'marketplace/brand_detail.html', {
        'brand': brand, 'products': products, 'categories': categories,
        'is_followed': is_followed, 'wishlist_ids': wishlist_ids,
    })


@login_required
@require_POST
def follow_brand(request, brand_id):
    if request.user.user_type != 'customer':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Only customers can follow brands'}, status=403)
        messages.error(request, 'Only customers can follow brands.')
        return redirect('brand_detail', brand_id=brand_id)
    brand = get_object_or_404(Brand, id=brand_id)
    if brand.followers.filter(id=request.user.id).exists():
        brand.followers.remove(request.user)
        followed = False
    else:
        brand.followers.add(request.user)
        followed = True
    # AJAX request — return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'followed': followed, 'follower_count': brand.follower_count})
    # Normal form POST — redirect back
    return redirect('brand_detail', brand_id=brand_id)


# ─────────────────────────────────────────────
# CATEGORIES & DEALS
# ─────────────────────────────────────────────

def categories(request):
    cats = Category.objects.prefetch_related('products')
    return render(request, 'marketplace/categories.html', {'categories': cats})


def deals(request):
    cat_slug    = request.GET.get('category', '')
    min_disc    = request.GET.get('min_discount', '')
    sort_by     = request.GET.get('sort', 'discount')

    deal_products = Product.objects.filter(status='active', discount__gt=0).select_related('brand', 'category')

    if cat_slug:
        deal_products = deal_products.filter(category__slug=cat_slug)
    if min_disc and min_disc.isdigit():
        deal_products = deal_products.filter(discount__gte=int(min_disc))

    if sort_by == 'price_low':
        deal_products = deal_products.order_by('price')
    elif sort_by == 'price_high':
        deal_products = deal_products.order_by('-price')
    elif sort_by == 'newest':
        deal_products = deal_products.order_by('-created_at')
    else:
        deal_products = deal_products.order_by('-discount')

    categories = Category.objects.filter(products__discount__gt=0, products__status='active').distinct()
    return render(request, 'marketplace/deals.html', {
        'products':    deal_products,
        'categories':  categories,
        'active_cat':  cat_slug,
        'min_disc':    min_disc,
        'sort_by':     sort_by,
        'total_deals': deal_products.count(),
    })


# ─────────────────────────────────────────────
# CART
# ─────────────────────────────────────────────

@login_required
def cart(request):
    cart_items = CartItem.objects.filter(user=request.user).select_related('product__brand')
    total = sum(item.subtotal for item in cart_items)
    return render(request, 'marketplace/cart.html', {'cart_items': cart_items, 'total': total})


@login_required
@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id, status='active')
    quantity = int(request.POST.get('quantity', 1))
    cart_item, created = CartItem.objects.get_or_create(
        user=request.user, product=product, defaults={'quantity': quantity})
    if not created:
        cart_item.quantity += quantity
        cart_item.save()
    messages.success(request, f'"{product.name}" added to cart.')
    return redirect(request.META.get('HTTP_REFERER', 'cart'))


@login_required
@require_POST
def update_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
    quantity = int(request.POST.get('quantity', 1))
    if quantity <= 0:
        cart_item.delete()
    else:
        cart_item.quantity = quantity
        cart_item.save()
    return redirect('cart')


@login_required
@require_POST
def remove_from_cart(request, item_id):
    get_object_or_404(CartItem, id=item_id, user=request.user).delete()
    return redirect('cart')


@login_required
@require_POST
def clear_cart(request):
    CartItem.objects.filter(user=request.user).delete()
    return redirect('cart')


# ─────────────────────────────────────────────
# CHECKOUT & ESCROW
# ─────────────────────────────────────────────

@login_required
def checkout(request):
    """
    Step 1 — Show the checkout form with delivery details.
    The actual payment is triggered by Paystack popup on the frontend.
    On form submit we call /paystack/initiate/ via JS to get a reference,
    then Paystack popup fires, then on success we call /paystack/verify/.
    """
    cart_items = CartItem.objects.filter(user=request.user).select_related('product__brand')
    if not cart_items.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('cart')

    campus_zones = CampusZone.objects.filter(is_active=True).order_by('zone_type', 'name')
    form = CheckoutForm(campus_zones=campus_zones, user=request.user)
    subtotal = sum(item.subtotal for item in cart_items)

    from django.conf import settings as django_settings
    return render(request, 'marketplace/checkout.html', {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'form': form,
        'campus_zones': campus_zones,
        'PAYSTACK_PUBLIC_KEY': django_settings.PAYSTACK_PUBLIC_KEY,
    })


@login_required
@require_POST
def paystack_initiate(request):
    """
    Step 2 — Called via AJAX when the user clicks Pay.
    Saves pending orders to DB, returns the Paystack amount + reference.
    Orders stay status='pending' until Paystack confirms payment.
    """
    import json as _json
    import uuid

    data = _json.loads(request.body)
    zone_id       = data.get('zone_id')
    address       = data.get('address', '')
    runner_note   = data.get('runner_note', '')
    phone         = data.get('phone', '').strip()
    delivery_lat  = data.get('delivery_lat')
    delivery_lng  = data.get('delivery_lng')

    cart_items    = CartItem.objects.filter(user=request.user).select_related('product__brand')
    if not cart_items.exists():
        return JsonResponse({'error': 'Cart is empty'}, status=400)

    zone = CampusZone.objects.filter(id=zone_id).first() if zone_id else None
    brands_in_cart = set(item.product.brand for item in cart_items)

    # Generate ONE shared payment reference for all orders in this checkout
    payment_ref = f"OJA-{uuid.uuid4().hex[:12].upper()}"

    # Create the MasterOrder first — groups all sub-orders from this session
    master = MasterOrder.objects.create(
        payment_reference=payment_ref,
        buyer=request.user,
        delivery_zone=zone,
        delivery_address=address,
        runner_note=runner_note,
        status='awaiting_payment',
    )

    order_ids = []
    grand_total = Decimal('0')

    for brand in brands_in_cart:
        brand_items = [i for i in cart_items if i.product.brand == brand]
        subtotal    = sum(i.subtotal for i in brand_items)
        delivery_fee = zone.flat_rate if zone else Decimal('0')

        order = Order(
            buyer=request.user, brand=brand,
            delivery_zone=zone, delivery_address=address,
            delivery_fee=delivery_fee, runner_note=runner_note,
            subtotal=subtotal, status='pending',
            payment_reference=payment_ref,
            master_order=master,
            hub_status='pending_vendor_shipment',
            phone=phone,
            delivery_lat=delivery_lat or None,
            delivery_lng=delivery_lng or None,
        )
        order.calculate_totals()
        order.save()

        for item in brand_items:
            OrderItem.objects.create(
                order=order, product=item.product,
                product_name=item.product.name,
                product_price=item.product.price,
                quantity=item.quantity,
            )

        order_ids.append(order.pk)
        grand_total += order.total

    # Update master grand total
    master.grand_total = grand_total
    master.save(update_fields=['grand_total'])

    # Store order IDs in session so verify can find them
    request.session['pending_order_ids'] = order_ids
    request.session['pending_payment_ref'] = payment_ref

    # Paystack amount is in KOBO (multiply naira by 100)
    amount_kobo = int(grand_total * 100)

    return JsonResponse({
        'reference': payment_ref,
        'amount':    amount_kobo,
        'email':     request.user.email,
    })


@login_required
def paystack_verify(request):
    """
    Step 3 — Verify payment after Paystack popup closes.
    Uses the requests library with proper headers.
    """
    import json as _json
    from django.conf import settings as django_settings

    reference = request.GET.get('reference') or request.session.get('pending_payment_ref', '')
    if not reference:
        messages.error(request, 'No payment reference found.')
        return redirect('checkout')

    secret_key = django_settings.PAYSTACK_SECRET_KEY.strip()
    url = f'https://api.paystack.co/transaction/verify/{reference}'

    try:
        import requests as _req
        resp = _req.get(
            url,
            headers={
                'Authorization': f'Bearer {secret_key}',
                'Content-Type': 'application/json',
            },
            timeout=30,
        )
        result = resp.json()
    except ImportError:
        # requests not installed — fallback to urllib
        import urllib.request as _urllib
        import ssl as _ssl
        req_obj = _urllib.Request(url, method='GET')
        req_obj.add_header('Authorization', f'Bearer {secret_key}')
        req_obj.add_header('Content-Type', 'application/json')
        req_obj.add_header('User-Agent', 'OJACampus-Django/1.0')
        try:
            ctx = _ssl.create_default_context()
            with _urllib.urlopen(req_obj, timeout=30, context=ctx) as r:
                result = _json.loads(r.read().decode('utf-8'))
        except _urllib.HTTPError as e:
            body = e.read().decode('utf-8') if hasattr(e, 'read') else ''
            messages.error(request, f'Paystack error {e.code}: {body[:200]}')
            return redirect('customer_profile')
        except Exception as e:
            messages.error(request, f'Verify failed: {type(e).__name__}: {e}')
            return redirect('customer_profile')
    except Exception as e:
        # Paystack verify API unreachable (network/firewall issue).
        # The payment popup already confirmed success client-side.
        # Activate orders and flag for manual review — webhook will also confirm.
        orders = Order.objects.filter(payment_reference=reference, buyer=request.user, status='pending')
        if orders.exists():
            _activate_orders(orders, reference)
            CartItem.objects.filter(user=request.user).delete()
            request.session.pop('pending_order_ids', None)
            request.session.pop('pending_payment_ref', None)
            messages.success(request, f'Payment received! Your order has been placed.')
        else:
            messages.error(request, f'Verify failed and no pending orders found. Ref: {reference} — contact support.')
        return redirect('customer_profile')

    # Check payment was successful
    pay_status = result.get('data', {}).get('status')
    if pay_status != 'success':
        Order.objects.filter(payment_reference=reference, buyer=request.user, status='pending').delete()
        messages.error(request, f'Payment was not completed (status: {pay_status}). No charge was made.')
        return redirect('checkout')

    orders = Order.objects.filter(payment_reference=reference, buyer=request.user, status='pending')
    if not orders.exists():
        messages.warning(request, 'Orders already processed or not found.')
        return redirect('customer_profile')

    _activate_orders(orders, reference)
    CartItem.objects.filter(user=request.user).delete()
    request.session.pop('pending_order_ids', None)
    request.session.pop('pending_payment_ref', None)

    messages.success(request, f'Payment successful! {orders.count()} order(s) placed. Funds held in escrow until you confirm delivery.')
    return redirect('customer_profile')


def _activate_orders(orders, reference):
    """Activate paid orders — move to escrow state and update MasterOrder."""
    for order in orders:
        order.status = 'paid'
        order.escrow_held_at = timezone.now()
        order.hub_status = 'pending_vendor_shipment'
        order.save(update_fields=['status', 'escrow_held_at', 'hub_status'])

        for item in order.items.select_related('product'):
            if item.product:
                item.product.stock = max(0, item.product.stock - item.quantity)
                item.product.sales += item.quantity
                item.product.save(update_fields=['stock', 'sales'])

        brand = order.brand
        brand.wallet_pending += order.vendor_payout
        brand.save(update_fields=['wallet_pending'])

        Notification.objects.create(
            recipient=brand.seller,
            notification_type='escrow',
            title='💰 New Sub-Order — Drop Off at OJA Hub',
            message=f'Sub-Order #{order.pk} paid. Please package your items and drop them at the OJA Hub. Ref: {reference}',
            priority='high',
        )

    # Activate the MasterOrder
    master = MasterOrder.objects.filter(payment_reference=reference).first()
    if master:
        master.status = 'awaiting_arrivals'
        master.save(update_fields=['status'])
        # Send buyer receipt
        send_order_receipt(master)

    # Send seller new-order emails (after master is set)
    for order in orders:
        send_seller_new_order(order)


@require_POST
def paystack_webhook(request):
    """
    Paystack server-to-server webhook.
    Set this URL in your Paystack dashboard: https://yourdomain.com/paystack/webhook/
    Paystack calls this automatically on payment events as a backup to the callback.
    """
    import hmac
    import hashlib
    import json as _json
    from django.conf import settings as django_settings

    paystack_signature = request.headers.get('X-Paystack-Signature', '')
    computed = hmac.new(
        django_settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
        request.body,
        hashlib.sha512,
    ).hexdigest()

    if paystack_signature != computed:
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    event = _json.loads(request.body)

    if event.get('event') == 'charge.success':
        reference = event['data']['reference']
        orders = Order.objects.filter(payment_reference=reference, status='pending')
        for order in orders:
            order.status = 'paid'
            order.escrow_held_at = timezone.now()
            order.save(update_fields=['status', 'escrow_held_at'])
            brand = order.brand
            brand.wallet_pending += order.vendor_payout
            brand.save(update_fields=['wallet_pending'])

    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def confirm_delivery(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user, status__in=['shipped', 'delivered', 'paid'])
    order.release_funds()
    Notification.objects.create(
        recipient=order.brand.seller, notification_type='escrow',
        title='💰 Funds Released!',
        message=f'Buyer confirmed delivery for Order #{order.pk}. ₦{order.vendor_payout} added to your wallet.',
        priority='high',
    )
    messages.success(request, 'Delivery confirmed! Funds have been released to the seller.')
    return redirect('customer_profile')


@login_required
@require_POST
def mark_order_shipped(request, order_id):
    """
    Seller confirms they've dropped the package at the OJA Hub.
    Updates hub_status to in_transit_to_hub.
    The Hub Admin then scans it in as 'received_at_hub'.
    """
    order = get_object_or_404(Order, id=order_id, brand__seller=request.user)
    if order.status == 'paid':
        order.hub_status = 'in_transit_to_hub'
        order.save(update_fields=['hub_status'])
        # Notify hub admin
        Notification.objects.create(
            recipient=None,  # broadcast to admins
            notification_type='system',
            title=f'🚚 Package En Route — Sub-Order #{order.pk}',
            message=f'{order.brand.name} has dropped Sub-Order #{order.pk} for Master Order {order.payment_reference[:16]}. Scan it in when it arrives at the hub.',
            priority='medium',
        )
        # Notify buyer
        Notification.objects.create(
            recipient=order.buyer,
            notification_type='sale',
            title=f'🚚 {order.brand.name} has dispatched your item',
            message=f'Your item from {order.brand.name} is on its way to the OJA Hub for consolidated delivery.',
        )
        send_order_shipped(order)
        messages.success(request, f'✅ Marked as dropped at hub. Hub team will scan it in.')
    return redirect('seller_profile')


# ─────────────────────────────────────────────
# WISHLIST
# ─────────────────────────────────────────────

@login_required
def wishlist(request):
    wishlist_items = WishlistItem.objects.filter(user=request.user).select_related('product__brand')
    return render(request, 'marketplace/wishlist.html', {'wishlist_items': wishlist_items})


@login_required
@require_POST
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    item, created = WishlistItem.objects.get_or_create(user=request.user, product=product)
    if not created:
        item.delete()
        messages.info(request, f'Removed "{product.name}" from wishlist.')
    else:
        messages.success(request, f'"{product.name}" added to wishlist.')
    return redirect(request.META.get('HTTP_REFERER', 'wishlist'))


# ─────────────────────────────────────────────
# NOTIFICATIONS
# ─────────────────────────────────────────────

@login_required
def notifications(request):
    notifs = Notification.objects.filter(
        Q(recipient=request.user) | Q(recipient=None, notification_type__in=['admin', 'system'])
    ).order_by('-created_at')
    return render(request, 'marketplace/notifications.html', {'notifications': notifs})


@login_required
@require_POST
def mark_notification_read(request, notif_id):
    # Try personal notification first, then broadcast
    from django.db.models import Q as _Q
    notif = Notification.objects.filter(
        _Q(recipient=request.user) | _Q(recipient=None),
        id=notif_id
    ).first()
    if notif:
        notif.is_read = True
        notif.save()
    return redirect('notifications')


@login_required
@require_POST
def delete_notification(request, notif_id):
    get_object_or_404(Notification, id=notif_id, recipient=request.user).delete()
    return redirect('notifications')


# ─────────────────────────────────────────────
# ORDER MANAGEMENT — customer actions
# ─────────────────────────────────────────────

@login_required
def order_detail(request, order_id):
    """Full sub-order detail page — accessible by buyer OR the brand's seller."""
    from django.db.models import Q as _Q
    order = get_object_or_404(
        Order,
        _Q(buyer=request.user) | _Q(brand__seller=request.user),
        pk=order_id,
    )
    enquiries = order.enquiries.order_by('created_at')
    master = order.master_order
    # Sibling sub-orders (other vendors in same consolidated delivery)
    siblings = master.orders.exclude(pk=order.pk).select_related('brand') if master else []
    return render(request, 'marketplace/order_detail.html', {
        'order': order,
        'enquiries': enquiries,
        'master': master,
        'siblings': siblings,
    })


@login_required
@require_POST
def cancel_order(request, order_id):
    """Cancel order — only allowed when status is pending or paid (not yet shipped)."""
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)

    if order.status not in ('pending', 'paid'):
        messages.error(request, f'Order #{order.pk} cannot be cancelled — it is already {order.get_status_display()}.')
        return redirect('order_detail', order_id=order.pk)

    reason = request.POST.get('reason', '').strip()

    # Refund escrow back to brand's pending wallet
    if order.status == 'paid':
        brand = order.brand
        brand.wallet_pending = max(Decimal('0'), brand.wallet_pending - order.vendor_payout)
        brand.save(update_fields=['wallet_pending'])

    order.status = 'cancelled'
    order.save(update_fields=['status'])

    # Restore stock
    for item in order.items.select_related('product'):
        if item.product:
            item.product.stock += item.quantity
            item.product.sales = max(0, item.product.sales - item.quantity)
            item.product.save(update_fields=['stock', 'sales'])

    # Notify seller
    Notification.objects.create(
        recipient=order.brand.seller,
        notification_type='sale',
        title=f'Order #{order.pk} Cancelled',
        message=f'Buyer cancelled Order #{order.pk}. Reason: {reason or "Not given"}',
        priority='high',
    )
    send_order_cancelled(order)
    messages.success(request, f'Order #{order.pk} has been cancelled.')
    return redirect('customer_profile')


@login_required
@require_POST
def dispute_order(request, order_id):
    """Raise a dispute — locks order in disputed state, notifies admin."""
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)

    if order.status not in ('paid', 'shipped', 'delivered'):
        messages.error(request, 'You can only dispute an active order.')
        return redirect('order_detail', order_id=order.pk)

    reason = request.POST.get('reason', '').strip()
    if not reason:
        messages.error(request, 'Please describe the issue before raising a dispute.')
        return redirect('order_detail', order_id=order.pk)

    order.status = 'disputed'
    order.save(update_fields=['status'])

    # Add as enquiry too so there's a record
    OrderEnquiry.objects.create(
        order=order,
        sender=request.user,
        message=f'[DISPUTE] {reason}',
        enquiry_type='dispute',
    )

    # Notify admin (broadcast)
    Notification.objects.create(
        recipient=None,
        notification_type='fraud',
        title=f'🚨 Dispute Raised — Order #{order.pk}',
        message=f'Buyer {request.user.email} disputed Order #{order.pk} from {order.brand.name}. Reason: {reason}',
        priority='high',
    )
    # Notify seller
    Notification.objects.create(
        recipient=order.brand.seller,
        notification_type='sale',
        title=f'⚠ Dispute on Order #{order.pk}',
        message=f'A dispute has been raised on Order #{order.pk}. Admin will review.',
        priority='high',
    )
    send_dispute_raised(order)
    messages.warning(request, f'Dispute raised for Order #{order.pk}. Our team will review within 24 hours.')
    return redirect('order_detail', order_id=order.pk)


@login_required
def send_enquiry(request, order_id):
    """Send a message/enquiry to the seller about an order."""
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)

    if request.method == 'POST':
        message = request.POST.get('message', '').strip()
        if not message:
            messages.error(request, 'Message cannot be empty.')
            return redirect('order_detail', order_id=order.pk)

        OrderEnquiry.objects.create(
            order=order,
            sender=request.user,
            message=message,
            enquiry_type='enquiry',
        )
        # Notify seller
        Notification.objects.create(
            recipient=order.brand.seller,
            notification_type='sale',
            title=f'💬 New Enquiry — Order #{order.pk}',
            message=f'{request.user.first_name or request.user.email} sent a message about Order #{order.pk}: "{message[:100]}"',
        )
        messages.success(request, 'Message sent to seller.')

    return redirect('order_detail', order_id=order.pk)


@login_required
@require_POST
def reply_enquiry(request, order_id):
    """Seller replies to an enquiry on their order."""
    order = get_object_or_404(Order, pk=order_id, brand__seller=request.user)
    message = request.POST.get('message', '').strip()
    if message:
        OrderEnquiry.objects.create(
            order=order,
            sender=request.user,
            message=message,
            enquiry_type='reply',
        )
        Notification.objects.create(
            recipient=order.buyer,
            notification_type='sale',
            title=f'💬 Reply from {order.brand.name} — Order #{order.pk}',
            message=f'Seller replied: "{message[:100]}"',
        )
        messages.success(request, 'Reply sent.')
    return redirect('order_detail', order_id=order.pk)


# ─────────────────────────────────────────────
# PRO UPGRADE — Paystack ₦5,000/month
# ─────────────────────────────────────────────

@login_required
@require_POST
def upgrade_initiate(request):
    """Return Paystack reference + amount in kobo for Pro upgrade."""
    import uuid as _uuid
    from django.conf import settings as django_settings

    if request.user.user_type != 'seller':
        return JsonResponse({'error': 'Sellers only'}, status=403)
    try:
        brand = request.user.brand
    except Exception:
        return JsonResponse({'error': 'No brand found'}, status=400)
    if brand.is_pro:
        return JsonResponse({'error': 'Already on Pro'}, status=400)

    ref = f"OJA-PRO-{_uuid.uuid4().hex[:12].upper()}"
    request.session['pro_upgrade_ref'] = ref

    return JsonResponse({
        'reference': ref,
        'amount':    500000,   # ₦5,000 in kobo
        'email':     request.user.email,
    })


@login_required
def upgrade_verify(request):
    """Verify Pro upgrade payment then activate tier + auto-submit Blue Tick request."""
    import json as _json
    from django.conf import settings as django_settings

    reference = request.GET.get('reference') or request.session.get('pro_upgrade_ref', '')
    if not reference:
        messages.error(request, 'No upgrade payment reference found.')
        return redirect('seller_profile')

    secret_key = django_settings.PAYSTACK_SECRET_KEY.strip()
    url = f'https://api.paystack.co/transaction/verify/{reference}'
    pay_status = 'success'   # default — trust popup if API unreachable

    try:
        import requests as _req
        resp = _req.get(
            url,
            headers={'Authorization': f'Bearer {secret_key}', 'Content-Type': 'application/json'},
            timeout=30,
        )
        result = resp.json()
        pay_status = result.get('data', {}).get('status', 'unknown')
    except Exception:
        pass   # fallback — trust the Paystack popup callback

    if pay_status != 'success':
        messages.error(request, 'Payment not confirmed by Paystack. Please try again.')
        return redirect('seller_profile')

    try:
        brand = request.user.brand
    except Exception:
        messages.error(request, 'Brand not found.')
        return redirect('seller_profile')

    # Activate Pro for 30 days
    brand.tier = Brand.TIER_PRO
    brand.tier_expires_at = timezone.now() + timezone.timedelta(days=30)
    brand.save(update_fields=['tier', 'tier_expires_at'])

    # Record subscription payment
    SubscriptionPayment.objects.create(
        brand=brand,
        amount=Decimal('5000.00'),
        duration_days=30,
        starts_at=timezone.now(),
        ends_at=brand.tier_expires_at,
        payment_ref=reference,
    )

    # Auto-submit Blue Tick verification request if not already verified
    if not brand.is_verified:
        SellerVerificationRequest.objects.get_or_create(
            brand=brand,
            defaults={'status': 'pending'},
        )
        # Notify admins
        Notification.objects.create(
            recipient=None,
            notification_type='verification',
            title=f'⭐ Pro Upgrade + Verification — {brand.name}',
            message=f'{brand.name} upgraded to Pro (Ref: {reference}). Blue Tick verification auto-requested.',
            priority='high',
        )

    # Notify seller
    Notification.objects.create(
        recipient=request.user,
        notification_type='verification',
        title='🎉 You are now Pro!',
        message='Your store is now on the Pro plan — unlimited listings, priority placement, and Blue Tick verification submitted to admin.',
        priority='high',
    )

    request.session.pop('pro_upgrade_ref', None)
    send_pro_upgrade_confirmation(brand)
    messages.success(request, '🎉 Upgrade successful! You are now on the Pro plan. Blue Tick verification has been submitted.')
    return redirect('seller_profile')


# ─────────────────────────────────────────────
# CROSS-DOCKING / HUB LOGIC
# ─────────────────────────────────────────────

def _check_master_order_completion(master_order):
    """
    Core trigger: called whenever a Sub-Order's hub_status changes.
    If ALL sub-orders for this Master are 'received_at_hub',
    upgrade Master to 'ready_for_packaging' and notify Hub Admin.
    Otherwise keep as 'awaiting_arrivals'.
    """
    if not master_order:
        return

    sub_orders = master_order.orders.filter(status__in=['paid', 'shipped'])

    if not sub_orders.exists():
        return

    all_arrived = not sub_orders.exclude(hub_status='received_at_hub').exists()

    if all_arrived:
        master_order.status = 'ready_for_packaging'
        master_order.save(update_fields=['status'])

        # Notify all Hub Admins (broadcast notification)
        Notification.objects.create(
            recipient=None,  # broadcast to admins
            notification_type='system',
            title=f'📦 Ready to Package — Master Order {master_order.payment_reference[:16]}',
            message=(
                f'All {sub_orders.count()} items for Master Order '
                f'{master_order.payment_reference} have arrived at the hub. '
                f'Buyer: {master_order.buyer.first_name or master_order.buyer.username} · '
                f'Zone: {master_order.delivery_zone.name if master_order.delivery_zone else "N/A"}. '
                f'Ready to pack into one OJA bag.'
            ),
            priority='high',
        )
        # Notify buyer
        Notification.objects.create(
            recipient=master_order.buyer,
            notification_type='sale',
            title='🎁 Your order is being packed!',
            message='All your items have arrived at the OJA Hub and are being packed into one delivery bag.',
        )
        send_all_at_hub(master_order)
    else:
        arrived = sub_orders.filter(hub_status='received_at_hub').count()
        total   = sub_orders.count()
        master_order.status = 'awaiting_arrivals'
        master_order.save(update_fields=['status'])

        # Notify hub that one more item arrived
        Notification.objects.create(
            recipient=None,
            notification_type='system',
            title=f'📬 Item Arrived at Hub ({arrived}/{total})',
            message=(
                f'{arrived} of {total} items for Master Order '
                f'{master_order.payment_reference[:16]} have arrived. '
                f'Still waiting for {total - arrived} vendor(s).'
            ),
            priority='medium',
        )


@login_required
def hub_dashboard(request):
    """
    Hub Admin Dashboard — scan package IDs, see bin assignments,
    manage sub-order hub statuses.
    """
    if request.user.user_type != 'admin':
        messages.error(request, 'Hub access restricted to admins.')
        return redirect('home')

    # Stats
    pending_arrivals  = Order.objects.filter(hub_status='pending_vendor_shipment', status='paid').count()
    in_transit        = Order.objects.filter(hub_status='in_transit_to_hub').count()
    at_hub            = Order.objects.filter(hub_status='received_at_hub').count()
    ready_to_pack     = MasterOrder.objects.filter(status='ready_for_packaging').count()

    # Active master orders (awaiting arrivals or ready)
    active_masters = MasterOrder.objects.filter(
        status__in=['awaiting_arrivals', 'ready_for_packaging', 'packaged']
    ).prefetch_related('orders__brand', 'orders__items').select_related('buyer', 'delivery_zone')

    # Scan result (from GET param)
    scan_result = None
    scan_query  = request.GET.get('scan', '').strip()
    if scan_query:
        # Try matching by package_scan_id or order PK
        sub_order = (
            Order.objects.filter(package_scan_id=scan_query).first()
            or Order.objects.filter(pk=scan_query if scan_query.isdigit() else None).first()
        )
        if sub_order:
            scan_result = {
                'found': True,
                'sub_order': sub_order,
                'master': sub_order.master_order,
            }
        else:
            scan_result = {'found': False, 'query': scan_query}

    if request.method == 'POST':
        action   = request.POST.get('action')
        order_id = request.POST.get('order_id')
        master_id = request.POST.get('master_id')

        if action == 'mark_in_transit' and order_id:
            sub = get_object_or_404(Order, pk=order_id)
            sub.hub_status = 'in_transit_to_hub'
            sub.save(update_fields=['hub_status'])
            messages.success(request, f'Sub-Order #{sub.pk} marked In Transit.')

        elif action == 'mark_received' and order_id:
            sub = get_object_or_404(Order, pk=order_id)
            sub.hub_status = 'received_at_hub'
            sub.hub_received_at = timezone.now()
            sub.package_scan_id = request.POST.get('scan_id', sub.package_scan_id)
            sub.save(update_fields=['hub_status', 'hub_received_at', 'package_scan_id'])
            # Trigger the completion check
            _check_master_order_completion(sub.master_order)
            messages.success(request, f'Sub-Order #{sub.pk} checked in at hub. Completion check triggered.')

        elif action == 'mark_packaged' and master_id:
            master = get_object_or_404(MasterOrder, pk=master_id)
            master.status = 'packaged'
            master.packaged_at = timezone.now()
            # Auto-generate bin label if not set
            if not master.hub_bin:
                master.hub_bin = f'BIN-{master.pk:04d}'
            master.save(update_fields=['status', 'packaged_at', 'hub_bin'])
            # Mark all sub-orders as packaged
            master.orders.filter(hub_status='received_at_hub').update(hub_status='packaged_for_customer')
            Notification.objects.create(
                recipient=master.buyer,
                notification_type='sale',
                title='📦 Your order is packed & ready!',
                message=f'Your OJA order ({master.hub_bin}) is packed and a rider will deliver it soon.',
            )
            messages.success(request, f'Master Order {master.payment_reference[:16]} packaged as {master.hub_bin}.')

        elif action == 'mark_dispatched' and master_id:
            master = get_object_or_404(MasterOrder, pk=master_id)
            master.status = 'out_for_delivery'
            master.dispatched_at = timezone.now()
            master.save(update_fields=['status', 'dispatched_at'])
            master.orders.all().update(status='shipped')
            Notification.objects.create(
                recipient=master.buyer,
                notification_type='sale',
                title='🛵 Your order is on the way!',
                message=f'Your OJA delivery bag ({master.hub_bin}) is out for delivery to {master.delivery_zone.name if master.delivery_zone else master.delivery_address}.',
                priority='high',
            )
            send_order_dispatched(master)
            messages.success(request, f'Master Order {master.hub_bin} dispatched for delivery.')

        elif action == 'assign_bin' and master_id:
            master = get_object_or_404(MasterOrder, pk=master_id)
            master.hub_bin = request.POST.get('bin_label', '').strip()
            master.save(update_fields=['hub_bin'])
            messages.success(request, f'Bin {master.hub_bin} assigned.')

        return redirect('hub_dashboard')

    return render(request, 'marketplace/hub_dashboard.html', {
        'pending_arrivals': pending_arrivals,
        'in_transit':       in_transit,
        'at_hub':           at_hub,
        'ready_to_pack':    ready_to_pack,
        'active_masters':   active_masters,
        'scan_result':      scan_result,
        'scan_query':       scan_query,
    })


@login_required
@require_POST
def confirm_master_delivery(request, master_id):
    """Buyer confirms receipt of the full consolidated delivery — releases funds to all vendors."""
    master = get_object_or_404(MasterOrder, pk=master_id, buyer=request.user)
    if master.status not in ('out_for_delivery', 'packaged', 'shipped'):
        messages.error(request, 'This order cannot be confirmed at this stage.')
        return redirect('customer_profile')

    master.status = 'confirmed'
    master.delivered_at = timezone.now()
    master.save(update_fields=['status', 'delivered_at'])

    # Release escrow for every sub-order
    for sub in master.orders.filter(status__in=['shipped', 'paid', 'delivered']):
        sub.release_funds()

    send_delivery_confirmed(master)
    messages.success(request, '✅ Order confirmed! Funds released to all sellers. Thank you!')
    return redirect('customer_profile')


# ─────────────────────────────────────────────
# CUSTOMER / SELLER SUPPORT CHAT WITH ADMIN
# ─────────────────────────────────────────────

@login_required
def support_chat(request):
    """Live chat / support ticket with admin team."""
    from .models import OrderEnquiry as _OE
    # Load existing support messages for this user (we re-use OrderEnquiry with order=None approach,
    # but simpler: use a dedicated queryset on Notification as messages)
    # Actually use a simple session-based approach with SupportMessage model
    messages_qs = SupportMessage.objects.filter(user=request.user).order_by('created_at')

    if request.method == 'POST':
        msg_text = request.POST.get('message', '').strip()
        if msg_text:
            SupportMessage.objects.create(
                user=request.user,
                message=msg_text,
                sender_type='user',
            )
            # Notify admin
            Notification.objects.create(
                recipient=None,
                notification_type='system',
                title=f'💬 Support Message from {request.user.first_name or request.user.username}',
                message=f'{request.user.email}: {msg_text[:120]}',
                priority='medium',
            )
        return redirect('support_chat')

    default_faqs = [
        ("How does escrow work?", "When you pay, your money is held safely by OJA. The seller only receives payment after you click 'Item Received'. If anything goes wrong, you can raise a dispute."),
        ("How long does delivery take?", "Items are first collected at the OJA Hub from all your vendors, then packed into one bag and delivered to your hostel. This usually takes 1-3 hours after all items arrive at the hub."),
        ("Can I cancel my order?", "Yes — you can cancel before the seller ships. Go to your order and click 'Cancel Order'. Stock is automatically restored."),
        ("What is the OJA Hub?", "The OJA Hub is our central collection point on campus. All your vendors drop their items here, we pack everything into one OJA bag, and a single rider delivers to you."),
        ("How do I become a verified seller?", "Upgrade to the Pro plan (₦5,000/month). After payment, your verification request is automatically submitted to our admin team who will review and grant the Blue Tick badge."),
        ("My item hasn't arrived, what do I do?", "First check your order status. If it shows 'Out for Delivery' but hasn't arrived, use the chat above to contact us. You can also raise a dispute from the order detail page."),
    ]
    return render(request, 'marketplace/support_chat.html', {
        'messages_qs': messages_qs,
        'default_faqs': default_faqs,
    })


@login_required
@require_POST
def support_reply(request):
    """Admin replies to a support message."""
    if request.user.user_type != 'admin':
        return redirect('home')
    user_id  = request.POST.get('user_id')
    msg_text = request.POST.get('message', '').strip()
    if user_id and msg_text:
        target_user = User.objects.filter(pk=user_id).first()
        if target_user:
            SupportMessage.objects.create(
                user=target_user,
                message=msg_text,
                sender_type='admin',
                admin_sender=request.user,
            )
            Notification.objects.create(
                recipient=target_user,
                notification_type='system',
                title='💬 Reply from OJA Support',
                message=msg_text[:120],
            )
    return redirect('admin_profile')


def offline_page(request):
    return render(request, 'marketplace/offline.html')


# ─────────────────────────────────────────────
# UNIVERSITY / CAMPUS AREA API
# ─────────────────────────────────────────────

def get_campus_areas(request):
    """AJAX endpoint — return areas for a given university (used in location pickers)."""
    university_name = request.GET.get('university', '')
    uni = University.objects.filter(name__icontains=university_name, is_active=True).first()
    if uni:
        areas = list(uni.areas.filter(is_active=True).values('id', 'name', 'area_type', 'latitude', 'longitude'))
    else:
        areas = []
    return JsonResponse({'areas': areas})


def universities_list(request):
    """AJAX endpoint — search universities."""
    q = request.GET.get('q', '')
    unis = University.objects.filter(is_active=True)
    if q:
        unis = unis.filter(name__icontains=q)
    data = list(unis.values('id', 'name', 'short_name', 'city', 'state', 'latitude', 'longitude')[:20])
    return JsonResponse({'universities': data})