"""
Django settings for taxiasiste project.
"""

from datetime import timedelta
from pathlib import Path

from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)

# Clave "TaxiAsiste - Backend" (Geocoding API + Directions API) -- ver taxiasiste/views.py
GOOGLE_MAPS_API_KEY = config('GOOGLE_MAPS_API_KEY', default='')

# Correo saliente (bienvenida + recuperacion de clave) via Gmail -- ver
# taxiasiste/usuarios/emails.py. EMAIL_HOST_PASSWORD es una "clave de app"
# de Gmail (16 caracteres), no la clave normal de la cuenta.
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='TaxiAsiste <noreply@taxiasiste.cl>')

# Link de descarga directa del APK (distribucion temporal antes de Play Store).
APK_DOWNLOAD_URL = config('APK_DOWNLOAD_URL', default='')

# Direccion del panel web, para el correo de bienvenida del personal administrativo.
PANEL_WEB_URL = config('PANEL_WEB_URL', default='http://45.236.130.233')

# Fila virtual (ver taxiasiste/moviles/fila_logic.py y el comando retirar_inactivos_fila).
# Un movil EN_ESPERA que lleva mas de estos minutos sin reportar ubicacion sale de la fila.
FILA_INACTIVIDAD_MIN = config('FILA_INACTIVIDAD_MIN', default=5, cast=int)
# Segundos que tiene un conductor llamado para pulsar "Voy" antes de pasar al final de la fila.
FILA_LLAMADO_SEGUNDOS = config('FILA_LLAMADO_SEGUNDOS', default=180, cast=int)

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_spectacular',
    'taxiasiste.usuarios',
    'taxiasiste.socios',
    'taxiasiste.solicitudes',
    'taxiasiste.moviles',
    'taxiasiste.reportes',
    'taxiasiste.agenda',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'taxiasiste.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'taxiasiste.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('POSTGRES_DB', default='taxiasiste_dev'),
        'USER': config('POSTGRES_USER', default='postgres'),
        'PASSWORD': config('POSTGRES_PASSWORD'),
        'HOST': config('POSTGRES_HOST', default='localhost'),
        'PORT': config('POSTGRES_PORT', default='5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'taxiasiste.authentication.UsuarioJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    # ROTATE_REFRESH_TOKENS+BLACKLIST_AFTER_ROTATION se probaron y se
    # DESCARTARON: con varios pollers concurrentes compartiendo el mismo
    # refresh token (fila, solicitudes, notificaciones, ubicacion en
    # background), si dos de ellos refrescan casi al mismo tiempo -- lo mas
    # probable justo cuando el access token de 8h vence -- el segundo usa un
    # refresh que el primero ya dejo en blacklist, y ese poller queda
    # muerto hasta el proximo login manual. Esto se vio en produccion: el
    # GPS del conductor dejaba de actualizarse "despues de un rato" tanto en
    # el mapa web como en su propio celular, y solo un logout+login lo
    # arreglaba. El refresh token ahora es reutilizable durante toda su
    # vida (1 dia) como antes -- el blacklist en si sigue activo para el
    # logout explicito (POST /api/logout/), que es una accion unica y
    # deliberada, no un hot path con carreras.
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'TaxiAsiste API',
    'VERSION': '1.0.0',
    'SCHEMA_PATH_PREFIX': '/api/',
    'SECURITY': [{'jwtAuth': []}],
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'jwtAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
        }
    },
}

CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:5173',
]

# --- Reservas (viajes programados) ---------------------------------------
# Todo en un solo lugar para ajustar las reglas sin tocar codigo.
RESERVA_MARGEN_MIN = 15               # colchon antes y despues de cada reserva
RESERVA_MAX_ACTIVAS = 3               # reservas activas (ASIGNADA/EN_CAMINO) por conductor
RESERVA_HORIZONTE_HORAS = 24          # hasta cuantas horas adelante se puede reservar
RESERVA_ANTICIPACION_MIN = 30         # minimo de anticipacion al crear una reserva
RESERVA_SOLTAR_SIN_PENALIZACION_H = 2 # soltar con menos de esto = "soltada tarde" (incumplimiento)
RESERVA_EN_CAMINO_DESDE_MIN = 60           # "Voy en camino" se habilita desde 60 min antes de la recogida
RESERVA_ALERTA_SIN_CONDUCTOR_MIN = 30      # alerta a Central si nadie la tomo a 30 min de la hora maxima de salida
RESERVA_TOLERANCIA_CONFIRMACION_MIN = 5    # alerta si el conductor no confirmo 5 min despues de su hora maxima de salida
RESERVA_ESPERA_PASAJERO_MIN = 10           # el conductor espera 10 min antes de cerrar "pasajero no se presento"
PASAJERO_MAX_INCUMPLIMIENTOS = 3           # a la 3a vez no puede pedir moviles a domicilio
