# YouTube Music — Configuración y Autenticación

Esta guía cubre todo lo necesario para usar **YouTube Music** como proveedor origen o destino en `playlist-migrate`.

---

## 📋 Requisitos previos

- Cuenta activa en [YouTube Music](https://music.youtube.com) (gratuita o Premium)
- Acceso a un navegador basado en Chromium (Chrome, Edge, Brave)

> **Nota**: YouTube Music **no tiene una API pública oficial** para terceros. `playlist-migrate` utiliza [`ytmusicapi`](https://ytmusicapi.readthedocs.io/), que funciona mediante las cabeceras de autenticación de tu sesión activa en el navegador. Por eso el proceso de autenticación es distinto al de Spotify.

---

## 1️⃣ Autenticación (una sola vez)

La autenticación con YouTube Music consiste en capturar las cabeceras HTTP de tu sesión activa y guardarlas en un archivo `headers_auth.json`. Este proceso se realiza **una sola vez** por sesión de cuenta.

### Paso A — Captura el cURL desde el navegador

1. Abre [music.youtube.com](https://music.youtube.com) e **inicia sesión** con tu cuenta de Google.
2. Abre las Herramientas de Desarrollador:
   - **Mac**: `Cmd + Option + I`
   - **Windows/Linux**: `F12` o `Ctrl + Shift + I`
3. Ve a la pestaña **Network** (Red).
4. En el filtro de la barra de búsqueda, escribe `browse`.
5. Recarga la página o navega dentro de YouTube Music hasta que aparezca una petición `browse` en la lista.
6. Haz **clic derecho** sobre esa petición → **Copy** → **Copy as cURL (bash)**.

### Paso B — Genera el archivo de autenticación

**En macOS** (usando el portapapeles directamente):
```bash
pbpaste > curl.txt
playlist-migrate setup-auth --from-file curl.txt
```

**En Linux/Windows (WSL)**:
```bash
# Pega el contenido del cURL en un archivo
nano curl.txt  # pega y guarda

playlist-migrate setup-auth --from-file curl.txt
```

**Salida esperada:**
```
🔄 Detectado formato cURL — convirtiendo a cabeceras raw...
✅ Cookie encontrada. Generando 'headers_auth.json' via ytmusicapi...
✅ Autenticación guardada exitosamente en 'headers_auth.json'.
```

### Resultado

Se genera el archivo `headers_auth.json` en tu directorio de trabajo. Este archivo contiene las cookies de sesión de tu cuenta de YouTube Music.

> ⚠️ **`headers_auth.json` es personal y confidencial.** Está en `.gitignore`. Nunca lo subas a un repositorio ni lo compartas.

---

## 2️⃣ Duración de la Sesión y Re-autenticación

Las cookies de YouTube Music tienen una duración limitada (generalmente varias semanas). Cuando expiren, recibirás un error de autenticación. Para renovarlas, simplemente repite el proceso del **Paso 1** y regenera el archivo:

```bash
# El archivo existente se sobreescribe automáticamente
playlist-migrate setup-auth --from-file curl.txt
```

Para usar un nombre de archivo o ruta diferente:
```bash
playlist-migrate setup-auth --from-file curl.txt --output /ruta/custom/mis_headers.json
```

Y luego usa `--auth-file` al migrar:
```bash
playlist-migrate "PLxxx..." \
    --source ytmusic --target spotify \
    --auth-file /ruta/custom/mis_headers.json
```

---

## 🆔 Cómo Obtener el ID de una Playlist de YouTube Music

El `PLAYLIST_ID` que necesita `playlist-migrate` es el **ID alfanumérico** de la playlist, que comienza con `PL`.

### Opción A — Desde la web de YouTube Music
1. Abre la playlist en [music.youtube.com](https://music.youtube.com).
2. La URL tiene el formato:
   ```
   https://music.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxxxxxxxx
                                           ^^^^^^^^^^^^^^^^^^^^^^^^
                                           Este es el ID
   ```
3. Copia únicamente la parte después de `list=`.

### Opción B — Desde YouTube Music en el navegador
1. Ve a tu biblioteca → Playlists.
2. Haz clic en la playlist deseada.
3. Copia el ID desde la URL como en la Opción A.

### Opción C — Desde la app móvil
1. Abre la playlist.
2. Toca los `⋮` (tres puntos) → **Compartir** → **Copiar enlace**.
3. Pega el enlace en cualquier editor y extrae el ID después de `list=`.

> **Importante**: Los IDs de YouTube Music siempre empiezan con `PL` y tienen aproximadamente 34 caracteres. No confundir con los IDs de YouTube regular.

---

## ⚡ Ejemplos de Uso

```bash
# Migrar playlist de YouTube Music hacia Spotify
playlist-migrate "PLxxxxxxxxxxxxxxxxxxxxxx" --source ytmusic --target spotify

# Migrar desde Spotify hacia YouTube Music (Canciones Favoritas / "Tus me gusta")
playlist-migrate --liked-songs-pl --source spotify --target ytmusic

# Con alias corto (-lsp) y nombre personalizado
playlist-migrate -lsp -s spotify -t ytmusic --name "Favoritas Spotify"

# Migrar desde Spotify hacia YouTube Music (Playlist normal)
playlist-migrate "37i9dQZF1DXcBWIGoYBM5M" --source spotify --target ytmusic

# Con nombre personalizado en destino
playlist-migrate "PLxxxxxxxxxxxxxxxxxxxxxx" \
    --source ytmusic --target spotify \
    --name "Mis Favoritos"

# Especificando una ruta distinta para headers_auth.json
playlist-migrate "PLxxxxxxxxxxxxxxxxxxxxxx" \
    --source ytmusic --target spotify \
    --auth-file /Users/usuario/ytmusic_headers.json

# Sincronización exacta
playlist-migrate "PLxxxxxxxxxxxxxxxxxxxxxx" \
    --source ytmusic --target spotify --sync
```

---

## 🚫 Limitaciones Conocidas de YouTube Music

| Limitación | Detalle |
|---|---|
| **Sin API oficial** | La autenticación se basa en cookies de sesión del navegador, no en un token OAuth estándar |
| **Sin subida de portadas** | La API de `ytmusicapi` no permite subir imágenes personalizadas a playlists (la portada se genera automáticamente por YouTube) |
| **Rate Limits** | YouTube Music puede limitar peticiones muy frecuentes; `playlist-migrate` maneja esto con *Exponential Backoff* automático |
| **Playlists privadas** | Solo puedes acceder a las playlists de la cuenta cuyas cookies se usaron para autenticarse |

---

## 🛠️ Solución de Problemas

### `AuthError: headers_auth.json not found`
El archivo de autenticación no existe o no está en la ruta esperada. Ejecuta:
```bash
playlist-migrate setup-auth --from-file curl.txt
```

### `KeyError: cookie` durante setup-auth
El cURL copiado no contiene una cookie válida de YouTube Music. Asegúrate de:
1. Estar **iniciado sesión** en music.youtube.com antes de capturar el cURL.
2. Capturar la petición **`browse`** específicamente (no otra petición de la página).
3. Usar **"Copy as cURL (bash)"** y no otro formato.
