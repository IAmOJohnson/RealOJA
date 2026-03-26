from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from decimal import Decimal


class User(AbstractUser):
    USER_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('seller', 'Seller'),
        ('admin', 'Admin'),
    ]
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='customer')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True)
    profile_complete = models.BooleanField(default=False)
    # Student verification
    matric_number = models.CharField(max_length=30, blank=True)
    student_id_image = models.ImageField(upload_to='student_ids/', blank=True, null=True)
    student_verified = models.BooleanField(default=False)
    university = models.CharField(max_length=200, blank=True)
    # Seller bank details
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=20, blank=True)
    account_holder_name = models.CharField(max_length=100, blank=True)
    bank_code = models.CharField(max_length=10, blank=True)
    # Location
    latitude  = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    campus_area = models.CharField(max_length=200, blank=True, help_text='e.g. Moremi Hall, Faculty of Science')

    def __str__(self):
        return f"{self.username} ({self.user_type})"

    @property
    def is_seller(self):
        return self.user_type == 'seller'

    @property
    def is_customer(self):
        return self.user_type == 'customer'

    @property
    def is_admin_user(self):
        return self.user_type == 'admin'


class CampusZone(models.Model):
    ZONE_TYPES = [
        ('hostel', 'Hostel'), ('faculty', 'Faculty'),
        ('gate', 'Campus Gate'), ('other', 'Other'),
    ]
    name = models.CharField(max_length=200)
    zone_type = models.CharField(max_length=50, choices=ZONE_TYPES, default='hostel')
    flat_rate = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('200.00'))
    is_active = models.BooleanField(default=True)
    university = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.name} — ₦{self.flat_rate}"


class Brand(models.Model):
    TIER_FREE = 'free'
    TIER_PRO = 'pro'
    TIER_CHOICES = [(TIER_FREE, 'Free'), (TIER_PRO, 'Pro')]
    FREE_PRODUCT_LIMIT = 5

    seller = models.OneToOneField(User, on_delete=models.CASCADE, related_name='brand',
        limit_choices_to={'user_type': 'seller'})
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='brand_logos/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    established = models.CharField(max_length=4, blank=True)
    location = models.CharField(max_length=200, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.0'))
    followers = models.ManyToManyField(User, related_name='followed_brands', blank=True,
        limit_choices_to={'user_type': 'customer'})
    # Tier
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default=TIER_FREE)
    tier_expires_at = models.DateTimeField(null=True, blank=True)
    # Promotion
    is_promoted = models.BooleanField(default=False)
    promoted_until = models.DateTimeField(null=True, blank=True)
    # Socials
    whatsapp = models.CharField(max_length=20, blank=True)
    instagram = models.CharField(max_length=100, blank=True)
    twitter = models.CharField(max_length=100, blank=True)
    tiktok = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    # Business
    business_category = models.CharField(max_length=100, blank=True)
    business_type = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True, default='Nigeria')
    tax_id = models.CharField(max_length=50, blank=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('3.00'))
    # Wallet
    wallet_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    wallet_pending = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    wallet_total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def product_count(self):
        return self.products.filter(status='active').count()

    @property
    def follower_count(self):
        return self.followers.count()

    @property
    def is_pro(self):
        if self.tier == self.TIER_PRO:
            if self.tier_expires_at is None or self.tier_expires_at > timezone.now():
                return True
        return False

    @property
    def is_promoted_active(self):
        if not self.is_promoted:
            return False
        if self.promoted_until and self.promoted_until < timezone.now():
            return False
        return True

    @property
    def can_add_product(self):
        if self.is_pro:
            return True
        return self.products.filter(status__in=['active', 'draft', 'inactive']).count() < self.FREE_PRODUCT_LIMIT

    @property
    def products_remaining(self):
        if self.is_pro:
            return None
        used = self.products.filter(status__in=['active', 'draft', 'inactive']).count()
        return max(0, self.FREE_PRODUCT_LIMIT - used)


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=10, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class Product(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'), ('inactive', 'Inactive'), ('draft', 'Draft'),
    ]
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    original_price = models.DecimalField(max_digits=12, decimal_places=2)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    stock = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    sales = models.PositiveIntegerField(default=0)
    is_promoted = models.BooleanField(default=False)
    discount = models.PositiveIntegerField(default=0)
    deal_ends_at = models.DateTimeField(blank=True, null=True)
    shipping_info = models.CharField(max_length=200, default='Campus delivery available')
    warranty = models.CharField(max_length=200, default='1-year warranty included')
    return_policy = models.CharField(max_length=200, default='30-day return policy')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Auto-calculate discount percentage from prices
        if self.original_price and self.original_price > self.price:
            from decimal import Decimal
            self.discount = int(((self.original_price - self.price) / self.original_price) * 100)
        else:
            self.discount = 0
        super().save(*args, **kwargs)

    @property
    def average_rating(self):
        reviews = self.reviews.all()
        if not reviews:
            return 0
        return round(sum(r.rating for r in reviews) / reviews.count(), 1)

    @property
    def review_count(self):
        return self.reviews.count()

    @property
    def is_on_deal(self):
        if not self.deal_ends_at:
            return False
        return self.deal_ends_at > timezone.now()


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']


class ProductVideo(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='videos')
    video = models.FileField(upload_to='products/videos/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Video for {self.product.name}"


class ProductSpecification(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='specifications')
    key = models.CharField(max_length=100)
    value = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.key}: {self.value}"


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField()
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'author')

    def __str__(self):
        return f"{self.author.username} → {self.product.name}"


class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} — {self.product.name} x{self.quantity}"

    @property
    def subtotal(self):
        return self.product.price * self.quantity


class WishlistItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} wishlist: {self.product.name}"


class MasterOrder(models.Model):
    """
    Groups all Sub-Orders (per-vendor Orders) from a single checkout session.
    Created once per payment_reference.
    """
    MASTER_STATUS = [
        ('awaiting_payment',    'Awaiting Payment'),
        ('awaiting_arrivals',   'Awaiting Arrivals at Hub'),
        ('ready_for_packaging', 'Ready for Final Packaging'),
        ('packaged',            'Packaged for Customer'),
        ('out_for_delivery',    'Out for Delivery'),
        ('delivered',           'Delivered to Customer'),
        ('confirmed',           'Buyer Confirmed'),
        ('cancelled',           'Cancelled'),
    ]
    payment_reference = models.CharField(max_length=100, unique=True)
    buyer             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='master_orders')
    delivery_zone     = models.ForeignKey('CampusZone', on_delete=models.SET_NULL, null=True, blank=True)
    delivery_address  = models.TextField(blank=True)
    runner_note       = models.TextField(blank=True)
    status            = models.CharField(max_length=25, choices=MASTER_STATUS, default='awaiting_payment')
    grand_total       = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    # Hub tracking
    hub_bin           = models.CharField(max_length=20, blank=True, help_text='Physical bin/bag label at hub e.g. BIN-042')
    packaged_at       = models.DateTimeField(null=True, blank=True)
    dispatched_at     = models.DateTimeField(null=True, blank=True)
    delivered_at      = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"MasterOrder {self.payment_reference} — {self.buyer.username}"

    @property
    def sub_orders(self):
        return self.orders.all()

    @property
    def total_sub_orders(self):
        return self.orders.count()

    @property
    def arrived_count(self):
        return self.orders.filter(hub_status='received_at_hub').count()

    @property
    def all_arrived(self):
        orders = self.orders.all()
        return orders.exists() and not orders.exclude(hub_status='received_at_hub').exists()


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending',   'Pending Payment'),
        ('paid',      'Paid — In Escrow'),
        ('shipped',   'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('confirmed', 'Buyer Confirmed — Funds Released'),
        ('disputed',  'Disputed'),
        ('cancelled', 'Cancelled'),
        ('refunded',  'Refunded'),
    ]
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='orders')
    delivery_zone = models.ForeignKey(CampusZone, on_delete=models.SET_NULL, null=True, blank=True)
    delivery_address = models.TextField(blank=True)
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    runner_note = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    delivery_lat  = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    delivery_lng  = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    vendor_payout = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    escrow_held_at = models.DateTimeField(null=True, blank=True)
    funds_released_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    # Cross-Docking / Hub fields
    master_order = models.ForeignKey(
        'MasterOrder', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders'
    )
    hub_status = models.CharField(max_length=30, choices=[
        ('pending_vendor_shipment', 'Pending — Vendor to Ship to Hub'),
        ('in_transit_to_hub',       'In Transit to Hub'),
        ('received_at_hub',         'Received at Hub'),
        ('packaged_for_customer',   'Packaged for Customer'),
    ], default='pending_vendor_shipment')
    hub_received_at  = models.DateTimeField(null=True, blank=True)
    package_scan_id  = models.CharField(max_length=50, blank=True, unique=False,
        help_text='Vendor-generated package ID scanned at the hub')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.pk} — {self.buyer.username}"

    def calculate_totals(self):
        rate = self.brand.commission_rate / Decimal('100')
        self.commission_amount = (self.subtotal * rate).quantize(Decimal('0.01'))
        self.vendor_payout = (self.subtotal - self.commission_amount).quantize(Decimal('0.01'))
        self.total = (self.subtotal + self.delivery_fee).quantize(Decimal('0.01'))

    def release_funds(self):
        brand = self.brand
        brand.wallet_pending = max(Decimal('0'), brand.wallet_pending - self.vendor_payout)
        brand.wallet_balance += self.vendor_payout
        brand.wallet_total_earned += self.vendor_payout
        brand.save(update_fields=['wallet_pending', 'wallet_balance', 'wallet_total_earned'])
        self.status = 'confirmed'
        self.funds_released_at = timezone.now()
        self.confirmed_at = timezone.now()
        self.save(update_fields=['status', 'funds_released_at', 'confirmed_at'])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=200)
    product_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    @property
    def line_total(self):
        return self.product_price * self.quantity

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"


class OrderEnquiry(models.Model):
    ENQUIRY_TYPES = [
        ('enquiry', 'Enquiry'),
        ('reply',   'Reply'),
        ('dispute', 'Dispute'),
        ('update',  'Status Update'),
    ]
    order        = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='enquiries')
    sender       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enquiries_sent')
    message      = models.TextField()
    enquiry_type = models.CharField(max_length=10, choices=ENQUIRY_TYPES, default='enquiry')
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Order #{self.order.pk} — {self.sender.username}: {self.message[:40]}"


class WithdrawalRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('approved', 'Approved'),
        ('paid', 'Paid Out'), ('rejected', 'Rejected'),
    ]
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='withdrawal_requests')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=20)
    account_holder_name = models.CharField(max_length=100)
    admin_note = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='processed_withdrawals')

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.brand.name} — ₦{self.amount} ({self.status})"


class PromotionPayment(models.Model):
    PROMO_TYPE_CHOICES = [('brand', 'Brand Homepage Promo'), ('product', 'Product Pin')]
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='promotions')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='promotions')
    promo_type = models.CharField(max_length=10, choices=PROMO_TYPE_CHOICES, default='brand')
    duration_days = models.PositiveIntegerField(default=7)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    payment_ref = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.brand.name} promo"


class SubscriptionPayment(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='subscriptions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.PositiveIntegerField(default=30)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    payment_ref = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.brand.name} Pro sub"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('admin', 'Admin'), ('product', 'Product'), ('sale', 'Sale'),
        ('offer', 'Offer'), ('system', 'System'), ('fraud', 'Fraud'),
        ('verification', 'Verification'), ('escrow', 'Escrow'), ('withdrawal', 'Withdrawal'),
    ]
    PRIORITY_CHOICES = [('high', 'High'), ('medium', 'Medium'), ('low', 'Low')]
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications',
        null=True, blank=True)
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} → {self.recipient}"


class SellerVerificationRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'),
    ]
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='verification_requests')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    applied_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_verifications')
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.brand.name} — {self.status}"

class SupportMessage(models.Model):
    SENDER_TYPES = [('user','User'),('admin','Admin')]
    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_messages')
    message      = models.TextField()
    sender_type  = models.CharField(max_length=5, choices=SENDER_TYPES, default='user')
    admin_sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='support_replies')
    is_read      = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender_type} — {self.user.username}: {self.message[:40]}"