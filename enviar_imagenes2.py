import csv
import base64
import requests
import mimetypes
import sys
import os
import json
from urllib.parse import urlparse
from PIL import Image
import io

# CONFIGURA AQUÍ tu endpoint
API_URL = "http://localhost:11434/api/generate" 
HEADERS = {
    "Content-Type": "application/json",
    # "Authorization": "Bearer TU_TOKEN_AQUI",
}

# Opcional: si tu API espera el prefijo data:image/xxx;base64, pon True
INCLUIR_PREFIJO_DATAURI = False

CSV_PATH = "/home/desarrollo/Descargas/image_urls.csv"  # archivo con columna image_url
OUTPUT_DIR = "/home/desarrollo/Descargas/fotos"

PROMPT = """Devuelve ÚNICAMENTE un JSON estricto. NO uses Markdown ni agregues explicaciones.

Analiza la imagen. Si NO es un comprobante real de transferencia (ej. es publicidad, un tutorial, o instrucciones), devuelve EXACTAMENTE esta estructura:
{"banco_origen": null, "banco_destino": null, "fecha": null, "monto": null, "costo_transaccion": null, "id_comprobante": null, "remitente": null, "destinatario": null, "motivo": null, "es_valido": false}

Si SÍ es un comprobante válido, extrae los datos y devuelve EXACTAMENTE esta estructura, reemplazando los valores:
{"banco_origen": "nombre del banco", "banco_destino": "nombre del banco", "fecha": "fecha", "monto": 0.0, "costo_transaccion": 0.0, "id_comprobante": "numero", "remitente": {"nombre": "nombre", "cuenta": "cuenta"}, "destinatario": {"nombre": "nombre", "cuenta": "cuenta"}, "motivo": "motivo", "es_valido": true}

Reglas adicionales:
1. Montos: Solo números con punto. Si no hay, pon 0.00.
2. Si falta cualquier dato en la imagen, usa null sin comillas.
3. TRANSFERENCIA INTERNA: Si solo se menciona un banco en la imagen, úsalo tanto en banco_origen como en banco_destino.
"""

def guess_mime(url, content=None):
    # Intenta adivinar mime por extensión, si no usar application/octet-stream
    path = urlparse(url).path
    mime, _ = mimetypes.guess_type(path)
    if mime:
        return mime
    # fallback simple
    return "application/octet-stream"

def procesar_y_enviar(image_url):
    try:
        r = requests.get(image_url, timeout=111)
        r.raise_for_status()
    except Exception as e:
        print(f"[ERROR DOWN] {image_url} -> {e}")
        return {"url": image_url, "status": "download_error", "error": str(e)}

    try:
        # 1. Abrir la imagen en memoria
        img = Image.open(io.BytesIO(r.content))
        
        # 2. Convertir a RGB (por si es un PNG transparente, para evitar errores al guardar como JPEG)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # 3. Redimensionar
        img.thumbnail((800, 800)) 
        
        # 4. Guardar la imagen comprimida de vuelta en memoria
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=80) # Calidad al 80% es suficiente para leer texto
        
        # 5. Codificar a Base64 la imagen ya reducida
        b64 = base64.b64encode(buffered.getvalue()).decode("ascii")

        mime = "image/jpeg" # Lo forzamos a jpeg porque lo acabamos de convertir
        if INCLUIR_PREFIJO_DATAURI:
            img_field = f"data:{mime};base64,{b64}"
        else:
            img_field = b64

        payload = {
            "model": "qwen3-vl:2b",
            "prompt": PROMPT,
            "stream": False,
            "images": [img_field],
            "options": {
                "temperature": 0.0,
                "num_ctx": 2048 # Limita el contexto de memoria de Ollama para que no se sature la RAM
            }
        }

        resp = requests.post(API_URL, json=payload, headers=HEADERS, timeout=1400)
        print(f"[POST] {image_url} -> {resp.status_code}")
        
        ollama_data = resp.json()
        ia_texto = ollama_data.get("response", "")
        
        ia_texto = ia_texto.strip("```json").strip("```").strip()
        
        try:
            datos_json = json.loads(ia_texto)
        except json.JSONDecodeError:
            print(f"[ERROR JSON] La IA devolvió texto mal formateado para {image_url}")
            return {"url": image_url, "status": resp.status_code, "resultado_ia_error": ia_texto}

        return {"url": image_url, "status": resp.status_code, "resultado_ia": datos_json}
        
    except Exception as e:
        print(f"[ERROR POST] {image_url} -> {e}")
        return {"url": image_url, "status": "post_error", "error": str(e)}

def main():
    # Asegurar que el directorio de salida exista
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    try:
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for index, row in enumerate(reader, start=1):
                image_url = row.get("image_url") or row.get("image") or list(row.values())[0]
                if not image_url:
                    continue
                
                # Procesar un solo link
                res = procesar_y_enviar(image_url.strip())
                
                # Generar nombre de archivo único por cada registro procesado
                filename = f"resultado_{index}.json"
                filepath = os.path.join(OUTPUT_DIR, filename)
                
                # Guardar el JSON individualmente
                with open(filepath, "w", encoding="utf-8") as out:
                    json.dump(res, out, ensure_ascii=False, indent=2)
                    
                print(f"[GUARDADO] {filepath}")

    except FileNotFoundError:
        print("No se encontró", CSV_PATH)
        sys.exit(1)

    print(f"Todos los resultados han sido guardados individualmente en {OUTPUT_DIR}")

if __name__ == "__main__":
    main()