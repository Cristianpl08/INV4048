#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script simplificado para convertir XML de WordPress a CSV
Versión rápida con opciones por línea de comandos
"""

import sys
import os
import xml.etree.ElementTree as ET
from xml_to_csv import xml_to_csv

def mostrar_ayuda():
    """Muestra la ayuda del programa"""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║           Conversor XML de WordPress a CSV                    ║
╚═══════════════════════════════════════════════════════════════╝

USO:
    python convertir_simple.py <archivo_xml> [archivo_csv]

EJEMPLOS:
    python convertir_simple.py datos.xml
    python convertir_simple.py export.xml resultado.csv
    python convertir_simple.py "mi archivo.xml" "mi resultado.csv"

ARGUMENTOS:
    archivo_xml     Archivo XML de entrada (requerido)
    archivo_csv     Archivo CSV de salida (opcional)
                    Si no se especifica, usa el mismo nombre que
                    el XML pero con extensión .csv

OPCIONES:
    -h, --help      Muestra esta ayuda
    """)

def main():
    """Función principal"""
    
    # Verificar ayuda
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help', '?']:
        mostrar_ayuda()
        sys.exit(0)
    
    # Obtener archivo XML
    xml_file = sys.argv[1]
    
    # Verificar que existe
    if not os.path.exists(xml_file):
        print(f"❌ ERROR: No se encuentra el archivo '{xml_file}'")
        print("\nVerifica que:")
        print("  • El nombre del archivo es correcto")
        print("  • El archivo está en la carpeta actual")
        print("  • Tienes permisos de lectura")
        sys.exit(1)
    
    # Obtener archivo CSV de salida
    if len(sys.argv) >= 3:
        csv_file = sys.argv[2]
    else:
        # Usar el mismo nombre pero con extensión .csv
        csv_file = os.path.splitext(xml_file)[0] + '.csv'
    
    # Mostrar información
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║           Conversor XML de WordPress a CSV                    ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()
    print(f"📄 Archivo de entrada:  {xml_file}")
    print(f"📊 Archivo de salida:   {csv_file}")
    print()
    print("Procesando...")
    print()
    
    try:
        # Realizar la conversión
        xml_to_csv(xml_file, csv_file)
        print()
        print("╔═══════════════════════════════════════════════════════════════╗")
        print("║                    ✓ CONVERSIÓN EXITOSA                       ║")
        print("╚═══════════════════════════════════════════════════════════════╝")
        print()
        print(f"El archivo CSV se guardó en: {csv_file}")
        print()
        
    except PermissionError:
        print()
        print("❌ ERROR: No tienes permisos para escribir el archivo CSV")
        print("\nIntenta:")
        print("  • Cerrar el archivo CSV si está abierto")
        print("  • Usar una ubicación diferente")
        print("  • Ejecutar como administrador")
        sys.exit(1)
        
    except ET.ParseError as e:
        print()
        print("❌ ERROR: El archivo XML está mal formado")
        print(f"\nDetalle: {str(e)}")
        print("\nVerifica que:")
        print("  • El archivo XML está completo")
        print("  • No se interrumpió la descarga")
        print("  • Es un archivo XML válido de WordPress")
        sys.exit(1)
        
    except Exception as e:
        print()
        print(f"❌ ERROR INESPERADO: {str(e)}")
        print("\nPor favor, reporta este error.")
        sys.exit(1)

if __name__ == "__main__":
    main()

