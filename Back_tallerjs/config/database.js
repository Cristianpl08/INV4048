const mongoose = require('mongoose');

/**
 * Conectar a MongoDB
 */
async function connectDB() {
  try {
    // Obtener URI de MongoDB desde variables de entorno
    const mongodbUri = process.env.MONGODB_URI || 'mongodb://localhost:27017/video-segments-player';
    
    // Configuración de conexión
    const options = {
      useNewUrlParser: true,
      useUnifiedTopology: true,
    };
    
    // Conectar a MongoDB
    await mongoose.connect(mongodbUri, options);
    
    // Verificar conexión
    const db = mongoose.connection;
    
    console.log(`✅ MongoDB conectado: ${db.host}:${db.port}`);
    console.log(`📊 Base de datos: ${db.name}`);
    
    // Manejar eventos de conexión
    db.on('error', (error) => {
      console.error('❌ Error de conexión a MongoDB:', error);
    });
    
    db.on('disconnected', () => {
      console.log('⚠️ MongoDB desconectado');
    });
    
    db.on('reconnected', () => {
      console.log('✅ MongoDB reconectado');
    });
    
    return db;
    
  } catch (error) {
    console.error('❌ Error al conectar a MongoDB:', error);
    process.exit(1);
  }
}

/**
 * Obtener instancia de la base de datos
 */
function getDB() {
  return mongoose.connection.db;
}

/**
 * Cerrar conexión a la base de datos
 */
async function closeDB() {
  try {
    await mongoose.connection.close();
    console.log('✅ Conexión a MongoDB cerrada');
  } catch (error) {
    console.error('❌ Error al cerrar conexión a MongoDB:', error);
  }
}

module.exports = {
  connectDB,
  getDB,
  closeDB
}; 