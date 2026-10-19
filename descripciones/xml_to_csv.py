import xml.etree.ElementTree as ET
import csv
import re
from html import unescape

def clean_text(text):
    """Limpia el texto removiendo etiquetas HTML y caracteres especiales"""
    if text is None:
        return ""
    # Remover CDATA
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    # Remover etiquetas HTML
    text = re.sub(r'<[^>]+>', '', text)
    # Decodificar entidades HTML
    text = unescape(text)
    # Limpiar espacios en blanco
    text = ' '.join(text.split())
    return text.strip()

def xml_to_csv(xml_file, csv_file):
    """
    Convierte un archivo XML de WordPress a CSV
    
    Args:
        xml_file: Ruta al archivo XML de entrada
        csv_file: Ruta al archivo CSV de salida
    """
    
    # Parsear el archivo XML
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    # Definir los namespaces usados en WordPress XML
    namespaces = {
        'content': 'http://purl.org/rss/1.0/modules/content/',
        'wp': 'http://wordpress.org/export/1.2/',
        'dc': 'http://purl.org/dc/elements/1.1/',
        'excerpt': 'http://wordpress.org/export/1.2/excerpt/'
    }
    
    # Abrir archivo CSV para escribir
    with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
        # Definir las columnas del CSV
        fieldnames = [
            'post_id',
            'title',
            'link',
            'pub_date',
            'creator',
            'content',
            'excerpt',
            'post_date',
            'post_date_gmt',
            'post_modified',
            'post_modified_gmt',
            'status',
            'post_type',
            'post_name',
            'categories',
            'event_start_date',
            'event_end_date',
            'event_timezone',
            'event_url'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Buscar todos los items (posts/eventos)
        items = root.findall('.//item')
        
        print(f"Procesando {len(items)} items...")
        
        for item in items:
            # Extraer información básica
            title = clean_text(item.find('title').text) if item.find('title') is not None else ""
            link = item.find('link').text if item.find('link') is not None else ""
            pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
            
            # Extraer creator
            creator_elem = item.find('dc:creator', namespaces)
            creator = clean_text(creator_elem.text) if creator_elem is not None else ""
            
            # Extraer contenido
            content_elem = item.find('content:encoded', namespaces)
            content = clean_text(content_elem.text) if content_elem is not None else ""
            
            # Extraer excerpt
            excerpt_elem = item.find('excerpt:encoded', namespaces)
            excerpt = clean_text(excerpt_elem.text) if excerpt_elem is not None else ""
            
            # Extraer campos de WordPress
            post_id = item.find('wp:post_id', namespaces)
            post_id = post_id.text if post_id is not None else ""
            
            post_date = item.find('wp:post_date', namespaces)
            post_date = clean_text(post_date.text) if post_date is not None else ""
            
            post_date_gmt = item.find('wp:post_date_gmt', namespaces)
            post_date_gmt = clean_text(post_date_gmt.text) if post_date_gmt is not None else ""
            
            post_modified = item.find('wp:post_modified', namespaces)
            post_modified = clean_text(post_modified.text) if post_modified is not None else ""
            
            post_modified_gmt = item.find('wp:post_modified_gmt', namespaces)
            post_modified_gmt = clean_text(post_modified_gmt.text) if post_modified_gmt is not None else ""
            
            status = item.find('wp:status', namespaces)
            status = status.text if status is not None else ""
            
            post_type = item.find('wp:post_type', namespaces)
            post_type = post_type.text if post_type is not None else ""
            
            post_name = item.find('wp:post_name', namespaces)
            post_name = clean_text(post_name.text) if post_name is not None else ""
            
            # Extraer categorías
            categories = []
            for category in item.findall('category'):
                cat_text = clean_text(category.text)
                if cat_text:
                    categories.append(cat_text)
            categories_str = "; ".join(categories)
            
            # Extraer información de eventos (si existe)
            event_start = ""
            event_end = ""
            event_timezone = ""
            event_url = ""
            
            for postmeta in item.findall('.//wp:postmeta', namespaces):
                meta_key = postmeta.find('wp:meta_key', namespaces)
                meta_value = postmeta.find('wp:meta_value', namespaces)
                
                if meta_key is not None and meta_value is not None:
                    key = clean_text(meta_key.text)
                    value = clean_text(meta_value.text)
                    
                    if key == '_EventStartDate':
                        event_start = value
                    elif key == '_EventEndDate':
                        event_end = value
                    elif key == '_EventTimezone':
                        event_timezone = value
                    elif key == '_EventURL':
                        event_url = value
            
            # Escribir la fila en el CSV
            writer.writerow({
                'post_id': post_id,
                'title': title,
                'link': link,
                'pub_date': pub_date,
                'creator': creator,
                'content': content[:500] + '...' if len(content) > 500 else content,  # Limitar contenido
                'excerpt': excerpt,
                'post_date': post_date,
                'post_date_gmt': post_date_gmt,
                'post_modified': post_modified,
                'post_modified_gmt': post_modified_gmt,
                'status': status,
                'post_type': post_type,
                'post_name': post_name,
                'categories': categories_str,
                'event_start_date': event_start,
                'event_end_date': event_end,
                'event_timezone': event_timezone,
                'event_url': event_url
            })
    
    print(f"✓ Conversión completada: {csv_file}")
    print(f"✓ Total de items procesados: {len(items)}")

if __name__ == "__main__":
    # Ejemplo de uso
    xml_input = "aocconnect.WordPress.2025-10-08.xml"  # Cambia esto por la ruta de tu archivo XML
    csv_output = "output.csv"  # Cambia esto por la ruta de salida deseada
    
    try:
        xml_to_csv(xml_input, csv_output)
    except FileNotFoundError:
        print(f"❌ Error: No se encontró el archivo '{xml_input}'")
        print("\nUso:")
        print(f"  1. Guarda tu archivo XML como '{xml_input}'")
        print(f"  2. Ejecuta: python xml_to_csv.py")
        print(f"  3. El resultado estará en '{csv_output}'")
    except Exception as e:
        print(f"❌ Error al procesar el archivo: {str(e)}")

