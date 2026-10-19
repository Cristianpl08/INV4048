#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para verificar el funcionamiento del nuevo flujo con segmentos.
Este script prueba la función cargar_tareas_locales con la nueva estructura.
"""

import os
import sys
import json

def test_new_structure():
    """Prueba la nueva estructura de segmentos"""
    print("=== PROBANDO NUEVA ESTRUCTURA DE SEGMENTOS ===")
    
    # Primero crear la estructura de ejemplo
    print("PASO 1: Creando estructura de ejemplo...")
    from create_example_structure import create_example_structure
    create_example_structure("temp")
    
    # Verificar que la función modificada funciona
    print("\nPASO 2: Probando función cargar_tareas_locales...")
    try:
        from Narrations_ducking import cargar_tareas_locales
        
        # Probar con la nueva estructura
        tareas = cargar_tareas_locales("temp")
        
        print(f"\n✅ RESULTADO DEL TEST:")
        print(f"   📊 Tareas encontradas: {len(tareas)}")
        
        if tareas:
            print(f"\n📋 DETALLES DE LAS TAREAS:")
            for i, tarea in enumerate(tareas, 1):
                print(f"\n   Tarea {i}:")
                print(f"   🆔 Video ID: {tarea.get('Video ID')}")
                print(f"   😊 Emoción: {tarea.get('Emoción')}")
                print(f"   📝 Texto (primeros 100 chars): {tarea.get('Texto a Generar', '')[:100]}...")
                print(f"   📁 Carpeta Origen: {tarea.get('Carpeta Origen')}")
                if 'Summary File' in tarea:
                    print(f"   📄 Summary File: {tarea.get('Summary File')}")
                if 'Prosody File' in tarea:
                    print(f"   📄 Prosody File: {tarea.get('Prosody File')}")
        else:
            print("   ❌ No se encontraron tareas válidas")
            
        return tareas
        
    except ImportError as e:
        print(f"❌ Error importando módulo: {e}")
        return None
    except Exception as e:
        print(f"❌ Error ejecutando prueba: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_structure_compatibility():
    """Prueba la compatibilidad con ambas estructuras"""
    print("\n=== PROBANDO COMPATIBILIDAD CON ESTRUCTURAS ANTERIORES ===")
    
    # Crear una estructura de ejemplo del método anterior
    old_structure_dir = "temp_old_test"
    os.makedirs(old_structure_dir, exist_ok=True)
    
    # Crear carpeta de descripción antigua
    desc_folder = os.path.join(old_structure_dir, "segment_001_descriptions")
    video_folder = os.path.join(desc_folder, "segment_001")
    os.makedirs(video_folder, exist_ok=True)
    
    # Crear archivos JSON en la estructura antigua
    summary_data = {
        "main_summary": "Esta es una prueba de la estructura anterior con carpetas de descripciones."
    }
    prosody_data = {
        "complementary_emotion": "nostálgia"
    }
    
    with open(os.path.join(video_folder, "video_summary.json"), 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)
    
    with open(os.path.join(video_folder, "prosody_analysis.json"), 'w', encoding='utf-8') as f:
        json.dump(prosody_data, f, ensure_ascii=False, indent=2)
    
    print(f"   📁 Estructura antigua creada en: {old_structure_dir}")
    
    # Probar con la estructura antigua
    try:
        from Narrations_ducking import cargar_tareas_locales
        tareas_old = cargar_tareas_locales(old_structure_dir)
        
        print(f"   ✅ Tareas encontradas en estructura antigua: {len(tareas_old)}")
        
        if tareas_old:
            tarea = tareas_old[0]
            print(f"   🆔 Video ID: {tarea.get('Video ID')}")
            print(f"   😊 Emoción: {tarea.get('Emoción')}")
            
        # Limpiar
        import shutil
        shutil.rmtree(old_structure_dir)
        
        return tareas_old
        
    except Exception as e:
        print(f"   ❌ Error probando estructura antigua: {e}")
        return None

def verify_structure_details():
    """Verifica los detalles de la estructura creada"""
    print("\n=== VERIFICANDO DETALLES DE LA ESTRUCTURA ===")
    
    temp_dir = "temp"
    if not os.path.exists(temp_dir):
        print(f"   ❌ Directorio {temp_dir} no existe")
        return
    
    print(f"   📂 Contenido de {temp_dir}:")
    for item in os.listdir(temp_dir):
        item_path = os.path.join(temp_dir, item)
        if os.path.isdir(item_path):
            print(f"      📁 {item}/")
            # Verificar si es un segmento
            if item.startswith('segment_') and item.endswith('s'):
                print(f"         📋 Archivos en {item}:")
                for subitem in os.listdir(item_path):
                    subitem_path = os.path.join(item_path, subitem)
                    if os.path.isdir(subitem_path):
                        print(f"            📁 {subitem}/")
                    else:
                        print(f"            📄 {subitem}")
                        
                # Verificar archivos clave
                summary_file = os.path.join(item_path, "video_summary.json")
                prosody_file = os.path.join(item_path, "prosody_analysis.json")
                
                if os.path.exists(summary_file):
                    print(f"         ✅ video_summary.json encontrado")
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if 'main_summary' in data:
                            print(f"            📝 Summary: {data['main_summary'][:50]}...")
                else:
                    print(f"         ❌ video_summary.json NO encontrado")
                
                if os.path.exists(prosody_file):
                    print(f"         ✅ prosody_analysis.json encontrado")
                    with open(prosody_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if 'complementary_emotion' in data:
                            print(f"            😊 Emoción: {data['complementary_emotion']}")
                else:
                    print(f"         ❌ prosody_analysis.json NO encontrado")
        else:
            print(f"      📄 {item}")

if __name__ == "__main__":
    print("🧪 INICIANDO TESTS DEL NUEVO FLUJO DE SEGMENTOS 🧪\n")
    
    # Test 1: Nueva estructura
    tareas_nuevas = test_new_structure()
    
    # Test 2: Compatibilidad con estructura anterior
    tareas_antiguas = test_structure_compatibility()
    
    # Test 3: Verificación de detalles
    verify_structure_details()
    
    # Resumen final
    print("\n" + "="*60)
    print("📊 RESUMEN DE TESTS:")
    print(f"   🆕 Tareas en nueva estructura: {len(tareas_nuevas) if tareas_nuevas else 0}")
    print(f"   🔄 Tareas en estructura anterior: {len(tareas_antiguas) if tareas_antiguas else 0}")
    print("="*60)
    
    if tareas_nuevas and len(tareas_nuevas) > 0:
        print("✅ Tests exitosos - El nuevo flujo funciona correctamente")
    else:
        print("❌ Tests fallidos - Revisar implementación")
