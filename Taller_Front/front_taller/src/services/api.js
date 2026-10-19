import { API_CONFIG, API_ENDPOINTS } from '../config.js';

class ApiService {
  constructor() {
    this.baseURL = API_CONFIG.BASE_URL;
    this.token = localStorage.getItem('authToken');
    console.log('🔧 ApiService initialized with:', {
      baseURL: this.baseURL,
      hasToken: !!this.token
    });
  }

  // Método para hacer peticiones HTTP
  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    
    console.log('🌐 API Request:', {
      url,
      method: options.method || 'GET',
      headers: options.headers,
      body: options.body
    });
    
    const defaultHeaders = {
      'Content-Type': 'application/json',
    };

    // Obtener el token fresco de localStorage para cada petición
    const currentToken = localStorage.getItem('authToken');
    
    // Agregar token de autenticación si existe
    if (currentToken) {
      defaultHeaders['Authorization'] = `Bearer ${currentToken}`;
      console.log('🔐 Token incluido en la petición:', currentToken.substring(0, 20) + '...');
    } else {
      console.log('⚠️ No se encontró token de autenticación');
    }

    const config = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, config);
      
      console.log('📡 API Response:', {
        status: response.status,
        statusText: response.statusText,
        url: response.url
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ API Error Response:', errorText);
        throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
      }
      
      const data = await response.json();
      console.log('✅ API Success Response:', data);
      return data;
    } catch (error) {
      console.error('❌ API request failed:', error);
      throw error;
    }
  }

  // Login con credenciales
  async login(credentials) {
    try {
      const response = await this.request(API_ENDPOINTS.LOGIN, {
        method: 'POST',
        body: JSON.stringify(credentials),
      });
      
      // Guardar el token y datos del usuario en localStorage
      if (response.data?.token) {
        this.token = response.data.token;
        localStorage.setItem('authToken', response.data.token);
        localStorage.setItem('user', JSON.stringify(response.data.user));
        console.log('✅ Token JWT guardado:', response.data.token);
        console.log('✅ Usuario guardado:', response.data.user);
      } else if (response.token) {
        // Compatibilidad con formato anterior
        this.token = response.token;
        localStorage.setItem('authToken', response.token);
        console.log('✅ Token JWT guardado (formato anterior):', response.token);
      }
      
      return response;
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  }

  // Verificar autenticación
  async verifyAuth() {
    try {
      const response = await this.request('/api/auth/verify');
      return response;
    } catch (error) {
      console.error('Auth verification failed:', error);
      throw error;
    }
  }

  // Obtener todos los proyectos
  async getAllProjects() {
    try {
      const response = await this.request(API_ENDPOINTS.PROJECTS);
      return response.data?.projects || response.projects || [];
    } catch (error) {
      console.error('Failed to get all projects:', error);
      throw error;
    }
  }

  // Obtener proyecto por ID
  async getProject(projectId = API_CONFIG.PROJECT_ID) {
    try {
      const response = await this.request(API_ENDPOINTS.PROJECT(projectId));
      return response.data?.project || response.project || response;
    } catch (error) {
      console.error('Failed to get project:', error);
      throw error;
    }
  }

  // Enviar edición de campo de segmento (descripción/prosody)
  async postDescriptionProsody({ segmentId, userId, fieldName, fieldValue, timestamp }) {
    const endpoint = `/api/segments/${segmentId}/descriptions_prosody`;
    const body = JSON.stringify({ segmentId, userId, fieldName, fieldValue, timestamp });
    return this.request(endpoint, {
      method: 'POST',
      body,
    });
  }

  // Verificar si el usuario está autenticado
  isAuthenticated() {
    return !!this.token;
  }

  // Actualizar el token en la instancia del servicio
  updateToken() {
    this.token = localStorage.getItem('authToken');
    console.log('🔄 Token actualizado en API service:', this.token ? 'presente' : 'no encontrado');
  }

  // Cerrar sesión
  async logout() {
    try {
      // Llamar endpoint de logout si existe
      await this.request('/api/auth/logout', {
        method: 'POST',
      });
    } catch (error) {
      console.log('Logout endpoint no disponible, continuando...');
    } finally {
      // Limpiar token y datos del usuario
      this.token = null;
      localStorage.removeItem('authToken');
      localStorage.removeItem('user');
      console.log('✅ Sesión cerrada, datos limpiados');
    }
  }
}

export const apiService = new ApiService(); 