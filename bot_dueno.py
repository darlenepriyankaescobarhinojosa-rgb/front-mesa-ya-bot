
import os

import sqlite3

import datetime

from collections import Counter

import pandas as pd

from groq import Groq

from telegram import Update

from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# =========================

# CONFIG

# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_DUENO_TOKEN")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_TOKEN:
    raise RuntimeError("Falta configurar TELEGRAM_DUENO_TOKEN en las variables de entorno.")

if not GROQ_API_KEY:
    raise RuntimeError("Falta configurar GROQ_API_KEY en las variables de entorno.")

groq_client = Groq(api_key=GROQ_API_KEY)

DB_PATH = "pedidos.db"

MENU_PATH = "menu_kiriko.csv"

CLIENTES_PATH = "clientes_restaurante_lima.csv"

RESERVAS_PATH = "reservas.csv"

RECLAMOS_PATH = "reclamos.csv"

CAMPANAS_PATH = "campanas.csv"

RESTAURANTE = "Kiriko Pollos y Parrillas"

DIRECCION = "Ca. Lima 491, Miraflores"

# =========================

# DB

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

def cargar_pedidos() -> pd.DataFrame:

    try:

        df = pd.read_sql_query("SELECT * FROM pedidos", conn)

        if not df.empty:

            df["hora"] = pd.to_datetime(df["hora"], errors="coerce")

            df["fecha"] = df["hora"].dt.date.astype(str)

        return df

    except Exception as e:

        print(f"⚠️ No pude cargar pedidos.db: {e}")

        return pd.DataFrame()

def cargar_contexto():

    pedidos = cargar_pedidos()

    menu = cargar_csv(MENU_PATH)

    clientes = cargar_csv(CLIENTES_PATH)

    reservas = cargar_csv(RESERVAS_PATH)

    reclamos = cargar_csv(RECLAMOS_PATH)

    campanas = cargar_csv(CAMPANAS_PATH)

    return pedidos, menu, clientes, reservas, reclamos, campanas

# =========================

# LÓGICA DE PRODUCTOS Y MÉTRICAS

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

        "parrilla": "Parrilla Familiar",

        "lomo": "Lomo Saltado Montado",

        "chaufa": "Chaufa Brasa",

        "pollo": "Pollo a la brasa",

        "ensalada": "Ensalada Kiriko",

        "inca": "Inca Kola",

        "chicha": "Chicha Morada",

        "bebida": "Inca Kola",

        "tallarin": "Tallarín Saltado",

        "tallarín": "Tallarín Saltado",

        "pesto": "Al Pesto",

        "asado": "Asado con Puré",

    }

    for palabra, producto in reglas.items():

        if palabra in texto:

            return producto

    return "No identificado"

def precio_producto(producto: str, menu: pd.DataFrame) -> float:

    if menu.empty or "plato" not in menu.columns or "precio" not in menu.columns:

        return 0.0

    match = menu[menu["plato"].astype(str).str.lower() == str(producto).lower()]

    if match.empty:

        return 0.0

    try:

        return float(match.iloc[0]["precio"])

    except:

        return 0.0

def margen_producto(producto: str, menu: pd.DataFrame) -> float:

    if menu.empty or "plato" not in menu.columns or "margen_estimado" not in menu.columns:

        return 0.0

    match = menu[menu["plato"].astype(str).str.lower() == str(producto).lower()]

    if match.empty:

        return 0.0

    try:

        return float(match.iloc[0]["margen_estimado"])

    except:

        return 0.0

def tiempo_producto(producto: str, menu: pd.DataFrame) -> float:

    if menu.empty or "plato" not in menu.columns or "tiempo_preparacion_min" not in menu.columns:

        return 0.0

    match = menu[menu["plato"].astype(str).str.lower() == str(producto).lower()]

    if match.empty:

        return 0.0

    try:

        return float(match.iloc[0]["tiempo_preparacion_min"])

    except:

        return 0.0

def enriquecer_pedidos(pedidos: pd.DataFrame, menu: pd.DataFrame) -> pd.DataFrame:

    if pedidos.empty:

        return pedidos

    df = pedidos.copy()

    df["texto_total"] = df["mensaje"].fillna("") + " " + df["respuesta"].fillna("")

    df["producto_detectado"] = df["texto_total"].apply(lambda x: detectar_producto(x, menu))

    df["pedido_confirmado"] = df["respuesta"].fillna("").str.upper().str.contains("PEDIDO CONFIRMADO")

    df["monto_estimado"] = df["producto_detectado"].apply(lambda x: precio_producto(x, menu))

    df["margen_estimado_soles"] = df.apply(

        lambda r: r["monto_estimado"] * margen_producto(r["producto_detectado"], menu),

        axis=1

    )

    df["tiempo_cocina_min"] = df["producto_detectado"].apply(lambda x: tiempo_producto(x, menu))

    return df

def filtrar_fecha(df: pd.DataFrame, fecha: str) -> pd.DataFrame:

    if df.empty:

        return df

    if "fecha" in df.columns:

        return df[df["fecha"].astype(str) == fecha]

    return df

# =========================

# RESÚMENES

# =========================

def construir_resumen_negocio(fecha=None) -> str:

    if fecha is None:

        fecha = datetime.date.today().isoformat()

    pedidos, menu, clientes, reservas, reclamos, campanas = cargar_contexto()

    pedidos = enriquecer_pedidos(pedidos, menu)

    pedidos_hoy = filtrar_fecha(pedidos, fecha)

    reservas_hoy = filtrar_fecha(reservas, fecha)

    reclamos_hoy = filtrar_fecha(reclamos, fecha)

    # Pedidos

    interacciones = len(pedidos_hoy)

    pedidos_confirmados = int(pedidos_hoy["pedido_confirmado"].sum()) if not pedidos_hoy.empty and "pedido_confirmado" in pedidos_hoy.columns else 0

    ventas_estimadas = float(pedidos_hoy[pedidos_hoy["pedido_confirmado"]]["monto_estimado"].sum()) if pedidos_confirmados > 0 else 0.0

    ticket_promedio = ventas_estimadas / pedidos_confirmados if pedidos_confirmados > 0 else 0.0

    margen_estimado = float(pedidos_hoy[pedidos_hoy["pedido_confirmado"]]["margen_estimado_soles"].sum()) if pedidos_confirmados > 0 else 0.0

    tiempo_cocina = float(pedidos_hoy[pedidos_hoy["pedido_confirmado"]]["tiempo_cocina_min"].sum()) if pedidos_confirmados > 0 else 0.0

    if not pedidos_hoy.empty and "producto_detectado" in pedidos_hoy.columns:

        productos = pedidos_hoy[pedidos_hoy["producto_detectado"] != "No identificado"]["producto_detectado"]

        producto_top = productos.value_counts().idxmax() if not productos.empty else "No identificado"

        productos_dict = productos.value_counts().head(5).to_dict()

    else:

        producto_top = "No identificado"

        productos_dict = {}

    agentes_dict = pedidos_hoy["agente"].value_counts().to_dict() if not pedidos_hoy.empty and "agente" in pedidos_hoy.columns else {}

    # Reservas

    reservas_total = len(reservas_hoy)

    personas_esperadas = int(reservas_hoy["personas"].sum()) if not reservas_hoy.empty and "personas" in reservas_hoy.columns else 0

    reservas_pendientes = len(reservas_hoy[reservas_hoy["estado"] == "pendiente"]) if not reservas_hoy.empty and "estado" in reservas_hoy.columns else 0

    reservas_confirmadas = len(reservas_hoy[reservas_hoy["estado"] == "confirmada"]) if not reservas_hoy.empty and "estado" in reservas_hoy.columns else 0

    if not reservas_hoy.empty and "hora" in reservas_hoy.columns:

        hora_pico = reservas_hoy["hora"].astype(str).str.slice(0, 2).mode()

        hora_pico = f"{hora_pico.iloc[0]}:00" if not hora_pico.empty else "N/D"

    else:

        hora_pico = "N/D"

    # Reclamos

    reclamos_total = len(reclamos_hoy)

    if not reclamos_hoy.empty and "estado" in reclamos_hoy.columns:

        reclamos_abiertos = len(reclamos_hoy[reclamos_hoy["estado"].isin(["pendiente", "en_revision"])])

        reclamos_alta = len(reclamos_hoy[reclamos_hoy.get("prioridad", "").astype(str) == "alta"]) if "prioridad" in reclamos_hoy.columns else 0

    else:

        reclamos_abiertos = 0

        reclamos_alta = 0

    if not reclamos_hoy.empty and "tipo" in reclamos_hoy.columns:

        tipo_reclamo_top = reclamos_hoy["tipo"].mode()

        tipo_reclamo_top = tipo_reclamo_top.iloc[0] if not tipo_reclamo_top.empty else "N/D"

    else:

        tipo_reclamo_top = "N/D"

    # Clientes

    clientes_total = len(clientes)

    if not clientes.empty and "estado" in clientes.columns:

        clientes_activos = len(clientes[clientes["estado"] == "activo"])

        clientes_riesgo = len(clientes[clientes["estado"] == "en_riesgo"])

        clientes_nuevos = len(clientes[clientes["estado"] == "nuevo"])

    else:

        clientes_activos = clientes_riesgo = clientes_nuevos = 0

    ticket_clientes = float(clientes["ticket_promedio"].mean()) if not clientes.empty and "ticket_promedio" in clientes.columns else 0.0

    frecuencia_promedio = float(clientes["frecuencia_mensual"].mean()) if not clientes.empty and "frecuencia_mensual" in clientes.columns else 0.0

    # Campañas

    campañas_total = len(campanas)

    campañas_activas = len(campanas[campanas["estado"] == "activa"]) if not campanas.empty and "estado" in campanas.columns else 0

    ventas_campanas = float(campanas["ventas_atribuidas"].sum()) if not campanas.empty and "ventas_atribuidas" in campanas.columns else 0.0

    conversion_promedio = float(campanas["tasa_conversion"].mean()) if not campanas.empty and "tasa_conversion" in campanas.columns else 0.0

    if not campanas.empty and "ventas_atribuidas" in campanas.columns:

        mejor_campana_row = campanas.sort_values("ventas_atribuidas", ascending=False).iloc[0]

        mejor_campana = f"{mejor_campana_row.get('nombre', 'N/D')} — S/ {float(mejor_campana_row.get('ventas_atribuidas', 0)):,.2f}"

    else:

        mejor_campana = "N/D"

    resumen = f"""

Fecha analizada: {fecha}

NEGOCIO / PEDIDOS

- Interacciones del bot hoy: {interacciones}

- Pedidos confirmados detectados: {pedidos_confirmados}

- Ventas estimadas por pedidos confirmados: S/ {ventas_estimadas:,.2f}

- Ticket promedio estimado: S/ {ticket_promedio:,.2f}

- Margen estimado: S/ {margen_estimado:,.2f}

- Tiempo total estimado de cocina: {tiempo_cocina:.0f} minutos

- Producto más demandado/mencionado: {producto_top}

- Top productos mencionados: {productos_dict}

- Uso por agente: {agentes_dict}

RESERVAS

- Reservas de hoy: {reservas_total}

- Reservas confirmadas: {reservas_confirmadas}

- Reservas pendientes: {reservas_pendientes}

- Personas esperadas: {personas_esperadas}

- Hora pico estimada: {hora_pico}

RECLAMOS

- Reclamos de hoy: {reclamos_total}

- Reclamos abiertos: {reclamos_abiertos}

- Reclamos de prioridad alta: {reclamos_alta}

- Tipo de reclamo más común: {tipo_reclamo_top}

CLIENTES

- Clientes en base: {clientes_total}

- Activos: {clientes_activos}

- En riesgo: {clientes_riesgo}

- Nuevos: {clientes_nuevos}

- Ticket promedio de clientes: S/ {ticket_clientes:,.2f}

- Frecuencia mensual promedio: {frecuencia_promedio:.2f}

CAMPAÑAS

- Campañas totales: {campañas_total}

- Campañas activas: {campañas_activas}

- Ventas atribuidas a campañas: S/ {ventas_campanas:,.2f}

- Conversión promedio de campañas: {conversion_promedio:.2%}

- Mejor campaña por ventas: {mejor_campana}

"""

    return resumen

def ultimos_pedidos_texto(limite=8) -> str:

    pedidos, menu, _, _, _, _ = cargar_contexto()

    pedidos = enriquecer_pedidos(pedidos, menu)

    if pedidos.empty:

        return "No hay interacciones registradas."

    pedidos = pedidos.sort_values("hora", ascending=False).head(limite)

    lineas = []

    for _, r in pedidos.iterrows():

        hora = str(r.get("hora", ""))[:16]

        cliente = r.get("cliente", "")

        agente = r.get("agente", "")

        producto = r.get("producto_detectado", "")

        confirmado = "sí" if r.get("pedido_confirmado", False) else "no"

        mensaje = str(r.get("mensaje", ""))[:70]

        lineas.append(f"- {hora} | {cliente} | {agente} | {producto} | confirmado: {confirmado} | '{mensaje}'")

    return "\n".join(lineas)

# =========================

# GROQ

# =========================

def llamar_groq(system: str, mensaje: str, max_tokens: int = 550) -> str:

    r = groq_client.chat.completions.create(

        model="llama-3.3-70b-versatile",

        max_tokens=max_tokens,

        temperature=0.35,

        messages=[

            {"role": "system", "content": system},

            {"role": "user", "content": mensaje}

        ]

    )

    return r.choices[0].message.content.strip()

ORQUESTADOR_DUENO = """

Eres un orquestador para el DUEÑO de Kiriko Pollos y Parrillas.

Lee el mensaje y responde con UNA sola palabra:

COCINA:

- pregunta sobre cocina, stock, preparación, demanda, qué cocinar, insumos, tiempos, cola de pedidos o productos más pedidos.

RESERVAS:

- pregunta sobre reservas, mesas, personas esperadas, hora pico, reservas pendientes o cancelaciones.

RECLAMOS:

- pregunta sobre quejas, reclamos, problemas, clientes molestos, demoras, calidad, delivery o atención.

CLIENTES:

- pregunta sobre clientes, fidelización, clientes en riesgo, nuevos, frecuentes, recompra o segmentos.

CAMPAÑAS:

- pregunta sobre campañas, promociones, marketing, descuentos, conversión, ventas atribuidas o recuperación de clientes.

INSIGHTS:

- pregunta por resumen del día, ventas, métricas generales, negocio, alertas, recomendaciones, decisiones o estado general.

Solo responde con una palabra:

COCINA, RESERVAS, RECLAMOS, CLIENTES, CAMPAÑAS o INSIGHTS.

"""

AGENTES_DUENO = {

    "COCINA": """

Eres el Agente Cocina de Kiriko Pollos y Parrillas.

Das recomendaciones operativas para cocina y salón.

Debes responder:

1. Qué producto priorizar

2. Qué preparar ahora

3. Riesgos operativos

4. Acción concreta

Sé breve y directo.

Usa números del contexto.

""",

    "RESERVAS": """

Eres el Agente Reservas para el dueño.

Analizas reservas del día.

Debes responder:

1. Reservas de hoy

2. Personas esperadas

3. Hora pico

4. Pendientes o cancelaciones

5. Acción recomendada

Sé ejecutivo.

""",

    "RECLAMOS": """

Eres el Agente Reclamos para el dueño.

Analizas reclamos y riesgos de atención.

Debes responder:

1. Reclamos de hoy

2. Reclamos abiertos

3. Prioridad alta

4. Tipo de problema más común

5. Qué resolver primero

Sé claro y orientado a acción.

""",

    "CLIENTES": """

Eres el Agente Clientes y Fidelización.

Analizas la base de clientes.

Debes responder:

1. Clientes activos, en riesgo y nuevos

2. Qué segmento atacar

3. Acción recomendada de fidelización

4. Oportunidad comercial

Sé comercial y accionable.

""",

    "CAMPAÑAS": """

Eres el Agente Campañas y Marketing.

Analizas promociones y campañas.

Debes responder:

1. Campañas activas

2. Ventas atribuidas

3. Conversión promedio

4. Mejor campaña

5. Siguiente campaña recomendada

Sé comercial y directo.

""",

    "INSIGHTS": """

Eres el Agente Insights del dueño.

Das un resumen ejecutivo del negocio.

Formato obligatorio:

📊 Resumen del día

🚨 Alertas

🧠 Recomendaciones MesaAI

Usa números concretos.

No seas genérico.

Prioriza ventas, pedidos, reservas, reclamos, clientes y campañas.

"""

}

# =========================

# TELEGRAM

# =========================

async def responder_dueno(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    msg = update.message.text

    await update.message.reply_text("📊 Analizando el negocio...")

    try:

        agente_key = llamar_groq(ORQUESTADOR_DUENO, msg, max_tokens=20).strip().upper()

    except Exception as e:

        print(f"Error orquestador dueño: {e}")

        agente_key = "INSIGHTS"

    if agente_key not in AGENTES_DUENO:

        agente_key = "INSIGHTS"

    nombres = {

        "COCINA": "👨‍🍳 Agente Cocina — Kiriko",

        "RESERVAS": "📅 Agente Reservas — Kiriko",

        "RECLAMOS": "🚨 Agente Reclamos — Kiriko",

        "CLIENTES": "👥 Agente Clientes — Kiriko",

        "CAMPAÑAS": "💸 Agente Campañas — Kiriko",

        "INSIGHTS": "📊 Agente Insights — Kiriko"

    }

    resumen = construir_resumen_negocio()

    ultimos = ultimos_pedidos_texto()

    contexto = f"""

Restaurante: {RESTAURANTE}

Dirección: {DIRECCION}

CONTEXTO ACTUAL DEL NEGOCIO:

{resumen}

ÚLTIMAS INTERACCIONES:

{ultimos}

"""

    try:

        respuesta = llamar_groq(

            AGENTES_DUENO[agente_key] + "\n\n" + contexto,

            msg,

            max_tokens=650

        )

    except Exception as e:

        print(f"Error Groq dueño: {e}")

        respuesta = "Tuve un problema leyendo el contexto del negocio. Revisa que los CSV y pedidos.db estén en la misma carpeta."

    await update.message.reply_text(f"{nombres[agente_key]}\n\n{respuesta}")

# =========================

# MAIN

# =========================

if __name__ == "__main__":

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_dueno))

    print("✅ Bot Dueño Kiriko — corriendo en @tu_mesa_bot")

    app.run_polling()
