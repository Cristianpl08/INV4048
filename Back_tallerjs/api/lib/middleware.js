/**
 * Middleware helpers para funciones serverless de Vercel
 */

// Configuración de CORS
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With',
  'Access-Control-Max-Age': '86400',
};

/**
 * Middleware para manejar CORS
 */
function corsMiddleware(handler) {
  return async (req, res) => {
    // Manejar preflight requests
    if (req.method === 'OPTIONS') {
      return res.status(200).json({});
    }

    // Agregar headers de CORS
    Object.keys(corsHeaders).forEach(key => {
      res.setHeader(key, corsHeaders[key]);
    });

    return handler(req, res);
  };
}

/**
 * Helper para respuestas exitosas
 */
function successResponse(res, data, statusCode = 200) {
  return res.status(statusCode).json({
    success: true,
    data,
    timestamp: new Date().toISOString()
  });
}

/**
 * Helper para respuestas de error
 */
function errorResponse(res, message, statusCode = 500, errors = null) {
  return res.status(statusCode).json({
    success: false,
    message,
    errors,
    timestamp: new Date().toISOString()
  });
}

/**
 * Middleware para manejo de errores
 */
function errorHandler(handler) {
  return async (req, res) => {
    try {
      return await handler(req, res);
    } catch (error) {
      console.error('💥 Error en función serverless:', error);
      
      // Error de validación de Mongoose
      if (error.name === 'ValidationError') {
        const errors = Object.values(error.errors).map(err => err.message);
        return errorResponse(res, 'Error de validación', 400, errors);
      }
      
      // Error de MongoDB
      if (error.name === 'MongoError' || error.name === 'MongoServerError') {
        if (error.code === 11000) {
          return errorResponse(res, 'Dato duplicado', 409);
        }
        return errorResponse(res, 'Error de base de datos', 500);
      }
      
      // Error genérico
      return errorResponse(res, error.message || 'Error interno del servidor', 500);
    }
  };
}

/**
 * Middleware completo que combina CORS y manejo de errores
 */
function withMiddleware(handler) {
  return corsMiddleware(errorHandler(handler));
}

module.exports = {
  corsMiddleware,
  successResponse,
  errorResponse,
  errorHandler,
  withMiddleware
}; 