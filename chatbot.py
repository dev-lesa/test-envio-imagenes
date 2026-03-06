import json
import httpx

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
OLLAMA_URL  = "http://localhost:11434"
CHAT_MODEL  = "qwen3.5:2b"   # <- cambia aquí el modelo
MEMORY_SIZE = 5               # últimos N turnos (1 turno = user + assistant)
# ─────────────────────────────────────────────────────────────────────────────

# ─── BASE DE CONOCIMIENTO KinetPOS ───────────────────────────────────────────
KNOWLEDGE_BASE = {
    
    "¿Qué es KinetPOS?": "KinetPOS es un sistema web que puedes usar desde cualquier dispositivo. Está diseñado para ayudarte a gestionar tu empresa de forma integral, facilitando procesos como ventas, inventarios, compras, proveedores, colaboradores, reportes, formas de pago, clientes, facturación física y electrónica, entre otros. Todo desde una sola plataforma.",
    "¿Qué productos ofrece KinetPOS?": "KinetPOS ofrece tres soluciones principales:\n1. Facturador Electrónico: Un talonario digital que reemplaza la facturación física. Permite gestionar facturas de venta, proformas y creación de productos.\n2. Sistema de Gestión Empresarial: Administra inventarios, compras, ventas, cuentas por cobrar y pagar, reportes, colaboradores, marketing, gastos, proformas, lotes, notas de crédito y más, siempre cumpliendo con las normativas del SRI.\n3. Firmas Electrónicas: Permite generar firmas electrónicas personales o jurídicas con cédula o RUC, con vigencia desde 1 hasta 5 años.",
    "¿Quiénes son sus clientes?": "Contamos con una amplia variedad de clientes. Puedes conocerlos visitando nuestra página oficial: https://www.kinetpos.com",
    "¿Dónde genero, solicito o renuevo mi firma electrónica?": "Puedes hacerlo directamente desde este enlace: https://www.kinetpos.com/suscripciones/firma_electronica_form/",
    "¿Cuántas facturas puedo contratar para mi facturador electrónico y qué costo tiene?": "En nuestra página oficial encontrarás todos los planes disponibles: https://www.kinetpos.com/suscripciones/suscripcion_facturero/",
    "¿Cuántas facturas puedo contratar con el sistema de gestión empresarial y cuál es su costo?": "Puedes revisar todos los planes disponibles en: https://www.kinetpos.com/suscripciones",
    "¿Por qué debo pagar $150 por la creación del entorno en los planes de gestión empresarial?": "El pago único de $150 USD corresponde a la instalación del sistema en la nube. Este monto cubre el espacio, seguridad, capacitaciones y configuración inicial. La mensualidad se paga luego de consumir el primer mes de servicio.",
    "¿Qué pasa si contrato el plan más bajo y luego necesito más facturas o ampliar mi plan?": "Puedes ampliar tu plan en cualquier momento, sin costos adicionales ni interrupciones.",
    "¿Hay alguna opción adicional para mis clientes en KinetPOS?": "Sí, tus clientes pueden visualizar todas sus facturas desde nuestra página principal, siempre que las empresas que les facturen usen KinetPOS.",
    "¿Qué soluciones ofrece KinetPOS?": "KinetPOS soluciona múltiples necesidades empresariales:\n• Punto de Venta: Transacciones e inventario en tiempo real.\n• Convenios Bancarios: Integración con Banco de Loja y la app Ahorita! para validar pagos.\n• Facturación Automatizada: Envío de facturas por correo y WhatsApp.\n• Cuentas por Cobrar/Pagar: Organiza pagos y cobros con reportes detallados.",
    "¿Puedo usar KinetPOS si tengo un restaurante?": "Sí, tenemos herramientas específicas para restaurantes, como menús en línea, pedidos a domicilio, catálogos virtuales, impresión de comandas y más. Todo desde celular, tablet o PC.",
    "¿Tienen integración con bancos?": "Sí. Contamos con integración con el Banco de Loja y la app Ahorita! para validar pagos en tiempo real sin necesidad de comprobantes físicos.",
    "¿Qué pasa si mi computadora se daña?": "No hay problema. Al ser un sistema en la nube, puedes acceder desde cualquier dispositivo con conexión a internet en https://www.kinetpos.com",
    "¿Por qué al presionar el botón Ingresar me aparecen dos opciones: Administración y Punto de Venta?": "Porque KinetPOS tiene dos módulos:\n• Administración: Para gestionar inventario, compras, gastos, etc.\n• Punto de Venta: Para emitir facturas, órdenes, manejar caja, entre otros.",
    "¿Cómo inicio sesión en KinetPOS?": "Dirígete a https://www.kinetpos.com/, presiona 'Ingresar', selecciona Administración o Punto de Venta, e ingresa tu usuario y contraseña.",
    "¿Cómo puedo crear una factura?": "Desde el módulo de 'Punto de Venta', sección órdenes selecciona 'Nueva', ingresa datos del cliente, agrega los productos y haz clic en 'Facturar', luego selecciona la forma de pago.",
    "¿Puedo anular una factura?": "Sí, en Administración > Ventas - Lista, selecciona la factura, clic en el ojo verde, y al final encontrarás el botón de anular.",
    "¿Cómo anulo una factura?": "Hay dos pasos: en el SRI (www.sri.gob.ec > SRI en línea > Facturación electrónica > Producción > Anulación) y en KinetPOS (kinetpos.com/facturas/factura_list/administracion > ojo verde > Anular > confirmar).",
    "¿Cómo agrego un nuevo producto?": "Ve a Administración > Artículos - Crear, llena nombre, código, categoría, precio, stock y guarda.",
    "¿KinetPOS me permite manejar inventario?": "Sí, KinetPOS incluye un módulo de inventario donde puedes registrar productos, ver disponibilidad, ajustar stock y generar reportes.",
    "¿Puedo usar KinetPOS desde mi celular?": "Sí, KinetPOS es compatible con dispositivos móviles. Accede desde tu navegador móvil preferido.",
    "¿KinetPOS genera reportes de ventas?": "Sí, desde Administración > Reportes puedes generar informes detallados de ventas diarias, mensuales, por producto, por cliente y más.",
    "¿Puedo tener múltiples usuarios con diferentes permisos?": "Claro, puedes crear múltiples usuarios y asignarles roles como vendedor, cajero o administrador.",
    "¿Cómo contacto soporte técnico?": "Por WhatsApp: https://wa.me/593982738089 o al correo: desarrollokirios@gmail.com",
    "¿KinetPOS está en la nube?": "Sí, KinetPOS es un sistema en la nube, accesible desde cualquier lugar con internet.",
    "¿Puedo personalizar mis facturas?": "Sí, puedes agregar el logo de tu empresa e información fiscal desde la configuración de la empresa.",
    "¿KinetPOS funciona sin internet?": "No, KinetPOS requiere conexión a internet para funcionar.",
    "¿Cómo agrego un cliente nuevo?": "Al facturar, el sistema lo agrega automáticamente. También puedes gestionarlos en Administración > Empresa - Partners.",
    "¿El sistema emite comprobantes electrónicos?": "Sí, KinetPOS emite facturas, notas de crédito, guías de remisión y más, conforme a la normativa del SRI.",
    "¿KinetPOS tiene módulo para productos con variaciones como talla o color?": "Sí, puedes crear productos con variaciones como tallas y colores desde el módulo de productos compuestos.",
    "¿Puedo aplicar descuentos en las ventas?": "Sí, puedes aplicar descuentos por producto o en el total de la venta antes de emitir la factura.",
    "¿KinetPOS es compatible con impresoras térmicas?": "Sí, es compatible con la mayoría de impresoras del mercado.",
    "¿Puedo ver el historial de compras de un cliente?": "Sí, desde el listado de ventas puedes buscar al cliente y ver su historial.",
    "¿Cómo envío las facturas electrónicas al WhatsApp del cliente?": "Ve a Administración > Marketing > WhatsApp > Mensajes, clic en 'Conectar celular' y escanea el QR como WhatsApp Web.",
    "¿Cómo personalizo el mensaje para WhatsApp al enviar una factura?": "Ve a Administración > Marketing > WhatsApp > Mensajes y selecciona 'Nuevo mensaje'.",
    "¿Tengo soporte técnico con el sistema?": "Sí, soporte de capacitación de lunes a viernes de 9am a 1pm y de 3pm a 7pm.",
    "¿Tengo soporte técnico en caso de que el sistema dé error?": "Sí, soporte técnico 24/7 por WhatsApp.",
    "¿Qué sucede si los botones de facturación se desactivan o bloquean?": "Revisa los datos del cliente, pueden estar incompletos. El sistema valida los datos antes de enviarlos al SRI.",
    "¿Qué hago si el cliente paga con varias formas de pago?": "En la ventana de pago ingresa el monto y forma de pago, clic en 'Guardar', y el sistema habilitará otra forma de pago hasta completar el total.",
    "¿Puedo configurar diferentes precios para un mismo producto?": "Sí, puedes configurar hasta tres precios (A, B y C) por producto desde Administración al crear o editar el artículo.",
    "¿KinetPOS permite trabajar con productos fraccionables?": "Sí, al crear un producto puedes marcarlo como fraccionable y configurar unidad de venta, precio y stock en fracciones.",
    "¿Cómo puedo registrar una compra o ingreso de productos al inventario?": "Ve a Administración > Compras - Nueva, selecciona proveedor, agrega productos y guarda. Si la factura es electrónica usa 'Cargar comprobante' con la clave de acceso.",
    "¿Puedo llevar un control de proveedores en KinetPOS?": "Sí, en Administración > Empresa - Partners puedes registrar proveedores asignándoles ese rol.",
    "¿Cómo puedo exportar mis reportes o facturas?": "Desde cualquier listado puedes exportar en PDF o Excel usando las opciones en la parte superior.",
    "¿KinetPOS puede trabajar con códigos de barras?": "Sí, puedes ingresar el código de barras en cada producto y usar lectores para agilizar las ventas.",
    "¿Puedo manejar sucursales diferentes dentro del sistema?": "Sí, puedes crear múltiples sucursales y asignar productos, usuarios y ventas a cada una.",
    "¿KinetPOS permite integración con ecommerce o tienda en línea?": "Sí, dependiendo del plan, KinetPOS puede integrarse con plataformas de ecommerce para sincronizar productos, inventario y ventas.",
}
# ─────────────────────────────────────────────────────────────────────────────

def build_system_prompt(kb: dict) -> str:
    kb_text = "\n".join(f"PREGUNTA: {p}\nRESPUESTA: {r}\n" for p, r in kb.items())
    
    return (
        "Eres el asistente virtual oficial de KinetPOS. Eres amable, profesional y tu único propósito es ayudar con este sistema.\n\n"
        "REGLAS DE COMPORTAMIENTO:\n"
        "1. SALUDOS: Si el usuario te dice 'hola', 'buenos días', 'gracias' o se despide, devuélvele el saludo amablemente y ofrécele tu ayuda con KinetPOS.\n"
        "2. PREGUNTAS SOBRE KINETPOS: Responde a las dudas del usuario usando ÚNICAMENTE la información dentro de la sección <CONOCIMIENTO>.\n"
        "3. PREGUNTAS FUERA DE TEMA: Si el usuario te hace una pregunta sobre CUALQUIER otro tema que no esté en la base de conocimiento (por ejemplo: lenguajes de programación, clima, historia, etc.), DEBES aplicar esta regla y responder EXACTAMENTE con la siguiente frase:\n"
        "'Lo siento, no tengo esa información. Solo puedo ayudarte con temas relacionados a las funciones de KinetPOS. Para consultas más específicas, puedes comunicarte con soporte técnico por WhatsApp: https://wa.me/593982738089 o al correo: desarrollokirios@gmail.com'\n\n"        "Bajo NINGUNA circunstancia debes inventar información o usar tus conocimientos previos.\n\n"
        "<CONOCIMIENTO>\n"
        f"{kb_text}\n"
        "</CONOCIMIENTO>"
    )


def stream_chat(messages: list, system: str):
    """Streaming: imprime cada token apenas llega — se siente instantáneo."""
    payload = {
        "model": CHAT_MODEL,
        "think": False,
        "stream": True,
        "messages": [{"role": "system", "content": system}] + messages,
        "options": {
            "temperature": 0.1, 
        },
    }
    try:
        with httpx.stream(
            "POST", f"{OLLAMA_URL}/api/chat", json=payload, timeout=None
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
                if chunk.get("done"):
                    break
    except httpx.ConnectError:
        yield "\n[ERROR] No se pudo conectar a Ollama. Verifica que esté corriendo en localhost:11434"
    except Exception as e:
        yield f"\n[ERROR] {e}"


def main():
    system = build_system_prompt(KNOWLEDGE_BASE)
    history = []

    print("\n" + "═" * 50)
    print("  KinetPOS Asistente — escribe 'salir' para salir")
    print(f"  Modelo: {CHAT_MODEL}  |  Memoria: {MEMORY_SIZE} turnos")
    print("═" * 50 + "\n")

    while True:
        try:
            user_input = input("Tú: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nHasta luego.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("salir", "exit", "quit"):
            print("Hasta luego.")
            break

        history.append({"role": "user", "content": user_input})

        # Enviamos solo los últimos N turnos (memoria corta = contexto más pequeño = más rápido)
        recent = history[-(MEMORY_SIZE * 2):]

        print("Asistente: ", end="", flush=True)
        full_reply = ""

        for chunk in stream_chat(recent, system):
            print(chunk, end="", flush=True)
            full_reply += chunk

        print("\n")
        history.append({"role": "assistant", "content": full_reply})


if __name__ == "__main__":
    main()