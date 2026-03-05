#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCRIPT OPTIMIZADO PARA MÁXIMO RENDIMIENTO
Basado en el análisis del usuario: la coma ayuda
Intentamos optimizar opciones de Ollama para mejorar respuestas
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

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

API_URL = "http://localhost:11434/api/generate"
CSV_PATH = r"C:\Users\Luis\Downloads\image_urls.csv"
OUTPUT_DIR = r"C:\Users\Luis\Downloads\images"

# ✅ PROMPT CON COMA - PROBADO: 56.8% de éxito
PROMPT = """Analiza la imagen. Si NO es un comprobante real de transferencia, depósito bancario o factura válida (ej. es publicidad, un tutorial o instrucciones), devuelve la estructura JSON con todos los valores como null, excepto "es_valido" que debe ser false.

Si SÍ es un documento válido (transferencia, depósito o factura de sistema POS como Kirios/KinetPos), extrae los datos y devuelve ÚNICAMENTE la siguiente estructura JSON exacta, reemplazando los valores. 

Si intervienen servicios corresponsales (como 'Mi Vecino', 'Pichincha Mi Vecino', 'Servipagos'), trátalos como el 'banco_origen' o 'banco_destino' según corresponda la transacción. No sobrepienses la diferencia entre la papeleta y el recibo del sistema; unifica los datos que concuerden

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
  "es_valido": true,
}
"""

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def crear_sesion_con_reintentos():
    """Crea sesión HTTP con reintentos automáticos"""
    sesion = requests.Session()
    reintentos = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )
    adaptador = HTTPAdapter(max_retries=reintentos)
    sesion.mount('http://', adaptador)
    sesion.mount('https://', adaptador)
    return sesion

def descargar_imagen(image_url, sesion):
    """Descarga imagen del URL con User-Agent para evitar bloqueos"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        respuesta = sesion.get(
            image_url, 
            timeout=30, 
            allow_redirects=True,
            headers=headers
        )
        respuesta.raise_for_status()
        return respuesta.content
    except Exception as e:
        print(f"[ERROR DOWN] {image_url} -> {e}")
        raise

def guess_mime(url):
    """Adivina MIME type de la URL"""
    path = urlparse(url).path
    mime, _ = mimetypes.guess_type(path)
    return mime if mime else "application/octet-stream"

def limpiar_json_agresivamente(texto):
    """Extrae JSON del texto con múltiples intentos"""
    if not texto or not texto.strip():
        return None
    
    texto = texto.strip()
    
    # 1. Eliminar bloques <think>
    texto = re.sub(r'<think>.*?</think>', '', texto, flags=re.DOTALL)
    texto = texto.strip()
    
    # 2. Eliminar markdown JSON
    texto = re.sub(r'```json\s*(.*?)\s*```', r'\1', texto, flags=re.DOTALL)
    texto = re.sub(r'```\s*(.*?)\s*```', r'\1', texto, flags=re.DOTALL)
    texto = texto.strip()
    
    # 3. Buscar JSON: desde primer { hasta último }
    if '{' not in texto or '}' not in texto:
        return None
    
    idx_inicio = texto.find('{')
    idx_fin = texto.rfind('}')
    
    if idx_inicio == -1 or idx_fin == -1 or idx_inicio >= idx_fin:
        return None
    
    json_str = texto[idx_inicio:idx_fin + 1].strip()
    return json_str if json_str else None

def parsear_json_tolerante(json_str):
    """Intenta parsear JSON con recuperación de errores comunes"""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        
        # Intento 1: Remover comillas finales extras y comas extras
        json_cleaned = re.sub(r',\s*}', '}', json_str)
        json_cleaned = re.sub(r',\s*]', ']', json_cleaned)
        
        try:
            return json.loads(json_cleaned)
        except:
            pass
        
        # Intento 2: Normalizar null
        json_cleaned = re.sub(r':\s*null\b', ': null', json_str)
        
        try:
            return json.loads(json_cleaned)
        except:
            pass
        
        # Intento 3: Intentar con comillas simples convertidas a dobles
        json_cleaned = json_str.replace("'", '"')
        
        try:
            return json.loads(json_cleaned)
        except:
            pass
        
        return None

def procesar_y_enviar(image_url, sesion):
    """Procesa una imagen y envía a la API"""
    try:
        # Descargar imagen
        contenido_imagen = descargar_imagen(image_url, sesion)
        
        # Codificar a base64
        b64 = base64.b64encode(contenido_imagen).decode("ascii")
        mime = guess_mime(image_url)
        
        # PAYLOAD OPTIMIZADO para máximo rendimiento
        payload = {
            "model": "qwen3-vl:4b",
            "prompt": PROMPT,
            "stream": False,
            "images": [b64],
            "options": {
                "temperature": 0.1,      # Sin variación, respuestas deterministas
                "num_ctx": 32768,        # Contexto ampliado
                "num_predict": 8192,     # Más espacio para completar JSON
                "top_k": 40,             # Top-k sampling
                "top_p": 0.9,            # Nucleus sampling
                "repeat_penalty": 1.0    # Sin penalización a repetición
            }
        }
        
        # Enviar a API (SIN HEADERS de más)
        resp = sesion.post(API_URL, json=payload, timeout=600)  # Timeout más largo
        
        if resp.status_code != 200:
            return {
                "url": image_url,
                "status": resp.status_code,
                "error": f"HTTP {resp.status_code}"
            }
        
        # Procesar respuesta
        try:
            ollama_data = resp.json()
        except json.JSONDecodeError:
            return {
                "url": image_url,
                "status": "error",
                "error": "Response JSON decode error"
            }
        
        ia_texto = ollama_data.get("response", "")
        
        if not ia_texto or ia_texto.strip() == "":
            return {
                "url": image_url,
                "status": resp.status_code,
                "error": "Empty API response"
            }
        
        # Limpiar JSON
        json_str = limpiar_json_agresivamente(ia_texto)
        
        if not json_str:
            return {
                "url": image_url,
                "status": resp.status_code,
                "error": "No JSON found in response"
            }
        
        # Parsear JSON
        datos_json = parsear_json_tolerante(json_str)
        
        if datos_json is None:
            return {
                "url": image_url,
                "status": resp.status_code,
                "error": "JSON parse failed"
            }
        
        return {
            "url": image_url,
            "status": resp.status_code,
            "resultado_ia": datos_json
        }
    
    except Exception as e:
        return {
            "url": image_url,
            "status": "error",
            "error": str(e)
        }

def main():
    """Procesa todas las imágenes del CSV"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    sesion = crear_sesion_con_reintentos()
    
    contador_exito = 0
    contador_error = 0
    
    print("🚀 SCRIPT OPTIMIZADO - Máximo rendimiento")
    print("=" * 70)
    print(f"Analizando: {CSV_PATH}")
    print(f"Guardando en: {OUTPUT_DIR}")
    print("=" * 70 + "\n")
    
    try:
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for index, row in enumerate(reader, start=1):
                image_url = row.get("image_url") or row.get("image") or list(row.values())[0]
                
                if not image_url:
                    continue
                
                image_url = image_url.strip()
                
                print(f"[{index:2d}] {image_url[:65]:65s} ", end="", flush=True)
                
                # Procesar
                res = procesar_y_enviar(image_url, sesion)
                
                # Contar resultados
                if "resultado_ia" in res:
                    contador_exito += 1
                    print("✓")
                else:
                    contador_error += 1
                    error_msg = res.get('error', 'Desconocido')[:30]
                    print(f"✗ {error_msg}")
                
                # Guardar
                filename = f"resultado_{index}.json"
                filepath = os.path.join(OUTPUT_DIR, filename)
                
                with open(filepath, "w", encoding="utf-8") as out:
                    json.dump(res, out, ensure_ascii=False, indent=2)
                
                time.sleep(0.2)  # Pequeña pausa entre requests
    
    except FileNotFoundError:
        print(f"❌ Error: No se encontró {CSV_PATH}")
        sys.exit(1)
    finally:
        sesion.close()
    
    # Resumen final
    total = contador_exito + contador_error
    tasa = (contador_exito / total * 100) if total > 0 else 0
    
    print("\n" + "=" * 70)
    print("✓ PROCESAMIENTO COMPLETADO")
    print("=" * 70)
    print(f"✓ Éxito:    {contador_exito:2d} imágenes")
    print(f"✗ Errores:  {contador_error:2d} imágenes")
    print(f"  Total:    {total:2d} imágenes")
    print(f"  Tasa:     {tasa:5.1f}% de éxito")
    print("=" * 70)
    print(f"📁 Resultados: {OUTPUT_DIR}")
    print("=" * 70)

if __name__ == "__main__":
    main()
