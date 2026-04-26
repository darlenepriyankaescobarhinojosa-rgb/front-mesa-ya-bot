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
        return None
    for plato in menu["plato"].dropna().astype(str):
        plato_l = plato.lower()
        palabras = [p for p in plato_l.split() if len(p) > 3]
        if plato_l in texto or any(p in texto for p in palabras):
            return plato
    return None


menu = cargar_csv(MENU_PATH)
clientes = cargar_csv(CLIENTES_PATH)
reservas = cargar_csv(RESERVAS_PATH)
reclamos = cargar_csv(RECLAMOS_PATH)
campanas = cargar_csv(CAMPANAS_PATH)
pedidos = cargar_pedidos()

pedidos_hoy = filtrar_hoy(pedidos)
reservas_hoy_df = filtrar_hoy(reservas)
reclamos_hoy_df = filtrar_hoy(reclamos)

pedidos_confirmados = 0
ventas_estimadas = 0.0
if not pedidos_hoy.empty and "respuesta" in pedidos_hoy.columns:
    confirmados_mask = pedidos_hoy["respuesta"].fillna("").str.upper().str.contains("PEDIDO CONFIRMADO")
    pedidos_confirmados = int(confirmados_mask.sum())
    if not menu.empty and "precio" in menu.columns:
        precio_por_plato = {
            str(row["plato"]): float(row["precio"])
            for _, row in menu.dropna(subset=["plato", "precio"]).iterrows()
        }
        for _, row in pedidos_hoy[confirmados_mask].iterrows():
            texto = f"{row.get('mensaje', '')} {row.get('respuesta', '')}"
            plato = detectar_plato(texto, menu)
            ventas_estimadas += precio_por_plato.get(str(plato), 0.0)

reclamos_hoy = len(reclamos_hoy_df)
reclamos_abiertos = 0
reclamos_alta = 0
if not reclamos_hoy_df.empty:
    if "estado" in reclamos_hoy_df.columns:
        reclamos_abiertos = int(reclamos_hoy_df["estado"].isin(["pendiente", "en_revision"]).sum())
    if "prioridad" in reclamos_hoy_df.columns:
        reclamos_alta = int((reclamos_hoy_df["prioridad"].astype(str).str.lower() == "alta").sum())

reservas_hoy = len(reservas_hoy_df)
clientes_activos = int((clientes["estado"] == "activo").sum()) if not clientes.empty and "estado" in clientes.columns else 0
clientes_riesgo = int((clientes["estado"] == "en_riesgo").sum()) if not clientes.empty and "estado" in clientes.columns else 0
clientes_nuevos = int((clientes["estado"] == "nuevo").sum()) if not clientes.empty and "estado" in clientes.columns else 0
campanas_activas = int((campanas["estado"] == "activa").sum()) if not campanas.empty and "estado" in campanas.columns else 0

categorias = []
if not menu.empty and "categoria" in menu.columns:
    categorias = menu["categoria"].dropna().astype(str).drop_duplicates().head(8).tolist()
categoria_iconos = ["🍗", "🥩", "🍝", "🍛", "🥗", "🍚", "🥤", "🍰"]
categorias_html = "\n".join(
    f'<div class="cat-pill {"active" if i == 0 else ""}"><span class="cat-emoji">{categoria_iconos[i % len(categoria_iconos)]}</span>{safe_text(cat)}</div>'
    for i, cat in enumerate(categorias or ["Pollos", "Parrillas", "Pastas", "Carnes", "Ensaladas", "Arroces"])
)

favoritos = clientes["plato_favorito"].value_counts() if not clientes.empty and "plato_favorito" in clientes.columns else pd.Series(dtype=int)
platos_base = []
if not favoritos.empty and not menu.empty and "plato" in menu.columns:
    for plato, pedidos_count in favoritos.head(6).items():
        match = menu[menu["plato"].astype(str).str.lower() == str(plato).lower()]
        precio = float(match.iloc[0]["precio"]) if not match.empty and "precio" in match.columns else 0.0
        platos_base.append((str(plato), precio, int(pedidos_count)))
elif not menu.empty:
    for _, row in menu.head(6).iterrows():
        platos_base.append((str(row.get("plato", "Plato")), float(row.get("precio", 0) or 0), 0))

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
        <div class="stars">★★★★☆ <span style="color:var(--text3)">4.{max(1, 9 - i)}</span></div>
        <div class="plato-sales">{pedidos_count} pedidos</div>
      </div>
    </div>
    """
    for i, (plato, precio, pedidos_count) in enumerate(platos_base)
)

estado_counts = clientes["estado"].value_counts() if not clientes.empty and "estado" in clientes.columns else pd.Series(dtype=int)
clientes_labels = ["Activos", "En riesgo", "Nuevos"]
clientes_chart_data = [
    int(estado_counts.get("activo", 0)),
    int(estado_counts.get("en_riesgo", 0)),
    int(estado_counts.get("nuevo", 0)),
]
platos_chart_labels = [str(x)[:12] for x in favoritos.head(7).index.tolist()] if not favoritos.empty else [p[0][:12] for p in platos_base]
platos_chart_data = [int(x) for x in favoritos.head(7).tolist()] if not favoritos.empty else [p[2] for p in platos_base]

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

cart_items = platos_base[:2] or [("Chaufa Brasa", 32.0, 2), ("Parrilla Familiar", 75.0, 1)]
cantidades = [2, 1]
subtotal = sum((cart_items[i][1] if i < len(cart_items) else 0) * cantidades[i] for i in range(min(2, len(cart_items))))
delivery = 5.0 if subtotal > 0 else 0.0
descuento = subtotal * 0.10 if subtotal > 0 else 0.0
total = subtotal + delivery - descuento
cart_html = "\n".join(
    f"""
    <div class="cart-item"><div class="cart-img">{plato_iconos[i % len(plato_iconos)]}</div><div class="cart-info"><div class="cart-name">{safe_text(plato)}</div><div class="cart-sub">Pedido sugerido</div><div class="qty-ctrl"><button class="qty-btn">−</button><span class="qty-num">{cantidades[i]}</span><button class="qty-btn">+</button></div></div></div>
    """
    for i, (plato, _, _) in enumerate(cart_items[:2])
)

top_plato = platos_base[0][0] if platos_base else "el plato principal"

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
    .kpi-strip,.platos-grid,.charts-row,.right-panel{grid-template-columns:1fr}
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
            <div class="plato-card"><div class="plato-badge">Top</div><div class="plato-emoji">🍚</div><div class="plato-name">Chaufa Brasa</div><div class="plato-from">Desde</div><div class="plato-price">S/ 32.00</div><div class="plato-footer"><div class="stars">★★★★★ <span style="color:var(--text3)">4.9</span></div><div class="plato-sales">16 pedidos</div></div></div>
            <div class="plato-card"><div class="plato-emoji">🥩</div><div class="plato-name">Parrilla Familiar</div><div class="plato-from">Desde</div><div class="plato-price">S/ 75.00</div><div class="plato-footer"><div class="stars">★★★★½ <span style="color:var(--text3)">4.7</span></div><div class="plato-sales">11 pedidos</div></div></div>
            <div class="plato-card"><div class="plato-emoji">🍛</div><div class="plato-name">Lomo Saltado</div><div class="plato-from">Desde</div><div class="plato-price">S/ 38.00</div><div class="plato-footer"><div class="stars">★★★★½ <span style="color:var(--text3)">4.6</span></div><div class="plato-sales">7 pedidos</div></div></div>
            <div class="plato-card"><div class="plato-emoji">🍜</div><div class="plato-name">Tallarín Saltado</div><div class="plato-from">Desde</div><div class="plato-price">S/ 30.00</div><div class="plato-footer"><div class="stars">★★★★☆ <span style="color:var(--text3)">4.4</span></div><div class="plato-sales">6 pedidos</div></div></div>
            <div class="plato-card"><div class="plato-emoji">🍗</div><div class="plato-name">Pollo a la Brasa</div><div class="plato-from">Desde</div><div class="plato-price">S/ 28.00</div><div class="plato-footer"><div class="stars">★★★★☆ <span style="color:var(--text3)">4.5</span></div><div class="plato-sales">11 pedidos</div></div></div>
            <div class="plato-card"><div class="plato-emoji">🥗</div><div class="plato-name">Ensalada Kiriko</div><div class="plato-from">Desde</div><div class="plato-price">S/ 22.00</div><div class="plato-footer"><div class="stars">★★★★☆ <span style="color:var(--text3)">4.3</span></div><div class="plato-sales">5 pedidos</div></div></div>
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
          <div class="delivery-time"><span>⏱️</span>20–35 min tiempo estimado</div>
        </div>

        <div class="cart-card">
          <div class="cart-header"><span class="cart-title">Pedido activo</span><span class="order-id">Orden en curso</span></div>
          <div class="tabs"><div class="tab active">Delivery</div><div class="tab">Salón</div><div class="tab">Retiro</div></div>
          <div class="cart-item"><div class="cart-img">🍚</div><div class="cart-info"><div class="cart-name">Chaufa Brasa</div><div class="cart-sub">Con menestra</div><div class="qty-ctrl"><button class="qty-btn">−</button><span class="qty-num">2</span><button class="qty-btn">+</button></div></div></div>
          <div class="cart-item"><div class="cart-img">🥩</div><div class="cart-info"><div class="cart-name">Parrilla Familiar</div><div class="cart-sub">Para 4 personas</div><div class="qty-ctrl"><button class="qty-btn">−</button><span class="qty-num">1</span><button class="qty-btn">+</button></div></div></div>
          <div class="promo-row"><input class="promo-input" placeholder="Código promoción"><button class="promo-btn">KIRIKO10</button></div>
          <div class="total-rows"><div class="total-row"><span>Sub Total</span><span>S/ 139.00</span></div><div class="total-row"><span>Delivery</span><span>S/ 5.00</span></div><div class="total-row" style="color:var(--green)"><span>Descuento</span><span>−S/ 13.90</span></div></div>
          <div class="total-final"><span>TOTAL</span><span>S/ 130.10</span></div>
          <button class="confirm-btn">Confirmar pedido</button>
        </div>

        <div class="delivery-card">
          <div class="delivery-header">MesaAI recomienda</div>
          <div style="display:flex;flex-direction:column;gap:10px;margin-top:4px">
            <div style="background:var(--green-soft);border-left:3px solid var(--green);border-radius:10px;padding:10px 12px;font-size:12px;color:var(--text2);line-height:1.5"><strong style="color:var(--green)">Cocina</strong><br>Chaufa Brasa es el más pedido. Refuerza stock para la hora pico.</div>
            <div style="background:var(--yellow-soft);border-left:3px solid var(--yellow);border-radius:10px;padding:10px 12px;font-size:12px;color:var(--text2);line-height:1.5"><strong style="color:var(--yellow)">Fidelización</strong><br>26 clientes en riesgo. Envía campaña con 10% de descuento esta semana.</div>
            <div style="background:var(--red-soft);border-left:3px solid var(--red);border-radius:10px;padding:10px 12px;font-size:12px;color:var(--text2);line-height:1.5"><strong style="color:var(--red)">Atención</strong><br>4 reclamos abiertos, 3 de alta prioridad. Resolver antes del cierre.</div>
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
dashboard_html = dashboard_html.replace('<div class="kpi-value">S/ 0</div>', f'<div class="kpi-value">S/ {ventas_estimadas:,.2f}</div>', 1)
dashboard_html = dashboard_html.replace('<div class="kpi-value">0</div><div class="kpi-sub">Confirmados</div>', f'<div class="kpi-value">{pedidos_confirmados}</div><div class="kpi-sub">Confirmados</div>', 1)
dashboard_html = dashboard_html.replace('<div class="kpi-value">6</div><div class="kpi-sub">4 abiertos · 3 alta</div>', f'<div class="kpi-value">{reclamos_hoy}</div><div class="kpi-sub">{reclamos_abiertos} abiertos · {reclamos_alta} alta</div>', 1)
dashboard_html = dashboard_html.replace('<div class="kpi-value">—</div><div class="kpi-sub">Hoy</div>', f'<div class="kpi-value">{reservas_hoy}</div><div class="kpi-sub">Hoy</div>', 1)
dashboard_html = dashboard_html.replace('<div class="kpi-value">26</div><div class="kpi-sub">de 50 activos</div>', f'<div class="kpi-value">{clientes_riesgo}</div><div class="kpi-sub">de {clientes_activos} activos</div>', 1)
dashboard_html = dashboard_html.replace('<div class="kpi-value">—</div><div class="kpi-sub">Activas</div>', f'<div class="kpi-value">{campanas_activas}</div><div class="kpi-sub">Activas</div>', 1)

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
dashboard_html = re.sub(
    r'<div class="platos-grid">.*?</div>\s*</div>\s*\n\n        <div class="charts-row">',
    f'<div class="platos-grid">\n{platos_html}\n          </div>\n        </div>\n\n        <div class="charts-row">',
    dashboard_html,
    flags=re.S,
    count=1,
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
    f'<div class="risk-list">\n{riesgo_html}\n          </div>\n        </div>\n      </div>\n\n      <div class="right-panel">',
    dashboard_html,
    flags=re.S,
    count=1,
)

dashboard_html = re.sub(
    r'<div class="cart-item"><div class="cart-img">🍚</div>.*?<div class="promo-row">',
    f'{cart_html}\n          <div class="promo-row">',
    dashboard_html,
    flags=re.S,
    count=1,
)
dashboard_html = dashboard_html.replace('<div class="total-row"><span>Sub Total</span><span>S/ 139.00</span></div>', f'<div class="total-row"><span>Sub Total</span><span>S/ {subtotal:.2f}</span></div>')
dashboard_html = dashboard_html.replace('<div class="total-row"><span>Delivery</span><span>S/ 5.00</span></div>', f'<div class="total-row"><span>Delivery</span><span>S/ {delivery:.2f}</span></div>')
dashboard_html = dashboard_html.replace('<div class="total-row" style="color:var(--green)"><span>Descuento</span><span>−S/ 13.90</span></div>', f'<div class="total-row" style="color:var(--green)"><span>Descuento</span><span>−S/ {descuento:.2f}</span></div>')
dashboard_html = dashboard_html.replace('<div class="total-final"><span>TOTAL</span><span>S/ 130.10</span></div>', f'<div class="total-final"><span>TOTAL</span><span>S/ {total:.2f}</span></div>')

dashboard_html = dashboard_html.replace("Chaufa Brasa es el más pedido. Refuerza stock para la hora pico.", f"{html.escape(top_plato)} es el más pedido. Refuerza stock para la hora pico.")
dashboard_html = dashboard_html.replace("26 clientes en riesgo. Envía campaña con 10% de descuento esta semana.", f"{clientes_riesgo} clientes en riesgo. Envía campaña con 10% de descuento esta semana.")
dashboard_html = dashboard_html.replace("4 reclamos abiertos, 3 de alta prioridad. Resolver antes del cierre.", f"{reclamos_abiertos} reclamos abiertos, {reclamos_alta} de alta prioridad. Resolver antes del cierre.")

dashboard_html = dashboard_html.replace("labels:['Activos','En riesgo','Nuevos']", f"labels:{json.dumps(clientes_labels, ensure_ascii=False)}")
dashboard_html = dashboard_html.replace("data:[50,26,24]", f"data:{json.dumps(clientes_chart_data)}", 1)
dashboard_html = dashboard_html.replace("labels:['Chaufa B.','1/4 Pollo','Pollo B.','Parrilla','Lomo S.','Tallarín','Ensalada']", f"labels:{json.dumps(platos_chart_labels, ensure_ascii=False)}")
dashboard_html = dashboard_html.replace("data:[16,11,11,11,7,6,5]", f"data:{json.dumps(platos_chart_data)}", 1)

components.html(dashboard_html, height=920, scrolling=True)
