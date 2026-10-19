const User = require('../models/User');
const { generateToken, getCurrentUser } = require('../config/jwt');

/**
 * Iniciar sesión de usuario
 */
async function login(req, res) {
  try {
    const { email, password } = req.body;
    
    console.log('🔐 Intento de login iniciado');
    console.log('📝 Datos recibidos:', { email, password: password ? '***' : 'undefined' });

    // Validar datos requeridos
    if (!email || !password) {
      return res.status(400).json({
        success: false,
        message: 'Email y contraseña son requeridos'
      });
    }

    console.log('🗄️ Buscando usuario con email:', email);
    
    // Buscar usuario por email
    const user = await User.findByEmail(email);
    
    if (!user) {
      console.log('❌ Usuario no encontrado:', email);
      return res.status(401).json({
        success: false,
        message: 'Credenciales inválidas'
      });
    }

    console.log('✅ Usuario encontrado:', {
      _id: user._id.toString(),
      username: user.username,
      email: user.email,
      passwordStored: user.password ? '***' : 'undefined'
    });

    // Verificar contraseña sin encriptar (como en el original)
    console.log('🔐 Verificando contraseña...');
    console.log('📝 Contraseña recibida:', password);
    console.log('📝 Contraseña almacenada:', user.password);
    
    if (user.password !== password) {
      console.log('❌ Contraseña incorrecta');
      console.log('🔍 Comparación:', {
        received: password,
        stored: user.password,
        match: user.password === password
      });
      return res.status(401).json({
        success: false,
        message: 'Credenciales inválidas'
      });
    }

    console.log('✅ Contraseña correcta - Login exitoso');

    // Generar token JWT
    const token = generateToken(user._id, user.username, user.email);
    console.log('🎫 Token JWT generado');

    // Respuesta exitosa con token
    const response = {
      success: true,
      message: 'Login exitoso',
      data: {
        user: user.toResponseDict(),
        token: token
      }
    };

    console.log('📤 Enviando respuesta exitosa con token');
    res.json(response);

  } catch (error) {
    console.log('💥 Error en login:', error.message);
    res.status(500).json({
      success: false,
      message: 'Error al iniciar sesión'
    });
  }
}

/**
 * Verificar si el usuario está autenticado
 */
async function verifyAuth(req, res) {
  try {
    const user = await getCurrentUser(req);
    
    if (!user) {
      return res.status(401).json({
        success: false,
        message: 'Usuario no autenticado'
      });
    }
    
    res.json({
      success: true,
      message: 'Usuario autenticado',
      data: {
        user: user.toResponseDict()
      }
    });
    
  } catch (error) {
    console.log('💥 Error en verificación de autenticación:', error.message);
    res.status(500).json({
      success: false,
      message: 'Error al verificar autenticación'
    });
  }
}

/**
 * Cerrar sesión (el frontend debe eliminar el token)
 */
function logout(req, res) {
  res.json({
    success: true,
    message: 'Sesión cerrada exitosamente'
  });
}

/**
 * Registrar un nuevo usuario
 */
async function register(req, res) {
  try {
    const { username, email, password } = req.body;
    
    console.log('📝 Intento de registro iniciado');
    console.log('📋 Datos recibidos:', {
      username, 
      email, 
      password: password ? '***' : 'undefined'
    });

    // Validar datos requeridos
    if (!username || !email || !password) {
      return res.status(400).json({
        success: false,
        message: 'Username, email y contraseña son requeridos'
      });
    }

    // Verificar si el usuario ya existe
    console.log('🔍 Verificando si username ya existe:', username);
    const existingUser = await User.findByUsername(username);
    if (existingUser) {
      console.log('❌ Usuario ya existe:', username);
      return res.status(400).json({
        success: false,
        message: 'El username ya está registrado'
      });
    }

    // Verificar si el email ya existe
    console.log('🔍 Verificando si email ya existe:', email);
    const existingEmail = await User.findByEmail(email);
    if (existingEmail) {
      console.log('❌ Email ya existe:', email);
      return res.status(400).json({
        success: false,
        message: 'El email ya está registrado'
      });
    }

    console.log('✅ Usuario y email disponibles, creando nuevo usuario');

    // Crear nuevo usuario
    const user = new User({
      username: username,
      email: email,
      password: password
    });

    console.log('💾 Guardando usuario en la base de datos...');
    await user.saveUser();
    console.log('✅ Usuario guardado exitosamente:', {
      _id: user._id.toString(),
      username: user.username,
      email: user.email
    });

    // Respuesta exitosa
    const response = {
      success: true,
      message: 'Usuario registrado exitosamente',
      data: {
        user: user.toResponseDict()
      }
    };

    console.log('📤 Enviando respuesta exitosa:', response);
    res.status(201).json(response);

  } catch (error) {
    console.log('💥 Error en registro:', error.message);
    res.status(500).json({
      success: false,
      message: 'Error al registrar usuario'
    });
  }
}

module.exports = {
  login,
  register,
  verifyAuth,
  logout
}; 