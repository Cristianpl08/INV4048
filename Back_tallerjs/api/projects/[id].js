const { connectToDatabase } = require('../../lib/mongodb');
const { withMiddleware, successResponse, errorResponse } = require('../../lib/middleware');
const Project = require('../../models/Project');

/**
 * Función serverless para manejar rutas de proyectos con ID dinámico
 * GET /api/projects/[id] - Obtener un proyecto específico
 * PUT /api/projects/[id] - Actualizar un proyecto
 * DELETE /api/projects/[id] - Eliminar un proyecto
 */
async function handler(req, res) {
  // Conectar a MongoDB
  await connectToDatabase();

  const { method, query } = req;
  const { id } = query; // Vercel automáticamente parsea [id] en query.id

  // Validar que se proporcione un ID
  if (!id) {
    return errorResponse(res, 'ID del proyecto requerido', 400);
  }

  switch (method) {
    case 'GET':
      return await getProject(req, res, id);
    case 'PUT':
      return await updateProject(req, res, id);
    case 'DELETE':
      return await deleteProject(req, res, id);
    default:
      return errorResponse(res, `Método ${method} no permitido`, 405);
  }
}

/**
 * GET /api/projects/[id] - Obtener un proyecto específico
 */
async function getProject(req, res, projectId) {
  try {
    console.log('📋 Obteniendo proyecto:', projectId);
    
    const project = await Project.findById(projectId).populate('user', 'username email');
    
    if (!project) {
      return errorResponse(res, 'Proyecto no encontrado', 404);
    }
    
    console.log('✅ Proyecto encontrado:', projectId);
    
    return successResponse(res, project);
  } catch (error) {
    console.error('❌ Error al obtener proyecto:', error);
    throw error;
  }
}

/**
 * PUT /api/projects/[id] - Actualizar un proyecto
 */
async function updateProject(req, res, projectId) {
  try {
    const { title, description, videoUrl } = req.body;
    
    console.log('📝 Actualizando proyecto:', projectId);
    
    const project = await Project.findById(projectId);
    
    if (!project) {
      return errorResponse(res, 'Proyecto no encontrado', 404);
    }
    
    // Actualizar campos
    if (title) project.title = title;
    if (description !== undefined) project.description = description;
    if (videoUrl) project.videoUrl = videoUrl;
    
    await project.save();
    
    console.log('✅ Proyecto actualizado exitosamente:', projectId);
    
    return successResponse(res, project);
  } catch (error) {
    console.error('❌ Error al actualizar proyecto:', error);
    throw error;
  }
}

/**
 * DELETE /api/projects/[id] - Eliminar un proyecto
 */
async function deleteProject(req, res, projectId) {
  try {
    console.log('🗑️ Eliminando proyecto:', projectId);
    
    const project = await Project.findByIdAndDelete(projectId);
    
    if (!project) {
      return errorResponse(res, 'Proyecto no encontrado', 404);
    }
    
    console.log('✅ Proyecto eliminado exitosamente:', projectId);
    
    return successResponse(res, { message: 'Proyecto eliminado exitosamente' });
  } catch (error) {
    console.error('❌ Error al eliminar proyecto:', error);
    throw error;
  }
}

// Exportar la función con middleware aplicado
module.exports = withMiddleware(handler); 