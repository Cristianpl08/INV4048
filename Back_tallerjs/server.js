#!/usr/bin/env node
/**
 * Script de ejecución para el backend de Node.js
 * Video Segments Player Backend
 */

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const dotenv = require('dotenv');
const { connectDB } = require('./config/database');

// Cargar variables de entorno
dotenv.config();

// Crear aplicación Express
const app = express();

// Configuración
const PORT = process.env.PORT || 5000;
const NODE_ENV = process.env.NODE_ENV || 'development';

// Middleware de seguridad
app.use(helmet());

// Middleware de logging
app.use(morgan('combined'));

// Middleware de CORS
app.use(cors({
  origin: '*',
  credentials: false,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
}));

// Middleware para parsear JSON
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// Middleware de logging personalizado para todas las peticiones
app.use((req, res, next) => {
  const timestamp = new Date().toISOString();
  console.log(`📨 ${timestamp} - ${req.method} ${req.path}`);
  console.log('📋 Headers:', req.headers);
  
  if (req.body && Object.keys(req.body).length > 0) {
    console.log('📝 Body:', req.body);
  }
  
  next();
});

// Ruta de prueba
app.get('/', (req, res) => {
  console.log('🏠 Petición a la ruta raíz');
  res.json({
    message: 'Video Segments Player API',
    version: '1.0.0',
    status: 'running',
    timestamp: new Date().toISOString()
  });
});

// Importar rutas
const authRoutes = require('./routes/auth');
const projectRoutes = require('./routes/projects');
const segmentRoutes = require('./routes/segments');

// Registrar rutas
app.use('/api/auth', authRoutes);
app.use('/api/projects', projectRoutes);
app.use('/api/segments', segmentRoutes);

// Middleware de manejo de errores 404
app.use('*', (req, res) => {
  console.log('❌ Ruta no encontrada:', req.originalUrl);
  res.status(404).json({
    success: false,
    message: 'Ruta no encontrada',
    path: req.originalUrl
  });
});

// Middleware de manejo de errores global
app.use((error, req, res, next) => {
  console.log('💥 Error global:', error.message);
  console.log('📋 Stack trace:', error.stack);
  
  // Error de validación
  if (error.name === 'ValidationError') {
    console.log('❌ Error de validación:', error.message);
    return res.status(400).json({
      success: false,
      message: 'Error de validación',
      errors: [error.message]
    });
  }
  
  // Error genérico
  console.log('❌ Error genérico:', error.message);
  res.status(500).json({
    success: false,
    message: error.message || 'Error interno del servidor'
  });
});

// Función para iniciar el servidor
async function startServer() {
  try {
    // Conectar a MongoDB
    await connectDB();
    
    // Iniciar servidor
    app.listen(PORT, '0.0.0.0', () => {
      console.log("🚀 Iniciando Video Segments Player Backend (Node.js)");
      console.log(`📡 Puerto: ${PORT}`);
      console.log(`🌍 Ambiente: ${NODE_ENV}`);
      console.log(`🗄️ MongoDB: ${process.env.MONGODB_URI || 'mongodb://localhost:27017/video-segments-player'}`);
      console.log("=" * 50);
      console.log(`🚀 Servidor corriendo en puerto ${PORT}`);
      console.log(`🌍 Ambiente: ${NODE_ENV}`);
      console.log(`📡 API disponible en: http://localhost:${PORT}`);
      console.log(`🔐 Rutas de autenticación: http://localhost:${PORT}/api/auth`);
      console.log(`🎬 Rutas de proyectos: http://localhost:${PORT}/api/projects`);
      console.log(`📹 Rutas de segmentos: http://localhost:${PORT}/api/segments`);
    });
    
  } catch (error) {
    console.error('❌ Error al iniciar el servidor:', error);
    process.exit(1);
  }
}

// Manejar señales de terminación
process.on('SIGINT', () => {
  console.log('\n👋 Servidor detenido por el usuario');
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log('\n👋 Servidor detenido por el sistema');
  process.exit(0);
});

// Iniciar servidor
startServer(); 