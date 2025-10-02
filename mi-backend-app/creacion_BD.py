

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app_init import db, application
from config import DATABASE, PASSWORD











#Configuración de la base de datos
#app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://aregalado:%40Planet01@localhost/backend'




def crear_base_si_no_existe():
    
    



    
   
    try:
        print (PASSWORD)
        #engine = create_engine(URL_SIN_DB)
        engine = create_engine(application.config['SQLALCHEMY_DATABASE_URI'], pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {DATABASE}"))
            print(f"✅ Base de datos '{DATABASE}' verificada o creada.")


         # Crear las tablas si no existen
        with application.app_context():
            db.create_all()
            print("✅ Tablas creadas o verificadas exitosamente.")
    except OperationalError as e:
        print(f"❌ Error al crear la base de datos: {e}")






   







 
 
