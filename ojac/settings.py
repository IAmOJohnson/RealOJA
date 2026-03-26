"""
OJA Marketplace - Django Settings
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-replace-this-in-production-with-a-real-secret-key'

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1',  'oja-lzug.onrender.com']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'marketplace',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ojac.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'marketplace.context_processors.cart_context',
                'marketplace.context_processors.notification_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'ojac.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_USER_MODEL = 'marketplace.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
# This line is the magic that makes CSS work on Render
STORAGES = {
    # This handles your CSS/JS (WhiteNoise)
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    # This handles regular files/images (The missing piece!)
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/profile/'
LOGOUT_REDIRECT_URL = '/'

# Session
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400  # 24 hours

MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'


# ── Paystack ──
PAYSTACK_PUBLIC_KEY = 'pk_test_8a4e151ac1c636556397893c39fc1f268a06e420'
PAYSTACK_SECRET_KEY = 'sk_test_4fd6d272efe52dab2a977dcd951275f05e68d64e'

# ── Email (Transactional) ──
# For SendGrid: set EMAIL_HOST=smtp.sendgrid.net, EMAIL_HOST_USER='apikey', EMAIL_HOST_PASSWORD=your_api_key
# For Mailgun:  set EMAIL_HOST=smtp.mailgun.org, EMAIL_HOST_USER=postmaster@yourdomain, EMAIL_HOST_PASSWORD=your_key
# For Gmail:    set EMAIL_HOST=smtp.gmail.com, EMAIL_HOST_USER=youremail, EMAIL_HOST_PASSWORD=app_password
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = 'smtp.gmail.com'       # Change to smtp.sendgrid.net or smtp.mailgun.org
EMAIL_PORT          = 587
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = 'ojamarket2026@gmail.com' # ← Replace with your email
EMAIL_HOST_PASSWORD = 'Yinka 12'    # ← Replace with your password / API key
DEFAULT_FROM_EMAIL  = 'OJA Campus <noreply@oja.campus>'
OJA_SITE_URL        = 'http://127.0.0.1:8000'  # ← Change to your live domain in production