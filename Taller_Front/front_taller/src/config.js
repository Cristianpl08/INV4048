// Configuración de la API
export const API_CONFIG = {
  BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000',
  PROJECT_ID: import.meta.env.VITE_PROJECT_ID || '6882f61f358cfb33745d32ca'
};

// Endpoints de la API
export const API_ENDPOINTS = {
  LOGIN: '/api/auth/login',
  PROJECT: (id) => `/api/projects/${id}`,
  PROJECTS: '/api/projects',
  DESCRIPTION_PROSODY: (segmentId) => `/api/segments/${segmentId}/descriptions_prosody`
}; 