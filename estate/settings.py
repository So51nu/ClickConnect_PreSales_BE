"""
Django settings for estate project.
"""

from datetime import timedelta
from pathlib import Path
from celery.schedules import crontab  # 👈 Celery schedules ke liye

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-__0y*ey0w8w%-$ai*o%wtkg&$*!_6v5_=38-tc5=7iut^em9mr"

# SECURITY WARNING: don't run with debug turned on in production!
import os
DEBUG = True

ALLOWED_HOSTS = ["*",]

CSRF_TRUSTED_ORIGINS = [
    "https://api.presales.clickconnectmedia.cloud",
]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_SSL_REDIRECT = True  # 👈 abhi false hi rakho

ZAPIER_META_WEBHOOK_SECRET = "put-a-long-random-secret-here"
MEDIA_URL = "/api/media/"
MEDIA_ROOT = BASE_DIR / "media"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.admin",
    "django.contrib.auth",
]

INSTALLED_APPS += [
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "clientsetup",
    "accounts",
    "channel",
    "booking",
    "setup",
    "common",
    "leadmanage",
    "salelead",
    "costsheet",
]

# ---------------- META verification token (Facebook webhook) ----------------
META_WEBHOOK_VERIFY_TOKEN = "koi-strong-secret-string"  # 👈 isko Meta app me bhi same rakhna

# ---------------- Google Sheets configuration (NEW) ----------------
# Service account JSON ka path (BASE_DIR/keys/gsheets-service.json)
GSHEETS_CREDENTIALS_FILE = BASE_DIR / "keys" / "gsheets-service.json"

# Google Sheet ka ID (URL ke beech wala lamba string)
# example: https://docs.google.com/spreadsheets/d/<YAHAN_ID>/edit#gid=0
GSHEETS_SHEET_ID = "YOUR_GOOGLE_SHEETS_ID_HERE"

# Sheet/tab ka naam (bottom wala "Sheet1", "Leads", etc.)
GSHEETS_WORKSHEET_NAME = "Sheet1"

# ---------------- Celery configuration ----------------
CELERY_BROKER_URL = "redis://localhost:6379/10"
CELERY_RESULT_BACKEND = "redis://localhost:6379/11"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Kolkata"

# Beat schedule: Google Sheet sync har 5 minute me
CELERY_BEAT_SCHEDULE = {
    # Inventory auto unblock – har 15 min
    "inventory-auto-unblock": {
        "task": "common.tasks.auto_unlock_expired_inventory_blocks",
        "schedule": crontab(minute="*/15"),
    },
    # Lead updates reminders – har 5 min
    "salesleadupdate-reminders": {
        "task": "common.tasks.send_due_salesleadupdate_reminders",
        "schedule": crontab(minute="*/5"),
    },
    # Site visit reminders – har 5 min
    "sitevisit-reminders": {
        "task": "common.tasks.send_due_sitevisit_reminders",
        "schedule": crontab(minute="*/5"),
    },
}


X_FRAME_OPTIONS = "SAMEORIGIN"

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "estate.urls"

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.1.13:5173",
    "http://192.168.1.18:5173",
    "http://192.168.1.15:5173",
    "https://clickconnectmedia.cloud",
    "https://www.clickconnectmedia.cloud",

]

CORS_URLS_REGEX = r"^/api/.*$"
CORS_ALLOW_CREDENTIALS = False

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

SIMPLE_JWT = {
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=24),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

AUTH_USER_MODEL = "accounts.User"

WSGI_APPLICATION = "estate.wsgi.application"

# ---------------- Database ----------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "presale_sonu",              # 👈 NEW DB NAME
        "USER": "presale_sonu_user",         # 👈 NEW USER
        "PASSWORD": "StrongPassword@123",    # 👈 wahi password
        "HOST": "localhost",
        "PORT": "5432",
    }
}

# ---------------- Password validation ----------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ---------------- Internationalization ----------------
# ---------------- Internationalization ----------------
LANGUAGE_CODE = "en-us"

# 🔹 Application ka base timezone India (IST)
TIME_ZONE = "Asia/Kolkata"

USE_I18N = True
USE_TZ = True   # ye True hi rehne do (Django recommended)


# ---------------- Static files ----------------
STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "EXCEPTION_HANDLER": "common.exceptions.custom_exception_handler",
}

FRONTEND_BASE_URL = "http://localhost:5173/"


EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'sonuyadav2192004@gmail.com'
EMAIL_HOST_PASSWORD = 'tcrvitsnimxmltej'

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django.security.DisallowedHost": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": True,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": True,
        },
    },
}

