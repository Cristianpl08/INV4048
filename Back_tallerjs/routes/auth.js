const express = require('express');
const router = express.Router();
const authController = require('../controllers/authController');

// Rutas de autenticación
router.post('/login', authController.login);
router.post('/register', authController.register);
router.get('/verify', authController.verifyAuth);
router.post('/logout', authController.logout);

module.exports = router; 