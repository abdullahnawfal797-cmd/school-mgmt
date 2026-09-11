import os
import sys
from pathlib import Path
from datetime import timedelta
from urllib.parse import urlparse

# تحديد المسار التنفيذي الحقيقي للبرنامج في بيئة التطوير وبيئة التجميع PyInstaller
if getattr(sys, 'frozen', False):
    EXE_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, '_MEIPASS', EXE_DIR / '_internal'))
    BASE_DIR = EXE_DIR
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = BASE_DIR
    EXE_DIR = BASE_DIR

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', os.getenv('SECRET_KEY', 'django-insecure-dev-only-secret-key-change-in-production'))

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'core',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # 'core.middleware.LicenseEnforcementMiddleware',
]

ROOT_URLCONF = 'school_mgmt.urls'

TEMPLATE_DIRS = list(dict.fromkeys([
    BUNDLE_DIR / 'core' / 'templates',
    BUNDLE_DIR / 'templates',
    BASE_DIR / 'core' / 'templates',
    BASE_DIR / 'templates',
]))

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [d for d in TEMPLATE_DIRS if d.exists()],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.school_portal_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'school_mgmt.wsgi.application'

LOCALAPPDATA = os.environ.get('LOCALAPPDATA')
if LOCALAPPDATA:
    MADRASATI_DATA_DIR = Path(LOCALAPPDATA) / 'Madrasati' / 'data'
else:
    MADRASATI_DATA_DIR = BASE_DIR / 'data'

MADRASATI_DATA_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR = MADRASATI_DATA_DIR / 'media'
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = MADRASATI_DATA_DIR / 'db.sqlite3'

# قراءة إعدادات PostgreSQL عبر مكتبة urllib القياسية دون الحاجة لتثبيت أي حزم خارجية
database_url = os.environ.get('DATABASE_URL')
if database_url:
    url = urlparse(database_url)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': url.path[1:],
            'USER': url.username,
            'PASSWORD': url.password,
            'HOST': url.hostname,
            'PORT': url.port or 5432,
            'CONN_MAX_AGE': 600,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': DB_PATH,
            'OPTIONS': {'timeout': 20},
            'ATOMIC_REQUESTS': True,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ar'
TIME_ZONE = 'Asia/Baghdad'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = list(dict.fromkeys([
    d for d in [
        BUNDLE_DIR / 'static',
        BASE_DIR / 'static',
    ] if d.exists() and d.is_dir()
]))

STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = MEDIA_DIR

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

AUTH_USER_MODEL = 'core.User'

CORS_ALLOW_ALL_ORIGINS = True
CSRF_TRUSTED_ORIGINS = [
    'https://school-mgmt-l0gu.onrender.com',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
]
