import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext.jsx';

function Login() {
  const { login, loading: authLoading } = useAuth();
  const [credentials, setCredentials] = useState({
    email: '',
    password: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const vantaRef = useRef(null);

  // Initialize VANTA.TRUNK background effect
  useEffect(() => {
    const initVanta = () => {
      if (window.VANTA && vantaRef.current) {
        window.VANTA.TRUNK({
          el: vantaRef.current,
          mouseControls: true,
          touchControls: true,
          gyroControls: false,
          minHeight: 100.00,
          minWidth: 100.00,
          scale: 0.60,
          scaleMobile: 1.00,
          color: 0xff6b35,
          backgroundColor: 0xf8f9fa,
          spacing: 0,
          chaos: 4,
          size: 1.5,
          zoom: 1.00,
          xOffset: -0.3,
          yOffset: 0.0
        });
      }
    };

    // Try to initialize immediately
    initVanta();
    
    // If VANTA is not loaded yet, wait a bit and try again
    if (!window.VANTA) {
      setTimeout(initVanta, 1000);
    }
  }, []);

  // Log de configuración al montar el componente
  useEffect(() => {
    console.log('🔧 Login component mounted');
    console.log('🔐 Usando contexto de autenticación JWT');
  }, []);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    console.log(`📝 Input changed: ${name} = ${name === 'password' ? '***' : value}`);
    setCredentials(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    console.log('🔐 Login attempt started');
    console.log('📧 Credentials:', {
      email: credentials.email,
      password: credentials.password ? '***' : 'empty'
    });

    try {
      console.log('🚀 Calling auth context login...');
      const result = await login(credentials);
      
      if (result.success) {
        console.log('✅ Login successful');
        // El contexto ya maneja la redirección automática
      } else {
        console.log('❌ Login failed:', result.message);
        setError(result.message || 'Error de autenticación');
      }
    } catch (error) {
      console.error('❌ Login failed:', error);
      setError(`Error de autenticación: ${error.message}`);
    } finally {
      setLoading(false);
      console.log('🏁 Login attempt finished');
    }
  };

  return (
    <div 
      ref={vantaRef}
      style={{
        position: 'relative',
        width: '100vw',
        height: '100vh',
        overflow: 'hidden',
        backgroundColor: '#ffffff'
      }}
    >

             {/* Login form panel - positioned on the right */}
       <div style={{
         position: 'absolute',
         top: '50%',
         right: '4rem',
         transform: 'translateY(-50%)',
         background: 'rgba(255, 255, 255, 0.5)',
         backdropFilter: 'blur(5px)',
         padding: '2rem',
         borderRadius: '10px',
         boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
         width: '350px',
         maxWidth: '90vw',
         zIndex: 20
       }}>
                 <h2 style={{
           textAlign: 'center',
           marginBottom: '2rem',
           color: '#000',
           fontSize: '1.8rem',
           fontWeight: '700',
           textShadow: '0 1px 2px rgba(255,255,255,0.8)'
         }}>
Bienvenido de nuevo        </h2>
        
        <form onSubmit={handleSubmit}>
                     <div style={{ marginBottom: '1.5rem' }}>
             <label style={{
               display: 'block',
               marginBottom: '0.5rem',
               color: '#000',
               fontSize: '0.9rem',
               fontWeight: '600',
               textShadow: '0 1px 1px rgba(255,255,255,0.6)'
             }}>
               Email
             </label>
                         <input
               type="email"
               name="email"
               value={credentials.email}
               onChange={handleInputChange}
               required
                               style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: '2px solid #333',
                  borderRadius: '5px',
                  fontSize: '1rem',
                  boxSizing: 'border-box',
                  backgroundColor: '#f8f9fa',
                  color: '#eb4d2e',
                  fontWeight: '500',
                  transition: 'all 0.3s ease'
                }}
               placeholder="usuario@gmail.com"
               onFocus={(e) => {
                 e.target.style.transform = 'scale(1.02)';
                 e.target.style.boxShadow = '0 0 15px rgba(235, 77, 46, 0.3)';
                 e.target.style.borderColor = '#eb4d2e';
               }}
               onBlur={(e) => {
                 e.target.style.transform = 'scale(1)';
                 e.target.style.boxShadow = 'none';
                 e.target.style.borderColor = '#333';
               }}
             />
          </div>
          
                     <div style={{ marginBottom: '1rem' }}>
             <label style={{
               display: 'block',
               marginBottom: '0.5rem',
               color: '#000',
               fontSize: '0.9rem',
               fontWeight: '600',
               textShadow: '0 1px 1px rgba(255,255,255,0.6)'
             }}>
               Contraseña
             </label>
                         <input
               type="password"
               name="password"
               value={credentials.password}
               onChange={handleInputChange}
               required
                               style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: '2px solid #333',
                  borderRadius: '5px',
                  fontSize: '1rem',
                  boxSizing: 'border-box',
                  backgroundColor: '#f8f9fa',
                  color: '#eb4d2e',
                  fontWeight: '500',
                  transition: 'all 0.3s ease',
                  WebkitTextSecurity: 'disc',
                  textSecurity: 'disc'
                }}
               placeholder="Contraseña"
               onFocus={(e) => {
                 e.target.style.transform = 'scale(1.02)';
                 e.target.style.boxShadow = '0 0 15px rgba(235, 77, 46, 0.3)';
                 e.target.style.borderColor = '#eb4d2e';
               }}
               onBlur={(e) => {
                 e.target.style.transform = 'scale(1)';
                 e.target.style.boxShadow = 'none';
                 e.target.style.borderColor = '#333';
               }}
             />
          </div>

          
          
          {error && (
            <div style={{
              background: '#fee',
              color: '#c33',
              padding: '0.75rem',
              borderRadius: '5px',
              marginBottom: '1rem',
              border: '1px solid #fcc',
              fontSize: '0.9rem'
            }}>
              {error}
            </div>
          )}
          
          <button
            type="submit"
            disabled={loading || authLoading}
            style={{
              width: '100%',
              padding: '0.75rem',
              background: (loading || authLoading) ? '#ccc' : '#eb4d2e',
              color: 'white',
              border: 'none',
              borderRadius: '5px',
              fontSize: '1rem',
              cursor: (loading || authLoading) ? 'not-allowed' : 'pointer',
              transition: 'background 0.3s',
              fontWeight: '500'
            }}
          >
            {loading || authLoading ? 'Iniciando sesión...' : 'Iniciar sesión'}
          </button>

      
        </form>
      </div>
    </div>
  );
}

export default Login; 