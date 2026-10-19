#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

console.log('🔧 Configurando variables de entorno...\n');

// Verificar si ya existe el archivo .env
const envPath = path.join(__dirname, '.env');
if (fs.existsSync(envPath)) {
  console.log('⚠️  El archivo .env ya existe. ¿Deseas sobrescribirlo? (y/N)');
  process.stdin.once('data', (data) => {
    const answer = data.toString().trim().toLowerCase();
    if (answer === 'y' || answer === 'yes') {
      createEnvFile();
    } else {
      console.log('❌ Configuración cancelada.');
      process.exit(0);
    }
  });
} else {
  createEnvFile();
}

function createEnvFile() {
  const envContent = `# Configuración de la API
VITE_API_BASE_URL=http://localhost:5000
VITE_PROJECT_ID=6882f61f358cfb33745d32ca
`;

  try {
    fs.writeFileSync(envPath, envContent);
    console.log('✅ Archivo .env creado exitosamente!');
    console.log('\n📋 Configuración:');
    console.log('   - URL del backend: http://localhost:5000');
    console.log('   - ID del proyecto: 6882f61f358cfb33745d32ca');
    console.log('\n💡 Puedes modificar estos valores editando el archivo .env');
    console.log('\n🚀 Ahora puedes ejecutar: npm run dev');
  } catch (error) {
    console.error('❌ Error creando el archivo .env:', error.message);
  }
} 