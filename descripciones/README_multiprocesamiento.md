# Multiprocesamiento para Procesamiento de Videos

Este proyecto ahora incluye capacidades de multiprocesamiento para procesar múltiples videos en paralelo, lo que puede reducir significativamente el tiempo total de procesamiento.

## 🚀 Características

- **Procesamiento Secuencial**: Procesa videos uno por uno (método original)
- **Procesamiento Paralelo Automático**: Usa todos los núcleos disponibles del sistema
- **Procesamiento Paralelo Personalizado**: Permite especificar el número de procesos
- **Comparación de Rendimiento**: Compara tiempos entre métodos secuencial y paralelo

## 📁 Archivos

- `Descripcionesmulti.py`: Script principal con funciones de multiprocesamiento
- `procesamiento_paralelo.py`: Interfaz interactiva para elegir el modo de procesamiento
- `README_multiprocesamiento.md`: Este archivo de documentación

## 🛠️ Uso

### Opción 1: Interfaz Interactiva (Recomendada)

Ejecuta el script interactivo:

```bash
python procesamiento_paralelo.py
```

Esto te mostrará un menú con las siguientes opciones:

1. **Procesamiento SECUENCIAL**: Procesa videos uno por uno
2. **Procesamiento PARALELO automático**: Usa todos los núcleos disponibles
3. **Procesamiento PARALELO personalizado**: Especifica cuántos procesos usar
4. **Comparar rendimiento**: Compara secuencial vs paralelo
5. **Salir**

### Opción 2: Uso Directo del Script Principal

Modifica `Descripcionesmulti.py` según tus necesidades:

```python
# Procesamiento secuencial (original)
process_videos_sequential("PruebaIAS", "output", api_key)

# Procesamiento paralelo automático
process_all_videos("PruebaIAS", "output", api_key)

# Procesamiento paralelo con 4 procesos
process_all_videos("PruebaIAS", "output", api_key, max_workers=4)
```

## ⚡ Ventajas del Multiprocesamiento

### Tiempo de Procesamiento
- **Secuencial**: Si tienes 10 videos y cada uno toma 5 minutos = 50 minutos total
- **Paralelo (4 núcleos)**: Los mismos 10 videos se procesan en ~12-15 minutos

### Escalabilidad
- Cuantos más núcleos tengas, mayor será la mejora de rendimiento
- Ideal para sistemas con múltiples núcleos (4, 8, 16+ núcleos)

## 🔧 Configuración Recomendada

### Para Sistemas con 4-8 Núcleos
```python
# Usar todos los núcleos disponibles
process_all_videos("PruebaIAS", "output", api_key)
```

### Para Sistemas con Muchos Núcleos (16+)
```python
# Limitar a un número razonable para evitar saturación
process_all_videos("PruebaIAS", "output", api_key, max_workers=8)
```

### Para Sistemas con Recursos Limitados
```python
# Usar solo 2-4 procesos para evitar sobrecarga
process_all_videos("PruebaIAS", "output", api_key, max_workers=2)
```

## 📊 Monitoreo del Rendimiento

El script proporciona información detallada sobre:

- Número de procesos utilizados
- Tiempo total de procesamiento
- Videos procesados exitosamente
- Videos con errores
- Comparación de rendimiento (cuando se usa la opción 4)

## ⚠️ Consideraciones Importantes

### Memoria
- Cada proceso consume memoria adicional
- Si tienes videos grandes, considera usar menos procesos
- Monitorea el uso de RAM durante el procesamiento

### API Rate Limits
- Cada proceso hace llamadas independientes a la API de OpenAI
- Asegúrate de que tu plan de API soporte múltiples llamadas simultáneas
- Considera implementar delays entre llamadas si es necesario

### GPU (si usas CUDA)
- Si usas GPU para CLIP, cada proceso intentará usar la GPU
- Esto puede causar conflictos de memoria
- Considera usar CPU para multiprocesamiento intensivo

## 🐛 Solución de Problemas

### Error: "Too many open files"
```python
# Reducir el número de procesos
process_all_videos("PruebaIAS", "output", api_key, max_workers=2)
```

### Error: "Out of memory"
```python
# Usar menos procesos o procesar en lotes más pequeños
process_all_videos("PruebaIAS", "output", api_key, max_workers=1)
```

### Error: "API rate limit exceeded"
```python
# Implementar delays o usar procesamiento secuencial
process_videos_sequential("PruebaIAS", "output", api_key)
```

## 📈 Ejemplo de Resultados

```
============================================================
COMPARACIÓN DE RENDIMIENTO
============================================================
Tiempo secuencial: 1250.45 segundos
Tiempo paralelo: 312.67 segundos
Speedup: 4.00x más rápido
Mejora de tiempo: 75.0%
============================================================
```

## 🔄 Migración desde el Código Original

Si ya tienes el código original funcionando:

1. **Backup**: Haz una copia de tu script original
2. **Reemplazo**: Usa el nuevo `Descripcionesmulti.py`
3. **Prueba**: Ejecuta con pocos videos primero
4. **Escala**: Aumenta gradualmente el número de procesos

## 📞 Soporte

Si encuentras problemas:

1. Verifica que todas las dependencias estén instaladas
2. Prueba con procesamiento secuencial primero
3. Reduce el número de procesos si hay errores
4. Revisa los logs de error para más detalles

---

**¡Disfruta del procesamiento paralelo y reduce significativamente tus tiempos de procesamiento!** 🚀 