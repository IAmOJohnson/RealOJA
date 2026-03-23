from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    MasterOrder,
    OrderEnquiry,
    ProductVideo,
    User, Brand, Product, Category, CartItem, WishlistItem,
    Notification, Review, ProductImage, ProductSpecification,
    SellerVerificationRequest, Order, OrderItem, CampusZone,
    WithdrawalRequest, PromotionPayment, SubscriptionPayment,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'user_type', 'student_verified', 'is_active')
    list_filter = ('user_type', 'student_verified', 'is_active')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('OJA Info', {'fields': ('user_type', 'phone', 'profile_complete',
                                 'matric_number', 'university', 'student_id_image', 'student_verified',
                                 'bank_name', 'account_number', 'account_holder_name', 'bank_code')}),
    )


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'seller', 'tier', 'is_verified', 'is_promoted', 'wallet_balance', 'follower_count')
    list_filter = ('tier', 'is_verified', 'is_promoted')
    search_fields = ('name', 'seller__username')


@admin.register(CampusZone)
class CampusZoneAdmin(admin.ModelAdmin):
    list_display = ('name', 'zone_type', 'flat_rate', 'is_active', 'university')
    list_filter = ('zone_type', 'is_active')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('line_total',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('pk', 'buyer', 'brand', 'total', 'commission_amount', 'vendor_payout', 'status', 'created_at')
    list_filter = ('status',)
    inlines = [OrderItemInline]


@admin.register(WithdrawalRequest)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ('brand', 'amount', 'status', 'requested_at', 'processed_by')
    list_filter = ('status',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'category', 'price', 'stock', 'status', 'is_promoted', 'sales')
    list_filter = ('status', 'category', 'is_promoted')
    search_fields = ('name', 'brand__name')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read')


@admin.register(SellerVerificationRequest)
class VerificationAdmin(admin.ModelAdmin):
    list_display = ('brand', 'status', 'applied_at')
    list_filter = ('status',)


admin.site.register(Review)
admin.site.register(CartItem)
admin.site.register(WishlistItem)
admin.site.register(PromotionPayment)
admin.site.register(SubscriptionPayment)
admin.site.register(ProductVideo)
admin.site.register(OrderEnquiry)

@admin.register(MasterOrder)
class MasterOrderAdmin(admin.ModelAdmin):
    list_display = ('payment_reference', 'buyer', 'status', 'grand_total', 'hub_bin', 'arrived_count', 'total_sub_orders', 'created_at')
    list_filter  = ('status',)
    search_fields = ('payment_reference', 'buyer__username')