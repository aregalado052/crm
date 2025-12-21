import json
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

import base64
from decimal import Decimal, ROUND_HALF_UP
from datetime import date

from types import SimpleNamespace


BD = ""  # PRODUCCION o PRUEBAS
EMAIL_USER = ""
EMAIL_PASSWORD = ""   
URL_CONTACTO =""
URL_OFERTAS = ""
API_KEY = ""

ENVIRONMENT = ""
SEND_EMAIL= False



ENVIRONMENT = 'Prodsand2025'
#ENVIRONMENT = 'Production'  # Cambia a 'production' en producción
COMPANY_ID = '6f7784f5-1aaa-ee11-be36-000d3a667eb7'
#COMPANY_ID = '3872d67e-5377-ee11-817c-6045bdc8af59'
SCOPE = "https://api.businesscentral.dynamics.com/.default"
USERNAME = "AREGALADO@PLANETPOWERTOOLSIBERICA.onmicrosoft.com"


#AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"



RESPONSE_TYPE = "code"

TENANT_ID = os.environ.get("TENANT_ID", "")
CLIENT_ID = os.environ.get("CLIENT_ID", "")
PASSWORD = os.environ.get("PASSWORD", "")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")











def get_db_credentials(secret_name):
    client = boto3.client("secretsmanager", region_name="eu-north-1")  # ✅ correcto
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])




# --- Obtener token de acceso ---
def get_token():
    """Obtiene un token de acceso para autenticar solicitudes a Business Central.
    Utiliza el flujo de contraseña para obtener un token JWT.
    """
    
    
    url = f'https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token'

    print("🔑 Pidiendo token...")
    print("  TENANT_ID :", TENANT_ID)
    print("  CLIENT_ID :", CLIENT_ID)
    print("  USERNAME  :", repr(USERNAME))
    print("  SCOPE     :", SCOPE)
    print("PASSWORD :", repr(PASSWORD) )

    data = {
        'grant_type': 'password',
        
        'client_id': CLIENT_ID,
        'username': USERNAME,
        'password': PASSWORD,
        'client_secret': CLIENT_SECRET,
        'scope': SCOPE,
    }

    postfields = urllib.parse.urlencode(data)

    headers = ['Content-Type: application/x-www-form-urlencoded']
    
    

   
   

   
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

def actualizar_sales_header(session_id, SalesHeaderNumber):
    creds = get_db_credentials("secretoBC/Mysql")

    dbname = "bc_pruebas" if (BD == "PRUEBAS") else creds["dbname"]

    print ("BD", BD)  
    
    print(f"Credenciales obtenidas: {creds}")
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
            cursor.execute("""
                UPDATE sessions
                SET SalesHeaderNumber = %s
                WHERE session_id = %s
            """, (SalesHeaderNumber, session_id))
        connection.commit()
    finally:
        connection.close()

def store_session(name, email, mailorigen, idioma, origen, bd, email_user, email_password, url_contacto, url_ofertas, api_key, environment, send_email):
    session_id = str(uuid.uuid4())  # 🔑 clave de sesión única
    creds = get_db_credentials("secretoBC/Mysql")

    dbname = "bc_pruebas" if (BD== "PRUEBAS") else creds["dbname"]

    print ("BD", BD)  
    
    print(f"Credenciales obtenidas send email : {creds}")
    print(f"Conectando a la base de datos con host: {creds['host']}, usuario: {creds['username']}, base de datos: {dbname}")
    print ("send_email", send_email)
    

    connection = pymysql.connect(
        host=creds['host'],
        user=creds['username'],
        password=creds['password'],
        database= dbname,
        port=int(creds.get('port', 3306))
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO sessions (session_id, name, email, mailorigen, idioma,origen, bd, email_user, email_password, url_contacto, url_ofertas, api_key, environment, send_email)
                VALUES   (%s, %s, %s, %s, %s, %s,
                   %s, %s, %s, %s, %s,
                   %s, %s, %s)
            """, (session_id, name, email, mailorigen, idioma,origen, bd, email_user, email_password, url_contacto, url_ofertas, api_key, environment, send_email))
        connection.commit()
    finally:
        connection.close()

    return session_id


def get_session_data(session_id,bd):
    creds = get_db_credentials("secretoBC/Mysql")

   
    dbname = "bc_pruebas" if (bd== "PRUEBAS") else creds["dbname"]

    print ("BD", bd)  
    
    print(f"Credenciales obtenidas: {creds}")
    print(f"Conectando a la base de datos con host: {creds['host']}, usuario: {creds['username']}, base de datos: {dbname}")
    

    connection = pymysql.connect(
        host=creds['host'],
        user=creds['username'],
        password=creds['password'],
        database= dbname,
        port=int(creds.get('port', 3306))
    )
    with connection.cursor() as cursor:
        cursor.execute("SELECT name, email, mailorigen, idioma, SalesHeaderNumber, send_email, email_password FROM sessions WHERE session_id = %s", (session_id,))
        row = cursor.fetchone()
        if row:
            return {
                "name": row[0],
                "email": row[1],
                "mailorigen": row[2],
                "idioma": row[3],
                "SalesHeaderNumber": row[4],
                "send_email": row[5],
                "email_password": row[6]
            }
        else:
            return None

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

    print (lines)

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



def obtener_datos_pais(pais, idioma):

    creds = get_db_credentials("secretoBC/Mysql")

    
    dbname = "bc_pruebas" if (BD== "PRUEBAS") else creds["dbname"]

    print ("BD", BD)  
    
    print(f"Credenciales obtenidas: {creds}")
    print(f"Conectando a la base de datos con host: {creds['host']}, usuario: {creds['username']}, base de datos: {dbname}")
    

    connection = pymysql.connect(
        host=creds['host'],
        user=creds['username'],
        password=creds['password'],
        database= dbname,
        port=int(creds.get('port', 3306))
    )

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
   
    try:
        with connection.cursor() as cursor:
            sql = f"""
                SELECT codigo_pais, zona, mercado
                FROM pais
                WHERE {col} = %s
                LIMIT 1
            """
            cursor.execute(sql, (pais,))
            result = cursor.fetchone()
    finally:
        connection.close()  
    
    
    if result:
        codigo_pais, zona, mercado = result

        print(f"Datos obtenidos: {codigo_pais}, {zona}, {mercado}")
        return codigo_pais, mercado, zona
    else:
        return None, None, None  # o lanzar una excepción si prefieres    
def obtener_descuento(zona, pistas_perimetrales, pistas_laterales, descuento_adicional=0):
    """
    Obtiene el descuento basado en la zona y el número de pistas.

    """

    
    creds = get_db_credentials("secretoBC/Mysql")

    dbname = "bc_pruebas" if (BD== "PRUEBAS") else creds["dbname"]

    print ("BD", BD)  
    
    print(f"Credenciales obtenidas: {creds}")
    print(f"Conectando a la base de datos con host: {creds['host']}, usuario: {creds['username']}, base de datos: {dbname}")
    

    connection = pymysql.connect(
        host=creds['host'],
        user=creds['username'],
        password=creds['password'],
        database= dbname,
        port=int(creds.get('port', 3306))
    )
    cantidad = pistas_perimetrales + pistas_laterales
    try:
        with connection.cursor() as cursor:
            # Obtener descuento por zona
            sql = """
                SELECT descuento
                FROM zonas_descuento
                WHERE zona = %s
                LIMIT 1
            """
            cursor.execute(sql, (zona,))
            row = cursor.fetchone()
            descuento_zona = row[0] if row else 0.0

            # Obtener descuento por cantidad
            sql = """
                SELECT descuento
                FROM descuentos_cantidad
                WHERE %s BETWEEN cantidad_min AND cantidad_max
               
                LIMIT 1
            """
            cursor.execute(sql, (cantidad,))
            row = cursor.fetchone()
            descuento_cantidad = row[0] if row else 0.0

    finally:
        connection.close()

    cien = Decimal("100")

    descuento_total_decimal = (
        (cien - ((cien - descuento_zona) * (cien - descuento_cantidad) * (cien - descuento_adicional) / cien / cien))
    )

    descuento_total_entero = int(descuento_total_decimal.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    print(f"Descuento por zona: {descuento_zona}, Descuento por cantidad: {descuento_cantidad}, Descuento adicional: {descuento_adicional}, Descuento total: {descuento_total_entero}")    

    return descuento_total_entero



def obterner_productos():
    """
    Obtiene los precios de los productos desde la base de datos.
    """
    creds = get_db_credentials("secretoBC/Mysql")

    
    dbname = "bc_pruebas" if (BD== "PRUEBAS") else creds["dbname"]

    print ("BD", BD)  
    
    print(f"Credenciales obtenidas: {creds}")
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



def obterner_productos():
    """
    Obtiene los precios de los productos desde la base de datos.
    """
    creds = get_db_credentials("secretoBC/Mysql")

    
    dbname = "bc_pruebas" if (BD== "PRUEBAS") else creds["dbname"]

    print ("BD", BD)  
    
    print(f"Credenciales obtenidas: {creds}")
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
    creds = get_db_credentials("secretoBC/Mysql")

    
    dbname = "bc_pruebas" if (BD== "PRUEBAS") else creds["dbname"]

    print ("BD", BD)  
    print(f"Credenciales obtenidas: {creds}")
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
    creds = get_db_credentials("secretoBC/Mysql")

    
    dbname = "bc_pruebas" if (BD== "PRUEBAS") else creds["dbname"]
    print ("BD", BD)  
    
    print(f"Credenciales obtenidas: {creds}")
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




def obtener_descuento_cantidad_total(session_id):
    creds = get_db_credentials("secretoBC/Mysql")
    
    dbname = "bc_pruebas" if (BD== "PRUEBAS") else creds["dbname"]
    print ("BD", BD)  
    
    print(f"Credenciales obtenidas: {creds}")
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
            SELECT descuento_total, cantidad_total
            FROM sessions
            WHERE session_id = %s
            """
            cursor.execute(sql, (session_id,))
            result = cursor.fetchone()  # Devuelve una fila (o None si no existe)

        if result:
            descuento_total, cantidad_total = result
            return {
                "session_id": session_id,
                "descuento_total": float(descuento_total) if descuento_total is not None else 0.0,
                "cantidad_total": float(cantidad_total) if cantidad_total is not None else 0.0
            }
        else:
            return None
    finally:
        connection.close()

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
    print ("Entorno:", ENVIRONMENT )
    print ("Tenant:", TENANT_ID )
    print ("Company ID:", COMPANY_ID )
   
   
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
        



def insert_base_datos(lead):

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

        creds = get_db_credentials("secretoBC/Mysql")

        
        dbname = "bc_pruebas" if (BD== "PRUEBAS") else creds["dbname"]

        
        print ("BD", BD)  
        print(f"Credenciales obtenidas: {creds}")
        print(f"Conectando a la base de datos con host: {creds['host']}, usuario: {creds['username']}, base de datos: {dbname}")
        

        conn = pymysql.connect(
            host=creds['host'],
            user=creds['username'],
            password=creds['password'],
            database= dbname,
            port=int(creds.get('port', 3306))
        )

        try:
            
            with conn.cursor() as cur:
                cur.execute(sql, params)
               
            conn.commit()
            print("✅ Datos insertados en la base de datos")
        except pymysql.connect.Error as db_err:
            print(f"❌ Error de conexión a la base de datos: {db_err}")
            # Detalle controlado para el cliente
            return {"ok": False, "error": f"DB: {db_err}"}
        finally:
            try:
                conn.close()
            except Exception:
                pass






def lambda_handler(event, context):
    print("Evento recibido:", event)

    """Endpoint para crear un contacto y una oferta en Business Central."""

   
    

    try:
        data = json.loads(event.get("body", "{}"))  # ✅ Correcto en Lambda
    except Exception as e:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "JSON inválido", "detalle": str(e)})
        }

    global BD, EMAIL_USER, EMAIL_PASSWORD, URL_CONTACTO, URL_OFERTAS, API_KEY, ENVIRONMENT, SEND_EMAIL

  

    print("  TENANT_ID :", TENANT_ID)
    print("  CLIENT_ID :", CLIENT_ID)
    print("PASSWORD :", repr(PASSWORD) )

    #AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
    
    

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
    URL_CONTACTO = data.get("URL_CONTACTO")
    URL_OFERTAS = data.get("URL_OFERTAS", "https://tx3fc457zf.execute-api.eu-north-1.amazonaws.com/prod/oferta") 
    ENVIRONMENT = data.get("ENVIRONMENT", "Production") 
    SEND_EMAIL= data.get("SEND_EMAIL", True) 
    #hdrs = { (k or "").lower(): v for k, v in (event.get("headers") or {}).items() }
    hdrs = { (k or "").lower(): v for k, v in (data.get("headers") or {}).items() }
    API_KEY = hdrs.get("x-api-key")
    

    if not API_KEY:
        API_KEY = "gdZgiMt2FD79LrR2opX9gxitgJQfB9X2OkP7dn3i"

   


    print(f"""Datos recibidos: {name}, {email}, {pais}, {idioma}, {pistas_perimetrales}, {pistas_laterales}, {mailorigen}, {descuento_adicional}, {origen},
        {BD}, {EMAIL_USER}, {EMAIL_PASSWORD}, {URL_CONTACTO}, {URL_OFERTAS}, {API_KEY}, {ENVIRONMENT}, {SEND_EMAIL}""")


    bd=BD
    email_user=EMAIL_USER
    email_password=EMAIL_PASSWORD
    url_contacto=URL_CONTACTO
    url_ofertas=URL_OFERTAS
    api_key=API_KEY
    environment=ENVIRONMENT
    send_email=SEND_EMAIL

    session_id= store_session(name, email, mailorigen, idioma, origen, bd, email_user, email_password, url_contacto, url_ofertas, api_key, environment, send_email)

    codigo_pais, mercado, zona = obtener_datos_pais (pais, idioma)

    if idioma == "Español":
        codigo_idioma = "ESP"
    else:
        codigo_idioma = "ENU"

    print(f"Código de país: {codigo_pais}, Mercado: {mercado}, Zona: {zona}")

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

    actualizar_sales_header(session_id, SalesHeaderNumber)

    


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


    data=obtener_descuento_cantidad_total(session_id)

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
    insert_base_datos(lead)
        
    
         
       


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










if __name__ == "__main__":

    import os
    import sys
    from flask import Flask,request,  jsonify

    BASE_DIR = os.path.dirname(os.path.dirname(__file__))
    # Añadimos esa ruta al sys.path
    sys.path.insert(0, BASE_DIR)
   
    from config import (TENANT_ID as CFG_TENANT_ID,
                        CLIENT_ID as CFG_CLIENT_ID,
                        PASSWORD as CFG_PASSWORD,
                        CLIENT_SECRET as CFG_CLIENT_SECRET)
    app = Flask(__name__)   
    
    TENANT_ID = CFG_TENANT_ID
    CLIENT_ID = CFG_CLIENT_ID
    PASSWORD = CFG_PASSWORD
    CLIENT_SECRET = CFG_CLIENT_SECRET
    AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

    @app.route("/api/contacto", methods=["POST"])
    def contacto():
        """Endpoint para crear un contacto y una oferta en Business Central."""

    
        

        #try:
        #    data = json.loads(event.get("body", "{}"))  # ✅ Correcto en Lambda
        #except Exception as e:
        #    return {
        #        "statusCode": 400,
        #        "body": json.dumps({"error": "JSON inválido", "detalle": str(e)})
        #    }

        global BD, EMAIL_USER, EMAIL_PASSWORD, URL_CONTACTO, URL_OFERTAS, API_KEY, ENVIRONMENT, SEND_EMAIL
        
        data = request.get_json()

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
        URL_CONTACTO = data.get("URL_CONTACTO")
        URL_OFERTAS = data.get("URL_OFERTAS", "https://tx3fc457zf.execute-api.eu-north-1.amazonaws.com/prod/oferta") 
        ENVIRONMENT = data.get("ENVIRONMENT", "Production") 
        SEND_EMAIL= data.get("SEND_EMAIL", True) 
        #hdrs = { (k or "").lower(): v for k, v in (event.get("headers") or {}).items() }
        hdrs = { (k or "").lower(): v for k, v in (data.get("headers") or {}).items() }
        API_KEY = hdrs.get("x-api-key")
        if not API_KEY:
            API_KEY = "gdZgiMt2FD79LrR2opX9gxitgJQfB9X2OkP7dn3i"

    


        print(f"""Datos recibidos: {name}, {email}, {pais}, {idioma}, {pistas_perimetrales}, {pistas_laterales}, {mailorigen}, {descuento_adicional}, {origen},
            {BD}, {EMAIL_USER}, {EMAIL_PASSWORD}, {URL_CONTACTO}, {URL_OFERTAS}, {API_KEY}, {ENVIRONMENT}, {SEND_EMAIL}""")



        print ("URL_OFERTAS :", URL_OFERTAS )


        bd=BD
        email_user=EMAIL_USER
        email_password=EMAIL_PASSWORD
        url_contacto=URL_CONTACTO
        url_ofertas=URL_OFERTAS
        api_key=API_KEY
        environment=ENVIRONMENT
        send_email=SEND_EMAIL

        session_id= store_session(name, email, mailorigen, idioma, origen, bd, email_user, email_password, url_contacto, url_ofertas, api_key, environment, send_email)

        codigo_pais, mercado, zona = obtener_datos_pais (pais, idioma)

        if (idioma == "Español") or (idioma == "Esp"):
            codigo_idioma = "ESP"
        else:
            codigo_idioma = "ENU"

        print(f"Código de país: {codigo_pais}, Mercado: {mercado}, Zona: {zona}")

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

        actualizar_sales_header(session_id, SalesHeaderNumber)

        


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


        data=obtener_descuento_cantidad_total(session_id)

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
        insert_base_datos(lead)
            
        
            
        


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


    app.run(debug=True, port=5000)

