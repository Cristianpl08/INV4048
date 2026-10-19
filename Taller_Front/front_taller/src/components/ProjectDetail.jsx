import React, { useState, useRef, useEffect } from 'react';
import { useProject } from '../hooks/useProjects.js';

function ProjectDetail({ projectId, onBackToList, onOpenPlayer }) {
  const { project, loading, error } = useProject(projectId);
  const videoRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [showControls, setShowControls] = useState(true);

  // Función para convertir URL de Google Drive a formato de reproducción
  const getVideoUrl = (url) => {
    if (!url) return null;
    
    // Si ya es una URL directa, usarla tal como está
    if (url.includes('drive.google.com/file/d/')) {
      const fileId = url.match(/\/file\/d\/([a-zA-Z0-9-_]+)/)?.[1];
      if (fileId) {
        return `https://drive.google.com/uc?export=download&id=${fileId}`;
      }
    }
    
    // Si es una URL de Google Drive con formato diferente
    if (url.includes('drive.google.com')) {
      const fileId = url.match(/[a-zA-Z0-9-_]{25,}/)?.[0];
      if (fileId) {
        return `https://drive.google.com/uc?export=download&id=${fileId}`;
      }
    }
    
    return url;
  };

  // Manejar eventos del video
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      setCurrentTime(video.currentTime);
    };

    const handleLoadedMetadata = () => {
      setDuration(video.duration);
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);

    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('loadedmetadata', handleLoadedMetadata);
    video.addEventListener('play', handlePlay);
    video.addEventListener('pause', handlePause);

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('loadedmetadata', handleLoadedMetadata);
      video.removeEventListener('play', handlePlay);
      video.removeEventListener('pause', handlePause);
    };
  }, []);

  // Formatear tiempo
  const formatTime = (time) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  // Manejar controles del video
  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
    }
  };

  const handleSeek = (e) => {
    const video = videoRef.current;
    if (video) {
      const rect = e.currentTarget.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const width = rect.width;
      const seekTime = (clickX / width) * duration;
      video.currentTime = seekTime;
    }
  };

  const handleVolumeChange = (e) => {
    const newVolume = parseFloat(e.target.value);
    setVolume(newVolume);
    if (videoRef.current) {
      videoRef.current.volume = newVolume;
    }
  };

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
        <p style={{ color: '#666', fontSize: '1.1rem' }}>Cargando proyecto...</p>
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
        <button
          onClick={onBackToList}
          style={{
            background: '#ea580c',
            color: 'white',
            border: 'none',
            padding: '0.75rem 1.5rem',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '1rem'
          }}
        >
          ← Volver a la lista
        </button>
      </div>
    );
  }

  if (!project) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '50vh',
        flexDirection: 'column',
        gap: '1rem'
      }}>
        <p style={{ color: '#666', fontSize: '1.1rem' }}>Proyecto no encontrado</p>
        <button
          onClick={onBackToList}
          style={{
            background: '#ea580c',
            color: 'white',
            border: 'none',
            padding: '0.75rem 1.5rem',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '1rem'
          }}
        >
          ← Volver a la lista
        </button>
      </div>
    );
  }

  const videoUrl = getVideoUrl(project.video || project.videoUrl);

  return (
    <div style={{
      padding: '2rem',
      maxWidth: '1200px',
      margin: '0 auto'
    }}>
      {/* Header con botón de regreso */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '2rem',
        gap: '1rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button
            onClick={onBackToList}
            style={{
              background: 'linear-gradient(135deg, #ea580c 0%, #fb923c 100%)',
              color: 'white',
              border: 'none',
              padding: '0.75rem 1.5rem',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '1rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              transition: 'transform 0.2s ease'
            }}
            onMouseEnter={(e) => e.currentTarget.style.transform = 'translateX(-2px)'}
            onMouseLeave={(e) => e.currentTarget.style.transform = 'translateX(0)'}
          >
            ← Volver a la lista
          </button>
          
          <h1 style={{
            margin: '0',
            color: '#1e293b',
            fontSize: '2rem',
            fontWeight: '700'
          }}>
            {project.name || `Proyecto ${project._id.slice(-6)}`}
          </h1>
        </div>

        {/* Botón para abrir el reproductor */}
        <button
          onClick={onOpenPlayer}
          style={{
            background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
            color: 'white',
            border: 'none',
            padding: '0.75rem 1.5rem',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '1rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            transition: 'all 0.2s ease',
            boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-2px)';
            e.currentTarget.style.boxShadow = '0 6px 12px rgba(0, 0, 0, 0.15)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = '0 4px 6px rgba(0, 0, 0, 0.1)';
          }}
        >
          🎬 Abrir Reproductor
        </button>
      </div>

      {/* Información del proyecto */}
      <div style={{
        background: 'linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)',
        borderRadius: '12px',
        padding: '1.5rem',
        marginBottom: '2rem',
        border: '1px solid #e2e8f0'
      }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1rem'
        }}>
          <div>
            <strong>📅 Fecha de creación:</strong>
            <p style={{ margin: '0.25rem 0 0 0', color: '#64748b' }}>
              {new Date(project.created_at || project.createdAt || Date.now()).toLocaleDateString()}
            </p>
          </div>
          <div>
            <strong>🆔 ID del proyecto:</strong>
            <p style={{ margin: '0.25rem 0 0 0', color: '#64748b' }}>
              {project._id}
            </p>
          </div>
          {project.updated_at && (
            <div>
              <strong>🔄 Última actualización:</strong>
              <p style={{ margin: '0.25rem 0 0 0', color: '#64748b' }}>
                {new Date(project.updated_at).toLocaleDateString()}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Reproductor de video */}
      <div style={{
        background: '#000',
        borderRadius: '12px',
        overflow: 'hidden',
        boxShadow: '0 10px 25px rgba(0, 0, 0, 0.2)',
        position: 'relative'
      }}>
        {videoUrl ? (
          <>
            <video
              ref={videoRef}
              src={videoUrl}
              style={{
                width: '100%',
                height: 'auto',
                display: 'block'
              }}
              onMouseMove={() => setShowControls(true)}
              onMouseLeave={() => setTimeout(() => setShowControls(false), 2000)}
            />
            
            {/* Controles personalizados */}
            <div style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              background: 'linear-gradient(transparent, rgba(0, 0, 0, 0.8))',
              padding: '1rem',
              opacity: showControls ? 1 : 0,
              transition: 'opacity 0.3s ease'
            }}>
              {/* Barra de progreso */}
              <div
                style={{
                  width: '100%',
                  height: '4px',
                  background: 'rgba(255, 255, 255, 0.3)',
                  borderRadius: '2px',
                  marginBottom: '1rem',
                  cursor: 'pointer',
                  position: 'relative'
                }}
                onClick={handleSeek}
              >
                                 <div style={{
                   width: `${(currentTime / duration) * 100}%`,
                   height: '100%',
                   background: '#ea580c',
                   borderRadius: '2px',
                   transition: 'width 0.1s ease'
                 }} />
              </div>

              {/* Controles principales */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '1rem'
              }}>
                <button
                  onClick={togglePlay}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'white',
                    fontSize: '1.5rem',
                    cursor: 'pointer',
                    padding: '0.5rem'
                  }}
                >
                  {isPlaying ? '⏸️' : '▶️'}
                </button>

                <span style={{ color: 'white', fontSize: '0.9rem' }}>
                  {formatTime(currentTime)} / {formatTime(duration)}
                </span>

                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem'
                }}>
                  <span style={{ color: 'white', fontSize: '0.9rem' }}>🔊</span>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={volume}
                    onChange={handleVolumeChange}
                    style={{
                      width: '80px'
                    }}
                  />
                </div>
              </div>
            </div>
          </>
        ) : (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '400px',
            color: 'white',
            fontSize: '1.2rem'
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🎬</div>
              <p>No se encontró URL de video para este proyecto</p>
            </div>
          </div>
        )}
      </div>

      {/* Descripción del proyecto */}
      {project.description && (
        <div style={{
          background: 'white',
          borderRadius: '12px',
          padding: '1.5rem',
          marginTop: '2rem',
          border: '1px solid #e2e8f0'
        }}>
          <h3 style={{ margin: '0 0 1rem 0', color: '#1e293b' }}>📝 Descripción</h3>
          <p style={{ margin: '0', lineHeight: '1.6', color: '#475569' }}>
            {project.description}
          </p>
        </div>
      )}
    </div>
  );
}

export default ProjectDetail; 