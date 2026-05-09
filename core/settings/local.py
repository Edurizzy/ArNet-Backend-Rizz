"""
Local development settings for ArNet project.

This module extends base settings with development-specific configurations.
Use this for local development environment.
"""

from .base import *

# Development-specific settings
DEBUG = True

# Additional allowed hosts for local development
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', '*']

# Development database - allow SQLite for quick local setup
DATABASES['default'].update({
    'OPTIONS': {
        'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        'charset': 'utf8mb4',
    },
})

# Debug toolbar for development
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

# Console email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# More permissive CORS for development
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:8080',
    'http://127.0.0.1:8080',
]

# Development-specific logging
LOGGING['loggers']['django']['level'] = 'DEBUG'
LOGGING['loggers']['apps']['level'] = 'DEBUG'

# Less strict cache timeout for development
CACHES['default']['TIMEOUT'] = 60  # 1 minute

# Celery eager execution in development (optional)
CELERY_TASK_ALWAYS_EAGER = env.bool('CELERY_EAGER', False)
CELERY_TASK_EAGER_PROPAGATES = True

# Development-specific security settings (relaxed)
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Static files handling in development
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'