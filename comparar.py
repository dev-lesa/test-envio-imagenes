import os
import json
import csv

# 1. Coloca aquí las rutas de tus 3 carpetas
carpeta_ia1 = r"C:\Users\Luis\Downloads\images_llava"
carpeta_ia2 = r"C:\Users\Luis\Downloads\images_qwen3vl"
carpeta_ia3 = r"C:\Users\Luis\Downloads\images_qwen3-5"

# Nombre del archivo Excel/CSV que se va a generar
archivo_salida = 'comparacion_resultados.csv'

# Obtener los nombres de los archivos de la primera carpeta
archivos = sorted(os.listdir(carpeta_ia1))

# Crear y abrir el archivo CSV
with open(archivo_salida, mode='w', newline='', encoding='utf-8') as csv_file:
    writer = csv.writer(csv_file)
    
    # Escribir la primera fila con los títulos de las columnas
    writer.writerow(['Nombre del Archivo', 'Respuesta IA llava:7b', 'Respuesta IA qwen3-vl:4b-instruct', 'Respuesta IA qwen3.5:4b'])

    for archivo in archivos:
        # Asegurarnos de que solo lea archivos JSON
        if not archivo.endswith('.json'):
            continue
            
        fila = [archivo]
        
        # Extraer la información de ese archivo en las 3 carpetas
        for carpeta in [carpeta_ia1, carpeta_ia2, carpeta_ia3]:
            ruta_completa = os.path.join(carpeta, archivo)
            try:
                with open(ruta_completa, 'r', encoding='utf-8') as f:
                    contenido_json = json.load(f)
                    # Convertimos el JSON a texto formateado para que se vea bien en la celda
                    texto_json = json.dumps(contenido_json, indent=2, ensure_ascii=False)
                    fila.append(texto_json)
            except Exception as e:
                # Si falta el archivo en alguna carpeta o hay error, lo avisa en la celda
                fila.append(f"Error: {e}")
        
        # Escribir la fila en el CSV
        writer.writerow(fila)

print(f"¡Listo! Se ha creado el archivo: {archivo_salida}")