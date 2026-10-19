import { useState, useEffect } from 'react';
import { apiService } from '../services/api.js';

// Hook para obtener todos los proyectos
export const useProjects = () => {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        setLoading(true);
        setError(null);
        console.log('📡 Cargando lista de proyectos...');
        
        const projectsData = await apiService.getAllProjects();
        console.log('✅ Proyectos cargados:', projectsData.length);
        setProjects(projectsData);
      } catch (err) {
        console.error('❌ Error al cargar proyectos:', err);
        setError('Error al cargar los proyectos. Verifica tu conexión.');
      } finally {
        setLoading(false);
      }
    };

    fetchProjects();
  }, []);

  // Función para actualizar un proyecto localmente
  const updateProjectLocally = (projectId, updates) => {
    setProjects(prevProjects => 
      prevProjects.map(project => 
        project._id === projectId 
          ? { ...project, ...updates }
          : project
      )
    );
  };

  return { projects, loading, error, updateProjectLocally };
};

// Hook para obtener un proyecto específico
export const useProject = (projectId) => {
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchProject = async () => {
      if (!projectId) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);
        console.log('📡 Cargando proyecto:', projectId);
        
        const projectData = await apiService.getProject(projectId);
        console.log('✅ Proyecto cargado:', projectData);
        setProject(projectData);
      } catch (err) {
        console.error('❌ Error al cargar proyecto:', err);
        setError('Error al cargar el proyecto. Verifica tu conexión.');
      } finally {
        setLoading(false);
      }
    };

    fetchProject();
  }, [projectId]);

  // Función para actualizar el proyecto localmente
  const updateProjectLocally = (updates) => {
    setProject(prevProject => 
      prevProject ? { ...prevProject, ...updates } : null
    );
  };

  // Función para actualizar un segmento específico localmente
  const updateSegmentLocally = (segmentId, updates) => {
    setProject(prevProject => {
      if (!prevProject || !prevProject.segments) return prevProject;
      
      return {
        ...prevProject,
        segments: prevProject.segments.map(segment => 
          segment._id === segmentId 
            ? { ...segment, ...updates }
            : segment
        )
      };
    });
  };

  // Función para actualizar las descripciones/prosody de un segmento localmente
  const updateSegmentDescriptionProsody = (segmentId, userId, fieldName, fieldValue) => {
    setProject(prevProject => {
      if (!prevProject || !prevProject.segments) return prevProject;
      
      return {
        ...prevProject,
        segments: prevProject.segments.map(segment => {
          if (segment._id !== segmentId) return segment;
          
          // Crear o actualizar descriptions_prosody
          const existingDescriptionsProsody = segment.descriptions_prosody || [];
          const existingUserIndex = existingDescriptionsProsody.findIndex(
            entry => entry.user_id === userId
          );
          
          let updatedDescriptionsProsody;
          if (existingUserIndex >= 0) {
            // Actualizar entrada existente del usuario
            updatedDescriptionsProsody = [...existingDescriptionsProsody];
            updatedDescriptionsProsody[existingUserIndex] = {
              ...updatedDescriptionsProsody[existingUserIndex],
              [fieldName]: fieldValue,
              timestamp: new Date().toISOString()
            };
          } else {
            // Crear nueva entrada para el usuario
            updatedDescriptionsProsody = [
              ...existingDescriptionsProsody,
              {
                user_id: userId,
                [fieldName]: fieldValue,
                timestamp: new Date().toISOString()
              }
            ];
          }
          
          return {
            ...segment,
            descriptions_prosody: updatedDescriptionsProsody
          };
        })
      };
    });
  };

  return { 
    project, 
    loading, 
    error, 
    updateProjectLocally, 
    updateSegmentLocally,
    updateSegmentDescriptionProsody
  };
}; 