import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only")

DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "true"

# --- Hosts / CSRF (Render) ---
RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")  # e.g. boxer-manager.onrender.com
ALLOWED_HOSTS = [RENDER_HOST] if RENDER_HOST else []
ALLOWED_HOSTS += [".onrender.com"]  # allow any *.onrender.com subdomain

CSRF_TRUSTED_ORIGINS = []
if RENDER_HOST:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_HOST}")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.getenv("DJANGO_DEBUG", "True").lower() != "true"  # redirect to https in prod

# --- Apps ---
INSTALLED_APPS = [
    'rest_framework',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "BoxersPresenceApp.apps.BoxersPresenceAppConfig",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'boxers_project.urls'
WSGI_APPLICATION = 'boxers_project.wsgi.application'
ASGI_APPLICATION = 'boxers_project.asgi.application'  # harmless; good if you ever use ASGI features

# --- Database ---
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# --- Static files (WhiteNoise) ---
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Cookies secure in prod
SESSION_COOKIE_SECURE = os.getenv("DJANGO_DEBUG", "True").lower() != "true"
CSRF_COOKIE_SECURE = os.getenv("DJANGO_DEBUG", "True").lower() != "true"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_REDIRECT_URL = 'home'
LOGIN_URL = '/login/'
LOGOUT_REDIRECT_URL = 'login'
