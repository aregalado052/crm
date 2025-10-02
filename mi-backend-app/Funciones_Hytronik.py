import json

import sys
import pycurl # type: ignore

#from acceso_BD import insertar_datos # type: ignore


from io import BytesIO
#from acceso_BD import dame_todos_los_datos # type: ignore

import random

import pycurl
from io import BytesIO

from datetime import datetime, time, timedelta,timezone
import time as time



API_SCRET= "Mg6MjW4572Wb1dt43cB794cRnP229B9r"#"EKav0288J3YNM0rwPg223H6S2xxyq50H"
RAW_PASSWORD = "946682011"
API_KEY = "iberica" #"demo"
EMAIL = "info@planetpower.es"
URL=  "https://openapi.koolmesh.com/v1" #"http://3.

MIN="5"
MAX ="55"
UID_HYTRONIK=766


token=""

def regular_pista(uid,nid,lightID,brightness):
   
    if nid== 16606 :
       
        return
   
    try :
        status_code,response_body,token = pedir_token_appi_hytronik()
        if status_code != 200:
            print(f"❌ Error en la solicitud: {status_code} - {response_body}")
            return status_code,response_body  

    except Exception as e:
        print("❌ No se recibió un token válido de Hytronik.  Deteniendo ejecución.")
        return status_code, response_body



    url = URL+"/ctrl/light/brightness"
    headers = [
        "api_key: " + API_KEY,
        "Request-Origion: SwaggerBootstrapUi",
        "accept: application/json",
        "Content-Type: application/json",
        "token: "+token

    ]

    data = json.dumps({
            "uid" : uid,
            "nid" : nid,
            "lightId" : lightID,
            "brightness" : brightness
        })

    buffer = BytesIO()

    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.POST, 1)
    c.setopt(c.POSTFIELDS, data)
    c.setopt(pycurl.SSL_VERIFYPEER, 0)
    c.setopt(pycurl.SSL_VERIFYHOST, 0)

     # Establecer tiempos de espera
    c.setopt(pycurl.CONNECTTIMEOUT, 10)  # Tiempo máximo para establecer la conexión
    c.setopt(pycurl.TIMEOUT, 30)         # Tiempo máximo total de la solicitud

    # Configurar encabezados
    
    c.setopt(c.HTTPHEADER, headers)

    # Capturar la respuesta
    c.setopt(c.WRITEDATA, buffer)

    

    # Ejecutar la solicitud   

    try:
        c.perform()
        status_code = c.getinfo(pycurl.RESPONSE_CODE)
        response_body = buffer.getvalue().decode('utf-8')
    except pycurl.error as e:
        # Manejar errores de pycurl
        status_code = None
        response_body = f"Error en la solicitud: {e}"
    finally:
        c.close()

    return status_code, response_body







def apagar_pista(uid,nid,lightID):

    if nid== 16606 :
       
        return
    
 


    try :
        status_code,response_body,token = pedir_token_appi_hytronik()
        if status_code != 200:
            print(f"❌ Error en la solicitud: {status_code} - {response_body}")
            return status_code, response_body  

    except Exception as e:
        print("❌ No se recibió un token válido de Hytronik.  Deteniendo ejecución.")
        return status_code, response_body


    print("token", token)

    url = URL+"/ctrl/light/switch"

    headers = [
        "api_key: " + API_KEY,
        "Request-Origion: SwaggerBootstrapUi",
        "accept: application/json",
        "Content-Type: application/json",
        "token: "+token

    ]

    print ("uid", uid, "nid", nid, "lightID", lightID)

    data = json.dumps({
            "uid" : uid,
            "nid" : nid,
            "lightId" : lightID,
            "onOff" : "0"
            
            })

    buffer = BytesIO()

    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.POST, 1)
    c.setopt(c.POSTFIELDS, data)
    c.setopt(pycurl.SSL_VERIFYPEER, 0)
    c.setopt(pycurl.SSL_VERIFYHOST, 0)
     # Establecer tiempos de espera
    c.setopt(pycurl.CONNECTTIMEOUT, 10)  # Tiempo máximo para establecer la conexión
    c.setopt(pycurl.TIMEOUT, 30)         # Tiempo máximo total de la solicitud


    # Configurar encabezados
    
    c.setopt(c.HTTPHEADER, headers)

    # Capturar la respuesta
    c.setopt(c.WRITEDATA, buffer)

    # Ejecutar la solicitud
     
    try:
        c.perform()
        status_code = c.getinfo(pycurl.RESPONSE_CODE)
        response_body = buffer.getvalue().decode('utf-8')
        print("response_body", response_body)
    except pycurl.error as e:
        # Manejar errores de pycurl
        status_code = None
        response_body = f"Error en la solicitud: {e}"
    finally:
        c.close()

    return status_code, response_body



def petición_datos_hytronik(url_peticion, data, headers):

        # Definir la URL y los datos   
    url = URL + url_peticion

    # Configurar la respuesta
    buffer = BytesIO()

    # Crear una instancia de Curl
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.POST, 1)
    c.setopt(c.POSTFIELDS, data)
    c.setopt(pycurl.SSL_VERIFYPEER, 0)
    c.setopt(pycurl.SSL_VERIFYHOST, 0)
    # Establecer tiempos de espera
    c.setopt(pycurl.CONNECTTIMEOUT, 10)  # Tiempo máximo para establecer la conexión
    c.setopt(pycurl.TIMEOUT, 30)         # Tiempo máximo total de la solicitud



    # Configurar encabezados

    
    c.setopt(c.HTTPHEADER, headers)

    # Capturar la respuesta
    c.setopt(c.WRITEDATA, buffer)

    # Ejecutar la solicitud
     
    try:
        c.perform()
        status_code = c.getinfo(pycurl.RESPONSE_CODE)
        response_body = buffer.getvalue().decode('utf-8')
        
    except pycurl.error as e:
        # Manejar errores de pycurl
        status_code = 500
        response_body = f"Error en la solicitud: {e}"
    finally:
        c.close()

    return status_code, response_body


def obtener_datos_appi_hytronik(uid,link_pistas):

   
    
    try :
        status_code,response_body,token = pedir_token_appi_hytronik()
        if status_code != 200:
            print(f"❌ Error en la solicitud: {status_code} - {response_body}")
            return status_code,  link_pistas  

    except Exception as e:
        print("❌ No se recibió un token válido de Hytronik.  Deteniendo ejecución.")
        return status_code,response_body, link_pistas


    

    

   

   

   

    
            
        
    for pista in link_pistas:
        if isinstance(pista, dict): 
 
            try:
                
                              

                # Definir la URL y los datos
                url = "/ctrl/light/query"
                data = json.dumps({
                    "uid" : uid,
                    "nid" : pista["NID"    ],
                    "lightId" : pista["lightID"]
                })

                headers = [
                    
                    "api_key: " + API_KEY,
                    "Request-Origion: SwaggerBootstrapUi",
                    "accept: application/json",
                    "Content-Type: application/json",
                    "token: "+token
                ]

                status_code,response_body = petición_datos_hytronik(url, data, headers)
                if status_code != 200:
                    print(f"❌ Error en la solicitud: {status_code} - {response_body}")
                    return status_code, response_body, link_pistas
                
                
                
                try:
                    response_json = json.loads(response_body)
                    # Extraer un valor específico (ejemplo: 'lightness')
                    msg = response_json.get("msg", "No encontrado")

                    if msg == "SUCCESS" :
                        lightness = response_json.get("data",{}).get("lightness", "No encontrado")
                        pista["lightness"] = lightness
                        if (int(lightness)>int(MIN)) : pista["On/Off"]="1" 
                        else : pista["On/Off"]="0"
                        #print("SUCCESS")
                    else : 
                        lightness = "55"
                        pista["lightness"] = lightness
                        pista["On/Off"]="1"   
                        #print("FAIL")
                     
                    print ("Pista", pista["PistaHT"],"Regulación al :", lightness) 

                except json.JSONDecodeError:
                    print("❌ Error: respuesta no es JSON válida")
                    
            except Exception as e:
                print("❌ Excepción al procesar pista:", e)
               

    # ✅ Fuera del for: aquí ya procesaste todas las pistas
    return status_code, response_body, link_pistas


def pedir_token_appi_hytronik():
    import json
    import os

    # Definir la URL y los datos
    url = "/test/encode/password"
    data = json.dumps({
        "api_secret": API_SCRET,
        "raw_password": RAW_PASSWORD
    })

    headers = [
        "api_key: " + API_KEY,
        "Request-Origion: SwaggerBootstrapUi",
        "accept: application/json",
        "Content-Type: application/json"
    ]

    # Obtener la respuesta como string
    status_code,response_body = petición_datos_hytronik(url, data, headers)

    if status_code != 200:
        print(f"❌ Error en la solicitud: {status_code} - {response_body}")
        return status_code, response_body, token

    try:
        response_json = json.loads(response_body)
        encoded_password = response_json.get("data")
        if not encoded_password:
            raise ValueError("No se obtuvo 'encoded_password' desde la respuesta")
    except (json.JSONDecodeError, ValueError) as e:
        print("Error al obtener encoded_password:", e)
        return None  # o puedes lanzar la excepción si lo prefieres

    # Login con password codificado
    url = "/user/email/login"
    data = json.dumps({
        "email": EMAIL,
        "password": encoded_password
    })

    status_code,response_body = petición_datos_hytronik(url, data, headers)

    if status_code != 200:
        print(f"❌ Error en la solicitud: {status_code} - {response_body}")
        return status_code, response_body, token

    
    try:
        response_json = json.loads(response_body)
        print("✅ JSON recibido:", response_json)
    except json.JSONDecodeError as e:
        print("❌ Error al parsear JSON:", e)
        print("Contenido de la respuesta:", response_body)
        return status_code, response_body, token
    
    data = response_json.get("data")
    if data is None:
        print("❌ Error al obtener el token: data es None. Mensaje:", response_json.get("msg"))
        return status_code, response_body, token

    token = data.get("token")
    if not token:
        print("❌ Token no encontrado en la respuesta:", data)
        return status_code, response_body, token

    print("✅ Token recibido:", token)
    return status_code,response_body, token



def obtener_pistas_hytronik(uid, pid,pistas_hytronik):

    
    try :
        status_code,response_body,token = pedir_token_appi_hytronik()
       
        if status_code != 200:
            print(f"❌ Error en la solicitud: {status_code} - {response_body}")
            return status_code,  pistas_hytronik  

    except Exception as e:
        print("❌ No se recibió un token válido de Hytronik.  Deteniendo ejecución.")
        return status_code,response_body, pistas_hytronik

    url = "/network/list"

    data = json.dumps({
        "uid" : uid,
        "pid" : pid
    })

   
    # Configurar encabezados
    headers = [
    "api_key: " + API_KEY,
    "Request-Origion: SwaggerBootstrapUi",
    "accept: application/json",
    "Content-Type: application/json",
    "token: "+token
    ]
    status_code, response_body = petición_datos_hytronik(url, data, headers)

   

    if status_code != 200:
        print(f"❌ Error en la solicitud: {status_code} - {response_body}")
        return status_code,response_body,  pistas_hytronik



    try:
        response_json = json.loads(response_body)

        # Extraer un valor específico (ejemplo: 'token')
        #nid = response_json.get("data",{}).get("nid", "No encontrado")
        data = response_json.get("data", [])

        # Aseguramos que sea una lista
        if isinstance(data, dict):
            data = [data]
        elif data is None:
            data = []

        nids = [item.get("nid") for item in data if isinstance(item, dict)]

            
            
        

    except json.JSONDecodeError:
        print("Error: La respuesta no es un JSON válido")
    
  
    
    url = "/network/lights"

    data = json.dumps({
        
        "uid" : uid,
        "nid" : nids[0]
    })

    # Configurar encabezados
    headers = [
        "api_key: " + API_KEY,
        "Request-Origion: SwaggerBootstrapUi",
        "accept: application/json",
        "Content-Type: application/json",
        "token: "+token
        ]


    status_code,response_body = petición_datos_hytronik(url, data, headers)
   
    if status_code != 200:
        print(f"❌ Error en la solicitud: {status_code} - {response_body}")
        return status_code,response_body,pistas_hytronik

    #link_pistas_actualizadas = []  # ← IMPORTANTE: definirlo antes del bucle principal

   

    try:
        response_json = json.loads(response_body)


        dids = [item.get("did") for item in response_json.get("data", []) if isinstance(item, dict)]
        #names_dids = [item.get("name") for item in response_json.get("data", []) if isinstance(item, dict)]
        lights = [item.get("lights") for item in response_json.get("data", []) if isinstance(item, dict)]

        
    
        

        k=0
        while k < (len(dids)): 

            

            
            


            try:
                
                light_ids = [light.get("lightId") for light in lights[k]]
                name_light_ids = [light.get("name") for light in lights[k]]
                OnOff_ids = [light.get("onOff") for light in lights[k]]
                tipo_iluminacion =  "Individual"

                pistas_hytronik.append({
                    "light_ids": light_ids,
                    "name_light_ids": name_light_ids,
                    "onoff_ids": OnOff_ids,
                    "tipo_iluminacion": tipo_iluminacion,
                    "name_light_ids_2": "",
                    "nid": nids[0]
                    })


                
               
                
                       
                
               
                                       
                k+=1
            except json.JSONDecodeError:
                return status_code,response_body,pistas_hytronik
       
        

    except json.JSONDecodeError:
      
        return status_code, response_body,pistas_hytronik

    
   
    return status_code, response_body, pistas_hytronik






