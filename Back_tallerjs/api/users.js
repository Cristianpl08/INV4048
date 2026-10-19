const { connectToDatabase } = require('./lib/mongodb');
const { withMiddleware, successResponse, errorResponse } = require('./lib/middleware');
const User = require('../models/User');

/**
 * Función serverless para manejar rutas de usuarios
 * GET /api/users - Obtener todos los usuarios
 * POST /api/users - Crear un nuevo usuario
 */
async function handler(req, res) {
  // Conectar a MongoDB
  await connectToDatabase();

  const { method } = req;

  switch (method) {
    case 'GET':
      return await getUsers(req, res);
    case 'POST':
      return await createUser(req, res);
    default:
      return errorResponse(res, `Método ${method} no permitido`, 405);
  }
}

/**
 * GET /api/users - Obtener todos los usuarios
 */
async function getUsers(req, res) {
  try {
    console.log('📋 Obteniendo todos los usuarios');
    
    const users = await User.find().select('-password'); // Excluir password
    
    console.log(`✅ ${users.length} usuarios encontrados`);
    
    return successResponse(res, users);
  } catch (error) {
    console.error('❌ Error al obtener usuarios:', error);
    throw error; // El middleware de errores lo manejará
  }
}

/**
 * POST /api/users - Crear un nuevo usuario
 */
async function createUser(req, res) {
  try {
    const { username, email, password } = req.body;
    
    console.log('📝 Creando nuevo usuario:', { username, email });
    
    // Validar datos requeridos
    if (!username || !email || !password) {
      return errorResponse(res, 'Username, email y password son requeridos', 400);
    }
    
    // Verificar si el usuario ya existe
    const existingUser = await User.findOne({
      $or: [{ email }, { username }]
    });
    
    if (existingUser) {
      return errorResponse(res, 'Usuario con ese email o username ya existe', 409);
    }
    
    // Crear nuevo usuario
    const newUser = new User({
      username,
      email,
      password // Nota: En producción deberías hashear la password
    });
    
    await newUser.save();
    
    console.log('✅ Usuario creado exitosamente:', newUser._id);
    
    // Retornar usuario sin password
    const userResponse = newUser.toResponseDict();
    
    return successResponse(res, userResponse, 201);
  } catch (error) {
    console.error('❌ Error al crear usuario:', error);
    throw error; // El middleware de errores lo manejará
  }
}

// Exportar la función con middleware aplicado
module.exports = withMiddleware(handler); 