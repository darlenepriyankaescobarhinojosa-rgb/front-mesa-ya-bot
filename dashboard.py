import os
import sqlite3
import datetime
import pandas as pd
import streamlit as st

# =========================
# CONFIG
# =========================

st.set_page_config(
    page_title="MesaAI — Panel del Dueño",
    page_icon="🍗",
    layout="wide"
)

DB_PATH = "pedidos.db"
MENU_PATH = "menu_kiriko.csv"
CLIENTES_PATH = "clientes_restaurante_lima.csv"
RESERVAS_PATH = "reservas.csv"
RECLAMOS_PATH = "reclamos.csv"
CAMPANAS_PATH = "campanas.csv"

# =========================
# ESTILOS
# =========================

st.markdown("""
<style>
.block-container {
    padding-top: 1.8rem;
    padding-bottom: 2rem;
}
.metric-card {
    background: #ffffff;
    border: 1px solid #eeeeee;
    border-radius: 18px;
    padding: 18px;
    box-shadow: 0px 3px 12px rgba(0,0,0,0.05);
}
.section-card {
    background: #ffffff;
    border: 1px solid #eeeeee;
    border-radius: 18px;
    padding: 18px;
    margin-bottom: 16px;
}
.alert-red {
    background: #fff1f1;
    border-left: 6px solid #e63946;
    border-radius: 10px;
    padding: 14px;
    margin-bottom: 10px;
}
.alert-yellow {
    background: #fff8e1;
    border-left: 6px solid #f4a261;
    border-radius: 10px;
    padding: 14px;
    margin-bottom: 10px;
}
.alert-green {
    background: #ecfdf3;
    border-left: 6px solid #2a9d8f;
    border-radius: 10px;
    padding: 14px;
    margin-bottom: 10px;
}
.small-text {
    color: #666;
    font-size: 0.9rem;
}
</style>
""", unsafe_allow_html=True)

# =========================
# CARGA DE DATA
# =========================

@st.cache_data(ttl=5)
def cargar_csv(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as e:
        st.warning(f"No pude cargar {path}: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=5)
def cargar_pedidos():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()

    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM pedidos", conn)
        conn.close()

        if not df.empty:
            df["hora"] = pd.to_datetime(df["hora"], errors="coerce")
            df["fecha"] = df["hora"].dt.date.astype(str)

        return df
    except Exception as e:
        st.warning(f"No pude cargar pedidos.db: {e}")
        return pd.DataFrame()

def filtrar_fecha(df, fecha_str):
    if df.empty:
        return df

    if "fecha" in df.columns:
        return df[df["fecha"].astype(str) == fecha_str]

    return df

# =========================
# LÓGICA DE PRODUCTOS
# =========================

def detectar_producto(texto, menu):
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

def precio_producto(producto, menu):
    if menu.empty or "plato" not in menu.columns or "precio" not in menu.columns:
        return 0.0

    match = menu[menu["plato"].astype(str).str.lower() == str(producto).lower()]
    if match.empty:
        return 0.0

    try:
        return float(match.iloc[0]["precio"])
    except:
        return 0.0

def margen_producto(producto, menu):
    if menu.empty or "plato" not in menu.columns or "margen_estimado" not in menu.columns:
        return 0.0

    match = menu[menu["plato"].astype(str).str.lower() == str(producto).lower()]
    if match.empty:
        return 0.0

    try:
        return float(match.iloc[0]["margen_estimado"])
    except:
        return 0.0

def tiempo_producto(producto, menu):
    if menu.empty or "plato" not in menu.columns or "tiempo_preparacion_min" not in menu.columns:
        return 0.0

    match = menu[menu["plato"].astype(str).str.lower() == str(producto).lower()]
    if match.empty:
        return 0.0

    try:
        return float(match.iloc[0]["tiempo_preparacion_min"])
    except:
        return 0.0

def enriquecer_pedidos(pedidos, menu):
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

# =========================
# CARGAR TODO
# =========================

pedidos = cargar_pedidos()
menu = cargar_csv(MENU_PATH)
clientes = cargar_csv(CLIENTES_PATH)
reservas = cargar_csv(RESERVAS_PATH)
reclamos = cargar_csv(RECLAMOS_PATH)
campanas = cargar_csv(CAMPANAS_PATH)

pedidos = enriquecer_pedidos(pedidos, menu)

# =========================
# HEADER
# =========================

st.title("🍗 MesaAI — Panel del Dueño")
st.caption("Kiriko Pollos y Parrillas · Ca. Lima 491, Miraflores")

col_fecha, col_refresh = st.columns([3, 1])

with col_fecha:
    fecha_seleccionada = st.date_input(
        "Fecha de análisis",
        value=datetime.date.today()
    )

with col_refresh:
    st.write("")
    st.write("")
    if st.button("🔄 Actualizar datos"):
        st.cache_data.clear()
        st.rerun()

fecha_str = fecha_seleccionada.isoformat()

pedidos_dia = filtrar_fecha(pedidos, fecha_str)
reservas_dia = filtrar_fecha(reservas, fecha_str)
reclamos_dia = filtrar_fecha(reclamos, fecha_str)

# =========================
# KPIs PRINCIPALES
# =========================

if pedidos_dia.empty:
    interacciones = 0
    pedidos_confirmados = 0
    ventas_estimadas = 0.0
    ticket_promedio = 0.0
    margen_estimado = 0.0
    tiempo_cocina = 0.0
else:
    interacciones = len(pedidos_dia)
    pedidos_confirmados = int(pedidos_dia["pedido_confirmado"].sum())
    ventas_estimadas = float(pedidos_dia[pedidos_dia["pedido_confirmado"]]["monto_estimado"].sum())
    ticket_promedio = ventas_estimadas / pedidos_confirmados if pedidos_confirmados > 0 else 0.0
    margen_estimado = float(pedidos_dia[pedidos_dia["pedido_confirmado"]]["margen_estimado_soles"].sum())
    tiempo_cocina = float(pedidos_dia[pedidos_dia["pedido_confirmado"]]["tiempo_cocina_min"].sum())

if reservas_dia.empty:
    reservas_hoy = 0
    personas_esperadas = 0
    reservas_pendientes = 0
else:
    reservas_hoy = len(reservas_dia)
    personas_esperadas = int(reservas_dia["personas"].sum()) if "personas" in reservas_dia.columns else 0
    reservas_pendientes = len(reservas_dia[reservas_dia["estado"] == "pendiente"]) if "estado" in reservas_dia.columns else 0

if reclamos_dia.empty:
    reclamos_hoy = 0
    reclamos_abiertos = 0
    reclamos_alta = 0
else:
    reclamos_hoy = len(reclamos_dia)
    reclamos_abiertos = len(reclamos_dia[reclamos_dia["estado"].isin(["pendiente", "en_revision"])]) if "estado" in reclamos_dia.columns else 0
    reclamos_alta = len(reclamos_dia[reclamos_dia["prioridad"] == "alta"]) if "prioridad" in reclamos_dia.columns else 0

if clientes.empty:
    clientes_riesgo = 0
    clientes_activos = 0
    clientes_nuevos = 0
    ticket_clientes = 0.0
    frecuencia_promedio = 0.0
else:
    clientes_riesgo = len(clientes[clientes["estado"] == "en_riesgo"]) if "estado" in clientes.columns else 0
    clientes_activos = len(clientes[clientes["estado"] == "activo"]) if "estado" in clientes.columns else 0
    clientes_nuevos = len(clientes[clientes["estado"] == "nuevo"]) if "estado" in clientes.columns else 0
    ticket_clientes = float(clientes["ticket_promedio"].mean()) if "ticket_promedio" in clientes.columns else 0.0
    frecuencia_promedio = float(clientes["frecuencia_mensual"].mean()) if "frecuencia_mensual" in clientes.columns else 0.0

if campanas.empty:
    campanas_activas = 0
    ventas_campanas = 0.0
    conversion_promedio = 0.0
else:
    campanas_activas = len(campanas[campanas["estado"] == "activa"]) if "estado" in campanas.columns else 0
    ventas_campanas = float(campanas["ventas_atribuidas"].sum()) if "ventas_atribuidas" in campanas.columns else 0.0
    conversion_promedio = float(campanas["tasa_conversion"].mean()) if "tasa_conversion" in campanas.columns else 0.0

st.subheader("📌 Estado del negocio")

k1, k2, k3, k4, k5, k6 = st.columns(6)

k1.metric("Ventas estimadas", f"S/ {ventas_estimadas:,.2f}")
k2.metric("Pedidos confirmados", pedidos_confirmados)
k3.metric("Ticket promedio", f"S/ {ticket_promedio:,.2f}")
k4.metric("Reservas", reservas_hoy)
k5.metric("Reclamos abiertos", reclamos_abiertos)
k6.metric("Clientes en riesgo", clientes_riesgo)

k7, k8, k9, k10, k11, k12 = st.columns(6)

k7.metric("Interacciones bot", interacciones)
k8.metric("Personas esperadas", personas_esperadas)
k9.metric("Reservas pendientes", reservas_pendientes)
k10.metric("Margen estimado", f"S/ {margen_estimado:,.2f}")
k11.metric("Campañas activas", campanas_activas)
k12.metric("Ventas campañas", f"S/ {ventas_campanas:,.2f}")

st.divider()

# =========================
# RECOMENDACIONES MESAAI
# =========================

st.subheader("🧠 Recomendaciones MesaAI")

recomendaciones = []

if not pedidos_dia.empty and "producto_detectado" in pedidos_dia.columns:
    productos_validos = pedidos_dia[pedidos_dia["producto_detectado"] != "No identificado"]["producto_detectado"]
    if not productos_validos.empty:
        producto_top = productos_validos.value_counts().idxmax()
        recomendaciones.append((
            "green",
            "🍗 Cocina",
            f"El producto con más demanda es **{producto_top}**. Refuerza preparación y stock para la hora pico."
        ))

if reservas_hoy > 0:
    hora_pico = "N/D"
    if not reservas_dia.empty and "hora" in reservas_dia.columns:
        moda = reservas_dia["hora"].astype(str).str.slice(0, 2).mode()
        if not moda.empty:
            hora_pico = f"{moda.iloc[0]}:00"

    recomendaciones.append((
        "yellow",
        "📅 Reservas",
        f"Hoy hay **{reservas_hoy} reservas** y **{personas_esperadas} personas esperadas**. Hora pico estimada: **{hora_pico}**."
    ))

if reclamos_abiertos > 0:
    recomendaciones.append((
        "red",
        "🚨 Atención",
        f"Hay **{reclamos_abiertos} reclamos abiertos** y **{reclamos_alta} de prioridad alta**. Resolverlos antes del cierre."
    ))

if clientes_riesgo > 0:
    recomendaciones.append((
        "yellow",
        "💸 Fidelización",
        f"Hay **{clientes_riesgo} clientes en riesgo**. Lanza una campaña de 10% o delivery gratis para recuperarlos esta semana."
    ))

if campanas_activas > 0:
    recomendaciones.append((
        "green",
        "📣 Campañas",
        f"Tienes **{campanas_activas} campañas activas** con conversión promedio de **{conversion_promedio:.1%}**. Mantén la mejor y pausa las de baja conversión."
    ))

if pedidos_confirmados == 0 and interacciones > 0:
    recomendaciones.append((
        "yellow",
        "🛒 Conversión",
        "Hay interacciones pero pocos pedidos confirmados. El bot debe cerrar con: **¿Confirmamos tu pedido?**"
    ))

if not recomendaciones:
    recomendaciones.append((
        "green",
        "✅ Estado general",
        "No hay alertas críticas. Sigue registrando pedidos, reservas y reclamos para generar mejores recomendaciones."
    ))

for color, titulo, texto in recomendaciones:
    css_class = {
        "red": "alert-red",
        "yellow": "alert-yellow",
        "green": "alert-green"
    }.get(color, "alert-green")

    st.markdown(
        f"""
        <div class="{css_class}">
            <b>{titulo}</b><br>
            {texto}
        </div>
        """,
        unsafe_allow_html=True
    )

st.divider()

# =========================
# OPERACIÓN DE HOY
# =========================

st.subheader("🍽️ Operación de hoy")

op1, op2 = st.columns(2)

with op1:
    st.markdown("### Productos más mencionados")

    if pedidos_dia.empty or "producto_detectado" not in pedidos_dia.columns:
        st.info("Aún no hay productos detectados para esta fecha.")
    else:
        productos = pedidos_dia[pedidos_dia["producto_detectado"] != "No identificado"]["producto_detectado"].value_counts()

        if productos.empty:
            st.info("No se detectaron productos todavía.")
        else:
            st.bar_chart(productos)

with op2:
    st.markdown("### Uso por agente")

    if pedidos_dia.empty or "agente" not in pedidos_dia.columns:
        st.info("Aún no hay interacciones para esta fecha.")
    else:
        agentes = pedidos_dia["agente"].value_counts()
        st.bar_chart(agentes)

op3, op4 = st.columns(2)

with op3:
    st.markdown("### Preparación estimada de cocina")
    st.metric("Minutos estimados de cocina", f"{tiempo_cocina:.0f} min")
    st.caption("Calculado con pedidos confirmados y tiempo de preparación del menú.")

with op4:
    st.markdown("### Conversión del bot")
    conversion = pedidos_confirmados / interacciones if interacciones > 0 else 0
    st.metric("Conversión a pedido", f"{conversion:.1%}")
    st.caption("Pedidos confirmados / interacciones del bot.")

st.divider()

# =========================
# RESERVAS
# =========================

st.subheader("📅 Reservas")

r1, r2, r3, r4 = st.columns(4)

reservas_confirmadas = len(reservas_dia[reservas_dia["estado"] == "confirmada"]) if not reservas_dia.empty and "estado" in reservas_dia.columns else 0
reservas_canceladas = len(reservas_dia[reservas_dia["estado"] == "cancelada"]) if not reservas_dia.empty and "estado" in reservas_dia.columns else 0

hora_pico_reservas = "N/D"
if not reservas_dia.empty and "hora" in reservas_dia.columns:
    moda_hora = reservas_dia["hora"].astype(str).str.slice(0, 2).mode()
    if not moda_hora.empty:
        hora_pico_reservas = f"{moda_hora.iloc[0]}:00"

r1.metric("Reservas del día", reservas_hoy)
r2.metric("Personas esperadas", personas_esperadas)
r3.metric("Pendientes", reservas_pendientes)
r4.metric("Hora pico", hora_pico_reservas)

if reservas_dia.empty:
    st.info("No hay reservas para esta fecha.")
else:
    columnas_reservas = [c for c in ["hora", "cliente", "telefono", "personas", "estado", "canal", "zona", "comentario"] if c in reservas_dia.columns]
    st.dataframe(
        reservas_dia[columnas_reservas].sort_values("hora"),
        use_container_width=True,
        hide_index=True
    )

st.divider()

# =========================
# RECLAMOS
# =========================

st.subheader("🚨 Reclamos y atención")

c1, c2, c3, c4 = st.columns(4)

tipo_mas_comun = "N/D"
if not reclamos_dia.empty and "tipo" in reclamos_dia.columns:
    moda_tipo = reclamos_dia["tipo"].mode()
    if not moda_tipo.empty:
        tipo_mas_comun = moda_tipo.iloc[0]

c1.metric("Reclamos del día", reclamos_hoy)
c2.metric("Abiertos", reclamos_abiertos)
c3.metric("Prioridad alta", reclamos_alta)
c4.metric("Tipo más común", tipo_mas_comun)

if reclamos_dia.empty:
    st.info("No hay reclamos para esta fecha.")
else:
    reclamos_vista = reclamos_dia.copy()

    if "estado" in reclamos_vista.columns:
        reclamos_vista["estado_visual"] = reclamos_vista["estado"].map({
            "pendiente": "🔴 pendiente",
            "en_revision": "🟡 en revisión",
            "resuelto": "🟢 resuelto"
        }).fillna(reclamos_vista["estado"])

    columnas_reclamos = [c for c in ["hora", "cliente", "telefono", "tipo", "descripcion", "estado_visual", "canal", "prioridad", "responsable"] if c in reclamos_vista.columns]

    st.dataframe(
        reclamos_vista[columnas_reclamos].sort_values("hora"),
        use_container_width=True,
        hide_index=True
    )

st.divider()

# =========================
# CLIENTES Y FIDELIZACIÓN
# =========================

st.subheader("👥 Clientes y fidelización")

cl1, cl2, cl3, cl4, cl5 = st.columns(5)

cl1.metric("Clientes activos", clientes_activos)
cl2.metric("Clientes en riesgo", clientes_riesgo)
cl3.metric("Clientes nuevos", clientes_nuevos)
cl4.metric("Ticket prom. clientes", f"S/ {ticket_clientes:,.2f}")
cl5.metric("Frecuencia prom.", f"{frecuencia_promedio:.1f}/mes")

cli_col1, cli_col2 = st.columns(2)

with cli_col1:
    st.markdown("### Estado de clientes")

    if clientes.empty or "estado" not in clientes.columns:
        st.info("No hay base de clientes cargada.")
    else:
        estado_clientes = clientes["estado"].value_counts()
        st.bar_chart(estado_clientes)

with cli_col2:
    st.markdown("### Platos favoritos")

    if clientes.empty or "plato_favorito" not in clientes.columns:
        st.info("No hay platos favoritos cargados.")
    else:
        favoritos = clientes["plato_favorito"].value_counts().head(8)
        st.bar_chart(favoritos)

st.markdown("### Clientes en riesgo")

if clientes.empty or "estado" not in clientes.columns:
    st.info("No hay clientes para mostrar.")
else:
    clientes_riesgo_df = clientes[clientes["estado"] == "en_riesgo"].copy()
    columnas_clientes = [c for c in ["nombre", "telefono", "fecha_ultima_visita", "frecuencia_mensual", "ticket_promedio", "plato_favorito"] if c in clientes_riesgo_df.columns]

    st.dataframe(
        clientes_riesgo_df[columnas_clientes].head(20),
        use_container_width=True,
        hide_index=True
    )

st.divider()

# =========================
# CAMPAÑAS
# =========================

st.subheader("📣 Campañas y recompra")

ca1, ca2, ca3, ca4 = st.columns(4)

if campanas.empty:
    mejor_campana = "N/D"
else:
    if "ventas_atribuidas" in campanas.columns and not campanas.empty:
        mejor_row = campanas.sort_values("ventas_atribuidas", ascending=False).iloc[0]
        mejor_campana = str(mejor_row.get("nombre", "N/D"))
    else:
        mejor_campana = "N/D"

ca1.metric("Campañas activas", campanas_activas)
ca2.metric("Ventas atribuidas", f"S/ {ventas_campanas:,.2f}")
ca3.metric("Conversión promedio", f"{conversion_promedio:.1%}")
ca4.metric("Mejor campaña", mejor_campana)

if campanas.empty:
    st.info("No hay campañas cargadas.")
else:
    columnas_campanas = [c for c in ["nombre", "fecha_envio", "segmento", "canal", "oferta", "clientes_objetivo", "tasa_apertura", "tasa_conversion", "ventas_atribuidas", "estado"] if c in campanas.columns]
    st.dataframe(
        campanas[columnas_campanas],
        use_container_width=True,
        hide_index=True
    )

st.divider()

# =========================
# MENÚ Y RENTABILIDAD
# =========================

st.subheader("📋 Menú y rentabilidad")

if menu.empty:
    st.info("No hay menú cargado.")
else:
    menu_vista = menu.copy()

    if "precio" in menu_vista.columns and "margen_estimado" in menu_vista.columns:
        menu_vista["ganancia_estimada"] = menu_vista["precio"] * menu_vista["margen_estimado"]

    col_menu1, col_menu2 = st.columns(2)

    with col_menu1:
        st.markdown("### Platos de mayor margen estimado")
        if "ganancia_estimada" in menu_vista.columns:
            margen_top = menu_vista.sort_values("ganancia_estimada", ascending=False).head(8)
            st.bar_chart(margen_top.set_index("plato")["ganancia_estimada"])
        else:
            st.info("Faltan columnas precio/margen_estimado.")

    with col_menu2:
        st.markdown("### Tiempo de preparación")
        if "tiempo_preparacion_min" in menu_vista.columns:
            tiempo_top = menu_vista.sort_values("tiempo_preparacion_min", ascending=False).head(8)
            st.bar_chart(tiempo_top.set_index("plato")["tiempo_preparacion_min"])
        else:
            st.info("Falta columna tiempo_preparacion_min.")

    columnas_menu = [c for c in ["categoria", "plato", "descripcion", "precio", "margen_estimado", "tiempo_preparacion_min", "para_compartir", "popularidad"] if c in menu_vista.columns]

    st.dataframe(
        menu_vista[columnas_menu],
        use_container_width=True,
        hide_index=True
    )

st.divider()

# =========================
# ÚLTIMAS INTERACCIONES
# =========================

st.subheader("💬 Últimas interacciones del bot")

if pedidos.empty:
    st.info("Todavía no hay interacciones registradas en pedidos.db.")
else:
    ultimas = pedidos.sort_values("hora", ascending=False).copy()

    columnas_interacciones = [
        c for c in [
            "hora",
            "cliente",
            "agente",
            "mensaje",
            "producto_detectado",
            "pedido_confirmado",
            "monto_estimado"
        ]
        if c in ultimas.columns
    ]

    st.dataframe(
        ultimas[columnas_interacciones].head(30),
        use_container_width=True,
        hide_index=True
    )

    with st.expander("Ver respuestas completas del bot"):
        columnas_respuestas = [c for c in ["hora", "cliente", "agente", "mensaje", "respuesta"] if c in ultimas.columns]
        st.dataframe(
            ultimas[columnas_respuestas].head(20),
            use_container_width=True,
            hide_index=True
        )

# =========================
# VALIDACIÓN DE ARCHIVOS
# =========================

st.divider()
st.subheader("🧩 Estado de archivos")

archivos = {
    "pedidos.db": os.path.exists(DB_PATH),
    "menu_kiriko.csv": os.path.exists(MENU_PATH),
    "clientes_restaurante_lima.csv": os.path.exists(CLIENTES_PATH),
    "reservas.csv": os.path.exists(RESERVAS_PATH),
    "reclamos.csv": os.path.exists(RECLAMOS_PATH),
    "campanas.csv": os.path.exists(CAMPANAS_PATH),
}

estado_archivos = pd.DataFrame([
    {"archivo": k, "estado": "✅ encontrado" if v else "❌ falta"}
    for k, v in archivos.items()
])

st.dataframe(estado_archivos, use_container_width=True, hide_index=True)
