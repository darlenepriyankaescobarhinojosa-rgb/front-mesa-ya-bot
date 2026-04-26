
import os

import sqlite3

import datetime

import pandas as pd

from groq import Groq

from telegram import Update

from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# =========================

# CONFIG

# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_TOKEN:
    raise RuntimeError("Falta configurar TELEGRAM_TOKEN en las variables de entorno.")

if not GROQ_API_KEY:
    raise RuntimeError("Falta configurar GROQ_API_KEY en las variables de entorno.")

groq_client = Groq(api_key=GROQ_API_KEY)

DB_PATH = "pedidos.db"

MENU_PATH = "menu_kiriko.csv"

CLIENTES_PATH = "clientes_restaurante_lima.csv"

RESERVAS_PATH = "reservas.csv"

RECLAMOS_PATH = "reclamos.csv"

CAMPANAS_PATH = "campanas.csv"

RESTAURANTE = {

    "nombre": "Kiriko Pollos y Parrillas",

    "direccion": "Ca. Lima 491, Miraflores",

    "telefono": "(01) 2420456",

    "web": "polleriakiriko.com",

    "horario": "Atendemos todos los días hasta las 11pm",

    "delivery": "Tenemos atención por delivery y recojo en tienda. Para el demo, el bot puede tomar el pedido y confirmar los datos.",

}

# =========================

# BASE DE DATOS

# =========================

conn = sqlite3.connect(DB_PATH, check_same_thread=False)

conn.execute("""

CREATE TABLE IF NOT EXISTS pedidos (

    id INTEGER PRIMARY KEY,

    cliente TEXT,

    agente TEXT,

    mensaje TEXT,

    respuesta TEXT,

    hora TEXT

)

""")

conn.commit()

# =========================

# CARGA DE DATA

# =========================

def cargar_csv(path: str) -> pd.DataFrame:

    try:

        if os.path.exists(path):

            return pd.read_csv(path)

        return pd.DataFrame()

    except Exception as e:

        print(f"⚠️ No pude cargar {path}: {e}")

        return pd.DataFrame()

def cargar_contexto():

    menu = cargar_csv(MENU_PATH)

    clientes = cargar_csv(CLIENTES_PATH)

    reservas = cargar_csv(RESERVAS_PATH)

    reclamos = cargar_csv(RECLAMOS_PATH)

    campanas = cargar_csv(CAMPANAS_PATH)

    return menu, clientes, reservas, reclamos, campanas

def texto_menu(menu: pd.DataFrame) -> str:

    if menu.empty:

        return "Menú no disponible en CSV."

    columnas = menu.columns.tolist()

    if "plato" not in columnas or "precio" not in columnas:

        return "El archivo menu_kiriko.csv no tiene columnas plato/precio."

    lineas = []

    for _, row in menu.iterrows():

        categoria = row.get("categoria", "Sin categoría")

        plato = row.get("plato", "")

        descripcion = row.get("descripcion", "")

        precio = row.get("precio", "")

        compartir = row.get("para_compartir", "")

        tiempo = row.get("tiempo_preparacion_min", "")

        lineas.append(

            f"- {plato} ({categoria}) — S/ {precio}. {descripcion}. "

            f"Para compartir: {compartir}. Tiempo aprox: {tiempo} min."

        )

    return "\n".join(lineas)

def texto_campanas(campanas: pd.DataFrame) -> str:

    if campanas.empty:

        return "No hay campañas cargadas."

    if "estado" in campanas.columns:

        activas = campanas[campanas["estado"].isin(["activa", "programada"])]

    else:

        activas = campanas

    if activas.empty:

        return "No hay campañas activas actualmente."

    lineas = []

    for _, row in activas.iterrows():

        nombre = row.get("nombre", "")

        segmento = row.get("segmento", "")

        oferta = row.get("oferta", "")

        canal = row.get("canal", "")

        estado = row.get("estado", "")

        lineas.append(f"- {nombre}: {oferta}. Segmento: {segmento}. Canal: {canal}. Estado: {estado}.")

    return "\n".join(lineas)

def buscar_cliente(nombre_telegram: str, clientes: pd.DataFrame) -> str:

    if clientes.empty:

        return "No hay base de clientes cargada."

    if "nombre" not in clientes.columns:

        return "La base de clientes no tiene columna nombre."

    # Para demo: como Telegram trae solo first_name, buscamos coincidencia parcial.

    nombre = str(nombre_telegram).lower()

    posibles = clientes[clientes["nombre"].str.lower().str.contains(nombre, na=False)]

    if posibles.empty:

        resumen = clientes["estado"].value_counts().to_dict() if "estado" in clientes.columns else {}

        return (

            f"Cliente no encontrado por nombre exacto. "

            f"Resumen de base: {len(clientes)} clientes. Estados: {resumen}."

        )

    row = posibles.iloc[0]

    return (

        f"Cliente encontrado: {row.get('nombre', '')}. "

        f"Estado: {row.get('estado', '')}. "

        f"Frecuencia mensual: {row.get('frecuencia_mensual', '')}. "

        f"Ticket promedio: S/ {row.get('ticket_promedio', '')}. "

        f"Plato favorito: {row.get('plato_favorito', '')}."

    )

def resumen_reservas(reservas: pd.DataFrame) -> str:

    if reservas.empty:

        return "No hay reservas cargadas."

    hoy = datetime.date.today().isoformat()

    if "fecha" in reservas.columns:

        reservas_hoy = reservas[reservas["fecha"].astype(str) == hoy]

    else:

        reservas_hoy = reservas

    if reservas_hoy.empty:

        return "No hay reservas registradas para hoy."

    total = len(reservas_hoy)

    personas = reservas_hoy["personas"].sum() if "personas" in reservas_hoy.columns else "N/D"

    pendientes = len(reservas_hoy[reservas_hoy["estado"] == "pendiente"]) if "estado" in reservas_hoy.columns else 0

    return f"Reservas hoy: {total}. Personas esperadas: {personas}. Reservas pendientes: {pendientes}."

def resumen_reclamos(reclamos: pd.DataFrame) -> str:

    if reclamos.empty:

        return "No hay reclamos cargados."

    hoy = datetime.date.today().isoformat()

    if "fecha" in reclamos.columns:

        reclamos_hoy = reclamos[reclamos["fecha"].astype(str) == hoy]

    else:

        reclamos_hoy = reclamos

    if reclamos_hoy.empty:

        return "No hay reclamos registrados para hoy."

    abiertos = reclamos_hoy[reclamos_hoy["estado"].isin(["pendiente", "en_revision"])] if "estado" in reclamos_hoy.columns else pd.DataFrame()

    tipo_mas_comun = reclamos_hoy["tipo"].mode().iloc[0] if "tipo" in reclamos_hoy.columns and not reclamos_hoy["tipo"].mode().empty else "N/D"

    return f"Reclamos hoy: {len(reclamos_hoy)}. Reclamos abiertos: {len(abiertos)}. Tipo más común: {tipo_mas_comun}."

# =========================

# DETECCIÓN SIMPLE PARA DASHBOARD

# =========================

def detectar_producto(texto: str, menu: pd.DataFrame) -> str:

    texto = str(texto).lower()

    if not menu.empty and "plato" in menu.columns:

        for plato in menu["plato"].dropna().tolist():

            plato_l = str(plato).lower()

            palabras = [p for p in plato_l.split() if len(p) > 3]

            if plato_l in texto or any(p in texto for p in palabras):

                return str(plato)

    reglas = {

        "pollo": "Pollo a la brasa",

        "chaufa": "Chaufa Brasa",

        "lomo": "Lomo Saltado Montado",

        "parrilla": "Parrilla Familiar",

        "ensalada": "Ensalada Kiriko",

        "inca": "Inca Kola",

        "chicha": "Chicha Morada",

        "tallarin": "Tallarín Saltado",

        "tallarín": "Tallarín Saltado",

    }

    for palabra, producto in reglas.items():

        if palabra in texto:

            return producto

    return "No identificado"

def es_confirmacion(mensaje: str, respuesta: str) -> bool:

    texto = f"{mensaje} {respuesta}".lower()

    claves = [

        "confirmo",

        "confirmar",

        "pedido confirmado",

        "sí quiero",

        "si quiero",

        "lo quiero",

        "dale",

        "ok",

        "va",

        "perfecto"

    ]

    return any(c in texto for c in claves)

# =========================

# IA

# =========================

def llamar_groq(system: str, mensaje: str, max_tokens: int = 450) -> str:

    r = groq_client.chat.completions.create(

        model="llama-3.3-70b-versatile",

        max_tokens=max_tokens,

        temperature=0.4,

        messages=[

            {"role": "system", "content": system},

            {"role": "user", "content": mensaje}

        ]

    )

    return r.choices[0].message.content.strip()

ORQUESTADOR = """

Eres un orquestador de agentes para CLIENTES de Kiriko Pollos y Parrillas.

Lee el mensaje del cliente y responde con UNA sola palabra:

PEDIDOS:

- quiere pedir comida

- quiere ver menú o precios

- pide recomendación de qué comer

- pregunta por platos, combos, bebidas o comida para compartir

- dice presupuesto, antojo, hambre o cantidad de personas

LOYALTY:

- pide descuentos, promociones, beneficios, cupones

- dice que no viene hace tiempo

- pregunta por campañas, ofertas, clientes frecuentes o recompensas

RESERVAS:

- quiere reservar una mesa

- pregunta por reservas de hoy

- quiere cambiar o cancelar reserva

- pregunta si hay mesa para cierta hora o cantidad de personas

RECLAMOS:

- se queja de demora, pedido incorrecto, mala atención, comida fría, delivery o problema con reserva

- quiere registrar una queja o reclamo

ATENCION:

- pregunta horarios, ubicación, teléfono, web, métodos de pago, delivery, recojo, contacto o dudas generales

IMPORTANTE:

Nunca respondas COCINA ni INSIGHTS. Eso es solo para el bot del dueño.

Solo responde con una palabra: PEDIDOS, LOYALTY, RESERVAS, RECLAMOS o ATENCION.

"""

def construir_agentes(menu, clientes, reservas, reclamos, campanas, user):

    menu_txt = texto_menu(menu)

    campanas_txt = texto_campanas(campanas)

    cliente_txt = buscar_cliente(user, clientes)

    reservas_txt = resumen_reservas(reservas)

    reclamos_txt = resumen_reclamos(reclamos)

    base = f"""

Eres MesaAI, asistente de clientes de {RESTAURANTE['nombre']}.

Datos del restaurante:

- Dirección: {RESTAURANTE['direccion']}

- Teléfono: {RESTAURANTE['telefono']}

- Web: {RESTAURANTE['web']}

- Horario: {RESTAURANTE['horario']}

- Delivery/recojo: {RESTAURANTE['delivery']}

Reglas generales:

- Responde en español peruano, cálido, directo y útil.

- No inventes precios fuera del menú.

- No digas que eres un modelo de IA.

- No menciones archivos CSV ni bases de datos al cliente.

- Si falta un dato para cerrar pedido/reserva/reclamo, pídeselo de forma breve.

- Mantén las respuestas cortas para Telegram.

"""

    agentes = {

        "PEDIDOS": base + f"""

Eres el Agente de Pedidos y Recomendaciones.

Tu objetivo:

1. Ayudar al cliente a elegir qué comer.

2. Recomendar según presupuesto, hambre, ocasión y cantidad de personas.

3. Tomar el pedido de forma simple.

4. Si el cliente confirma, escribir exactamente: PEDIDO CONFIRMADO: [resumen del pedido]

Menú disponible:

{menu_txt}

Contexto del cliente:

{cliente_txt}

Cómo recomendar:

- Si quiere algo barato: 1/4 Pollo, Chaufa Brasa o Pollo Saltado.

- Si quiere compartir: 1/2 Pollo, Pollo Entero, Combo Familiar Brasa o Parrilla Familiar.

- Si quiere algo clásico: Pollo a la brasa.

- Si quiere algo criollo: Lomo Saltado Montado o Chaufa Brasa.

- Si quiere algo ligero: Ensalada Kiriko, César con Pollo o Ensalada Florentina.

- Recomienda máximo 2 opciones.

- Incluye precio si está disponible.

- Cierra con una pregunta: "¿Te lo separo?" o "¿Confirmamos el pedido?"

""",

        "LOYALTY": base + f"""

Eres el Agente Loyalty y Promociones.

Tu objetivo:

- Dar beneficios simples.

- Recuperar clientes en riesgo.

- Aumentar recompra.

- Invitar a cerrar pedido.

Campañas disponibles:

{campanas_txt}

Contexto del cliente:

{cliente_txt}

Reglas:

- Si el cliente pide descuento, puedes ofrecer hasta 10% de descuento.

- Si dice que no viene hace tiempo, ofrece campaña de recuperación.

- Si es cliente activo/frecuente, ofrece bebida o complemento como beneficio.

- Si es nuevo, ofrece beneficio de bienvenida.

- No regales descuentos exagerados.

- Termina invitando a hacer un pedido.

""",

        "RESERVAS": base + f"""

Eres el Agente de Reservas.

Tu objetivo:

- Ayudar al cliente a reservar mesa.

- Pedir datos faltantes: nombre, fecha, hora y número de personas.

- Confirmar de manera clara.

Contexto de reservas:

{reservas_txt}

Reglas:

- Si el cliente ya dio fecha, hora y personas, responde como si hubieras tomado la solicitud.

- Si falta algún dato, pídeselo.

- Para el demo, puedes decir: "Dejo tu reserva como pendiente de confirmación del local".

- Si confirma, usa: RESERVA REGISTRADA: [nombre, fecha, hora, personas]

""",

        "RECLAMOS": base + f"""

Eres el Agente de Reclamos y Atención Postventa.

Tu objetivo:

- Recibir reclamos con empatía.

- Pedir datos faltantes: nombre, problema, hora/pedido y teléfono.

- Dar tranquilidad y prometer seguimiento.

Contexto de reclamos:

{reclamos_txt}

Reglas:

- Empieza pidiendo disculpas.

- Clasifica mentalmente el reclamo: demora, pedido_incorrecto, calidad, atencion, delivery o reserva.

- Si el reclamo es grave, ofrece escalarlo.

- Si tiene datos suficientes, responde: RECLAMO REGISTRADO: [resumen]

- No culpes al cliente.

""",

        "ATENCION": base + f"""

Eres el Agente de Atención al Cliente.

Puedes responder sobre:

- horario

- ubicación

- teléfono

- web

- delivery

- recojo en tienda

- métodos de pago de forma general

- dudas frecuentes

Contexto operativo:

{reservas_txt}

{reclamos_txt}

Reglas:

- Si pregunta ubicación, da dirección.

- Si pregunta horario, da horario.

- Si pregunta delivery, explica que puede hacer el pedido por el bot para demo.

- Si pregunta reservas o reclamos, deriva de forma natural.

"""

    }

    return agentes

# =========================

# TELEGRAM

# =========================

async def responder(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    msg = update.message.text

    user = update.message.from_user.first_name or "Cliente"

    await update.message.reply_text("🔄 MesaAI está revisando tu solicitud...")

    menu, clientes, reservas, reclamos, campanas = cargar_contexto()

    try:

        agente_key = llamar_groq(ORQUESTADOR, msg, max_tokens=20).strip().upper()

    except Exception as e:

        print(f"Error orquestador: {e}")

        agente_key = "ATENCION"

    if agente_key not in ["PEDIDOS", "LOYALTY", "RESERVAS", "RECLAMOS", "ATENCION"]:

        agente_key = "ATENCION"

    agentes = construir_agentes(menu, clientes, reservas, reclamos, campanas, user)

    nombres = {

        "PEDIDOS": "🍗 Agente Pedidos y Recomendaciones — Kiriko",

        "LOYALTY": "⭐ Agente Loyalty — Kiriko",

        "RESERVAS": "📅 Agente Reservas — Kiriko",

        "RECLAMOS": "🚨 Agente Reclamos — Kiriko",

        "ATENCION": "💬 Atención al Cliente — Kiriko"

    }

    try:

        respuesta = llamar_groq(agentes[agente_key], msg, max_tokens=500)

    except Exception as e:

        print(f"Error Groq: {e}")

        respuesta = "Disculpa, tuve un problema procesando tu solicitud. ¿Puedes escribirme otra vez en una frase más corta?"

    hora = datetime.datetime.now().isoformat()

    conn.execute(

        "INSERT INTO pedidos VALUES (null,?,?,?,?,?)",

        (user, agente_key, msg, respuesta, hora)

    )

    conn.commit()

    await update.message.reply_text(f"{nombres[agente_key]}\n\n{respuesta}")

# =========================

# MAIN

# =========================

if __name__ == "__main__":

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    print("✅ MesaAI Cliente — Kiriko activo en @mesa_ya_bot")

    app.run_polling()
