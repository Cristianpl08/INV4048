import React, { useState, useEffect } from "react";
import VideoSegmentPlayer from "./VideoSegmentPlayer";
import Login from "./components/Login";
import ProjectList from "./components/ProjectList";
import ProjectDetail from "./components/ProjectDetail";
import { useAuth } from "./contexts/AuthContext.jsx";
import { API_CONFIG } from "./config.js";
import { apiService } from "./services/api.js";
import './App.css';

function App() {
  const { isAuthenticated, user, loading: authLoading, logout } = useAuth();
  const [loading, setLoading] = useState(true);
  const [projectData, setProjectData] = useState(null);
  const [segments, setSegments] = useState([]);
  const [error, setError] = useState('');
  const [currentView, setCurrentView] = useState('player'); // 'projects', 'detail', 'player'
  const [selectedProject, setSelectedProject] = useState(null);
  const [selectedActivity, setSelectedActivity] = useState('actividad1'); // Estado para la actividad seleccionada
  const [lastSelectedActivity, setLastSelectedActivity] = useState('actividad1'); // Estado para la última actividad real seleccionada

  // Verificar autenticación al cargar la aplicación
  useEffect(() => {
    const checkAuth = async () => {
      if (isAuthenticated) {
        // Intentar cargar datos del proyecto desde localStorage primero
        const savedProject = localStorage.getItem('currentProject');
        const savedSegments = localStorage.getItem('currentSegments');
        
        if (savedProject && savedSegments) {
          try {
            console.log('📦 Cargando datos del proyecto desde localStorage...');
            setProjectData(JSON.parse(savedProject));
            setSegments(JSON.parse(savedSegments));
            setCurrentView('player'); // Ir directamente al reproductor
            console.log('✅ Datos cargados desde localStorage, mostrando reproductor');
          } catch (error) {
            console.error('Error cargando datos desde localStorage:', error);
            await loadProjectData();
          }
        } else {
          await loadProjectData();
        }
      }
      setLoading(false);
    };
    
    checkAuth();
  }, [isAuthenticated]);

  // Cargar datos del proyecto y segmentos
  const loadProjectData = async (projectId = API_CONFIG.PROJECT_ID) => {
    try {
      setLoading(true);
      setError('');
      
      console.log("📡 Cargando datos del proyecto:", projectId);
      
      // Cargar proyecto (que incluye los segmentos)
      const project = await apiService.getProject(projectId);
      console.log("✅ Proyecto cargado:", project);
      setProjectData(project);
      
      // Los segmentos vienen incluidos en la respuesta del proyecto
      const segmentsFromProject = project.segments || [];
      console.log("✅ Segmentos cargados:", segmentsFromProject.length, "segmentos");
      
      // Transformar los segmentos para que sean compatibles con el formato esperado
      const transformedSegments = segmentsFromProject.map((segment, index) => ({
        id: index + 1, // ID numérico para compatibilidad
        start: segment.start_time * 1000, // Convertir a milisegundos
        end: segment.end_time * 1000, // Convertir a milisegundos
        duration: segment.duration || (segment.end_time - segment.start_time),
        description: segment.description || '',
        prosody: segment.prosody || '',
        prosody2: segment.prosody2 || '',
        views: segment.views || 0,
        likes: segment.likes || 0,
        _id: segment._id,
        projectid: segment.project_id
      }));
      
      setSegments(transformedSegments);
      setCurrentView('player'); // Ir al reproductor después de cargar los datos
      console.log("🎯 Video y wave surfer se cargarán automáticamente");
    } catch (error) {
      console.error('Error loading project data:', error);
      setError('Error al cargar los datos del proyecto. Verifica tu conexión.');
      // Si hay error de autenticación, cerrar sesión
      if (error.message.includes('401') || error.message.includes('403')) {
        handleLogout();
      }
    } finally {
      setLoading(false);
    }
  };

  const handleLoginSuccess = async () => {
    console.log("🔐 Login exitoso, cargando datos del proyecto...");
    await loadProjectData();
    console.log("✅ Datos del proyecto cargados automáticamente");
  };

  const handleLogout = async () => {
    await logout();
    setProjectData(null);
    setSegments([]);
    setError('');
    setCurrentView('projects');
    setSelectedProject(null);
  };

  const handleProjectSelect = (project) => {
    setSelectedProject(project);
    setCurrentView('detail');
  };

  const handleBackToProjects = () => {
    setCurrentView('projects');
    setSelectedProject(null);
  };

  const handleOpenPlayer = async (project) => {
    setSelectedProject(project);
    setCurrentView('player');
    await loadProjectData(project._id);
  };

  if (authLoading || loading) {
    return (
              <div style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          background: 'linear-gradient(135deg, #ea580c 0%, #fb923c 100%)'
        }}>
        <div style={{
          background: 'white',
          padding: '2rem',
          borderRadius: '10px',
          boxShadow: '0 10px 25px rgba(0,0,0,0.1)',
          textAlign: 'center'
        }}>
          <div style={{
            width: '40px',
            height: '40px',
            border: '4px solid #f3f3f3',
            borderTop: '4px solid #ea580c',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            margin: '0 auto 1rem'
          }}></div>
          <h3 style={{ margin: '0 0 1rem 0', color: '#1e293b' }}>
            {authLoading ? '🔐 Verificando autenticación...' : '🚀 Cargando proyecto automáticamente...'}
          </h3>
          {!authLoading && loading && (
            <div style={{ color: '#64748b', fontSize: '0.9rem' }}>
              <p style={{ margin: '0.5rem 0' }}>📡 Conectando con el servidor...</p>
              <p style={{ margin: '0.5rem 0' }}>📁 Obteniendo datos del proyecto...</p>
              <p style={{ margin: '0.5rem 0' }}>🎬 Preparando reproductor de video...</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Login />;
  }

  // Renderizar diferentes vistas según el estado
  const renderContent = () => {
    switch (currentView) {
      case 'projects':
        return <ProjectList onProjectSelect={handleProjectSelect} />;
      
      case 'detail':
        return (
          <ProjectDetail 
            projectId={selectedProject?._id} 
            onBackToList={handleBackToProjects}
            onOpenPlayer={() => handleOpenPlayer(selectedProject)}
          />
        );
      
      case 'player':
        return (
          <div>
            {/* Header con información del proyecto y botón de logout */}
            <div style={{
              background: 'linear-gradient(135deg, #ea580c 0%, #fb923c 100%)',
              color: 'white',
              padding: '0.5rem 1.5rem',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              boxShadow: '0 2px 10px rgba(0,0,0,0.1)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <h1 style={{ margin: '0', fontSize: '1.5rem' }}>🎬 Taller</h1>
                
                {/* Menú hamburguesa */}
                <div style={{ position: 'relative' }}>
                  <button
                    onClick={() => {
                      // If menu is open, close it and restore the last selected activity
                      // If menu is closed, open it and remember the current activity
                      if (selectedActivity === 'menu-open') {
                        setSelectedActivity(lastSelectedActivity);
                      } else {
                        setLastSelectedActivity(selectedActivity); // Remember current activity
                        setSelectedActivity('menu-open');
                      }
                    }}
                    style={{
                      background: 'rgba(255,255,255,0.2)',
                      border: '1px solid rgba(255,255,255,0.3)',
                      color: 'white',
                      padding: '0.4rem 0.8rem',
                      borderRadius: '5px',
                      cursor: 'pointer',
                      transition: 'background 0.3s',
                      fontSize: '0.9rem',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem'
                    }}
                    onMouseOver={e => e.currentTarget.style.background = 'rgba(255,255,255,0.3)'}
                    onMouseOut={e => e.currentTarget.style.background = 'rgba(255,255,255,0.2)'}
                  >
                    <span>☰</span>
                    Actividades
                  </button>
                  
                  {/* Dropdown del menú */}
                  {selectedActivity === 'menu-open' && (
                    <div style={{
                      position: 'absolute',
                      top: '100%',
                      left: '0',
                      background: 'white',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                      zIndex: 1000,
                      minWidth: '200px',
                      marginTop: '0.5rem'
                    }}>
                      <div
                        onClick={() => {
                          // Set the activity directly instead of setting menu-open
                          setSelectedActivity('actividad1'); // This will close the menu and set the activity
                          setLastSelectedActivity('actividad1');
                        }}
                        style={{
                          padding: '0.75rem 1rem',
                          cursor: 'pointer',
                          borderBottom: '1px solid #f1f5f9',
                          background: lastSelectedActivity === 'actividad1' ? '#fef3c7' : 'transparent',
                          color: lastSelectedActivity === 'actividad1' ? '#92400e' : '#374151',
                          fontWeight: lastSelectedActivity === 'actividad1' ? '600' : '400'
                        }}
                        onMouseOver={e => e.currentTarget.style.background = lastSelectedActivity === 'actividad1' ? '#fef3c7' : '#f8fafc'}
                        onMouseOut={e => e.currentTarget.style.background = lastSelectedActivity === 'actividad1' ? '#fef3c7' : 'transparent'}
                      >
                        📝 Actividad 1
                      </div>
                      <div
                        onClick={() => {
                          // Set the activity directly instead of menu-open
                          setSelectedActivity('actividad2');
                          setLastSelectedActivity('actividad2');
                        }}
                        style={{
                          padding: '0.75rem 1rem',
                          cursor: 'pointer',
                          borderBottom: '1px solid #f1f5f9',
                          background: lastSelectedActivity === 'actividad2' ? '#fef3c7' : 'transparent',
                          color: lastSelectedActivity === 'actividad2' ? '#92400e' : '#374151',
                          fontWeight: lastSelectedActivity === 'actividad2' ? '600' : '400'
                        }}
                        onMouseOver={e => e.currentTarget.style.background = lastSelectedActivity === 'actividad2' ? '#fef3c7' : '#f8fafc'}
                        onMouseOut={e => e.currentTarget.style.background = lastSelectedActivity === 'actividad2' ? '#fef3c7' : 'transparent'}
                      >
                        📋 Actividad 2
                      </div>
                      <div
                        onClick={() => {
                          // Set the activity directly instead of menu-open
                          setSelectedActivity('actividad3');
                          setLastSelectedActivity('actividad3');
                        }}
                        style={{
                          padding: '0.75rem 1rem',
                          cursor: 'pointer',
                          borderBottom: '1px solid #f1f5f9',
                          background: lastSelectedActivity === 'actividad3' ? '#fef3c7' : 'transparent',
                          color: lastSelectedActivity === 'actividad3' ? '#92400e' : '#374151',
                          fontWeight: lastSelectedActivity === 'actividad3' ? '600' : '400'
                        }}
                        onMouseOver={e => e.currentTarget.style.background = lastSelectedActivity === 'actividad3' ? '#fef3c7' : '#f8fafc'}
                        onMouseOut={e => e.currentTarget.style.background = lastSelectedActivity === 'actividad3' ? '#fef3c7' : 'transparent'}
                      >
                        📊 Actividad 3
                      </div>
                      <div
                        onClick={() => {
                          // Set the activity directly instead of menu-open
                          setSelectedActivity('actividad4');
                          setLastSelectedActivity('actividad4');
                        }}
                        style={{
                          padding: '0.75rem 1rem',
                          cursor: 'pointer',
                          background: lastSelectedActivity === 'actividad4' ? '#fef3c7' : 'transparent',
                          color: lastSelectedActivity === 'actividad4' ? '#92400e' : '#374151',
                          fontWeight: lastSelectedActivity === 'actividad4' ? '600' : '400'
                        }}
                        onMouseOver={e => e.currentTarget.style.background = lastSelectedActivity === 'actividad4' ? '#fef3c7' : '#f8fafc'}
                        onMouseOut={e => e.currentTarget.style.background = lastSelectedActivity === 'actividad4' ? '#fef3c7' : 'transparent'}
                      >
                        📝 Actividad 4
                      </div>
                    </div>
                  )}
                </div>
                
                {projectData && (
                  <p style={{ margin: '0.25rem 0 0 0', opacity: '0.9', fontSize: '0.85rem' }}>
                    {segments.length} segmentos disponibles
                  </p>
                )}
              </div>
              <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                <button
                  onClick={handleLogout}
                  style={{
                    background: 'rgba(255,255,255,0.2)',
                    border: '1px solid rgba(255,255,255,0.3)',
                    color: 'white',
                    padding: '0.4rem 0.8rem',
                    borderRadius: '5px',
                    cursor: 'pointer',
                    transition: 'background 0.3s',
                    fontSize: '0.9rem'
                  }}
                  onMouseOver={e => e.currentTarget.style.background = 'rgba(255,255,255,0.3)'}
                  onMouseOut={e => e.currentTarget.style.background = 'rgba(255,255,255,0.2)'}
                >
                  Cerrar Sesión
                </button>
              </div>
            </div>

            {/* Mostrar error si existe */}
            {error && (
              <div style={{
                background: '#fee',
                color: '#c33',
                padding: '1rem',
                margin: '1rem 2rem',
                borderRadius: '5px',
                border: '1px solid #fcc',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <span>{error}</span>
                <button
                  onClick={() => setError('')}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#c33',
                    cursor: 'pointer',
                    fontSize: '1.2rem'
                  }}
                >
                  ×
                </button>
              </div>
            )}



            {/* Componente principal del reproductor */}
            <VideoSegmentPlayer 
              segments={segments}
              projectData={projectData}
              hideUpload={true} // Ocultar la subida de archivos ya que usamos la API
              selectedActivity={selectedActivity === 'menu-open' ? lastSelectedActivity : selectedActivity} // Pasar la actividad real seleccionada
            />
          </div>
        );
      
      default:
        return <ProjectList onProjectSelect={handleProjectSelect} />;
    }
  };

  return (
    <div>
      {/* Header principal solo para vistas de proyectos y detalle */}
      {currentView !== 'player' && (
        <div style={{
          background: 'linear-gradient(135deg, #ea580c 0%, #fb923c 100%)',
          color: 'white',
          padding: '0.5rem 1.5rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          boxShadow: '0 2px 10px rgba(0,0,0,0.1)'
        }}>
                  <div>
          <h1 style={{ margin: '0', fontSize: '1.5rem' }}>
            {currentView === 'projects' ? '📁 Mis Proyectos' : '🎬 Reproductor de Videos'}
          </h1>
          {user && (
            <p style={{ margin: '0.25rem 0 0 0', opacity: '0.9', fontSize: '0.85rem' }}>
              👤 {user.email || user.name || 'Usuario'}
            </p>
          )}
        </div>
          <button
            onClick={handleLogout}
            style={{
              background: 'rgba(255,255,255,0.2)',
              border: '1px solid rgba(255,255,255,0.3)',
              color: 'white',
              padding: '0.4rem 0.8rem',
              borderRadius: '5px',
              cursor: 'pointer',
              transition: 'background 0.3s',
              fontSize: '0.9rem'
            }}
            onMouseOver={e => e.currentTarget.style.background = 'rgba(255,255,255,0.3)'}
            onMouseOut={e => e.currentTarget.style.background = 'rgba(255,255,255,0.2)'}
          >
            Cerrar Sesión
          </button>
        </div>
      )}

      {/* Contenido principal */}
      {renderContent()}
    </div>
  );
}

export default App;