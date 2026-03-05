#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script alternativo SIN HEADERS - Extracción JSON agresiva
Úsalo si prueba_mejorada_sin_headers.py sigue fallando
"""

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
    sesion = requests.Session()
    reintentos = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adaptador = HTTPAdapter(max_retries=reintentos)
    sesion.mount('http://', adaptador)
    sesion.mount('https://', adaptador)
    return sesion

def descargar_imagen(image_url, sesion):
    try:
        respuesta = sesion.get(image_url, timeout=30, allow_redirects=True)
        respuesta.raise_for_status()
        return respuesta.content
    except Exception as e:
        print(f"[ERROR DOWN] {image_url} -> {e}")
        raise

def guess_mime(url):
    path = urlparse(url).path
    mime, _ = mimetypes.guess_type(path)
    return mime if mime else "application/octet-stream"

def limpiar_agresivamente(texto):
    """
    Extracción AGRESIVA de JSON sin HEADERS
    """
    if not texto or not texto.strip():
        return None
    
    # 0. LIMPIEZA INICIAL
    texto = texto.strip()
    
    # Eliminar bloques <think>
    texto = re.sub(r'<think>.*?</think>', '', texto, flags=re.DOTALL)
    texto = texto.strip()
    
    # 1. INTENTAR EXTRACCIÓN ESTÁNDAR
    patron_json = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
    matches = list(re.finditer(patron_json, texto, flags=re.DOTALL))
    
    if matches:
        json_str = max(matches, key=lambda m: len(m.group(0))).group(0)
        json_str = json_str.strip()
        return json_str
    
    # 2. SI FALLA, INTENTAR CON REGEX MÁS FLEXIBLE
    match = re.search(r'\{[^{}]*\}', texto, flags=re.DOTALL)
    if match:
        return match.group(0).strip()
    
    # 3. SI AÚN FALLA, BUSCAR CAMPOS JSON CLAVE
    campos_clave = ['banco_origen', 'banco_destino', 'fecha', 'monto', 'es_valido']
    if any(campo in texto for campo in campos_clave):
        idx_inicio = texto.find('{')
        if idx_inicio != -1:
            resto = texto[idx_inicio:]
            idx_fin = resto.rfind('}')
            if idx_fin != -1:
                posible_json = resto[:idx_fin+1]
                return posible_json.strip()
    
    return None

def intentar_parsear_json(json_str):
    """
    Intenta parsear JSON con recuperación automática
    """
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"[JSON ERROR] {e}")
        
        # INTENTO 1: Remover comillas finales extras
        json_str_cleaned = re.sub(r',\s*}', '}', json_str)
        json_str_cleaned = re.sub(r',\s*]', ']', json_str_cleaned)
        
        try:
            return json.loads(json_str_cleaned)
        except:
            pass
        
        # INTENTO 2: Agregar comillas a null values si falta
        json_str_cleaned = re.sub(r':\s*null\s*([,}])', r': null\1', json_str)
        
        try:
            return json.loads(json_str_cleaned)
        except:
            pass
        
        # INTENTO 3: Convertir null a "null"
        json_str_cleaned = re.sub(r':\s*null\b', ': null', json_str)
        
        try:
            return json.loads(json_str_cleaned)
        except:
            return None

def procesar_y_enviar(image_url, sesion):
    """Procesa imagen y envía a API"""
    try:
        print(f"  → Descargando imagen...")
        contenido_imagen = descargar_imagen(image_url, sesion)
        
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
                "num_ctx": 16384,
                "num_predict": 4096
            }
        }
        
        print(f"  → Enviando a API...")
        # Enviar sin HEADERS
        resp = sesion.post(API_URL, json=payload, timeout=300)
        print(f"  → Respuesta: {resp.status_code}")
        
        if resp.status_code != 200:
            return {
                "url": image_url,
                "status": resp.status_code,
                "error": f"HTTP {resp.status_code}",
                "resultado_ia_error": resp.text[:300]
            }
        
        try:
            ollama_data = resp.json()
        except json.JSONDecodeError as e:
            return {
                "url": image_url,
                "status": resp.status_code,
                "error": "Response decode error",
                "resultado_ia_error": resp.text[:300]
            }
        
        ia_texto = ollama_data.get("response", "")
        
        if not ia_texto:
            print(f"  ⚠ Respuesta vacía de la API")
            return {
                "url": image_url,
                "status": resp.status_code,
                "error": "Empty API response",
                "resultado_ia_error": ""
            }
        
        print(f"  → Limpiando respuesta...")
        json_str = limpiar_agresivamente(ia_texto)
        
        if not json_str:
            print(f"  ✗ No se encontró JSON")
            return {
                "url": image_url,
                "status": resp.status_code,
                "error": "No JSON found",
                "resultado_ia_crudo": ia_texto[:500]
            }
        
        print(f"  → Parseando JSON...")
        datos_json = intentar_parsear_json(json_str)
        
        if datos_json is None:
            print(f"  ✗ JSON no parseable")
            return {
                "url": image_url,
                "status": resp.status_code,
                "error": "JSON parse failed",
                "resultado_ia_error": json_str[:500]
            }
        
        print(f"  ✓ Éxito")
        return {"url": image_url, "status": resp.status_code, "resultado_ia": datos_json}
    
    except Exception as e:
        print(f"  ✗ Error: {type(e).__name__}: {e}")
        return {
            "url": image_url,
            "status": "error",
            "error": str(e)
        }

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    sesion = crear_sesion_con_reintentos()
    
    try:
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for index, row in enumerate(reader, start=1):
                image_url = row.get("image_url") or row.get("image") or list(row.values())[0]
                
                if not image_url:
                    continue
                
                image_url = image_url.strip()
                print(f"\n{'='*70}")
                print(f"[{index}] {image_url[:60]}...")
                print(f"{'='*70}")
                
                res = procesar_y_enviar(image_url, sesion)
                
                filename = f"resultado_{index}.json"
                filepath = os.path.join(OUTPUT_DIR, filename)
                
                with open(filepath, "w", encoding="utf-8") as out:
                    json.dump(res, out, ensure_ascii=False, indent=2)
                
                print(f"  → Guardado: {filename}")
                time.sleep(0.5)
    
    except FileNotFoundError:
        print(f"Error: No se encontró {CSV_PATH}")
        sys.exit(1)
    finally:
        sesion.close()
    
    print(f"\n{'='*70}")
    print(f"✓ Completado. Resultados en: {OUTPUT_DIR}")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
