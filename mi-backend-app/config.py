import os
import urllib.parse
from datetime import timedelta



BASE_URL_PRUEBAS = os.getenv("BASE_URL_PRUEBAS", "")
BASE_URL_PRODUCCION = os.getenv("BASE_URL_PRODUCCION", "")


SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")

SECRET_KEY_OFERTAS = os.getenv("SECRET_KEY_OFERTAS", "")

AWS_REGION = os.getenv("AWS_REGION", "")
S3_BUCKET = os.getenv("S3_BUCKET", "")  
USE_S3 = os.getenv("USE_S3", "true").lower() == "true"

ROOT_PREFIX_DROPBOX = os.getenv("ROOT_PREFIX_DROPBOX", "")
ROOT_PREFIX_S3 = os.getenv("ROOT_PREFIX_S3", "")

URL_LAMBDA_CONTACTO = os.getenv('URL_LAMBDA_CONTACTO', "")
URL_LAMBDA_OFERTAS = os.getenv('URL_LAMBDA_OFERTAS', "")
URL_LAMBDA_PROFORMAS = os.getenv('URL_LAMBDA_PROFORMAS', "")
URL_NGROK = os.getenv("URL_NGROK", "")
URL_LOCALHOST = os.getenv ("URL_LOCALHOST","")
URL_LAMBDA_ACTUALIZAR_CONTACTO = os.getenv('URL_LAMBDA_ACTUALIZAR_CONTACTO', "")
URL_API_GATEWAY_FORMCONTACTO = os.getenv('URL_API_GATEWAY_FORMCONTACTO', "")
URL_LAMBDA_OFERTAS_PUBLICAS = os.getenv('URL_LAMBDA_OFERTAS_PUBLICAS', "")


URL_NGROK_ACTUALIZAR_CONTACTO = f"{URL_LOCALHOST}/api/actualizar_contacto"
URL_NGROK_PROFORMAS = f"{URL_NGROK}/proforma"
URL_NGROK_OFERTAS =    f"{URL_NGROK}/oferta"
URL_NGROK_CONTACTO =  f"{URL_LOCALHOST}/api/contacto"

URL_ACTUALIZAR_CONTACTO = URL_NGROK_ACTUALIZAR_CONTACTO

EMAIL_USER = os.getenv ("EMAIL_USER","")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD","")

  
API_KEY = os.environ.get('API_KEY', "")
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', "")  # Cambiar esta clave en producción

HOST_DB = "AWS"  # Cambia a "AWS" para producción, "LOCAL" para desarrollo local
BD = "PRUEBAS" # PRUEBAS o PRODUCCION

SEND_EMAIL= False  # Enviar email al crear usuario nuevo    
SEND_WELLCOME_EMAIL = True  # Enviar email de bienvenida al crear usuario nuevo 
CONTACTO_OFERTA_LAMBDA = True
ENVIRONMENT_AL = "PRODUCCION" # PRODUCCION o SANDBOX


ENTORNO_COMPLETO = "DESARROLLO 5"# Puede ser PRODUCCION O DESARROLLO 1,2,3,...16

if ( ENTORNO_COMPLETO == "PRODUCCION") :
    HOST_DB = "AWS"
    BD = "PRODUCCION"
    SEND_EMAIL= True
    ENVIRONMENT_AL = "PRODUCCION"
    CONTACTO_OFERTA_LAMBDA = True

elif ( ENTORNO_COMPLETO == "DESARROLLO 1") :
    
    HOST_DB = "AWS"  # Cambia a "AWS" para producción, "LOCAL" para desarrollo local
    BD = "PRUEBAS"
    SEND_EMAIL= False
    ENVIRONMENT_AL = "SANDBOX"
    CONTACTO_OFERTA_LAMBDA = False

elif ( ENTORNO_COMPLETO == "DESARROLLO 2") :

    HOST_DB = "AWS"
    BD = "PRUEBAS"
    SEND_EMAIL= False
    ENVIRONMENT_AL = "SANDBOX"
    CONTACTO_OFERTA_LAMBDA = True
    

elif ( ENTORNO_COMPLETO == "DESARROLLO 3") :
    
    HOST_DB = "AWS"
    BD = "PRUEBAS"
    SEND_EMAIL= False
    ENVIRONMENT_AL = "PRODUCCION"
    CONTACTO_OFERTA_LAMBDA = False    

elif ( ENTORNO_COMPLETO == "DESARROLLO 4") :
    
    print("ENTORNO_COMPLETO seleccionado:", ENTORNO_COMPLETO)
    HOST_DB = "AWS"
    BD = "PRUEBAS"
    SEND_EMAIL= False
    ENVIRONMENT_AL = "PRODUCCION"
    CONTACTO_OFERTA_LAMBDA = True   

elif ( ENTORNO_COMPLETO == "DESARROLLO 5") :
    
    HOST_DB = "AWS"  # Cambia a "AWS" para producción, "LOCAL" para desarrollo local
    BD = "PRUEBAS"
    SEND_EMAIL= True
    ENVIRONMENT_AL = "SANDBOX"
    CONTACTO_OFERTA_LAMBDA = False

elif ( ENTORNO_COMPLETO == "DESARROLLO 6") :

    HOST_DB = "AWS"
    BD = "PRUEBAS"
    SEND_EMAIL= True
    ENVIRONMENT_AL = "SANDBOX"
    CONTACTO_OFERTA_LAMBDA = True

elif ( ENTORNO_COMPLETO == "DESARROLLO 7") :
    
    HOST_DB = "AWS"
    BD = "PRUEBAS"
    SEND_EMAIL= True
    ENVIRONMENT_AL = "PRODUCCION"
    CONTACTO_OFERTA_LAMBDA = False    
    
elif ( ENTORNO_COMPLETO == "DESARROLLO 8") :
    
    HOST_DB = "AWS"
    BD = "PRUEBAS"
    SEND_EMAIL= True
    ENVIRONMENT_AL = "PRODUCCION"
    CONTACTO_OFERTA_LAMBDA = True   

elif ( ENTORNO_COMPLETO == "DESARROLLO 9") :
    
    HOST_DB = "AWS"  # Cambia a "AWS" para producción, "LOCAL" para desarrollo local
    BD = "PRODUCCION"
    SEND_EMAIL= False
    ENVIRONMENT_AL = "SANDBOX"
    CONTACTO_OFERTA_LAMBDA = False

elif ( ENTORNO_COMPLETO == "DESARROLLO 10") :

    HOST_DB = "AWS"
    BD = "PRODUCCION"
    SEND_EMAIL= False
    ENVIRONMENT_AL = "SANDBOX"
    CONTACTO_OFERTA_LAMBDA = True

elif ( ENTORNO_COMPLETO == "DESARROLLO 11") :
    
    HOST_DB = "AWS"
    BD = "PRODUCCION"
    SEND_EMAIL= False
    ENVIRONMENT_AL = "PRODUCCION"
    CONTACTO_OFERTA_LAMBDA = False    

elif ( ENTORNO_COMPLETO == "DESARROLLO 12") :
    
    HOST_DB = "AWS"
    BD = "PRODUCCION"
    SEND_EMAIL= False
    ENVIRONMENT_AL = "PRODUCCION"
    CONTACTO_OFERTA_LAMBDA = True    

elif ( ENTORNO_COMPLETO == "DESARROLLO 13") :
    
    HOST_DB = "AWS"  # Cambia a "AWS" para producción, "LOCAL" para desarrollo local
    BD = "PRODUCCION"
    SEND_EMAIL= True
    ENVIRONMENT_AL = "SANDBOX"
    CONTACTO_OFERTA_LAMBDA = False

elif ( ENTORNO_COMPLETO == "DESARROLLO 14") :

    HOST_DB = "AWS"
    BD = "PRODUCCION"
    SEND_EMAIL= True
    ENVIRONMENT_AL = "SANDBOX"
    CONTACTO_OFERTA_LAMBDA = True

elif ( ENTORNO_COMPLETO == "DESARROLLO 15") :
    
    HOST_DB = "AWS"
    BD = "PRODUCCION"
    SEND_EMAIL= True
    ENVIRONMENT_AL = "PRODUCCION"
    CONTACTO_OFERTA_LAMBDA = False    

elif ( ENTORNO_COMPLETO == "DESARROLLO 16") :
    
    HOST_DB = "AWS"
    BD = "PRODUCCION"
    SEND_EMAIL= True
    ENVIRONMENT_AL = "PRODUCCION"
    CONTACTO_OFERTA_LAMBDA = True   


print("ENTORNO_COMPLETO seleccionado:", ENTORNO_COMPLETO)
print ("HOST_DB:", HOST_DB)
print ("BD:", BD)   
print ("SEND_EMAIL:", SEND_EMAIL)
print ("ENVIRONMENT_AL:", ENVIRONMENT_AL)
print ("CONTACTO_OFERTA_LAMBDA:", CONTACTO_OFERTA_LAMBDA)




if HOST_DB == "LOCAL"    :
    HOST = os.environ.get('DB_HOST', 'localhost')  # Host de la base de datos
else :
    HOST= "backend.c768segyuvlz.eu-north-1.rds.amazonaws.com"

if (BD== "PRUEBAS"):
    DATABASE = os.environ.get('DB_NAME', 'bc_pruebas')  # Nombre de la base de datos
else :
    DATABASE = os.environ.get('DB_NAME', 'bc')  # Nombre de la base de datos



if CONTACTO_OFERTA_LAMBDA : 
    
    URL_CONTACTO = URL_LAMBDA_CONTACTO
    URL_OFERTAS = URL_LAMBDA_OFERTAS
    URL_PROFORMAS = URL_LAMBDA_PROFORMAS
    URL_ACTUALIZAR_CONTACTO = URL_LAMBDA_ACTUALIZAR_CONTACTO
    URL_FORM_CONTACTO= URL_API_GATEWAY_FORMCONTACTO
    URL_OFERTAS_PUBLICAS = URL_LAMBDA_OFERTAS_PUBLICAS
   
else : 
    URL_CONTACTO = URL_NGROK_CONTACTO
    URL_OFERTAS = URL_NGROK_OFERTAS
    URL_ACTUALIZAR_CONTACTO = URL_NGROK_ACTUALIZAR_CONTACTO
    URL_PROFORMAS = URL_NGROK_PROFORMAS
    URL_FORM_CONTACTO = URL_LOCALHOST
    URL_OFERTAS_PUBLICAS = URL_LOCALHOST      

LANGUAGES = {
    'en': 'English',
    'es': 'Español',
    'fr': 'Français'
}


USERNAME = os.environ.get('DB_USERNAME', 'root')  # Nombre de usuario de la base de datos
PASSWORD = os.environ.get('DB_PASSWORD', urllib.parse.quote_plus("Planet01"))  

# Contraseña de la base de datos

PORT = '3306'
TOKEN_EXPIRATION_TIME = timedelta(hours=1)
#URL_SIN_DB = f"mysql+pymysql://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/"


# Cambia la siguiente línea para que apunte a MySQL
SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{USERNAME}:{PASSWORD}@{HOST}/{DATABASE}'

if ENVIRONMENT_AL == 'PRODUCCION' : ENVIRONMENT = 'Production' 
else :
    ENVIRONMENT = 'Sandbox2026'

#BASE_URL = BASE_URL_PRUEBAS
BASE_URL =  BASE_URL_PRODUCCION




