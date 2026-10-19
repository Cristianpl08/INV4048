const { connectToDatabase } = require('../../lib/mongodb');
const { withMiddleware, successResponse, errorResponse } = require('../../lib/middleware');
const User = require('../../models/User');
const bcrypt = require('bcryptjs');

/**
 * POST /api/auth/register - Registrar nuevo usuario
 */
async function handler(req, res) {
  // Solo permitir método POST
  if (req.method !== 'POST') {
    return errorResponse(res, `Método ${req.method} no permitido`, 405);
  }

  try {
    // Conectar a MongoDB
    await connectToDatabase();

    const { username, email, password } = req.body;

    console.log('📝 Intento de registro para:', email);

    // Validar datos requeridos
    if (!username || !email || !password) {
      return errorResponse(res, 'Username, email y password son requeridos', 400);
    }

    // Verificar si el usuario ya existe
    const existingUser = await User.findOne({
      $or: [{ email }, { username }]
    });

    if (existingUser) {
      console.log('❌ Usuario ya existe:', email);
      return errorResponse(res, 'Usuario con ese email o username ya existe', 409);
    }

    // Hashear password
    const saltRounds = 10;
    const hashedPassword = await bcrypt.hash(password, saltRounds);

    // Crear nuevo usuario
    const newUser = new User({
      username,
      email,
      password: hashedPassword
    });

    await newUser.save();

    console.log('✅ Usuario registrado exitosamente:', newUser._id);

    // Retornar respuesta exitosa (sin password)
    return successResponse(res, {
      user: newUser.toResponseDict(),
      message: 'Usuario registrado exitosamente'
    }, 201);

  } catch (error) {
    console.error('❌ Error en registro:', error);
    throw error; // El middleware de errores lo manejará
  }
}

// Exportar la función con middleware aplicado
module.exports = withMiddleware(handler); 