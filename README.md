# MesaAI - Dashboard y Bots para Restaurante

MesaAI es un prototipo de sistema de gestión para **Kiriko Pollos y Parrillas**. Incluye un dashboard visual en Streamlit y dos bots de Telegram conectados a Groq para atención al cliente y soporte al dueño del restaurante.

El proyecto está pensado para mostrar información operativa del restaurante: pedidos, reclamos, clientes en riesgo, platos populares, recomendaciones, reservas y pedido activo.

## Características

- Dashboard dark premium construido con Streamlit.
- Interfaz personalizada con HTML, CSS y JavaScript embebido desde Python.
- Gráficos con Chart.js cargado desde CDN.
- Bot de atención al cliente para pedidos, reservas, reclamos y consultas generales.
- Bot para el dueño con insights de operación, cocina, reservas, reclamos, clientes y campañas.
- Datos de demo en CSV y base SQLite local.
- Diseño orientado a restaurantes, delivery y operación diaria.

## Estructura del Proyecto

```text
front-mesa-ya-bot/
├── dashboard.py                    # Dashboard Streamlit principal
├── bot.py                          # Bot Telegram para clientes
├── bot_dueno.py                    # Bot Telegram para el dueño
├── pedidos.db                      # Base SQLite de interacciones/pedidos
├── menu_kiriko.csv                 # Menú del restaurante
├── clientes_restaurante_lima.csv   # Base de clientes
├── reservas.csv                    # Reservas de ejemplo
├── reclamos.csv                    # Reclamos de ejemplo
├── campanas.csv                    # Campañas comerciales
├── .env.example                    # Variables de entorno necesarias
└── README.md
```

## Requisitos

- Python 3.10 o superior.
- Cuenta/API key de Groq si vas a ejecutar los bots.
- Tokens de Telegram si vas a ejecutar los bots.
- Conexión a internet para cargar Chart.js y la fuente del dashboard desde CDN.

## Instalación

1. Clona o descarga el proyecto.

2. Entra a la carpeta:

```bash
cd front-mesa-ya-bot
```

3. Crea un entorno virtual:

```bash
python -m venv .venv
```

4. Activa el entorno virtual.

En Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

5. Instala dependencias:

```bash
pip install streamlit pandas groq python-telegram-bot
```

## Variables de Entorno

Copia `.env.example` como `.env` o configura las variables directamente en tu sistema:

```env
TELEGRAM_TOKEN=pon_aqui_el_token_del_bot_cliente
TELEGRAM_DUENO_TOKEN=pon_aqui_el_token_del_bot_dueno
GROQ_API_KEY=pon_aqui_tu_api_key_de_groq
```

Si usas PowerShell, puedes configurarlas temporalmente así:

```powershell
$env:TELEGRAM_TOKEN="tu_token_cliente"
$env:TELEGRAM_DUENO_TOKEN="tu_token_dueno"
$env:GROQ_API_KEY="tu_api_key_groq"
```

## Ejecutar el Dashboard

```bash
streamlit run dashboard.py
```

Luego abre:

```text
http://localhost:8501
```

El dashboard muestra una interfaz dark con:

- Sidebar de navegación.
- KPIs del negocio.
- Categorías del menú.
- Platos populares.
- Gráficas de clientes y platos favoritos.
- Tabla de reclamos.
- Lista de clientes en riesgo.
- Panel derecho con pedido activo, delivery, totales y recomendaciones.

## Ejecutar el Bot de Clientes

Este bot atiende mensajes de clientes y puede responder sobre pedidos, reservas, reclamos, fidelización y atención general.

```bash
python bot.py
```

El bot guarda interacciones en `pedidos.db`.

## Ejecutar el Bot del Dueño

Este bot está orientado al dueño o administrador del restaurante. Resume contexto del negocio y responde consultas operativas.

```bash
python bot_dueno.py
```

Puede ayudar con:

- Estado de pedidos.
- Cocina y productos más demandados.
- Reservas.
- Reclamos.
- Clientes en riesgo.
- Campañas.
- Insights del negocio.

## Datos del Proyecto

Los datos están precargados para demo:

- `menu_kiriko.csv`: platos, precios y datos del menú.
- `clientes_restaurante_lima.csv`: clientes, frecuencia, ticket y platos favoritos.
- `reservas.csv`: reservas por fecha, hora, estado, zona y canal.
- `reclamos.csv`: reclamos con tipo, estado, prioridad y responsable.
- `campanas.csv`: campañas y métricas comerciales.
- `pedidos.db`: base SQLite donde los bots registran interacciones.

## Notas Técnicas

- `dashboard.py` usa `streamlit.components.v1.html` para renderizar una interfaz HTML/CSS/JS dentro de Streamlit.
- Chart.js se carga desde CDN, por eso las gráficas necesitan internet.
- Los bots usan `python-telegram-bot` y Groq.
- No hay backend web separado; todo corre localmente con Python.

## Próximas Mejoras

- Conectar el dashboard a los CSV y SQLite en tiempo real.
- Agregar filtros por fecha, estado y canal.
- Crear un archivo `requirements.txt`.
- Separar estilos del dashboard para facilitar mantenimiento.
- Agregar autenticación para el panel del dueño.
- Exportar reportes de ventas, reclamos y clientes.

## Autor

Proyecto demo para gestión de restaurante con IA, dashboard operativo y bots conversacionales.
