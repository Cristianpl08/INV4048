from flask_pymongo import PyMongo
from pymongo import MongoClient
import os
import sys

# Variable global para la conexión
mongo = None

def connect_db():
    """Conectar a MongoDB"""
    global mongo
    
    try:
        # Obtener URI de MongoDB desde variables de entorno
        mongodb_uri = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/video-segments-player')
        
        # Crear cliente de MongoDB
        client = MongoClient(mongodb_uri)
        
        # Verificar conexión
        client.admin.command('ping')
        
        print(f"✅ MongoDB conectado: {client.address[0]}:{client.address[1]}")
        
        # Retornar cliente para usar en la aplicación
        return client
        
    except Exception as error:
        print(f'❌ Error al conectar a MongoDB: {error}')
        sys.exit(1)

def get_db():
    """Obtener instancia de la base de datos"""
    client = connect_db()
    db_name = os.environ.get('MONGODB_DB', 'video-segments-player')
    return client[db_name] 