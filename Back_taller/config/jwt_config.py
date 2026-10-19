import jwt
import os
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app
from models.user import User
from config.database import get_db

# Configuración JWT
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24  # Token válido por 24 horas

def generate_token(user_id, username, email):
    """Generar token JWT para un usuario"""
    payload = {
        'user_id': str(user_id),
        'username': username,
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token

def verify_token(token):
    """Verificar y decodificar token JWT"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def token_required(f):
    """Decorador para proteger rutas que requieren autenticación"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Obtener token del header Authorization
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({
                'success': False,
                'message': 'Token de autenticación requerido'
            }), 401
        
        try:
            # Verificar token
            payload = verify_token(token)
            if not payload:
                return jsonify({
                    'success': False,
                    'message': 'Token inválido o expirado'
                }), 401
            
            # Obtener usuario de la base de datos
            db = get_db()
            user = User.find_by_email(db, payload['email'])
            
            if not user:
                return jsonify({
                    'success': False,
                    'message': 'Usuario no encontrado'
                }), 401
            
            # Agregar usuario al request
            request.current_user = user
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': 'Error al verificar token'
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated

def get_current_user():
    """Obtener usuario actual desde el token"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    payload = verify_token(token)
    
    if not payload:
        return None
    
    db = get_db()
    user = User.find_by_email(db, payload['email'])
    return user 