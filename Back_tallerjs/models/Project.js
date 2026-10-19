const mongoose = require('mongoose');

// Esquema de Proyecto
const projectSchema = new mongoose.Schema({
  video: {
    type: String,
    required: [true, 'Video es requerido'],
    trim: true
  },
  audio: {
    type: String,
    trim: true
  },
  audiofinal: {
    type: String,
    trim: true
  }
}, {
  timestamps: true, // Agrega createdAt y updatedAt automáticamente
  toJSON: { virtuals: true },
  toObject: { virtuals: true }
});

// Método para convertir a diccionario de respuesta
projectSchema.methods.toResponseDict = function() {
  return {
    _id: this._id.toString(),
    video: this.video,
    audio: this.audio,
    audiofinal: this.audiofinal,
    created_at: this.createdAt ? this.createdAt.toISOString() : new Date().toISOString(),
    updated_at: this.updatedAt ? this.updatedAt.toISOString() : new Date().toISOString()
  };
};

// Método estático para buscar por ID
projectSchema.statics.findById = function(projectId) {
  try {
    return this.findOne({ _id: projectId });
  } catch (error) {
    console.error('❌ Error al buscar proyecto por ID:', error);
    return null;
  }
};

// Método estático para obtener todos los proyectos
projectSchema.statics.findAll = function() {
  return this.find().sort({ createdAt: -1 });
};

// Método para guardar proyecto
projectSchema.methods.saveProject = function() {
  return this.save();
};

// Método para eliminar proyecto
projectSchema.methods.deleteProject = function() {
  return this.deleteOne();
};

// Middleware pre-save para logging
projectSchema.pre('save', function(next) {
  console.log('💾 Guardando proyecto:', {
    _id: this._id,
    video: this.video,
    audio: this.audio,
    audiofinal: this.audiofinal,
    isNew: this.isNew
  });
  next();
});

// Middleware post-save para logging
projectSchema.post('save', function(doc) {
  console.log('✅ Proyecto guardado exitosamente:', {
    _id: doc._id,
    video: doc.video,
    audio: doc.audio,
    audiofinal: doc.audiofinal
  });
});

// Middleware pre-remove para logging
projectSchema.pre('deleteOne', function(next) {
  console.log('🗑️ Eliminando proyecto:', {
    _id: this._id,
    video: this.video
  });
  next();
});

// Middleware post-remove para logging
projectSchema.post('deleteOne', function(doc) {
  console.log('✅ Proyecto eliminado exitosamente:', {
    _id: doc._id,
    video: doc.video
  });
});

// Índices para mejorar rendimiento
projectSchema.index({ createdAt: -1 });

// Crear y exportar el modelo
const Project = mongoose.model('Project', projectSchema);

module.exports = Project; 