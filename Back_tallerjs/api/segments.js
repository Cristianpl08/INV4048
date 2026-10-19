const { connectToDatabase } = require('./lib/mongodb');
const { withMiddleware, successResponse, errorResponse } = require('./lib/middleware');
const Segment = require('../models/Segment');

/**
 * Función serverless para manejar rutas de segmentos
 * GET /api/segments - Obtener todos los segmentos
 * POST /api/segments - Crear un nuevo segmento
 */
async function handler(req, res) {
  // Conectar a MongoDB
  await connectToDatabase();

  const { method } = req;

  switch (method) {
    case 'GET':
      return await getSegments(req, res);
    case 'POST':
      return await createSegment(req, res);
    default:
      return errorResponse(res, `Método ${method} no permitido`, 405);
  }
}

/**
 * GET /api/segments - Obtener todos los segmentos
 */
async function getSegments(req, res) {
  try {
    console.log('📋 Obteniendo todos los segmentos');
    
    const segments = await Segment.find()
      .populate('project', 'title')
      .populate('user', 'username email');
    
    console.log(`✅ ${segments.length} segmentos encontrados`);
    
    return successResponse(res, segments);
  } catch (error) {
    console.error('❌ Error al obtener segmentos:', error);
    throw error;
  }
}

/**
 * POST /api/segments - Crear un nuevo segmento
 */
async function createSegment(req, res) {
  try {
    const { title, startTime, endTime, description, projectId, userId } = req.body;
    
    console.log('📝 Creando nuevo segmento:', { title, projectId });
    
    // Validar datos requeridos
    if (!title || !startTime || !endTime || !projectId || !userId) {
      return errorResponse(res, 'Title, startTime, endTime, projectId y userId son requeridos', 400);
    }
    
    // Validar que startTime sea menor que endTime
    if (startTime >= endTime) {
      return errorResponse(res, 'startTime debe ser menor que endTime', 400);
    }
    
    // Crear nuevo segmento
    const newSegment = new Segment({
      title,
      startTime,
      endTime,
      description,
      project: projectId,
      user: userId
    });
    
    await newSegment.save();
    
    console.log('✅ Segmento creado exitosamente:', newSegment._id);
    
    return successResponse(res, newSegment, 201);
  } catch (error) {
    console.error('❌ Error al crear segmento:', error);
    throw error;
  }
}

// Exportar la función con middleware aplicado
module.exports = withMiddleware(handler); 