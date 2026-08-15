# cp-music 🎵↔️

Herramienta extensible en Python para **migrar listas de reproducción** entre servicios de música de forma bidireccional, agnóstica y con un único comando.

```bash
uv run python -m cpmusic migrate "PLAYLIST_ID" --source spotify --target ytmusic
```

---

## ✨ Características

| Funcionalidad | Detalle |
|---|---|
| **Arquitectura extensible** | Protocolo `MusicProvider` — añade nuevos servicios sin tocar el core |
| **Un solo comando** | `migrate --source X --target Y` — no importa la dirección |
| **Búsqueda concurrente** | `asyncio` + búsquedas paralelas para migraciones ultra-rápidas |
| **Detección de duplicados** | Matching por ISRC, ID nativo y Artista+Título |
| **Modo `--sync`** | Sincronización exacta — el destino queda idéntico al origen |
| **Tolerancia a fallos** | *Exponential Backoff* automático ante Rate Limits y errores de red |
| **Portadas** | Sincroniza las carátulas de las playlists hacia los servicios que lo soporten |
| **Calidad de código** | Hooks pre-commit con Ruff, Bandit SAST y pip-audit CVE scanning |

---

## 📦 Servicios Disponibles

| Servicio | ID CLI | Estado | Documentación |
|---|---|---|---|
| Spotify | `spotify` | ✅ Disponible | [docs/providers/SPOTIFY.md](./docs/providers/SPOTIFY.md) |
| YouTube Music | `ytmusic` | ✅ Disponible | [docs/providers/YTMUSIC.md](./docs/providers/YTMUSIC.md) |

> ¿Quieres añadir un nuevo servicio? Consulta la guía para desarrolladores en [`docs/ADDING_NEW_PROVIDERS.md`](./docs/ADDING_NEW_PROVIDERS.md).

---

## 🏗️ Estructura del Proyecto

```
cp-music/
├── cpmusic/
│   ├── __init__.py
│   ├── __main__.py          # Entrada: python -m cpmusic
│   ├── cli.py               # CLI: subcomando 'migrate' y 'setup-auth'
│   ├── interfaces.py        # Protocolo MusicProvider (contrato para todos los servicios)
│   ├── models.py            # Track, Playlist, MigrationResult (dataclasses con slots)
│   ├── exceptions.py        # AuthError, NetworkError, RateLimitError
│   ├── utils.py             # Decorador @with_retries (Exponential Backoff)
│   ├── migrator.py          # Orquestador genérico: fuente → destino
│   └── providers/           # Clientes modulares de servicios de música
│       ├── __init__.py      # Exporta SpotifyClient y YTMusicClient
│       ├── spotify.py       # Implementación MusicProvider para Spotify
│       └── ytmusic.py       # Implementación MusicProvider para YouTube Music
├── docs/
│   ├── providers/
│   │   ├── SPOTIFY.md       # Configuración y autenticación de Spotify
│   │   └── YTMUSIC.md       # Configuración y autenticación de YouTube Music
│   └── ADDING_NEW_PROVIDERS.md  # Guía para añadir nuevos servicios
├── tests/
│   ├── conftest.py               # Fixtures pytest (mocks de proveedores)
│   ├── test_migrator.py          # Tests del orquestador migrador (asyncio)
│   ├── test_spotify_provider.py  # Tests unitarios mockeados de Spotify
│   └── test_ytmusic_provider.py  # Tests unitarios mockeados de YouTube Music
├── .pre-commit-config.yaml  # Hooks de calidad y seguridad
├── .env.example
├── pyproject.toml           # uv, Ruff, Bandit, pytest
└── README.md
```

---

## 🛠️ Requisitos

- **Python 3.14+**
- **[uv](https://github.com/astral-sh/uv)** — gestor de dependencias moderno y ultrarrápido

---

## 🚀 Instalación

```bash
# 1. Instalar uv (si aún no lo tienes)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clonar el proyecto
git clone <tu-repositorio>
cd cp-music

# 3. Instalar dependencias con Python 3.14
uv sync
```

---

## ⚙️ Configuración por Servicio

Cada servicio de música requiere su propia autenticación. Consulta la documentación específica del proveedor antes de ejecutar migraciones:

- 🟢 **[Configurar Spotify →](./docs/providers/SPOTIFY.md)**
- 🔴 **[Configurar YouTube Music →](./docs/providers/YTMUSIC.md)**

---

## ⚡ Uso

Todos los comandos se ejecutan con `uv run python -m cpmusic` (o simplemente `cpmusic` si instalaste el paquete).

### Comando principal: `migrate`

```bash
uv run python -m cpmusic migrate PLAYLIST_ID \
    --source <proveedor_origen> \
    --target <proveedor_destino> \
    [--name "Nombre Destino"] \
    [--sync] \
    [--verbose]
```

### Ejemplos

```bash
# Spotify → YouTube Music
uv run python -m cpmusic migrate "37i9dQZF1DXcBWIGoYBM5M" \
    --source spotify --target ytmusic

# YouTube Music → Spotify
uv run python -m cpmusic migrate "PLxxxxxxxxxxxxxxxxxxxxxx" \
    --source ytmusic --target spotify

# Con nombre personalizado en el destino
uv run python -m cpmusic migrate "37i9dQZF1DXcBWIGoYBM5M" \
    --source spotify --target ytmusic \
    --name "Mis Favoritos"

# Modo sincronización exacta (borra lo que sobra en destino)
uv run python -m cpmusic migrate "PLxxxxxxxxxxxxxxxxxxxxxx" \
    --source ytmusic --target spotify --sync
```

### Opciones del comando `migrate`

| Opción | Descripción |
|---|---|
| `PLAYLIST_ID` | ID nativo de la playlist en el servicio origen |
| `--source ID` | Proveedor origen (ej: `spotify`, `ytmusic`) |
| `--target ID` | Proveedor destino (ej: `spotify`, `ytmusic`) |
| `--name NAME` | Nombre personalizado para la playlist destino |
| `--sync` | Reemplaza el contenido del destino para que sea idéntico al origen |
| `--auth-file PATH` | Ruta al archivo `headers_auth.json` de YTMusic (default: directorio actual) |
| `--verbose` / `-v` | Activa logging DEBUG detallado |

---

## 🧪 Tests y Calidad de Código

```bash
# Ejecutar suite de tests
uv run pytest tests/

# Con reporte de cobertura
uv run pytest --cov=cpmusic --cov-report=term-missing

# Linter y formatter
uv run ruff check --fix .
uv run ruff format .

# Análisis de seguridad estático
uv run bandit -c pyproject.toml -r cpmusic/

# Auditoría de vulnerabilidades en dependencias
uv tool run pip-audit

# Ejecutar todos los hooks de calidad (igual que en git commit)
uv tool run pre-commit run --all-files
```

---

## 🔒 Seguridad

- `.env` y `headers_auth.json` están en `.gitignore` — **nunca los subas al repositorio**.
- Los hooks pre-commit incluyen **Bandit** (SAST) y **pip-audit** (CVE scanning) automáticamente en cada commit.
- El token PKCE de Spotify se guarda localmente en `.cache/` (ignorado en git).

---

## 🤝 Contribuir

¿Quieres añadir un nuevo proveedor de música? Lee la guía completa:

📖 **[docs/ADDING_NEW_PROVIDERS.md](./docs/ADDING_NEW_PROVIDERS.md)**
