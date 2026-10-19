from datetime import datetime
from bson import ObjectId

class Segment:
    def __init__(self, start_time, end_time, project_id, prosody=None, prosody2=None, 
                 description=None, descriptions_prosody=None, views=0, likes=0, 
                 _id=None, created_at=None, updated_at=None):
        self._id = _id
        self.start_time = start_time or 0
        self.end_time = end_time or 0
        self.duration = (self.end_time - self.start_time) if self.end_time and self.start_time else 0
        self.views = views or 0
        self.likes = likes or 0
        self.prosody = prosody
        self.prosody2 = prosody2
        self.description = description
        self.descriptions_prosody = descriptions_prosody or []
        self.project_id = project_id
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
    
    def to_dict(self):
        """Convertir a diccionario para MongoDB"""
        data = {
            'startTime': self.start_time,      # ← camelCase
            'endTime': self.end_time,          # ← camelCase
            'duration': self.duration,
            'views': self.views,
            'likes': self.likes,
            'prosody': self.prosody,
            'prosody2': self.prosody2,
            'description': self.description,
            'descriptions_prosody': self.descriptions_prosody,
            'projectid': ObjectId(self.project_id) if isinstance(self.project_id, str) else self.project_id,  # ← sin guión bajo
            'createdAt': self.created_at,      # ← camelCase
            'updatedAt': self.updated_at       # ← camelCase
        }
        if self._id:
            data['_id'] = self._id
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Crear instancia desde diccionario de MongoDB"""
        return cls(
            _id=data.get('_id'),
            start_time=data.get('startTime'),  # ← camelCase
            end_time=data.get('endTime'),      # ← camelCase
            project_id=data.get('projectid'),  # ← sin guión bajo
            prosody=data.get('prosody'),
            prosody2=data.get('prosody2'),
            description=data.get('description'),
            descriptions_prosody=data.get('descriptions_prosody', []),
            views=data.get('views', 0),
            likes=data.get('likes', 0),
            created_at=data.get('createdAt'),  # ← camelCase
            updated_at=data.get('updatedAt')   # ← camelCase
        )
    
    @classmethod
    def find_by_id(cls, db, segment_id):
        """Buscar segmento por ID"""
        try:
            segment_data = db.segments.find_one({'_id': ObjectId(segment_id)})
            if segment_data:
                return cls.from_dict(segment_data)
        except:
            pass
        return None
    
    @classmethod
    def find_by_project(cls, db, project_id):
        """Buscar segmentos por proyecto"""
        try:
            # Validar que project_id sea válido
            if not project_id:
                print(f'❌ project_id es None o vacío')
                return []
            
            # Convertir a ObjectId
            project_object_id = ObjectId(project_id)
            segments_data = db.segments.find({'projectid': project_object_id})  # ← usar 'projectid'
            segments = [cls.from_dict(data) for data in segments_data]
            print(f'✅ Encontrados {len(segments)} segmentos para proyecto {project_id}')
            return segments
        except Exception as e:
            print(f'❌ Error al buscar segmentos por proyecto {project_id}: {str(e)}')
            return []
    
    @classmethod
    def find_all(cls, db):
        """Obtener todos los segmentos"""
        segments_data = db.segments.find()
        return [cls.from_dict(data) for data in segments_data]
    
    def save(self, db):
        """Guardar segmento en la base de datos"""
        # Recalcular duración
        self.duration = self.end_time - self.start_time
        
        if self._id:
            # Actualizar
            self.updated_at = datetime.now()
            result = db.segments.update_one(
                {'_id': self._id},
                {'$set': self.to_dict()}
            )
            return result.modified_count > 0
        else:
            # Crear nuevo
            self.created_at = datetime.now()
            self.updated_at = datetime.now()
            result = db.segments.insert_one(self.to_dict())
            self._id = result.inserted_id
            return True
    
    def delete(self, db):
        """Eliminar segmento de la base de datos"""
        if self._id:
            result = db.segments.delete_one({'_id': self._id})
            return result.deleted_count > 0
        return False
    
    def increment_views(self, db):
        """Incrementar contador de vistas"""
        if self._id:
            result = db.segments.update_one(
                {'_id': self._id},
                {'$inc': {'views': 1}}
            )
            if result.modified_count > 0:
                self.views += 1
            return result.modified_count > 0
        return False
    
    def increment_likes(self, db):
        """Incrementar contador de likes"""
        if self._id:
            result = db.segments.update_one(
                {'_id': self._id},
                {'$inc': {'likes': 1}}
            )
            if result.modified_count > 0:
                self.likes += 1
            return result.modified_count > 0
        return False
    
    def to_response_dict(self):
        """Convertir a diccionario para respuesta"""
        return {
            '_id': str(self._id) if self._id else None,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration,
            'views': self.views,
            'likes': self.likes,
            'prosody': self.prosody,
            'prosody2': self.prosody2,
            'description': self.description,
            'descriptions_prosody': self.descriptions_prosody,
            'project_id': str(self.project_id) if self.project_id else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        } 