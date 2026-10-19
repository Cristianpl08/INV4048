import cv2
import os

def extract_frames(video_path, output_folder):
    # Verificar si la carpeta de salida existe, si no, crearla
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Capturar el video
    cap = cv2.VideoCapture(video_path)
    
    # Obtener FPS del video
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    print(f"FPS del video: {fps}")
    
    frame_count = 0
    second_count = 0
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break  # Salir del bucle si no hay más frames
        
        # Solo guardar un frame por segundo (cuando frame_count es múltiplo de fps)
        if frame_count % fps == 0:
            frame_filename = os.path.join(output_folder, f"frame_second_{second_count:04d}.jpg")
            cv2.imwrite(frame_filename, frame)
            print(f"Guardando frame del segundo {second_count}")
            second_count += 1
        
        frame_count += 1
    
    cap.release()
    print(f"Extracción completada: {second_count} frames guardados en {output_folder} (uno por segundo)")

# Ejemplo de uso
video_path = "Z3XarHZ3HpY_10_17.avi"  # Cambia esto por la ruta de tu video
output_folder = "allframes"  # Carpeta donde se guardarán los frames
extract_frames(video_path, output_folder)
