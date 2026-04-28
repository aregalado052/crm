import smtplib
import pycurl
from flask import jsonify

from io import BytesIO
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import secrets
import random
import string
import json
import boto3
from sqlalchemy import exists
from sqlalchemy.exc import OperationalError
from app_init import db
import base64
import urllib.parse
import io
import smtplib, ssl, socket


from models import ResetToken, User, Project
from config import (SENDER_EMAIL, SENDER_PASSWORD, ENTORNO_COMPLETO)

URL_LOCAL = "http://127.0.0.1:8000"
URL_WWW = "https://crmplanetpower.es"




if ENTORNO_COMPLETO == "PRODUCCION":
    URL = URL_WWW
else :
    URL = URL_LOCAL


client = boto3.client('scheduler', region_name='eu-north-1')
TOKEN_EXPIRATION_TIME = timedelta(hours=1)

def generar_contrasena(longitud=9):

    print (__name__)
    if __name__ != "__main__":

        # Definir el conjunto de caracteres a utilizar
        caracteres = string.ascii_letters + string.digits
        # Generar una contraseña aleatoria
        contrasena = ''.join(random.choice(caracteres) for _ in range(longitud))
        print("Contraseña generada:", contrasena)
        return contrasena
    return None
    # Ejemplo de uso


GENERIC_EMAIL_DOMAINS = {
    "gmail.com",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "msn.com",
    "yahoo.com",
    "icloud.com",
    "me.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
    "gmx.com",
    "gmx.es",
    "mail.com",
    "yandex.com",
    "yandex.ru",
    "zoho.com"
}


def split_email(email: str):
    email = (email or "").strip().lower()
    if "@" not in email:
        return "", ""
    local, domain = email.rsplit("@", 1)
    return local.strip(), domain.strip()


def lead_exists_for_prospect(cur, email: str) -> bool:
    local, domain = split_email(email)
    if not domain:
        return False

    if domain in GENERIC_EMAIL_DOMAINS:
        cur.execute("""
            SELECT 1
            FROM lead_forms lf
            WHERE LOWER(TRIM(lf.email)) = %s
            LIMIT 1
        """, (f"{local}@{domain}",))
    else:
        cur.execute("""
            SELECT 1
            FROM lead_forms lf
            WHERE LOWER(TRIM(lf.email)) LIKE %s
            LIMIT 1
        """, (f"%@{domain}",))

    return cur.fetchone() is not None


def validate_reset_token(token):
    if __name__ != "__main__":

    # Obtener datos del token de la base de datos (puedes ajustar esto según tu implementación)
        token_data = get_token_data(token)
        if not token_data:
            return False  # Si no hay datos para el token, es inválido

        user_id = token_data.user_id
        expires_at = token_data.expires_at

        print("User ID:", user_id)
        print("Token expira en:", expires_at)
        print("Ahora:", datetime.now())
        # Verificar si el token ha expirado
        if datetime.now() > expires_at:

            print("El token ha expirado.")
            # Eliminar el token de la base de datos

            try :
                db.session.delete(token_data)
                db.session.commit()
                print("El token ha expirado y ha sido eliminado.")
            except OperationalError as e:
                db.session.rollback()
                print(f"Error operacional: {e}")
            return False  # El token es inválido
        return True  # El token es válido y se ha utilizado
    return False



def create_reset_token(user_id):
    if __name__ != "__main__":
    # Paso 1: Eliminar tokens existentes del usuario
        try :
            db.session.query(ResetToken).filter(ResetToken.user_id == user_id).delete()
            db.session.commit()   
        except OperationalError as e:
            db.session.rollback()
            print(f"Error operacional: {e}")

    # Genera un token seguro
        token = secrets.token_urlsafe(16)  # Puedes modificar el tamaño según sea necesario
        expires_at = datetime.now() + TOKEN_EXPIRATION_TIME  # El token expira en 1 hora
        created_at = datetime.now()
        # Crea un nuevo objeto de ResetToken
        new_token = ResetToken(user_id=user_id, token=token,
                               created_at= created_at,expires_at=expires_at)
        # Agrega el nuevo token a la sesión y confirma los cambios
        try :
            db.session.add(new_token)
            db.session.commit()
        except OperationalError as e:
            db.session.rollback()
            print(f"Error operacional: {e}")
        return token  # Devuelve el token, si necesitas mostrarlo o registrarlo
    


def get_user_id_from_token(token):
    
    if __name__ != "__main__":

        
        try :
            # Buscar el registro del token en la base de datos
            token_data = ResetToken.query.filter_by(token=token).first()

        except OperationalError as e:
            db.session.rollback()
            print(f"Error operacional: {e}")





        if token_data:
            return token_data.user_id  # Retorna el ID del usuario asociado al token
        else:
            return None  # Retorna None si el token no es válido o no se encuentra



def get_token_data(token):
    
    if __name__ != "__main__":

       
        try :
            # Buscar el registro del token en la base de datos
            token_data = ResetToken.query.filter_by(token=token).first()

        except OperationalError as e:
            db.session.rollback()
            print(f"Error operacional: {e}")

        if token_data:
            return token_data  # Retorna el token_data completo
        
        else:
            return None  # Retorna None si no se encuentra el token



def update_user_password(token, hashed_password):
    
    if __name__ != "__main__":

        # Buscar el registro del token en la base de datos para obtener el user_id
        try :
            # Buscar el registro del token en la base de datos
            token_data = ResetToken.query.filter_by(token=token).first()

        except OperationalError as e:
            db.session.rollback()
            print(f"Error operacional: {e}")

        if token_data:
            user_id = token_data.user_id  # Obtener el user_id del token

           

            try :
                # Buscar el usuario por su ID
                user = User.query.get(user_id)

            except OperationalError as e:
                db.session.rollback()
                print(f"Error operacional: {e}")
                return False

            if user:
                # Actualizar la contraseña del usuario
                user.password = hashed_password

                 # 🔥Eliminar el token de la base de datos

                try :
                    db.session.delete(token_data)

                    # Guardar los cambios en la base de datos
                    db.session.commit()

                except OperationalError as e:
                    db.session.rollback()
                    print(f"Error operacional: {e}")
                    return False


                return True  # Retorna True si la actualización fue exitosa
            else:
                print("2Token no encontrado en la base de datos.")
                return False  # Retorna False si no se encontró el usuario
            
        else:
            print("3Token no encontrado en la base de datos.")
            return False  # Retorna False si no se encontró el token
    
    return False  # Retorna False si no se encontró el token



def send_new_password(email, reset_token):
    
    if __name__ != "__main__":
        # Configuración del correo
        smtp_server = "smtp.office365.com"
        smtp_port = 587
       
        
        
       
        sender_email = SENDER_EMAIL
        sender_password = SENDER_PASSWORD
        recipient_email = email
        
        # Crear el mensaje
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = recipient_email
        message["Subject"] = "Solicitud de Nueva Contraseña"

        


        html_content = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Times, sans-serif; /* Tipo de letra */
                    font-size: 20px;
                    color: #333;
                }}
                .signature {{
                    margin-top: 20px;
                    
                    color: #555;
                }}
            </style>
        </head>
       <body>
        <p>Estimado/a usuario:</p>
        <p>Hemos recibido una solicitud para restablecer tu contraseña. Si deseas restablecer tu contraseña, haz clic en el siguiente enlace:</p>
        <p><a href="{URL}/reset_password?token={reset_token}">Restablecer Contraseña</a></p>
        <p>Si no solicitaste este cambio, puedes ignorar este correo.</p>
        <p>Atentamente,</p>
        <p>El equipo de soporte</p>
    </body>
        </html>
        """

    # Adjuntar el contenido HTML al mensaje
    message.attach(MIMEText(html_content, "html"))

    # Cargar el contenido de la firma desde el archivo HTML
    with open("static/PPT email plantilla 2023 Angel P1.html", "r") as file:
        signature = file.read()

    # Adjuntar la firma al mensaje
    message.attach(MIMEText(signature, "html"))

    socket.setdefaulttimeout(20)
    print("sender", sender_email)
    print("smtp", smtp_server, smtp_port)

    

    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as server:
            server.set_debuglevel(1)   # <-- IMPORTANTE: ver conversación SMTP

            print("STEP 1: ehlo")
            server.ehlo()

            print("STEP 2: starttls")
            server.starttls(context=ssl.create_default_context())

            print("STEP 3: ehlo post-tls")
            server.ehlo()

            SMTP_LOGIN = "ofertas@planetpower.es"
            print("STEP 4: login", SMTP_LOGIN)
            server.login(SMTP_LOGIN, sender_password)

            print("STEP 5: send_message")
            server.send_message(message)

        print("✅ Correo enviado correctamente.")
        return ("Instrucciones enviadas al correo con éxito.", 1)

    except smtplib.SMTPAuthenticationError as e:
        print("❌ AUTH ERROR:", e)
        return (f"Error autenticación SMTP: {e}", 0)

    except smtplib.SMTPException as e:
        print("❌ SMTP ERROR:", e)
        return (f"Error SMTP: {e}", 0)

    except (socket.timeout, TimeoutError) as e:
        print("❌ TIMEOUT:", e)
        return (f"Timeout conectando/enviando: {e}", 0)

    except Exception as e:
        print("❌ UNEXPECTED:", e)
        return (f"Error inesperado: {e}", 0)






      
    
# Ejemplo de uso

def create_scheduler_by_project(pid,uid):
    
    # Verificar en la BD si ya tiene un scheduler
    proyecto = Project.query.filter_by(pid=pid).first()

    if not proyecto:
        print(f"No se encontró un proyecto con pid={pid}")
        return None

    if proyecto.scheduler_name and proyecto.scheduler_arn:
        print(f"Scheduler ya existe para el club {pid}: {proyecto.scheduler_name}")
        return proyecto

    # Crear scheduler con boto3
    client = boto3.client('scheduler', region_name='eu-north-1')
    

    scheduler_name = f"scheduler-club-{pid}"
    lambda_arn = "arn:aws:lambda:eu-north-1:307946636882:function:playtomic-hytronik-pruebas-oficina"
    role_arn = "arn:aws:iam::307946636882:role/service-role/Rol_pruebas"
    print("UID",uid)
    print("PID", pid)
    response = client.create_schedule(
        Name=scheduler_name,
        ScheduleExpression="rate(2 minutes)",
        FlexibleTimeWindow={"Mode": "OFF"},
        

        Target={
            "Arn": lambda_arn,
            "RoleArn": role_arn,
            "Input": json.dumps({"pid": pid,
                                 "uid": uid,
                                 })
        }
    )

   

   

    try :
        Project.query.filter_by(pid=pid).update({
            'scheduler_name': scheduler_name,
            'scheduler_arn': response['ScheduleArn']
        })
      
        db.session.commit()

                   

    except OperationalError as e:
        db.session.rollback()
        print(f"Error operacional: {e}")



    print(f"Scheduler creado para club {pid}: {scheduler_name}")
    return response
    

def get_dropbox_access_token():


    # === CONFIGURA ESTOS DATOS ===
    APP_KEY = 'gcwcrtb1njdp6zm'
    APP_SECRET = '7r5f0uvnmfbhsz1'
    REFRESH_TOKEN = 'sd2BXGVRNBUAAAAAAAAAASk4qlUGFPw6Z5NObZq4oEY114DUQFCxs9jkV-acFft_'

    # Codifica app_key:app_secret en base64
    user_pass = f"{APP_KEY}:{APP_SECRET}"
    b64_auth = base64.b64encode(user_pass.encode()).decode()

    # Cuerpo de la solicitud
    postfields = {
        'grant_type': 'refresh_token',
        'refresh_token': REFRESH_TOKEN
    }
    post_data = urllib.parse.urlencode(postfields)

    # Buffer para la respuesta
    response_buffer = io.BytesIO()

    # Configura pycurl
    c = pycurl.Curl()
    c.setopt(c.URL, 'https://api.dropboxapi.com/oauth2/token') 
    c.setopt(c.POST, 1)
    c.setopt(c.POSTFIELDS, post_data)
    c.setopt(c.WRITEDATA, response_buffer)
    c.setopt(c.HTTPHEADER, [
        f'Authorization: Basic {b64_auth}',
        'Content-Type: application/x-www-form-urlencoded'
    ])

    # Ejecuta y muestra resultado
    try:
        c.perform()
        c.close()
        response = response_buffer.getvalue().decode('utf-8')
        data = json.loads(response)
        print("✅ Nuevo access_token:")
        print(data)
        return data.get('access_token')
        
    except pycurl.error as e:
        print("❌ Error al refrescar token:", e)
        return None
