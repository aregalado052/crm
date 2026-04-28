import json
import socket
from botocore.exceptions import ClientError, BotoCoreError
import html

import urllib.parse
import pymysql
import boto3

import os
import math
import dropbox
import smtplib
from email.message import EmailMessage
import os
import uuid
import pycurl
import io
import base64
import urllib.parse
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from types import SimpleNamespace
from bs4 import BeautifulSoup
from itsdangerous import URLSafeTimedSerializer
from urllib.parse import urlencode






import pycurl
from io import BytesIO







AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
DROPBOX_SECRET_NAME = os.getenv("DROPBOX_SECRET_NAME", "")
S3_BUCKET = os.getenv("S3_BUCKET", "")
USE_S3 = os.getenv("USE_S3", "").lower() == "true"
ROOT_PREFIX_S3 = os.getenv("ROOT_PREFIX_S3", "")
SECRET_KEY_PROFORMAS = os.getenv("SECRET_KEY_PROFORMAS", "")
MYSQL_DB_SECRET_NAME = os.getenv("MYSQL_DB_SECRET_NAME", "")
SECRET_KEY_OFERTAS= os.getenv("SECRET_KEY_OFERTAS", "")




s3 = boto3.client("s3", region_name=AWS_REGION)


import json
import base64

def _get_route(event):
    # HTTP API v2
    rc = event.get("requestContext", {})
    http = rc.get("http")
    if isinstance(http, dict):
        method = (http.get("method") or "").upper()
        path = http.get("path") or ""
        return method, path

    # REST API v1
    method = (event.get("httpMethod") or "").upper()
    path = event.get("path") or ""
    return method, path

def _parse_body_any(event):
    """
    Devuelve: (payload_dict, pdf_bytes)
    - Si body es JSON -> payload_dict
    - Si body es binario (PDF) -> pdf_bytes
    """
    body = event.get("body")
    if not body:
        return {}, b""

    if event.get("isBase64Encoded"):
        raw = base64.b64decode(body)  # bytes (puede ser JSON o PDF)

        # intenta interpretarlo como JSON UTF-8
        try:
            text = raw.decode("utf-8")
            return json.loads(text), b""
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}, raw  # es binario (PDF)

    # no base64 => texto
    try:
        return json.loads(body), b""
    except json.JSONDecodeError:
        return {}, b""

def _json_response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "OPTIONS,POST",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }


def get_recipient_config(tracking_id, connection):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    email_user AS EMAIL_USER,
                    email_password AS EMAIL_PASSWORD,
                    url_contacto AS URL_CONTACTO,
                    url_ofertas AS URL_OFERTAS,
                    url_proformas AS URL_PROFORMAS,
                    url_actualizar_contacto AS URL_ACTUALIZAR_CONTACTO,
                    url_form_contacto AS URL_FORM_CONTACTO,
                    api_key AS API_KEY,
                    environment AS ENVIRONMENT,
                    send_email AS SEND_EMAIL,
                    send_wellcome_email AS SEND_WELLCOME_EMAIL,
                    tracking_id
                FROM campaign_recipients
                WHERE tracking_id = %s
            """, (tracking_id,))

            row = cursor.fetchone()

            if not row:
                print("[WARN] No se encontró configuración")
                return None

            # 🔐 Convertir binarios a string (si aplica)
            if row.get("EMAIL_PASSWORD"):
                row["EMAIL_PASSWORD"] = row["EMAIL_PASSWORD"].decode("utf-8", errors="ignore")

            if row.get("API_KEY"):
                row["API_KEY"] = row["API_KEY"].decode("utf-8", errors="ignore")

            # ✅ Convertir booleanos
            row["SEND_EMAIL"] = bool(row.get("SEND_EMAIL"))
            row["SEND_WELLCOME_EMAIL"] = bool(row.get("SEND_WELLCOME_EMAIL"))

            return row
    except Exception as e:
        print(f"[ERROR] Error al obtener configuración: {e}")
        return None


def oferta_core(payload: dict, pdf_data: bytes | None = None):
    print("oferta_core - payload:", payload)
    try:

        session_id = (payload.get("session_id") or "").strip()
        total_excl_iva_raw = str(payload.get("total_excl_iva") or "").strip()
        bd = (payload.get("BD") or "").strip()

        if not session_id:
            return {"ok": False, "error": "Falta session_id"}, 400

        # si vino por JSON como pdf_base64, decodifica aquí
        if (not pdf_data) and payload.get("pdf_base64"):
            pdf_data = base64.b64decode(payload["pdf_base64"])

        if not pdf_data:
            return {"ok": False, "error": "No se ha recibido PDF"}, 400
            
        print(f"📥 Solicitud recibida (Lambda)")
        print(f"📄 Tamaño del PDF: {len(pdf_data)} bytes")
        print(f"🆔 Session ID: {session_id}")
        print(f"💶 total_excl_iva: {total_excl_iva_raw}")
        print(f"💶 BD: {bd}")
        global BD
        BD= bd if bd in ["PRODUCCION", "PRUEBAS"] else "PRODUCCION"
        print(f"💶 BD (interna): {BD}")

        DROPBOX_TOKEN= get_dropbox_access_token()
        dbx = dropbox.Dropbox(DROPBOX_TOKEN)
        account_info = dbx.users_get_current_account()
        print(f"Conectado a Dropbox como: {account_info.name.display_name}")



        creds = get_db_credentials()

        dbname = "bc_pruebas" if (BD == "PRUEBAS") else creds["dbname"]

        print ("BD", BD)  
        
        #print(f"Credenciales obtenidas: {creds}")
        print(f"Conectando a la base de datos con host: {creds['host']}, usuario: {creds['username']}, base de datos: {dbname}")
        

        connection = pymysql.connect(
            host=creds["host"],
            user=creds["username"],
            password=creds["password"],
            database=dbname,
            port=int(creds.get("port", 3306)),
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )
        

        print ("Conexión a la base de datos establecida correctamente.")
        

        session_data = get_session_data(session_id, connection=connection)

        first_word = session_data['name'].split()[0] if session_data['name'] else "Cliente"
        print(f"ID de sesión: {session_id}")
        print(f"Datos de sesión: {session_data}")
        

        if (session_data['idioma'] == "Español") or (session_data['idioma'] == "Esp"):
            document_no = f"OFERTA {first_word} {session_data['SalesHeaderNumber']}.pdf"
        else:
            document_no = f"SALES QUOTE {first_word} {session_data['SalesHeaderNumber']}.pdf"

        print(f"Nombre del documento: {document_no}")

        update_pdf_bd(session_id, total_excl_iva_raw, document_no, pdf_data,connection)
        
        dropbox_path = f"/2024 PPT - Ofertas/{document_no}"
        

        # Guardar localmente (opcional)
        #with open(f'{document_no}.pdf', 'wb') as f:
        #    f.write(pdf_data)

        # Subir a Dropbox
        dbx = dropbox.Dropbox(DROPBOX_TOKEN)
        dbx.files_upload(pdf_data, dropbox_path, mode=dropbox.files.WriteMode.overwrite)

        




        print(f"✅ PDF subido a Dropbox en: {dropbox_path}")

        url_proformas=session_data['url_proformas'] 
        url = session_data['url_form_contacto']
        secret_key= SECRET_KEY_PROFORMAS    

        send_email_with_pdf(pdf_data, document_no, session_id,url,secret_key, session_data['SalesHeaderNumber'],connection)
        print(f"✅ Correo enviado con el PDF adjunto: {document_no}")

        SEND_WELLCOME_EMAIL = True if session_data['send_wellcome_email'] else False
        

        if SEND_WELLCOME_EMAIL:
            send_wellcome_email(session_id, connection)
            #send_prueba_email(session_id)
            print(f"✅ Correo de bienvenida enviado ")

        print("✅ PDF guardado")
        connection.close()
        return {"ok": True, "message": "OK"}, 200


   

    except Exception as e:
   
   
        return {"ok": False, "error": "Error interno", "detail": str(e)}, 500
       

def marcar_prospecto_como_lead(entity_id, campaign_id, tracking_id, connection):
    if not entity_id:
        return 0

    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE prospects_IA
            SET lead_status = 'lead',
                lead_converted_at = NOW(),
                lead_converted_campaign_id = %s,
                lead_converted_tracking_id = %s
            WHERE id = %s
        """, (
            campaign_id,
            tracking_id,
            entity_id
        ))

        return cursor.rowcount






def oferta_prospect_submit_core(payload: dict):
    print("oferta_prospect_submit_core - payload:", payload)

    token = payload.get("token", "")
    tracking_id = payload.get("tracking_id", "")

    print(f"Token recibido: {token}")
    print(f"Tracking ID recibido: {tracking_id}")

    if not token:
        return response(400, {
            "ok": False,
            "code": "MISSING_TOKEN",
            "message": "Falta el token."
        })

    serializer = URLSafeTimedSerializer(
        SECRET_KEY_OFERTAS,
        salt="oferta-link-v1"
    )

    token_data = serializer.loads(token, max_age=60 * 60 * 24 * 7)
    print("[VAL] Datos decodificados del token:", token_data)

    BD = token_data.get("bd", "PRODUCCION")

    creds = get_db_credentials()
    dbname = "bc_pruebas" if BD == "PRUEBAS" else creds["dbname"]

    connection = pymysql.connect(
        host=creds["host"],
        user=creds["username"],
        password=creds["password"],
        database=dbname,
        port=int(creds.get("port", 3306)),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )

    try:
        recipient = get_campaign_recipient_data(tracking_id, connection)
        conf = get_recipient_config(tracking_id=tracking_id, connection=connection)
    finally:
        connection.close()

    if not recipient:
        return response(404, {"ok": False, "message": "Recipient no encontrado"})

    if not conf:
        return response(404, {"ok": False, "message": "Configuración no encontrada"})

    pistas_perimetrales = float(payload.get("pistas_perimetrales") or 0)
    pistas_laterales = float(payload.get("pistas_laterales") or 0)

    api_payload = {
        "name": payload.get("name"),
        "email": recipient.get("email"),
        "idioma": payload.get("idioma"),
        "pais": payload.get("pais"),
        "pistas_perimetrales": pistas_perimetrales,
        "pistas_laterales": pistas_laterales,
        "mailorigen": "web@planetpower.es",
        "origen": "oferta_email",
        "BD": BD,
        "EMAIL_USER": conf.get("EMAIL_USER", ""),
        "EMAIL_PASSWORD": conf.get("EMAIL_PASSWORD", ""),
        "URL_CONTACTO": conf.get("URL_CONTACTO", ""),
        "URL_OFERTAS": conf.get("URL_OFERTAS", ""),
        "URL_ACTUALIZAR_CONTACTO": conf.get("URL_ACTUALIZAR_CONTACTO", ""),
        "URL_FORM_CONTACTO": conf.get("URL_FORM_CONTACTO", ""),
        "URL_PROFORMAS": conf.get("URL_PROFORMAS", ""),
        "ENVIRONMENT": conf.get("ENVIRONMENT", ""),
        "SEND_EMAIL": bool(conf.get("SEND_EMAIL")),
        "SEND_WELLCOME_EMAIL": bool(conf.get("SEND_WELLCOME_EMAIL")),
    }

    print("📤 Enviando a API:", api_payload)

    url_contacto = conf.get("URL_CONTACTO")
    api_key = conf.get("API_KEY")

    if isinstance(api_key, bytes):
        api_key = api_key.decode("utf-8", errors="ignore")

    

    if not url_contacto:
        return response(500, {"ok": False, "message": "URL_CONTACTO no definida"})

    
    

    try:
        buffer = BytesIO()
        c = pycurl.Curl()

        c.setopt(pycurl.URL, url_contacto)
        c.setopt(pycurl.POST, 1)
        c.setopt(pycurl.POSTFIELDS, json.dumps(api_payload))
        c.setopt(pycurl.HTTPHEADER, [
            "Content-Type: application/json",
            f"x-api-key: {api_key or ''}"
        ])
        c.setopt(pycurl.TIMEOUT, 60)
        c.setopt(pycurl.WRITEDATA, buffer)

        c.perform()

        status_code = c.getinfo(pycurl.RESPONSE_CODE)
        response_text = buffer.getvalue().decode("utf-8")

        c.close()

        print("📥 Respuesta API:", status_code, response_text)


        

        if status_code >= 400:

            return response(status_code, { "ok": False,
                "message": "Error llamando a URL_CONTACTO",
                "status_code": status_code,
                "response": response_text})

        # Si la oferta se creó bien, marcamos el prospecto como lead
        if recipient and recipient.get("entity_kind") == "prospect":
            connection = pymysql.connect(
                host=creds["host"],
                user=creds["username"],
                password=creds["password"],
                database=dbname,
                port=int(creds.get("port", 3306)),
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
            )

            try:
                marcar_prospecto_como_lead(
                    entity_id=recipient.get("entity_id"),
                    campaign_id=recipient.get("campaign_id"),
                    tracking_id=recipient.get("tracking_id"),
                    connection=connection
                )
            finally:
                connection.close()   
                
            
        return response(200, {"ok": True, "response": response_text})



    except pycurl.error as e:
        print("❌ Error pycurl:", str(e))
        return response(500, {"ok": False, "message": str(e)})


def proforma_core(payload: dict, pdf_data: bytes | None = None):
      
    print("Profroma_core - payload:", payload)
    try:
        session_id = (payload.get("session_id") or "").strip()
       
        bd = (payload.get("BD") or "").strip()

        if not session_id:
            return {"ok": False, "error": "Falta session_id"}, 400

        # si vino por JSON como pdf_base64, decodifica aquí
        if (not pdf_data) and payload.get("pdf_base64"):
            pdf_data = base64.b64decode(payload["pdf_base64"])

        if not pdf_data:
            return {"ok": False, "error": "No se ha recibido PDF"}, 400

        
        print(f"📥 Solicitud recibida (Lambda)")
        print(f"📄 Tamaño del PDF: {len(pdf_data)} bytes")
        print(f"🆔 Session ID: {session_id}")
        
        print(f"💶 BD: {bd}")
        global BD
        BD= bd if bd in ["PRODUCCION", "PRUEBAS"] else "PRODUCCION"
        print(f"💶 BD (interna): {BD}")

        DROPBOX_TOKEN= get_dropbox_access_token()
        dbx = dropbox.Dropbox(DROPBOX_TOKEN)
        account_info = dbx.users_get_current_account()
        print(f"Conectado a Dropbox como: {account_info.name.display_name}")

        

        creds = get_db_credentials()

        dbname = "bc_pruebas" if (BD == "PRUEBAS") else creds["dbname"]

        print ("BD", BD)  
        
        #print(f"Credenciales obtenidas: {creds}")
        print(f"Conectando a la base de datos con hosten Lambda: {creds['host']}, usuario: {creds['username']}, base de datos: {dbname}")
        

        connection = pymysql.connect(
            host=creds["host"],
            user=creds["username"],
            password=creds["password"],
            database=dbname,
            port=int(creds.get("port", 3306)),
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )
        

        print ("Conexión a la base de datos establecida correctamente.", connection)


        print("Antes de get_session_data")
        session_data = get_session_data(session_id, connection)
        print("Después de get_session_data:", session_data)

        print("Antes de calcular first_word")
        first_word = session_data['name'].split()[0] if session_data['name'] else "Cliente"
        print("Después de calcular first_word:", first_word)
                

        
        print(f"ID de sesión: {session_id}")
        print(f"Datos de sesión: {session_data}")

        print(f"Name de sesión: {session_data['name']}")
        

        if (session_data['idioma'] == "Español") or (session_data['idioma'] == "Esp"):
            document_no = f"FACTURA PROFORMA {first_word} {session_data['SalesHeaderNumber']}.pdf"
        else:
            document_no = f"PROFORMA INVOICE {first_word} {session_data['SalesHeaderNumber']}.pdf"

        print(f"Nombre del documento: {document_no}")

        
        
        dropbox_path = f"/2024 PPT - Ofertas/{document_no}"
        

        # Guardar localmente (opcional)
        #with open(f'{document_no}.pdf', 'wb') as f:
        #    f.write(pdf_data)

        # Subir a Dropbox
        dbx = dropbox.Dropbox(DROPBOX_TOKEN)
        dbx.files_upload(pdf_data, dropbox_path, mode=dropbox.files.WriteMode.overwrite)

        print(f"✅ PDF subido a Dropbox en: {dropbox_path}")

        send_email_with_proforma_pdf(pdf_data, document_no, session_id,connection)
        print(f"✅ Correo enviado con el PDF adjunto: {document_no}")

        connection.close()
        return {"ok": True, "message": "OK"}, 200


   

    except Exception as e:
        print("ERROR:", str(e))
        print(traceback.format_exc())
        return {"ok": False, "error": "Error interno", "detail": str(e)}, 500



def build_payload(data: dict) -> dict:
    return {
        "token": (data.get("token") or "").strip(),
        "tracking_id": (data.get("session_id") or data.get("tracking_id") or "").strip(),
        "name": (data.get("name") or "").strip(),
        "pais": (data.get("pais") or "").strip(),
        "idioma": (data.get("idioma") or "").strip(),
        "pistas_perimetrales": (data.get("pistas_perimetrales") or "").strip(),
        "pistas_laterales": (data.get("pistas_laterales") or "").strip(),
        "mailorigen": "web@planetpower.es",
        "origen": "oferta_campaña_prospecto",
    }








def lambda_handler(event, context):
    try:
        print("Evento recibido:", json.dumps(event, indent=2))
        method, path = _get_route(event)

        # CORS preflight
        if method == "OPTIONS":
            return {
                "statusCode": 200,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,Authorization",
                    "Access-Control-Allow-Methods": "OPTIONS,GET,POST"
                },
                "body": ""
            }

        stage = event.get("requestContext", {}).get("stage")
        if stage and path.startswith(f"/{stage}/"):
            path = path[len(stage) + 1:]

        route_key = f"{method} {path}"

        if route_key == "POST /oferta":
            print("Ruta POST /oferta detectada")
            payload, pdf_bytes = _parse_body_any(event)

            qs = event.get("queryStringParameters") or {}
            payload.setdefault("session_id", qs.get("session_id"))
            payload.setdefault("BD", qs.get("bd") or qs.get("BD"))
            payload.setdefault("total_excl_iva", qs.get("total_excl_iva"))

            result, status = oferta_core(payload, pdf_bytes)
            return _json_response(status, result)

        if route_key == "POST /proforma":
            print("Ruta POST /proforma detectada")
            payload, pdf_bytes = _parse_body_any(event)

            qs = event.get("queryStringParameters") or {}
            payload.setdefault("session_id", qs.get("session_id"))
            payload.setdefault("BD", qs.get("bd") or qs.get("BD"))

            result, status = proforma_core(payload, pdf_bytes)
            return _json_response(status, result)

        if route_key == "POST /oferta_prospect_submit":
            print("Ruta POST /oferta_prospect_submit detectada")

            raw_payload, _ = _parse_body_any(event)

            qs = event.get("queryStringParameters") or {}

            # mezclar body + querystring
            data = {**qs, **(raw_payload or {})}

            payload = build_payload(data)

            return oferta_prospect_submit_core(payload)

        return _json_response(404, {
            "ok": False,
            "error": "Ruta no encontrada",
            "routeKey": route_key
        })

    except json.JSONDecodeError:
        return _json_response(400, {"ok": False, "error": "JSON inválido"})

    except Exception as e:
        return _json_response(500, {
            "ok": False,
            "error": "Error interno",
            "detail": str(e)
        })

def get_db_credentials():

   
    client = boto3.client("secretsmanager", region_name=AWS_REGION)  # ✅ correcto
    response = client.get_secret_value(SecretId=MYSQL_DB_SECRET_NAME)
    
    return json.loads(response["SecretString"])


def get_session_data(session_id, connection):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT name, email, mailorigen, idioma, SalesHeaderNumber,
                   url_proformas, url_form_contacto, send_email,
                   email_password, send_wellcome_email
            FROM sessions
            WHERE session_id = %s
        """, (session_id,))
        
        row = cursor.fetchone()

        if row:
            print(f"Datos de sesión encontrados para session_id {session_id}: {row}")
            return {
                "name": row["name"],
                "email": row["email"],
                "mailorigen": row["mailorigen"],
                "idioma": row["idioma"],
                "SalesHeaderNumber": row["SalesHeaderNumber"],
                "url_proformas": row["url_proformas"],
                "url_form_contacto": row["url_form_contacto"],
                "send_email": row["send_email"],
                "email_password": row["email_password"],
                "send_wellcome_email": row["send_wellcome_email"],
            }
        else:
            print(f"No se encontraron datos para session_id {session_id}")
            return None



def get_campaign_recipient_data(tracking_id, connection):
    with connection.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("""
            SELECT 
                cr.id AS recipient_id,
                cr.email,
                cr.pais,
                cr.idioma,
                cr.origen,
                cr.tipo_lead,
                cr.estado,
                cr.entity_id,
                cr.entity_kind,
                cr.campaign_id,
                cr.send_status,
                cr.sent_at,
                cr.opened_at,
                cr.clicked_at,
                cr.tracking_id,
                c.name AS campaign_name,
                c.sender,
                c.reply_to,
                c.subject_es,
                c.subject_en
            FROM campaign_recipients cr
            JOIN campaigns c ON cr.campaign_id = c.id
            WHERE cr.tracking_id = %s
        """, (tracking_id,))
        
        row = cursor.fetchone()

        if row:
            print(f"Datos encontrados para tracking_id {tracking_id}: {row}")
            return row

        print(f"No se encontraron datos para tracking_id {tracking_id}")
        return None
    

def generar_url_proforma(quote_number: str, url: str, secret_key: str, connection, session_id: str) -> str:
    serializer = URLSafeTimedSerializer(secret_key, salt="proforma-link-v1")
    token = serializer.dumps({
        "quoteNumber": quote_number,
        "env": BD,
        "url_form_contacto": url,
        "session_id": session_id
    })

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO reset_token (user_id, token, created_at, expires_at)
                VALUES (0, %s, NOW(), DATE_ADD(NOW(), INTERVAL 7 DAY))
            """, (token,))
            connection.commit()
    except pymysql.err.IntegrityError:
        connection.rollback()
        raise

    qs = urlencode({"token": token})
    final_url = f"{url}/proforma_form?{qs}"
    print("URL:", final_url)
    return final_url

def build_proforma_cta(proforma_url: str, idioma: str) -> str:
    es = idioma in ("Español", "Esp")

    if es:
        pretext = "Si desea que emitamos una factura proforma, puede solicitarla aquí:"
        button_text = "Solicitar factura proforma"
    else:
        pretext = "If you would like us to issue a proforma invoice, you can request it here:"
        button_text = "Request proforma invoice"

    return f"""
    <p style="font-family:Arial, sans-serif; font-size:15px; color:#333; margin:18px 0 10px 0;">
      {pretext}
    </p>

    <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="margin:10px auto 22px auto;">
      <tr>
        <td align="center" bgcolor="#5B9BD5"
            style="border-radius:8px; padding:14px 24px; font-family:Arial, sans-serif;">
          <a href="{proforma_url}" target="_blank"
             style="color:#ffffff; font-size:15px; font-weight:bold; text-decoration:none; display:inline-block;">
            {button_text}
          </a>
        </td>
      </tr>
    </table>
    """




def send_email_with_proforma_pdf(pdf_data: bytes, filename: str, session_id: str, connection):
    session_data = get_session_data(session_id, connection)
    # Configuración SMTP (ejemplo con Gmail; sustituye con tus valores)
    smtp_server = "smtp.office365.com"
    smtp_port = 587
    global SEND_EMAIL, EMAIL_PASSWORD
    sender_email = session_data['mailorigen']
    SEND_EMAIL= session_data['send_email']
    EMAIL_PASSWORD= session_data['email_password']
    sender_password = EMAIL_PASSWORD
    print("sender", sender_email)
        
    if isinstance(sender_password, (bytes, bytearray)):
        sender_password = sender_password.decode("utf-8", errors="replace")  # ahora es str




    print ("SEND_EMAIL", SEND_EMAIL)
    print("EMAIL_PASSWORD", sender_password )
    if not sender_email or not sender_password:
        raise ValueError("Credenciales de correo no configuradas en variables de entorno")

    # Crear el mensaje
    msg = EmailMessage()
    msg["From"] = sender_email
    msg["To"] = session_data['email']

    cc_addresses = ["angel.r@planetpower.es"]
    #cc_addresses = ["alfonso@planetpower.es", "angel.r@planetpower.es"]
    msg["Cc"] = ", ".join(cc_addresses)




    

    
    if(( session_data['idioma'] == "Español")or (session_data['idioma'] == "Esp"))  :
        subject = f"Factura Proforma {session_data['name']} {session_data['SalesHeaderNumber']}"
        body = (
            "Buenos días, le enviamos la factura proforma solicitada"
                        
        )
        closing = "Saludos cordiales,"
    else:
        subject = f"Proforma Invoice {session_data['name']} {session_data['SalesHeaderNumber']}"
        body =  (
            "Good day, we are sending you the requested proforma invoice"
        )
        closing = "Kind regards,"

    msg["Subject"] = subject
    msg.set_content(body)
    html_signature = f"""
    <br><br>
    <p>{closing}</p>
   <html><body><div class="moz-signature">-- <br/>
<meta content="text/html; charset=utf-8" http-equiv="content-type"/>
<title>Fwd: nueva firma para email</title>
<o:p></o:p>
<div class="moz-forward-container">
<div class="WordSection1">
<p class="MsoNormal"><o:p> </o:p></p>
<p class="MsoNormal"><span style="mso-ligatures:none;mso-fareast-language:ES"><o:p> </o:p></span></p>
<table border="0" cellpadding="0" cellspacing="0" class="MsoTableGrid" style="width:265.15pt;border-collapse:collapse;border:none" width="354">
<tbody>
<tr style="height:36.2pt">
<td style="width:102.25pt;padding:0cm 5.4pt 0cm
                5.4pt;height:36.2pt" valign="top" width="136">
<p class="MsoNormal"><span style="font-size:9.0pt"><img alt="image-1" class="" data-img-id="1" height="42" id="Imagen_x0020_15" src="https://emailingledpadel.s3.eu-north-1.amazonaws.com/emails/templates/prueba/images/1.png" style="width:1.1916in;height:.4416in" width="114"/></span><span style="font-size:9.0pt;mso-ligatures:none"><o:p></o:p></span></p>
<p class="MsoNormal"><span style="font-size:9.0pt"><img alt="Imagen que contiene Logotipo
                      Descripción generada automáticamente" class="" data-img-id="2" height="47" id="Imagen_x0020_14" src="https://emailingledpadel.s3.eu-north-1.amazonaws.com/emails/templates/prueba/images/2.png" style="width:1.1916in;height:.4916in" width="114"/><span style="mso-ligatures:none"><o:p></o:p></span></span></p>
</td>
<td style="width:162.9pt;padding:0cm 5.4pt 0cm
                5.4pt;height:36.2pt" valign="top" width="217">
<p class="MsoNormal"><b><span style="font-size:10.0pt;color:#5B9BD5;mso-ligatures:none">Alfonso Martínez</span></b><b><span style="font-size:10.0pt;color:#5B9BD5;mso-ligatures:none"><o:p></o:p></span></b></p>
<p class="MsoNormal"><b><span style="font-size:8.0pt;color:#5B9BD5;mso-ligatures:none">T.</span></b><span style="font-size:8.0pt;mso-ligatures:none"> +34
                      946682011  <b><span style="color:#5B9BD5">M. </span></b>+34
                      629422113</span><span style="font-size:8.0pt;mso-ligatures:none"><o:p></o:p></span></p>
<p class="MsoNormal"><b><span style="font-size:8.0pt;color:#8EAADB;mso-ligatures:none">E. </span></b><span style="font-size:8.0pt;color:#8EAADB;mso-ligatures:none"><a href="mailto:alfonso@planetpower.es" moz-do-not-send="true"><span style="color:#8EAADB">alfonso@planetpower.es</span></a> 
                      <o:p></o:p></span></p>
<p class="MsoNormal"><span style="font-size:8.0pt;color:#8EAADB;mso-ligatures:none">                     </span><span lang="EN-US" style="font-size:8.0pt;color:#8EAADB;mso-ligatures:none"><a href="http://www.planetpower.es" moz-do-not-send="true"><span style="color:#8EAADB">planetpower.es</span></a>
</span><span lang="EN-US" style="font-size:8.0pt;color:#2F5496;mso-ligatures:none">  </span><span lang="EN-US" style="font-size:8.0pt;mso-ligatures:none"><o:p></o:p></span></p>
<p class="MsoNormal"><span lang="EN-US" style="font-size:8.0pt;color:#8EAADB;mso-ligatures:none">                     <a href="http://www.moduloled.es" moz-do-not-send="true"><span style="color:#8EAADB">moduloled.es</span></a>
<o:p></o:p></span></p>
<p class="MsoNormal"><span lang="EN-US" style="font-size:8.0pt;color:#8EAADB;mso-ligatures:none">                     <a href="http://www.ledpadel.com" moz-do-not-send="true"><span style="color:#8EAADB">ledpadel.com</span></a><o:p></o:p></span></p>
</td>
</tr>
</tbody>
</table>
<p class="MsoNormal"><span style="mso-ligatures:none;mso-fareast-language:ES"><o:p> </o:p></span></p>
<p class="MsoNormal"><span style='font-size:5.0pt;font-family:"Arial",sans-serif;color:#003C61;mso-ligatures:none;mso-fareast-language:ES'>La
              información contenida tanto en este e-mail, como en los
              documentos adjuntos, es información confidencial y
              privilegiada para uso exclusivo de la persona o personas a
              las que va dirigido. No está permitido el acceso a este
              mensaje a cualquier otra persona distinta a los indicados.
              Si no es uno de los destinatarios o ha recibido este
              mensaje por error, cualquier duplicación, reproducción,
              distribución, así como cualquier uso de la información
              contenida, está prohibida y puede ser ilegal. LOPD 15/1999
              Sus datos de carácter personal forman parte de nuestros
              ficheros con la finalidad de hacer efectiva nuestra
              relación comercial garantizándole en todo momento la más
              absoluta confidencialidad. Si lo desea puede ejercitar los
              derechos A.R.C.O. en <b>Planet Power Tools S.L.</b>,Avd.
              Sabino Arana 64 - 48640 (Vizcaya) España. Por favor piensa
              en el medio ambiente antes de imprimir este correo. </span><span style="font-size:5.0pt;mso-ligatures:none;mso-fareast-language:ES"><a href="http://planetpower.es/condiciones/" moz-do-not-send="true"><span style='font-family:"Arial",sans-serif;color:#0563C1'>Condiciones
                  Generales de Venta y Garantía</span></a></span><span style="mso-ligatures:none"><o:p></o:p></span></p>
<p class="MsoNormal"><o:p> </o:p></p>
</div>
</div>
</div>
<div data-inserted="unreferenced-attachments"></div></body>
</html>

    """

  
    msg.add_alternative(f"<html><body><p>{body}</p>{html_signature}</body></html>", subtype='html')

    # Adjuntar el PDF
    
    msg.add_attachment(pdf_data, maintype="application", subtype="pdf", filename=filename)

    SEND_EMAIL=True
    
    if (SEND_EMAIL) :

        print("🔄 Enviando correo electrónico...")
        print("🔄 Conectando a SMTP...", smtp_server, smtp_port)
        socket.setdefaulttimeout(20)
        try:
            if smtp_port == 465:
                # TLS implícito
                with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=20) as server:
                    SMTP_LOGIN = "ofertas@planetpower.es"


                    server.login(SMTP_LOGIN, sender_password)
                  
                    server.send_message(msg)
            else:
                # STARTTLS (587 recomendado)
                with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as server:
                    server.set_debuglevel(1)  # <-- CLAVE (ver conversación SMTP)
                    with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as server:
                        server.set_debuglevel(1)

                       
                        server.ehlo()

                       
                        server.starttls()
                        
                        server.ehlo()

                       
                        SMTP_LOGIN = "ofertas@planetpower.es"


                        server.login(SMTP_LOGIN, sender_password)

                       
                        server.send_message(msg)

                   

            print("Correo enviado correctamente.")
            print("sender", sender_email)
            print("smtp", smtp_server, smtp_port)
            return {"status": "sent"}

        except smtplib.SMTPConnectError as e:
            # 530 "IP denied" u otros de conexión
            return {"status": "failed", "reason": f"connect_error: {e}"}
        except smtplib.SMTPAuthenticationError as e:
            return {"status": "failed", "reason": f"auth_error: {e}"}
        except smtplib.SMTPRecipientsRefused as e:
            return {"status": "failed", "reason": f"rcpt_refused: {e.recipients}"}
        except smtplib.SMTPSenderRefused as e:
            return {"status": "failed", "reason": f"sender_refused: {e.sender}"}
        except smtplib.SMTPServerDisconnected as e:
            return {"status": "failed", "reason": f"disconnected: {e}"}
        except Exception as e:
            return {"status": "failed", "reason": f"unexpected: {e}"}






def send_email_with_pdf(pdf_data: bytes, filename: str, session_id: str, url:str, secret_key:str, quote_number:str, connection ):
    session_data = get_session_data(session_id, connection)
    # Configuración SMTP (ejemplo con Gmail; sustituye con tus valores)
    smtp_server = "smtp.office365.com"
    smtp_port = 587
    global SEND_EMAIL, EMAIL_PASSWORD
    sender_email = session_data['mailorigen']
    SEND_EMAIL= session_data['send_email']
    EMAIL_PASSWORD= session_data['email_password']
    sender_password = EMAIL_PASSWORD
    print("sender", sender_email)
        
    if isinstance(sender_password, (bytes, bytearray)):
        sender_password = sender_password.decode("utf-8", errors="replace")  # ahora es str




    print ("SEND_EMAIL", SEND_EMAIL)
    print("EMAIL_PASSWORD", sender_password )
    if not sender_email or not sender_password:
        raise ValueError("Credenciales de correo no configuradas en variables de entorno")

    # Crear el mensaje
    msg = EmailMessage()
    msg["From"] = sender_email
    msg["To"] = session_data['email']

    cc_addresses = ["angel.r@planetpower.es"]
    #cc_addresses = ["alfonso@planetpower.es", "angel.r@planetpower.es"]
    msg["Cc"] = ", ".join(cc_addresses)




    

    
    if(( session_data['idioma'] == "Español")or (session_data['idioma'] == "Esp"))  :
        subject = f"Oferta {session_data['name']} {session_data['SalesHeaderNumber']}"
        body = (
            "Buenos días, me llamo Alfonso, me puede escribir, contactar por WhatsApp o llamarme en caso de dudas (ver detalles en mi firma)"
            + "<br><br>"
            + "Adjunto encontrará la oferta de solicitada."
        )
        closing = "Saludos cordiales,"
    else:
        subject = f"Sales Quote {session_data['name']} {session_data['SalesHeaderNumber']}"
        body =  (
            "Good day, my name is Alfonso, you can email me, WhatsApp or call me in case of doubts (see details in my signature)" 
            + "<br><br>" 
            + "Attached you will find the requested quotation."
        )
        closing = "Kind regards,"

    msg["Subject"] = subject
    msg.set_content(body)
    html_signature = f"""
    <br><br>
    <p>{closing}</p>
   <html><body><div class="moz-signature">-- <br/>
<meta content="text/html; charset=utf-8" http-equiv="content-type"/>
<title>Fwd: nueva firma para email</title>
<o:p></o:p>
<div class="moz-forward-container">
<div class="WordSection1">
<p class="MsoNormal"><o:p> </o:p></p>
<p class="MsoNormal"><span style="mso-ligatures:none;mso-fareast-language:ES"><o:p> </o:p></span></p>
<table border="0" cellpadding="0" cellspacing="0" class="MsoTableGrid" style="width:265.15pt;border-collapse:collapse;border:none" width="354">
<tbody>
<tr style="height:36.2pt">
<td style="width:102.25pt;padding:0cm 5.4pt 0cm
                5.4pt;height:36.2pt" valign="top" width="136">
<p class="MsoNormal"><span style="font-size:9.0pt"><img alt="image-1" class="" data-img-id="1" height="42" id="Imagen_x0020_15" src="https://emailingledpadel.s3.eu-north-1.amazonaws.com/emails/templates/prueba/images/1.png" style="width:1.1916in;height:.4416in" width="114"/></span><span style="font-size:9.0pt;mso-ligatures:none"><o:p></o:p></span></p>
<p class="MsoNormal"><span style="font-size:9.0pt"><img alt="Imagen que contiene Logotipo
                      Descripción generada automáticamente" class="" data-img-id="2" height="47" id="Imagen_x0020_14" src="https://emailingledpadel.s3.eu-north-1.amazonaws.com/emails/templates/prueba/images/2.png" style="width:1.1916in;height:.4916in" width="114"/><span style="mso-ligatures:none"><o:p></o:p></span></span></p>
</td>
<td style="width:162.9pt;padding:0cm 5.4pt 0cm
                5.4pt;height:36.2pt" valign="top" width="217">
<p class="MsoNormal"><b><span style="font-size:10.0pt;color:#5B9BD5;mso-ligatures:none">Alfonso Martínez</span></b><b><span style="font-size:10.0pt;color:#5B9BD5;mso-ligatures:none"><o:p></o:p></span></b></p>
<p class="MsoNormal"><b><span style="font-size:8.0pt;color:#5B9BD5;mso-ligatures:none">T.</span></b><span style="font-size:8.0pt;mso-ligatures:none"> +34
                      946682011  <b><span style="color:#5B9BD5">M. </span></b>+34
                      629422113</span><span style="font-size:8.0pt;mso-ligatures:none"><o:p></o:p></span></p>
<p class="MsoNormal"><b><span style="font-size:8.0pt;color:#8EAADB;mso-ligatures:none">E. </span></b><span style="font-size:8.0pt;color:#8EAADB;mso-ligatures:none"><a href="mailto:alfonso@planetpower.es" moz-do-not-send="true"><span style="color:#8EAADB">alfonso@planetpower.es</span></a> 
                      <o:p></o:p></span></p>
<p class="MsoNormal"><span style="font-size:8.0pt;color:#8EAADB;mso-ligatures:none">                     </span><span lang="EN-US" style="font-size:8.0pt;color:#8EAADB;mso-ligatures:none"><a href="http://www.planetpower.es" moz-do-not-send="true"><span style="color:#8EAADB">planetpower.es</span></a>
</span><span lang="EN-US" style="font-size:8.0pt;color:#2F5496;mso-ligatures:none">  </span><span lang="EN-US" style="font-size:8.0pt;mso-ligatures:none"><o:p></o:p></span></p>
<p class="MsoNormal"><span lang="EN-US" style="font-size:8.0pt;color:#8EAADB;mso-ligatures:none">                     <a href="http://www.moduloled.es" moz-do-not-send="true"><span style="color:#8EAADB">moduloled.es</span></a>
<o:p></o:p></span></p>
<p class="MsoNormal"><span lang="EN-US" style="font-size:8.0pt;color:#8EAADB;mso-ligatures:none">                     <a href="http://www.ledpadel.com" moz-do-not-send="true"><span style="color:#8EAADB">ledpadel.com</span></a><o:p></o:p></span></p>
</td>
</tr>
</tbody>
</table>
<p class="MsoNormal"><span style="mso-ligatures:none;mso-fareast-language:ES"><o:p> </o:p></span></p>
<p class="MsoNormal"><span style='font-size:5.0pt;font-family:"Arial",sans-serif;color:#003C61;mso-ligatures:none;mso-fareast-language:ES'>La
              información contenida tanto en este e-mail, como en los
              documentos adjuntos, es información confidencial y
              privilegiada para uso exclusivo de la persona o personas a
              las que va dirigido. No está permitido el acceso a este
              mensaje a cualquier otra persona distinta a los indicados.
              Si no es uno de los destinatarios o ha recibido este
              mensaje por error, cualquier duplicación, reproducción,
              distribución, así como cualquier uso de la información
              contenida, está prohibida y puede ser ilegal. LOPD 15/1999
              Sus datos de carácter personal forman parte de nuestros
              ficheros con la finalidad de hacer efectiva nuestra
              relación comercial garantizándole en todo momento la más
              absoluta confidencialidad. Si lo desea puede ejercitar los
              derechos A.R.C.O. en <b>Planet Power Tools S.L.</b>,Avd.
              Sabino Arana 64 - 48640 (Vizcaya) España. Por favor piensa
              en el medio ambiente antes de imprimir este correo. </span><span style="font-size:5.0pt;mso-ligatures:none;mso-fareast-language:ES"><a href="http://planetpower.es/condiciones/" moz-do-not-send="true"><span style='font-family:"Arial",sans-serif;color:#0563C1'>Condiciones
                  Generales de Venta y Garantía</span></a></span><span style="mso-ligatures:none"><o:p></o:p></span></p>
<p class="MsoNormal"><o:p> </o:p></p>
</div>
</div>
</div>
<div data-inserted="unreferenced-attachments"></div></body>
</html>

    """

    


    proforma_url = generar_url_proforma (quote_number,url, secret_key, connection,session_id) # luego lo sustituimos por el real
    proforma_cta = build_proforma_cta(proforma_url, session_data["idioma"])

    html_body = f"""
    <html>
    <body>
   
        <p>{body}</p>
        {proforma_cta}
        {html_signature}
    </body>
    </html>
    """

    msg.add_alternative(html_body, subtype="html")

  
    #msg.add_alternative(f"<html><body><p>{body}</p>{html_signature}</body></html>", subtype='html')

    # Adjuntar el PDF
    
    msg.add_attachment(pdf_data, maintype="application", subtype="pdf", filename=filename)
    
    if (SEND_EMAIL) :

        print("🔄 Enviando correo electrónico...")
        print("🔄 Conectando a SMTP...", smtp_server, smtp_port)
        socket.setdefaulttimeout(20)
        try:
            if smtp_port == 465:
                # TLS implícito
                with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=20) as server:
                    SMTP_LOGIN = "ofertas@planetpower.es"


                    server.login(SMTP_LOGIN, sender_password)
                  
                    server.send_message(msg)
            else:
                # STARTTLS (587 recomendado)
                with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as server:
                    server.set_debuglevel(1)  # <-- CLAVE (ver conversación SMTP)
                    with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as server:
                        server.set_debuglevel(1)

                       
                        server.ehlo()

                        server.starttls()
                       
                        server.ehlo()

                        
                        SMTP_LOGIN = "ofertas@planetpower.es"


                        server.login(SMTP_LOGIN, sender_password)

                        
                        server.send_message(msg)

                    print("✅ FIN: después de send_message()")


            print("Correo enviado correctamente.")
            print("sender", sender_email)
            print("smtp", smtp_server, smtp_port)
            return {"status": "sent"}

        except smtplib.SMTPConnectError as e:
            # 530 "IP denied" u otros de conexión
            return {"status": "failed", "reason": f"connect_error: {e}"}
        except smtplib.SMTPAuthenticationError as e:
            return {"status": "failed", "reason": f"auth_error: {e}"}
        except smtplib.SMTPRecipientsRefused as e:
            return {"status": "failed", "reason": f"rcpt_refused: {e.recipients}"}
        except smtplib.SMTPSenderRefused as e:
            return {"status": "failed", "reason": f"sender_refused: {e.sender}"}
        except smtplib.SMTPServerDisconnected as e:
            return {"status": "failed", "reason": f"disconnected: {e}"}
        except Exception as e:
            return {"status": "failed", "reason": f"unexpected: {e}"}






def send_wellcome_email ( session_id: str, connection):
    session_data = get_session_data(session_id, connection)
    # Configuración SMTP (ejemplo con Gmail; sustituye con tus valores)
    smtp_server = "smtp.office365.com"
    smtp_port = 587
    global SEND_EMAIL, EMAIL_PASSWORD
    sender_email = session_data['mailorigen']
    SEND_EMAIL= session_data['send_email']
    EMAIL_PASSWORD= session_data['email_password']
    sender_password = EMAIL_PASSWORD
    print("sender", sender_email)
        
    if isinstance(sender_password, (bytes, bytearray)):
        sender_password = sender_password.decode("utf-8", errors="replace")  # ahora es str




    print ("SEND_EMAIL", SEND_EMAIL)
    print("EMAIL_PASSWORD", sender_password )
    if not sender_email or not sender_password:
        raise ValueError("Credenciales de correo no configuradas en variables de entorno")

    # Crear el mensaje
    msg = EmailMessage()
    msg["From"] = sender_email
    msg["To"] = session_data['email']

    cc_addresses = ["angel.r@planetpower.es"]
    #cc_addresses = ["alfonso@planetpower.es", "angel.r@planetpower.es"]
    msg["Cc"] = ", ".join(cc_addresses)

    slug = "wellcome-email"  # (si es 'welcome' o similar, usa el correcto)
   
    
    

    
    if( session_data['idioma'] == "Español")or ( session_data['idioma'] == "Esp"):
        subject = f"Información Comercial"
        lang = "es"
    else:
        subject = f"Commercial Information"
        lang = "en"
    msg["Subject"] = subject

    print ("lang", lang)

    #html_body = build_message_html_from_s3(slug, lang)
    #safe_message = normalize_incoming_content(html_body)
    body_html = render_email_body_images_folder(slug, lang)


    msg.set_content("")
    
  
  
    msg.add_alternative(body_html, subtype='html')
    
    
    
    
    if (SEND_EMAIL) :

        print("🔄 Enviando correo electrónico...")
        try:
            if smtp_port == 465:
                # TLS implícito
                with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=20) as server:

                    SMTP_LOGIN = "ofertas@planetpower.es"


                    server.login(SMTP_LOGIN, sender_password)
                    
                    server.send_message(msg)
            else:
                # STARTTLS (587 recomendado)
                with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    SMTP_LOGIN = "ofertas@planetpower.es"


                    server.login(SMTP_LOGIN, sender_password)
                    server.send_message(msg)

            print("Correo enviado correctamente.")
            print("sender", sender_email)
            print("smtp", smtp_server, smtp_port)
            return {"status": "sent"}

        except smtplib.SMTPConnectError as e:
            # 530 "IP denied" u otros de conexión
            return {"status": "failed", "reason": f"connect_error: {e}"}
        except smtplib.SMTPAuthenticationError as e:
            return {"status": "failed", "reason": f"auth_error: {e}"}
        except smtplib.SMTPRecipientsRefused as e:
            return {"status": "failed", "reason": f"rcpt_refused: {e.recipients}"}
        except smtplib.SMTPSenderRefused as e:
            return {"status": "failed", "reason": f"sender_refused: {e.sender}"}
        except smtplib.SMTPServerDisconnected as e:
            return {"status": "failed", "reason": f"disconnected: {e}"}
        except Exception as e:
            return {"status": "failed", "reason": f"unexpected: {e}"}




def get_dropbox_access_token():

    sm = boto3.client("secretsmanager", region_name=AWS_REGION)
    resp = sm.get_secret_value(SecretId=DROPBOX_SECRET_NAME)
    secret = json.loads(resp["SecretString"])


    # === CONFIGURA ESTOS DATOS ===
    APP_KEY = secret["DROPBOX_APP_KEY"]
    APP_SECRET = secret["DROPBOX_APP_SECRET"]
    REFRESH_TOKEN =secret["DROPBOX_REFRESH_TOKEN"]

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

def update_pdf_bd(session_id, total_amount_quote, document_no, pdf_data,connection):
    
    try:
        with connection.cursor() as cursor:
          cursor.execute(
            """
            UPDATE sessions
            SET filename = %s,
                file_data = %s,
                cantidad_total = %s
            WHERE session_id = %s
            """,
          (document_no, pdf_data, total_amount_quote, session_id)
        )
        connection.commit()
        print(f"✅ PDF guardado en la base de datos para la sesión {session_id}.")
   
    finally:
        return


def s3_read_text(bucket: str, key: str, encoding: str = "utf-8") -> str:
    """Lee un objeto de S3 como texto."""
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read().decode(encoding)
    except (ClientError, BotoCoreError) as e:
        # Loguea si tienes logger; aquí re-lanzamos con detalle
        raise RuntimeError(f"Error leyendo s3://{bucket}/{key}: {e}")

def build_message_html_from_s3(slug: str, lang: str = "en") -> str:
    """
    Construye la KEY y devuelve el HTML de:
      emails/templates/<slug>/<lang>/partials/message.html
    """
    base = ROOT_PREFIX_S3.rstrip("/")
    key = f"{base}/{slug.strip('/')}/{lang}/partials/message.html"
    return s3_read_text(S3_BUCKET, key)        




def normalize_incoming_content(raw: str) -> str:
    raw = raw or ""
    looks_html = "<" in raw and ">" in raw
    if not looks_html:
        # tu helper ya existente
        return text_to_html_preserving_lf(raw)

    soup = BeautifulSoup(raw, "html.parser")
    node = soup.body or soup  # solo contenido, sin <html>/<body>

    # limpia restos de Outlook/Thunderbird
    for t in list(node.find_all(True)):
        # elimina tags con namespace de Office/Word: o:, v:, w:
        if ":" in t.name and t.name.split(":", 1)[0].lower() in {"o", "v", "w"}:
            t.decompose()
            continue
 
        # quita clases Mso*/moz-*
        if t.has_attr("class"):
            t["class"] = [c for c in t.get("class", []) if not c.lower().startswith(("mso", "moz-"))]
            if not t["class"]:
                t.attrs.pop("class", None)

        # borra estilos con propiedades mso-
        if t.has_attr("style") and "mso-" in t["style"].lower():
            t.attrs.pop("style", None)

        # borra atributos moz-*
        for a in list(t.attrs.keys()):
            if a.lower().startswith("moz"):
                t.attrs.pop(a, None)

    # desenvuelve wrappers típicos de Thunderbird
    for sel in ["div.moz-signature", "div.moz-quote-pre", 'blockquote[type="cite"]']:
        for e in node.select(sel):
            e.unwrap()

    # devuelve solo hijos del body (sin <body>)
    return "".join(str(c) for c in node.children)




def text_to_html_preserving_lf(txt: str) -> str:
    """
    Convierte texto plano a HTML simple:
    - Normaliza saltos de línea (CRLF/CR -> LF)
    - Escapa caracteres HTML (&, <, >, ", ')
    - Sustituye cada LF por <br>
    """
    if not txt:
        return ""
    s = txt.replace("\r\n", "\n").replace("\r", "\n")
    s = html.escape(s, quote=True)
    return s.replace("\n", "<br>")



def s3_get_text(key: str) -> str | None:
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        return obj["Body"].read().decode("utf-8")
    except Exception:
        return None

def s3_list(prefix: str):
    """Lista keys bajo un prefijo."""
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for it in page.get("Contents", []):
            keys.append(it["Key"])
    return keys

def s3_url_for(key: str) -> str:
    """Elige cómo servir imágenes (CloudFront > público S3 > presigned)."""
    cdn = os.getenv("CLOUDFRONT_DOMAIN")  # ej: dxxx.cloudfront.net
    if cdn:
        return f"https://{cdn}/{key}"
    # si el bucket es público:
    if os.getenv("S3_PUBLIC", "false").lower() == "true":
        return f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"
    # privado → presigned
    return s3.generate_presigned_url(
        "get_object", Params={"Bucket": S3_BUCKET, "Key": key}, ExpiresIn=3600
    )

def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or "", "html.parser")

def _norm_src(s: str | None) -> str | None:
    if not s: return None
    s = s.strip()
    if s.lower().startswith("data:"): return None
    return s.split("?")[0].split("#")[0].lower()

# ----------------------------------
def render_email_body_images_folder(slug: str, lang: str = "en") -> str:
    base = "emails/templates"

    sig_key      = f"{base}/{slug}/partials/signature.html"
    tpl_key      = f"{base}/{slug}/{lang}/template.html"   # solo para <head>
    manifest_key = f"{base}/{slug}/manifest.json"

    # 1) message desde S3 y normalización
    html_body = build_message_html_from_s3(slug, lang) or ""
    message   = normalize_incoming_content(html_body)

    # 2) signature, template y manifest
    signature = s3_get_text(sig_key) or ""
    template  = s3_get_text(tpl_key) or ""
    mtxt      = s3_get_text(manifest_key)

    try:
        manifest = json.loads(mtxt) if mtxt else {}
    except Exception:
        manifest = {}

    # 3) allowlist de imágenes (excluye logos)
    shared_images = (manifest.get("shared") or {}).get("images") or {}
    allowed_names = {
        name.lower()
        for name, meta in shared_images.items()
        if isinstance(meta, dict) and not meta.get("is_logo", False)
    }

    # 4) <head> del template (si existe)
    tpl_soup  = _soup(template)
    head_html = str(tpl_soup.head) if tpl_soup.head else ""

    # 5) imágenes de la firma (para evitar duplicar)
    sig_soup = _soup(signature)
    sig_img_keys = set()
    for tag in sig_soup.find_all(["img", "source"]):
        key = _norm_src(tag.get("src") or tag.get("srcset"))
        if key:
            sig_img_keys.add(os.path.basename(key).lower())

    # 6) listar imágenes desde S3 (sin idioma)
    img_prefix_shared = f"{base}/{slug}/images/"
    keys = s3_list(img_prefix_shared)

    exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
    seen = set()
    imgs_block_parts = []
       
    for key in keys:
        name = os.path.basename(key).lower()
        ext  = os.path.splitext(name)[1]
        if ext not in exts:
            continue
        if allowed_names and (name not in allowed_names):
            continue
        if name in sig_img_keys or name in seen:
            continue

        seen.add(name)

        # Tamaños desde manifest: target_w/target_h (+ fit opcional)
        meta = shared_images.get(name) if isinstance(shared_images, dict) else None
        w = (meta.get("target_w") if isinstance(meta, dict) else None)
        try:
            w = int(w) if w is not None else None
        except:
            w = None

        # Usa la URL pública del manifest si la tienes; si no, tu fallback
        url = meta.get("url") if isinstance(meta, dict) and meta.get("url") else s3_url_for(key)

        
        width_attr = f' width="{w}"' if w else ""
        style_parts = ["display:block", "height:auto!important"]
        if w:
            style_parts.append(f"width:{w}px!important")
            style_parts.append("max-width:100%!important")  # responsive
        style_attr = f' style="{";".join(style_parts)}"'

        wrapper_style = 'style="display:block;width:100%;line-height:0;"'
        imgs_block_parts.append(
            f'<div {wrapper_style}>'
            f'<img src="{url}" alt="{name}"{width_attr}{style_attr} />'
            f'</div>'
        )

        if allowed_names and len(seen) >= len(allowed_names):
            break

    images_block = "".join(imgs_block_parts)


    
    # 7) attachments desde manifest (opcional)
    try:
        att_list = ((manifest.get("languages") or {}).get(lang) or {}).get("attachments") or []
    except Exception:
        att_list = []

    atts_html = ""
    if att_list:
        items = "".join(
            f'<li><a href="{a.get("url","#")}" target="_blank">{a.get("filename","attachment")}</a></li>'
            for a in att_list if isinstance(a, dict)
        )
        atts_html = f'<div data-composed="attachments"><ul>{items}</ul></div>'

    # 8) ensamblar resultado final
    html = f"""<!doctype html>
<html>
{head_html if head_html.startswith("<head") else f"<head>{head_html}</head>"}
<body>
  <div data-composed="message">{message}</div>
  {atts_html}
  <div data-composed="images">{images_block}</div>
  <div data-composed="signature">{signature}</div>
  </body>
</html>"""
    return html








if __name__ == "__main__":

    from flask import Flask,request, jsonify

    
   
    
    from dotenv import load_dotenv



    from pathlib import Path
    app = Flask(__name__)   
    load_dotenv(Path(__file__).resolve().parent / ".env")
    

    SECRET_KEY_PROFORMAS= os.getenv ("SECRET_KEY_PROFORMAS","")

    def _parse_body_any_flask(req):
    # 1) multipart file
        if "pdf" in req.files:
            payload = req.form.to_dict()  # campos de form si los hay
            pdf_bytes = req.files["pdf"].read()
            return payload, pdf_bytes

        # 2) JSON
        payload = req.get_json(silent=True) or {}
        pdf_bytes = None
        if payload.get("pdf_base64"):
            pdf_bytes = base64.b64decode(payload["pdf_base64"])
        return payload, pdf_bytes
    
   
    @app.route('/proforma', methods=['POST','GET'])
    def recibir_proforma():
        payload = {}

        qs = request.args or {}
        payload["session_id"] = (qs.get("session_id") or "").strip()
        payload["BD"] = (qs.get("BD") or "").strip()

        pdf_data = request.data or b""

        if not pdf_data:
            data = request.get_json(silent=True) or {}
            if "pdf_base64" in data:
                pdf_data = base64.b64decode(data["pdf_base64"])

        if not pdf_data and "file" in request.files:
            pdf_data = request.files["file"].read()

        result, status = proforma_core(payload, pdf_data)

        return jsonify(result), status
                
            
        
        

    
    @app.route("/oferta", methods=["POST"])
    def recibir_oferta():
        # 1) payload: viene por querystring o JSON (si algún día lo mandas)
        payload = request.get_json(silent=True) or {}
        qs = request.args.to_dict()

        payload.setdefault("session_id", qs.get("session_id"))
        payload.setdefault("BD", qs.get("BD") or qs.get("bd"))
        payload.setdefault("total_excl_iva", qs.get("total_excl_iva"))

        # 2) pdf_bytes: soporta 3 modos
        pdf_bytes = None

        # A) RAW PDF en body
        if (request.content_type or "").startswith("application/pdf"):
            pdf_bytes = request.data  # <-- AQUÍ ESTÁ LA CLAVE

        # B) multipart/form-data
        elif "pdf" in request.files:
            pdf_bytes = request.files["pdf"].read()

        # C) JSON base64
        elif payload.get("pdf_base64"):
            pdf_bytes = base64.b64decode(payload["pdf_base64"])

        result, status = oferta_core(payload, pdf_bytes)
        return jsonify(result), status
    


    @app.route("/oferta_prospect_submit", methods=["POST", "OPTIONS"])
    def oferta_prospect_submit():

       
        
        from flask import make_response

        if request.method == "OPTIONS":
            response = make_response("", 200)
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
            response.headers["Access-Control-Allow-Methods"] = "OPTIONS,POST"
            return response

        form_data = request.get_json(silent=True) or request.form or request.args or {}

        payload = build_payload(form_data)

        result = oferta_prospect_submit_core(payload)

        return (
            result.get("body", ""),
            result.get("statusCode", 200),
            result.get("headers", {})
        )

 
        
    app.run(debug=True, port=5001)

