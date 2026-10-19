// Interceptor para manejar errores de autenticación automáticamente
export const setupAuthInterceptor = (logoutCallback) => {
  const originalFetch = window.fetch;
  
  window.fetch = async (...args) => {
    let [resource, config = {}] = args;
    config = { ...config, headers: { ...(config.headers || {}) } };

    // Añadir token si existe
    const token = localStorage.getItem('authToken');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await originalFetch(resource, config);
      
      // Si la respuesta es 401 (Unauthorized), limpiar la sesión
      if (response.status === 401) {
        console.log('🔒 Token expirado o inválido, limpiando sesión...');
        
        // Limpiar localStorage
        localStorage.removeItem('authToken');
        localStorage.removeItem('user');
        
        // Llamar callback de logout si existe
        if (logoutCallback) {
          logoutCallback();
        }
        
        // Redirigir a login si no estamos ya ahí
        if (!window.location.pathname.includes('login')) {
          window.location.reload();
        }
      }
      
      return response;
    } catch (error) {
      console.error('❌ Error en fetch interceptor:', error);
      throw error;
    }
  };
  
  console.log('✅ Interceptor de autenticación configurado');
};

// Función para restaurar fetch original
export const removeAuthInterceptor = () => {
  if (window.originalFetch) {
    window.fetch = window.originalFetch;
    console.log('🔄 Interceptor de autenticación removido');
  }
}; 