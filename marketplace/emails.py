"""
OJA Campus Marketplace — Transactional Email Engine
All email sending logic lives here. Each function is self-contained.

Usage:
    from .emails import send_order_receipt, send_seller_new_order
    send_order_receipt(master_order)
    send_seller_new_order(sub_order)

Email provider: configure EMAIL_* in settings.py.
Works with Gmail SMTP, SendGrid (smtp.sendgrid.net / apikey), Mailgun (smtp.mailgun.org).
"""

from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone


# ─── Base HTML wrapper ────────────────────────────────────────────────────────

def _wrap(title: str, body: str) -> str:
    """Wrap email body in a clean OJA-branded HTML shell."""
    year = timezone.now().year
    site = getattr(settings, 'OJA_SITE_URL', 'http://localhost:8000')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ margin:0; padding:0; background:#f5f5f5; font-family:'Segoe UI',Arial,sans-serif; color:#333; }}
    .wrap {{ max-width:600px; margin:0 auto; background:#fff; }}
    .header {{ background:linear-gradient(135deg,#0f172a,#1e293b); padding:2rem; text-align:center; }}
    .header-logo {{ font-size:2.5rem; font-weight:900; color:#D4AF37; letter-spacing:.08em; }}
    .header-sub {{ color:rgba(255,255,255,.5); font-size:.85rem; margin-top:.25rem; }}
    .body {{ padding:2rem; }}
    .title {{ font-size:1.4rem; font-weight:800; margin-bottom:.5rem; color:#0f172a; }}
    .subtitle {{ color:#666; font-size:.9rem; margin-bottom:1.5rem; }}
    .card {{ background:#f8f8f8; border-radius:10px; padding:1.25rem; margin-bottom:1.25rem; }}
    .card-gold {{ background:linear-gradient(135deg,#fff8e1,#fffde7); border:1.5px solid #D4AF37; border-radius:10px; padding:1.25rem; margin-bottom:1.25rem; }}
    .row {{ display:flex; justify-content:space-between; padding:.35rem 0; font-size:.875rem; border-bottom:1px solid #eee; }}
    .row:last-child {{ border-bottom:none; }}
    .row-label {{ color:#666; }}
    .row-val {{ font-weight:700; color:#0f172a; }}
    .total-row {{ display:flex; justify-content:space-between; padding:.5rem 0; font-size:1rem; font-weight:800; }}
    .gold {{ color:#D4AF37; }}
    .green {{ color:#15803d; }}
    .red {{ color:#ef4444; }}
    .btn {{ display:inline-block; background:#D4AF37; color:#fff; padding:.75rem 2rem; border-radius:8px; text-decoration:none; font-weight:700; font-size:.9rem; margin:.5rem 0; }}
    .btn-outline {{ display:inline-block; border:2px solid #D4AF37; color:#D4AF37; padding:.7rem 1.75rem; border-radius:8px; text-decoration:none; font-weight:700; font-size:.9rem; margin:.5rem .5rem .5rem 0; }}
    .step {{ display:flex; gap:.875rem; align-items:flex-start; margin-bottom:1rem; }}
    .step-num {{ width:28px; height:28px; border-radius:50%; background:#D4AF37; color:#fff; font-weight:800; font-size:.8rem; display:flex; align-items:center; justify-content:center; flex-shrink:0; margin-top:.1rem; }}
    .step-text {{ font-size:.875rem; color:#444; line-height:1.5; }}
    .item-row {{ display:flex; gap:1rem; align-items:center; padding:.75rem 0; border-bottom:1px solid #eee; }}
    .item-img {{ width:52px; height:52px; border-radius:8px; background:#eee; object-fit:cover; flex-shrink:0; }}
    .item-name {{ font-weight:700; font-size:.875rem; }}
    .item-meta {{ font-size:.78rem; color:#666; }}
    .item-price {{ font-weight:700; color:#D4AF37; margin-left:auto; white-space:nowrap; }}
    .badge {{ display:inline-block; padding:.25rem .75rem; border-radius:20px; font-size:.75rem; font-weight:700; }}
    .badge-gold {{ background:rgba(212,175,55,.15); color:#92400e; }}
    .badge-green {{ background:#dcfce7; color:#15803d; }}
    .badge-blue  {{ background:#dbeafe; color:#1d4ed8; }}
    .divider {{ border:none; border-top:1px solid #eee; margin:1.5rem 0; }}
    .footer {{ background:#0f172a; color:rgba(255,255,255,.45); font-size:.78rem; text-align:center; padding:1.5rem; }}
    .footer a {{ color:rgba(212,175,55,.7); text-decoration:none; }}
    @media(max-width:480px){{ .body{{ padding:1.25rem; }} }}
  </style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div class="header-logo">OJA</div>
    <div class="header-sub">Campus Marketplace</div>
  </div>
  <div class="body">
    {body}
  </div>
  <div class="footer">
    <p>© {year} OJA Campus Marketplace &nbsp;·&nbsp; <a href="{site}">Visit OJA</a> &nbsp;·&nbsp; <a href="{site}/support/">Contact Support</a></p>
    <p style="margin-top:.5rem;font-size:.72rem">You're receiving this because you have an OJA account. This is an automated message.</p>
  </div>
</div>
</body>
</html>"""


def _send(to: str | list, subject: str, html: str, text: str = ''):
    """Send a single transactional email. Silently swallows errors so app doesn't crash."""
    if not to:
        return
    if isinstance(to, str):
        to = [to]
    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'OJA Campus <noreply@oja.campus>')
        msg = EmailMultiAlternatives(subject, text or subject, from_email, to)
        msg.attach_alternative(html, 'text/html')
        msg.send(fail_silently=False)
    except Exception as exc:
        # Log but never crash the view
        import logging
        logging.getLogger('oja.email').warning(f'Email failed to {to}: {exc}')


# ─── Order Emails ─────────────────────────────────────────────────────────────

def send_order_receipt(master_order):
    """
    Buyer Receipt — sent immediately after Paystack payment confirmed.
    Lists all sub-orders, total, delivery details, and what happens next.
    """
    site    = getattr(settings, 'OJA_SITE_URL', '')
    buyer   = master_order.buyer
    orders  = list(master_order.orders.prefetch_related('items', 'brand').all())
    ref     = master_order.payment_reference

    # Build items table
    items_html = ''
    for sub in orders:
        items_html += f'<div style="margin-bottom:.5rem;font-size:.8rem;font-weight:700;color:#D4AF37;text-transform:uppercase">{sub.brand.name}</div>'
        for item in sub.items.all():
            items_html += f"""<div class="item-row">
              <div style="flex:1"><div class="item-name">{item.product_name}</div><div class="item-meta">Qty: {item.quantity} × ₦{item.product_price:,.0f}</div></div>
              <div class="item-price">₦{item.line_total:,.0f}</div>
            </div>"""
        items_html += '<div style="margin-bottom:1rem"></div>'

    zone_name = master_order.delivery_zone.name if master_order.delivery_zone else '—'

    body = f"""
    <p class="title">🎉 Order Confirmed!</p>
    <p class="subtitle">Hi {buyer.first_name or buyer.username}, your payment was successful and your order is now in escrow protection.</p>

    <div class="card-gold">
      <div style="display:flex;align-items:center;gap:.75rem">
        <span style="font-size:1.75rem">🔒</span>
        <div>
          <div style="font-weight:700;color:#92400e">Your money is protected</div>
          <div style="font-size:.825rem;color:#78350f">₦{master_order.grand_total:,.0f} held in escrow. Sellers only get paid after you confirm delivery.</div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="row"><span class="row-label">Order Reference</span><span class="row-val" style="font-family:monospace;font-size:.8rem">{ref}</span></div>
      <div class="row"><span class="row-label">Vendors</span><span class="row-val">{len(orders)} seller{"s" if len(orders)>1 else ""}</span></div>
      <div class="row"><span class="row-label">Delivery Zone</span><span class="row-val">{zone_name}</span></div>
      <div class="row"><span class="row-label">Delivery Address</span><span class="row-val">{master_order.delivery_address or "—"}</span></div>
      <div class="total-row"><span>Total Paid</span><span class="gold">₦{master_order.grand_total:,.0f}</span></div>
    </div>

    <p style="font-weight:700;margin-bottom:.75rem">Your Items</p>
    {items_html}

    <hr class="divider">
    <p style="font-weight:700;margin-bottom:.75rem">What happens next?</p>
    <div class="step"><div class="step-num">1</div><div class="step-text"><strong>Vendors pack your items</strong> — Each seller receives a notification to pack and drop their items at the OJA Hub.</div></div>
    <div class="step"><div class="step-num">2</div><div class="step-text"><strong>Hub consolidates</strong> — All your items arrive at the OJA Hub and are packed into one OJA-branded delivery bag.</div></div>
    <div class="step"><div class="step-num">3</div><div class="step-text"><strong>One rider delivers to you</strong> — A single rider delivers your complete order to {master_order.delivery_address or "your location"}.</div></div>
    <div class="step"><div class="step-num">4</div><div class="step-text"><strong>You confirm receipt</strong> — Click "Item Received" in your OJA dashboard to release funds to the sellers.</div></div>

    <div style="text-align:center;margin-top:2rem">
      <a href="{site}/profile/customer/" class="btn">Track My Order →</a>
    </div>
    """
    html = _wrap(f'Order Confirmed — {ref[:14]}', body)
    _send(buyer.email, f'✅ Order Confirmed — ₦{master_order.grand_total:,.0f} | OJA Campus', html)


def send_seller_new_order(sub_order):
    """
    Seller New Order Alert — sent to the brand's seller when a paid sub-order arrives.
    Includes items, buyer info, payout amount, and hub drop-off instructions.
    """
    site   = getattr(settings, 'OJA_SITE_URL', '')
    seller = sub_order.brand.seller
    items  = list(sub_order.items.all())
    ref    = sub_order.payment_reference

    items_html = ''
    for item in items:
        items_html += f"""<div class="item-row">
          <div style="flex:1"><div class="item-name">{item.product_name}</div><div class="item-meta">Qty: {item.quantity} × ₦{item.product_price:,.0f}</div></div>
          <div class="item-price">₦{item.line_total:,.0f}</div>
        </div>"""

    body = f"""
    <p class="title">🛒 You Have a New Order!</p>
    <p class="subtitle">Hi {seller.first_name or seller.username}, someone just bought from <strong>{sub_order.brand.name}</strong>. Payment is confirmed and in escrow.</p>

    <div class="card-gold">
      <div style="font-weight:700;color:#92400e;margin-bottom:.5rem">💰 Funds Secured in Escrow</div>
      <div class="total-row"><span>Your Payout</span><span class="gold">₦{sub_order.vendor_payout:,.0f}</span></div>
      <div style="font-size:.78rem;color:#92400e;margin-top:.25rem">Released to your wallet after buyer confirms delivery</div>
    </div>

    <div class="card">
      <div class="row"><span class="row-label">Sub-Order #</span><span class="row-val">{sub_order.pk}</span></div>
      <div class="row"><span class="row-label">Reference</span><span class="row-val" style="font-family:monospace;font-size:.8rem">{ref[:18]}</span></div>
      <div class="row"><span class="row-label">Subtotal</span><span class="row-val">₦{sub_order.subtotal:,.0f}</span></div>
      <div class="row"><span class="row-label">Commission ({sub_order.brand.commission_rate}%)</span><span class="row-val red">−₦{sub_order.commission_amount:,.0f}</span></div>
      <div class="total-row"><span>Your Payout</span><span class="gold">₦{sub_order.vendor_payout:,.0f}</span></div>
    </div>

    <p style="font-weight:700;margin-bottom:.75rem">Items Ordered</p>
    {items_html}

    <hr class="divider">

    <div class="card" style="border-left:4px solid #D4AF37;border-radius:0 10px 10px 0">
      <p style="font-weight:700;margin:0 0 .75rem">📋 Action Required — Drop at OJA Hub</p>
      <div class="step"><div class="step-num">1</div><div class="step-text">Pack the items listed above securely.</div></div>
      <div class="step"><div class="step-num">2</div><div class="step-text">Go to your Order Detail page to get your <strong>QR code / Sub-Order ID: {sub_order.pk}</strong></div></div>
      <div class="step"><div class="step-num">3</div><div class="step-text">Drop the package at the <strong>OJA Hub desk</strong> and show the QR code. The hub team will scan it in.</div></div>
    </div>

    <div style="text-align:center;margin-top:1.5rem">
      <a href="{site}/order/{sub_order.pk}/" class="btn">View Order Details →</a>
    </div>
    """
    html = _wrap(f'New Order #{sub_order.pk}', body)
    _send(seller.email, f'🛒 New Order #{sub_order.pk} — ₦{sub_order.vendor_payout:,.0f} payout | OJA', html)


def send_order_shipped(sub_order):
    """Buyer update — seller has dropped package at hub."""
    site  = getattr(settings, 'OJA_SITE_URL', '')
    buyer = sub_order.buyer
    body  = f"""
    <p class="title">🚚 Item On Its Way to the Hub!</p>
    <p class="subtitle">Hi {buyer.first_name or buyer.username}, <strong>{sub_order.brand.name}</strong> has packed your order and dropped it at the OJA Hub.</p>

    <div class="card">
      <div class="row"><span class="row-label">Sub-Order #</span><span class="row-val">{sub_order.pk}</span></div>
      <div class="row"><span class="row-label">From</span><span class="row-val">{sub_order.brand.name}</span></div>
      <div class="row"><span class="row-label">Hub Status</span><span class="row-val"><span class="badge badge-blue">🚚 In Transit to Hub</span></span></div>
    </div>

    <div class="card-gold">
      <p style="margin:0;font-size:.875rem;color:#92400e">
        Once <strong>all</strong> your vendors' items arrive at the hub, they'll be packed into one OJA bag and a rider will deliver everything to you at once.
      </p>
    </div>

    <div style="text-align:center;margin-top:1.5rem">
      <a href="{site}/profile/customer/" class="btn">Track Order →</a>
    </div>
    """
    html = _wrap('Item Dispatched to Hub', body)
    _send(buyer.email, f'🚚 {sub_order.brand.name} dropped your item at OJA Hub | Order #{sub_order.pk}', html)


def send_all_at_hub(master_order):
    """Buyer — all items are at hub, being packed."""
    site  = getattr(settings, 'OJA_SITE_URL', '')
    buyer = master_order.buyer
    count = master_order.orders.count()
    body  = f"""
    <p class="title">📦 All Your Items Are at the OJA Hub!</p>
    <p class="subtitle">Hi {buyer.first_name or buyer.username}, all {count} vendor{"s have" if count>1 else " has"} delivered your items to the OJA Hub. We're packing everything into one bag now!</p>

    <div class="card-gold">
      <div style="text-align:center;font-size:2rem;margin-bottom:.5rem">🎁</div>
      <div style="font-weight:700;text-align:center;color:#92400e">Packing in Progress</div>
      <div style="text-align:center;font-size:.85rem;color:#78350f;margin-top:.25rem">Your items are being combined into one OJA-branded delivery bag</div>
    </div>

    <div class="card">
      <div class="row"><span class="row-label">Reference</span><span class="row-val" style="font-family:monospace;font-size:.8rem">{master_order.payment_reference[:18]}</span></div>
      <div class="row"><span class="row-label">Items</span><span class="row-val">{count} vendor{"s" if count>1 else ""}</span></div>
      <div class="row"><span class="row-label">Deliver to</span><span class="row-val">{master_order.delivery_address or "Your location"}</span></div>
    </div>

    <p style="font-size:.875rem;color:#666;">A rider will be assigned and your order will be on the way soon. You'll get another email when it's dispatched.</p>

    <div style="text-align:center;margin-top:1.5rem">
      <a href="{site}/profile/customer/" class="btn">Track Order →</a>
    </div>
    """
    html = _wrap('Items Ready for Delivery', body)
    _send(buyer.email, f'📦 All your items are packed and ready for delivery! | OJA', html)


def send_order_dispatched(master_order):
    """Buyer — rider is on the way."""
    site  = getattr(settings, 'OJA_SITE_URL', '')
    buyer = master_order.buyer
    bin_label = master_order.hub_bin or 'your OJA bag'
    body  = f"""
    <p class="title">🛵 Your Order Is Out for Delivery!</p>
    <p class="subtitle">Hi {buyer.first_name or buyer.username}, a rider has picked up your {bin_label} and is heading to you now!</p>

    <div class="card-gold">
      <div style="text-align:center;font-size:2rem;margin-bottom:.5rem">🛵</div>
      <div style="font-weight:700;text-align:center;color:#92400e">Rider On The Way</div>
      <div style="text-align:center;font-size:.85rem;color:#78350f;margin-top:.25rem">Delivering to: {master_order.delivery_address or "your location"}</div>
    </div>

    <div class="card">
      <div class="row"><span class="row-label">Delivery Zone</span><span class="row-val">{master_order.delivery_zone.name if master_order.delivery_zone else "—"}</span></div>
      <div class="row"><span class="row-label">Bag Label</span><span class="row-val" style="font-family:monospace">{master_order.hub_bin or "—"}</span></div>
      <div class="row"><span class="row-label">Total Paid</span><span class="row-val gold">₦{master_order.grand_total:,.0f}</span></div>
    </div>

    <div style="background:#fef9c3;border-radius:10px;padding:1.1rem;margin-top:1rem">
      <p style="font-weight:700;margin:0 0 .4rem;color:#92400e">⚠ Important</p>
      <p style="font-size:.85rem;color:#78350f;margin:0">Please be available to receive your delivery. Once you receive your items, click <strong>"Item Received"</strong> in the OJA app to release payment to your sellers.</p>
    </div>

    <div style="text-align:center;margin-top:1.5rem">
      <a href="{site}/profile/customer/" class="btn">Confirm Delivery →</a>
    </div>
    """
    html = _wrap('Rider On The Way', body)
    _send(buyer.email, f'🛵 Your OJA order is out for delivery! Ref: {master_order.payment_reference[:14]}', html)


def send_delivery_confirmed(master_order):
    """Both buyer and all sellers — delivery confirmed, funds released."""
    site   = getattr(settings, 'OJA_SITE_URL', '')
    buyer  = master_order.buyer
    orders = list(master_order.orders.select_related('brand__seller').all())

    # Email to buyer
    body_buyer = f"""
    <p class="title">✅ Delivery Confirmed!</p>
    <p class="subtitle">Hi {buyer.first_name or buyer.username}, you've confirmed receipt of your OJA order. Funds have been released to all sellers. Thank you!</p>

    <div class="card" style="border-left:4px solid #15803d;border-radius:0 10px 10px 0">
      <div class="row"><span class="row-label">Reference</span><span class="row-val" style="font-family:monospace;font-size:.8rem">{master_order.payment_reference[:18]}</span></div>
      <div class="row"><span class="row-label">Confirmed</span><span class="row-val">{timezone.now().strftime("%b %d, %Y")}</span></div>
      <div class="total-row"><span>Total</span><span class="green">₦{master_order.grand_total:,.0f}</span></div>
    </div>

    <p style="font-size:.875rem;color:#666;">All sellers have been paid. We hope you love your items! 🎉</p>

    <div style="text-align:center;margin-top:1.5rem">
      <a href="{site}/brands/" class="btn">Shop Again →</a>
    </div>
    """
    _send(buyer.email, '✅ Order Complete — Funds Released to Sellers | OJA', _wrap('Order Complete', body_buyer))

    # Email to each seller
    for sub in orders:
        seller = sub.brand.seller
        body_seller = f"""
    <p class="title">💰 Funds Released to Your Wallet!</p>
    <p class="subtitle">Hi {seller.first_name or seller.username}, the buyer has confirmed delivery for Order #{sub.pk}. Your payout has been released!</p>

    <div class="card-gold">
      <div class="total-row"><span>Payout Added</span><span class="gold">₦{sub.vendor_payout:,.0f}</span></div>
      <div style="font-size:.78rem;color:#92400e;margin-top:.25rem">Now available in your OJA wallet — request withdrawal anytime</div>
    </div>

    <div class="card">
      <div class="row"><span class="row-label">Order #</span><span class="row-val">{sub.pk}</span></div>
      <div class="row"><span class="row-label">Subtotal</span><span class="row-val">₦{sub.subtotal:,.0f}</span></div>
      <div class="row"><span class="row-label">Commission</span><span class="row-val red">−₦{sub.commission_amount:,.0f}</span></div>
      <div class="total-row"><span>Your Payout</span><span class="gold">₦{sub.vendor_payout:,.0f}</span></div>
    </div>

    <div style="text-align:center;margin-top:1.5rem">
      <a href="{site}/profile/seller/" class="btn">View Wallet →</a>
    </div>
        """
        _send(seller.email, f'💰 ₦{sub.vendor_payout:,.0f} released to your OJA wallet! | Order #{sub.pk}', _wrap('Payout Released', body_seller))


def send_order_cancelled(order):
    """Both buyer and seller — order cancelled."""
    site   = getattr(settings, 'OJA_SITE_URL', '')
    buyer  = order.buyer
    seller = order.brand.seller

    # Buyer
    body_buyer = f"""
    <p class="title">❌ Order Cancelled</p>
    <p class="subtitle">Hi {buyer.first_name or buyer.username}, your order #{order.pk} from {order.brand.name} has been cancelled.</p>
    <div class="card">
      <div class="row"><span class="row-label">Order #</span><span class="row-val">{order.pk}</span></div>
      <div class="row"><span class="row-label">Amount</span><span class="row-val">₦{order.total:,.0f}</span></div>
      <div class="row"><span class="row-label">Status</span><span class="row-val"><span class="badge" style="background:#f3f4f6;color:#6b7280">Cancelled</span></span></div>
    </div>
    <p style="font-size:.875rem;color:#666;">If you paid via Paystack, any escrow-locked funds will be reversed. Contact support if you have questions.</p>
    <div style="text-align:center;margin-top:1.5rem"><a href="{site}/support/" class="btn">Contact Support</a></div>
    """
    _send(buyer.email, f'❌ Order #{order.pk} Cancelled | OJA', _wrap('Order Cancelled', body_buyer))

    # Seller
    body_seller = f"""
    <p class="title">❌ Order Cancelled by Buyer</p>
    <p class="subtitle">Hi {seller.first_name or seller.username}, Order #{order.pk} from {order.brand.name} was cancelled by the buyer.</p>
    <div class="card">
      <div class="row"><span class="row-label">Order #</span><span class="row-val">{order.pk}</span></div>
      <div class="row"><span class="row-label">Value</span><span class="row-val">₦{order.subtotal:,.0f}</span></div>
    </div>
    <p style="font-size:.875rem;color:#666;">No action required. Stock has been restored automatically.</p>
    """
    _send(seller.email, f'❌ Order #{order.pk} was cancelled | OJA', _wrap('Order Cancelled', body_seller))


def send_dispute_raised(order):
    """Admin + seller — dispute raised."""
    site   = getattr(settings, 'OJA_SITE_URL', '')
    seller = order.brand.seller
    body   = f"""
    <p class="title">⚠ Dispute Raised on Your Order</p>
    <p class="subtitle">Hi {seller.first_name or seller.username}, the buyer has raised a dispute on Order #{order.pk}. The OJA admin team will review and resolve within 24 hours.</p>
    <div class="card" style="border-left:4px solid #f59e0b;border-radius:0 10px 10px 0">
      <div class="row"><span class="row-label">Order #</span><span class="row-val">{order.pk}</span></div>
      <div class="row"><span class="row-label">Payout at Risk</span><span class="row-val red">₦{order.vendor_payout:,.0f}</span></div>
      <div class="row"><span class="row-label">Status</span><span class="row-val"><span class="badge" style="background:#fee2e2;color:#b91c1c">⚠ Disputed</span></span></div>
    </div>
    <p style="font-size:.875rem;color:#666;">Funds remain in escrow during the review. Our team will contact you if more information is needed.</p>
    <div style="text-align:center;margin-top:1.5rem"><a href="{site}/order/{order.pk}/" class="btn">View Order →</a></div>
    """
    _send(seller.email, f'⚠ Dispute on Order #{order.pk} — Under Review | OJA', _wrap('Dispute Raised', body))


def send_pro_upgrade_confirmation(brand):
    """Seller — Pro upgrade confirmed."""
    site   = getattr(settings, 'OJA_SITE_URL', '')
    seller = brand.seller
    expires = brand.tier_expires_at.strftime('%B %d, %Y') if brand.tier_expires_at else '30 days'
    body   = f"""
    <p class="title">⭐ Welcome to OJA Pro!</p>
    <p class="subtitle">Hi {seller.first_name or seller.username}, your store <strong>{brand.name}</strong> is now on the Pro plan. 🎉</p>

    <div class="card-gold">
      <p style="font-weight:700;color:#92400e;margin:0 0 .875rem">Your Pro benefits are now active:</p>
      <div class="step"><div class="step-num">✓</div><div class="step-text"><strong>Unlimited product listings</strong> — no more 5-product cap</div></div>
      <div class="step"><div class="step-num">✓</div><div class="step-text"><strong>Blue Tick badge</strong> — verification request submitted to admin</div></div>
      <div class="step"><div class="step-num">✓</div><div class="step-text"><strong>Priority placement</strong> — your store appears higher in search</div></div>
      <div class="step"><div class="step-num">✓</div><div class="step-text"><strong>Promoted homepage slot</strong> — featured brand section</div></div>
    </div>

    <div class="card">
      <div class="row"><span class="row-label">Plan</span><span class="row-val">Pro Monthly</span></div>
      <div class="row"><span class="row-label">Amount Paid</span><span class="row-val">₦5,000</span></div>
      <div class="row"><span class="row-label">Active Until</span><span class="row-val">{expires}</span></div>
    </div>

    <div style="text-align:center;margin-top:1.5rem">
      <a href="{site}/profile/seller/" class="btn">Go to Dashboard →</a>
    </div>
    """
    html = _wrap('Welcome to OJA Pro!', body)
    _send(seller.email, f'⭐ You\'re now on OJA Pro! {brand.name} is verified', html)


def send_withdrawal_processed(withdrawal, status):
    """Seller — withdrawal approved or rejected."""
    site   = getattr(settings, 'OJA_SITE_URL', '')
    seller = withdrawal.brand.seller
    if status == 'paid':
        body = f"""
    <p class="title">💸 Withdrawal Processed!</p>
    <p class="subtitle">Hi {seller.first_name or seller.username}, your withdrawal request has been approved and processed.</p>
    <div class="card-gold">
      <div class="total-row"><span>Amount Transferred</span><span class="gold">₦{withdrawal.amount:,.0f}</span></div>
      <div style="font-size:.78rem;color:#92400e;margin-top:.25rem">To: {withdrawal.bank_name} · {withdrawal.account_number}</div>
    </div>
    <p style="font-size:.875rem;color:#666;">Bank transfers typically arrive within 1–2 business days. Contact support if you don't receive it.</p>
        """
        subject = f'💸 Withdrawal of ₦{withdrawal.amount:,.0f} processed | OJA'
    else:
        body = f"""
    <p class="title">❌ Withdrawal Rejected</p>
    <p class="subtitle">Hi {seller.first_name or seller.username}, your withdrawal request was not approved.</p>
    <div class="card">
      <div class="row"><span class="row-label">Amount</span><span class="row-val">₦{withdrawal.amount:,.0f}</span></div>
      <div class="row"><span class="row-label">Reason</span><span class="row-val">{withdrawal.admin_note or "Contact support"}</span></div>
    </div>
    <p style="font-size:.875rem;color:#666;">Your balance has been restored. Please contact support if you have questions.</p>
    <div style="text-align:center;margin-top:1.5rem"><a href="{site}/support/" class="btn">Contact Support</a></div>
        """
        subject = f'❌ Withdrawal request rejected | OJA'
    _send(seller.email, subject, _wrap('Withdrawal Update', body))