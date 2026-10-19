from datetime import datetime
from bson import ObjectId

class User:
    def __init__(self, username, email, password, _id=None, created_at=None, updated_at=None):
        self._id = _id
        self.username = username
        self.email = email
        self.password = password
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
    
    def to_dict(self):
        """Convertir a diccionario para MongoDB"""
        data = {
            'username': self.username,
            'email': self.email,
            'password': self.password,
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
            username=data.get('username'),
            email=data.get('email'),
            password=data.get('password'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    @classmethod
    def find_by_email(cls, db, email):
        """Buscar usuario por email"""
        print(f'🔍 Ejecutando consulta: db.users.find_one({{"email": "{email}"}})')
        user_data = db.users.find_one({'email': email})
        print(f'📊 Resultado de la consulta: {user_data}')
        if user_data:
            return cls.from_dict(user_data)
        return None
    
    @classmethod
    def find_by_username(cls, db, username):
        """Buscar usuario por username"""
        user_data = db.users.find_one({'username': username})
        if user_data:
            return cls.from_dict(user_data)
        return None
    
    def save(self, db):
        """Guardar usuario en la base de datos"""
        if self._id:
            # Actualizar
            self.updated_at = datetime.now()
            result = db.users.update_one(
                {'_id': self._id},
                {'$set': self.to_dict()}
            )
            return result.modified_count > 0
        else:
            # Crear nuevo
            self.created_at = datetime.now()
            self.updated_at = datetime.now()
            result = db.users.insert_one(self.to_dict())
            self._id = result.inserted_id
            return True
    
    def to_response_dict(self):
        """Convertir a diccionario para respuesta (sin password)"""
        return {
            '_id': str(self._id),
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        } 