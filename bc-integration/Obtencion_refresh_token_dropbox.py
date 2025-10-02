import pycurl
import io
import base64
import urllib.parse

# === CONFIGURA ESTOS DATOS PRIMERO ===
APP_KEY = 'gcwcrtb1njdp6zm'
APP_SECRET = '7r5f0uvnmfbhsz1'
AUTH_CODE = '-nYQUlaPCKAAAAAAAAAJgQgzVfVJN61vWpRW8BQluh8'
REDIRECT_URI = 'http://localhost'

# === NO CAMBIES ESTO ===
# Prepara encabezado Authorization
user_pass = f"{APP_KEY}:{APP_SECRET}"
b64_auth = base64.b64encode(user_pass.encode()).decode()

# Prepara los datos del POST
postfields = {
    'code': AUTH_CODE,
    'grant_type': 'authorization_code',
    'redirect_uri': REDIRECT_URI
}
post_data = urllib.parse.urlencode(postfields)

# Buffer para capturar la respuesta
response_buffer = io.BytesIO()

# Configura pycurl
c = pycurl.Curl()
c.setopt(c.URL, 'https://api.dropbox.com/oauth2/token')
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
    print("✅ Respuesta de Dropbox:")
    print(response)
except pycurl.error as e:
    print("❌ Error en pycurl:", e)
