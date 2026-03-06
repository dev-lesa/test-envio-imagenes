import csv
import base64
import requests
import mimetypes
import sys
import os
import json
from urllib.parse import urlparse

# CONFIGURA AQUÍ tu endpoint
API_URL = "http://localhost:11434/api/generate"  # <- PON ACA tu URL
HEADERS = {
    "Content-Type": "application/json",
    # "Authorization": "Bearer TU_TOKEN_AQUI",
}

# Opcional: si tu API espera el prefijo data:image/xxx;base64, pon True
INCLUIR_PREFIJO_DATAURI = False

CSV_PATH = r"C:\Users\Luis\Downloads\imagenes.csv"  # archivo con columna image_url
OUTPUT_DIR = r"C:\Users\Luis\Downloads\images_qwen3-5"

PROMPT = PROMPT = """Analiza la imagen de forma estrictamente lógica.

PASO 1: VALIDACIÓN
Determina si la imagen es un comprobante de transferencia, depósito bancario o factura (POS como Kirios/KinetPos) VÁLIDO Y COMPLETO.
La imagen es INVÁLIDA si es: publicidad, un tutorial, capturas de pantalla muy recortadas/incompletas, o documentos de otro tipo (por ejemplo, "Comprobante de Retención").

PASO 2: RESPUESTA JSON
DEBES devolver ÚNICAMENTE texto en formato JSON. LA ESTRUCTURA DEBE ESTAR COMPLETA SIEMPRE, no puedes omitir ninguna clave.

CASO A - SI LA IMAGEN ES INVÁLIDA:
No intentes extraer ningún dato. Ignora todo el texto de la imagen y devuelve EXACTAMENTE este JSON literal:
{
  "banco_origen": null,
  "banco_destino": null,
  "fecha": null,
  "monto": null,
  "costo_transaccion": null,
  "id_comprobante": null,
  "remitente": {
    "nombre": null,
    "cuenta": null
  },
  "destinatario": {
    "nombre": null,
    "cuenta": null
  },
  "motivo": null,
  "es_valido": false
}

CASO B - SI LA IMAGEN ES VÁLIDA:
Extrae los datos y devuelve LA MISMA estructura JSON, reemplazando los valores nulos con los datos extraídos y cambiando "es_valido" a true.
Reglas de extracción para documentos válidos:
1. Servicios corresponsales ('Mi Vecino', 'Servipagos', etc.): trátalos como 'banco_origen' o 'banco_destino'.
2. Facturas: pon el emisor en "banco_origen" o "remitente.nombre".
3. Datos faltantes: Si un dato no existe, usa la palabra null (sin comillas). NUNCA inventes ni dupliques datos.
4. Montos: Solo números decimales (ej. 12.50). Si no hay, pon 0.0.
5. Fechas: Formato ISO (YYYY-MM-DD). Si no hay, pon null.
6. Depósitos en efectivo: Si es un depósito y menciona efectivo, el remitente NO tiene cuenta de origen. "remitente.cuenta" y "banco_origen" DEBEN ser null.

REGLA ESTRICTA FINAL: No agregues ningún saludo, conclusión ni bloques de código markdown (como ```json o ```). Devuelve SOLO el texto plano del JSON."""

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
        b64 = base64.b64encode(r.content).decode("ascii")
        mime = guess_mime(image_url, r.content)
        if INCLUIR_PREFIJO_DATAURI:
            img_field = f"data:{mime};base64,{b64}"
        else:
            img_field = b64

        payload = {
            "model": "qwen3.5:4b",
            "prompt": PROMPT,
            "think": False,
            "stream": False,
            "images": [img_field],
            "options": {
                "temperature": 0.0  
            }
        }

        resp = requests.post(API_URL, json=payload, headers=HEADERS, timeout=1400)
        print(f"[POST] {image_url} -> {resp.status_code}")
        
        # Procesar la respuesta para que quede como un JSON limpio
        ollama_data = resp.json()
        ia_texto = ollama_data.get("response", "")
        
        # Limpiar posibles bloques markdown (```json ... ```)
        ia_texto = ia_texto.strip("```json").strip("```").strip()
        
        # Convertir el texto de la IA a un diccionario real de Python
        try:
            datos_json = json.loads(ia_texto)
        except json.JSONDecodeError:
            print(f"[ERROR JSON] La IA devolvió texto mal formateado para {image_url}")
            # Si falla, guardamos el texto crudo para que puedas revisarlo
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
