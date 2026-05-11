"""
Local development settings for ArNet project.
"""
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', '*']

DATABASES['default'].update({
    'OPTIONS': {
        # PostgreSQL specific options (init_command is MySQL-specific)
        'sslmode': 'prefer',
    },
})

if DEBUG:
    try:
        import debug_toolbar
        INSTALLED_APPS.append('debug_toolbar')
        MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
        DEBUG_TOOLBAR_CONFIG = {
            'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG,
            'SHOW_COLLAPSED': True,
        }
    except ImportError:
        pass

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:8080',
    'http://127.0.0.1:8080',
]

# === CORREÇÃO DOS LOGS (Fim do Spam infinito) ===
LOGGING['loggers']['django']['level'] = 'INFO'
LOGGING['loggers']['apps']['level'] = 'DEBUG'

LOGGING['loggers']['django.utils.autoreload'] = {
    'level': 'INFO',
    'handlers': ['console'],
    'propagate': False,
}

if 'file' in LOGGING['handlers']:
    LOGGING['handlers']['file'] = {
        'class': 'logging.StreamHandler',
    }
# ===============================================

CACHES['default']['TIMEOUT'] = 60 

CELERY_TASK_ALWAYS_EAGER = env.bool('CELERY_EAGER', False)
CELERY_TASK_EAGER_PROPAGATES = True

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'