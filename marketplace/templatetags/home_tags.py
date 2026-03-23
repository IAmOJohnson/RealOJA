from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def subtract(value, arg):
    """Subtract arg from value — used for savings calculation."""
    try:
        return Decimal(str(value)) - Decimal(str(arg))
    except Exception:
        return 0
