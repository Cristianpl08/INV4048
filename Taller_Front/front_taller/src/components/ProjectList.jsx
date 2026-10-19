import React from 'react';
import { useProjects } from '../hooks/useProjects.js';

function ProjectList({ onProjectSelect }) {
  const { projects, loading, error } = useProjects();

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '50vh',
        flexDirection: 'column',
        gap: '1rem'
      }}>
        <div style={{
          width: '40px',
          height: '40px',
          border: '4px solid #f3f3f3',
          borderTop: '4px solid #ea580c',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite'
        }}></div>
        <p style={{ color: '#666', fontSize: '1.1rem' }}>Cargando proyectos...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '50vh',
        flexDirection: 'column',
        gap: '1rem',
        padding: '2rem'
      }}>
        <div style={{
          background: '#fee',
          color: '#c33',
          padding: '1rem',
          borderRadius: '8px',
          border: '1px solid #fcc',
          textAlign: 'center'
        }}>
          <h3 style={{ margin: '0 0 0.5rem 0' }}>❌ Error</h3>
          <p style={{ margin: '0' }}>{error}</p>
        </div>
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '50vh',
        flexDirection: 'column',
        gap: '1rem',
        padding: '2rem'
      }}>
        <div style={{
          background: '#f0f9ff',
          color: '#0369a1',
          padding: '2rem',
          borderRadius: '12px',
          border: '1px solid #bae6fd',
          textAlign: 'center'
        }}>
          <h3 style={{ margin: '0 0 1rem 0' }}>📁 No hay proyectos</h3>
          <p style={{ margin: '0' }}>No se encontraron proyectos disponibles.</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{
      padding: '2rem',
      maxWidth: '1200px',
      margin: '0 auto'
    }}>
      <h2 style={{
        textAlign: 'center',
        marginBottom: '2rem',
        color: '#1e293b',
        fontSize: '2rem',
        fontWeight: '700'
      }}>
        📁 Mis Proyectos
      </h2>
      
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
        gap: '1.5rem',
        padding: '0 1rem'
      }}>
        {projects.map((project) => (
          <div
            key={project._id}
            onClick={() => onProjectSelect(project)}
            style={{
              background: 'linear-gradient(135deg, #ea580c 0%, #fb923c 100%)',
              borderRadius: '12px',
              padding: '1.5rem',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              border: '2px solid transparent',
              boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
              color: 'white',
              position: 'relative',
              overflow: 'hidden'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-4px)';
              e.currentTarget.style.boxShadow = '0 8px 25px rgba(0, 0, 0, 0.15)';
              e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.3)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 4px 6px rgba(0, 0, 0, 0.1)';
              e.currentTarget.style.borderColor = 'transparent';
            }}
          >
            {/* Thumbnail del video */}
            <div style={{
              width: '100%',
              height: '160px',
              background: 'rgba(0, 0, 0, 0.3)',
              borderRadius: '8px',
              marginBottom: '1rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative'
            }}>
              <div style={{
                fontSize: '3rem',
                opacity: '0.7'
              }}>
                🎬
              </div>
              <div style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                background: 'rgba(0, 0, 0, 0.7)',
                borderRadius: '50%',
                width: '50px',
                height: '50px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '1.5rem'
              }}>
                ▶️
              </div>
            </div>

            {/* Información del proyecto */}
            <div>
              <h3 style={{
                margin: '0 0 0.5rem 0',
                fontSize: '1.2rem',
                fontWeight: '600'
              }}>
                {project.name || `Proyecto ${project._id.slice(-6)}`}
              </h3>
              
              <p style={{
                margin: '0 0 1rem 0',
                opacity: '0.9',
                fontSize: '0.9rem',
                lineHeight: '1.4'
              }}>
                {project.description || 'Sin descripción disponible'}
              </p>

              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontSize: '0.8rem',
                opacity: '0.8'
              }}>
                <span>
                  📅 {new Date(project.created_at || project.createdAt || Date.now()).toLocaleDateString()}
                </span>
                <span>
                  🆔 {project._id.slice(-8)}
                </span>
              </div>
            </div>

            {/* Indicador de hover */}
            <div style={{
              position: 'absolute',
              top: '1rem',
              right: '1rem',
              background: 'rgba(255, 255, 255, 0.2)',
              borderRadius: '20px',
              padding: '0.25rem 0.75rem',
              fontSize: '0.8rem',
              opacity: '0',
              transition: 'opacity 0.3s ease'
            }}
            onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
            onMouseLeave={(e) => e.currentTarget.style.opacity = '0'}
            >
              Ver proyecto
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default ProjectList; 