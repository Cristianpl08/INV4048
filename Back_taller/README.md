# Video Segments Player Backend

Backend para la aplicación Video Segments Player desarrollado en Python con Flask.

## 🚀 Características

- **Framework**: Flask (Python)
- **Base de Datos**: MongoDB
- **Autenticación**: Sistema de login/registro
- **API RESTful**: Endpoints para proyectos y segmentos de video
- **CORS**: Configurado para permitir peticiones desde cualquier origen
- **Logging**: Sistema de logs detallado para debugging

## 📋 Requisitos

- Python 3.8 o superior
- MongoDB
- pip (gestor de paquetes de Python)

## 🛠️ Instalación

1. **Clonar el repositorio**:
   ```bash
   git clone <url-del-repositorio>
   cd Back_taller
   ```

2. **Crear entorno virtual** (recomendado):
   ```bash
   python -m venv venv
   
   # En Windows:
   venv\Scripts\activate
   
   # En macOS/Linux:
   source venv/bin/activate
   ```

3. **Instalar dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno**:
   Crear un archivo `.env` en la raíz del proyecto:
   ```env
   MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>/<database>
   MONGODB_DB=testad
   JWT_SECRET_KEY=your-secret-key-change-in-production
   PORT=5000
   FLASK_ENV=development
   FRONTEND_URL=http://localhost:5173
   LOG_LEVEL=info
   ```

5. **Ejecutar el servidor**:
   ```bash
   python run.py
   ```

## 📡 Endpoints de la API

### Autenticación
- `POST /api/auth/login` - Iniciar sesión
- `POST /api/auth/register` - Registrar usuario

### Proyectos
- `GET /api/projects/` - Obtener todos los proyectos
- `GET /api/projects/<id>` - Obtener proyecto por ID
- `POST /api/projects/` - Crear nuevo proyecto
- `PUT /api/projects/<id>` - Actualizar proyecto
- `DELETE /api/projects/<id>` - Eliminar proyecto

### Segmentos
- `GET /api/segments/` - Obtener todos los segmentos
- `GET /api/segments/<id>` - Obtener segmento por ID
- `GET /api/segments/project/<project_id>` - Obtener segmentos por proyecto
- `POST /api/segments/` - Crear nuevo segmento
- `PUT /api/segments/<id>` - Actualizar segmento
- `DELETE /api/segments/<id>` - Eliminar segmento
- `POST /api/segments/<id>/views` - Incrementar vistas
- `POST /api/segments/<id>/likes` - Incrementar likes

## 🗄️ Estructura de la Base de Datos

### Colección: users
```json
{
  "_id": "ObjectId",
  "username": "string",
  "email": "string",
  "password": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### Colección: projects
```json
{
  "_id": "ObjectId",
  "video": "string (URL)",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### Colección: segments
```json
{
  "_id": "ObjectId",
  "start_time": "number",
  "end_time": "number",
  "duration": "number",
  "views": "number",
  "likes": "number",
  "prosody": "string",
  "prosody2": "string",
  "description": "string",
  "descriptions_prosody": ["string"],
  "project_id": "ObjectId",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

## 📁 Estructura del Proyecto

```
Back_taller/
├── index.py              # Archivo principal de Flask
├── requirements.txt      # Dependencias de Python
├── run.py               # Script de ejecución principal
├── Procfile             # Configuración para Railway
├── runtime.txt          # Versión de Python
├── nixpacks.toml        # Configuración de build
├── env.example          # Ejemplo de variables de entorno
├── config/
│   ├── __init__.py
│   ├── database.py       # Configuración de MongoDB
│   └── jwt_config.py     # Configuración JWT
├── models/
│   ├── __init__.py
│   ├── user.py          # Modelo de Usuario
│   ├── project.py       # Modelo de Proyecto
│   └── segment.py       # Modelo de Segmento
├── controllers/
│   ├── __init__.py
│   ├── auth_controller.py    # Controlador de autenticación
│   ├── project_controller.py # Controlador de proyectos
│   └── segment_controller.py # Controlador de segmentos
└── routes/
    ├── __init__.py
    ├── auth.py           # Rutas de autenticación
    ├── projects.py       # Rutas de proyectos
    └── segments.py       # Rutas de segmentos
```

## 🔧 Desarrollo

### Ejecutar en modo desarrollo:
```bash
python run.py
```

### Ejecutar con debug activado:
```bash
export FLASK_ENV=development
python run.py
```

### Ejecutar con debug activado:
```bash
export FLASK_ENV=development
python app.py
```

## 🧪 Testing

Para probar los endpoints, puedes usar herramientas como:
- Postman
- curl
- Insomnia
- Thunder Client (VS Code extension)

### Ejemplo de petición de login:
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
```

## 📝 Logs

El sistema incluye logs detallados que muestran:
- Todas las peticiones HTTP
- Headers de las peticiones
- Cuerpo de las peticiones (si aplica)
- Errores y excepciones
- Operaciones de base de datos

## 🔒 Seguridad

**Nota**: Esta versión mantiene las contraseñas en texto plano. Para un entorno de producción, se recomienda implementar:

- Hashing de contraseñas (bcrypt)
- JWT para autenticación
- Validación de entrada más robusta
- Rate limiting
- HTTPS

## 🚀 Despliegue

### Railway
1. El proyecto ya incluye los archivos necesarios:
   - `Procfile`: `web: python run.py`
   - `runtime.txt`: `python-3.11.7`
   - `nixpacks.toml`: Configuración de build

2. **Configurar variables de entorno en Railway (OBLIGATORIO):**
   
   Ve a tu proyecto en Railway → Variables → Add Variable
   
   ```bash
   MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>/<database>
   JWT_SECRET_KEY=tu-clave-secreta-super-segura-aqui
   FLASK_ENV=production
   ```

3. **Verificar configuración:**
   Si tienes problemas, puedes ejecutar el script de verificación:
   ```bash
   python scripts/check_env.py
   ```

4. **Troubleshooting:**
   - Si ves "MongoDB local" en los logs, significa que `MONGODB_URI` no está configurada
   - Railway configurará `PORT` automáticamente
   - Asegúrate de que `FLASK_ENV=production`

### Heroku (Alternativo)
1. Crear `Procfile`:
   ```
   web: python run.py
   ```

2. Configurar variables de entorno en Heroku:
   ```bash
   heroku config:set MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>/<database>
   heroku config:set JWT_SECRET_KEY=your-secret-key-change-in-production
   heroku config:set FLASK_ENV=production
   ```

### Docker
Crear `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "run.py"]
```

## 📞 Soporte

Para reportar bugs o solicitar nuevas características, por favor crear un issue en el repositorio.

## 📄 Licencia

MIT License 