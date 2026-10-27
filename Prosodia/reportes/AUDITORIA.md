# Auditoría de notebooks, entradas, salidas y artículo

Fecha: 6 de octubre de 2026. Alcance: los tres notebooks, el texto fuente del artículo,
los JSON de 10 videos, las voces de Andrea/Sergio/Sebastian y los resultados entregados.

## Conclusión comprobable

**El código recibido sintetiza solo con XTTS. No se encontró implementación de Spanish-F5.**
`EmotivaAD (1).ipynb`, celda 41, y `Integracion_final_(1).ipynb`, celda 12
(índices desde cero) llaman a `tts.tts_to_file` con `language="es"`.
Las búsquedas de F5/Spanish-F5 en el código no identifican un segundo motor.

La carpeta `2. Output AD` contiene 30 WAV y `3. AD Final` contiene otros 30 WAV.
Son **dos etapas de XTTS**, con 10 videos × 3 locutores en cada una; no acreditan
las 60 generaciones de dos modelos indicadas en `sn-article (6).tex`, líneas 314 y 333.
No se encontraron WAV identificados como Spanish-F5 entre los archivos entregados.
Esto no descarta que existan en otro lugar; no están en este material.

`Graficas Prosodia.ipynb` contiene dos celdas y produce principalmente radares de
las 16 emociones y tres locutores. No implementa generación de voz.

## Problemas corregidos en la versión nueva

| Hallazgo | Consecuencia | Cambio |
|---|---|---|
| Credenciales literales y salidas persistentes | Exposición al compartir notebooks | Copias sanitizadas y ningún secreto incorporado en los notebooks nuevos |
| Cambios de NumPy/Pandas/CUDA en varias celdas | Importaciones incompatibles y necesidad de reiniciar | Python 3.11 aislado por motor; comprobación de dependencias |
| Spanish-F5 solo mencionado en el paper | Comparación entre modelos no reproducible | Adaptador real y opciones 1/2/3/4 con manifiestos separados |
| Se eliminan puntos antes de sintetizar | Cambia el texto/prosodia experimental | Conservar puntuación y texto idénticos |
| Se acepta el último audio aunque falle su verificación | Salidas potencialmente incorrectas tratadas como válidas | Validación de WAV y errores explícitos; revisión semántica humana pendiente |
| Limpieza de ruido, silencio y mezcla sobre la misma salida | Confusión entre efecto del modelo y del postprocesado | RAW separado de la copia temporal ajustada y de la mezcla |
| Mezclador busca Main_Video.json y nombres segmento_ID | No coincide con los nombres MSVD usados por el generador | Un único project.json con IDs y tiempos explícitos |
| Selección de un primer archivo/folder de Drive | Posibles asociaciones incorrectas | Rutas explícitas verificadas contra cada video |
| Sonoridad, ritmo y duración con etiquetas ambiguas | Interpretaciones físicas equivocadas | Nombres de medidas eGeMAPS y unidades/proxies documentados |
| Z-score seguido de min–max dentro de cada conjunto | Escalas no comparables entre corpus/modelos | Medidas originales y z común ajustado solo con referencias |
| Voz más larga que el hueco | Se pisa audio posterior | Aceleración limitada o estado needs_edit, sin truncamiento |

El z-score seguido de min–max del notebook es algebraicamente equivalente a min–max
cuando la desviación no es cero. No proporciona por sí mismo una escala perceptual
de 1 a 5, ni permite comparar valores escalados por separado en distintos conjuntos.

Un JSON de fotogramas contiene incluso una respuesta de rechazo en lugar de una
descripción (`yAD_TS5L2d4_4_11`, frame 95). Los resúmenes deben revisarse semánticamente;
no se puede convertir cada respuesta del modelo automáticamente en verdad de referencia.

## Evidencia acústica añadida

Se recalculan eGeMAPSv02 Functionals para 48 referencias y 60 WAV de las dos etapas.
Las figuras principales usan los 30 audios `legacy_final`; `legacy_output` permanece
en el CSV para auditar postprocesamiento, sin sumarlo como nuevas observaciones.

1. Dispersión referencia–síntesis por cuatro medidas, con diagonal de identidad.
2. Dispersión de F0 frente a sonoridad, coloreada por locutor.
3. Boxplots con todas las observaciones, sin ocultar variabilidad con un promedio.
4. Matriz de correlaciones de Spearman, de interpretación descriptiva.
5. Mapa de perfiles emocionales con calibración común sobre referencias.
6. Comparación emparejada entre motores, habilitada únicamente al proporcionar ambos.

Se exportan PNG, SVG y PDF, medidas completas, errores absolutos y bootstrap agrupado
por video. Los tres locutores de un video no se tratan como tres videos independientes.
No se generan valores p ni resultados de Spanish-F5 inexistentes.

## Ajustes necesarios en el paper

- Mantener la comparación XTTS–Spanish-F5 como pendiente hasta generar, escuchar y
  evaluar los 30 audios del segundo motor con textos, referencias y etapas equivalentes.
- Revisar la afirmación de 60 salidas de dos modelos (líneas 314/333) y las conclusiones
  de diferencias entre modelos (línea 400). No inferirlas de los gráficos actuales.
- Reportar 10 videos como tamaño de muestra independiente, distribución de emociones,
  3 voces y repeticiones/semillas, con intervalos de incertidumbre.
- Separar resultados objetivos de sonoridad/F0/proxies de las afirmaciones de
  naturalidad, emoción percibida o accesibilidad: necesitan evaluación perceptual.
- `VoicedSegmentsPerSec` no equivale a palabras/s; `MeanUnvoicedSegmentLength` no
  equivale a duración total de la AD ni únicamente a pausas lingüísticas.
- La comparación semántica de ocho modelos indicada en el artículo necesita sus
  anotaciones, predicciones y scripts de métricas. Ese experimento no se reproduce
  con los CSV acústicos recibidos. Revisar también consistencia BLEU/BLEURT en el texto.
- Describir con precisión selección de fotogramas y prompts: mencionar atención
  en una descripción textual no demuestra una nueva arquitectura de atención.
- Sustituir “validación a gran escala” por un alcance acorde al corpus pequeño.
- Distinguir licencia del código de licencia de pesos: XTTS y Spanish-F5 no se deben
  presentar sin matices como alternativas abiertas de uso irrestricto.

El manuscrito original se conserva sin alterar resultados ni inventar evidencia.
