# app_init.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from config import JWT_SECRET_KEY, LANGUAGES, SQLALCHEMY_DATABASE_URI,TOKEN_EXPIRATION_TIME




bcrypt = Bcrypt()
db = SQLAlchemy()
application = Flask(__name__)

CORS(
    application,
    origins=[
        "http://ledpadeliot.com",
        "https://ledpadeliot.com",
        "https://www.ledpadeliot.com",
    ],
    supports_credentials=True,                # si usas cookies/sesión
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    expose_headers=["Content-Length", "Content-Type"],
)

def create_app():
    """
    Crea y configura una instancia de la aplicación Flask.

    Esta función inicializa la aplicación con múltiples configuraciones,
    incluyendo conexión a base de datos, claves JWT, configuración de cookies,
    localización (i18n) y CORS. También inicializa las extensiones utilizadas 
    como SQLAlchemy, Bcrypt, Babel y JWTManager.

    Configuraciones clave:
    - SQLAlchemy: URI de conexión y seguimiento desactivado.
    - JWT: manejo de tokens en cookies, claves secretas y expiración.
    - CORS: habilitado para orígenes locales con credenciales.
    - Babel: soporte multilenguaje y directorio de traducciones.

    Returns:
        Flask: Una instancia de la aplicación Flask completamente configurada.
    """
    application.config.from_pyfile('config.py')
    application.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    application.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    application.config['JWT_SECRET_KEY'] = JWT_SECRET_KEY  # Cambiaremos esta clave en producción
    application.config['JWT_TOKEN_LOCATION'] = ['cookies']
    application.config['JWT_ACCESS_COOKIE_PATH'] = '/'  # válida en toda la app
    application.config['JWT_COOKIE_CSRF_PROTECT'] = False  # Puedes activarlo para  más seguridad
    application.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token_cookie'
    application.config["PROPAGATE_EXCEPTIONS"] = True
    application.config['JWT_ACCESS_TOKEN_EXPIRES'] = TOKEN_EXPIRATION_TIME
    application.secret_key = JWT_SECRET_KEY
    application.config["JWT_COOKIE_SECURE"] = True
    application.config["JWT_COOKIE_SAMESITE"] = "Lax"
   # Configuración de Babel
    application.config['LANGUAGES'] = LANGUAGES
    application.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations'
    application.config['BABEL_DEFAULT_LOCALE'] = 'es'
    application.config['BABEL_SUPPORTED_LOCALES'] = ['es', 'en', 'fr']
    CORS(application, supports_credentials=True, origins=["http://localhost:8000",
                                                          "http://127.0.0.1:8000"])
    jwt = JWTManager(application)
    db.init_app(application)
    bcrypt.init_app(application)
    jwt.init_app(application)
    return application
