# OJA Marketplace — React to Django Migration Guide

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Architecture Comparison](#2-architecture-comparison)
3. [Project Structure](#3-project-structure)
4. [Setup & Installation](#4-setup--installation)
5. [Model Reference](#5-model-reference)
6. [URL & View Reference](#6-url--view-reference)
7. [Authentication System](#7-authentication-system)
8. [Feature Migration Map](#8-feature-migration-map)
9. [Deployment Checklist](#9-deployment-checklist)
10. [Extending the Project](#10-extending-the-project)

---

## 1. Project Overview

**OJA** is a Nigerian multi-role e-commerce marketplace with three user types:
- **Customer** — browses products, manages cart/wishlist, follows brands
- **Seller** — manages a brand/store, lists products, receives orders
- **Admin** — verifies sellers, sends notifications, monitors platform

### What changed in the migration

| Before (React) | After (Django) |
|---|---|
| `localStorage` for ALL data | SQLite database (real persistence) |
| No real backend | Django views handle all logic |
| Passwords stored in browser | Hashed passwords via `django.contrib.auth` |
| State lost on browser clear | Server-side sessions |
| No real auth | Django sessions, login_required decorators |
| Vite + Node.js | Python only |
| TSX components | Django HTML templates |

---

## 2. Architecture Comparison

### React (before)
```
Browser
  └── React App
        ├── localStorage ("ojaCUser", "ojaCart", "marketplace_products", ...)
        ├── Context providers (UserContext, MarketplaceContext, CartContext, ...)
        └── Express server (barely used — one /api/demo stub)
```

### Django (after)
```
Browser  ──HTTP──►  Django
                      ├── urls.py  (routing)
                      ├── views.py (logic)
                      ├── models.py (database via ORM)
                      ├── templates/ (HTML rendering)
                      └── SQLite database
```

---

## 3. Project Structure

```
ojac_django/
├── manage.py
├── requirements.txt
├── db.sqlite3                  ← auto-created on first migrate
│
├── ojac/                       ← Django project config
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── marketplace/                ← Main app
│   ├── models.py               ← All database models
│   ├── views.py                ← All request handlers
│   ├── urls.py                 ← URL patterns
│   ├── forms.py                ← Form definitions
│   ├── admin.py                ← Django admin config
│   ├── context_processors.py   ← Global template variables (cart count, etc.)
│   ├── apps.py
│   └── templates/
│       └── marketplace/
│           ├── base.html           ← Layout with navbar & footer
│           ├── home.html
│           ├── login.html
│           ├── signup.html
│           ├── seller_onboard.html
│           ├── brands.html
│           ├── brand_detail.html
│           ├── product_detail.html
│           ├── product_edit.html
│           ├── cart.html
│           ├── wishlist.html
│           ├── categories.html
│           ├── deals.html
│           ├── notifications.html
│           ├── profile_customer.html
│           ├── profile_seller.html
│           └── profile_admin.html
│
└── static/
    └── css/
        └── oja.css             ← All styles (replicates Tailwind design)
```

---

## 4. Setup & Installation

### Prerequisites
- Python 3.10+ installed
- pip installed

### Step-by-step

```bash
# 1. Navigate to project folder
cd ojac_django

# 2. Create a virtual environment
python -m venv venv

# 3. Activate it
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run database migrations
python manage.py makemigrations
python manage.py migrate

# 6. Create a superuser (for Django admin panel)
python manage.py createsuperuser
# When prompted, fill in email, username, and password.
# Then open SQLite shell or Django shell to set user_type = 'admin':
python manage.py shell
>>> from marketplace.models import User
>>> u = User.objects.get(username='your_username')
>>> u.user_type = 'admin'
>>> u.save()
>>> exit()

# 7. (Optional) Load some initial categories
python manage.py shell
>>> from marketplace.models import Category
>>> cats = [
...   ('Fashion', 'fashion', '👗'),
...   ('Electronics', 'electronics', '📱'),
...   ('Food & Beverages', 'food', '🍔'),
...   ('Beauty', 'beauty', '💄'),
...   ('Home & Living', 'home', '🏠'),
...   ('Sports', 'sports', '⚽'),
... ]
>>> for name, slug, icon in cats:
...     Category.objects.get_or_create(name=name, slug=slug, defaults={'icon': icon})
>>> exit()

# 8. Start the development server
python manage.py runserver

# 9. Open in browser
# http://127.0.0.1:8000/
```

### Access the Django Admin panel
Visit `http://127.0.0.1:8000/admin/` and log in with your superuser credentials.
From there you can manage all users, brands, products, and notifications directly.

---

## 5. Model Reference

All models live in `marketplace/models.py`. Here's a quick reference:

### User
Custom user extending Django's AbstractUser.

| Field | Type | Notes |
|---|---|---|
| `username` | CharField | Set to email on registration |
| `email` | EmailField | Used for login |
| `user_type` | CharField | `customer`, `seller`, or `admin` |
| `phone` | CharField | |
| `profile_complete` | BooleanField | True after onboarding |
| `bank_name` | CharField | Seller only |
| `account_number` | CharField | Seller only |
| `account_holder_name` | CharField | Seller only |

### Brand
One-to-one with a Seller user.

| Field | Type | Notes |
|---|---|---|
| `seller` | ForeignKey(User) | OneToOne |
| `name` | CharField | Unique |
| `description` | TextField | |
| `logo` | ImageField | Uploaded to `/media/brand_logos/` |
| `is_verified` | BooleanField | Set by admin |
| `followers` | ManyToManyField(User) | Customers only |
| `whatsapp/instagram/twitter/tiktok` | CharField | Social links |

### Product

| Field | Type | Notes |
|---|---|---|
| `brand` | ForeignKey(Brand) | |
| `category` | ForeignKey(Category) | |
| `price` | DecimalField | Current sale price |
| `original_price` | DecimalField | For showing discount |
| `image` | ImageField | Main image |
| `stock` | PositiveIntegerField | |
| `status` | CharField | `active`, `inactive`, `draft` |
| `discount` | PositiveIntegerField | Percentage (0-100) |
| `deal_ends_at` | DateTimeField | Null = no deal |

### CartItem
Links a User to a Product with quantity.

### WishlistItem
Links a User to a Product.

### Notification
Has optional `recipient` (null = broadcast to admins).

---

## 6. URL & View Reference

| URL | View | Auth Required |
|---|---|---|
| `/` | `home` | No |
| `/login/` | `login_view` | No |
| `/signup/` | `signup_view` | No |
| `/logout/` | `logout_view` | No |
| `/seller-onboard/` | `seller_onboard` | Yes (seller) |
| `/profile/` | `profile` (redirects) | Yes |
| `/profile/customer/` | `customer_profile` | Yes (customer) |
| `/profile/seller/` | `seller_profile` | Yes (seller) |
| `/profile/admin/` | `admin_profile` | Yes (admin) |
| `/product/<id>/` | `product_detail` | No |
| `/product/<id>/edit/` | `edit_product` | Yes (seller) |
| `/product/<id>/add-to-cart/` | `add_to_cart` | Yes |
| `/product/<id>/wishlist/` | `toggle_wishlist` | Yes |
| `/brands/` | `brands_list` | No |
| `/brand/<id>/` | `brand_detail` | No |
| `/brand/<id>/follow/` | `follow_brand` | Yes (customer) |
| `/categories/` | `categories` | No |
| `/deals/` | `deals` | No |
| `/cart/` | `cart` | Yes |
| `/wishlist/` | `wishlist` | Yes |
| `/notifications/` | `notifications` | Yes |
| `/admin/` | Django admin | Superuser |

---

## 7. Authentication System

### Registration
**Customer signup** → `CustomerSignupForm`
- Creates a `User` with `user_type='customer'`
- Sets `username = email` (so login works with email)

**Seller signup** → `SellerSignupForm`
- Creates a `User` with `user_type='seller'`
- Automatically creates a linked `Brand`
- Redirects to 3-step onboarding

### Login
Uses Django's `AuthenticationForm` — email as username field.

### Session
Django handles sessions server-side via `django.contrib.sessions`.
The `@login_required` decorator protects all authenticated routes.
`LOGIN_URL = '/login/'` is set in settings.

### Password storage
Django hashes passwords with PBKDF2 by default. **Passwords are never stored in plain text** (unlike the old localStorage approach).

---

## 8. Feature Migration Map

### localStorage keys → Database tables

| React localStorage key | Django model / field |
|---|---|
| `ojaCUser` | `request.user` (Django session) |
| `ojaUsers` | `marketplace_user` table |
| `marketplace_brands` | `marketplace_brand` table |
| `marketplace_products` | `marketplace_product` table |
| `ojaCart` | `marketplace_cartitem` table |
| `ojaWishlist` | `marketplace_wishlistitem` table |
| `ojaNotifications` | `marketplace_notification` table |
| `followed_brands` | `marketplace_brand_followers` (M2M) |

### React Context → Django equivalent

| React Context | Django equivalent |
|---|---|
| `UserContext` | `request.user` + Django auth |
| `MarketplaceContext` | ORM queries in views |
| `CartContext` | `CartItem` model + cart views |
| `WishlistContext` | `WishlistItem` model + wishlist views |
| `NotificationContext` | `Notification` model + notification views |

### React routes → Django URLs

| React Route | Django URL |
|---|---|
| `/` | `/` |
| `/product/:productId` | `/product/<int:product_id>/` |
| `/brand/:brandId` | `/brand/<int:brand_id>/` |
| `/brands` | `/brands/` |
| `/categories` | `/categories/` |
| `/deals` | `/deals/` |
| `/login` | `/login/` |
| `/signup` | `/signup/` |
| `/profile` | `/profile/` (auto-redirects by user type) |
| `/seller-onboard` | `/seller-onboard/` |
| `/notifications` | `/notifications/` |
| `/cart` | `/cart/` |
| `/wishlist` | `/wishlist/` |

---

## 9. Deployment Checklist

When you're ready to go to production:

### 1. Update settings.py
```python
DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')  # use env vars!
```

### 2. Switch to PostgreSQL (recommended for production)
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': '5432',
    }
}
```
Add `psycopg2-binary` to requirements.txt.

### 3. Collect static files
```bash
python manage.py collectstatic
```

### 4. Serve media files
For production, configure Nginx or use a cloud storage service (e.g. AWS S3 with `django-storages`).

### 5. Use Gunicorn
```bash
pip install gunicorn
gunicorn ojac.wsgi:application
```

### 6. Set up HTTPS
Use Let's Encrypt + Certbot with Nginx.

---

## 10. Extending the Project

### Add an Order model (next step)
```python
class Order(models.Model):
    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    items = models.ManyToManyField(Product, through='OrderItem')
    total = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Add payment integration (Paystack — popular in Nigeria)
```python
pip install django-paystack
# or use their REST API directly
```

### Add product search
```python
# In views.py — products with search
products = Product.objects.filter(
    Q(name__icontains=query) |
    Q(description__icontains=query) |
    Q(brand__name__icontains=query)
)
```

### Add pagination
```python
from django.core.paginator import Paginator
paginator = Paginator(products, 12)
page_obj = paginator.get_page(request.GET.get('page'))
```

### Convert to Django REST Framework (API)
If you later want to rebuild the React frontend while keeping Django as the backend:
```bash
pip install djangorestframework
```

---

*Generated for OJA Marketplace — March 2026*
