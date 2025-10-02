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
from models import ResetToken, User, Project



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
        sender_email = "soporte@planetpower.es"
        sender_password = "Ppt946682011"
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





      
    try:
        # Establecer la conexión con el servidor SMTP
        with smtplib.SMTP("smtp.planetpower.es", 587) as server:
            server.starttls()  # Activar TLS
            server.login(sender_email, sender_password)
            server.send_message(message)
            return ("Instruciones enviadas al coreo con éxito.", 1)
    except Exception as e:
        return (f"Error al enviar el correo: {e}",2)

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
