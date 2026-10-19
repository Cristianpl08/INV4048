const mongoose = require('mongoose');

// Esquema de Segmento
const segmentSchema = new mongoose.Schema({
  startTime: {
    type: Number,
    required: [true, 'Start time es requerido'],
    default: 0
  },
  endTime: {
    type: Number,
    required: [true, 'End time es requerido'],
    default: 0
  },
  duration: {
    type: Number,
    default: 0
  },
  views: {
    type: Number,
    default: 0
  },
  likes: {
    type: Number,
    default: 0
  },
  prosody: {
    type: String,
    trim: true
  },
  prosody2: {
    type: String,
    trim: true
  },
  description: {
    type: String,
    trim: true
  },
  descriptions_prosody: {
    type: [Object],
    default: []
  },
  projectid: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'Project',
    required: [true, 'Project ID es requerido']
  }
}, {
  timestamps: true, // Agrega createdAt y updatedAt automáticamente
  toJSON: { virtuals: true },
  toObject: { virtuals: true }
});

// Middleware pre-save para recalcular duración
segmentSchema.pre('save', function(next) {
  this.duration = this.endTime - this.startTime;
  console.log('💾 Guardando segmento:', {
    _id: this._id,
    startTime: this.startTime,
    endTime: this.endTime,
    duration: this.duration,
    projectid: this.projectid,
    isNew: this.isNew
  });
  next();
});

// Método para convertir a diccionario de respuesta
segmentSchema.methods.toResponseDict = function() {
  return {
    _id: this._id.toString(),
    start_time: this.startTime,
    end_time: this.endTime,
    duration: this.duration,
    views: this.views,
    likes: this.likes,
    prosody: this.prosody,
    prosody2: this.prosody2,
    description: this.description,
    descriptions_prosody: this.descriptions_prosody,
    project_id: this.projectid.toString(),
    created_at: this.createdAt ? this.createdAt.toISOString() : new Date().toISOString(),
    updated_at: this.updatedAt ? this.updatedAt.toISOString() : new Date().toISOString()
  };
};

// Método estático para buscar por ID
segmentSchema.statics.findById = function(segmentId) {
  try {
    return this.findOne({ _id: segmentId });
  } catch (error) {
    console.error('❌ Error al buscar segmento por ID:', error);
    return null;
  }
};

// Método estático para buscar por proyecto
segmentSchema.statics.findByProject = function(projectId) {
  try {
    // Validar que projectId sea válido
    if (!projectId) {
      console.log('❌ projectId es null o vacío');
      return [];
    }
    
    console.log(`🔍 Buscando segmentos para proyecto: ${projectId}`);
    return this.find({ projectid: projectId }).sort({ startTime: 1 });
  } catch (error) {
    console.error(`❌ Error al buscar segmentos por proyecto ${projectId}:`, error);
    return [];
  }
};

// Método estático para obtener todos los segmentos
segmentSchema.statics.findAll = function() {
  return this.find().sort({ createdAt: -1 });
};

// Método para guardar segmento
segmentSchema.methods.saveSegment = function() {
  return this.save();
};

// Método para eliminar segmento
segmentSchema.methods.deleteSegment = function() {
  return this.deleteOne();
};

// Método para incrementar vistas
segmentSchema.methods.incrementViews = function() {
  this.views += 1;
  return this.save();
};

// Método estático para incrementar vistas por ID
segmentSchema.statics.incrementViewsById = function(segmentId) {
  return this.findByIdAndUpdate(
    segmentId,
    { $inc: { views: 1 } },
    { new: true }
  );
};

// Método para incrementar likes
segmentSchema.methods.incrementLikes = function() {
  this.likes += 1;
  return this.save();
};

// Método estático para incrementar likes por ID
segmentSchema.statics.incrementLikesById = function(segmentId) {
  return this.findByIdAndUpdate(
    segmentId,
    { $inc: { likes: 1 } },
    { new: true }
  );
};

// Método para actualizar descriptions_prosody
segmentSchema.methods.updateDescriptionsProsody = function(descriptionsProsody) {
  this.descriptions_prosody = descriptionsProsody;
  return this.save();
};

// Método estático para actualizar descriptions_prosody por ID
segmentSchema.statics.updateDescriptionsProsodyById = function(segmentId, descriptionsProsody) {
  return this.findByIdAndUpdate(
    segmentId,
    { descriptions_prosody: descriptionsProsody },
    { new: true }
  );
};

// Middleware post-save para logging
segmentSchema.post('save', function(doc) {
  console.log('✅ Segmento guardado exitosamente:', {
    _id: doc._id,
    startTime: doc.startTime,
    endTime: doc.endTime,
    duration: doc.duration,
    projectid: doc.projectid
  });
});

// Middleware pre-remove para logging
segmentSchema.pre('deleteOne', function(next) {
  console.log('🗑️ Eliminando segmento:', {
    _id: this._id,
    startTime: this.startTime,
    endTime: this.endTime,
    projectid: this.projectid
  });
  next();
});

// Middleware post-remove para logging
segmentSchema.post('deleteOne', function(doc) {
  console.log('✅ Segmento eliminado exitosamente:', {
    _id: doc._id,
    startTime: doc.startTime,
    endTime: doc.endTime
  });
});

// Índices para mejorar rendimiento
segmentSchema.index({ projectid: 1 });
segmentSchema.index({ startTime: 1 });
segmentSchema.index({ createdAt: -1 });

// Crear y exportar el modelo
const Segment = mongoose.model('Segment', segmentSchema);

module.exports = Segment; 