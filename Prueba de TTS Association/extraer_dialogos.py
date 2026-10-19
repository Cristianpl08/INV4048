import re
import os
from pathlib import Path
from docx import Document
from docx.shared import Pt

# ============================================
# CONFIGURACIÓN: Carpeta de archivos de entrada
# ============================================
CARPETA_DIARIZATION = "diarization"
# ============================================
def extraer_dialogos(archivo_txt):
    """
    Extrae solo los diálogos del archivo txt, eliminando speakers y timestamps
    Captura cualquier tipo de speaker entre corchetes: [Speaker X], [Crew], [Magallanes], etc.
    """
    dialogos = []
    
    with open(archivo_txt, 'r', encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()
            
            # Si la línea está vacía, saltarla
            if not linea:
                continue
            
            # Buscar líneas que contengan diálogos
            # Patrón flexible que captura:
            # - Cualquier texto entre corchetes [Cualquier cosa]
            # - Timestamp entre paréntesis (cualquier formato)
            # - Diálogo después de los dos puntos
            # Ejemplos: [Speaker 1] (0:09): texto
            #          [Crew] (2:05): texto
            #          [Magallanes] (3:11): texto
            #          [Crew (Contando)] (3:01): texto
            patron = r'^\[[^\]]+\]\s*\([^)]*\):\s*(.+)$'
            match = re.match(patron, linea)
            
            if match:
                # Extraer solo el texto del diálogo (después de los dos puntos)
                dialogo = match.group(1).strip()
                if dialogo:  # Solo agregar si hay texto
                    dialogos.append(dialogo)
    
    return dialogos

def guardar_en_word(dialogos, archivo_salida):
    """
    Guarda los diálogos en un documento Word, manteniendo los saltos de línea
    """
    doc = Document()
    
    # Configurar estilo por defecto
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    
    # Agregar cada diálogo como un párrafo separado
    for dialogo in dialogos:
        para = doc.add_paragraph(dialogo)
        para.paragraph_format.space_after = Pt(6)
    
    # Guardar el documento
    doc.save(archivo_salida)
    print(f"✓ Documento Word guardado: {archivo_salida}")
    print(f"✓ Total de diálogos extraídos: {len(dialogos)}")

def main():
    """
    Función principal - Procesa todos los archivos .txt en la carpeta diarization
    """
    print("=" * 60)
    print("EXTRACCIÓN DE DIÁLOGOS")
    print("=" * 60)
    
    # Verificar que existe la carpeta
    if not os.path.exists(CARPETA_DIARIZATION):
        print(f"✗ Error: No se encontró la carpeta '{CARPETA_DIARIZATION}'")
        return
    
    # Buscar todos los archivos .txt en la carpeta
    archivos_txt = list(Path(CARPETA_DIARIZATION).glob("*.txt"))
    
    if not archivos_txt:
        print(f"⚠ No se encontraron archivos .txt en la carpeta '{CARPETA_DIARIZATION}'")
        return
    
    print(f"\nSe encontraron {len(archivos_txt)} archivo(s) para procesar:\n")
    for archivo in archivos_txt:
        print(f"  - {archivo.name}")
    print()
    
    # Procesar cada archivo
    archivos_procesados = 0
    archivos_con_errores = 0
    
    for archivo_txt in archivos_txt:
        nombre_base = archivo_txt.stem  # Nombre sin extensión
        archivo_docx = f"{nombre_base}.docx"
        
        print("-" * 60)
        print(f"Procesando: {archivo_txt.name}")
        print(f"Salida: {archivo_docx}")
        
        try:
            # Extraer diálogos
            dialogos = extraer_dialogos(str(archivo_txt))
            
            if not dialogos:
                print(f"⚠ No se encontraron diálogos en '{archivo_txt.name}'")
                archivos_con_errores += 1
                continue
            
            # Guardar en Word
            guardar_en_word(dialogos, archivo_docx)
            archivos_procesados += 1
            
            # Mostrar una vista previa
            print(f"\n--- Vista previa (primeros 3 diálogos) ---")
            for i, dialogo in enumerate(dialogos[:3], 1):
                print(f"  {i}. {dialogo}")
            if len(dialogos) > 3:
                print(f"  ... y {len(dialogos) - 3} diálogos más")
            print()
            
        except FileNotFoundError:
            print(f"✗ Error: No se encontró el archivo '{archivo_txt}'")
            archivos_con_errores += 1
        except Exception as e:
            print(f"✗ Error al procesar '{archivo_txt.name}': {str(e)}")
            archivos_con_errores += 1
    
    # Resumen final
    print("\n" + "=" * 60)
    print("PROCESO COMPLETADO")
    print("=" * 60)
    print(f"✓ Archivos procesados exitosamente: {archivos_procesados}")
    if archivos_con_errores > 0:
        print(f"⚠ Archivos con errores: {archivos_con_errores}")

if __name__ == "__main__":
    main()

