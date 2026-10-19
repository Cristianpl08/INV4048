const mongoose = require('mongoose');

// Variable global para mantener la conexión
let cached = global.mongoose;

if (!cached) {
  cached = global.mongoose = { conn: null, promise: null };
}

/**
 * Conectar a MongoDB de forma optimizada para serverless
 * Reutiliza conexiones existentes para evitar crear múltiples conexiones
 */
async function connectToDatabase() {
  // Si ya hay una conexión activa, la retornamos
  if (cached.conn) {
    console.log('✅ Reutilizando conexión existente a MongoDB');
    return cached.conn;
  }

  // Si no hay una promesa de conexión en curso, creamos una nueva
  if (!cached.promise) {
    const opts = {
      bufferCommands: false, // Deshabilitar buffering para serverless
      maxPoolSize: 1, // Pool mínimo para serverless
      serverSelectionTimeoutMS: 5000, // Timeout de 5 segundos
      socketTimeoutMS: 45000, // Timeout de socket
    };

    // Obtener URI de MongoDB desde variables de entorno
    const MONGODB_URI = process.env.MONGODB_URI;
    
    if (!MONGODB_URI) {
      throw new Error('❌ MONGODB_URI no está definida en las variables de entorno');
    }

    console.log('🔌 Conectando a MongoDB...');
    cached.promise = mongoose.connect(MONGODB_URI, opts);
  }

  try {
    cached.conn = await cached.promise;
    console.log('✅ MongoDB conectado exitosamente');
  } catch (e) {
    cached.promise = null;
    console.error('❌ Error al conectar a MongoDB:', e);
    throw e;
  }

  return cached.conn;
}

/**
 * Cerrar conexión a MongoDB (útil para testing)
 */
async function closeConnection() {
  if (cached.conn) {
    await cached.conn.disconnect();
    cached.conn = null;
    cached.promise = null;
    console.log('✅ Conexión a MongoDB cerrada');
  }
}

module.exports = {
  connectToDatabase,
  closeConnection
}; 