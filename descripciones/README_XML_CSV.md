# Conversor de XML a CSV

Script de Python para convertir archivos XML de WordPress (WordPress eXtended RSS) a formato CSV.

## Características

- ✅ Convierte archivos XML de exportación de WordPress a CSV
- ✅ Extrae información de posts, páginas y eventos
- ✅ Limpia automáticamente etiquetas HTML y CDATA
- ✅ Maneja múltiples namespaces de WordPress
- ✅ Extrae metadatos de eventos (fechas, timezone, URLs)
- ✅ Codificación UTF-8 para caracteres especiales

## Requisitos

- Python 3.6 o superior
- Librerías estándar (incluidas con Python):
  - `xml.etree.ElementTree`
  - `csv`
  - `re`
  - `html`

No necesitas instalar dependencias adicionales.

## Uso

### Método 1: Uso básico

1. Guarda tu archivo XML como `input.xml` en la misma carpeta que el script
2. Ejecuta el script:

```bash
python xml_to_csv.py
```

3. El resultado se guardará en `output.csv`

### Método 2: Personalizar nombres de archivos

Edita las últimas líneas del script:

```python
if __name__ == "__main__":
    xml_input = "mi_archivo.xml"  # Tu archivo XML
    csv_output = "mi_resultado.csv"  # Tu archivo CSV de salida
    
    xml_to_csv(xml_input, csv_output)
```

### Método 3: Importar como módulo

```python
from xml_to_csv import xml_to_csv

xml_to_csv("datos_wordpress.xml", "datos_convertidos.csv")
```

## Columnas del CSV generado

El CSV resultante incluye las siguientes columnas:

| Columna | Descripción |
|---------|-------------|
| `post_id` | ID del post en WordPress |
| `title` | Título del post/evento |
| `link` | URL del post |
| `pub_date` | Fecha de publicación |
| `creator` | Autor del contenido |
| `content` | Contenido del post (primeros 500 caracteres) |
| `excerpt` | Extracto del post |
| `post_date` | Fecha del post (hora local) |
| `post_date_gmt` | Fecha del post (GMT) |
| `post_modified` | Última modificación (hora local) |
| `post_modified_gmt` | Última modificación (GMT) |
| `status` | Estado (publish, draft, etc.) |
| `post_type` | Tipo (post, page, tribe_events, etc.) |
| `post_name` | Slug del post |
| `categories` | Categorías (separadas por ";") |
| `event_start_date` | Fecha inicio del evento |
| `event_end_date` | Fecha fin del evento |
| `event_timezone` | Zona horaria del evento |
| `event_url` | URL externa del evento |

## Ejemplo de código completo

```python
import xml.etree.ElementTree as ET
import csv

from xml_to_csv import xml_to_csv

# Convertir archivo XML a CSV
xml_to_csv("export_wordpress.xml", "posts_convertidos.csv")
```

## Características del limpiado de datos

El script automáticamente:

1. **Remueve etiquetas CDATA**: `<![CDATA[texto]]>` → `texto`
2. **Elimina HTML**: `<strong>texto</strong>` → `texto`
3. **Decodifica entidades HTML**: `&amp;` → `&`, `&quot;` → `"`
4. **Normaliza espacios**: Elimina espacios múltiples y saltos de línea
5. **Maneja valores nulos**: Campos vacíos se convierten en cadenas vacías

## Solución de problemas

### Error: "No se encontró el archivo"
- Verifica que el archivo XML existe en la carpeta correcta
- Verifica que el nombre del archivo es correcto (incluyendo la extensión .xml)

### Error: "ParseError"
- El archivo XML puede estar corrupto o mal formado
- Abre el archivo XML en un editor y verifica que está completo

### Caracteres extraños en el CSV
- Abre el CSV con un programa que soporte UTF-8 (como Excel, LibreOffice, o Google Sheets)
- En Excel: Datos → Desde texto → Selecciona UTF-8 como codificación

### Contenido truncado
- El contenido se limita a 500 caracteres por defecto
- Para cambiar esto, modifica esta línea en el código:
  ```python
  'content': content[:500] + '...' if len(content) > 500 else content
  ```
  Cambia `500` por el valor que desees, o elimina esta limitación:
  ```python
  'content': content
  ```

## Personalización

### Agregar más columnas

Para extraer campos adicionales de WordPress, agrega en `fieldnames`:

```python
fieldnames = [
    # ... columnas existentes ...
    'mi_nueva_columna'
]
```

Y luego en el bucle principal:

```python
mi_valor = item.find('wp:mi_campo', namespaces)
mi_valor = mi_valor.text if mi_valor is not None else ""

writer.writerow({
    # ... campos existentes ...
    'mi_nueva_columna': mi_valor
})
```

### Filtrar por tipo de post

Para exportar solo ciertos tipos de posts:

```python
if post_type == "tribe_events":  # Solo eventos
    writer.writerow({...})
```

## Licencia

Este script es de código abierto y libre de usar.

## Soporte

Si encuentras algún problema o necesitas ayuda, verifica:
1. Que estás usando Python 3.6+
2. Que el archivo XML es válido
3. Que tienes permisos de escritura en la carpeta de salida


