const express = require('express');
const router = express.Router();
const projectController = require('../controllers/projectController');

// Rutas de proyectos
router.get('/', projectController.getProjects);
router.get('/:projectId', projectController.getProject);
router.post('/', projectController.createProject);
router.put('/:projectId', projectController.updateProject);
router.delete('/:projectId', projectController.deleteProject);

module.exports = router; 