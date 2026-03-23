from .models import CartItem, Notification
from django.db.models import Q


def cart_context(request):
    if request.user.is_authenticated:
        cart_count = CartItem.objects.filter(user=request.user).values_list(
            'quantity', flat=True
        )
        return {'cart_count': sum(cart_count)}
    return {'cart_count': 0}


def notification_context(request):
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            Q(recipient=request.user) | Q(recipient=None),
            is_read=False
        ).count()
        return {'unread_notifications': unread_count}
    return {'unread_notifications': 0}
