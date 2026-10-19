/**
 * Utilidades para trabajar con Cloudinary
 */

/**
 * Detecta si una URL es de Cloudinary
 * @param {string} url - URL a verificar
 * @returns {boolean} - true si es URL de Cloudinary
 */
export const isCloudinaryUrl = (url) => {
  return url && url.includes('cloudinary.com');
};

/**
 * Extrae información de una URL de Cloudinary
 * @param {string} url - URL de Cloudinary
 * @returns {object} - Información extraída
 */
export const parseCloudinaryUrl = (url) => {
  if (!isCloudinaryUrl(url)) return null;

  // Patrón para URLs de Cloudinary
  const pattern = /https:\/\/res\.cloudinary\.com\/([^\/]+)\/video\/upload\/([^\/]+)\/(.+)/;
  const match = url.match(pattern);

  if (match) {
    return {
      cloudName: match[1],
      transformations: match[2],
      publicId: match[3].replace(/\.[^/.]+$/, '') // Remover extensión
    };
  }

  return null;
};



/**
 * Genera URL para audio extraído del video
 * @param {string} videoUrl - URL del video de Cloudinary
 * @returns {string} - URL del audio
 */
export const generateAudioUrl = (videoUrl) => {
  if (!isCloudinaryUrl(videoUrl)) return videoUrl;

  const parsed = parseCloudinaryUrl(videoUrl);
  if (!parsed) return videoUrl;

  // Para Cloudinary, usar la misma URL del video sin transformaciones
  // WaveSurfer puede manejar videos directamente y extraer el audio
  return `https://res.cloudinary.com/${parsed.cloudName}/video/upload/${parsed.publicId}`;
};





/**
 * Procesa una URL de Cloudinary para uso en reproductor
 * @param {string} url - URL original
 * @returns {string} - URL procesada
 */
export const processCloudinaryUrl = (url) => {
  if (!isCloudinaryUrl(url)) return url;

  // Para Cloudinary, es mejor usar la URL original sin transformaciones
  // ya que las transformaciones pueden causar problemas de carga
  const parsed = parseCloudinaryUrl(url);
  if (!parsed) return url;

  // Para evitar problemas, usar la URL original sin transformaciones
  return `https://res.cloudinary.com/${parsed.cloudName}/video/upload/${parsed.publicId}`;
};





/**
 * Obtiene la URL original de Cloudinary sin transformaciones
 * @param {string} url - URL de Cloudinary
 * @returns {string} - URL original
 */
export const getOriginalCloudinaryUrl = (url) => {
  if (!isCloudinaryUrl(url)) return url;

  const parsed = parseCloudinaryUrl(url);
  if (!parsed) return url;

  // URL sin transformaciones
  return `https://res.cloudinary.com/${parsed.cloudName}/video/upload/${parsed.publicId}`;
}; 