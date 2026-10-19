import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiService } from '../services/api.js';
import { setupAuthInterceptor } from '../utils/authInterceptor.js';
import { API_CONFIG } from '../config.js';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Verificar estado de autenticación al cargar la aplicación
  const checkAuthStatus = async () => {
    const token = localStorage.getItem('authToken');
    
    if (token) {
      try {
        console.log('🔍 Verificando token JWT...');
        // Actualizar el token en la instancia del API service
        apiService.updateToken();
        const response = await apiService.verifyAuth();
        
        if (response.success) {
          console.log('✅ Token válido, usuario autenticado');
          setIsAuthenticated(true);
          setUser(response.data?.user || JSON.parse(localStorage.getItem('user')));
        } else {
          console.log('❌ Token inválido, limpiando datos');
          await handleLogout();
        }
      } catch (error) {
        console.error('❌ Error verificando autenticación:', error);
        await handleLogout();
      }
    } else {
      console.log('📝 No hay token almacenado');
    }
    
    setLoading(false);
  };

  // Login
  const login = async (credentials) => {
    try {
      setLoading(true);
      const response = await apiService.login(credentials);
      
      if (response.success || response.data?.token || response.token) {
        console.log('✅ Login exitoso');
        // Actualizar el token en la instancia del API service
        apiService.updateToken();
        setIsAuthenticated(true);
        setUser(response.data?.user || response.user);
        
        // Después del login exitoso, cargar automáticamente el proyecto
        try {
          console.log('🚀 Cargando proyecto automáticamente después del login...');
          const projectId = API_CONFIG.PROJECT_ID;
          const project = await apiService.getProject(projectId);
          console.log('✅ Proyecto cargado automáticamente:', project);
          
          // Guardar el proyecto en localStorage para que esté disponible inmediatamente
          localStorage.setItem('currentProject', JSON.stringify(project));
          
          // Cargar también los segmentos
          const segmentsData = await apiService.getSegments(projectId);
          const transformedSegments = (segmentsData.data?.segments || []).map((segment, index) => ({
            id: index + 1,
            start: segment.start_time * 1000,
            end: segment.end_time * 1000,
            duration: segment.duration || (segment.end_time - segment.start_time),
            description: segment.description || '',
            prosody: segment.prosody || '',
            prosody2: segment.prosody2 || '',
            views: segment.views || 0,
            likes: segment.likes || 0,
            _id: segment._id,
            projectid: segment.project_id
          }));
          
          localStorage.setItem('currentSegments', JSON.stringify(transformedSegments));
          console.log('✅ Segmentos cargados automáticamente:', transformedSegments.length);
          
        } catch (projectError) {
          console.error('⚠️ Error cargando proyecto automáticamente:', projectError);
          // No fallar el login si hay error cargando el proyecto
        }
        
        return { success: true };
      } else {
        console.log('❌ Login fallido');
        return { success: false, message: response.message || 'Error en el login' };
      }
    } catch (error) {
      console.error('❌ Error en login:', error);
      return { success: false, message: error.message };
    } finally {
      setLoading(false);
    }
  };

  // Logout
  const handleLogout = async () => {
    try {
      await apiService.logout();
    } catch (error) {
      console.error('Error en logout:', error);
    } finally {
      setIsAuthenticated(false);
      setUser(null);
    }
  };

  // Verificar autenticación al montar el componente
  useEffect(() => {
    checkAuthStatus();
    
    // Configurar interceptor de autenticación
    setupAuthInterceptor(handleLogout);
  }, []);

  const value = {
    isAuthenticated,
    user,
    loading,
    login,
    logout: handleLogout,
    checkAuthStatus
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe ser usado dentro de un AuthProvider');
  }
  return context;
}; 