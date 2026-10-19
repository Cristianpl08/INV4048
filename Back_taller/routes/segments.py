from flask import Blueprint
from controllers.segment_controller import (
    get_segments, get_segment, get_segments_by_project,
    create_segment, update_segment, delete_segment,
    increment_views, increment_likes, update_descriptions_prosody
)

# Crear blueprint para segmentos
segments_bp = Blueprint('segments', __name__)

# Rutas de segmentos
@segments_bp.route('/', methods=['GET'])
def get_segments_route():
    """Obtener todos los segmentos"""
    return get_segments()

@segments_bp.route('/<segment_id>', methods=['GET'])
def get_segment_route(segment_id):
    """Obtener un segmento por ID"""
    return get_segment(segment_id)

@segments_bp.route('/project/<project_id>', methods=['GET'])
def get_segments_by_project_route(project_id):
    """Obtener segmentos por proyecto"""
    return get_segments_by_project(project_id)

@segments_bp.route('/', methods=['POST'])
def create_segment_route():
    """Crear un nuevo segmento"""
    return create_segment()

@segments_bp.route('/<segment_id>', methods=['PUT'])
def update_segment_route(segment_id):
    """Actualizar un segmento"""
    return update_segment(segment_id)

@segments_bp.route('/<segment_id>', methods=['DELETE'])
def delete_segment_route(segment_id):
    """Eliminar un segmento"""
    return delete_segment(segment_id)

@segments_bp.route('/<segment_id>/views', methods=['POST'])
def increment_views_route(segment_id):
    """Incrementar contador de vistas de un segmento"""
    return increment_views(segment_id)

@segments_bp.route('/<segment_id>/likes', methods=['POST'])
def increment_likes_route(segment_id):
    """Incrementar contador de likes de un segmento"""
    return increment_likes(segment_id)

@segments_bp.route('/<segment_id>/descriptions_prosody', methods=['POST'])
def update_descriptions_prosody_route(segment_id):
    """Actualizar/agregar campo de descriptions_prosody para un usuario en un segmento"""
    # El segment_id se puede usar para validar que coincida con el body, pero el controlador usa el del body
    return update_descriptions_prosody() 