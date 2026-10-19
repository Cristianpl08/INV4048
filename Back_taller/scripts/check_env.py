#!/usr/bin/env python3
"""
Script para verificar la configuración de variables de entorno
Útil para debugging en Railway
"""

import os

def check_environment():
    """Verificar variables de entorno críticas"""
    print("🔍 Verificando configuración de variables de entorno...")
    print("=" * 50)
    
    # Variables críticas
    critical_vars = {
        'MONGODB_URI': 'Conexión a MongoDB Atlas',
        'JWT_SECRET_KEY': 'Clave secreta para JWT',
        'FLASK_ENV': 'Ambiente de Flask',
        'PORT': 'Puerto del servidor'
    }
    
    all_good = True
    
    for var, description in critical_vars.items():
        value = os.environ.get(var)
        if value:
            # Ocultar valores sensibles
            if var in ['MONGODB_URI', 'JWT_SECRET_KEY']:
                display_value = value[:20] + "..." if len(value) > 20 else value
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")
        else:
            print(f"❌ {var}: NO CONFIGURADA - {description}")
            all_good = False
    
    print("=" * 50)
    
    if all_good:
        print("🎉 Todas las variables críticas están configuradas")
    else:
        print("⚠️ Faltan variables críticas. Configúralas en Railway.")
        print("\n📝 Variables que necesitas configurar en Railway:")
        print("MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>/<database>")
        print("JWT_SECRET_KEY=tu-clave-secreta-aqui")
        print("FLASK_ENV=production")
    
    return all_good

if __name__ == '__main__':
    check_environment() 