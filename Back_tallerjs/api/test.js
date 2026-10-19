const { withMiddleware, successResponse } = require('./lib/middleware');

/**
 * GET /api/test - Función de prueba para verificar el despliegue
 */
async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Método no permitido' });
  }

  return successResponse(res, {
    message: '🎉 ¡Backend serverless funcionando correctamente!',
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV || 'development',
    version: '1.0.0',
    features: [
      '✅ Conexión a MongoDB optimizada',
      '✅ Middleware de CORS',
      '✅ Manejo de errores centralizado',
      '✅ Respuestas estandarizadas',
      '✅ Funciones serverless de Vercel'
    ],
    endpoints: {
      auth: {
        login: 'POST /api/auth/login',
        register: 'POST /api/auth/register'
      },
      users: {
        list: 'GET /api/users',
        create: 'POST /api/users'
      },
      projects: {
        list: 'GET /api/projects',
        create: 'POST /api/projects',
        get: 'GET /api/projects/[id]',
        update: 'PUT /api/projects/[id]',
        delete: 'DELETE /api/projects/[id]'
      },
      segments: {
        list: 'GET /api/segments',
        create: 'POST /api/segments'
      }
    }
  });
}

// Exportar la función con middleware aplicado
module.exports = withMiddleware(handler); 