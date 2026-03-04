# enviar_imagenes.py
import csv
import base64
import requests
import mimetypes
import sys
from urllib.parse import urlparse

# CONFIGURA AQUÍ tu endpoint
API_URL = "http://localhost:11434/api/generate"  # <- PON ACA tu URL
HEADERS = {
    "Content-Type": "application/json",
    # "Authorization": "Bearer TU_TOKEN_AQUI",
}

# Opcional: si tu API espera el prefijo data:image/xxx;base64, pon True
INCLUIR_PREFIJO_DATAURI = False

CSV_PATH = "C:/Users/Luis/Downloads/imagenes.csv"  # archivo con columna image_url

PROMPT = ("¿Es una captura de pantalla de un comprobante real? Responde SI si es el recibo "
          "de una transferencia, incluso si se ven botones o menús de la aplicación. "
          "Responde NO solo si es un tutorial, tiene instrucciones numeradas (1, 2, 3) o publicidad. "
          "Solo una palabra: SI o NO.")

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
        r = requests.get(image_url, timeout=30)
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
            "model": "qwen3-vl:4b",
            "prompt": PROMPT,
            "stream": False,
            "images": [img_field]
        }

        resp = requests.post(API_URL, json=payload, headers=HEADERS, timeout=60)
        print(f"[POST] {image_url} -> {resp.status_code}")
        return {"url": image_url, "status": resp.status_code, "response": resp.text}
    except Exception as e:
        print(f"[ERROR POST] {image_url} -> {e}")
        return {"url": image_url, "status": "post_error", "error": str(e)}

def main():
    results = []
    try:
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                image_url = row.get("image_url") or row.get("image") or list(row.values())[0]
                if not image_url:
                    continue
                res = procesar_y_enviar(image_url.strip())
                results.append(res)
    except FileNotFoundError:
        print("No se encontró", CSV_PATH)
        sys.exit(1)

    # Guardar resultados
    import json
    with open("resultados_enviar.json", "w", encoding="utf-8") as out:
        json.dump(results, out, ensure_ascii=False, indent=2)
    print("Hecho. Resultados en resultados_enviar.json")

if __name__ == "__main__":
    main()