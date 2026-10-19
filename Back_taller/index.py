from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import os
from dotenv import load_dotenv
from config.database import connect_db
from routes.auth import auth_bp
from routes.projects import projects_bp
from routes.segments import segments_bp

# Cargar variables de entorno
load_dotenv()

# Crear aplicación Flask
app = Flask(__name__)

# Configuración
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# Conectar a la base de datos (se conectará cuando se necesite)
# connect_db()

# Configurar CORS
CORS(app, origins='*', supports_credentials=False, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])

# Middleware de logging para todas las peticiones
@app.before_request
def log_request():
    print(f"📨 {datetime.now().isoformat()} - {request.method} {request.path}")
    print('📋 Headers:', dict(request.headers))
    # Solo intentar parsear JSON si la petición tiene contenido y es JSON
    if request.content_length and request.content_length > 0 and request.is_json:
        try:
            body = request.get_json()
            if body:
                print('📝 Body:', body)
        except Exception as e:
            print('⚠️ Error al parsear JSON del body:', str(e))

# Ruta de prueba
@app.route('/', methods=['GET'])
def home():
    print('🏠 Petición a la ruta raíz')
    return jsonify({
        'message': 'Video Segments Player API',
        'version': '1.0.0',
        'status': 'running',
        'timestamp': datetime.now().isoformat()
    })

# Registrar blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(projects_bp, url_prefix='/api/projects')
app.register_blueprint(segments_bp, url_prefix='/api/segments')

# Middleware de manejo de errores 404
@app.errorhandler(404)
def not_found(error):
    print('❌ Ruta no encontrada:', request.url)
    return jsonify({
        'success': False,
        'message': 'Ruta no encontrada',
        'path': request.url
    }), 404

# Middleware de manejo de errores global
@app.errorhandler(Exception)
def handle_exception(error):
    print('💥 Error global:', str(error))
    print('📋 Stack trace:', error.__traceback__)
    
    # Error de validación
    if hasattr(error, 'description'):
        print('❌ Error de validación:', error.description)
        return jsonify({
            'success': False,
            'message': 'Error de validación',
            'errors': [error.description]
        }), 400
    
    # Error genérico
    print('❌ Error genérico:', str(error))
    return jsonify({
        'success': False,
        'message': str(error) or 'Error interno del servidor'
    }), 500

if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 5000))
    print(f"🚀 Servidor corriendo en puerto {PORT}")
    print(f"🌍 Ambiente: {os.environ.get('FLASK_ENV', 'development')}")
    print(f"📡 API disponible en: http://localhost:{PORT}")
    print(f"🔐 Rutas de autenticación: http://localhost:{PORT}/api/auth")
    print(f"🎬 Rutas de proyectos: http://localhost:{PORT}/api/projects")
    print(f"📹 Rutas de segmentos: http://localhost:{PORT}/api/segments")
    app.run(host='0.0.0.0', port=PORT, debug=True) 