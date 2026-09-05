import os
import sys
from pathlib import Path
from datetime import timedelta

# تحديد المسار التنفيذي الحقيقي للبرنامج في بيئة التطوير وبيئة التجميع PyInstaller
if getattr(sys, 'frozen', False):
    # مسار المجلد الحاوي للملف التنفيذي (.exe)
    EXE_DIR = Path(sys.executable).resolve().parent
    # مسار الحزم والمكتبات المجمعة داخل _internal أو _MEIPASS
    BUNDLE_DIR = Path(getattr(sys, '_MEIPASS', EXE_DIR / '_internal'))
    BASE_DIR = EXE_DIR
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = BASE_DIR
    EXE_DIR = BASE_DIR

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-dev-only-secret-key-change-in-production')
DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() not in ('false', '0', 'no')
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '::1', '*']

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
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'core.middleware.LicenseEnforcementMiddleware',
]

ROOT_URLCONF = 'school_mgmt.urls'

# تجميع مسارات القوالب بدون تكرار
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

# مسار التخزين الدائم المعتمد لمنع فقدان البيانات نهائياً (Data Persistence)
LOCALAPPDATA = os.environ.get('LOCALAPPDATA')
if LOCALAPPDATA:
    MADRASATI_DATA_DIR = Path(LOCALAPPDATA) / 'Madrasati' / 'data'
else:
    MADRASATI_DATA_DIR = BASE_DIR / 'data'

MADRASATI_DATA_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR = MADRASATI_DATA_DIR / 'media'
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# قاعدة البيانات الدائمة
DB_PATH = MADRASATI_DATA_DIR / 'db.sqlite3'

# هجرة البيانات التلقائية عند أول تشغيل من مجلد المشروع إلى المسار الدائم لضمان عدم فقدان أي بيانات
SOURCE_DB = BASE_DIR / 'db.sqlite3'
if not DB_PATH.exists() and SOURCE_DB.exists():
    import shutil
    try:
        shutil.copy2(SOURCE_DB, DB_PATH)
    except Exception:
        pass

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DB_PATH,
        'OPTIONS': {
            'timeout': 20,
        },
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

# Celery أوفلاين فوري للمنظومة المكتبية
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

AUTH_USER_MODEL = 'core.User'

CORS_ALLOW_ALL_ORIGINS = True