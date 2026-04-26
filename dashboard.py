import datetime
import html
import json
import os
import re
import sqlite3

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


st.set_page_config(page_title="MesaAI Dashboard", layout="wide")

DB_PATH = "pedidos.db"
MENU_PATH = "menu_kiriko.csv"
CLIENTES_PATH = "clientes_restaurante_lima.csv"
RESERVAS_PATH = "reservas.csv"
RECLAMOS_PATH = "reclamos.csv"
CAMPANAS_PATH = "campanas.csv"
HOY = datetime.date.today().isoformat()


@st.cache_data(ttl=10)
def cargar_csv(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=10)
def cargar_pedidos():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM pedidos", conn)
        conn.close()
        if not df.empty and "hora" in df.columns:
            df["hora"] = pd.to_datetime(df["hora"], errors="coerce")
            df["fecha"] = df["hora"].dt.date.astype(str)
        return df
    except Exception:
        return pd.DataFrame()


def filtrar_hoy(df):
    if df.empty or "fecha" not in df.columns:
        return df.iloc[0:0] if not df.empty else df
    return df[df["fecha"].astype(str) == HOY].copy()


def safe_text(value, default=""):
    if pd.isna(value):
        return default
    return html.escape(str(value))


def iniciales(nombre):
    partes = str(nombre).split()
    return html.escape("".join(p[0] for p in partes[:2]).upper() or "NA")


def detectar_plato(texto, menu):
    texto = str(texto).lower()
    if menu.empty or "plato" not in menu.columns:
        return "No identificado"
    for plato in menu["plato"].dropna().astype(str):
        plato_l = plato.lower()
        palabras = [p for p in plato_l.split() if len(p) > 3]
        if plato_l in texto or any(p in texto for p in palabras):
            return plato
    reglas = {
        "parrilla": "Parrilla Familiar",
        "lomo": "Lomo Saltado",
        "chaufa": "Chaufa Brasa",
        "pollo": "Pollo a la brasa",
        "ensalada": "Ensalada Kiriko",
        "tallarin": "Tallarín Saltado",
        "tallarín": "Tallarín Saltado",
        "inca": "Inca Kola",
        "chicha": "Chicha Morada",
    }
    for palabra, producto in reglas.items():
        if palabra in texto:
            return producto
    return "No identificado"


def valor_menu(plato, columna, default=0.0):
    if menu.empty or "plato" not in menu.columns or columna not in menu.columns:
        return default
    match = menu[menu["plato"].astype(str).str.lower() == str(plato).lower()]
    if match.empty:
        return default
    try:
        return float(match.iloc[0][columna])
    except Exception:
        return default


menu = cargar_csv(MENU_PATH)
clientes = cargar_csv(CLIENTES_PATH)
reservas = cargar_csv(RESERVAS_PATH)
reclamos = cargar_csv(RECLAMOS_PATH)
campanas = cargar_csv(CAMPANAS_PATH)
pedidos = cargar_pedidos()

pedidos_hoy = filtrar_hoy(pedidos)
reservas_hoy_df = filtrar_hoy(reservas)
reclamos_hoy_df = filtrar_hoy(reclamos)

if not pedidos.empty and {"mensaje", "respuesta"}.issubset(pedidos.columns):
    pedidos = pedidos.copy()
    pedidos["texto_total"] = pedidos["mensaje"].fillna("") + " " + pedidos["respuesta"].fillna("")
    pedidos["producto_detectado"] = pedidos["texto_total"].apply(lambda texto: detectar_plato(texto, menu))
    pedidos["pedido_confirmado"] = pedidos["respuesta"].fillna("").str.upper().str.contains("PEDIDO CONFIRMADO")
    pedidos["monto_estimado"] = pedidos["producto_detectado"].apply(lambda plato: valor_menu(plato, "precio"))
    pedidos["margen_estimado_soles"] = pedidos.apply(
        lambda row: row["monto_estimado"] * valor_menu(row["producto_detectado"], "margen_estimado"),
        axis=1,
    )
    pedidos["tiempo_cocina_min"] = pedidos["producto_detectado"].apply(lambda plato: valor_menu(plato, "tiempo_preparacion_min"))
    pedidos_hoy = filtrar_hoy(pedidos)

pedidos_confirmados = 0
ventas_estimadas = 0.0
interacciones = len(pedidos_hoy)
ticket_promedio = 0.0
margen_estimado = 0.0
tiempo_cocina = 0.0
conversion_bot = 0.0
if not pedidos_hoy.empty and "pedido_confirmado" in pedidos_hoy.columns:
    confirmados_mask = pedidos_hoy["pedido_confirmado"].fillna(False)
    pedidos_confirmados = int(confirmados_mask.sum())
    ventas_estimadas = float(pedidos_hoy.loc[confirmados_mask, "monto_estimado"].sum()) if "monto_estimado" in pedidos_hoy.columns else 0.0
    ticket_promedio = ventas_estimadas / pedidos_confirmados if pedidos_confirmados else 0.0
    margen_estimado = float(pedidos_hoy.loc[confirmados_mask, "margen_estimado_soles"].sum()) if "margen_estimado_soles" in pedidos_hoy.columns else 0.0
    tiempo_cocina = float(pedidos_hoy.loc[confirmados_mask, "tiempo_cocina_min"].sum()) if "tiempo_cocina_min" in pedidos_hoy.columns else 0.0
    conversion_bot = pedidos_confirmados / interacciones if interacciones else 0.0

reclamos_hoy = len(reclamos_hoy_df)
reclamos_abiertos = 0
reclamos_alta = 0
if not reclamos_hoy_df.empty:
    if "estado" in reclamos_hoy_df.columns:
        reclamos_abiertos = int(reclamos_hoy_df["estado"].isin(["pendiente", "en_revision"]).sum())
    if "prioridad" in reclamos_hoy_df.columns:
        reclamos_alta = int((reclamos_hoy_df["prioridad"].astype(str).str.lower() == "alta").sum())

reservas_hoy = len(reservas_hoy_df)
personas_esperadas = int(reservas_hoy_df["personas"].sum()) if not reservas_hoy_df.empty and "personas" in reservas_hoy_df.columns else 0
reservas_pendientes = int((reservas_hoy_df["estado"] == "pendiente").sum()) if not reservas_hoy_df.empty and "estado" in reservas_hoy_df.columns else 0
reservas_confirmadas = int((reservas_hoy_df["estado"] == "confirmada").sum()) if not reservas_hoy_df.empty and "estado" in reservas_hoy_df.columns else 0
reservas_canceladas = int((reservas_hoy_df["estado"] == "cancelada").sum()) if not reservas_hoy_df.empty and "estado" in reservas_hoy_df.columns else 0
hora_pico_reservas = "N/D"
if not reservas_hoy_df.empty and "hora" in reservas_hoy_df.columns:
    moda_hora = reservas_hoy_df["hora"].astype(str).str.slice(0, 2).mode()
    if not moda_hora.empty:
        hora_pico_reservas = f"{moda_hora.iloc[0]}:00"

clientes_activos = int((clientes["estado"] == "activo").sum()) if not clientes.empty and "estado" in clientes.columns else 0
clientes_riesgo = int((clientes["estado"] == "en_riesgo").sum()) if not clientes.empty and "estado" in clientes.columns else 0
clientes_nuevos = int((clientes["estado"] == "nuevo").sum()) if not clientes.empty and "estado" in clientes.columns else 0
ticket_clientes = float(clientes["ticket_promedio"].mean()) if not clientes.empty and "ticket_promedio" in clientes.columns else 0.0
frecuencia_promedio = float(clientes["frecuencia_mensual"].mean()) if not clientes.empty and "frecuencia_mensual" in clientes.columns else 0.0
campanas_activas = int((campanas["estado"] == "activa").sum()) if not campanas.empty and "estado" in campanas.columns else 0
ventas_campanas = float(campanas["ventas_atribuidas"].sum()) if not campanas.empty and "ventas_atribuidas" in campanas.columns else 0.0
conversion_promedio = float(campanas["tasa_conversion"].mean()) if not campanas.empty and "tasa_conversion" in campanas.columns else 0.0
mejor_campana = "N/D"
if not campanas.empty and "ventas_atribuidas" in campanas.columns:
    mejor_campana = str(campanas.sort_values("ventas_atribuidas", ascending=False).iloc[0].get("nombre", "N/D"))
promocion_label = mejor_campana if mejor_campana != "N/D" else "Sin campaña"
tiempo_preparacion_promedio = float(menu["tiempo_preparacion_min"].mean()) if not menu.empty and "tiempo_preparacion_min" in menu.columns else 0.0

categorias = []
if not menu.empty and "categoria" in menu.columns:
    categorias = menu["categoria"].dropna().astype(str).drop_duplicates().head(8).tolist()
categoria_iconos = ["🍗", "🥩", "🍝", "🍛", "🥗", "🍚", "🥤", "🍰"]
categorias_html = "\n".join(
    f'<div class="cat-pill {"active" if i == 0 else ""}"><span class="cat-emoji">{categoria_iconos[i % len(categoria_iconos)]}</span>{safe_text(cat)}</div>'
    for i, cat in enumerate(categorias)
) or '<div class="empty-state">No hay categorías registradas en el menú.</div>'

favoritos = clientes["plato_favorito"].value_counts() if not clientes.empty and "plato_favorito" in clientes.columns else pd.Series(dtype=int)
platos_base = []
if not favoritos.empty and not menu.empty and "plato" in menu.columns:
    for plato, pedidos_count in favoritos.head(6).items():
        match = menu[menu["plato"].astype(str).str.lower() == str(plato).lower()]
        precio = float(match.iloc[0]["precio"]) if not match.empty and "precio" in match.columns else 0.0
        popularidad = str(match.iloc[0].get("popularidad", "sin dato")) if not match.empty else "sin dato"
        platos_base.append((str(plato), precio, int(pedidos_count), popularidad))
elif not menu.empty and {"plato", "precio"}.issubset(menu.columns):
    menu_orden = menu.copy()
    if "popularidad" in menu_orden.columns:
        orden_popularidad = {"alta": 0, "media": 1, "baja": 2}
        menu_orden["_orden_popularidad"] = menu_orden["popularidad"].astype(str).str.lower().map(orden_popularidad).fillna(3)
        menu_orden = menu_orden.sort_values("_orden_popularidad")
    for _, row in menu_orden.head(6).iterrows():
        platos_base.append((str(row.get("plato", "Plato")), float(row.get("precio", 0) or 0), 0, str(row.get("popularidad", "sin dato"))))

plato_iconos = ["🍚", "🥩", "🍛", "🍜", "🍗", "🥗"]
platos_html = "\n".join(
    f"""
    <div class="plato-card">
      {'<div class="plato-badge">Top</div>' if i == 0 else ''}
      <div class="plato-emoji">{plato_iconos[i % len(plato_iconos)]}</div>
      <div class="plato-name">{safe_text(plato)}</div>
      <div class="plato-from">Desde</div>
      <div class="plato-price">S/ {precio:.2f}</div>
      <div class="plato-footer">
        <div class="stars">Popularidad: <span style="color:var(--text3)">{safe_text(popularidad)}</span></div>
        <div class="plato-sales">{pedidos_count} favoritos</div>
      </div>
    </div>
    """
    for i, (plato, precio, pedidos_count, popularidad) in enumerate(platos_base)
) or '<div class="empty-state">No hay platos registrados para mostrar.</div>'

estado_counts = clientes["estado"].value_counts() if not clientes.empty and "estado" in clientes.columns else pd.Series(dtype=int)
clientes_labels = ["Activos", "En riesgo", "Nuevos"]
clientes_chart_data = [
    int(estado_counts.get("activo", 0)),
    int(estado_counts.get("en_riesgo", 0)),
    int(estado_counts.get("nuevo", 0)),
]
platos_chart_labels = [str(x)[:12] for x in favoritos.head(7).index.tolist()]
platos_chart_data = [int(x) for x in favoritos.head(7).tolist()]

estado_class = {
    "resuelto": ("s-res", "var(--green)"),
    "pendiente": ("s-pend", "var(--yellow)"),
    "en_revision": ("s-rev", "var(--blue)"),
}
reclamos_rows = []
for _, row in reclamos_hoy_df.head(6).iterrows():
    estado = str(row.get("estado", "")).lower()
    clase, color = estado_class.get(estado, ("s-rev", "var(--blue)"))
    estado_label = estado.replace("_", " ") or "sin estado"
    prioridad = str(row.get("prioridad", "")).lower()
    prioridad_color = "var(--red)" if prioridad == "alta" else "var(--yellow)"
    nombre = row.get("cliente", "Cliente")
    reclamos_rows.append(
        f"""
        <tr>
          <td><div style="display:flex;align-items:center;gap:8px"><div class="avatar-sm" style="background:var(--red-soft);color:var(--red)">{iniciales(nombre)}</div>{safe_text(nombre)}</div></td>
          <td>{safe_text(row.get("tipo", ""))}</td>
          <td>{safe_text(row.get("descripcion", ""))}</td>
          <td><span class="status-badge {clase}"><span class="dot" style="background:{color}"></span>{safe_text(estado_label)}</span></td>
          <td>{safe_text(row.get("canal", ""))}</td>
          <td style="color:{prioridad_color}">{safe_text(prioridad)}</td>
        </tr>
        """
    )
reclamos_html = "\n".join(reclamos_rows) or '<tr><td colspan="6">No hay reclamos para hoy.</td></tr>'

riesgo_df = clientes[clientes["estado"] == "en_riesgo"].copy() if not clientes.empty and "estado" in clientes.columns else pd.DataFrame()
riesgo_rows = []
for _, row in riesgo_df.head(5).iterrows():
    riesgo_rows.append(
        f"""
        <div class="risk-item">
          <div class="risk-avatar">{iniciales(row.get("nombre", ""))}</div>
          <div><div class="risk-name">{safe_text(row.get("nombre", ""))}</div><div class="risk-meta">Última visita: {safe_text(row.get("fecha_ultima_visita", ""))} · {safe_text(row.get("frecuencia_mensual", "0"))} vez/mes</div></div>
          <div style="text-align:right;margin-left:auto"><div class="risk-ticket">S/ {float(row.get("ticket_promedio", 0) or 0):.2f}</div><div class="risk-plato">{safe_text(row.get("plato_favorito", ""))}</div></div>
        </div>
        """
    )
riesgo_html = "\n".join(riesgo_rows) or '<div class="risk-item"><div class="risk-meta">No hay clientes en riesgo registrados.</div></div>'

pedidos_confirmados_df = pedidos[pedidos["pedido_confirmado"] == True].copy() if not pedidos.empty and "pedido_confirmado" in pedidos.columns else pd.DataFrame()
pedido_activo = pedidos_confirmados_df.sort_values("hora", ascending=False).head(1) if not pedidos_confirmados_df.empty and "hora" in pedidos_confirmados_df.columns else pedidos_confirmados_df.head(1)
cart_items = []
pedido_activo_label = "Sin pedido confirmado"
if not pedido_activo.empty:
    pedido_row = pedido_activo.iloc[0]
    pedido_activo_label = f"Orden #{safe_text(pedido_row.get('id', ''))}" if "id" in pedido_activo.columns else "Último pedido confirmado"
    producto = pedido_row.get("producto_detectado", "No identificado")
    precio = float(pedido_row.get("monto_estimado", 0) or 0)
    if producto and str(producto) != "No identificado":
        cart_items.append(
            {
                "producto": str(producto),
                "precio": precio,
                "cantidad": 1,
                "cliente": str(pedido_row.get("cliente", "")),
                "agente": str(pedido_row.get("agente", "")),
            }
        )

subtotal = sum(item["precio"] * item["cantidad"] for item in cart_items)
delivery = 0.0
descuento = 0.0
total = subtotal
cart_html = "\n".join(
    f"""
    <div class="cart-item"><div class="cart-img">{plato_iconos[i % len(plato_iconos)]}</div><div class="cart-info"><div class="cart-name">{safe_text(item["producto"])}</div><div class="cart-sub">{safe_text(item["cliente"])} · {safe_text(item["agente"])}</div><div class="qty-ctrl"><span class="qty-num">Cantidad registrada: {item["cantidad"]}</span></div></div></div>
    """
    for i, item in enumerate(cart_items)
) or '<div class="empty-state">No hay pedido confirmado para mostrar como pedido activo.</div>'


def mini_stat(icono, label, value, sub="", color="var(--blue)", bg="var(--blue-soft)"):
    return f"""
    <div class="mini-stat">
      <div class="mini-icon" style="background:{bg};color:{color}">{icono}</div>
      <div><div class="mini-label">{safe_text(label)}</div><div class="mini-value">{safe_text(value)}</div><div class="mini-sub">{safe_text(sub)}</div></div>
    </div>
    """


def progress_items(series, empty_text):
    if series is None or len(series) == 0:
        return f'<div class="empty-state">{safe_text(empty_text)}</div>'
    max_value = max(float(series.max()), 1.0)
    items = []
    for name, value in series.head(6).items():
        numeric_value = float(value)
        pct = int((numeric_value / max_value) * 100)
        shown_value = f"{numeric_value:.2f}" if numeric_value % 1 else f"{numeric_value:.0f}"
        items.append(
            f"""
            <div class="progress-item">
              <div class="progress-top"><span>{safe_text(name)}</span><strong>{shown_value}</strong></div>
              <div class="progress-track"><div class="progress-fill" style="width:{pct}%"></div></div>
            </div>
            """
        )
    return "\n".join(items)


productos_mencionados = (
    pedidos_hoy[pedidos_hoy["producto_detectado"] != "No identificado"]["producto_detectado"].value_counts()
    if not pedidos_hoy.empty and "producto_detectado" in pedidos_hoy.columns
    else pd.Series(dtype=int)
)
agentes_uso = pedidos_hoy["agente"].value_counts() if not pedidos_hoy.empty and "agente" in pedidos_hoy.columns else pd.Series(dtype=int)
top_plato = productos_mencionados.index[0] if not productos_mencionados.empty else (platos_base[0][0] if platos_base else "")
cocina_recomendacion = (
    f"{safe_text(top_plato)} es el más mencionado. Refuerza stock para la hora pico."
    if top_plato
    else "No hay producto más mencionado todavía. Registra pedidos para generar recomendaciones."
)

extra_kpis_html = "\n".join(
    [
        mini_stat("💬", "Interacciones bot", str(interacciones), "mensajes de hoy", "var(--blue)", "var(--blue-soft)"),
        mini_stat("👥", "Personas esperadas", str(personas_esperadas), "en reservas", "var(--purple)", "var(--purple-soft)"),
        mini_stat("⏳", "Reservas pendientes", str(reservas_pendientes), "por confirmar", "var(--yellow)", "var(--yellow-soft)"),
        mini_stat("💰", "Margen estimado", f"S/ {margen_estimado:,.2f}", "pedidos confirmados", "var(--green)", "var(--green-soft)"),
        mini_stat("📣", "Ventas campañas", f"S/ {ventas_campanas:,.2f}", f"{conversion_promedio:.1%} conversión", "var(--red)", "var(--red-soft)"),
        mini_stat("🧾", "Ticket promedio", f"S/ {ticket_promedio:,.2f}", "por pedido", "var(--blue)", "var(--blue-soft)"),
    ]
)

operacion_html = f"""
<div>
  <div class="sec-header" style="margin-bottom:12px">
    <div><div class="sec-title">Operación de hoy</div><div class="sec-sub">Productos, agentes, cocina y conversión</div></div>
  </div>
  <div class="ops-grid">
    <div class="chart-card"><div class="chart-title">Productos más mencionados</div>{progress_items(productos_mencionados, "Aún no hay productos detectados para esta fecha.")}</div>
    <div class="chart-card"><div class="chart-title">Uso por agente</div>{progress_items(agentes_uso, "Aún no hay interacciones por agente.")}</div>
    <div class="chart-card"><div class="chart-title">Preparación estimada</div><div class="big-number">{tiempo_cocina:.0f} min</div><div class="muted-copy">Calculado con pedidos confirmados y tiempo del menú.</div></div>
    <div class="chart-card"><div class="chart-title">Conversión del bot</div><div class="big-number">{conversion_bot:.1%}</div><div class="muted-copy">Pedidos confirmados / interacciones del bot.</div></div>
  </div>
</div>
"""

reservas_rows = []
for _, row in reservas_hoy_df.sort_values("hora").head(8).iterrows() if not reservas_hoy_df.empty and "hora" in reservas_hoy_df.columns else reservas_hoy_df.head(8).iterrows():
    estado = str(row.get("estado", "")).lower()
    clase = {"confirmada": "s-res", "pendiente": "s-pend", "cancelada": "s-red"}.get(estado, "s-rev")
    reservas_rows.append(
        f"""
        <tr>
          <td>{safe_text(row.get("hora", ""))}</td><td>{safe_text(row.get("cliente", ""))}</td><td>{safe_text(row.get("personas", ""))}</td>
          <td><span class="status-badge {clase}">{safe_text(estado)}</span></td><td>{safe_text(row.get("zona", ""))}</td><td>{safe_text(row.get("canal", ""))}</td>
        </tr>
        """
    )
reservas_table_html = "\n".join(reservas_rows) or '<tr><td colspan="6">No hay reservas para esta fecha.</td></tr>'
reservas_section_html = f"""
<div>
  <div class="sec-header" style="margin-bottom:12px">
    <div><div class="sec-title">Reservas</div><div class="sec-sub">{reservas_confirmadas} confirmadas · {reservas_pendientes} pendientes · {reservas_canceladas} canceladas · Hora pico {hora_pico_reservas}</div></div>
  </div>
  <div class="mini-grid" style="margin-bottom:12px">
    {mini_stat("📅", "Reservas del día", str(reservas_hoy), "hoy", "var(--blue)", "var(--blue-soft)")}
    {mini_stat("👥", "Personas esperadas", str(personas_esperadas), "asistencia", "var(--purple)", "var(--purple-soft)")}
    {mini_stat("⏳", "Pendientes", str(reservas_pendientes), "confirmación", "var(--yellow)", "var(--yellow-soft)")}
    {mini_stat("🕘", "Hora pico", hora_pico_reservas, "estimada", "var(--red)", "var(--red-soft)")}
  </div>
  <div class="table-wrap"><table class="data-table"><thead><tr><th>Hora</th><th>Cliente</th><th>Personas</th><th>Estado</th><th>Zona</th><th>Canal</th></tr></thead><tbody>{reservas_table_html}</tbody></table></div>
</div>
"""

campanas_rows = []
for _, row in campanas.head(6).iterrows():
    campanas_rows.append(
        f"""
        <tr><td>{safe_text(row.get("nombre", ""))}</td><td>{safe_text(row.get("segmento", ""))}</td><td>{safe_text(row.get("canal", ""))}</td><td>{safe_text(row.get("oferta", ""))}</td><td>{float(row.get("tasa_conversion", 0) or 0):.1%}</td><td>S/ {float(row.get("ventas_atribuidas", 0) or 0):,.2f}</td><td>{safe_text(row.get("estado", ""))}</td></tr>
        """
    )
campanas_html = "\n".join(campanas_rows) or '<tr><td colspan="7">No hay campañas cargadas.</td></tr>'
campanas_section_html = f"""
<div>
  <div class="sec-header" style="margin-bottom:12px">
    <div><div class="sec-title">Campañas y recompra</div><div class="sec-sub">{campanas_activas} activas · mejor campaña: {safe_text(mejor_campana)}</div></div>
  </div>
  <div class="table-wrap"><table class="data-table"><thead><tr><th>Nombre</th><th>Segmento</th><th>Canal</th><th>Oferta</th><th>Conv.</th><th>Ventas</th><th>Estado</th></tr></thead><tbody>{campanas_html}</tbody></table></div>
</div>
"""

menu_vista = menu.copy()
if not menu_vista.empty and {"precio", "margen_estimado"}.issubset(menu_vista.columns):
    menu_vista["ganancia_estimada"] = menu_vista["precio"] * menu_vista["margen_estimado"]
margen_top_series = menu_vista.sort_values("ganancia_estimada", ascending=False).set_index("plato")["ganancia_estimada"].head(6) if not menu_vista.empty and "ganancia_estimada" in menu_vista.columns else pd.Series(dtype=float)
tiempo_top_series = menu_vista.sort_values("tiempo_preparacion_min", ascending=False).set_index("plato")["tiempo_preparacion_min"].head(6) if not menu_vista.empty and "tiempo_preparacion_min" in menu_vista.columns else pd.Series(dtype=float)
menu_rows = []
for _, row in menu.head(8).iterrows():
    menu_rows.append(
        f"<tr><td>{safe_text(row.get('categoria', ''))}</td><td>{safe_text(row.get('plato', ''))}</td><td>S/ {float(row.get('precio', 0) or 0):.2f}</td><td>{float(row.get('margen_estimado', 0) or 0):.0%}</td><td>{float(row.get('tiempo_preparacion_min', 0) or 0):.0f} min</td><td>{safe_text(row.get('popularidad', ''))}</td></tr>"
    )
menu_table_html = "\n".join(menu_rows) or '<tr><td colspan="6">No hay menú cargado.</td></tr>'
menu_section_html = f"""
<div>
  <div class="sec-header" style="margin-bottom:12px">
    <div><div class="sec-title">Menú y rentabilidad</div><div class="sec-sub">Margen, preparación y popularidad del menú</div></div>
  </div>
  <div class="ops-grid" style="margin-bottom:12px">
    <div class="chart-card"><div class="chart-title">Platos de mayor margen</div>{progress_items(margen_top_series.round(2), "Faltan datos de margen.")}</div>
    <div class="chart-card"><div class="chart-title">Tiempo de preparación</div>{progress_items(tiempo_top_series.round(0), "Falta tiempo de preparación.")}</div>
  </div>
  <div class="table-wrap"><table class="data-table"><thead><tr><th>Categoría</th><th>Plato</th><th>Precio</th><th>Margen</th><th>Tiempo</th><th>Popularidad</th></tr></thead><tbody>{menu_table_html}</tbody></table></div>
</div>
"""

interacciones_rows = []
ultimas = pedidos.sort_values("hora", ascending=False).head(8) if not pedidos.empty and "hora" in pedidos.columns else pedidos.head(8)
for _, row in ultimas.iterrows():
    interacciones_rows.append(
        f"<tr><td>{safe_text(row.get('hora', ''))}</td><td>{safe_text(row.get('cliente', ''))}</td><td>{safe_text(row.get('agente', ''))}</td><td>{safe_text(row.get('mensaje', ''))}</td><td>{safe_text(row.get('producto_detectado', ''))}</td><td>{'sí' if bool(row.get('pedido_confirmado', False)) else 'no'}</td></tr>"
    )
interacciones_html = "\n".join(interacciones_rows) or '<tr><td colspan="6">Todavía no hay interacciones registradas.</td></tr>'

archivos = {
    "pedidos.db": os.path.exists(DB_PATH),
    "menu_kiriko.csv": os.path.exists(MENU_PATH),
    "clientes_restaurante_lima.csv": os.path.exists(CLIENTES_PATH),
    "reservas.csv": os.path.exists(RESERVAS_PATH),
    "reclamos.csv": os.path.exists(RECLAMOS_PATH),
    "campanas.csv": os.path.exists(CAMPANAS_PATH),
}
archivos_html = "\n".join(
    f'<div class="file-pill {"ok" if exists else "bad"}"><span>{"●" if exists else "×"}</span>{safe_text(name)}</div>'
    for name, exists in archivos.items()
)
interacciones_section_html = f"""
<div>
  <div class="sec-header" style="margin-bottom:12px">
    <div><div class="sec-title">Últimas interacciones del bot</div><div class="sec-sub">Mensajes recientes registrados en pedidos.db</div></div>
  </div>
  <div class="table-wrap"><table class="data-table"><thead><tr><th>Hora</th><th>Cliente</th><th>Agente</th><th>Mensaje</th><th>Producto</th><th>Confirmado</th></tr></thead><tbody>{interacciones_html}</tbody></table></div>
</div>
<div>
  <div class="sec-header" style="margin-bottom:12px">
    <div><div class="sec-title">Estado de archivos</div><div class="sec-sub">Validación de fuentes locales del dashboard</div></div>
  </div>
  <div class="file-grid">{archivos_html}</div>
</div>
"""

st.markdown(
    """
    <style>
    .stApp {
        background: #0d0d10;
    }
    .block-container {
        padding: 0;
        max-width: 100%;
    }
    header[data-testid="stHeader"] {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

dashboard_html = r"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MesaAI — Panel del Dueño · Kiriko</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
  *{box-sizing:border-box;margin:0;padding:0}
  :root{
    --bg:#0d0d10;--bg2:#131318;--bg3:#1a1a22;--bg4:#21212c;
    --card:#1e1e28;--card2:#252530;
    --red:#e63946;--red2:#ff4d5a;--red-soft:rgba(230,57,70,0.15);
    --green:#22c55e;--green-soft:rgba(34,197,94,0.12);
    --yellow:#f59e0b;--yellow-soft:rgba(245,158,11,0.12);
    --blue:#3b82f6;--blue-soft:rgba(59,130,246,0.12);
    --purple:#a855f7;--purple-soft:rgba(168,85,247,0.12);
    --text:#f0eeff;--text2:#9d9ab5;--text3:#6b6888;
    --border:rgba(255,255,255,0.06);
    --font:'Outfit',sans-serif;
  }
  html,body{height:100%;background:var(--bg);font-family:var(--font);color:var(--text)}
  body{display:flex;overflow:hidden}
  .sidebar{width:72px;background:var(--bg2);border-right:1px solid var(--border);display:flex;flex-direction:column;align-items:center;padding:16px 0;gap:6px;flex-shrink:0;height:100vh}
  .logo{width:42px;height:42px;border-radius:14px;background:linear-gradient(135deg,var(--red),#ff8a3d);display:flex;align-items:center;justify-content:center;font-size:20px;margin-bottom:12px;box-shadow:0 8px 20px rgba(230,57,70,0.35)}
  .logo::before{content:"🍗"}
  .nav-item{width:46px;height:46px;border-radius:14px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;cursor:pointer;transition:all .2s;color:var(--text3);font-size:9px;font-weight:600;letter-spacing:.3px;text-transform:uppercase}
  .nav-item:hover{background:var(--bg3);color:var(--text2)}
  .nav-item.active{background:var(--red-soft);color:var(--red)}
  .nav-icon{font-size:18px;line-height:1}
  .nav-sep{width:32px;height:1px;background:var(--border);margin:6px 0}
  .main{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0;height:100vh}
  .topbar{background:var(--bg2);border-bottom:1px solid var(--border);padding:14px 20px;display:flex;align-items:center;gap:12px;flex-shrink:0}
  .search-box{flex:1;max-width:380px;position:relative}
  .search-box input{width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:12px;padding:10px 14px 10px 38px;color:var(--text);font-size:13px;font-family:var(--font);outline:none;transition:border-color .2s}
  .search-box input::placeholder{color:var(--text3)}
  .search-box input:focus{border-color:rgba(230,57,70,0.4)}
  .search-box .si{position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--text3);font-size:15px}
  .search-box .si::before{content:"🔎"}
  .date-chip{background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:8px 14px;font-size:12px;color:var(--text2);font-weight:600}
  .refresh-btn{background:var(--red);border:none;border-radius:10px;padding:8px 14px;color:#fff;font-size:12px;font-weight:700;cursor:pointer;font-family:var(--font);transition:opacity .2s}
  .refresh-btn:hover{opacity:.85}
  .content{flex:1;overflow-y:auto;padding:20px;display:flex;gap:20px;min-height:0}
  .content::-webkit-scrollbar{width:4px}
  .content::-webkit-scrollbar-track{background:transparent}
  .content::-webkit-scrollbar-thumb{background:var(--bg4);border-radius:4px}
  .left-col{flex:1;display:flex;flex-direction:column;gap:18px;min-width:0}
  .sec-header{display:flex;align-items:flex-start;justify-content:space-between}
  .sec-title{font-size:16px;font-weight:700;color:var(--text)}
  .sec-sub{font-size:11px;color:var(--red);font-weight:600;margin-top:2px}
  .view-more{font-size:12px;color:var(--text3);cursor:pointer;background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:5px 10px;font-family:var(--font);transition:all .2s;white-space:nowrap}
  .view-more:hover{color:var(--text);border-color:var(--red-soft)}
  .kpi-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
  .kpi{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:14px 16px;transition:transform .2s,border-color .2s}
  .kpi:hover{transform:translateY(-2px);border-color:rgba(230,57,70,0.2)}
  .kpi-icon{width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:16px;margin-bottom:10px}
  .kpi-label{font-size:11px;color:var(--text3);font-weight:600;text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px}
  .kpi-value{font-size:22px;font-weight:800;color:var(--text);line-height:1}
  .kpi-sub{font-size:11px;color:var(--text3);margin-top:3px}
  .cats{display:flex;gap:10px;overflow-x:auto;padding-bottom:4px}
  .cats::-webkit-scrollbar{display:none}
  .cat-pill{background:var(--card);border:1px solid var(--border);border-radius:50px;padding:8px 16px;font-size:12px;font-weight:600;color:var(--text2);cursor:pointer;white-space:nowrap;transition:all .2s;display:flex;align-items:center;gap:6px}
  .cat-pill:hover,.cat-pill.active{background:var(--red-soft);border-color:rgba(230,57,70,0.3);color:var(--red)}
  .cat-emoji{font-size:18px}
  .platos-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
  .plato-card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:16px;cursor:pointer;transition:all .25s;position:relative;overflow:hidden}
  .plato-card::before{content:'';position:absolute;inset:0;border-radius:18px;background:radial-gradient(circle at 50% -20%,rgba(230,57,70,0.08),transparent 65%);pointer-events:none}
  .plato-card:hover{transform:translateY(-4px);border-color:rgba(230,57,70,0.3);box-shadow:0 16px 40px rgba(0,0,0,0.4)}
  .plato-emoji{font-size:52px;text-align:center;margin-bottom:10px;filter:drop-shadow(0 4px 12px rgba(0,0,0,0.5))}
  .plato-name{font-size:15px;font-weight:700;margin-bottom:2px}
  .plato-from{font-size:10px;color:var(--text3);text-transform:uppercase;letter-spacing:.4px;margin-bottom:6px}
  .plato-price{font-size:20px;font-weight:800;color:var(--text);margin-bottom:8px}
  .plato-footer{display:flex;align-items:center;justify-content:space-between}
  .stars{color:var(--yellow);font-size:11px}
  .plato-sales{font-size:10px;color:var(--text3)}
  .plato-badge{position:absolute;top:12px;right:12px;background:var(--red);color:#fff;font-size:9px;font-weight:800;padding:3px 8px;border-radius:20px;text-transform:uppercase;letter-spacing:.4px}
  .table-wrap{background:var(--card);border:1px solid var(--border);border-radius:16px;overflow:hidden}
  .data-table{width:100%;border-collapse:collapse;font-size:12px}
  .data-table th{background:var(--bg4);color:var(--text3);font-weight:600;font-size:10px;text-transform:uppercase;letter-spacing:.5px;padding:10px 14px;text-align:left;border-bottom:1px solid var(--border)}
  .data-table td{padding:10px 14px;border-bottom:1px solid rgba(255,255,255,0.03);color:var(--text2)}
  .data-table tr:last-child td{border-bottom:none}
  .data-table tr:hover td{background:rgba(255,255,255,0.02);color:var(--text)}
  .avatar-sm{width:28px;height:28px;border-radius:9px;display:inline-flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;flex-shrink:0}
  .status-badge{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:20px;font-size:10px;font-weight:700;white-space:nowrap}
  .s-res{background:var(--green-soft);color:var(--green)}
  .s-pend{background:var(--yellow-soft);color:var(--yellow)}
  .s-rev{background:var(--blue-soft);color:var(--blue)}
  .dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
  .right-panel{width:290px;flex-shrink:0;display:flex;flex-direction:column;gap:16px}
  .delivery-card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:18px}
  .delivery-header{font-size:11px;font-weight:800;letter-spacing:.8px;text-transform:uppercase;color:var(--text3);margin-bottom:12px}
  .delivery-addr{display:flex;align-items:flex-start;gap:8px;margin-bottom:8px}
  .delivery-addr .ic{color:var(--red);font-size:14px;margin-top:1px}
  .delivery-addr .ic::before{content:"📍"}
  .delivery-addr .txt{font-size:12px;color:var(--text2);line-height:1.4}
  .delivery-time{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--text3)}
  .cart-card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:18px;flex:1}
  .cart-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
  .cart-title{font-size:15px;font-weight:700}
  .order-id{font-size:11px;color:var(--text3)}
  .tabs{display:flex;gap:4px;background:var(--bg3);border-radius:10px;padding:3px;margin-bottom:16px}
  .tab{flex:1;text-align:center;padding:6px 4px;font-size:11px;font-weight:700;border-radius:8px;cursor:pointer;color:var(--text3);transition:all .2s}
  .tab.active{background:var(--red);color:#fff}
  .cart-item{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--border)}
  .cart-item:last-of-type{border-bottom:none}
  .cart-img{width:44px;height:44px;border-radius:12px;background:var(--bg3);display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0}
  .cart-info{flex:1;min-width:0}
  .cart-name{font-size:13px;font-weight:700;margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .cart-sub{font-size:10px;color:var(--text3)}
  .qty-ctrl{display:flex;align-items:center;gap:6px;margin-top:6px}
  .qty-btn{width:20px;height:20px;border-radius:6px;background:var(--bg4);border:none;color:var(--text2);font-size:13px;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;font-family:var(--font)}
  .qty-btn:hover{background:var(--red);color:#fff}
  .qty-num{font-size:12px;font-weight:700;min-width:14px;text-align:center}
  .promo-row{display:flex;gap:8px;margin:14px 0}
  .promo-input{flex:1;background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:8px 12px;font-size:12px;color:var(--text);font-family:var(--font);outline:none;min-width:0}
  .promo-input::placeholder{color:var(--text3)}
  .promo-btn{background:var(--bg4);border:1px solid var(--border);border-radius:10px;padding:8px 12px;font-size:11px;font-weight:800;color:var(--text2);cursor:pointer;font-family:var(--font);white-space:nowrap;letter-spacing:.4px}
  .total-rows{display:flex;flex-direction:column;gap:8px;margin-bottom:14px}
  .total-row{display:flex;justify-content:space-between;font-size:12px;color:var(--text2)}
  .total-final{display:flex;justify-content:space-between;font-size:15px;font-weight:800;color:var(--text);padding-top:10px;border-top:1px solid var(--border)}
  .confirm-btn{width:100%;background:var(--red);border:none;border-radius:12px;padding:13px;color:#fff;font-size:14px;font-weight:800;cursor:pointer;font-family:var(--font);letter-spacing:.3px;transition:all .2s;box-shadow:0 6px 20px rgba(230,57,70,0.35);margin-top:14px}
  .confirm-btn:hover{background:var(--red2);transform:translateY(-1px)}
  .charts-row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
  .chart-card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:16px}
  .chart-title{font-size:13px;font-weight:700;margin-bottom:12px}
  .mini-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
  .mini-stat{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:12px;display:flex;gap:10px;align-items:center;transition:transform .2s,border-color .2s}
  .mini-stat:hover{transform:translateY(-2px);border-color:rgba(230,57,70,0.22)}
  .mini-icon{width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0}
  .mini-label{font-size:10px;color:var(--text3);font-weight:700;text-transform:uppercase;letter-spacing:.35px}
  .mini-value{font-size:15px;color:var(--text);font-weight:800;margin-top:2px}
  .mini-sub{font-size:10px;color:var(--text3);margin-top:1px}
  .ops-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
  .progress-item{display:flex;flex-direction:column;gap:6px;margin-bottom:11px}
  .progress-top{display:flex;justify-content:space-between;gap:10px;font-size:12px;color:var(--text2)}
  .progress-top strong{color:var(--text)}
  .progress-track{height:7px;background:var(--bg3);border-radius:20px;overflow:hidden}
  .progress-fill{height:100%;background:linear-gradient(90deg,var(--red),#ff8a3d);border-radius:20px}
  .big-number{font-size:34px;font-weight:850;color:var(--text);margin-top:8px}
  .muted-copy,.empty-state{font-size:12px;color:var(--text3);line-height:1.45}
  .s-red{background:var(--red-soft);color:var(--red)}
  .file-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
  .file-pill{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:11px 12px;color:var(--text2);font-size:12px;font-weight:700;display:flex;gap:8px;align-items:center}
  .file-pill.ok span{color:var(--green)}
  .file-pill.bad span{color:var(--red)}
  .risk-list{display:flex;flex-direction:column;gap:8px}
  .risk-item{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px 14px;display:flex;align-items:center;gap:12px;transition:border-color .2s}
  .risk-item:hover{border-color:rgba(245,158,11,0.3)}
  .risk-avatar{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;flex-shrink:0;background:var(--yellow-soft);color:var(--yellow)}
  .risk-name{font-size:13px;font-weight:700;margin-bottom:1px}
  .risk-meta{font-size:11px;color:var(--text3)}
  .risk-ticket{font-size:13px;font-weight:800;color:var(--text)}
  .risk-plato{font-size:10px;color:var(--text3);text-align:right}
  @media(max-width:1100px){
    body{overflow:auto}
    .content{flex-direction:column;overflow:visible}
    .main{height:auto;min-height:100vh;overflow:visible}
    .right-panel{width:100%;display:grid;grid-template-columns:repeat(3,1fr)}
  }
  @media(max-width:760px){
    body{display:block}
    .sidebar{width:100%;height:auto;flex-direction:row;overflow:auto;border-right:0;border-bottom:1px solid var(--border)}
    .main{height:auto}
    .topbar{flex-wrap:wrap}
    .search-box{max-width:none;min-width:100%}
    .kpi-strip,.platos-grid,.charts-row,.right-panel,.mini-grid,.ops-grid,.file-grid{grid-template-columns:1fr}
    .content{padding:14px}
  }
</style>
</head>
<body>
  <div class="sidebar">
    <div class="logo"></div>
    <div class="nav-item active"><span class="nav-icon">⊞</span>Panel</div>
    <div class="nav-item"><span class="nav-icon">◉</span>Pedidos</div>
    <div class="nav-item"><span class="nav-icon">◷</span>Reservas</div>
    <div class="nav-item"><span class="nav-icon">◎</span>Clientes</div>
    <div class="nav-sep"></div>
    <div class="nav-item"><span class="nav-icon">◇</span>Campañas</div>
    <div class="nav-item"><span class="nav-icon">!</span>Reclamos</div>
    <div class="nav-sep"></div>
    <div class="nav-item"><span class="nav-icon">⚙️</span>Config</div>
  </div>

  <div class="main">
    <div class="topbar">
      <div class="search-box">
        <span class="si"></span>
        <input placeholder="Buscar plato, cliente, reclamo...">
      </div>
      <div class="date-chip">Hoy — Kiriko Pollos &amp; Parrillas</div>
      <button class="refresh-btn">Actualizar</button>
    </div>

    <div class="content">
      <div class="left-col">
        <div>
          <div class="sec-header" style="margin-bottom:12px">
            <div>
              <div class="sec-title">Estado del negocio</div>
              <div class="sec-sub">Métricas en tiempo real</div>
            </div>
            <button class="view-more">Ver más →</button>
          </div>
          <div class="kpi-strip">
            <div class="kpi"><div class="kpi-icon" style="background:var(--red-soft);color:var(--red)">S/</div><div class="kpi-label">Ventas est.</div><div class="kpi-value">S/ 0</div><div class="kpi-sub">Hoy</div></div>
            <div class="kpi"><div class="kpi-icon" style="background:var(--green-soft);color:var(--green)">✅</div><div class="kpi-label">Pedidos conf.</div><div class="kpi-value">0</div><div class="kpi-sub">Confirmados</div></div>
            <div class="kpi"><div class="kpi-icon" style="background:var(--yellow-soft);color:var(--yellow)">⚠️</div><div class="kpi-label">Reclamos</div><div class="kpi-value">6</div><div class="kpi-sub">4 abiertos · 3 alta</div></div>
            <div class="kpi"><div class="kpi-icon" style="background:var(--blue-soft);color:var(--blue)">📅</div><div class="kpi-label">Reservas</div><div class="kpi-value">—</div><div class="kpi-sub">Hoy</div></div>
            <div class="kpi"><div class="kpi-icon" style="background:var(--purple-soft);color:var(--purple)">⚠</div><div class="kpi-label">En riesgo</div><div class="kpi-value">26</div><div class="kpi-sub">de 50 activos</div></div>
            <div class="kpi"><div class="kpi-icon" style="background:rgba(34,197,94,0.1);color:#22c55e">📣</div><div class="kpi-label">Campañas</div><div class="kpi-value">—</div><div class="kpi-sub">Activas</div></div>
          </div>
        </div>

        <div>
          <div class="sec-header" style="margin-bottom:10px">
            <div><div class="sec-title">Categorías del menú</div><div class="sec-sub">8 categorías disponibles</div></div>
          </div>
          <div class="cats">
            <div class="cat-pill active"><span class="cat-emoji">🍗</span>Pollo</div>
            <div class="cat-pill"><span class="cat-emoji">🥩</span>Parrillas</div>
            <div class="cat-pill"><span class="cat-emoji">🍝</span>Pastas</div>
            <div class="cat-pill"><span class="cat-emoji">🍛</span>Carnes</div>
            <div class="cat-pill"><span class="cat-emoji">🥗</span>Ensaladas</div>
            <div class="cat-pill"><span class="cat-emoji">🍚</span>Arroces</div>
            <div class="cat-pill"><span class="cat-emoji">🥤</span>Bebidas</div>
            <div class="cat-pill"><span class="cat-emoji">🍰</span>Postres</div>
          </div>
        </div>

        <div>
          <div class="sec-header" style="margin-bottom:12px">
            <div><div class="sec-title">Platos populares</div><div class="sec-sub">Los más pedidos esta semana</div></div>
            <button class="view-more">Ver más →</button>
          </div>
          <div class="platos-grid">
            __PLATOS_HTML__
          </div>
        </div>

        <div class="charts-row">
          <div class="chart-card"><div class="chart-title">Estado de clientes</div><canvas id="clientesChart" height="140"></canvas></div>
          <div class="chart-card"><div class="chart-title">Platos favoritos</div><canvas id="platosChart" height="140"></canvas></div>
        </div>

        <div>
          <div class="sec-header" style="margin-bottom:12px">
            <div><div class="sec-title">Reclamos y atención</div><div class="sec-sub">6 del día · 4 abiertos · 3 alta prioridad</div></div>
            <button class="view-more">Ver más →</button>
          </div>
          <div class="table-wrap">
            <table class="data-table">
              <thead><tr><th>Cliente</th><th>Tipo</th><th>Descripción</th><th>Estado</th><th>Canal</th><th>Prioridad</th></tr></thead>
              <tbody>
                <tr><td><div style="display:flex;align-items:center;gap:8px"><div class="avatar-sm" style="background:var(--green-soft);color:var(--green)">CP</div>Carlos Perez</div></td><td>demora</td><td>Pedido tardó más de 45 min</td><td><span class="status-badge s-res"><span class="dot" style="background:var(--green)"></span>resuelto</span></td><td>bot</td><td style="color:var(--yellow)">media</td></tr>
                <tr><td><div style="display:flex;align-items:center;gap:8px"><div class="avatar-sm" style="background:var(--red-soft);color:var(--red)">ML</div>María López</div></td><td>calidad</td><td>El pollo llegó frío</td><td><span class="status-badge s-pend"><span class="dot" style="background:var(--yellow)"></span>pendiente</span></td><td>whatsapp</td><td style="color:var(--red)">alta</td></tr>
                <tr><td><div style="display:flex;align-items:center;gap:8px"><div class="avatar-sm" style="background:var(--blue-soft);color:var(--blue)">LT</div>Luis Torres</div></td><td>atención</td><td>Sin respuesta en WhatsApp</td><td><span class="status-badge s-rev"><span class="dot" style="background:var(--blue)"></span>en revisión</span></td><td>whatsapp</td><td style="color:var(--yellow)">media</td></tr>
                <tr><td><div style="display:flex;align-items:center;gap:8px"><div class="avatar-sm" style="background:var(--red-soft);color:var(--red)">AR</div>Ana Ruiz</div></td><td>pedido incorrecto</td><td>Recibió papas en vez de ensalada</td><td><span class="status-badge s-pend"><span class="dot" style="background:var(--yellow)"></span>pendiente</span></td><td>bot</td><td style="color:var(--red)">alta</td></tr>
                <tr><td><div style="display:flex;align-items:center;gap:8px"><div class="avatar-sm" style="background:var(--green-soft);color:var(--green)">JM</div>Jose Mendoza</div></td><td>delivery</td><td>El repartidor llegó tarde</td><td><span class="status-badge s-res"><span class="dot" style="background:var(--green)"></span>resuelto</span></td><td>telefono</td><td style="color:var(--yellow)">media</td></tr>
                <tr><td><div style="display:flex;align-items:center;gap:8px"><div class="avatar-sm" style="background:var(--red-soft);color:var(--red)">SV</div>Sofia Vega</div></td><td>reserva</td><td>Mesa no estaba lista</td><td><span class="status-badge s-pend"><span class="dot" style="background:var(--yellow)"></span>pendiente</span></td><td>instagram</td><td style="color:var(--red)">alta</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <div class="sec-header" style="margin-bottom:12px">
            <div><div class="sec-title">⚠️ Clientes en riesgo</div><div class="sec-sub">26 clientes sin visita reciente — requieren reactivación</div></div>
            <button class="view-more">Ver todos →</button>
          </div>
          <div class="risk-list">
            <div class="risk-item"><div class="risk-avatar">CM</div><div><div class="risk-name">Carlos Medina</div><div class="risk-meta">Última visita: 2026-03-08 · 1 vez/mes</div></div><div style="text-align:right;margin-left:auto"><div class="risk-ticket">S/ 31</div><div class="risk-plato">Chaufa Brasa</div></div></div>
            <div class="risk-item"><div class="risk-avatar">MV</div><div><div class="risk-name">Marco Vega</div><div class="risk-meta">Última visita: 2026-04-01 · 1 vez/mes</div></div><div style="text-align:right;margin-left:auto"><div class="risk-ticket">S/ 28.5</div><div class="risk-plato">1/4 Pollo</div></div></div>
            <div class="risk-item"><div class="risk-avatar">JC</div><div><div class="risk-name">Jorge Castillo</div><div class="risk-meta">Última visita: 2026-02-27 · 1 vez/mes</div></div><div style="text-align:right;margin-left:auto"><div class="risk-ticket">S/ 30</div><div class="risk-plato">Tallarín Saltado</div></div></div>
            <div class="risk-item"><div class="risk-avatar">RV</div><div><div class="risk-name">Ricardo Vega</div><div class="risk-meta">Última visita: 2026-03-15 · 1 vez/mes</div></div><div style="text-align:right;margin-left:auto"><div class="risk-ticket">S/ 33</div><div class="risk-plato">Pollo Saltado</div></div></div>
            <div class="risk-item"><div class="risk-avatar">PH</div><div><div class="risk-name">Paula Herrera</div><div class="risk-meta">Última visita: 2026-02-20 · 1 vez/mes</div></div><div style="text-align:right;margin-left:auto"><div class="risk-ticket">S/ 27</div><div class="risk-plato">Ensalada Kiriko</div></div></div>
          </div>
        </div>
      </div>

      <div class="right-panel">
        <div class="delivery-card">
          <div class="delivery-header">Dirección de delivery</div>
          <div class="delivery-addr"><span class="ic"></span><span class="txt">Ca. Lima 491, Miraflores, Lima</span></div>
          <div class="delivery-time"><span>⏱️</span>__TIEMPO_PREPARACION__</div>
        </div>

        <div class="cart-card">
          <div class="cart-header"><span class="cart-title">Pedido activo</span><span class="order-id">__PEDIDO_ACTIVO_LABEL__</span></div>
          <div class="tabs"><div class="tab active">Delivery</div><div class="tab">Salón</div><div class="tab">Retiro</div></div>
          __CART_HTML__
          <div class="promo-row"><input class="promo-input" placeholder="Campaña activa" disabled><button class="promo-btn">__PROMOCION_LABEL__</button></div>
          <div class="total-rows"><div class="total-row"><span>Sub Total</span><span>__SUBTOTAL__</span></div><div class="total-row"><span>Delivery registrado</span><span>__DELIVERY__</span></div><div class="total-row" style="color:var(--green)"><span>Descuento registrado</span><span>__DESCUENTO__</span></div></div>
          <div class="total-final"><span>TOTAL</span><span>__TOTAL__</span></div>
          <button class="confirm-btn">Confirmar pedido</button>
        </div>

        <div class="delivery-card">
          <div class="delivery-header">MesaAI recomienda</div>
          <div style="display:flex;flex-direction:column;gap:10px;margin-top:4px">
            <div style="background:var(--green-soft);border-left:3px solid var(--green);border-radius:10px;padding:10px 12px;font-size:12px;color:var(--text2);line-height:1.5"><strong style="color:var(--green)">Cocina</strong><br>__COCINA_RECOMENDACION__</div>
            <div style="background:var(--yellow-soft);border-left:3px solid var(--yellow);border-radius:10px;padding:10px 12px;font-size:12px;color:var(--text2);line-height:1.5"><strong style="color:var(--yellow)">Fidelización</strong><br>__FIDELIZACION_RECOMENDACION__</div>
            <div style="background:var(--red-soft);border-left:3px solid var(--red);border-radius:10px;padding:10px 12px;font-size:12px;color:var(--text2);line-height:1.5"><strong style="color:var(--red)">Atención</strong><br>__ATENCION_RECOMENDACION__</div>
          </div>
        </div>
      </div>
    </div>
  </div>

<script>
const chartDefaults = {
  plugins:{legend:{display:false}},
  scales:{
    x:{grid:{color:'rgba(255,255,255,0.04)'},ticks:{color:'#6b6888',font:{size:10,family:'Outfit'}}},
    y:{grid:{color:'rgba(255,255,255,0.04)'},ticks:{color:'#6b6888',font:{size:10,family:'Outfit'}}}
  }
};

new Chart(document.getElementById('clientesChart'),{
  type:'bar',
  data:{
    labels:['Activos','En riesgo','Nuevos'],
    datasets:[{
      data:[50,26,24],
      backgroundColor:['rgba(59,130,246,0.7)','rgba(245,158,11,0.7)','rgba(34,197,94,0.7)'],
      borderColor:['#3b82f6','#f59e0b','#22c55e'],
      borderWidth:1,borderRadius:6
    }]
  },
  options:{...chartDefaults,responsive:true}
});

new Chart(document.getElementById('platosChart'),{
  type:'bar',
  data:{
    labels:['Chaufa B.','1/4 Pollo','Pollo B.','Parrilla','Lomo S.','Tallarín','Ensalada'],
    datasets:[{
      data:[16,11,11,11,7,6,5],
      backgroundColor:'rgba(59,130,246,0.65)',
      borderColor:'#3b82f6',
      borderWidth:1,borderRadius:6
    }]
  },
  options:{...chartDefaults,responsive:true}
});

document.querySelectorAll('.tab').forEach(t=>{
  t.addEventListener('click',()=>{
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
    t.classList.add('active');
  });
});

document.querySelectorAll('.cat-pill').forEach(p=>{
  p.addEventListener('click',()=>{
    document.querySelectorAll('.cat-pill').forEach(x=>x.classList.remove('active'));
    p.classList.add('active');
  });
});

document.querySelectorAll('.qty-btn').forEach(btn=>{
  btn.addEventListener('click',()=>{
    const ctrl=btn.parentElement;
    const num=ctrl.querySelector('.qty-num');
    let v=parseInt(num.textContent);
    if(btn.textContent==='−') v=Math.max(1,v-1);
    else v++;
    num.textContent=v;
  });
});

document.querySelectorAll('.nav-item').forEach(n=>{
  n.addEventListener('click',()=>{
    document.querySelectorAll('.nav-item').forEach(x=>x.classList.remove('active'));
    n.classList.add('active');
  });
});
</script>
</body>
</html>
"""

dashboard_html = dashboard_html.replace(
    '<div class="date-chip">Hoy — Kiriko Pollos &amp; Parrillas</div>',
    f'<div class="date-chip">{HOY} — Kiriko Pollos &amp; Parrillas</div>',
)
dashboard_html = dashboard_html.replace("__TIEMPO_PREPARACION__", f"{tiempo_preparacion_promedio:.0f} min preparación promedio")
dashboard_html = dashboard_html.replace("__PEDIDO_ACTIVO_LABEL__", pedido_activo_label)
dashboard_html = dashboard_html.replace("__PROMOCION_LABEL__", safe_text(promocion_label))
dashboard_html = dashboard_html.replace("__PLATOS_HTML__", platos_html)
dashboard_html = dashboard_html.replace("__CART_HTML__", cart_html)
dashboard_html = dashboard_html.replace("__SUBTOTAL__", f"S/ {subtotal:.2f}")
dashboard_html = dashboard_html.replace("__DELIVERY__", f"S/ {delivery:.2f}")
dashboard_html = dashboard_html.replace("__DESCUENTO__", f"−S/ {descuento:.2f}")
dashboard_html = dashboard_html.replace("__TOTAL__", f"S/ {total:.2f}")
dashboard_html = dashboard_html.replace("__COCINA_RECOMENDACION__", cocina_recomendacion)
dashboard_html = dashboard_html.replace("__FIDELIZACION_RECOMENDACION__", f"{clientes_riesgo} clientes en riesgo. Revisa campañas activas para reactivarlos.")
dashboard_html = dashboard_html.replace("__ATENCION_RECOMENDACION__", f"{reclamos_abiertos} reclamos abiertos, {reclamos_alta} de alta prioridad. Resolver antes del cierre.")
dashboard_html = dashboard_html.replace('<div class="kpi-value">S/ 0</div>', f'<div class="kpi-value">S/ {ventas_estimadas:,.2f}</div>', 1)
dashboard_html = dashboard_html.replace('<div class="kpi-value">0</div><div class="kpi-sub">Confirmados</div>', f'<div class="kpi-value">{pedidos_confirmados}</div><div class="kpi-sub">Confirmados</div>', 1)
dashboard_html = dashboard_html.replace('<div class="kpi-value">6</div><div class="kpi-sub">4 abiertos · 3 alta</div>', f'<div class="kpi-value">{reclamos_hoy}</div><div class="kpi-sub">{reclamos_abiertos} abiertos · {reclamos_alta} alta</div>', 1)
dashboard_html = dashboard_html.replace('<div class="kpi-value">—</div><div class="kpi-sub">Hoy</div>', f'<div class="kpi-value">{reservas_hoy}</div><div class="kpi-sub">Hoy</div>', 1)
dashboard_html = dashboard_html.replace('<div class="kpi-value">26</div><div class="kpi-sub">de 50 activos</div>', f'<div class="kpi-value">{clientes_riesgo}</div><div class="kpi-sub">de {clientes_activos} activos</div>', 1)
dashboard_html = dashboard_html.replace('<div class="kpi-value">—</div><div class="kpi-sub">Activas</div>', f'<div class="kpi-value">{campanas_activas}</div><div class="kpi-sub">Activas</div>', 1)

dashboard_html = dashboard_html.replace(
    '<div>\n          <div class="sec-header" style="margin-bottom:10px">\n            <div><div class="sec-title">Categorías del menú</div>',
    f'<div class="mini-grid">{extra_kpis_html}</div>\n\n        {operacion_html}\n\n        <div>\n          <div class="sec-header" style="margin-bottom:10px">\n            <div><div class="sec-title">Categorías del menú</div>',
    1,
)

dashboard_html = re.sub(
    r'<div class="sec-sub">8 categorías disponibles</div>',
    f'<div class="sec-sub">{len(categorias) if categorias else 0} categorías disponibles</div>',
    dashboard_html,
    count=1,
)
dashboard_html = re.sub(
    r'<div class="cats">.*?</div>\s*</div>\s*\n\n        <div>\n          <div class="sec-header" style="margin-bottom:12px">\n            <div><div class="sec-title">Platos populares</div>',
    f'<div class="cats">\n{categorias_html}\n          </div>\n        </div>\n\n        <div>\n          <div class="sec-header" style="margin-bottom:12px">\n            <div><div class="sec-title">Platos populares</div>',
    dashboard_html,
    flags=re.S,
    count=1,
)
dashboard_html = dashboard_html.replace(
    '<div>\n          <div class="sec-header" style="margin-bottom:12px">\n            <div><div class="sec-title">Reclamos y atención</div>',
    f'{reservas_section_html}\n\n        <div>\n          <div class="sec-header" style="margin-bottom:12px">\n            <div><div class="sec-title">Reclamos y atención</div>',
    1,
)

dashboard_html = dashboard_html.replace(
    '<div class="sec-sub">6 del día · 4 abiertos · 3 alta prioridad</div>',
    f'<div class="sec-sub">{reclamos_hoy} del día · {reclamos_abiertos} abiertos · {reclamos_alta} alta prioridad</div>',
)
dashboard_html = re.sub(
    r'<tbody>\s*<tr><td><div style="display:flex;align-items:center;gap:8px"><div class="avatar-sm".*?</tbody>',
    f'<tbody>\n{reclamos_html}\n              </tbody>',
    dashboard_html,
    flags=re.S,
    count=1,
)

dashboard_html = dashboard_html.replace(
    '<div class="sec-sub">26 clientes sin visita reciente — requieren reactivación</div>',
    f'<div class="sec-sub">{clientes_riesgo} clientes sin visita reciente — requieren reactivación</div>',
)
dashboard_html = re.sub(
    r'<div class="risk-list">.*?</div>\s*</div>\s*</div>\s*\n\n      <div class="right-panel">',
    f'<div class="risk-list">\n{riesgo_html}\n          </div>\n        </div>\n\n        {campanas_section_html}\n\n        {menu_section_html}\n\n        {interacciones_section_html}\n      </div>\n\n      <div class="right-panel">',
    dashboard_html,
    flags=re.S,
    count=1,
)

dashboard_html = dashboard_html.replace("labels:['Activos','En riesgo','Nuevos']", f"labels:{json.dumps(clientes_labels, ensure_ascii=False)}")
dashboard_html = dashboard_html.replace("data:[50,26,24]", f"data:{json.dumps(clientes_chart_data)}", 1)
dashboard_html = dashboard_html.replace("labels:['Chaufa B.','1/4 Pollo','Pollo B.','Parrilla','Lomo S.','Tallarín','Ensalada']", f"labels:{json.dumps(platos_chart_labels, ensure_ascii=False)}")
dashboard_html = dashboard_html.replace("data:[16,11,11,11,7,6,5]", f"data:{json.dumps(platos_chart_data)}", 1)

components.html(dashboard_html, height=920, scrolling=True)
