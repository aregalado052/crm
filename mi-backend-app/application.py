
import json
import pymysql
import os
from io import BytesIO
import boto3
import dropbox
import uuid
from datetime import datetime,date
import botocore
import base64
from flask import Response
from jinja2 import Template
from urllib.parse import quote
from pathlib import PurePosixPath
import mimetypes
import hashlib
from flask import render_template_string
import re



from bs4 import BeautifulSoup

from flask import (flash, jsonify, make_response, redirect, render_template,
                   request, session, url_for)
from flask_babel import Babel, _
from flask_jwt_extended import (create_access_token, get_jwt_identity,
                                jwt_required, set_access_cookies)
from sqlalchemy import and_, asc, case
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import joinedload

from app_init import bcrypt, create_app, db
from creacion_BD import crear_base_si_no_existe
from funciones import (create_reset_token,
                       send_new_password, update_user_password,
                       validate_reset_token, get_dropbox_access_token)
from models import (  User)
from config import (BD ,EMAIL_USER,EMAIL_PASSWORD,URL_CONTACTO ,URL_OFERTAS,
                     API_KEY,ENVIRONMENT,SEND_EMAIL,AWS_ACCESS_KEY_ID,
                     AWS_SECRET_ACCESS_KEY,AWS_REGION,S3_BUCKET,ROOT_PREFIX_S3,ROOT_PREFIX_DROPBOX)


from funciones_generar_email import (build_framework,slugify,
                                     extract_html_inline_and_attachments_from_eml_bytes,
                                     rehost_images_under_template_from_html,
                                     resolve_cid_with_attachments,
                                     insert_extra_files_into_html,
                                     extract_default_context_from_html,
                                     replace_cid_srcs_with_urls,
                                     fix_relative_imgs,
                                     replace_cid_everywhere,clean_signature_images,
                                     inject_preview_css,put_public_s3,
                                     public_url, parent_of,normalize_incoming_content,
                                     update_manifest,update_manifest_for_key,
                                     apply_manifest_images_all,
                                     manifest_lookup,_attachments_html,
                                     enforce_dimensions_from_manifest,
                                    insert_extra_files_into_html,
                                    s3_key_exists,_norm_src,_collect_image_keys,split_body_and_signature,
                                    _coerce_items,paths, TEMPLATES_ROOT, get_s3,
                                    USE_S3, S3_BUCKET,key_message, key_original,key_template, key_signature,
                                    s3_get_text, s3_put_text,BASE_DIR)
                                     




application = create_app()

@application.template_filter('escapejs')
def escapejs_filter(s):
    return json.dumps(str(s))[1:-1]


from decimal import Decimal

@application.route('/')
def index():
    session.pop('_flashes', None)  # Limpia mensajes pendientes manualmente

    return render_template('login.html')






def get_locale():

    lang = session.get('lang') or request.cookies.get('lang') or 'es'
    # Normaliza: solo letras minúsculas (ej. "en-us" -> "en")
    
    if lang:
        # Si el idioma tiene un guion, tomamos solo la parte antes del guion
        # Ejemplo: 'en-us' -> 'en'
        # Esto es útil si se quiere normalizar a un código de idioma más simple
        return lang.split('-')[0].lower()

        # Si no hay idioma en la sesión, lo forzamos a español
    session['lang'] = 'es'
    return 'es'
    


babel = Babel(application, locale_selector=get_locale)


@application.route('/set_language', methods=['POST'])
def set_language():

    lang = request.form.get('language', 'es')
    next_page = request.form.get('next') or url_for('index') 
    # Normaliza si es necesario
    lang = lang.split('-')[0]  # 'en-us' -> 'en'
    session['lang'] = lang
    resp = make_response(redirect(next_page))

    #resp = make_response(redirect(request.referrer or '/'))
    print("🔍 Referrer:", request.referrer) 
    print("resp", resp)
    resp.set_cookie('lang', lang)
    print("set_language", lang)
    return resp

    
   


   

@application.context_processor
def inject_get_locale():
    return dict(get_locale=get_locale)

@application.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session.pop('_flashes', None)  # Limpia mensajes pendientes manualmente
        data = request.get_json()  # Obtener datos en formato JSON

        email = data.get('email')
        password = data.get('password')

        try:
            user = User.query.filter_by(email=email).first()
        except OperationalError as e:
            db.session.rollback()
            flash(_("Error Operacional."), 'error')
            return jsonify({"msg": _("Error operacional")}), 500

        if user is None:
            flash(_("El email facilitado no existe"), 'error')
            return jsonify({"msg": _("El email facilitado no existe")}), 401
        else:
           
            
            ruta_login = '/main_page'
            
            
            if user and bcrypt.check_password_hash(user.password, password):
                #access_token = create_access_token(identity=str({'email': user.email}))
                access_token = create_access_token(identity=user.email)
                print("Usuario autenticado:", user.email)
                session['email'] = user.email
                session['access_token'] = access_token
                print ("user.uid", user.uid )

                # Creamos primero el diccionario de datos
                response_data = {
                    "msg": _("Login exitoso"),
                    "uid": user.uid,
                    "ruta_login": ruta_login,
                    
                }

                
                # Convertimos el dict a JSON, y luego lo envolvemos con make_response
                json_response = jsonify(response_data)
                response = make_response(json_response)

                # Establecemos la cookie JWT
                set_access_cookies(response, access_token)

                return response

            flash(_("Contraseña incorrecta."), 'error')
            return jsonify({"msg": _("Contraseña incorrecta.")}), 401
    session.pop('_flashes', None)  # Limpia mensajes pendientes manualmente
    return render_template('login.html')
                

        
    

#@app.route('/register', methods=['GET', 'POST'])
#def register():
#    if request.method == 'POST':
#        username = request.form['username']
#        password = request.form['password']
        # Aquí iría la lógica de registro

@application.route('/register', methods=[ 'GET','POST'])
def register():
    
   
    if request.method == 'POST':
        
        data = request.get_json()
       
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
       

        try :
            user = User.query.filter_by(username=username).first()
        except OperationalError as e:
            db.session.rollback()
            print(f"Error operacional: {e}")
            flash("Error Operacional.", 'error')
            return jsonify({"msg": "Error operacional"}), 500


        if user:
            print (username)
            uid = user.uid

            

            
            


            try :
                #Buscar  cunato clubs tiene es uid
                existing_user_email = User.query.filter( (User.email == email)).first()
            except OperationalError as e:
                db.session.rollback()
                print(f"Error operacional: {e}")
                flash("Error Operacional.", 'error')
                return jsonify({"msg": "Error operacional"}), 500




            # Verificar si el usuario ya existe
            if existing_user_email:  

                print ("existing_user_email", existing_user_email.email)         

                return jsonify({"msg": "La dirección de email ya esá registrada"}), 401
            
            else :    

                print (" NO existing_user_email")
               
                hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

                
                if not user.email :
                   

                    

                    try :
                        User.query.filter_by(username=username).update({
                        'email': email,
                        'password': hashed_password})

                    
                        print  ("User_email", email)
                        db.session.commit()
               

                    except OperationalError as e:
                        db.session.rollback()
                        print(f"Error operacional: {e}")
                        flash("Error Operacional.", 'error')
                        return jsonify({"msg": "Error operacional"}), 500





                else :

                    print  ("User_email2", email)
                    # Aquí iría la lógica de autenticación
                   
                    try :
                        new_user = User(username=username, email=email, password=hashed_password, uid=uid, uid_hytronik=UID_HYTRONIK)
                        db.session.add(new_user)
                        db.session.commit()


                    except OperationalError as e:
                        db.session.rollback()
                        print(f"Error operacional: {e}")
                        flash("Error Operacional.", 'error')
                        return jsonify({"msg": "Error operacional"}), 500


                    





                flash("Usuario registrado con éxito.", 'success')
                flash("Por favor, inicie sesión.", 'success')
                return redirect(url_for('login'))  # Redirigir al formulario de login


                #return jsonify({"msg": "Usuario registrado correctamente"}), 200
        
        else : 
            
            existe_usuario = db.session.query(User).first()

            if existe_usuario:
                return jsonify({"msg": "El usuario no existe"}), 404
            else:
                print ("admin")
                username = "admin"
                print (email)
                print (password)
                hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

                
                try :
                        
                    new_user = User(username=username, email=email, password=hashed_password,uid=766)
                    db.session.add(new_user)
                    db.session.commit()
                    flash("Usuario registrado con éxito.", 'success')
                    flash("Por favor, inicie sesión.", 'success')


                except OperationalError as e:
                    db.session.rollback()
                    flash("Error Operacional.", 'error')
                    print(f"Error operacional: {e}")

                return redirect(url_for('login'))  # Redirigir al formulario de login
                
                #return jsonify({"msg": "El usuario admin se ha registrado"}), 200



        
        
        
           
  
    
    return render_template('register.html')





@application.route('/forgot_password', methods=[ 'GET','POST'])


def forgot_password():
    if request.method == 'POST':


        
        #data= { "username": 'aregalado', "password": 'Madrid01' }
        data = request.get_json()  # Obtener datos en formato JSON         
        email = data.get('email')
        

       
       

       

        try :
                        
            user = User.query.filter_by(email=email).first()            

        except OperationalError as e:
            db.session.rollback()
            print(f"Error operacional: {e}")
            flash("Error Operacional.", 'error')
            return jsonify({"msg": "Error operacional"}), 500




        if user :
           

            
            reset_token = create_reset_token(user.id) # Genera un token seguro

            
            # Llamar a la función para enviar el correo con el token
            respuesta = send_new_password(email, reset_token)

            if (respuesta == "error"): 
                    
                return jsonify({"msg":"error al enviar el correo" }), 404
            else :

                flash ("Instrucciones enviadas con exito por email ")
               
                        

                return jsonify({"msg":"Cooreo enviado con éxito" }), 200
        
            


       

        

        
                
            

        return jsonify({"msg": "No existe la dirección de correo"}), 401
    else : 
      
        



        return render_template('Forgot_password.html')





@application.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        token = request.form.get('token')
        new_password = request.form.get('new_password')

        

        # (Aquí deberías validar el token primero)
        if validate_reset_token(token):
            # Si el token es válido, actualizar la contraseña en la base de datos
            hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
            
        
            if update_user_password(token, hashed_password):
                    flash("Contraseña restablecida con éxito.", 'success')
                    flash("Por favor, inicie sesión.", 'success')
                    return redirect(url_for('login'))  # Redirigir al formulario de login
            else:
                    flash("No se pudo actualizar la contraseña.", 'error')
                    return redirect(url_for('reset_password'))  # Redirigir de nuevo a restablecer contraseña
        


        else : 
            

            flash("Tiempo máximo expirado para restablecer la contraseña.", 'error')
            flash("Por favor, vuelva a intentarlo", 'error')
            return redirect(url_for('login'))  # Redirigir al formulario de login
    
    
    
        

    # Si es un GET, mostrar el formulario
    token = request.args.get('token')

    
    return render_template('reset_password.html', token=token)


       





        
               
       #
   
   


@application.route('/main_page', methods=[ 'GET','POST'])

#@jwt_required()



def main_page():
   
    print ("main_page")
   
    
    if request.method == 'POST':
        data = request.json
        application.logger.info('Datos recibidos: %s', data)
        print ("if POST")
    
   
    else: 

        print ("enviando dtos del GET main page")
        
        access_token = session.get('access_token')  # ✅ Recuperas el token desde la sesión
        if not access_token:
            return "Token no encontrado en sesión", 401

        # 🔁 Rediriges a la ruta que realmente renderiza el HTML
        response = redirect(url_for("consultar_leads", estado="Sin calificar"))

        # 🔐 Guardas el token como cookie segura en la misma response de la redirección
        #set_access_cookies(response, access_token)
        

        # 🔐 Guardar el token como cookie segura
        set_access_cookies(response, access_token)

        return response
       

               
       # Renderea la plantilla
    




@application.route('/ofertas', methods=['GET', 'POST'])
def ofertas():
    if request.method == 'POST':
        from io import BytesIO
        import pycurl
        try:
            data = request.get_json()

            # Recoge los datos enviados desde el frontend
            name = data.get('name')
            email = data.get('email')
            idioma = data.get('idioma')
            pais = data.get('pais')
            tipo_lead = data.get('tipo_lead')
            pistas_perimetrales = data.get('pistas_perimetrales')
            pistas_laterales = data.get('pistas_laterales')
            incluir_transporte = data.get('incluir_transporte', False)
            importe_transporte = data.get('importe_transporte', 0)   
            mailorigen = 'soporte@planetpower.es'
            descuento_adicional = Decimal(data.get("descuento_adicional", 0))
            origen = 'CRM'
 

            print("📥 Datos recibidos:")
            print(f"Nombre: {name}")
            print(f"Email: {email}")
            print(f"Idioma: {idioma}")
            print(f"País: {pais}")
            print(f"Tipo: {tipo_lead}")
            print(f"Descuento adicional: {descuento_adicional}")
            print(f"Pistas perimetrales: {pistas_perimetrales}")
            print(f"Pistas laterales: {pistas_laterales}")
            print(f"Descuento adicional: {descuento_adicional}")
            print(f"Incluir Transporte : {incluir_transporte}")
            print(f"Importe Transporte : {importe_transporte}")
            print ("Send_EMAIL", SEND_EMAIL)





       

            payload = {
                "name": name,
                "email": email,
                "idioma": idioma,
                "pais": pais,
                "tipo_lead": tipo_lead,
                "pistas_perimetrales": pistas_perimetrales,
                "pistas_laterales": pistas_laterales,
                "mailorigen": EMAIL_USER,
                "descuento_adicional": int(descuento_adicional),
                "incluir_transporte": incluir_transporte,
                "importe_transporte": importe_transporte,
                "origen": origen,
                "BD": BD,
                "EMAIL_USER": EMAIL_USER,
                "EMAIL_PASSWORD": EMAIL_PASSWORD,
                "URL_CONTACTO": URL_CONTACTO,
                "URL_OFERTAS": URL_OFERTAS,
                "ENVIRONMENT": ENVIRONMENT,
                "SEND_EMAIL": SEND_EMAIL,
            }
            


            print ("URL_CONTACTO", URL_CONTACTO)


    
            api_key = API_KEY
          

            api_url = URL_CONTACTO

            headers = [
                "x-api-key: " + api_key,
                "Request-Origin: SwaggerBootstrapUi",
                "Accept: application/json",
                "Content-Type: application/json",
            ]

            body = json.dumps({
                "name": name,
                "email": email,
                "idioma": idioma,
                "pais": pais,
                "tipo_lead": tipo_lead,
                "pistas_perimetrales": pistas_perimetrales,
                "pistas_laterales": pistas_laterales,
                #"mailorigen": mailorigen,
                "mailorigen": EMAIL_USER,
                "descuento_adicional": int (descuento_adicional),
                "incluir_transporte": incluir_transporte,
                "importe_transporte": importe_transporte,
                "origen": origen,
                "BD": BD,
                "EMAIL_USER": EMAIL_USER,
                "EMAIL_PASSWORD": EMAIL_PASSWORD,
                "URL_CONTACTO": URL_CONTACTO,
                "URL_OFERTAS": URL_OFERTAS,
                "ENVIRONMENT": ENVIRONMENT ,
                "SEND_EMAIL": SEND_EMAIL

            })


           

            buffer = BytesIO()
            c = pycurl.Curl()
            c.setopt(c.URL, api_url)
            c.setopt(c.POST, 1)
            c.setopt(c.POSTFIELDS, body)
            c.setopt(pycurl.SSL_VERIFYPEER, 0)
            c.setopt(pycurl.SSL_VERIFYHOST, 0)
            c.setopt(pycurl.CONNECTTIMEOUT, 10)
            c.setopt(pycurl.TIMEOUT, 60)
            c.setopt(c.HTTPHEADER, headers)
            c.setopt(c.WRITEDATA, buffer)

            c.perform()
            status_code = c.getinfo(pycurl.RESPONSE_CODE) or 500
            response_body = buffer.getvalue().decode('utf-8')
            c.close()

            print(f"✅ Respuesta del backend (status {status_code}): {response_body}")

            response = make_response(response_body, status_code)
            response.headers["Content-Type"] = "application/json"
            return response

        except Exception as e:
            print("❌ Excepción capturada:", str(e))
            return make_response(jsonify({"error": str(e)}), 500)

    # Si es GET, renderiza el formulario
    return render_template('ofertas.html')

def _parse_date(s):
    if not s:
        return None
    # Espera 'YYYY-MM-DD' del <input type="date">
    return datetime.strptime(s, "%Y-%m-%d").date()

def _num(x):
    if x is None or x == "":
        return None
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError, TypeError):
        return None

def _clip_len(s, n):
    if s is None:
        return None
    return str(s)[:n]

def get_db_credentials(secret_name):
    client = boto3.client("secretsmanager", region_name="eu-north-1")  # ✅ correcto
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])

@application.route('/leads', methods=['GET', 'POST'])
def leads():
    if request.method == 'POST':

        # Asegura parseo JSON
        data = request.get_json(force=True) or {}
        
        # Extrae valores del payload
       
        fecha_actual            = data.get('fecha_actual')           # str 'YYYY-MM-DD' o None
        fecha_proyecto          = data.get('fecha_proyecto')
        fecha_proxima_accion    = data.get('fecha_proxima_accion')
        name                    = data.get('name')
        email                   = data.get('email')
        quote_number            = data.get('quote_number')
        idioma                  = data.get('idioma')
        pais                    = data.get('pais')
        incluir_transporte      = data.get('incluir_transporte')    
        importe_transporte      = _num(data.get('importe_transporte'))
        descuento_adicional     = _num(data.get('descuento_adicional'))
        descuento_total         = _num(data.get('descuento_total'))
        cantidad_total          = _num(data.get('cantidad_total'))  
        estado                  = data.get('estado')
        prob_exito_raw          = data.get('probabilidad_exito')
        pistas_perimetrales     = _num(data.get('pistas_perimetrales'))
        pistas_laterales        = _num(data.get('pistas_laterales'))    
        info_tecnica            = _clip_len(data.get('info_tecnica'), 1000)
        info_general            = _clip_len(data.get('info_general'), 1000)
        observaciones           = _clip_len(data.get('observaciones'), 200)

        # Conversión/normalización
        probabilidad_exito = None
        if prob_exito_raw not in (None, ""):
            probabilidad_exito = int(prob_exito_raw)  # lanza ValueError si no es número

        

        # --- Inserción ---
        sql = """
        INSERT INTO lead_forms (
          fecha_actual, fecha_proyecto, fecha_proxima_accion,
          name, email, quote_number, idioma, pais,
          descuento_adicional, descuento_total, cantidad_total,incluir_transporte, importe_transporte,
          probabilidad_exito, pistas_perimetrales, pistas_laterales,
          info_tecnica, info_general, observaciones
        ) VALUES (
          %(fecha_actual)s, %(fecha_proyecto)s, %(fecha_proxima_accion)s,
          %(name)s, %(email)s, %(quote_number)s, %(idioma)s, %(pais)s,
          %(descuento_adicional)s, %(descuento_total)s, %(cantidad_total)s, %(incluir_transporte)s, %(importe_transporte)s,
          %(probabilidad_exito)s, %(pistas_perimetrales)s, %(pistas_laterales)s,
          %(info_tecnica)s, %(info_general)s, %(observaciones)s
        )
        """

        params = {
            #"session_id": session_id,
            "fecha_actual": fecha_actual,
            "fecha_proyecto": fecha_proyecto,
            "fecha_proxima_accion": fecha_proxima_accion,
            "name": name,
            "email": email,
            "quote_number": quote_number,
            "idioma": idioma,
            "pais": pais,
            "descuento_adicional": descuento_adicional,
            "descuento_total": descuento_total,
            "cantidad_total": cantidad_total,
            "probabilidad_exito": probabilidad_exito,
            "incluir_transporte": incluir_transporte,
            "importe_transporte": importe_transporte,   
            "pistas_laterales": pistas_laterales,
            "pistas_perimetrales": pistas_perimetrales,
            "info_tecnica": info_tecnica,
            "info_general": info_general,
            "observaciones": observaciones,
        }

        creds = get_db_credentials("secretoBC/Mysql")

        
        
        dbname = "bc_pruebas" if (BD== "PRUEBAS") else creds["dbname"]

        print(f"Credenciales obtenidas: {creds}")
        print(f"Conectando a la base de datos con host: {creds['host']}, usuario: {creds['username']}, base de datos: {dbname}")

        conn = pymysql.connect(
            host=creds['host'],
            user=creds['username'],
            password=creds['password'],
            database=dbname,
            port=int(creds.get('port', 3306))
        )

        try:
            
            with conn.cursor() as cur:
                cur.execute(sql, params)
                new_id = cur.lastrowid
            conn.commit()
            return jsonify({"ok": True, "id": new_id, "quote_number": quote_number}), 201

        except pymysql.err.IntegrityError as e:
            conn.rollback()
            # Tip: suele venir (errno, errmsg). Ej. 1048 → NOT NULL
            errno = e.args[0] if e.args else None
            errmsg = e.args[1] if len(e.args) > 1 else str(e)
            print(f"DB IntegrityError {errno}: {errmsg} | params.quote_number={repr(quote_number)}")
            return jsonify({"ok": False, "error": f"MySQL {errno}: {errmsg}"}), 400
        
        except pymysql.err.Error as e:
            conn.rollback()
            print(f"DB Error: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

        finally:
            try:
                conn.close()
            except Exception:
                pass

        return make_response(jsonify({"ok": True, "id": new_id}), 201)

    # GET opcional: podrías listar últimos leads
    #return make_response(jsonify({"ok": True, "msg": "Use POST para crear leads"}), 200)
        
       
    # Si es GET, renderiza el formulario

    incluir_transporte = request.args.get('incluir_transporte')        # 'true' / 'false' / None
    importe_transporte = request.args.get('importe_transporte')        # '400' / None
    name                = request.args.get('name')
    email               = request.args.get('email')
    idioma              = request.args.get('idioma')
    pais                = request.args.get('pais')
    descuento_adicional = request.args.get('descuento_adicional')
    descuento_total     = request.args.get('descuento_total')
    cantidad_total      = request.args.get('cantidad_total')
    quote_number        = request.args.get('quoteNumber')  # ojo: en la URL es quoteNumber
    pistas_perimetrales = request.args.get('pistas_perimetrales')
    pistas_laterales    = request.args.get('pistas_laterales')

    # si quieres, convierte incluir_transporte a boolean:
    if incluir_transporte is not None:
        incluir_transporte = incluir_transporte.lower() == 'true'
    return render_template(
            'leads.html',
            incluir_transporte=incluir_transporte,
            importe_transporte=importe_transporte,
            name=name,
            email=email,
            idioma=idioma,
            pais=pais,
            descuento_adicional=descuento_adicional,
            descuento_total=descuento_total,
            cantidad_total=cantidad_total,
            quote_number=quote_number,
            pistas_perimetrales=pistas_perimetrales,
            pistas_laterales=pistas_laterales,
        )


@application.route('/consultar_leads', methods=['GET', 'POST'])
def consultar_leads():
    estado = request.args.get("estado")
    creds = get_db_credentials("secretoBC/Mysql")
    

    dbname = "bc_pruebas" if (BD== "PRUEBAS") else creds["dbname"]

    print(f"Credenciales obtenidas: {creds}")
    print(f"Conectando a la base de datos con host: {creds['host']}, usuario: {creds['username']}, base de datos: {dbname}")

    conn = pymysql.connect(
        host=creds['host'],
        user=creds['username'],
        password=creds['password'],
        database=dbname,
        port=int(creds.get('port', 3306))
    )


    from pymysql.cursors import DictCursor

    where_sql = ""
    params = []
    if estado and estado != "Todos":
        where_sql = "WHERE estado = %s"
        params.append(estado)



   

   
    try:
        with conn.cursor(DictCursor) as cur:
            sql = f"""
                SELECT
                id,
                fecha_actual,
                fecha_proyecto,
                fecha_proxima_accion,
                name,
                pais,
                tipo_lead,
                quote_number,
                cantidad_total,
                descuento_total,
                COALESCE(pistas_laterales,0) + COALESCE(pistas_perimetrales,0) AS pistas_total,
                probabilidad_exito,
                incluir_transporte,
                importe_transporte,
                estado
                FROM lead_forms
                {where_sql}
                ORDER BY fecha_actual DESC, id DESC
            """
            cur.execute(sql, params)   # 👈 pasa params (aunque esté vacío)
            rows = cur.fetchall()
    finally:
        conn.close()

    
    print(f"Leads obtenidos: {len(rows)}")
    print("Leads:", rows)
    # render
    return render_template("consultar_leads.html", 
                           leads=rows,
                           estado=estado,
                           )
def db_get_lead(lead_id):
    creds = get_db_credentials("secretoBC/Mysql")
    

    dbname = "bc_pruebas" if (BD== "PRUEBAS") else creds["dbname"]
    print(f"Credenciales obtenidas: {creds}")
    print(f"Conectando a la base de datos con host: {creds['host']}, usuario: {creds['username']}, base de datos: {dbname}")

    conn = pymysql.connect(
        host=creds['host'],
        user=creds['username'],
        password=creds['password'],
        database=dbname,
        port=int(creds.get('port', 3306))
    )


    from pymysql.cursors import DictCursor

    where_sql = "WHERE id = %s"
    params = []
   
    params.append(lead_id)

   
    try:
        with conn.cursor(DictCursor) as cur:
            sql = f"""
                SELECT
                id,
                fecha_actual,
                fecha_proyecto,
                fecha_proxima_accion,
                name,
                email,
                idioma,
                pais,
                tipo_lead,
                quote_number,
                cantidad_total,
                descuento_adicional,
                descuento_total,
                pistas_perimetrales,
                pistas_laterales,
                probabilidad_exito,
                incluir_transporte,
                importe_transporte,
                info_tecnica,
                info_general,
                observaciones,
                estado
                FROM lead_forms
                {where_sql}
                ORDER BY fecha_actual DESC, id DESC
            """
            print ("sql",sql)
            print ("params", params)
            cur.execute(sql, params)   # 👈 pasa params (aunque esté vacío)
            rows = cur.fetchall()
    finally:
        conn.close()

    
    print(f"Leads obtenidos: {len(rows)}")
    print("Leads:", rows)
                               
    return (rows[0] if rows else None)  # Devuelve el primer lead o None si no existe

def db_update_lead(lead):
    creds = get_db_credentials("secretoBC/Mysql")
   

    dbname = "bc_pruebas" if (BD== "PRUEBAS") else creds["dbname"]

    print(f"Credenciales obtenidas: {creds}")
    print(f"Conectando a la base de datos con host: {creds['host']}, usuario: {creds['username']}, base de datos: {dbname}")

    conn = pymysql.connect(
        host=creds['host'],
        user=creds['username'],
        password=creds['password'],
        database=dbname,
        port=int(creds.get('port', 3306))
    )


    from pymysql.cursors import DictCursor

    try:
        with conn.cursor(DictCursor) as cur:
            sql = """
                UPDATE lead_forms
                SET
                  fecha_actual          = %s,
                  fecha_proyecto        = %s,
                  fecha_proxima_accion  = %s,
                  probabilidad_exito    = %s,
                  tipo_lead             = %s,
                  info_tecnica          = %s,
                  info_general          = %s,
                  observaciones         = %s,
                  estado                = %s
                WHERE id = %s
            """
            params = [
                lead.fecha_actual,
                lead.fecha_proyecto,
                lead.fecha_proxima_accion,
                lead.probabilidad_exito,
                lead.tipo_lead,
                lead.info_tecnica,
                lead.info_general,
                lead.observaciones,
                lead.estado,
                lead.id   # 👈 muy importante que el id vaya al final
            ]
            print("SQL:", sql)
            print("Params:", params)

            cur.execute(sql, params)
            conn.commit()   # 👈 confirma cambios
            rows = cur.rowcount
            print("Filas actualizadas:", rows)
    finally:
        conn.close()

    
   



@application.route('/lead_manage', methods=['GET', 'POST'])
def lead_manage():

    

    try:
        if request.method == "POST":
            from types import SimpleNamespace
            
            try:
                # Asegura parseo JSON
                data = request.get_json(force=True) or {}
                
                # Extrae valores del payload
                id_                     = data.get('id')
                fecha_actual            = data.get('fecha_actual')           # str 'YYYY-MM-DD' o None
                fecha_proyecto          = data.get('fecha_proyecto')
                fecha_proxima_accion    = data.get('fecha_proxima_accion')
                estado                  = data.get('estado')
                tipo_lead               = data.get('tipo_lead')
                prob_exito_raw          = data.get('probabilidad_exito')
                incluir_transporte      = data.get('incluir_transporte')
                importe_transporte      = _num(data.get('importe_transporte'))
                info_tecnica            = _clip_len(data.get('info_tecnica'), 1000)
                info_general            = _clip_len(data.get('info_general'), 1000)
                observaciones           = _clip_len(data.get('observaciones'), 200)

                # Conversión/normalización
                probabilidad_exito = None
                if prob_exito_raw not in (None, ""):
                    probabilidad_exito = int(prob_exito_raw)  # lanza ValueError si no es número

                # Valida mínimos
                if not id_:
                    return jsonify({"ok": False, "message": "Falta id"}), 400

                # Crea 'lead' como un objeto con atributos 
                lead = SimpleNamespace(
                    id=id_,
                    fecha_actual=fecha_actual,
                    fecha_proyecto=fecha_proyecto,
                    fecha_proxima_accion=fecha_proxima_accion,
                    estado=estado,
                    tipo_lead=tipo_lead,
                    probabilidad_exito=probabilidad_exito,
                    incluir_transporte=incluir_transporte,
                    importe_transporte=importe_transporte,
                    info_tecnica=info_tecnica,
                    info_general=info_general,
                    observaciones=observaciones
                )

                # Logs correctos (usa las variables definidas)
                print("📥 Datos recibidos:")
                print(f"id: {lead.id}")
                print(f"Fecha actual: {lead.fecha_actual}")
                print(f"Fecha proyecto: {lead.fecha_proyecto}")
                print(f"Fecha próxima acción: {lead.fecha_proxima_accion}")
                print(f"Estado: {lead.estado}")
                print(f"Tipo de lead: {lead.tipo_lead}")
                print(f"Probabilidad de éxito: {lead.probabilidad_exito}")
                print(f"Información técnica: {lead.info_tecnica}")
                print(f"Información general: {lead.info_general}")
                print(f"Observaciones: {lead.observaciones}")

                # Persistencia
                db_update_lead(lead)

                return jsonify({"ok": True})

            except Exception as e:
                application.logger.exception("Error en lead_manage")
                return jsonify({"ok": False, "message": str(e)}), 400

        # GET
        else : 
            lead_id = request.args.get("lead_id")
            if not lead_id:
                return jsonify({"error": "missing_lead_id"}), 400
            lead = db_get_lead(lead_id)  # tu función para obtener el lead


            if not lead:
                # Puedes usar abort(404) o una plantilla 404
                return render_template("lead_not_found.html", lead_id=lead_id), 404  # <-- return

            return render_template("lead_manage.html", lead=lead)  # <-- return SIEMPRE

    except Exception as e:
        application.logger.exception("Error inesperado en lead_manage")
        # Devolver algo incluso en error
        return jsonify({"error": "internal", "detail": str(e)}), 500

@application.route('/redes', methods=['GET', 'POST'])
def redes():
    session.clear()  # Elimina todos los datos de sesión
    return redirect(url_for('login'))  # Cambiá 'login' por tu vista de inicio o login

@application.route('/campanas', methods=['GET', 'POST'])
def campanas():
    session.clear()  # Elimina todos los datos de sesión
    return redirect(url_for('login'))  # Cambiá 'login' por tu vista de inicio o login






@application.route('/upload_template_email', methods=['GET', 'POST'])
def upload_template_email():
    if request.method == "POST":


        try:
            payload = request.get_json(force=True, silent=False)
        except Exception as e:
            print("[ERROR] JSON parse:", repr(e))
            return jsonify({"error": "JSON inválido"}), 400

        print("[DEBUG] payload keys:", list(payload.keys()))
        name = (payload.get("name") or "").strip()
        eml_b64 = (payload.get("eml_base64") or "").strip()
        html_in = (payload.get("html") or "").strip()
        if not name:
            return jsonify({"error": "Campo 'name' es obligatorio"}), 400
        if not eml_b64 and not html_in:
            return jsonify({"error": "Envía 'eml_base64' (archivo .eml) o 'html'"}), 400
        lang = (payload.get("lang") or "es").strip().lower()
        print("[DEBUG] lang payload:", lang)

        
        lang = (payload.get("lang") or "es").strip().lower()
        print("[DEBUG] lang payload:", lang)

        slug = slugify(name)
        out_dir = os.path.join("output", slug, lang)
        # helpers mínimos
        def ensure_html(s: str) -> str:
            if "<" in s and ">" in s: return s
            blocks = [f"<p>{line.strip()}</p>" for line in s.split("\n\n") if line.strip()]
            return "<html><body>" + "\n".join(blocks) + "</body></html>"

        attachments = []  # SIEMPRE define por adelantado
        images = []       # SIEMPRE define por adelantado

        if eml_b64:
            print("[DEBUG] usando flujo EML; eml_base64 len:", len(eml_b64))
            try:
                eml_bytes = base64.b64decode(eml_b64, validate=True)
                print("[DEBUG] eml_bytes len:", len(eml_bytes))
            except Exception as e:
                import traceback; traceback.print_exc()
                return jsonify({"ok": False, "where": "base64", "error": str(e)}), 400

            try:
                extracted = extract_html_inline_and_attachments_from_eml_bytes(
                    eml_bytes, slug, lang, append_unreferenced_images=True
                )
            except Exception as e:
                import traceback; traceback.print_exc()
                return jsonify({"ok": False, "where": "extractor", "error": str(e)}), 400

            if not extracted or not isinstance(extracted, dict):
                return jsonify({"ok": False, "where": "extractor", "error": "Extractor devolvió None o tipo no dict"}), 400
            if not extracted.get("html"):
                return jsonify({"ok": False, "where": "extractor", "error": "Extractor sin parte HTML"}), 400

            html_final  = extracted["html"]
            attachments = extracted.get("attachments", [])
            images      = extracted.get("images", [])
            print("[DEBUG] extractor.debug:", extracted.get("debug", {}))

            put_public_s3(
                f"emails/templates/{slug}/{lang}/original.html",
                html_final.encode("utf-8"),
                "text/html; charset=utf-8",
                cache_seconds=0
            )
        else:
            print("[DEBUG] usando flujo HTML (textarea/archivo .html)")
            html_final = ensure_html(html_in)

            # 1) Si el front te manda binarios en payload.attachments, primero
            #    resuelve CIDs con esos binarios (si hay), y separa "file" sin cid.
            payload_attachments = payload.get("attachments") or []
            if payload_attachments:
                html_final, resolved_info = resolve_cid_with_attachments(html_final, slug, payload_attachments)
                # resolved_info: {resolved: [...], unresolved: [...]}  (ids cid que sí/no se mapearon)

            # 2) Rehost de <img> http(s)/data:/ruta → S3 (/images)
            html_final, stats = rehost_images_under_template_from_html(html_final, slug)
            print("[DEBUG] rehost stats:", stats)

            # recopila imágenes subidas (ids y urls) del rehost
            images = stats.get("uploaded", [])

            # Si detectamos <img src="cid:..."> no resueltos y NO nos han enviado binarios, devolvemos 400
            if any(s.get("reason") == "cid_in_html_send_eml" for s in (stats.get("skipped") or [])) and not payload_attachments:
                return jsonify({"error": "El HTML contiene imágenes cid:. Sube el .eml (eml_base64) o envía attachments[] con los binarios."}), 400

            # 3) Insertar y subir ficheros extra SIN cid (pdf/mp4/etc.) que vengan en payload.attachments
            #    a s3://.../emails/templates/<slug>/attachments/<filename>
            if payload_attachments:
                html_final, added_files = insert_extra_files_into_html(html_final, slug, payload_attachments)
                # added_files -> [{"filename","content_type","url"}]
                attachments = added_files

           # ========= NUEVO BLOQUE: separar imágenes de firma (< 30 KB) =========
        SIGNATURE_MAX_BYTES = 30 * 1024  # 30 KB

        signature_images = []
        content_images = []

        for img in images or []:
            # Intenta inferir el tamaño en bytes desde distintos posibles campos
            size = img.get("size") or img.get("filesize") or img.get("length") or 0
            try:
                size = int(size)
            except (TypeError, ValueError):
                size = 0  # si no se puede parsear, lo consideramos “desconocido”

            if size and size < SIGNATURE_MAX_BYTES:
                signature_images.append(img)
            else:
                content_images.append(img)

        images = content_images  # solo las de contenido real en `images`
        # ====================================================================
        body_html, signature_html = split_body_and_signature(html_final)

        # 🔹 limpiar imágenes de la firma (quitar fotos grandes / .jpg, etc.)
        signature_html = clean_signature_images(signature_html)

        # si quieres guardar la firma en algún sitio (S3, parcial, etc.), aquí es el sitio.
        # por ahora seguimos como estabas, usando solo el cuerpo para build_framework:
        html_final = body_html

        # Generar y subir la plantilla (template.html/mjml/schema/manifest)
        result = build_framework(
            input_path_or_html=html_final,
            out_dir=out_dir,
            slug=slug,
            lang=lang,
            upload_to_s3=True,
            display_name=name,
            lang_attachments=attachments
        )

        if signature_html:
        # ruta relativa que quieres usar para el manifest
            signature_key = f"emails/templates/{slug}/partials/signature.html"

            os.makedirs(os.path.join("output", slug, "partials"), exist_ok=True)
            with open(os.path.join("output", slug, "partials", "signature.html"), "w", encoding="utf-8") as f:
                f.write(signature_html)

            put_public_s3(
                signature_key,
                signature_html.encode("utf-8"),
                "text/html; charset=utf-8",
                cache_seconds=0
            )

        # añade metadatos
        manifest_path = result.get("manifest")
        if manifest_path and os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                m = json.load(f)
        else:
            m = {}

        m["attachments"] = attachments
        m["images_uploaded"] = images
        if signature_html:
            shared = m.setdefault("shared", {})
            partials = shared.setdefault("partials", {})
            partials.setdefault("signature_html", f"emails/templates/{slug}/partials/signature.html")

        with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(m, f, indent=2, ensure_ascii=False)

        return jsonify({
            "template_id": str(uuid.uuid4()),
            "name": name,
            "slug": slug,
            "paths": result,
            "attachments": attachments,
            "images": images,
            "signature_html": signature_html
        }), 200


           






        
    # GET
    else:
        
        return render_template('upload_template_email.html')  # Cambiá 'login' por tu vista de inicio o login



@application.route('/update_template_email', methods=['GET', 'POST'])
def update_template_email():
   
    if request.method == "POST":
        # tu lógica de POST
        pass

    raw = list_email_templates()  
    print ("raw:", raw )          # <- lo que tengas ahora
    items = _coerce_items(raw)     
    print ("items:", items)       # <- **forzamos lista/dict serializable**

    return render_template("update_template_email.html", items=items)
    

        







@application.route("/list_email_templates", methods=["GET"])
def list_email_templates():
    s3 = boto3.client("s3", region_name=AWS_REGION)
    prefix = "emails/templates/"
    items = []

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix, Delimiter="/"):
        for cp in page.get("CommonPrefixes", []):
            base = cp["Prefix"]  # p.ej. emails/templates/mi-slug/
            slug = base.rstrip("/").split("/")[-1]
            manifest_key = f"{base}manifest.json"

            display_name = slug
            languages = []
            try:
                obj = s3.get_object(Bucket=S3_BUCKET, Key=manifest_key)
                man = json.loads(obj["Body"].read())
                display_name = man.get("display_name") or man.get("slug") or slug
                languages = sorted((man.get("languages") or {}).keys())
            except s3.exceptions.NoSuchKey:
                pass

            items.append({
                "slug": slug,
                "display_name": display_name,
                "languages": languages
            })

    items.sort(key=lambda x: x["display_name"].lower())
    return jsonify(items), 200

@application.route('/templates/<slug>', methods=['DELETE'])
def delete_template(slug):
    """
    Borra TODOS los objetos que cuelgan de emails/templates/<slug>/ en S3.
    Retorna la cantidad de objetos borrados.
       
    """
     
    s3 = get_s3()
    base = ROOT_PREFIX_S3.rstrip("/")
    prefix= f"{base}/{slug.strip('/')}/" 
    paginator = s3.get_paginator("list_objects_v2")
    deleted_count = 0
    to_delete_batch = []

    try:
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
            contents = page.get("Contents", [])
            if not contents:
                continue

            for obj in contents:
                to_delete_batch.append({"Key": obj["Key"]})

                # S3 permite borrar hasta 1000 objetos por llamada
                if len(to_delete_batch) == 1000:
                    resp = s3.delete_objects(
                        Bucket=S3_BUCKET, Delete={"Objects": to_delete_batch, "Quiet": True}
                    )
                    deleted_count += len(resp.get("Deleted", []))
                    to_delete_batch = []

        # Último lote pendiente
        if to_delete_batch:
            resp = s3.delete_objects(
                Bucket=S3_BUCKET, Delete={"Objects": to_delete_batch, "Quiet": True}
            )
            deleted_count += len(resp.get("Deleted", []))

        return "", 204  # borrado OK

    except botocore.exceptions.ClientError as e:
        application.logger.exception("Error borrando en S3: %s", e)
        # Usa -1 para indicar error
        return jsonify({"error": "Error al borrar en S3"}), 500


@application.route("/templates/<slug>/<lang>/preview", methods=["GET"])
def preview_template_lang(slug, lang):
    

    # -------- keys --------
    raw_key       = f"emails/templates/{slug}/{lang}/original.html"
    tpl_key       = f"emails/templates/{slug}/{lang}/template.html"
    schema_key    = f"emails/templates/{slug}/{lang}/schema.json"
    schema_fbk    = f"emails/templates/{slug}/schema.json"
    msg_key       = f"emails/templates/{slug}/{lang}/partials/message.html"
    
    sig_key       = f"emails/templates/{slug}/partials/signature.html"
    manifest_key  = f"emails/templates/{slug}/manifest.json"
    cidmap_key    = f"emails/templates/{slug}/cid-map.json"

    # -------- flags --------
    use_raw_param = request.args.get("raw")      # '1' | '0' | None
    force_demo    = request.args.get("demo") == "1"

    # -------- elegir base (original vs template) --------
    if use_raw_param == "1":
        chosen = raw_key
    elif use_raw_param == "0":
        chosen = tpl_key
    else:
        chosen = tpl_key if s3_key_exists(tpl_key) else raw_key

    if not s3_key_exists(chosen):
        abort(404, description="No hay template.html ni original.html para esta plantilla/idioma")

    print("[DEBUG] preview use_raw:", use_raw_param, "chosen:", chosen)

    html = s3_get_text(chosen) or ""

    # 🚫 ORIGINAL: devolver tal cual (sin montaje)
    if chosen.endswith("/original.html") or use_raw_param == "1":
        # === Adjuntos (mismo código que en template) ===
        s3=get_s3()
        try:
            man_obj = s3.get_object(Bucket=S3_BUCKET, Key=f"emails/templates/{slug}/manifest.json")
            manifest = json.loads(man_obj["Body"].read())
        except botocore.exceptions.ClientError:
            manifest = {}

        try:
            lang_node = (manifest.get("languages") or {}).get(lang) or {}
            att_list  = lang_node.get("attachments") or []
        except Exception:
            att_list = []

        if att_list:
            block = _attachments_html(att_list)  # <-- reutilizas tu helper
            try:
                soup_orig = BeautifulSoup(html, "lxml")
                (soup_orig.body or soup_orig).append(BeautifulSoup(block, "lxml"))
                html = str(soup_orig)
            except Exception:
                low = html.lower()
                idx = low.rfind("</body>")
                html = (html[:idx] + block + html[idx:]) if idx != -1 else (html + block)

        # === Respuesta ===
        resp = Response(html, mimetype="text/html; charset=utf-8")
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'none'; img-src https: data:; style-src 'unsafe-inline'; "
            "font-src https: data:; frame-ancestors 'self';"
        )
        return resp


    # A partir de aquí: TEMPLATE MODE (montaje UNA sola vía)
    is_template_mode = True

    # -------- carga schema -> ctx (para variables que use el template) --------
    ctx = {}
    if is_template_mode:
        schema = {}
        if not force_demo:
            stxt = s3_get_text(schema_key)
            if stxt:
                try: schema = json.loads(stxt)
                except Exception: schema = {}
            else:
                stxt = s3_get_text(schema_fbk)
                if stxt:
                    try: schema = json.loads(stxt)
                    except Exception: schema = {}
        vars_from_schema = (schema.get("variables") or {}) if isinstance(schema, dict) else {}
        demo_defaults = {
            "subject": "Asunto de ejemplo",
            "headline": "Título de ejemplo",
            "hero_url": f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/emails/templates/{slug}/images/1.jpg",
            "hero_alt": "Hero",
            "html_content": "<p><strong>Vista previa:</strong> contenido de muestra.</p>",
            "cta_label": "Ver más",
            "cta_url": "https://ejemplo.com/oferta",
            "cta_url_wrapped": "https://ejemplo.com/click?u={{ cta_url|urlencode }}",
            "unsubscribe_url": "https://ejemplo.com/unsubscribe",
            "open_pixel_url": "data:image/gif;base64,R0lGODlhAQABAAAAACw=",
            "company_address": "Tu empresa · Dirección · Ciudad",
        }
        ctx = {**demo_defaults, **vars_from_schema}

    # Corrige URLs de imágenes en ctx usando manifest (si aplicase)
    mtxt = s3_get_text(manifest_key)
    try: manifest = json.loads(mtxt) if mtxt else {}
    except Exception: manifest = {}

    def manifest_lookup_safe(mani, lang_code, name):
        try:
            return manifest_lookup(mani, lang_code, name)
        except Exception:
            return None

    for k_, v_ in list(ctx.items()):
        if isinstance(v_, str) and "/emails/templates/" in v_ and "/images/" in v_:
            name = v_.split("?",1)[0].rsplit("/",1)[-1]
            mv = manifest_lookup_safe(manifest, lang, name)
            if mv:
                ctx[k_] = mv
  
    def text_to_html_preserving_lf(txt: str) -> str:
        if not txt:
            return ""
        txt = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        txt = txt.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
        return txt

    # 1) Leer piezas
    # 1) Leer piezas
    msg_key = f"emails/templates/{slug}/{lang}/partials/message.html"
    sig_key = f"emails/templates/{slug}/partials/signature.html"
    message   = s3_get_text(msg_key) or ""
    signature = s3_get_text(sig_key) or ""

    #safe_message   = text_to_html_preserving_lf(message)  # → HTML

    safe_message = normalize_incoming_content(message)
    safe_signature = signature                             # ya viene HTML

    # 2) Parsear el template base PRÍSTINO (sin mensaje/firma)
    tpl_key = f"emails/templates/{slug}/{lang}/template.html"
    template_html_string = s3_get_text(tpl_key) or "" 
    tpl_soup = BeautifulSoup(template_html_string, "lxml")

    # Excluir cualquier imagen que esté dentro del slot de firma del template (por si acaso)
    for n in tpl_soup.select('[data-slot="signature"] img, [data-slot="signature"] source'):
        n.extract()

    # Imágenes originales del template (PRÍSTINO)
    #tpl_imgs = tpl_soup.find_all(["img", "source"])

    
    # --- construir bloque de imágenes NO-LOGO directamente desde manifest.shared.images ---

    shared_images = (manifest.get("shared") or {}).get("images") or {}

    non_logo_imgs = [
        meta for name, meta in shared_images.items()
        if isinstance(meta, dict) and not meta.get("is_logo", False)
    ]

    imgs_holder_soup = BeautifulSoup("<div data-composed='images'></div>", "lxml")
    imgs_holder_div = imgs_holder_soup.div

    for meta in non_logo_imgs:
        src = meta.get("url") or meta.get("key")
        if not src:
            continue

        img = imgs_holder_soup.new_tag("img")
        img["src"] = src

        if meta.get("target_w"):
            img["width"] = meta["target_w"]
        if meta.get("target_h"):
            img["height"] = meta["target_h"]

        imgs_holder_div.append(img)

    # --- 3) RECONSTRUIR cuerpo NUEVO: message -> imágenes -> signature ---
    out = BeautifulSoup("<!doctype html><html><head></head><body></body></html>", "lxml")

    # conservar <head> del template prístino (estilos, meta, etc.)
    if tpl_soup.head:
        out.head.replace_with(tpl_soup.head)

    # message
    out.body.append(BeautifulSoup(f"<div data-composed='message'>{safe_message}</div>", "lxml"))

    # imágenes (las no-logo desde el manifest)
    out.body.append(imgs_holder_div)

    # signature
    out.body.append(BeautifulSoup(f"<div data-composed='signature'>{safe_signature}</div>", "lxml"))

    rendered = str(out)
    rendered_before_post = rendered

    
    # -------- Post-procesado (tu pipeline) --------
    cid_map = {}
    cmap_txt = s3_get_text(cidmap_key)
    if cmap_txt:
        try: cid_map = json.loads(cmap_txt)
        except Exception: cid_map = {}

    rendered = replace_cid_everywhere(rendered, cid_map)

    mtxt = s3_get_text(manifest_key)
    try: manifest = json.loads(mtxt) if mtxt else {}
    except Exception: manifest = {}

    rendered = fix_relative_imgs(rendered, slug)
    rendered = apply_manifest_images_all(rendered, manifest, lang=lang)
    rendered = enforce_dimensions_from_manifest(rendered, manifest)
    rendered = inject_preview_css(rendered)

    try:
        soup_final = BeautifulSoup(rendered, "lxml")

        sig_block = soup_final.select_one("[data-composed='signature']")
        if sig_block:
            sig_keys_final = _collect_image_keys(BeautifulSoup(str(sig_block), "lxml"))

            shared_images = (manifest.get("shared") or {}).get("images") or {}

            for im in list(soup_final.find_all("img")):
                # ¿está dentro del bloque de firma?
                parent = im
                inside_signature = False
                while parent is not None:
                    if getattr(parent, "attrs", None) and parent.attrs.get("data-composed") == "signature":
                        inside_signature = True
                        break
                    parent = getattr(parent, "parent", None)
                if inside_signature:
                    continue

                key = _norm_src(im.get("src","") or im.get("srcset",""))
                if key and key in sig_keys_final:
                    meta = shared_images.get(key.lower()) or {}
                    if meta.get("is_logo"):
                        im.decompose()

        rendered = str(soup_final)
    except Exception as e:
        print("[WARN] dedup firmas: salto por error:", e)
        pass

    # -------- attachments (desde manifest si existen) --------
    try:
        lang_node = (manifest.get("languages") or {}).get(lang) or {}
        att_list  = lang_node.get("attachments") or []
    except Exception:
        att_list = []

    if att_list:
        block = _attachments_html(att_list)
        try:
            soup_prev = BeautifulSoup(rendered, "lxml")
            (soup_prev.body or soup_prev).append(BeautifulSoup(block, "lxml"))
            rendered = str(soup_prev)
        except Exception:
            low = rendered.lower()
            idx = low.rfind("</body>")
            rendered = (rendered[:idx] + block + rendered[idx:]) if idx != -1 else (rendered + block)

    # -------- logs útiles --------
    soup_raw = BeautifulSoup(rendered_before_post, "lxml")

    soup_out = BeautifulSoup(rendered, "lxml")
    print("[DEBUG] tpl img count (raw/before):", len(soup_raw.find_all("img")))
    print("[DEBUG] preview img count:", len(soup_out.find_all("img")))
    print("[DEBUG] preview first 10 srcs:", [(i.get("src") or "") for i in soup_out.find_all("img")[:10]])

    # -------- respuesta --------
    resp = Response(rendered, mimetype="text/html; charset=utf-8")
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'none'; img-src https: data:; style-src 'unsafe-inline'; "
        "font-src https: data:; connect-src 'self'; frame-ancestors 'self'; "
        "base-uri 'none'; form-action 'none'; script-src 'none'"
    )
    return resp

# app.py (o donde declares tu Flask app)
from flask import Flask, Response, request, abort
from pathlib import Path

# ------------------ API para editar el cuerpo ------------------
@application.put("/api/templates/<slug>/<lang>/partials/message")
def put_message(slug, lang):
    s3 = get_s3()
    body = request.get_data(as_text=True) or ""
    key = key_message(slug, lang)
    resp = s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="text/html; charset=utf-8",
        CacheControl="no-cache",
    )
    etag = (resp.get("ETag") or "").strip('"')
    print("[PUT:S3]", {"bucket": S3_BUCKET, "key": key, "bytes": len(body.encode()), "etag": etag})
    return {"ok": True, "bucket": S3_BUCKET, "key": key, "bytes": len(body.encode()), "etag": etag}, 200

@application.get("/api/templates/<slug>/<lang>/partials/message")
def get_message(slug, lang):
    s3 = get_s3()
    for key in (key_message(slug, lang), key_original(slug, lang)):
        try:
            obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
            print("[GET:S3]", {"key": key})
            return Response(obj["Body"].read().decode("utf-8", "replace"),
                            mimetype="text/html; charset=utf-8")
        except botocore.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404", "NotFound"):
                continue
            raise
    abort(404, "message.html ni original.html")

# --- API: signature (sin idioma) -------------------------------------------


@application.route("/api/templates/<slug>/partials/signature", methods=["GET"])
def api_get_signature(slug):
    s3 = get_s3()
    key = f"emails/templates/{slug}/partials/signature.html"
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    except botocore.exceptions.ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("NoSuchKey", "404", "NotFound"):
            # si prefieres 200 "" en vez de 404, cambia esto
            abort(404, description="signature.html no existe")
        raise
    txt = obj["Body"].read().decode("utf-8", errors="replace")
    return Response(txt, mimetype="text/html; charset=utf-8")


@application.route("/api/templates/<slug>/partials/signature", methods=["PUT"])
def api_put_signature(slug):
    s3 = get_s3()
    key = f"emails/templates/{slug}/partials/signature.html"
    body = request.get_data(as_text=True) or ""
    # Guarda como HTML; si prefieres text/plain, cambia el ContentType
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="text/html; charset=utf-8",
        CacheControl="no-store",
    )
    return {"ok": True, "mode": "s3", "bucket": S3_BUCKET, "key": key}, 200


# ------------------ PREVIEW compuesto (solo S3) ------------------

@application.get("/templates/<slug>/<lang>/preview")
def preview(slug, lang):
    # raw=1 -> devuelve template.html tal cual desde S3
    raw = request.args.get("raw") == "1"

    tpl = s3_get_text(key_template(slug, lang))
    if tpl is None:
        abort(404, f"template.html no existe en s3://{S3_BUCKET}/{key_template(slug, lang)}")

    if raw:
        return Response(tpl, mimetype="text/html; charset=utf-8")

    # message con fallback a original
    msg = s3_get_text(key_message(slug, lang))
    if msg is None:
        msg = s3_get_text(key_original(slug, lang)) or ""

    sig = s3_get_text(key_signature(slug)) or ""

    # Inyección simple: ajusta a tu sintaxis de marcadores
    html = tpl
    html = re.sub(r"{{\s*>\s*message\s*}}", msg, html)
    html = re.sub(r"{{\s*>\s*signature\s*}}", sig, html)
    html = html.replace("<!-- MESSAGE -->", msg).replace("<!-- SIGNATURE -->", sig)

    return Response(html, mimetype="text/html; charset=utf-8")


@application.route("/list_s3")
def list_s3():
    s3 = boto3.client("s3", region_name=AWS_REGION)
    prefix = request.args.get("prefix") or ROOT_PREFIX_S3
    if not prefix.endswith("/"):
        prefix += "/"

    kwargs = dict(Bucket=S3_BUCKET, Prefix=prefix, Delimiter="/", MaxKeys=1000)
    token = request.args.get("token")
    if token:
        kwargs["ContinuationToken"] = token

    try:
        resp = s3.list_objects_v2(**kwargs)

        folders = []
        for cp in resp.get("CommonPrefixes", []) or []:
            folders.append({
                "name": cp["Prefix"][len(prefix):].rstrip("/"),
                "prefix": cp["Prefix"]
            })

        files = []
        for obj in resp.get("Contents", []) or []:
            key = obj["Key"]
            if key.endswith("/"):
                continue
            relative = key[len(prefix):]
            if "/" in relative:
                continue  # pertenece a subniveles; ya sale en folders
            files.append({
                "key": relative,
                "size": obj.get("Size", 0),
                "last_modified": obj["LastModified"].isoformat(),
                "url": public_url(key)
            })

        return jsonify({
            "ok": True,
            "prefix": prefix,
            "parent_prefix": parent_of(prefix),
            "folders": folders,
            "files": files,
            "is_truncated": bool(resp.get("IsTruncated")),
            "next_token": resp.get("NextContinuationToken"),
            "error": None
        })

   
    except Exception as e:
        err = {"code": "Unexpected", "message": str(e)}

    # ⚠️ En error: mantenemos el mismo shape para no romper el .map()
    return jsonify({
        "ok": False,
        "prefix": prefix,
        "parent_prefix": parent_of(prefix),
        "folders": [],
        "files": [],
        "is_truncated": False,
        "next_token": None,
        "error": err
    }), 500



import dropbox
from flask import jsonify, request
from pathlib import PurePosixPath

def clamp_to_root(path: str) -> str:
    """Fuerza que el path esté bajo DROPBOX_ROOT; si no, devuelve DROPBOX_ROOT."""
    if not path:
        return ROOT_PREFIX_DROPBOX
    # normaliza: sin espacios y siempre con barra inicial
    p = path.strip()
    if not p.startswith("/"):
        p = "/" + p
    # si intenta salir de la raíz virtual, lo fijamos a la raíz
    if not p.startswith(ROOT_PREFIX_DROPBOX):
        return ROOT_PREFIX_DROPBOX
    return p

def get_parent_path(path: str) -> str | None:
    """Calcula la carpeta padre respetando DROPBOX_ROOT."""
    p = PurePosixPath(path)
    parent = str(p.parent)
    if parent == ".":
        parent = ""  # Dropbox usa "" para raíz real
    # Evitar que suba por encima de DROPBOX_ROOT
    if ROOT_PREFIX_DROPBOX and not parent.startswith(ROOT_PREFIX_DROPBOX):
        return None
    return parent

@application.route("/list_dropbox")
def list_dropbox():
    DROPBOX_TOKEN = get_dropbox_access_token()
    dbx = dropbox.Dropbox(DROPBOX_TOKEN)

    raw_path = request.args.get("path", "")
    path = clamp_to_root(raw_path)

    try:
        res = dbx.files_list_folder(path, recursive=False)
    except dropbox.exceptions.ApiError as e:
        return jsonify({
            "ok": False,
            "path": path,
            "parent_path": get_parent_path(path),
            "folders": [],
            "files": [],
            "root_path": ROOT_PREFIX_DROPBOX,
            "error": {"code": "DropboxError", "message": str(e)}
        }), 400

    folders, files = [], []
    for entry in res.entries:
        if isinstance(entry, dropbox.files.FileMetadata):
            tmp = dbx.files_get_temporary_link(entry.path_lower)
            files.append({
                "name": entry.name,
                "path": entry.path_display,
                "size": entry.size,
                "client_modified": entry.client_modified.isoformat(),
                "url": tmp.link
            })
        elif isinstance(entry, dropbox.files.FolderMetadata):
            folders.append({
                "name": entry.name,
                "path": entry.path_display
            })

    return jsonify({
        "ok": True,
        "path": path,
        "parent_path": get_parent_path(path),  # será None cuando estés en /1
        "folders": folders,
        "files": files,
        "error": None
    })

# --- Backend: copiar desde Dropbox a S3 ---


@application.post("/dbx_to_s3")
def dbx_to_s3():
    try:
        data = request.get_json(force=True)
        dbx_path = data.get("dbx_path")
        s3_key   = data.get("s3_key")
        if not dbx_path or not s3_key:
            return jsonify({"ok": False, "error": {"message": "Parámetros requeridos: dbx_path y s3_key"}}), 400

        # 1) Descargar bytes desde Dropbox
        DROPBOX_TOKEN = get_dropbox_access_token()
        dbx = dropbox.Dropbox(DROPBOX_TOKEN)
        

        md, resp = dbx.files_download(dbx_path)
        body = resp.content




        
        

        s3 = boto3.client("s3", region_name=AWS_REGION)

        md5_b64 = base64.b64encode(hashlib.md5(body).digest()).decode("ascii")

        content_type = mimetypes.guess_type(s3_key)[0] or "application/octet-stream"

        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=body,
            ContentType=content_type,
            ContentMD5=md5_b64,
            CacheControl="no-cache, no-store, must-revalidate",
            Expires=0,
        )

        # 3. Actualizar manifest SOLO para esta imagen
        try:
            slug = s3_key.split("/")[2]  # emails/templates/<slug>/...
            updated_manifest = update_manifest_for_key(slug, s3_key)
        except Exception as e:
            # Si algo falla, reconstruye todo
            updated_manifest = update_manifest(slug)

        # 4. Devolver datos útiles al front (etag y last_modified actualizados)
        img_name = s3_key.rsplit("/", 1)[-1]
        img_data = (
            updated_manifest
            .get("shared", {})
            .get("images", {})
            .get(img_name, {})
        )

        return jsonify({
            "ok": True,
            "s3_key": s3_key,
            "etag": img_data.get("etag"),
            "last_modified": img_data.get("last_modified"),
            "url": img_data.get("url"),
        })

      

    except dropbox.exceptions.ApiError as e:
        return jsonify({"ok": False, "error": {"message": f"Dropbox error: {e}"}}), 400
    except boto3.exceptions.Boto3Error as e:
        return jsonify({"ok": False, "error": {"message": f"S3 error: {e}"}}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": {"message": str(e)}}), 500


@application.route('/upload_files_s3', methods=['GET', 'POST'])
def upload_files_s3():
    if request.method == "POST":
        # Procesar la subida del archivo
        pass

    # GET
    else:
        
        return render_template('upload_files_s3.html')  # Cambiá 'login' por tu vista de inicio o login





@application.route('/base', methods=['GET', 'POST'])
def base():
    
    return render_template('base.html')


@application.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()  # Elimina todos los datos de sesión
    return redirect(url_for('login'))  # Cambiá 'login' por tu vista de inicio o login

    


# Función para crear la base de datos si no existe
#def crear_base_si_no_existe():
#    with application.app_context():
#        db.create_all()

# Crear la base de datos y las tablas
crear_base_si_no_existe()

# Determinar el entorno de ejecución



if  __name__ == "__main__":     application.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)




