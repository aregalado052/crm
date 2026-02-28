
import html
import json
from multiprocessing import connection
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
from io import BytesIO
import re

#from flask import Response, request, jsonify

import base64
from decimal import Decimal, ROUND_HALF_UP
from datetime import date

from types import SimpleNamespace
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from jinja2 import Environment, FileSystemLoader

# Inicializar Jinja una sola vez (fuera del handler)
env = Environment(
    loader=FileSystemLoader(searchpath=os.path.join(os.getcwd(), "templates"))
)


MYSQL_DB_SECRET_NAME = os.getenv("MYSQL_DB_SECRET_NAME", "")
MICROSOFT_BC_SECRET_NAME = os.getenv("MICROSOFT_BC_SECRET_NAME", "")
SCOPE = os.getenv("SCOPE", "")
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
TENANT_ID = os.getenv("TENANT_ID", "")
COMPANY_ID = os.getenv("COMPANY_ID", "")

SECRET_KEY_PROFORMAS= os.getenv("SECRET_KEY_PROFORMAS", "")

global BD, ENVIRONMENT, URL_OFERTAS, URL_PROFORMAS




TOKEN_MAX_AGE = 21 * 24 * 60 * 60  # 7 días








def validate_token_and_get_quote(token: str) -> str:
    serializer = URLSafeTimedSerializer(SECRET_KEY_PROFORMAS    , salt="proforma-link-v1")
    print (f"Validando token: {token}")
    print("secret key used for validation:", SECRET_KEY_PROFORMAS)

    payload = serializer.loads(token, max_age=TOKEN_MAX_AGE)  # firma + exp
    quote_number = payload.get("quoteNumber")
    BD = payload.get("env")
    url_form_contacto = payload.get("url_form_contacto")
    session_id = payload.get("session_id")
    

    print(f"Token válido. QuoteNumber: {quote_number}, BD: {BD}, URL_FORMCONTACTO: {url_form_contacto}, session_id: {session_id}    ")
    if not quote_number:
        raise BadSignature("missing quoteNumber")
    return quote_number, BD, url_form_contacto, session_id





def token_exists_in_db(connection, token: str) -> bool:
    # Si guardas tokens en reset_token para one-time-use / control
    with connection.cursor() as cur:
        cur.execute("""
            SELECT 1
            FROM reset_token
            WHERE token=%s
              AND user_id=0
              AND expires_at > NOW()
            LIMIT 1
        """, (token,))
        return cur.fetchone() is not None




def get_db_credentials():
    client = boto3.client("secretsmanager", region_name=AWS_REGION)  # ✅ correcto
    response = client.get_secret_value(SecretId=MYSQL_DB_SECRET_NAME)
    return json.loads(response["SecretString"])

def get_session_data(session_id,connection):


    
    
    with connection.cursor() as cursor:
        cursor.execute("SELECT name, email, mailorigen, idioma, SalesHeaderNumber,url_proformas, url_form_contacto, send_email, email_password, send_wellcome_email FROM sessions WHERE session_id = %s", (session_id,))
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
                "environment": row.get("environment", "Production"),
                "send_email": row.get("send_email", True),
                "email_user": row.get("email_user", ""),
            }
        else:
            return None



# --- Obtener token de acceso ---
def get_token():
    """Obtiene un token de acceso para autenticar solicitudes a Business Central.
    Utiliza el flujo de contraseña para obtener un token JWT.
    """
    sm = boto3.client("secretsmanager", region_name=AWS_REGION)
    resp = sm.get_secret_value(SecretId=MICROSOFT_BC_SECRET_NAME)
    secret = json.loads(resp["SecretString"])


    # === CONFIGURA ESTOS DATOS ===
    CLIENT_ID = secret["CLIENT_ID"]
    CLIENT_SECRET = secret["CLIENT_SECRET"]
   

    
    url = f'https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token'

   

    data = {
        "grant_type": "client_credentials",        
        'client_id': CLIENT_ID,        
        'client_secret': CLIENT_SECRET,
        'scope': SCOPE,
    }

  

    postfields = urllib.parse.urlencode(data)

    headers = ['Content-Type: application/x-www-form-urlencoded']
    
    

    #print("POSTFIELDS:", postfields.replace(CLIENT_SECRET, "***"))
   

   
    buffer = BytesIO()

    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.POST, 1)
    c.setopt(c.POSTFIELDS, postfields)

    # Configurar encabezados
    
    c.setopt(c.HTTPHEADER, headers)

    # Capturar la respuesta
    c.setopt(c.WRITEDATA, buffer)

    # Ejecutar la solicitud
    c.perform()

    status_code = c.getinfo(pycurl.RESPONSE_CODE)

    # Cerrar Curl
    c.close()

    response_body = buffer.getvalue().decode('utf-8')
   
    

   
    
    if status_code == 200:
        try:
            token_data = json.loads(response_body)
            token = token_data['access_token']
            print("✅ Access token:", token)
            return token
        except Exception as e:
            print("❌ No se pudo extraer el token:", e)
            print("Respuesta cruda:", response_body)
            return None
    else:
        print(f"❌ Error: código HTTP {status_code}")
        print("Respuesta:", response_body)
        return None

def actualizar_sales_header(connection, session_id, SalesHeaderNumber):
    

    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE sessions
            SET SalesHeaderNumber = %s
            WHERE session_id = %s
        """, (SalesHeaderNumber, session_id))
    connection.commit()
   

def store_session(connection, name, email, mailorigen, idioma, origen, bd, email_user, email_password, url_contacto, url_ofertas, url_proformas, 
                  url_actualizar_contacto, url_form_contacto, api_key, environment, send_email, send_wellcome_email):
    session_id = str(uuid.uuid4())  # 🔑 clave de sesión única
    
    
    with connection.cursor() as cursor:
        cursor.execute("""
    INSERT INTO sessions (session_id, name, email, mailorigen, idioma,origen, bd, email_user, email_password, url_contacto, url_ofertas, url_proformas, url_actualizar_contacto, url_form_contacto, api_key, environment, send_email,send_wellcome_email)
            VALUES   (%s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s)
        """, (session_id, name, email, mailorigen, idioma,origen, bd, email_user, email_password, url_contacto, url_ofertas, url_proformas, url_actualizar_contacto, url_form_contacto, api_key, environment, send_email, send_wellcome_email))
    connection.commit()

    return session_id



def actualizar_contacto_service(data: dict) -> dict:
    """
    Contiene TODA la lógica actual de actualizar_contacto,
    pero SIN request.get_json() y SIN depender de Flask.
    """
   

       

    global BD, EMAIL_USER, EMAIL_PASSWORD, URL_CONTACTO, URL_OFERTAS, API_KEY, ENVIRONMENT, SEND_EMAIL,SEND_WELLCOME_EMAIL
    
   

    QuoteNo= data.get("QuoteNo")

    billToName = data.get("Name")
    Address = data.get("Address")
    Address2 = data.get("Address2")
    PostCode = data.get("PostCode")
    City = data.get("City")
    VATRegNo = data.get("VATRegNo")
    ForeignRegNo = data.get("ForeignRegNo")
    email=data.get("email")
    idioma=data.get("idioma")
    mailorigen=data.get("mailorigen", "web@planetpower.es") 
    BD = data.get("BD", "PRODUCCION")  # PRODUCCION o PRUEBAS
    EMAIL_USER = data.get("EMAIL_USER", "web@planetpower.es") 
    EMAIL_PASSWORD = data.get("EMAIL_PASSWORD", 'Ppt946682011') 
    URL_CONTACTO = data.get("URL_CONTACTO","https://rfg45eg4lk.execute-api.eu-north-1.amazonaws.com/prod/contacto")
    URL_OFERTAS = data.get("URL_OFERTAS", "https://tx3fc457zf.execute-api.eu-north-1.amazonaws.com/prod/oferta")
    URL_PROFORMAS = data.get("URL_PROFORMAS", "https://tx3fc457zf.execute-api.eu-north-1.amazonaws.com/prod/proforma")
    URL_ACTUALIZAR_CONTACTO = data.get("URL_ACTUALIZAR_CONTACTO", "https://rfg45eg4lk.execute-api.eu-north-1.amazonaws.com/prod/actualizar_contacto")
    URL_FORMCONTACTO= data.get("URL_FORMCONTACTO", "https://rfg45eg4lk.execute-api.eu-north-1.amazonaws.com") 
    ENVIRONMENT = data.get("ENVIRONMENT", "Production") 
    SEND_EMAIL= data.get("SEND_EMAIL", True) 
    session_id = data.get("session_id", str(uuid.uuid4()))  # Si no viene, generar uno nuevo (aunque idealmente siempre debería venir)

    
    hdrs = { (k or "").lower(): v for k, v in (data.get("headers") or {}).items() }
    API_KEY = hdrs.get("x-api-key")
    if not API_KEY:
        API_KEY = "gdZgiMt2FD79LrR2opX9gxitgJQfB9X2OkP7dn3i"



    print(f"""Datos recibidos: {QuoteNo}, {billToName}, {Address}, {Address2}, {PostCode}, {City}, {VATRegNo},  {ForeignRegNo}, {mailorigen},{email}, {idioma},
        {BD}, {EMAIL_USER},  {URL_CONTACTO}, {URL_OFERTAS}, {URL_PROFORMAS}, {URL_ACTUALIZAR_CONTACTO}, {URL_FORMCONTACTO}, {ENVIRONMENT}, {SEND_EMAIL}""")


    name=billToName
    
    origen=""
    bd=BD
    email_user=EMAIL_USER
    email_password=EMAIL_PASSWORD
    url_contacto=URL_CONTACTO
    url_ofertas=URL_OFERTAS
    url_proformas=URL_PROFORMAS
    url_actualizar_contacto=URL_ACTUALIZAR_CONTACTO
    url_form_contacto=URL_FORMCONTACTO
    api_key=API_KEY 
    environment=ENVIRONMENT
    send_email=SEND_EMAIL
    send_wellcome_email= ""


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
    


    
    #session_id= store_session(connection,name, email, mailorigen, idioma, origen, bd, email_user, email_password, url_contacto, url_ofertas,url_proformas, 
    #                          url_actualizar_contacto, url_form_contacto, api_key, environment, send_email,send_wellcome_email)

    #codigo_pais, mercado, zona = obtener_datos_pais (pais, idioma)

    #if (idioma == "Español") or (idioma == "Esp"):
    #    codigo_idioma = "ESP"
    #else:
    #    codigo_idioma = "ENU"




        


    token=get_token()

    QuoteNo = update_contact_salesheader(token, QuoteNo, billToName,Address, Address2, PostCode, City, VATRegNo, ForeignRegNo)

    actualizar_sales_header(connection,session_id, QuoteNo)

    send_proforma_invoice_to_lambda(token, QuoteNo, session_id, url_proformas, bd)
    


    return {"ok": True, "message": "Factura Proforma Generada "}
    



def _curl_patch(url, headers, payload_dict):
    buf = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.CUSTOMREQUEST, "PATCH")
    c.setopt(c.POSTFIELDS, json.dumps(payload_dict))
    c.setopt(c.HTTPHEADER, headers)
    c.setopt(c.WRITEDATA, buf)
    c.perform()
    status = c.getinfo(pycurl.RESPONSE_CODE)
    c.close()
    body = buf.getvalue().decode("utf-8")
    return status, body


def create_quote_lines(token, name, email, customer_template, customer_country_code, lines=[]):
    """
    Crea un contacto y una oferta en Business Central.
    
    Args:
        token (str): Token de acceso para autenticar la solicitud.
        name (str): Nombre del contacto.
        email (str): Email del contacto.
        customer_template (str): Plantilla de cliente a usar.
        
    Returns:
        dict: Información de la oferta creada.
    """
    
   
    url = f"https://api.businesscentral.dynamics.com/v2.0/{TENANT_ID}/{ENVIRONMENT}/api/planet/sales/v1.0/quoteLines?company=PLANET"

    

    
    

    headers = [
        f"Authorization: Bearer {token}",
        "Content-Type: application/json",
        "Accept: application/json",
       
    ]


    for line in lines:
        try:
            postfields = json.dumps(line) 

            buffer = BytesIO()
            c = pycurl.Curl()
            c.setopt(c.URL, url)
            c.setopt(c.POST, 1)
            c.setopt(c.POSTFIELDS, postfields)
            c.setopt(c.HTTPHEADER, headers)
            c.setopt(c.WRITEDATA, buffer)
            c.perform()
            status_code = c.getinfo(pycurl.RESPONSE_CODE)
            c.close()

            response_body = buffer.getvalue().decode('utf-8')
            

            print(f"📤 Enviando datos a BC: {postfields}")
            print(f"📥 Respuesta completa de BC: {response_body}")
            print(f"📟 Código de estado: {status_code}")

            # Optional: detener si hay error
            if status_code >= 400:
                print("❌ Error al crear línea. Deteniendo Ngrok.")
                break

        except Exception as e:
            print(f"❌ Excepción al enviar línea: {e}")



def obtener_datos_pais(connection, pais, idioma):

    

    LABEL_TO_SLUG = {
    'Español': 'es',
    'Esp': 'es',
    'Ingles': 'en',
    'Frances': 'fr',
    'Italiano': 'it',
}

    slug = LABEL_TO_SLUG.get(idioma, 'es')  # fallback 'es'

    # Paso 2: slug -> columna
    COL_BY_LANG = {
        'es': 'pais_es',
        'en': 'pais_en',
        'fr': 'pais_fr',
        'it': 'pais_it',
    }
    col = COL_BY_LANG[slug]

    print(f"Buscando en columna '{col}' para idioma '{idioma}' (slug '{slug}') el país '{pais}'")
   
    
    with connection.cursor() as cursor:
        sql = f"""
            SELECT codigo_pais, zona, mercado
            FROM pais
            WHERE {col} = %s
            LIMIT 1
        """
        cursor.execute(sql, (pais,))
        result = cursor.fetchone()

    
    print("DEBUG result:", result, type(result))
    if result:
    # Si el cursor devuelve dict (DictCursor), sacamos por clave
        if isinstance(result, dict):
            codigo_pais = result.get("codigo_pais")
            zona = result.get("zona")
            mercado = result.get("mercado")
        else:
            # Si devuelve tupla normal
            codigo_pais, zona, mercado = result

        print(f"Datos obtenidos: {codigo_pais}, {zona}, {mercado}")
        return codigo_pais, mercado, zona
    else:
        return None, None, None


def obtener_descuento(zona, pistas_perimetrales, pistas_laterales, descuento_adicional=0):

    creds = get_db_credentials()
    dbname = "bc_pruebas" if (BD == "PRUEBAS") else creds["dbname"]

    connection = pymysql.connect(
        host=creds['host'],
        user=creds['username'],
        password=creds['password'],
        database=dbname,
        port=int(creds.get('port', 3306))
    )

    cantidad = pistas_perimetrales + pistas_laterales

    try:
        with connection.cursor() as cursor:

            # --- Descuento por zona ---
            cursor.execute("""
                SELECT descuento
                FROM zonas_descuento
                WHERE zona = %s
                LIMIT 1
            """, (zona,))
            row = cursor.fetchone()
            descuento_zona = row[0] if row else 0

            # --- Descuento por cantidad ---
            cursor.execute("""
                SELECT descuento
                FROM descuentos_cantidad
                WHERE %s BETWEEN cantidad_min AND cantidad_max
                LIMIT 1
            """, (cantidad,))
            row = cursor.fetchone()
            descuento_cantidad = row[0] if row else 0

    finally:
        connection.close()

    # ✅ Convertir TODO a Decimal
    cien = Decimal("100")
    descuento_zona = Decimal(str(descuento_zona or 0))
    descuento_cantidad = Decimal(str(descuento_cantidad or 0))
    descuento_adicional = Decimal(str(descuento_adicional or 0))

    # ✅ Fórmula sin mezcla float/Decimal
    descuento_total_decimal = (
        cien - (
            (cien - descuento_zona)
            * (cien - descuento_cantidad)
            * (cien - descuento_adicional)
            / cien / cien
        )
    )

    # Redondeo final
    descuento_total_entero = int(
        descuento_total_decimal.quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP
        )
    )

    print(
        f"Zona: {descuento_zona} | "
        f"Cantidad: {descuento_cantidad} | "
        f"Adicional: {descuento_adicional} | "
        f"TOTAL: {descuento_total_entero}"
    )

    return descuento_total_entero



def obterner_productos():
    """
    Obtiene los precios de los productos desde la base de datos.
    """
    creds = get_db_credentials()

    
    dbname = "bc_pruebas" if (BD== "PRUEBAS") else creds["dbname"]

    print ("BD", BD)  
    
    #print(f"Credenciales obtenidas: {creds}")
    print(f"Conectando a la base de datos con host: {creds['host']}, usuario: {creds['username']}, base de datos: {dbname}")
    

    connection = pymysql.connect(
        host=creds['host'],
        user=creds['username'],
        password=creds['password'],
        database= dbname,
        port=int(creds.get('port', 3306))
    )

    try:
        with connection.cursor() as cursor:
            sql = "SELECT codigo, descripcion, precio FROM productos"
            cursor.execute(sql)
            resultados = cursor.fetchall()

            # Convertir a lista de diccionarios
            lista_productos = []
            for fila in resultados:
                producto = {
                    "codigo": fila[0],
                    "descripcion": fila[1],
                    "precio": float(fila[2])
                }
                lista_productos.append(producto)

            print(lista_productos)  # O devuélvelo desde una función

    finally:
        connection.close()

    return lista_productos  # O devuelve la lista de productos

def buscar_producto_por_codigo(codigo_busqueda, lista_productos):
    for producto in lista_productos:
        if producto["codigo"] == codigo_busqueda:
            return producto["descripcion"], producto["precio"]
    return None, None  # Si no se encuentra





def guardar_porcentaje_descuento_session (porcentaje_descuento,session_id):
    creds = get_db_credentials()

    
    dbname = "bc_pruebas" if (BD== "PRUEBAS") else creds["dbname"]

    print ("BD", BD)  
    #print(f"Credenciales obtenidas: {creds}")
    print(f"Conectando a la base de datos con host: {creds['host']}, usuario: {creds['username']}, base de datos: {dbname}")
    

    connection = pymysql.connect(
        host=creds['host'],
        user=creds['username'],
        password=creds['password'],
        database= dbname,
        port=int(creds.get('port', 3306))
    )



    try:
        with connection.cursor() as cursor:
            sql = """
            UPDATE sessions
            SET descuento_total = %s
            WHERE session_id = %s
            """
            cursor.execute(sql, (porcentaje_descuento, session_id))

        connection.commit()
        print("✅ Descuento actualizado correctamente")
    finally:
        connection.close()

def guardar_cantidad_total_session (total,session_id):
    creds = get_db_credentials()

    
    dbname = "bc_pruebas" if (BD== "PRUEBAS") else creds["dbname"]
    print ("BD", BD)  
    
    #print(f"Credenciales obtenidas: {creds}")
    print(f"Conectando a la base de datos con host: {creds['host']}, usuario: {creds['username']}, base de datos: {dbname}")
    

    connection = pymysql.connect(
        host=creds['host'],
        user=creds['username'],
        password=creds['password'],
        database= dbname,
        port=int(creds.get('port', 3306))
    )

    print ("CANTIDAD TOTAL A GUARDAR ", total  )

    try:
        with connection.cursor() as cursor:
            sql = """
            UPDATE sessions
            SET cantidad_total = %s
            WHERE session_id = %s
            """
            cursor.execute(sql, (total, session_id))

        connection.commit()
        print("✅ Cantidad Total actualizada correctamente")
    finally:
        connection.close()




def obtener_descuento_cantidad_total(connection, session_id):
   
    with connection.cursor() as cursor:
        sql = """
        SELECT descuento_total, cantidad_total
        FROM sessions
        WHERE session_id = %s
        """
        cursor.execute(sql, (session_id,))
        result = cursor.fetchone()

    if result:
        # Si es dict
        if isinstance(result, dict):
            descuento_total = result.get("descuento_total")
            cantidad_total = result.get("cantidad_total")
        else:
            # Si es tupla
            descuento_total, cantidad_total = result

        return {
            "session_id": session_id,
            "descuento_total": float(descuento_total or 0),
            "cantidad_total": float(cantidad_total or 0)
        }

    return None



def ensamblar_oferta (codigo_pais,zona,idioma, pistas_perimetrales, pistas_laterales, SalesHeaderNumber, session_id, descuento_adicional=0, incluir_transporte=False, importe_transporte=0  ):
    """
    Ensambla una oferta basada en los parámetros proporcionados.    
    Args:
        pais (str): País del cliente.
        idioma (str): Idioma preferido.         
        pistas_perimetrales (int): Número de pistas perimetrales.
        pistas_laterales (int): Número de pistas laterales.
    Returns:        
        list: Lista de líneas de oferta ensambladas.    
    """
    # Aquí puedes implementar la lógica para ensamblar la oferta
    # Basado en los parámetros recibidos, por ejemplo:

    print("Ensamblando oferta con los siguientes Idioma:", idioma)
   

    porcentaje_descuento = math.ceil(round(obtener_descuento(zona,pistas_perimetrales, pistas_laterales,descuento_adicional) , 1))

    guardar_porcentaje_descuento_session (porcentaje_descuento,session_id)
    
    lista_productos = obterner_productos()
    numerolinea = 10000
    lineas = []
   
    if codigo_pais != "US":
        if pistas_perimetrales != 0:
            codigo= "P-ELI-12-5K60-R50CE"
            descripcion, precio = buscar_producto_por_codigo(codigo, lista_productos)

            lineas.append ({
                    "type": "Item",
                    "documentNo": SalesHeaderNumber,
                    "lineNo": numerolinea,
                    #"description": descripcion,
                    "itemNo": codigo,
                    "linediscount": porcentaje_descuento,
                    "quantity": pistas_perimetrales,

                    #"unitPrice": precio,
                })
          
            if pistas_laterales != 0:
                numerolinea = 20000
                codigo= "P-ELI-8-5K60-R50CE"
                descripcion, precio = buscar_producto_por_codigo(codigo, lista_productos)
                lineas.append  ({
                        "type": "Item",
                        "documentNo": SalesHeaderNumber,
                        "lineNo": numerolinea,
                        #"description": descripcion,
                        "itemNo": codigo,
                        "linediscount": porcentaje_descuento,
                        "quantity": pistas_laterales,
                        #"unitPrice": precio,
                    })
                
                



        else:
            codigo= "P-ELI-8-5K60-R50CE"
            descripcion, precio = buscar_producto_por_codigo(codigo, lista_productos)

            lineas.append ({
                    "type": "Item",
                    "documentNo": SalesHeaderNumber,
                    "lineNo": numerolinea,
                    #"description": descripcion,
                    "itemNo": codigo,
                    "linediscount": porcentaje_descuento,
                    "quantity": pistas_laterales,
                    #"unitPrice": precio,
                })
            

    else :
        if pistas_perimetrales != 0:
            codigo= "P-ELI-12-5K-60-R50UL"
            descripcion, precio = buscar_producto_por_codigo(codigo, lista_productos)
            lineas.append  ({
                    "type": "Item",
                    "documentNo": SalesHeaderNumber,
                    "lineNo": numerolinea,
                    #"description": descripcion,
                    "itemNo": codigo,
                    "linediscount": porcentaje_descuento,
                    "quantity": pistas_perimetrales,
                    #"unitPrice": precio,
                })
            
            if pistas_laterales != 0:
                numerolinea = 20000
                codigo= "P-ELI-8-5K-60-R50UL"
                descripcion, precio = buscar_producto_por_codigo(codigo, lista_productos)
                lineas.append  ({
                    "type": "Item",
                    "documentNo": SalesHeaderNumber,
                    "lineNo": numerolinea,
                    #"description": descripcion,
                    "itemNo": codigo,
                    "linediscount": porcentaje_descuento,
                    "quantity": pistas_laterales,
                    #"unitPrice": precio,
                })
            
                
        else:
            codigo= "P-ELI-8-5K60-R50UL"
            descripcion, precio = buscar_producto_por_codigo(codigo, lista_productos)

            lineas.append  ({
                    "type": "Item",
                    "documentNo": SalesHeaderNumber,
                    "lineNo": numerolinea,
                    #"description": descripcion,
                    "itemNo": codigo,
                    "linediscount": porcentaje_descuento,
                    "quantity": pistas_laterales,
                    #"unitPrice": precio,
                })
            

    
    if (pistas_perimetrales != 0) :
        codigo= "KIT-INS-ELI-C2-12-25"
        numerolinea += 10000

        descripcion, precio = buscar_producto_por_codigo(codigo, lista_productos)

        lineas.append  ({
                "type": "Item",
                "documentNo": SalesHeaderNumber,
                "lineNo": numerolinea,
                #"description": descripcion,
                "itemNo": codigo,
                "linediscount": porcentaje_descuento,
                "quantity": pistas_perimetrales,
                #"unitPrice": precio,
            })
        
        

    if (pistas_laterales != 0) :
        codigo= "KIT-INST-ELI-C2-8"
        numerolinea += 10000

        descripcion, precio = buscar_producto_por_codigo(codigo, lista_productos)

        lineas.append  ({
                "type": "Item",
                "documentNo": SalesHeaderNumber,
                "lineNo": numerolinea,
                #"description": descripcion,
                "itemNo": codigo,
                "linediscount": porcentaje_descuento,
                "quantity": pistas_laterales,
                #"unitPrice": precio,
            })
        
        

      
    if codigo_pais != "US": 
        codigo= "S-REG-BL-DALI-CE"
        numerolinea += 10000
        cantidad = (pistas_laterales*2) +pistas_perimetrales
        descripcion, precio = buscar_producto_por_codigo(codigo, lista_productos)

        lineas.append ({
                "type": "Item",
                "documentNo": SalesHeaderNumber,
                "lineNo": numerolinea,
                #"description": descripcion,
                "itemNo": codigo,
                "linediscount": porcentaje_descuento,
                "quantity": cantidad,
                #"unitPrice": precio,
            })
        
        

        
    else :  
        
        codigo= "S-REG-BL-DALI-UL"
        numerolinea += 10000
        cantidad = (pistas_laterales*2)+pistas_perimetrales
        descripcion, precio = buscar_producto_por_codigo(codigo, lista_productos)

        lineas.append  ({
                "type": "Item",
                "documentNo": SalesHeaderNumber,
                "lineNo": numerolinea,
                #"description": descripcion,
                "itemNo": codigo,
                "linediscount": porcentaje_descuento,
                "quantity": cantidad,
                #"unitPrice": precio,
            })
        
        
        

    codigo= "HBGW01"
    numerolinea += 10000
    
    descripcion, precio = buscar_producto_por_codigo(codigo, lista_productos)

    lineas.append  ({
            "type": "Item",
            "documentNo": SalesHeaderNumber,
            "lineNo": numerolinea,
            #"description": descripcion,
            "itemNo": codigo,
            "linediscount": porcentaje_descuento,
            "quantity": 1,
            #"unitPrice": precio,
        })
    numerolinea += 10000
    lineas.append ({
        #"type": "Item",
        "documentNo": SalesHeaderNumber,
        "lineNo": numerolinea,
        "description": "",
        
        })
    
    
    
    

   
    numerolinea += 10000
    if (idioma == "Español") or (idioma == "Esp"):
        if (incluir_transporte):

            descripcion = "TRANSPORTE PUERTA A PUERTA"
            
            lineas.append  ({
                "type": "Charge (Item)",
                "itemNo": 'C-TR',
                "documentNo": SalesHeaderNumber,
                "lineNo": numerolinea,
                "description": descripcion,
                "quantity": 1,
                "unitPrice": importe_transporte,        
                })
          
        else:
            descripcion = "EL TRANSPORTE NO ESTA INCLUIDO FUERA DE LA PENINSULA IBERICA"
            
            lineas.append  ({
                #"type": "Item",
                "documentNo": SalesHeaderNumber,
                "lineNo": numerolinea,
                "description": descripcion,
                
                
                })


    else:

        if (incluir_transporte):

            descripcion = "TRANSPORT DOOR TO DOOR"
            
            lineas.append  ({
                "type": "Charge (Item)",
                "itemNo": 'C-TR',
                "documentNo": SalesHeaderNumber,
                "lineNo": numerolinea,
                "description": descripcion,
                "quantity": 1,
                "unitPrice": importe_transporte,        
                })
        
        else:
            descripcion =  "TRANSPORT NOT INCLUDED OUTSIDE THE IBERIAN PENINSULA"
            
            lineas.append  ({
                #"type": "Item",
                "documentNo": SalesHeaderNumber,
                "lineNo": numerolinea,
                "description": descripcion,
                
                
                })






       
    
    if (idioma == "Español") or (idioma == "Esp")   :
         descripcion = "EL TUBO 4040 PARA LA INSTALACION DE LA PISTA NO ESTA INCLUIDO"
         
    else:
        descripcion = "THE 4040 TUBE FOR INSTALLING THE COURT IS NOT INCLUDED"
    numerolinea += 10000
    lineas.append ({
        #"type": "Item",
        "documentNo": SalesHeaderNumber,
        "lineNo": numerolinea,
        "description": descripcion,
        
        })
    if (idioma == "Español") or (idioma == "Esp")   :
        descripcion = (
            "Más info:https://f.crmplanetpower.es/4040es.pdf "
            
        )
    else:
        descripcion = (
            "More info:https://f.crmplanetpower.es/4040en.pdf"
           
        )
    numerolinea += 10000

    print("URL_OFERTAS", URL_OFERTAS)
    lineas.append ({
        #"type": "Item",
        "documentNo": SalesHeaderNumber,
        "lineNo": numerolinea,
        "description": descripcion,
        "session_id": session_id,

        "isLastLine": True,
        "url": URL_OFERTAS,
        "bd" : BD
        
        })    

    return lineas


    



def create_contact_salesheader(token, name, email, customer_template,  cod_idioma, cod_pais):

    print("Creando contacto y oferta en BC...")
    print (f"Datos: {name}, {email}, {customer_template}, {cod_idioma}, {cod_pais}")

    print (TENANT_ID,ENVIRONMENT, COMPANY_ID)

   
   
    url = f"https://api.businesscentral.dynamics.com/v2.0/{TENANT_ID}/{ENVIRONMENT}/ODataV4/Company('{COMPANY_ID}')/createQuotes"
    headers = [
            f"Authorization: Bearer {token}",
            "Content-Type: application/json"
        ]
        
    data = {
            "CustomerName": name,
            "CustomerEmail": email,
            "CustomerTemplate": customer_template,
            "CustomerCountryCode": cod_pais,
            "CodIdioma": cod_idioma,
            "skipHeaderDiscounts": True,
           
        }
    postfields = json.dumps(data)
        
    
    buffer = BytesIO()

    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.POST, 1)
    c.setopt(c.POSTFIELDS, postfields)

    # Configurar encabezados

    c.setopt(c.HTTPHEADER, headers)

    # Capturar la respuesta
    c.setopt(c.WRITEDATA, buffer)

    # Ejecutar la solicitud
    c.perform()

    status_code = c.getinfo(pycurl.RESPONSE_CODE)

    # Cerrar Curl
    c.close()

    response_body = buffer.getvalue().decode('utf-8')

    print(f"Status code: {status_code}")
    print(f"Response body: {response_body}")



    if status_code not in [200, 201]:
        print(f"❌ Error al crear la oferta: {status_code}")
        print("Cuerpo de respuesta de la funcion :", response_body)
        return None

    try:
        quote = json.loads(response_body)
        print(f"✅ Oferta creada: {quote.get('No')}")
        return (quote.get('No'))
        
    except Exception as e:
        print("❌ Error al interpretar JSON:", e)
        print("Cuerpo recibido:", response_body)
        return None
        




def update_contact_salesheader(token,QuoteNo,billToName, Address, Address2, PostCode, City, VATRegNo, ForeignRegNo):

    print("Creando contacto y proforma en BC...")
    print (f"Datos: {QuoteNo},{billToName}, {Address}, {Address2}, {PostCode}, {City}, {VATRegNo}, {ForeignRegNo}")

    print (TENANT_ID,ENVIRONMENT, COMPANY_ID)

    

   
   
    url = f"https://api.businesscentral.dynamics.com/v2.0/{TENANT_ID}/{ENVIRONMENT}/ODataV4/Company('{COMPANY_ID}')/updateContacts"
    headers = [
            f"Authorization: Bearer {token}",
            "Content-Type: application/json"
        ]
        
    data = {
        "QuoteNo": QuoteNo,
        "billToName": billToName,
        "Address": Address,
        "Address2": Address2,
        "PostCode": PostCode,
        "City": City,
        "VATRegNo": VATRegNo,
        "ForeignRegNo": ForeignRegNo
                     
        }
    postfields = json.dumps(data)
        
    
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.POST, 1)
    c.setopt(c.POSTFIELDS, postfields)

    # Configurar encabezados

    c.setopt(c.HTTPHEADER, headers)

    # Capturar la respuesta
    c.setopt(c.WRITEDATA, buffer)

    # Ejecutar la solicitud
    c.perform()

    status_code = c.getinfo(pycurl.RESPONSE_CODE)

    # Cerrar Curl
    c.close()

    response_body = buffer.getvalue().decode('utf-8')

    print(f"Status code: {status_code}")
    print(f"Response body: {response_body}")



    if status_code not in [200, 201]:
        print(f"❌ Error al crear la oferta: {status_code}")
        print("Cuerpo de respuesta de la funcion :", response_body)
        return None

    try:
        quote = json.loads(response_body)
        print(f"✅ Factura creada: {quote.get('quoteNo')}")
        return (quote.get('quoteNo'))
        
    except Exception as e:
        print("❌ Error al interpretar JSON:", e)
        print("Cuerpo recibido:", response_body)
        return None
        


def send_proforma_invoice_to_lambda(token, QuoteNo, session_id, url_proformas, bd):

    print("Generando factura en BC y enviando datos a Lambda...")
    print (f"Datos: {QuoteNo}, {session_id}, {url_proformas}, {bd}")

    print (TENANT_ID,ENVIRONMENT, COMPANY_ID)

    

   
   
    url = f"https://api.businesscentral.dynamics.com/v2.0/{TENANT_ID}/{ENVIRONMENT}/ODataV4/Company('{COMPANY_ID}')/sendProformas"

    headers = [
            f"Authorization: Bearer {token}",
            "Content-Type: application/json"
        ]
        
    

    data = {
        "QuoteNo": QuoteNo,
        "SessionId": session_id,                # el que uses en tu flujo
        "url": url_proformas,     # endpoint lambda proforma
        "bd": bd
        }

    postfields = json.dumps(data)
        
    
    buffer = BytesIO()

    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.POST, 1)
    c.setopt(c.POSTFIELDS, postfields)

    # Configurar encabezados

    c.setopt(c.HTTPHEADER, headers)

    # Capturar la respuesta
    c.setopt(c.WRITEDATA, buffer)

    # Ejecutar la solicitud
    c.perform()

    status_code = c.getinfo(pycurl.RESPONSE_CODE)

    # Cerrar Curl
    c.close()

    response_body = buffer.getvalue().decode('utf-8')

    print(f"Status code: {status_code}")
    print(f"Response body: {response_body}")



    if status_code not in [200, 201]:
        print(f"❌ Error al crear la oferta: {status_code}")
        print("Cuerpo de respuesta de la funcion :", response_body)
        return None

    try:
        quote = json.loads(response_body)
        print(f"✅ Factura Proforma creada: {QuoteNo}")
        return (quote.get('No'))
        
    except Exception as e:
        print("❌ Error al interpretar JSON:", e)
        print("Cuerpo recibido:", response_body)
        return None



def consume_token(conn, token: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("""
            DELETE FROM reset_token
            WHERE token=%s
              AND user_id=0
              AND expires_at > NOW()
        """, (token,))
        return cur.rowcount == 1





def insert_base_datos( connection,lead):

     # Extrae valores del payload
       
        fecha_actual            = lead.fecha_actual        # str 'YYYY-MM-DD' o None
        origen                  = lead.origen              # str o None
        name                    = lead.name                # str o None
        email                   = lead.email               # str o None
        quote_number            = lead.quote_number        # str o None
        idioma                  = lead.idioma              # str o None
        pais                    = lead.pais                # str o None
        descuento_adicional     = lead.descuento_adicional
        descuento_total         = lead.descuento_total
        cantidad_total          = lead.cantidad_total
        estado                  = lead.estado
        tipo_lead               = lead.tipo_lead
        pistas_perimetrales     = lead.pistas_perimetrales
        pistas_laterales        = lead.pistas_laterales
        incluir_transporte      = lead.incluir_transporte
        importe_transporte      = lead.importe_transporte   

        print (f"Datos para insertar en BD: {fecha_actual}, {origen}, {name}, {email}, {quote_number}, {idioma}, {pais}, {descuento_adicional},{tipo_lead}, {descuento_total}, {cantidad_total}, {estado}, {pistas_perimetrales}, {pistas_laterales} {incluir_transporte}, {importe_transporte} ")

        # --- Inserción ---
        sql = """
        INSERT INTO lead_forms (
          fecha_actual, origen,
          name, email, quote_number, idioma, pais, tipo_lead,
          descuento_adicional, descuento_total, cantidad_total,
          estado,pistas_perimetrales, pistas_laterales,incluir_transporte, importe_transporte
          
        ) VALUES (
          %(fecha_actual)s, %(origen)s, 
          %(name)s, %(email)s, %(quote_number)s, %(idioma)s, %(pais)s, %(tipo_lead)s,
          %(descuento_adicional)s, %(descuento_total)s, %(cantidad_total)s,
          %(estado)s, %(pistas_perimetrales)s, %(pistas_laterales)s, %(incluir_transporte)s, %(importe_transporte)s
          
        )
        """

        params = {
            "origen": origen,
            "fecha_actual": fecha_actual,            
            "name": name,
            "email": email,
            "quote_number": quote_number,
            "idioma": idioma,
            "pais": pais,
            "tipo_lead": tipo_lead, 
            "descuento_adicional": descuento_adicional,
            "descuento_total": descuento_total,
            "cantidad_total": cantidad_total,
            "estado": estado,
            "pistas_perimetrales": pistas_perimetrales,
            "pistas_laterales": pistas_laterales,
            "incluir_transporte": incluir_transporte,
            "importe_transporte": importe_transporte    
        }


        try:
            
            with connection.cursor() as cur:
                cur.execute(sql, params)
               
            connection.commit()
            print("✅ Datos insertados en la base de datos")
        except pymysql.connect.Error as db_err:
            print(f"❌ Error de conexión a la base de datos: {db_err}")
            # Detalle controlado para el cliente
            return {"ok": False, "error": f"DB: {db_err}"}
       

import json
import base64

def _get_token_from_event(event):
    method = ((event.get("requestContext", {}).get("http", {}) or {}).get("method") or event.get("httpMethod") or "").upper()

    if method == "GET":
        qs = event.get("queryStringParameters") or {}
        return (qs.get("token") or "").strip()

    # POST: JSON en body (base64 o no)
    body = event.get("body")
    if not body:
        return ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8", errors="strict")
    try:
        data = json.loads(body)
        return (data.get("token") or "").strip()
    except Exception:
        return ""

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

def _parse_json_body(event):
    raw = event.get("body")
    if not raw:
        return {}
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    return json.loads(raw)

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

def _html_response(status: int, html: str):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
        },
        "body": html,
    }



def lambda_handler(event, context):
   
    try:
        method, path = _get_route(event)

        # CORS preflight
        if method == "OPTIONS":
            return _json_response(200, {"ok": True})

        # Quita el stage (/prod) del path en REST API
        stage = event.get("requestContext", {}).get("stage")
        if stage and path.startswith(f"/{stage}/"):
            path = path[len(stage) + 1:]  # deja /actualizar_contacto, /contacto, etc.

        payload = _parse_json_body(event)
        route_key = f"{method} {path}"

        # Legacy (en explotación)
        if route_key == "POST /procesarFormularioContacto":
           
            result = crear_contacto_core(payload)
            return _json_response(200, result)
        # Nuevo crear
        if route_key == "POST /contacto":
            
            result = crear_contacto_core(payload)
            return _json_response(200, result)

        # Nuevo actualizar
        if route_key == "POST /actualizar_contacto":

            print("Ruta /actualizar_contacto recibida con payload:", payload)
           
            return _json_response(200, actualizar_contacto_service(payload))
        
        if route_key == "POST /proforma_submit":
            payload = _parse_json_body(event)  # o el parser que ya tienes
            result, status = proforma_submit_core(payload)
            return _json_response(status, result)
            
            
        if route_key == "GET /proforma_form":
            token = _get_token_from_event(event)
            body, status, ct = proforma_form_service(token)

            if ct.startswith("text/html"):
                return _html_response(status, body)

            # si es error JSON
            return {
                "statusCode": status,
                "headers": {"Content-Type": ct, "Access-Control-Allow-Origin": "*"},
                "body": body,
            }

        return _json_response(404, {"ok": False, "error": "Ruta no encontrada", "routeKey": route_key})
    

    except json.JSONDecodeError:
        return _json_response(400, {"ok": False, "error": "JSON inválido"})
    except Exception as e:
        return _json_response(500, {"ok": False, "error": "Error interno", "detail": str(e)})


def crear_contacto_core(data):
    #print("Evento recibido:", event)

    """Endpoint para crear un contacto y una oferta en Business Central."""

   
    

    

    global BD, EMAIL_USER, EMAIL_PASSWORD, URL_CONTACTO, URL_OFERTAS, API_KEY, ENVIRONMENT, SEND_EMAIL,SEND_WELLCOME_EMAIL

  

    

    
    
    

    origen= data.get("origen")
    name = data.get("name")
    email = data.get("email")
    pais = data.get("pais")
    idioma = data.get("idioma")
    descuento_adicional = data.get("descuento_adicional", 0)    
    mailorigen=data.get("mailorigen", "web@planetpower.es") 
    pistas_perimetrales = data.get("pistas_perimetrales")
    pistas_laterales = data.get("pistas_laterales")
    tipo_lead = data.get("tipo_lead", "Sin calificar")
    incluir_transporte = data.get("incluir_transporte", False)
    importe_transporte = data.get("importe_transporte", 0)
    BD = data.get("BD", "PRODUCCION")  # PRODUCCION o PRUEBAS
    EMAIL_USER = data.get("EMAIL_USER", "web@planetpower.es") 
    EMAIL_PASSWORD = data.get("EMAIL_PASSWORD", 'Ppt946682011') 
    URL_CONTACTO = data.get("URL_CONTACTO","https://rfg45eg4lk.execute-api.eu-north-1.amazonaws.com/prod/contacto")
    URL_OFERTAS = data.get("URL_OFERTAS", "https://tx3fc457zf.execute-api.eu-north-1.amazonaws.com/prod/oferta")
    URL_PROFORMAS = data.get("URL_PROFORMAS", "https://tx3fc457zf.execute-api.eu-north-1.amazonaws.com/prod/proforma")
    URL_ACTUALIZAR_CONTACTO = data.get("URL_ACTUALIZAR_CONTACTO", "https://rfg45eg4lk.execute-api.eu-north-1.amazonaws.com/prod/actualizar_contacto")
    URL_FORMCONTACTO= data.get("URL_FORMCONTACTO", "https://rfg45eg4lk.execute-api.eu-north-1.amazonaws.com") 
    ENVIRONMENT = data.get("ENVIRONMENT", "Production") 
    SEND_EMAIL= data.get("SEND_EMAIL", True)
    SEND_WELLCOME_EMAIL = data.get("SEND_WELLCOME_EMAIL", True)
    hdrs = { (k or "").lower(): v for k, v in (data.get("headers") or {}).items() }
    API_KEY = hdrs.get("x-api-key")
    

    if not API_KEY:
        API_KEY = "gdZgiMt2FD79LrR2opX9gxitgJQfB9X2OkP7dn3i"

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


   


    print(f"""Datos recibidos : {name}, {email}, {pais}, {idioma}, {pistas_perimetrales}, {pistas_laterales}, {mailorigen}, {descuento_adicional}, {origen},
        {BD}, {EMAIL_USER},{URL_CONTACTO}, {URL_OFERTAS},{URL_PROFORMAS},{URL_ACTUALIZAR_CONTACTO},{URL_FORMCONTACTO} {ENVIRONMENT}, {SEND_EMAIL}, {SEND_WELLCOME_EMAIL}""")


    bd=BD
    email_user=EMAIL_USER
    email_password=EMAIL_PASSWORD
    url_contacto=URL_CONTACTO
    url_ofertas=URL_OFERTAS
    api_key=API_KEY
    url_proformas=URL_PROFORMAS
    url_actualizar_contacto= URL_ACTUALIZAR_CONTACTO
    url_form_contacto= URL_FORMCONTACTO
    environment=ENVIRONMENT
    send_email=SEND_EMAIL
    send_wellcome_email= SEND_WELLCOME_EMAIL

    session_id= store_session(connection,name, email, mailorigen, idioma, origen, bd, email_user, email_password, url_contacto, url_ofertas,url_proformas, 
                              url_actualizar_contacto, url_form_contacto, api_key, environment, send_email,send_wellcome_email)

    codigo_pais, mercado, zona = obtener_datos_pais (connection,pais, idioma)

    if idioma == "Español":
        codigo_idioma = "ESP"
    else:
        codigo_idioma = "ENU"

    print(f"Código de país: {codigo_pais}, Mercado: {mercado}, Zona: {zona}")

    customer_template = "QUOTELEAD E E"

    if mercado == 'NACIONAL':
        customer_template = "QUOTELEAD E E" 
    elif mercado == 'INTERNACIONAL' and (idioma == "Español" or idioma == "Esp"):
        customer_template = "QUOTELEAD I E"   
    elif mercado == 'INTERNACIONAL' and (idioma != "Español" and idioma != "Esp"):
        customer_template = "QUOTELEAD I I"
    elif mercado == 'UE' and (idioma != "Español" and idioma != "Esp"):
        customer_template = "QUOTELEAD U I"
    elif mercado == 'UE' and (idioma == "Español" or idioma == "Esp"):
        customer_template = "QUOTELEAD U E"

    print(f"Plantilla de cliente: {customer_template}")
   
  

    token=get_token()

    SalesHeaderNumber = create_contact_salesheader (token, name, email, customer_template, codigo_idioma, codigo_pais)

    actualizar_sales_header(connection,session_id, SalesHeaderNumber)


    


    lineas =ensamblar_oferta (codigo_pais,zona,idioma, pistas_perimetrales, pistas_laterales, SalesHeaderNumber,session_id, descuento_adicional,incluir_transporte, importe_transporte  )


    print(f"Líneas de oferta ensambladas: {lineas}")

    #token=get_token()
    #decode_token(token)
    quote = create_quote_lines(token, name, email, customer_template, pais, lineas)



    print(f"Oferta creada: {SalesHeaderNumber}")

    #token=get_token()
    #decode_token(token)
    #quote = create_contact_and_quote(token, name, email)

    #return jsonify({"message": "Contacto y oferta creados exitosamente"}), 200


    data=obtener_descuento_cantidad_total(connection,session_id)

    porcentaje_descuento = data["descuento_total"]
    total_amount_quote = data["cantidad_total"]

    print (f"Descuento total: {porcentaje_descuento}, Cantidad total: {total_amount_quote}")

   
   
    
    lead = SimpleNamespace(
                
                fecha_actual=date.today(),
                name=name,
                email=email,
                pais=pais,
                tipo_lead=tipo_lead,
                idioma=idioma,
                descuento_adicional=descuento_adicional,
                origen=origen,
                pistas_perimetrales=pistas_perimetrales,
                pistas_laterales=pistas_laterales,
                estado="Sin calificar",
                cantidad_total=float(total_amount_quote),
                descuento_total =  float(porcentaje_descuento),
                incluir_transporte=incluir_transporte,
                importe_transporte=importe_transporte,
                quote_number =  str(SalesHeaderNumber)

            )




    print (f"Lead para insertar en BD: {lead}")
    insert_base_datos(connection,lead)
            
        
            
    connection.close()
        
    
         
       


    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "message": "Contacto y oferta creados exitosamente",
            "quoteNumber": str(SalesHeaderNumber),
            "descuentoTotal": float(porcentaje_descuento),
            "cantidadTotal": float(total_amount_quote),
        }, ensure_ascii=False)
    }


def obtener_idioma_y_pais_por_oferta(quote_number: str, connection) -> dict | None:
    with connection.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("""
            SELECT idioma, pais, email
            FROM lead_forms
            WHERE quote_number = %s
            LIMIT 1
        """, (quote_number,))
        row = cursor.fetchone()

    if not row:
        print(f"[WARN] No hay datos en lead_forms para quote_number={quote_number}")
        return None

    print(
        f"Datos obtenidos para la oferta {quote_number}: "
        f"Idioma: {row.get('idioma')}, País: {row.get('pais')}, Email: {row.get('email')}"
    )

    return {
        "idioma": row.get("idioma") or "",
        "pais": row.get("pais") or "",
        "email": row.get("email") or "",
    }


def tipo_identificacion_por_pais_texto(pais_texto: str, connection) -> str:
    if not pais_texto:
        return "REGISTRO"

    p = re.sub(r"\s+", " ", pais_texto).strip()

    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("""
                SELECT codigo_pais, mercado
                FROM pais
                WHERE pais_es = %s OR pais_en = %s OR pais_fr = %s OR pais_it = %s
                LIMIT 1
            """, (p, p, p, p))
            row = cur.fetchone()
    except Exception as e:
        print(f"Error consultando paises: {e}")
        return "REGISTRO"

    if not row:
        return "REGISTRO"

    codigo_pais = (row.get("codigo_pais") or "").upper()
    mercado = (row.get("mercado") or "").upper()

    if codigo_pais == "ES" or mercado == "NACIONAL":
        return "NIF"
    if mercado == "UE":
        return "VAT"
    return "REGISTRO"





def proforma_form_service(token: str):
    if not token:
        print("[WARN] Falta el token.")
        return (
            
            json.dumps({"ok": False, "code": "MISSING_TOKEN", "message": "Falta el token."}, ensure_ascii=False),
            400,
            "application/json; charset=utf-8",
        )

    try:
        quote_number, BD, url_form_contacto, session_id = validate_token_and_get_quote(token)
        print(f"Token válido para quote_number={quote_number}, BD={BD}, session_id={session_id}")
    except SignatureExpired:
        return (
            json.dumps({"ok": False, "code": "EXPIRED", "message": "El enlace ha caducado."}, ensure_ascii=False),
            410,
            "application/json; charset=utf-8",
        )
    except BadSignature:
        return (
            json.dumps({"ok": False, "code": "INVALID", "message": "Token inválido."}, ensure_ascii=False),
            400,
            "application/json; charset=utf-8",
        )

    
    creds = get_db_credentials()
    dbname = "bc_pruebas" if (BD == "PRUEBAS") else creds["dbname"]

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
        if not token_exists_in_db(connection, token):
            print(f"[WARN] Token no válido o ya utilizado: {token}")
            return (
                json.dumps({"ok": False, "code": "NOT_FOUND", "message": "Enlace no válido o ya utilizado."},
                           ensure_ascii=False),
                410,
                "application/json; charset=utf-8",
            )

        datos_oferta = obtener_idioma_y_pais_por_oferta(quote_number, connection)
        if not datos_oferta:
            return (
                json.dumps({"ok": False, "code": "OFFER_NOT_FOUND", "message": "Oferta no encontrada."},
                           ensure_ascii=False),
                404,
                "application/json; charset=utf-8",
            )

        email = datos_oferta["email"]
        idioma = datos_oferta["idioma"]
        pais = datos_oferta["pais"]
        id_mode = tipo_identificacion_por_pais_texto(pais, connection)

    finally:
        connection.close()

    # render html
    template = env.get_template("proforma_public_es.html" if idioma in ("Español", "Esp") else "proforma_public_en.html")
    html = template.render(
        token=token,
        api_base_url=url_form_contacto,
        quote_number=quote_number,
        email=email,
        idioma=idioma,
        pais=pais,
        id_mode=id_mode,
    )
    return (html, 200, "text/html; charset=utf-8")


def proforma_submit_core(payload: dict):
    data = payload or {}

    token = (data.get("token") or "").strip()
    session_id_in = (data.get("session_id") or "").strip()

    if not token:
        return {"ok": False, "message": "Falta el token."}, 400

    # 1) Validar token (firma + max_age)
    try:
        quote_number, BD, url_form_contacto, session_id_token = validate_token_and_get_quote(token)
        session_id = session_id_token or session_id_in
    except SignatureExpired:
        return {"ok": False, "message": "El enlace ha caducado."}, 410
    except BadSignature:
        return {"ok": False, "message": "Token inválido."}, 400

    # 2) Validar campos mínimos del form
    required = ["name", "direccion1", "codigoPostal", "poblacion"]
    for k in required:
        if not (data.get(k) or "").strip():
            return {"ok": False, "message": f"Campo obligatorio: {k}"}, 400

    # Consumir token (one-time-use)
    creds = get_db_credentials()
    dbname = "bc_pruebas" if (BD == "PRUEBAS") else creds["dbname"]

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
        if not consume_token(connection, token):
            connection.rollback()
            return {"ok": False, "message": "Enlace no válido o ya utilizado."}, 410
        connection.commit()
    finally:
        connection.close()

    email = (data.get("email") or "").strip()
    idioma = (data.get("idioma", "Español") or "").strip()
    name = (data.get("name") or "").strip()
    Address = (data.get("direccion1") or "").strip()
    Address2 = (data.get("direccion2") or "").strip()
    PostCode = (data.get("codigoPostal") or "").strip()
    City = (data.get("poblacion") or "").strip()

    id_mode = (data.get("idMode") or "").upper()
    ident = (data.get("identificacion") or "").strip()
    n_reg = (data.get("nRegistro") or "").strip()

    VATRegNo = ""
    ForeignRegNo = ""
    if id_mode in ("NIF", "VAT"):
        VATRegNo = ident
    elif id_mode == "REGISTRO":
        ForeignRegNo = ident
    elif id_mode == "VAT+REGISTRO":
        VATRegNo = ident
        ForeignRegNo = n_reg
    else:
        VATRegNo = ident

    payload2 = {
        "QuoteNo": quote_number,
        "Name": name,
        "Address": Address,
        "Address2": Address2,
        "PostCode": PostCode,
        "City": City,
        "VATRegNo": VATRegNo,
        "ForeignRegNo": ForeignRegNo,
        "mailorigen": EMAIL_USER,
        "email": email,
        "idioma": idioma,
        "BD": BD,
        "URL_FORMCONTACTO": url_form_contacto,
        "EMAIL_USER": EMAIL_USER,
        "EMAIL_PASSWORD": EMAIL_PASSWORD,
        "ENVIRONMENT": ENVIRONMENT,
        "SEND_EMAIL": SEND_EMAIL,
        "session_id": session_id,
    }

    result = actualizar_contacto_service(payload2)

    if not result.get("ok"):
        if idioma in ("Español", "Esp"):
            return {"ok": False, "message": "Error actualizando contacto", "detail": result}, 500
        return {"ok": False, "message": "Error updating contact", "detail": result}, 500

    if idioma in ("Español", "Esp"):
        return {"ok": True, "message": "Solicitud recibida. Generando proforma..."}, 200
    return {"ok": True, "message": "Request received. Generating proforma..."}, 200
   



if __name__ == "__main__":

    import os
    import sys
    from flask import Flask,request,  jsonify

    from dotenv import load_dotenv



    from pathlib import Path

    THIS_DIR = os.path.dirname(os.path.abspath(__file__))  # ProcesarFormularioContacto/
    
    app = Flask(__name__, template_folder=os.path.join(THIS_DIR, "templates"))
    #app = Flask(__name__)   
    load_dotenv(Path(__file__).resolve().parent / ".env")
   

    BASE_DIR = os.path.dirname(os.path.dirname(__file__))
    # Añadimos esa ruta al sys.path
    sys.path.insert(0, BASE_DIR)
   
   
    

    @app.route("/api/contacto", methods=["POST"])
    def contacto():
        data = request.get_json()
        result = crear_contacto_core(data)
        return jsonify(result), 200

    
    
    @app.route("/api/actualizar_contacto", methods=["POST"])
    def actualizar_contacto():
   

        """Endpoint para actulizar un contacto y para crear una factura Proforma en BC."""

        data = request.get_json() or {}
        result = actualizar_contacto_service(data)
        
        return jsonify(result), 200
    


    from flask import request, jsonify

    @app.route("/proforma_submit", methods=["POST"])
    def proforma_submit():

        """Endpoint para actulizar un contacto y para crear una factura Proforma en BC."""
        data = request.get_json(silent=True) or {}
        result, status = proforma_submit_core(data)
        return jsonify(result), status
       



    @app.route("/proforma_form", methods=["GET", "POST"])
    def proforma_form():
        """Endpoint para actualizar un contacto y crear una factura Proforma en BC."""

        print("Endpoint /api/proforma_form called with method:", request.method)

        # 1️⃣ Extraer token
        if request.method == "GET":
            token = (request.args.get("token") or "").strip()
        else:
            if request.is_json:
                data = request.get_json(silent=True) or {}
                token = (data.get("token") or "").strip()
            else:
                token = (request.form.get("token") or "").strip()

        # 2️⃣ Llamar al servicio común
        body, status, content_type = proforma_form_service(token)

        # 3️⃣ Responder según tipo
        if content_type.startswith("text/html"):
            return body, status, {"Content-Type": content_type}

        # Si es error JSON
        return body, status, {"Content-Type": content_type}
        


        
            

            

        

        



    app.run(debug=True, port=5000)

