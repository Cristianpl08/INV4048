const express = require('express');
const router = express.Router();
const segmentController = require('../controllers/segmentController');

// Rutas de segmentos
router.get('/', segmentController.getSegments);
router.get('/:segmentId', segmentController.getSegment);
router.get('/project/:projectId', segmentController.getSegmentsByProject);
router.post('/', segmentController.createSegment);
router.put('/:segmentId', segmentController.updateSegment);
router.delete('/:segmentId', segmentController.deleteSegment);
router.post('/:segmentId/views', segmentController.incrementViews);
router.post('/:segmentId/likes', segmentController.incrementLikes);
router.post('/:segmentId/descriptions_prosody', segmentController.updateDescriptionsProsody);

module.exports = router; 