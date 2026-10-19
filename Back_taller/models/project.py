from datetime import datetime
from bson import ObjectId

class Project:
    def __init__(self, video, audio=None, _id=None, created_at=None, updated_at=None):
        self._id = _id
        self.video = video
        self.audio = audio
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
    
    def to_dict(self):
        """Convertir a diccionario para MongoDB"""
        data = {
            'video': self.video,
            'audio': self.audio,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        if self._id:
            data['_id'] = self._id
        return data
    
    @classmethod
    def from_dict(cls, data):
        """Crear instancia desde diccionario de MongoDB"""
        return cls(
            _id=data.get('_id'),
            video=data.get('video'),
            audio=data.get('audio'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    @classmethod
    def find_by_id(cls, db, project_id):
        """Buscar proyecto por ID"""
        try:
            project_data = db.projects.find_one({'_id': ObjectId(project_id)})
            if project_data:
                return cls.from_dict(project_data)
        except:
            pass
        return None
    
    @classmethod
    def find_all(cls, db):
        """Obtener todos los proyectos"""
        projects_data = db.projects.find()
        return [cls.from_dict(data) for data in projects_data]
    
    def save(self, db):
        """Guardar proyecto en la base de datos"""
        if self._id:
            # Actualizar
            self.updated_at = datetime.now()
            result = db.projects.update_one(
                {'_id': self._id},
                {'$set': self.to_dict()}
            )
            return result.modified_count > 0
        else:
            # Crear nuevo
            self.created_at = datetime.now()
            self.updated_at = datetime.now()
            result = db.projects.insert_one(self.to_dict())
            self._id = result.inserted_id
            return True
    
    def delete(self, db):
        """Eliminar proyecto de la base de datos"""
        if self._id:
            result = db.projects.delete_one({'_id': self._id})
            return result.deleted_count > 0
        return False
    
    def to_response_dict(self):
        """Convertir a diccionario para respuesta"""
        return {
            '_id': str(self._id),
            'video': self.video,
            'audio': self.audio,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        } 