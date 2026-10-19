const { connectToDatabase } = require('./lib/mongodb');
const { withMiddleware, successResponse, errorResponse } = require('./lib/middleware');
const Project = require('../models/Project');

/**
 * Función serverless para manejar rutas de proyectos
 * GET /api/projects - Obtener todos los proyectos
 * POST /api/projects - Crear un nuevo proyecto
 * GET /api/projects/[id] - Obtener un proyecto específico
 * PUT /api/projects/[id] - Actualizar un proyecto
 * DELETE /api/projects/[id] - Eliminar un proyecto
 */
async function handler(req, res) {
  // Conectar a MongoDB
  await connectToDatabase();

  const { method, query } = req;
  const { id } = query; // Vercel automáticamente parsea [id] en query.id

  switch (method) {
    case 'GET':
      if (id) {
        return await getProject(req, res, id);
      }
      return await getProjects(req, res);
    case 'POST':
      return await createProject(req, res);
    case 'PUT':
      if (!id) {
        return errorResponse(res, 'ID del proyecto requerido', 400);
      }
      return await updateProject(req, res, id);
    case 'DELETE':
      if (!id) {
        return errorResponse(res, 'ID del proyecto requerido', 400);
      }
      return await deleteProject(req, res, id);
    default:
      return errorResponse(res, `Método ${method} no permitido`, 405);
  }
}

/**
 * GET /api/projects - Obtener todos los proyectos
 */
async function getProjects(req, res) {
  try {
    console.log('📋 Obteniendo todos los proyectos');
    
    const projects = await Project.find().populate('user', 'username email');
    
    console.log(`✅ ${projects.length} proyectos encontrados`);
    
    return successResponse(res, projects);
  } catch (error) {
    console.error('❌ Error al obtener proyectos:', error);
    throw error;
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
 * POST /api/projects - Crear un nuevo proyecto
 */
async function createProject(req, res) {
  try {
    const { title, description, videoUrl, userId } = req.body;
    
    console.log('📝 Creando nuevo proyecto:', { title, userId });
    
    // Validar datos requeridos
    if (!title || !userId) {
      return errorResponse(res, 'Title y userId son requeridos', 400);
    }
    
    // Crear nuevo proyecto
    const newProject = new Project({
      title,
      description,
      videoUrl,
      user: userId
    });
    
    await newProject.save();
    
    console.log('✅ Proyecto creado exitosamente:', newProject._id);
    
    return successResponse(res, newProject, 201);
  } catch (error) {
    console.error('❌ Error al crear proyecto:', error);
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