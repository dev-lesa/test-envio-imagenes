#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import base64
import requests
import mimetypes
import sys
import os
import json
import re
import time
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# CONFIGURA AQUÍ tu endpoint
API_URL = "http://localhost:11434/api/generate"

INCLUIR_PREFIJO_DATAURI = False

CSV_PATH = r"C:\Users\Luis\Downloads\image_urls.csv"
OUTPUT_DIR = r"C:\Users\Luis\Downloads\images"

PROMPT = """Analiza la imagen. Si NO es un comprobante real de transferencia, depósito bancario o factura válida (ej. es publicidad, un tutorial o instrucciones), devuelve la estructura JSON con todos los valores como null, excepto "es_valido" que debe ser false.

Si SÍ es un documento válido (transferencia, depósito o factura de sistema POS como Kirios/KinetPos), extrae los datos y devuelve ÚNICAMENTE la siguiente estructura JSON exacta, reemplazando los valores. 

Reglas estrictas:
1. Formato: No agregues ningún texto introductorio, conclusiones, ni bloques markdown (```json). Devuelve SOLO el texto del JSON.
2. Facturas: Si es una factura o recibo de caja, pon el emisor en "banco_origen" o en el remitente, y adapta los datos que existan.
3. Datos faltantes: Si algún dato no aparece en la imagen, usa null sin comillas.
4. Montos: Solo números con punto. Si no hay, pon 0.00.
5. Fechas: La fecha debe estar en formato ISO (YYYY-MM-DD). Si no se puede determinar, pon null.

Estructura:
{
  "banco_origen": "nombre",
  "banco_destino": "nombre",
  "fecha": "fecha",
  "monto": 0.0,
  "costo_transaccion": 0.0,
  "id_comprobante": "numero",
  "remitente": {
    "nombre": "nombre",
    "cuenta": "cuenta"
  },
  "destinatario": {
    "nombre": "nombre",
    "cuenta": "cuenta"
  },
  "motivo": "motivo",
  "es_valido": true
}
"""

def crear_sesion_con_reintentos():
    """Crea una sesión con reintentos automáticos"""
    sesion = requests.Session()
    reintentos = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504]
    )
    adaptador = HTTPAdapter(max_retries=reintentos)
    sesion.mount('http://', adaptador)
    sesion.mount('https://', adaptador)
    return sesion

def descargar_imagen(image_url, sesion):
    """Descarga imagen"""
    try:
        respuesta = sesion.get(image_url, timeout=30, allow_redirects=True)
        respuesta.raise_for_status()
        return respuesta.content
    except Exception as e:
        print(f"[ERROR DOWN] {image_url} -> {e}")
        raise

def guess_mime(url):
    """Adivina el MIME type"""
    path = urlparse(url).path
    mime, _ = mimetypes.guess_type(path)
    return mime if mime else "application/octet-stream"

def limpiar_respuesta_json(texto):
    """Extrae JSON de la respuesta"""
    if not texto or not texto.strip():
        return None
    
    # Eliminar bloques <think>
    texto = re.sub(r'<think>.*?</think>', '', texto, flags=re.DOTALL)
    
    # Eliminar bloques ```json
    texto = re.sub(r'```json\s*(.*?)\s*```', r'\1', texto, flags=re.DOTALL)
    texto = re.sub(r'```\s*(.*?)\s*```', r'\1', texto, flags=re.DOTALL)
    
    # Extraer JSON
    match = re.search(r'\{.*\}', texto, flags=re.DOTALL)
    
    if match:
        json_str = match.group(0).strip()
        return json_str
    
    return None

def procesar_y_enviar(image_url, sesion):
    """Procesa imagen y envía a la API"""
    try:
        # Descargar imagen
        contenido_imagen = descargar_imagen(image_url, sesion)
        
        # Codificar a base64
        b64 = base64.b64encode(contenido_imagen).decode("ascii")
        
        mime = guess_mime(image_url)
        
        if INCLUIR_PREFIJO_DATAURI:
            img_field = f"data:{mime};base64,{b64}"
        else:
            img_field = b64
        
        payload = {
            "model": "qwen3-vl:4b",
            "prompt": PROMPT,
            "stream": False,
            "images": [img_field],
            "options": {
                "temperature": 0.0,
                "num_ctx": 8192,
                "num_predict": 8192
            }
        }
        
        print(f"[POST] {image_url} -> enviando...")
        
        # Enviar sin HEADERS
        resp = sesion.post(API_URL, json=payload, timeout=300)
        print(f"[POST] {image_url} -> {resp.status_code}")
        
        if resp.status_code != 200:
            return {
                "url": image_url,
                "status": resp.status_code,
                "error": f"HTTP {resp.status_code}",
                "resultado_ia_error": resp.text[:200]
            }
        
        # Procesar respuesta
        try:
            ollama_data = resp.json()
        except json.JSONDecodeError as e:
            print(f"[ERROR RESPONSE] No se pudo parsear respuesta JSON: {e}")
            return {
                "url": image_url,
                "status": resp.status_code,
                "error": "Response JSON decode error",
                "resultado_ia_error": resp.text[:200]
            }
        
        ia_texto = ollama_data.get("response", "")
        
        if ia_texto:
            print(f"[DEBUG] Primeros 200 chars: {ia_texto[:200]}")
        else:
            print(f"[DEBUG] Respuesta vacía")
        
        # Limpiar y extraer JSON
        json_str = limpiar_respuesta_json(ia_texto)
        
        if not json_str:
            print(f"[ERROR JSON] No se encontró JSON para {image_url}")
            print(f"[DEBUG] Respuesta: {ia_texto}")
            return {
                "url": image_url,
                "status": resp.status_code,
                "error": "No JSON found in response",
                "resultado_ia_error": ia_texto[:500]
            }
        
        # Parsear JSON
        try:
            datos_json = json.loads(json_str)
            print(f"[SUCCESS] JSON parseado correctamente")
            return {"url": image_url, "status": resp.status_code, "resultado_ia": datos_json}
        
        except json.JSONDecodeError as e:
            print(f"[ERROR JSON] JSON malformado: {e}")
            print(f"[DEBUG] JSON string: {json_str[:500]}")
            return {
                "url": image_url,
                "status": resp.status_code,
                "error": f"JSON decode error: {str(e)}",
                "resultado_ia_error": json_str[:500]
            }
    
    except Exception as e:
        print(f"[ERROR POST] {image_url} -> {type(e).__name__}: {e}")
        return {
            "url": image_url,
            "status": "error",
            "error": str(e)
        }

def main():
    """Procesa todas las imágenes del CSV"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Crear sesión con reintentos
    sesion = crear_sesion_con_reintentos()
    
    try:
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for index, row in enumerate(reader, start=1):
                image_url = row.get("image_url") or row.get("image") or list(row.values())[0]
                
                if not image_url:
                    continue
                
                image_url = image_url.strip()
                print(f"\n{'='*60}")
                print(f"[{index}] Procesando: {image_url}")
                print(f"{'='*60}")
                
                # Procesar imagen
                res = procesar_y_enviar(image_url, sesion)
                
                # Guardar resultado
                filename = f"resultado_{index}.json"
                filepath = os.path.join(OUTPUT_DIR, filename)
                
                with open(filepath, "w", encoding="utf-8") as out:
                    json.dump(res, out, ensure_ascii=False, indent=2)
                
                print(f"[GUARDADO] {filepath}")
                
                # Pequeña pausa entre requests
                time.sleep(0.5)
    
    except FileNotFoundError:
        print(f"Error: No se encontró {CSV_PATH}")
        sys.exit(1)
    finally:
        sesion.close()
    
    print(f"\n✓ Todos los resultados guardados en {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
