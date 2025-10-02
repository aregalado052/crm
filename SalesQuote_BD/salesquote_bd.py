import json
import base64
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List
#from flask import Flask,request,  jsonify
import boto3
import pymysql
from flask import Flask,request,  jsonify
from pymysql import err as pym_err
from config import (CLIENT_SECRET)


BD= "PRODUCCION"  # o "PRUEBAS"

app = Flask(__name__)







#@app.route("/salesquote_bd", methods=["POST"])
def salesquote_bd():
    """Endpoint para crear un contacto y una oferta en Business Central."""

   
    

    #try:
    #    data = json.loads(event.get("body", "{}"))  # ✅ Correcto en Lambda
    #except Exception as e:
    #    return {
    #        "statusCode": 400,
    #        "body": json.dumps({"error": "JSON inválido", "detalle": str(e)})

    #    }

    try :
        data = request.get_json()

        amount = _D(data.get("amount"))
        cantidad_total = _D(data.get("amountInclVAT"))
        add_pct = _D(data.get("additionalDiscountPct"))
        total_pct = _D(data.get("totalDiscountPct"))
        documentNo = data.get("documentNo")
        sellToCustomerNo = data.get("sellToCustomerNo")  
        sellToName = data.get("sellToName")
        sellToEmail = data.get("sellToEmail")
        fecha = data.get("postingDate")
        
        CountryCode = data.get("countryCode")
        pais = data.get("countryName")  
        languageCode = data.get("languageCode")


        lines = data.get("lines") or []
        if not isinstance(lines, list):
            return _response(400, {"error": "'lines' must be an array"})


        if languageCode == "ENU":
            idioma = "Ingles"
        else:
            idioma = "Español"

        

       

        print(f"""Datos recibidos: {fecha},{CountryCode}, {pais}, {languageCode}, {amount}, {cantidad_total}, {add_pct}, {total_pct},{documentNo}, {sellToCustomerNo}, {sellToName}, {sellToEmail}""")

        normalized_lines: List[Dict[str, Any]] = []
        for ln in lines:
            try:
                line_no = ln.get("lineNo")
                qty = _D(ln.get("quantity", 0))
                unit_price = _D(ln.get("unitPrice", 0))
                line_amount = _D(ln.get("lineAmount", 0))
            except InvalidOperation:
                return _response(400, {"error": f"Invalid numeric value in line {ln!r}"})

            normalized = {
                "lineNo": line_no,
                "type": ln.get("type"),
                "no": ln.get("no"),
                "description": ln.get("description"),
                "quantity": qty,
                "unitPrice": unit_price,
                "lineAmount": line_amount,
            }
            normalized_lines.append(normalized)

        perimetrales, laterales = calcular_perimetrales_laterales(normalized_lines)
       

        print(f"""Datos recibidos: {normalized_lines}""")
        print(f"""Perimetrales: {perimetrales}, Laterales: {laterales}""")

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
            origen = "BC"
            probabilidad_exito = 50
            estado = "Sin calificar"

            params = (
                fecha,
                sellToName, sellToEmail, origen, documentNo,
                idioma, pais,
                add_pct, total_pct, cantidad_total,
                probabilidad_exito, perimetrales, laterales,
                estado
            )

            sql = """
                INSERT INTO lead_forms (
                    fecha_actual,
                    name, email, origen, quote_number,
                    idioma, pais,
                    descuento_adicional, descuento_total, cantidad_total,
                    probabilidad_exito, pistas_perimetrales, pistas_laterales,
                    estado, 
                    created_at, updated_at
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    
                    NOW(), NOW()
                )
                """

            with connection.cursor() as cur:
                cur.execute(sql, params)
            
            connection.commit()
            connection.close()
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "OK"})
            }
        except pym_err.IntegrityError as e:
            connection.rollback()
            connection.close()
            # 1062 = Duplicate entry
            if e.args and e.args[0] == 1062:
                
                return {
                "statusCode": 409,
                "body": json.dumps({"message":"Duplicado (quote_number ya existe)", "detail": str(e)})
                }
            
            return {
                "statusCode": 400,
                "body": json.dumps({"message":"Error de integridad", "detail": str(e)})
            }
           
        except pym_err.MySQLError as e:
            connection.rollback()
            connection.close()
            return {
                "statusCode": 500,
                "body": json.dumps({"message":"Error de base de datos", "detail": str(e)})
            }
           
           
        except Exception as e:
            connection.rollback()
            connection.close()
            return {
                "statusCode": 500,
                "body": json.dumps({"message":"Error inesperado", "detail": str(e)})
            }
           
        
            


    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


   
    
def get_db_credentials(secret_name):
    client = boto3.client("secretsmanager", region_name="eu-north-1")  # ✅ correcto
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])




    
def calcular_perimetrales_laterales(normalized_lines):


    creds = get_db_credentials("secretoBC/Mysql")

    dbname = "bc_pruebas" if (BD == "PRUEBAS") else creds["dbname"]

    print ("BD", BD)  
    
    print(f"Credenciales obtenidas: {creds}")
    print(f"Conectando a la base de datos con host: {creds['host']}, usuario: {creds['username']}, base de datos: {dbname}")
    
    # Reúne códigos únicos
    codes = {str(ln.get("no", "")).strip() for ln in normalized_lines if str(ln.get("no", "")).strip()}
    code_to_tipo = {}

    if codes:
        

        connection = pymysql.connect(
            host=creds['host'],
            user=creds['username'],
            password=creds['password'],
            database= dbname,
            port=int(creds.get('port', 3306))
        )
        try:
            placeholders = ",".join(["%s"] * len(codes))
            sql = f"SELECT codigo, COALESCE(tipo,'Otros') FROM productos WHERE codigo IN ({placeholders})"
            with connection.cursor() as cur:
                cur.execute(sql, list(codes))
                for codigo, tipo in cur.fetchall():
                    code_to_tipo[str(codigo).strip()] = (tipo or "Otros")
            
           
        finally:
            connection.close()

    perimetrales = Decimal("0")
    laterales    = Decimal("0")

    for ln in normalized_lines:
        code = str(ln.get("no", "")).strip()
        # Acepta 'quantity' o el posible typo 'quatity'
        qty_raw = ln.get("quantity", ln.get("quatity", 0))
        qty = Decimal(str(qty_raw or 0))

        tipo = (code_to_tipo.get(code, "Otros") or "").lower()
        if tipo.startswith("peri"):
            perimetrales += qty
        elif tipo.startswith("lat"):
            laterales += qty

    perimetrales_int = int(perimetrales.to_integral_value(rounding=ROUND_HALF_UP))
    laterales_int    = int(laterales.to_integral_value(rounding=ROUND_HALF_UP))
    return perimetrales_int, laterales_int

   




def lambda_handler(event, context):
    """
    Handler para API Gateway (REST o HTTP API).
    Espera un JSON con las claves:
      - documentType, documentNo, sellToCustomerNo, sellToName,
        currencyCode, postingDate, amount, amountInclVAT,
        additionalDiscountPct, totalDiscountPct, lines[...]
    Cada línea: lineNo, type, no, description, quantity, unitPrice, lineAmount

    Responde con 200 y un resumen, o 400 si faltan campos/datos inválidos.
    """

    try:
        data = _read_json_body(event)
    
        amount = _D(data.get("amount"))
        cantidad_total = _D(data.get("amountInclVAT"))
        add_pct = _D(data.get("additionalDiscountPct"))
        total_pct = _D(data.get("totalDiscountPct"))
        documentNo = data.get("documentNo")
        sellToCustomerNo = data.get("sellToCustomerNo")  
        sellToName = data.get("sellToName")
        sellToEmail = data.get("sellToEmail")
        fecha = data.get("postingDate")
        
        CountryCode = data.get("countryCode")
        pais = data.get("countryName")  
        languageCode = data.get("languageCode")

        lines = data.get("lines") or []
        if not isinstance(lines, list):
            return _response(400, {"error": "'lines' must be an array"})


        if languageCode == "ENU":
            idioma = "Ingles"
        else:
            idioma = "Español"

        print(f"""Datos recibidos: {fecha},{CountryCode}, {pais}, {languageCode}, {amount}, {cantidad_total}, {add_pct}, {total_pct},{documentNo}, {sellToCustomerNo}, {sellToName}, {sellToEmail}""")
        normalized_lines: List[Dict[str, Any]] = []
        for ln in lines:
            try:
                line_no = ln.get("lineNo")
                qty = _D(ln.get("quantity", 0))
                unit_price = _D(ln.get("unitPrice", 0))
                line_amount = _D(ln.get("lineAmount", 0))
            except InvalidOperation:
                return _response(400, {"error": f"Invalid numeric value in line {ln!r}"})

            normalized = {
                "lineNo": line_no,
                "type": ln.get("type"),
                "no": ln.get("no"),
                "description": ln.get("description"),
                "quantity": qty,
                "unitPrice": unit_price,
                "lineAmount": line_amount,
            }
            normalized_lines.append(normalized)

        perimetrales, laterales = calcular_perimetrales_laterales(normalized_lines)


        print(f"""Datos recibidos: {normalized_lines}""")
        print(f"""Perimetrales: {perimetrales}, Laterales: {laterales}""")

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
            origen = "BC"
            probabilidad_exito = 50
            estado = "Sin calificar"

            params = (
                fecha,
                sellToName, sellToEmail, origen, documentNo,
                idioma, pais,
                add_pct, total_pct, cantidad_total,
                probabilidad_exito, perimetrales, laterales,
                estado
            )

            sql = """
                INSERT INTO lead_forms (
                    fecha_actual,
                    name, email, origen, quote_number,
                    idioma, pais,
                    descuento_adicional, descuento_total, cantidad_total,
                    probabilidad_exito, pistas_perimetrales, pistas_laterales,
                    estado, 
                    created_at, updated_at
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    
                    NOW(), NOW()
                )
                """

            with connection.cursor() as cur:
                cur.execute(sql, params)
            
            connection.commit()
            connection.close()
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "OK"})
            }
        except pym_err.IntegrityError as e:
            connection.rollback()
            connection.close()
            # 1062 = Duplicate entry
            if e.args and e.args[0] == 1062:
                
                return {
                "statusCode": 409,
                "body": json.dumps({"message":"Duplicado (quote_number ya existe)", "detail": str(e)})
                }
            
            return {
                "statusCode": 400,
                "body": json.dumps({"message":"Error de integridad", "detail": str(e)})
            }
        
        except pym_err.MySQLError as e:
            connection.rollback()
            connection.close()
            return {
                "statusCode": 500,
                "body": json.dumps({"message":"Error de base de datos", "detail": str(e)})
            }
        
        
        except Exception as e:
            connection.rollback()
            connection.close()
            return {
                "statusCode": 500,
                "body": json.dumps({"message":"Error inesperado", "detail": str(e)})
            }
        
            
                


    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }






# -------- Utilidades -------- #

def _read_json_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """Lee y decodifica event['body'] (posible base64) y devuelve JSON (parse_float=Decimal)."""
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    return json.loads(body, parse_float=Decimal)


def _D(value: Any) -> Decimal:
    """Convierte a Decimal de forma segura (acepta int/float/str/Decimal)."""
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def compound_discount(volume_pct: Decimal, additional_pct: Decimal) -> Decimal:
    """Descuento compuesto: 1 - (1 - v/100)*(1 - a/100) -> porcentaje (0..100)."""
    v = _clamp_pct(volume_pct)
    a = _clamp_pct(additional_pct)
    res = (Decimal("1") - (Decimal("1") - v / 100) * (Decimal("1") - a / 100)) * 100
    return res


def _clamp_pct(p: Decimal) -> Decimal:
    if p < 0:
        return Decimal("0")
    if p > 100:
        return Decimal("100")
    return p


def _jsonify_decimals(obj: Any) -> Any:
    """Convierte Decimals a str en estructuras dict/list para json.dumps."""
    if isinstance(obj, dict):
        return {k: _jsonify_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonify_decimals(x) for x in obj]
    if isinstance(obj, Decimal):
        return str(obj)
    return obj


def _response(status_code: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Respuesta estándar para API Gateway (con CORS)."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",              # ajusta si necesitas restringir
            "Access-Control-Allow-Headers": "Content-Type",  # idem
            "Access-Control-Allow-Methods": "POST,OPTIONS",
        },
        "body": json.dumps(data),
        "isBase64Encoded": False,
    }



if __name__ == "__main__":
    app.run(debug=True, port=5000)

