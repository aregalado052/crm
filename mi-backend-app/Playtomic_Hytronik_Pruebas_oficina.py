import json
import random
import sys
from models import Horario

from app_init import create_app
from funciones_tiempo import obtener_horario_para_fecha
import random

import pycurl
from io import BytesIO

from datetime import datetime, time, timedelta,timezone
import time as tm

from Funciones_Hytronik import apagar_pista,regular_pista,obtener_datos_appi_hytronik
    


NID_OFICINA = "18683"
NID_M4= "16606" 
UID = "766"
PID=3461
UMBRAL_ON = 28
MIN="5"
MAX ="55"
HORA_INICIO = "07:50:00"
HORA_FIN = "23:59:59"
CLUB = "OFICINA" # M4, OFICINA
ENTORNO = "PRUEBAS" #PRUEBAS, REAL
PLAYTOMIC= "OFF" # ON,OFF
ONOFF_PISTAS = "true" # true, false
TIEMPO_EXTRA_INCIO = 10
TIEMPO_EXTRA_FIN = 30
HORARIO_BD = "ON" # ON/OFF indica que el horario se consigue de la Base de Datos

HORA_CAMBIO_CICLO = "04:00:00"

HORA_INICIO_APAGAR_LUZ_SERVICIO ="09:00:00"
HORA_FIN_APAGAR_LUZ_SERVICIO ="22:00:00"
ILUMINACION_SERVICIO = False

token=""

application = create_app()
#uid =  p1.get("uid")
#pid = p1.get("pid")

#UID = str(uid)
#print ("UID: " + UID)
#PID = int(pid)
#print ("PID: " + str(PID))

if PID==14038 :
    PLAYTOMIC= "ON" # ON,OFF
    ONOFF_PISTAS = "true" # true, false
else :
    PLAYTOMIC= "OFF" # ON,OFF
    ONOFF_PISTAS = "true" # true, false

# Convierte a segundos teniendo en cuenta el cambio de Ciclo

def convertir_a_segundos(hora_str):
    h, m, s = map(int, hora_str.split(":"))
    hc,mc,sc = map(int, HORA_CAMBIO_CICLO.split(":"))    
    segundos = h * 60 *60 + m*60 +s
    if h < hc :  # Consideramos que las horas menores a CAMBIO DE CICLO pertenecen al día anterior
        segundos += 24 * 60 * 60
    return segundos


# Comparación de horas
def comparar_horas(hora1, hora2):

    """
    Compara horas .

    Args:
        hora1 (time)
        hora2 (time)
    Returns:
        True o False  .
    """
    return convertir_a_segundos(hora1.strftime("%H:%M:%S")) > convertir_a_segundos(hora2.strftime("%H:%M:%S"))     




hora_inicio = datetime.strptime(HORA_INICIO, "%H:%M:%S").time()

hora_fin = datetime.strptime(HORA_FIN, "%H:%M:%S").time()

#hora_actual_dt = datetime.utcnow() + timedelta(hours=1)



hora_actual_dt = datetime.now(timezone.utc) + timedelta(hours=2)

hora_actual=hora_actual_dt.time()

hora_cambio_ciclo = datetime.strptime(HORA_CAMBIO_CICLO,"%H:%M:%S").time()



fecha_base = datetime.today().date()  # Usamos la fecha de hoy

if HORARIO_BD== "ON" :
    with application.app_context():
        horario, franjas = obtener_horario_para_fecha(PID, fecha_base)

    if horario:
        hora_inicio = horario.hora_inicio
        hora_fin = horario.hora_fin
        print(f"Horario de Reservas: {fecha_base} - {horario.hora_inicio} a {horario.hora_fin}")
        print("Franjas asignadas:")
        if (franjas):
            ILUMINACION_SERVICIO = True
            for franja in franjas:
                print(f" → {franja.hora_inicio} - {franja.hora_fin}")
        else : ILUMINACION_SERVICIO = False
    else:
        print("No se encontró asignación diaria para ese PID y fecha.")
        


















def es_horario_apagar_pistas () :
    """
    Retorna True si hora_actual está entre la hora fin
    o si está dentro de alguna franja en la lista y hora_fin extra de 3 minutos,
    """
    # Verificar si está en el horario principal
    hora_fin_dt = datetime.combine(fecha_base, hora_fin)
    hora_apagado_total_dt= hora_fin_dt + timedelta(minutes= 3)
    hora_apagado_total= hora_apagado_total_dt.time()

    
   
   

    if comparar_horas(hora_actual, hora_inicio) and comparar_horas(hora_apagado_total, hora_actual):
        return False

    # Verificar si pertenece a alguna franja
    for franja_item in franjas:
        inicio = franja_item.hora_inicio
        fin= franja_item.hora_fin
        fin_dt = datetime.combine(fecha_base, fin)
        hora_apagado_total_dt= fin_dt + timedelta(minutes= 3)
        hora_apagado_total= hora_apagado_total_dt.time()


       
            # Franja normal
        if comparar_horas( hora_actual,inicio) and comparar_horas(hora_apagado_total, hora_actual):
                return False

    return(True)







def es_horario_apagado_total():
    """
    Retorna False si hora_actual está entre hora_inicio y hora_fin,
    o si está dentro de alguna franja en la lista.
    """
    # Verificar si está en el horario principal
    if comparar_horas(hora_actual, hora_inicio) and comparar_horas(hora_fin, hora_actual):
        return False

    # Verificar si pertenece a alguna franja
    for franja_item in franjas:
        inicio = franja_item.hora_inicio
        fin= franja_item.hora_fin

       
            # Franja normal
        if comparar_horas( hora_actual,inicio) and comparar_horas(fin, hora_actual):
                return False
        
    return True








def es_horario_reservas () :
    if (hora_fin > hora_cambio_ciclo):
        if (hora_actual< hora_fin ) and (hora_actual > hora_inicio ) : 
            return True
        else :  
            return False
                    
    else :
        if(hora_actual> hora_inicio ):
                return True
        else :
            if(hora_actual< hora_cambio_ciclo) :
                if (hora_actual> hora_fin ):
                    return False
                else :
                    return True


def es_horario_iluminacion_servicio_activa():
    """
    Usa la función comparar_horas para verificar si hora_actual cae en alguna franja.
    """
    if ILUMINACION_SERVICIO:
        for franja_item in franjas:
            inicio = franja_item.hora_inicio
            fin = franja_item.hora_fin
        if comparar_horas(hora_actual, inicio) and comparar_horas(fin, hora_actual):
            return True
    return False


if (es_horario_apagado_total ()) :  
    print("Horario Fuera de Servicio. Pistas en OFF :", hora_actual)
    #return {
    #"statusCode": 200
    #}  

else :
    
    

    

    if (PID==3461) :

        
        link_pistas = [
            
            {"PistaPT": "0001477", "PistaHT": "luminaria negra izquierda ","On/Off":"0","Off":MIN,"On":MAX,"lightID":"000000", "Pista D":"", "lightID_Pista D":"000000", "lightness":"0"},
            {"PistaPT": "0001478", "PistaHT": "luminaria azul derecha ","On/Off":"0","Off":"0","On":MAX,"lightID":"000000", "Pista D":"", "lightID_Pista D":"000000", "lightness":"0"},
        
            
        ]

        NID= NID_OFICINA

            





    

    if (PID==14038) :
        link_pistas = [
            
            {"PistaPT": "0001477", "PistaHT": "Pista 1","On/Off":"0","Off":MIN,"On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001478", "PistaHT": "Pista 2","On/Off":"0","Off":"0","On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001479", "PistaHT": "Pista 3","On/Off":"0","Off":"0","On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001480", "PistaHT": "Pista 4","On/Off":"0","Off":"0","On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001481", "PistaHT": "Pista 5","On/Off":"0","Off":"0","On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001482", "PistaHT": "Pista 6","On/Off":"0","Off":"0","On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001483", "PistaHT": "Pista 7","On/Off":"0","Off":"0","On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001484", "PistaHT": "Pista 8","On/Off":"0","Off":"0","On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001485", "PistaHT": "Pista 9","On/Off":"0","Off":MIN,"On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001499", "PistaHT": "Pista10","On/Off":"0","Off":"0","On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001501", "PistaHT": "Pista 11","On/Off":"0","Off":"0","On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001502", "PistaHT": "Pista 12","On/Off":"0","Off":MIN,"On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001503", "PistaHT": "Pista 13","On/Off":"0","Off":"0","On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001504", "PistaHT": "Pista 14","On/Off":"0","Off":"0","On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001505", "PistaHT": "Pista 15","On/Off":"0","Off":"0","On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001506", "PistaHT": "Pista 16","On/Off":"0","Off":MIN,"On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001507", "PistaHT": "Pista 17","On/Off":"0","Off":"0","On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001508", "PistaHT": "Pista 18","On/Off":"0","Off":"0","On":MAX,"lightID":"000000","Pista D":"", "lightID_Pista D":"000000"},
            {"PistaPT": "0001509", "PistaHT": "Pista 19 IZQUIERDA","On/Off":"0","Off":"0","On":MAX,"lightID":"000000","Pista D":"Pista 19 DERECHA", "lightID_Pista D":"000000"},
            {"PistaPT": "0001510", "PistaHT": "Pista 20 IZQUIERDA","On/Off":"0","Off":"0","On":MAX,"lightID":"000000","Pista D":"Pista 20 DERECHA", "lightID_Pista D":"000000"}
        ]

        NID= NID_M4

        # Asegurar que link_pistas sea una lista


    

    if isinstance(link_pistas, dict):
        link_pistas = [link_pistas]  # Convertir a lista si es un solo diccionario

    if(link_pistas) : codigo, mensaje, link_pistas = respuesta= obtener_datos_appi_hytronik (UID,PID,link_pistas=link_pistas)



    if es_horario_reservas ():

        print("Horario de Reservas :", hora_actual)
        numero_aleatorio = random.randint(0, 3)
        if (PLAYTOMIC == "OFF")  :
            R= []
            R.append(["true", "true"])
            R.append(["true", "false"])
            R.append(["false", "false"])
            R.append(["false", "true"])

            print ("NUMERO", numero_aleatorio)


              # Incluye tanto 0 como 3

        i=0

        
        for pistas in link_pistas:


            if (PLAYTOMIC== "ON"):

                # Buffer para almacenar la respuesta
                buffer = BytesIO()

                # Crear una instancia de Curl
                c = pycurl.Curl()

                url = "https://m3.syltek.com//api/Activateligths?idresource="+ pistas["PistaPT"] + "&apikey=9rgHGqjybKHSPfoqujz55zfW0MAhNoJyzNJRqrNBYazupv6Zx57wWRjMmvJ6ZbWZaktcHG0dG8f4aWHPQLVTsp&ignoreSunLigth=true&useExtrasPeriods=false"

                

                # Configurar la solicitud GET
                c.setopt(c.URL, url)
                c.setopt(c.WRITEDATA, buffer)  # Guardar respuesta en buffer

                # Ejecutar la solicitud
                c.perform()

                # Obtener el código de respuesta HTTP
                http_status = c.getinfo(c.RESPONSE_CODE)

                # Cerrar la conexión
                c.close()

                # Mostrar la respuesta
                #print("Código de respuesta:", http_status)
                respuesta = buffer.getvalue().decode("utf-8")
                #print("Respuesta:", buffer.getvalue().decode("utf-8"))
            else :  
                respuesta = R[numero_aleatorio][i]
                print("Pista ",pistas["PistaHT"], "respuesta:", respuesta) 
                    

            if respuesta == "true" and int(pistas["lightness"]) < UMBRAL_ON :
                
                print ("Enciendo Pista ", pistas["PistaHT"], "Ajustando la regulación ", pistas["On"])

                if (pistas["Pista D"]) != "" :
                    print ("Enciendo Pista ", pistas["Pista D"], "Ajustando la regulación ", pistas["On"])

                if(ONOFF_PISTAS == "true"):
                    response_body= regular_pista (UID,NID,pistas["lightID"],pistas ["On"])
                    print("Respuesta: ", response_body)

                    if (pistas["Pista D"]) != "" :
                        response_body= regular_pista (UID,NID,pistas["lightID_Pista D"],pistas ["On"])
                        print("Respuesta: ", response_body)
            else :
                if respuesta == "false" :

                    if(int(pistas["lightness"])> UMBRAL_ON):
                        if (pistas["Off"]=="0"):
                            print ("Apago Pista ", pistas["PistaHT"], "Poniendola en OFF")
                            if (pistas["Pista D"]) != "" :
                                    print ("Apago Pista ", pistas["Pista D"], "Poniendola en OFF")
                        

                            if(ONOFF_PISTAS == "true"): 

                                response_body=apagar_pista(UID,NID,pistas["lightID"])
                                print("Respuesta: ", response_body)

                                if (pistas["Pista D"]) != "" :

                                    response_body=apagar_pista(UID,NID,pistas["lightID_Pista D"])
                                    print("Respuesta: ", response_body)

                        else: 

                            if es_horario_iluminacion_servicio_activa() :
                                print("Apago Pista ",pistas["PistaHT"], "Regulando la pista a ", pistas["Off" ])

                                if (pistas["Pista D"]) != "" :
                                        print ("Apago Pista ", pistas["Pista D"], "Regulando la pista a ", pistas["Off" ])

                                if(ONOFF_PISTAS == "true"): 

                                    response_body= regular_pista (UID,NID,pistas["lightID"],pistas ["Off"])
                                    print("Respuesta: ", response_body)
                                
                                    if (pistas["Pista D"]) != "" :

                                        response_body= regular_pista (UID,NID,pistas["lightID_Pista D"],pistas ["Off"])
                                        print("Respuesta: ", response_body)
                            else :
                                # Si la pista esta regulada al mínimo y deberia estar apagada la apago OFF
                                print ("Apago Pista ", pistas["PistaHT"], "Poniendola en OFF")
                                if (pistas["Pista D"]) != "" :
                                        print ("Apago Pista ", pistas["Pista D"], "Poniendola en OFF")
                                if(ONOFF_PISTAS == "true"): 

                                    response_body=apagar_pista(UID,NID,pistas["lightID"])
                                    print("Respuesta: ", response_body)

                                    if (pistas["Pista D"]) != "" :

                                        response_body=apagar_pista(UID,NID,pistas["lightID_Pista D"])
                                        print("Respuesta: ", response_body)
                                



                    else :
                    #  # Si no tengo reserva y la pista esta encendida por debajo del UMBRAL_ON o apagada

                        if ((pistas["Off"]!="0") and (str(pistas["lightness"]) == "0")) : 
                            # Si la pista esta apagada OFF y debería estar regulada al mínimo la regulo
                            if es_horario_iluminacion_servicio_activa() :
                                print("Apago Pista ",pistas["PistaHT"], "Regulando la pista a ", pistas["Off" ])
                                
                                if (pistas["Pista D"]) != "" :
                                        print ("Apago Pista ", pistas["Pista D"], "Regulando la pista a ", pistas["Off" ])
                                
                                if(ONOFF_PISTAS == "true"): 

                                    response_body= regular_pista (UID,NID,pistas["lightID"],pistas ["Off"])
                                    print("Respuesta: ", response_body)
                                
                                    if (pistas["Pista D"]) != "" :

                                        response_body= regular_pista (UID,NID,pistas["lightID_Pista D"],pistas ["Off"])
                                        print("Respuesta: ", response_body)
                            else: 
                            
                                # Si la pista esta regulada al mínimo y deberia estar apagada la apago OFF
                                print ("Apago Pista ", pistas["PistaHT"], "Poniendola en OFF")
                                if (pistas["Pista D"]) != "" :
                                        print ("Apago Pista ", pistas["Pista D"], "Poniendola en OFF")
                                if(ONOFF_PISTAS == "true"): 

                                    response_body=apagar_pista(UID,NID,pistas["lightID"])
                                    print("Respuesta: ", response_body)

                                    if (pistas["Pista D"]) != "" :

                                        response_body=apagar_pista(UID,NID,pistas["lightID_Pista D"])
                                        print("Respuesta: ", response_body)



                        else :
                            if ((pistas["Off"]=="0") and (str(pistas["lightness"]) != "0")) :

                                # Si la pista esta regulada al mínimo y deberia estar apagada la apago OFF
                                print ("Apago Pista ", pistas["PistaHT"], "Poniendola en OFF")
                                if (pistas["Pista D"]) != "" :
                                        print ("Apago Pista ", pistas["Pista D"], "Poniendola en OFF")
                            

                                if(ONOFF_PISTAS == "true"): 

                                    response_body=apagar_pista(UID,NID,pistas["lightID"])
                                    print("Respuesta: ", response_body)

                                    if (pistas["Pista D"]) != "" :

                                        response_body=apagar_pista(UID,NID,pistas["lightID_Pista D"])
                                        print("Respuesta: ", response_body)




            i+=1

        #return {
        #   "statusCode": 200
        #   }  
        
        

    else : 

        if es_horario_iluminacion_servicio_activa() :
        

        # Apago todas las pistas menos las de servicio que las dejo reguladas al mínimo

            print("Horario de iluminación de cortesía. Pistas de servicio reguladas al mínimo :", hora_actual)

            for pistas in link_pistas:
                if(int(pistas["lightness"])> UMBRAL_ON):
                    if (pistas["Off"]=="0"):
                        print ("Apago Pista ", pistas["PistaHT"], "Poniendola en OFF")
                        if (pistas["Pista D"]) != "" :
                                print ("Apago Pista ", pistas["Pista D"], "Poniendola en OFF")

                        

                        if(ONOFF_PISTAS == "true"): 

                            response_body=apagar_pista(UID,NID,pistas["lightID"])
                        
                            print("Respuesta: ", response_body)

                            if (pistas["Pista D"]) != "" :

                                response_body=apagar_pista(UID,NID,pistas["lightID_Pista D"])
                                print("Respuesta: ", response_body)
                                
                    else: 
                        print("Regulamos Pista ",pistas["PistaHT"], "Regulando la pista a ", pistas["Off" ])

                        if (pistas["Pista D"]) != "" :
                                print ("Regulamos Pista ", pistas["Pista D"], "Regulando la pista a ", pistas["Off" ])

                        if(ONOFF_PISTAS == "true"): 

                            response_body= regular_pista (UID,NID,pistas["lightID"],pistas ["Off"])
                            print("Respuesta: ", response_body)

                            if (pistas["Pista D"]) != "" :

                                response_body= regular_pista (UID,NID,pistas["lightID_Pista D"],pistas ["Off"])
                                print("Respuesta: ", response_body)

        # return {
            #    "statusCode": 200
            #   }  

        
        
        
if es_horario_apagar_pistas () :                       

    print("Horario de apagar pistas total. Pistas en OFF :", hora_actual)

    for pistas in link_pistas:
        
        print ("Apago Pista ", pistas["PistaHT"], "Poniendola en OFF")
        if (pistas["Pista D"]) != "" :
                print ("Apago Pista ", pistas["Pista D"], "Poniendola en OFF")
        

        if(ONOFF_PISTAS == "true"): 

            response_body=apagar_pista(UID,NID,pistas["lightID"])
            print("Respuesta: ", response_body)

            if (pistas["Pista D"]) != "" :
                response_body=apagar_pista(UID,NID,pistas["lightID_Pista D"])
                print("Respuesta: ", response_body)
# return {
    #    "statusCode": 200
    #   }                   