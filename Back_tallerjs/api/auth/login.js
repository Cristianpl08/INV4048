const { connectToDatabase } = require('../../lib/mongodb');
const { withMiddleware, successResponse, errorResponse } = require('../../lib/middleware');
const User = require('../../models/User');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');

/**
 * POST /api/auth/login - Autenticar usuario
 */
async function handler(req, res) {
  // Solo permitir método POST
  if (req.method !== 'POST') {
    return errorResponse(res, `Método ${req.method} no permitido`, 405);
  }

  try {
    // Conectar a MongoDB
    await connectToDatabase();

    const { email, password } = req.body;

    console.log('🔐 Intento de login para:', email);

    // Validar datos requeridos
    if (!email || !password) {
      return errorResponse(res, 'Email y password son requeridos', 400);
    }

    // Buscar usuario por email
    const user = await User.findByEmail(email);
    
    if (!user) {
      console.log('❌ Usuario no encontrado:', email);
      return errorResponse(res, 'Credenciales inválidas', 401);
    }

    // Verificar password
    const isPasswordValid = await bcrypt.compare(password, user.password);
    
    if (!isPasswordValid) {
      console.log('❌ Password incorrecto para:', email);
      return errorResponse(res, 'Credenciales inválidas', 401);
    }

    // Generar JWT token
    const token = jwt.sign(
      { 
        userId: user._id,
        email: user.email,
        username: user.username
      },
      process.env.JWT_SECRET || 'your-secret-key',
      { expiresIn: '24h' }
    );

    console.log('✅ Login exitoso para:', email);

    // Retornar respuesta exitosa
    return successResponse(res, {
      user: user.toResponseDict(),
      token,
      message: 'Login exitoso'
    });

  } catch (error) {
    console.error('❌ Error en login:', error);
    throw error; // El middleware de errores lo manejará
  }
}

// Exportar la función con middleware aplicado
module.exports = withMiddleware(handler); 