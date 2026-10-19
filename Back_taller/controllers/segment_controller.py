from flask import request, jsonify
from models.segment import Segment
from models.project import Project
from config.database import get_db

def get_segments():
    """Obtener todos los segmentos"""
    try:
        print('📹 Obteniendo todos los segmentos')
        
        # Obtener base de datos
        db = get_db()
        
        # Obtener todos los segmentos
        segments = Segment.find_all(db)
        
        print(f'✅ Segmentos encontrados: {len(segments)}')
        
        # Convertir a formato de respuesta
        segments_data = [segment.to_response_dict() for segment in segments]
        
        response = {
            'success': True,
            'message': 'Segmentos obtenidos exitosamente',
            'data': {
                'segments': segments_data,
                'count': len(segments_data)
            }
        }
        
        print('📤 Enviando respuesta exitosa:', response)
        return jsonify(response)
        
    except Exception as error:
        print('💥 Error al obtener segmentos:', str(error))
        return jsonify({
            'success': False,
            'message': 'Error al obtener segmentos'
        }), 500

def get_segment(segment_id):
    """Obtener un segmento por ID"""
    try:
        print(f'📹 Obteniendo segmento con ID: {segment_id}')
        
        # Obtener base de datos
        db = get_db()
        
        # Buscar segmento
        segment = Segment.find_by_id(db, segment_id)
        
        if not segment:
            print(f'❌ Segmento no encontrado: {segment_id}')
            return jsonify({
                'success': False,
                'message': 'Segmento no encontrado'
            }), 404
        
        print(f'✅ Segmento encontrado: {segment_id}')
        
        response = {
            'success': True,
            'message': 'Segmento obtenido exitosamente',
            'data': {
                'segment': segment.to_response_dict()
            }
        }
        
        print('📤 Enviando respuesta exitosa:', response)
        return jsonify(response)
        
    except Exception as error:
        print('💥 Error al obtener segmento:', str(error))
        return jsonify({
            'success': False,
            'message': 'Error al obtener segmento'
        }), 500

def get_segments_by_project(project_id):
    """Obtener segmentos por proyecto"""
    try:
        print(f'📹 Obteniendo segmentos del proyecto: {project_id}')
        print(f'📋 Tipo de project_id: {type(project_id)}')
        
        # Validar project_id
        if not project_id:
            print('❌ project_id es None o vacío')
            return jsonify({
                'success': False,
                'message': 'ID de proyecto requerido'
            }), 400
        
        # Obtener base de datos
        db = get_db()
        print(f'🗄️ Base de datos conectada: {db.name}')
        
        # Verificar que el proyecto existe
        print(f'🔍 Verificando existencia del proyecto: {project_id}')
        project = Project.find_by_id(db, project_id)
        if not project:
            print(f'❌ Proyecto no encontrado: {project_id}')
            return jsonify({
                'success': False,
                'message': 'Proyecto no encontrado'
            }), 404
        
        print(f'✅ Proyecto encontrado: {project_id}')
        
        # Obtener segmentos del proyecto
        print(f'🔍 Buscando segmentos para proyecto: {project_id}')
        segments = Segment.find_by_project(db, project_id)
        
        print(f'✅ Segmentos encontrados: {len(segments)}')
        
        # Convertir a formato de respuesta
        print('🔄 Convirtiendo segmentos a formato de respuesta...')
        segments_data = []
        for i, segment in enumerate(segments):
            try:
                segment_dict = segment.to_response_dict()
                segments_data.append(segment_dict)
                print(f'  ✅ Segmento {i+1} convertido: {segment_dict.get("_id", "sin_id")}')
            except Exception as e:
                print(f'  ❌ Error al convertir segmento {i+1}: {str(e)}')
        
        response = {
            'success': True,
            'message': 'Segmentos obtenidos exitosamente',
            'data': {
                'segments': segments_data,
                'count': len(segments_data),
                'project_id': project_id
            }
        }
        
        print('📤 Enviando respuesta exitosa:', response)
        return jsonify(response)
        
    except Exception as error:
        print('💥 Error al obtener segmentos del proyecto:', str(error))
        import traceback
        print('📋 Stack trace:', traceback.format_exc())
        return jsonify({
            'success': False,
            'message': 'Error al obtener segmentos del proyecto'
        }), 500

def create_segment():
    """Crear un nuevo segmento"""
    try:
        data = request.get_json()
        start_time = data.get('startTime')
        end_time = data.get('endTime')
        project_id = data.get('projectid')
        prosody = data.get('prosody')
        prosody2 = data.get('prosody2')
        description = data.get('description')
        descriptions_prosody = data.get('Descriptions_prosody', [])
        
        print('📹 Creando nuevo segmento')
        print('📋 Datos recibidos:', {
            'start_time': start_time,
            'end_time': end_time,
            'project_id': project_id,
            'prosody': prosody,
            'prosody2': prosody2,
            'description': description,
            'descriptions_prosody': descriptions_prosody
        })

        # Validar datos requeridos
        if start_time is None or end_time is None or not project_id:
            return jsonify({
                'success': False,
                'message': 'startTime, endTime y projectid son requeridos'
            }), 400

        # Validar que los tiempos sean válidos
        if start_time < 0 or end_time < 0:
            return jsonify({
                'success': False,
                'message': 'Los tiempos deben ser mayores o iguales a 0'
            }), 400

        if start_time >= end_time:
            return jsonify({
                'success': False,
                'message': 'El tiempo de inicio debe ser menor al tiempo de fin'
            }), 400

        # Obtener base de datos
        db = get_db()

        # Verificar que el proyecto existe
        project = Project.find_by_id(db, project_id)
        if not project:
            print(f'❌ Proyecto no encontrado: {project_id}')
            return jsonify({
                'success': False,
                'message': 'Proyecto no encontrado'
            }), 404

        # Crear nuevo segmento
        segment = Segment(
            start_time=start_time,
            end_time=end_time,
            project_id=project_id,
            prosody=prosody,
            prosody2=prosody2,
            description=description,
            descriptions_prosody=descriptions_prosody
        )
        
        print('💾 Guardando segmento en la base de datos...')
        segment.save(db)
        print('✅ Segmento guardado exitosamente:', {
            '_id': str(segment._id),
            'start_time': segment.start_time,
            'end_time': segment.end_time,
            'project_id': segment.project_id
        })

        # Respuesta exitosa
        response = {
            'success': True,
            'message': 'Segmento creado exitosamente',
            'data': {
                'segment': segment.to_response_dict()
            }
        }

        print('📤 Enviando respuesta exitosa:', response)
        return jsonify(response), 201

    except Exception as error:
        print('💥 Error al crear segmento:', str(error))
        return jsonify({
            'success': False,
            'message': 'Error al crear segmento'
        }), 500

def update_segment(segment_id):
    """Actualizar un segmento"""
    try:
        data = request.get_json()
        start_time = data.get('startTime')
        end_time = data.get('endTime')
        prosody = data.get('prosody')
        prosody2 = data.get('prosody2')
        description = data.get('description')
        descriptions_prosody = data.get('Descriptions_prosody')
        
        print(f'📹 Actualizando segmento con ID: {segment_id}')
        print('📋 Datos recibidos:', {
            'start_time': start_time,
            'end_time': end_time,
            'prosody': prosody,
            'prosody2': prosody2,
            'description': description,
            'descriptions_prosody': descriptions_prosody
        })

        # Obtener base de datos
        db = get_db()

        # Buscar segmento
        segment = Segment.find_by_id(db, segment_id)
        
        if not segment:
            print(f'❌ Segmento no encontrado: {segment_id}')
            return jsonify({
                'success': False,
                'message': 'Segmento no encontrado'
            }), 404

        # Actualizar campos si se proporcionan
        if start_time is not None:
            if start_time < 0:
                return jsonify({
                    'success': False,
                    'message': 'El tiempo de inicio debe ser mayor o igual a 0'
                }), 400
            segment.start_time = start_time

        if end_time is not None:
            if end_time < 0:
                return jsonify({
                    'success': False,
                    'message': 'El tiempo de fin debe ser mayor o igual a 0'
                }), 400
            segment.end_time = end_time

        # Validar que los tiempos sean válidos juntos
        if start_time is not None or end_time is not None:
            if segment.start_time >= segment.end_time:
                return jsonify({
                    'success': False,
                    'message': 'El tiempo de inicio debe ser menor al tiempo de fin'
                }), 400

        if prosody is not None:
            segment.prosody = prosody
        if prosody2 is not None:
            segment.prosody2 = prosody2
        if description is not None:
            segment.description = description
        if descriptions_prosody is not None:
            segment.descriptions_prosody = descriptions_prosody
        
        print('💾 Guardando cambios en la base de datos...')
        segment.save(db)
        print('✅ Segmento actualizado exitosamente:', {
            '_id': str(segment._id),
            'start_time': segment.start_time,
            'end_time': segment.end_time
        })

        # Respuesta exitosa
        response = {
            'success': True,
            'message': 'Segmento actualizado exitosamente',
            'data': {
                'segment': segment.to_response_dict()
            }
        }

        print('📤 Enviando respuesta exitosa:', response)
        return jsonify(response)

    except Exception as error:
        print('💥 Error al actualizar segmento:', str(error))
        return jsonify({
            'success': False,
            'message': 'Error al actualizar segmento'
        }), 500

def update_descriptions_prosody():
    """Actualizar/agregar campo de descriptions_prosody para un usuario en un segmento, guardando timestamp por campo"""
    try:
        data = request.get_json()
        segment_id = data.get('segmentId')
        user_id = data.get('userId')
        field_name = data.get('fieldName')
        field_value = data.get('fieldValue')
        timestamp = data.get('timestamp')

        if not all([segment_id, user_id, field_name, field_value, timestamp]):
            return jsonify({
                'success': False,
                'message': 'Faltan campos requeridos'
            }), 400

        db = get_db()
        segment = Segment.find_by_id(db, segment_id)
        if not segment:
            return jsonify({
                'success': False,
                'message': 'Segmento no encontrado'
            }), 404

        # Buscar si el usuario ya tiene entrada en descriptions_prosody
        updated = False
        for entry in segment.descriptions_prosody:
            if entry.get('user_id') == user_id:
                entry[field_name] = field_value
                # Guardar timestamp por campo
                if 'timestamps' not in entry:
                    entry['timestamps'] = {}
                entry['timestamps'][field_name] = timestamp
                updated = True
                break
        if not updated:
            # Crear nueva entrada para el usuario
            new_entry = {
                'user_id': user_id,
                field_name: field_value,
                'timestamps': {field_name: timestamp}
            }
            segment.descriptions_prosody.append(new_entry)

        segment.save(db)
        return jsonify({
            'success': True,
            'message': 'Campo actualizado exitosamente',
            'data': {'segment': segment.to_response_dict()}
        })
    except Exception as error:
        print('💥 Error en update_descriptions_prosody:', str(error))
        return jsonify({
            'success': False,
            'message': 'Error al actualizar descriptions_prosody'
        }), 500

def delete_segment(segment_id):
    """Eliminar un segmento"""
    try:
        print(f'📹 Eliminando segmento con ID: {segment_id}')
        
        # Obtener base de datos
        db = get_db()

        # Buscar segmento
        segment = Segment.find_by_id(db, segment_id)
        
        if not segment:
            print(f'❌ Segmento no encontrado: {segment_id}')
            return jsonify({
                'success': False,
                'message': 'Segmento no encontrado'
            }), 404

        # Eliminar segmento
        print('🗑️ Eliminando segmento de la base de datos...')
        segment.delete(db)
        print('✅ Segmento eliminado exitosamente:', segment_id)

        # Respuesta exitosa
        response = {
            'success': True,
            'message': 'Segmento eliminado exitosamente',
            'data': {
                'segment_id': segment_id
            }
        }

        print('📤 Enviando respuesta exitosa:', response)
        return jsonify(response)

    except Exception as error:
        print('💥 Error al eliminar segmento:', str(error))
        return jsonify({
            'success': False,
            'message': 'Error al eliminar segmento'
        }), 500

def increment_views(segment_id):
    """Incrementar contador de vistas de un segmento"""
    try:
        print(f'📹 Incrementando vistas del segmento: {segment_id}')
        
        # Obtener base de datos
        db = get_db()

        # Buscar segmento
        segment = Segment.find_by_id(db, segment_id)
        
        if not segment:
            print(f'❌ Segmento no encontrado: {segment_id}')
            return jsonify({
                'success': False,
                'message': 'Segmento no encontrado'
            }), 404

        # Incrementar vistas
        segment.increment_views(db)
        print(f'✅ Vistas incrementadas: {segment.views}')

        # Respuesta exitosa
        response = {
            'success': True,
            'message': 'Vistas incrementadas exitosamente',
            'data': {
                'segment_id': segment_id,
                'views': segment.views
            }
        }

        print('📤 Enviando respuesta exitosa:', response)
        return jsonify(response)

    except Exception as error:
        print('💥 Error al incrementar vistas:', str(error))
        return jsonify({
            'success': False,
            'message': 'Error al incrementar vistas'
        }), 500

def increment_likes(segment_id):
    """Incrementar contador de likes de un segmento"""
    try:
        print(f'📹 Incrementando likes del segmento: {segment_id}')
        
        # Obtener base de datos
        db = get_db()

        # Buscar segmento
        segment = Segment.find_by_id(db, segment_id)
        
        if not segment:
            print(f'❌ Segmento no encontrado: {segment_id}')
            return jsonify({
                'success': False,
                'message': 'Segmento no encontrado'
            }), 404

        # Incrementar likes
        segment.increment_likes(db)
        print(f'✅ Likes incrementados: {segment.likes}')

        # Respuesta exitosa
        response = {
            'success': True,
            'message': 'Likes incrementados exitosamente',
            'data': {
                'segment_id': segment_id,
                'likes': segment.likes
            }
        }

        print('📤 Enviando respuesta exitosa:', response)
        return jsonify(response)

    except Exception as error:
        print('💥 Error al incrementar likes:', str(error))
        return jsonify({
            'success': False,
            'message': 'Error al incrementar likes'
        }), 500 