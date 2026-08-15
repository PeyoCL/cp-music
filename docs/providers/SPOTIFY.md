# Spotify — Configuración y Autenticación

Esta guía cubre todo lo necesario para usar **Spotify** como proveedor origen o destino en `playlist-migrate`.

---

## 📋 Requisitos previos

- Cuenta activa en [Spotify](https://open.spotify.com) (Free o Premium)
- Acceso al [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)

> **Nota**: Para *crear* playlists y *subir portadas*, se requiere una cuenta **Spotify Premium**. La lectura de playlists públicas funciona con cualquier cuenta.

---

## 1️⃣ Crear una Aplicación en el Dashboard

1. Ingresa a [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) e inicia sesión.
2. Haz clic en **"Create app"**.
3. Completa el formulario:
   - **App name**: `cp-music` (o el nombre que prefieras)
   - **App description**: `Playlist migration tool`
   - **Redirect URIs**: Agrega exactamente `http://127.0.0.1:8888/callback`
   - **APIs used**: selecciona `Web API`
4. Acepta los términos y haz clic en **Save**.
5. En la pantalla de tu app, ve a **Settings** y copia:
   - `Client ID`
   - `Client Secret`

---

## 2️⃣ Configurar Variables de Entorno

Copia el archivo de ejemplo y rellena tus credenciales:

```bash
cp .env.example .env
```

Edita `.env`:

```env
SPOTIPY_CLIENT_ID=tu_client_id_aquí
SPOTIPY_CLIENT_SECRET=tu_client_secret_aquí
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

> ⚠️ **Nunca subas `.env` al repositorio.** Ya está incluido en `.gitignore`.

---

## 3️⃣ Primer Login (PKCE — una sola vez)

`playlist-migrate` usa el flujo **PKCE** de Spotify: no necesitas copiar ni pegar URLs manualmente.

La primera vez que ejecutes cualquier comando que use Spotify como origen o destino, el navegador se abrirá automáticamente para que autorices la app:

```bash
playlist-migrate "PLxxxxxxxxxxxxxxxxxxxxxx" --source ytmusic --target spotify
```

El flujo es:
1. Se abre el navegador en la página de autorización de Spotify.
2. Aceptas los permisos solicitados.
3. Spotify redirige a `http://127.0.0.1:8888/callback` y la sesión se guarda en `.cache`.

Las siguientes ejecuciones reutilizan el token guardado automáticamente. El archivo `.cache` está incluido en `.gitignore`.

---

## 🆔 Cómo Obtener el ID de una Playlist de Spotify

El `PLAYLIST_ID` que necesita `playlist-migrate` es el **ID alfanumérico** de la playlist, **no** la URL completa.

### Opción A — Desde la app web
1. Abre la playlist en [open.spotify.com](https://open.spotify.com).
2. La URL tiene el formato:
   ```
   https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=...
                                      ^^^^^^^^^^^^^^^^^^^^^^^^
                                      Este es el ID
   ```
3. Copia únicamente la parte después de `/playlist/` y antes de `?`.

### Opción B — Desde la app de escritorio
1. Abre la playlist.
2. Clic en los `···` → **Compartir** → **Copiar enlace de la playlist**.
3. Extrae el ID de la URL como en la Opción A.

---

## ⚡ Ejemplos de Uso

```bash
# Migrar playlist de Spotify hacia YouTube Music
playlist-migrate "37i9dQZF1DXcBWIGoYBM5M" --source spotify --target ytmusic

# Migrar con nombre personalizado en destino
playlist-migrate "37i9dQZF1DXcBWIGoYBM5M" \
    --source spotify --target ytmusic \
    --name "Road Trip 2025"

# Migrar desde YouTube Music hacia Spotify
playlist-migrate "PLxxxxxxxxxxxxxxxxxxxxxx" --source ytmusic --target spotify

# Sincronización exacta (borra lo que sobra en la playlist destino)
playlist-migrate "37i9dQZF1DXcBWIGoYBM5M" --source spotify --target ytmusic --sync
```

---

## 🔐 Permisos (Scopes) Solicitados

`playlist-migrate` solicita los siguientes permisos a Spotify:

| Scope | Para qué se usa |
|---|---|
| `playlist-read-private` | Leer playlists privadas del usuario |
| `playlist-read-collaborative` | Leer playlists colaborativas |
| `playlist-modify-public` | Crear/modificar playlists públicas |
| `playlist-modify-private` | Crear/modificar playlists privadas |
| `ugc-image-upload` | Subir portadas personalizadas a playlists |

---

## 🛠️ Solución de Problemas

### `AuthError: No Spotify credentials found`
Verifica que el archivo `.env` existe y tiene las tres variables (`CLIENT_ID`, `CLIENT_SECRET`, `REDIRECT_URI`) correctamente definidas.

### `Invalid redirect URI`
La URI en el `.env` debe coincidir **exactamente** (incluyendo `http://` y el puerto) con la registrada en el Spotify Developer Dashboard.

### `Token expired` / re-autenticación
Borra el archivo `.cache` en el directorio del proyecto y vuelve a ejecutar el comando. El flujo PKCE se iniciará de nuevo.

```bash
rm .cache
playlist-migrate "PLAYLIST_ID" --source ... --target ...
```
