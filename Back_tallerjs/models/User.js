const mongoose = require('mongoose');

// Esquema de Usuario
const userSchema = new mongoose.Schema({
  username: {
    type: String,
    required: [true, 'Username es requerido'],
    unique: true,
    trim: true,
    minlength: [3, 'Username debe tener al menos 3 caracteres'],
    maxlength: [50, 'Username no puede exceder 50 caracteres']
  },
  email: {
    type: String,
    required: [true, 'Email es requerido'],
    unique: true,
    trim: true,
    lowercase: true,
    match: [/^\w+([.-]?\w+)*@\w+([.-]?\w+)*(\.\w{2,3})+$/, 'Email inválido']
  },
  password: {
    type: String,
    required: [true, 'Password es requerido'],
    minlength: [6, 'Password debe tener al menos 6 caracteres']
  }
}, {
  timestamps: true, // Agrega createdAt y updatedAt automáticamente
  toJSON: { virtuals: true },
  toObject: { virtuals: true }
});

// Método para convertir a diccionario de respuesta (sin password)
userSchema.methods.toResponseDict = function() {
  return {
    _id: this._id.toString(),
    username: this.username,
    email: this.email,
    created_at: this.createdAt ? this.createdAt.toISOString() : new Date().toISOString(),
    updated_at: this.updatedAt ? this.updatedAt.toISOString() : new Date().toISOString()
  };
};

// Método estático para buscar por email
userSchema.statics.findByEmail = function(email) {
  console.log(`🔍 Ejecutando consulta: User.findOne({email: "${email}"})`);
  return this.findOne({ email: email });
};

// Método estático para buscar por username
userSchema.statics.findByUsername = function(username) {
  return this.findOne({ username: username });
};

// Método para guardar usuario
userSchema.methods.saveUser = function() {
  return this.save();
};

// Middleware pre-save para logging
userSchema.pre('save', function(next) {
  console.log('💾 Guardando usuario:', {
    _id: this._id,
    username: this.username,
    email: this.email,
    isNew: this.isNew
  });
  next();
});

// Middleware post-save para logging
userSchema.post('save', function(doc) {
  console.log('✅ Usuario guardado exitosamente:', {
    _id: doc._id,
    username: doc.username,
    email: doc.email
  });
});

// Índices para mejorar rendimiento
userSchema.index({ email: 1 });
userSchema.index({ username: 1 });

// Crear y exportar el modelo
const User = mongoose.model('User', userSchema);

module.exports = User; 