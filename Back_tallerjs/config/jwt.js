const jwt = require('jsonwebtoken');
const User = require('../models/User');

// Configuración JWT
const JWT_SECRET_KEY = process.env.JWT_SECRET_KEY || 'your-secret-key-change-in-production';
const JWT_ALGORITHM = 'HS256';
const JWT_EXPIRATION_HOURS = 24; // Token válido por 24 horas

/**
 * Generar token JWT para un usuario
 */
function generateToken(userId, username, email) {
  const payload = {
    user_id: userId.toString(),
    username: username,
    email: email,
    exp: Math.floor(Date.now() / 1000) + (JWT_EXPIRATION_HOURS * 60 * 60),
    iat: Math.floor(Date.now() / 1000)
  };
  
  return jwt.sign(payload, JWT_SECRET_KEY, { algorithm: JWT_ALGORITHM });
}

/**
 * Verificar y decodificar token JWT
 */
function verifyToken(token) {
  try {
    const payload = jwt.verify(token, JWT_SECRET_KEY, { algorithms: [JWT_ALGORITHM] });
    return payload;
  } catch (error) {
    if (error.name === 'TokenExpiredError') {
      console.log('❌ Token expirado');
    } else if (error.name === 'JsonWebTokenError') {
      console.log('❌ Token inválido');
    } else {
      console.log('❌ Error al verificar token:', error.message);
    }
    return null;
  }
}

/**
 * Middleware para proteger rutas que requieren autenticación
 */
function tokenRequired(req, res, next) {
  let token = null;
  
  // Obtener token del header Authorization
  const authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith('Bearer ')) {
    token = authHeader.split(' ')[1];
  }
  
  if (!token) {
    return res.status(401).json({
      success: false,
      message: 'Token de autenticación requerido'
    });
  }
  
  try {
    // Verificar token
    const payload = verifyToken(token);
    if (!payload) {
      return res.status(401).json({
        success: false,
        message: 'Token inválido o expirado'
      });
    }
    
    // Obtener usuario de la base de datos
    User.findOne({ email: payload.email })
      .then(user => {
        if (!user) {
          return res.status(401).json({
            success: false,
            message: 'Usuario no encontrado'
          });
        }
        
        // Agregar usuario al request
        req.currentUser = user;
        next();
      })
      .catch(error => {
        console.error('❌ Error al buscar usuario:', error);
        return res.status(401).json({
          success: false,
          message: 'Error al verificar usuario'
        });
      });
    
  } catch (error) {
    console.error('❌ Error al verificar token:', error);
    return res.status(401).json({
      success: false,
      message: 'Error al verificar token'
    });
  }
}

/**
 * Obtener usuario actual desde el token
 */
async function getCurrentUser(req) {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return null;
  }
  
  const token = authHeader.split(' ')[1];
  const payload = verifyToken(token);
  
  if (!payload) {
    return null;
  }
  
  try {
    const user = await User.findOne({ email: payload.email });
    return user;
  } catch (error) {
    console.error('❌ Error al obtener usuario actual:', error);
    return null;
  }
}

module.exports = {
  generateToken,
  verifyToken,
  tokenRequired,
  getCurrentUser,
  JWT_SECRET_KEY,
  JWT_ALGORITHM,
  JWT_EXPIRATION_HOURS
}; 