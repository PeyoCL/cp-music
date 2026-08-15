# cp-music 🎵↔️

Herramienta profesional en Python para **migrar listas de reproducción en ambos sentidos** entre **Spotify** y **YouTube Music**.

- ✅ Spotify → YouTube Music
- ✅ YouTube Music → Spotify
- ✅ **Arquitectura Agonóstica / Extensible**: Listo para añadir nuevos servicios mediante su protocolo `MusicProvider`.
- ✅ Búsqueda asíncrona concurrente (`asyncio`) para migraciones ultra-rápidas.
- ✅ Tolerancia a fallos con *Exponential Backoff* ante bloqueos de red o *Rate Limits*.
- ✅ Detección inteligente de duplicados (vía ISRC y Artista+Título).
- ✅ Modo `--sync` para sincronización exacta (reemplaza el destino para que quede idéntico al origen).
- ✅ Sincronización automática de carátulas (portadas) de playlists.
- ✅ Paginación automática para playlists de cualquier tamaño.
- ✅ Autenticación PKCE en Spotify (sin copy-paste de URLs).

*Desarrollado bajo los más altos estándares modernos de Python 3.14+ (type hints estrictos, optimizaciones de memoria de dataclasses, linters rigurosos).*

---

## 🏗️ Estructura del proyecto

```
cp-music/
├── cpmusic/
│   ├── __init__.py
│   ├── __main__.py          # python -m cpmusic
│   ├── cli.py               # CLI (migrate-to-ytmusic / migrate-to-spotify / setup-auth)
│   ├── interfaces.py        # Protocolo MusicProvider para extender con nuevos servicios
│   ├── models.py            # Track, Playlist, MigrationResult (optimizados con slots=True)
│   ├── exceptions.py        # Excepciones personalizadas (Auth, Network, RateLimit)
│   ├── utils.py             # Utilidades asíncronas y decoradores (Exponential Backoff)
│   ├── spotify_client.py    # Cliente API de Spotify (implementa MusicProvider)
│   ├── ytmusic_client.py    # Cliente API de YTMusic (implementa MusicProvider)
│   └── migrator.py          # Orquestador asíncrono agnostic para migrar playlists
├── docs/
│   └── ADDING_NEW_PROVIDERS.md # Guía para desarrolladores: Cómo añadir Apple Music, Tidal, etc.
├── tests/
│   ├── conftest.py          # Fixtures comunes de pytest (clientes mockeados)
│   └── test_migrator.py     # Suite de tests pure pytest (asíncronos y parametrizados)
├── .env.example
├── .gitignore
├── pyproject.toml           # Configuración de uv, Ruff y pytest
└── README.md
```

---

## 🛠️ Requisitos

- **Python 3.14+**
- **[uv](https://github.com/astral-sh/uv)** (Gestor de dependencias ultrarrápido)
- Cuenta activa en [Spotify](https://open.spotify.com) y [YouTube Music](https://music.youtube.com)
- Credenciales de la [Spotify Developer App](https://developer.spotify.com/dashboard)

---

## 🚀 Instalación y Entorno (uv)

Este proyecto utiliza `uv` para gestionar el entorno, ofreciendo una instalación instantánea.

```bash
# Instalar uv si aún no lo tienes
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clonar el proyecto
git clone <tu-repositorio>
cd cp-music

# Instalar dependencias y enlazar entorno para Python 3.14
uv sync --python 3.14
```

---

## ⚙️ Configuración

### 1. Variables de entorno de Spotify

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales:

```env
SPOTIPY_CLIENT_ID=tu_client_id
SPOTIPY_CLIENT_SECRET=tu_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

> **Importante**: En el [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
> → tu app → **Settings** → **Redirect URIs**, añade exactamente
> `http://127.0.0.1:8888/callback`.

### 2. Autenticación con YouTube Music (una sola vez)

**Paso A** — Copia el cURL desde Chrome/Edge:
1. Abre [music.youtube.com](https://music.youtube.com) e inicia sesión.
2. Presiona `Cmd + Option + I` → pestaña **Network** → filtra por `browse`.
3. Clic derecho en la petición `browse` → **Copy** → **Copy as cURL (bash)**.

**Paso B** — Genera el archivo de autenticación:
```bash
pbpaste > curl.txt
uv run python -m cpmusic setup-auth --from-file curl.txt
```

---

## ⚡ Uso

Se recomienda ejecutar la aplicación a través de `uv run` para asegurar el uso del entorno virtual correcto.

### Spotify → YouTube Music

```bash
# URL de Spotify
uv run python -m cpmusic migrate-to-ytmusic \
    "https://open.spotify.com/playlist/TU_PLAYLIST_ID"

# Con nombre personalizado en el destino
uv run python -m cpmusic migrate-to-ytmusic \
    "https://open.spotify.com/playlist/..." \
    --name "Mis Favoritos"
```

### YouTube Music → Spotify

```bash
# ID de playlist de YouTube Music (empieza con PL...)
uv run python -m cpmusic migrate-to-spotify "PLxxxxxxxxxxxxxxxxxxxxxx"
```

### Modo Sincronización Estricta (`--sync`)

Si prefieres que la lista destino sea un **reflejo exacto** del origen (útil si eliminaste pistas en origen y quieres que desaparezcan en destino), usa el flag `--sync`:

```bash
uv run python -m cpmusic migrate-to-spotify "PLxxx..." --sync
```
*(Esto reemplaza todo el contenido del destino para que coincida 1:1 con la fuente).*

---

## 📋 Calidad de Código y Arquitectura

### Tests (`pytest`)
La aplicación cuenta con una suite completa en `pytest`, utilizando mocks avanzados e inyección de dependencias (`pytest-asyncio`, `pytest-cov`).

```bash
# Correr tests
uv run pytest tests/
```

### Linter & Formatter (`Ruff`)
Configurado estrictamente en `pyproject.toml` (target Python 3.14).
```bash
# Analizar y formatear código
uv run ruff check --fix .
uv run ruff format .
```

### Extensibilidad
Gracias a la interfaz `MusicProvider` (`typing.Protocol`), puedes agregar fácilmente clientes para Apple Music, Amazon Music u otros. Revisa [`docs/ADDING_NEW_PROVIDERS.md`](./docs/ADDING_NEW_PROVIDERS.md) para más detalles.

---

## 🔒 Seguridad

- `.env` y `headers_auth.json` están en `.gitignore` — **nunca los subas al repositorio**.
- Las cookies de YouTube Music son personales — no las compartas.
- El token PKCE de Spotify se guarda localmente en el directorio de trabajo (ignorado en el repo).
