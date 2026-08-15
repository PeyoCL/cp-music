# Añadir un Nuevo Proveedor de Música

`cp-music` fue diseñado desde el principio para ser extensible. Gracias al protocolo `MusicProvider`, puedes añadir soporte para cualquier servicio de streaming implementando una sola clase, sin modificar el core del migrador.

---

## Visión General

El flujo de integración de un nuevo proveedor tiene 4 pasos:

```
1. Implementar MusicProvider  →  2. Registrar en CLI  →  3. Añadir Tests  →  4. Documentar
```

---

## 1. Implementar el Protocolo `MusicProvider`

El contrato que debe cumplir cualquier cliente está definido en [`cpmusic/interfaces.py`](../cpmusic/interfaces.py). Gracias a `typing.Protocol`, **no necesitas heredar** de ninguna clase base: solo debes implementar los métodos con las firmas correctas.

```python
# cpmusic/providers/your_service.py
from __future__ import annotations

from cpmusic.models import Playlist, Track
from cpmusic.utils import with_retries


class YourServiceClient:
    """Client for YourService implementing the MusicProvider protocol."""

    def __init__(self, api_key: str) -> None:
        # Inicializa tu cliente con las credenciales necesarias
        self._api_key = api_key

    def get_playlist(self, identifier: str) -> Playlist:
        """Obtiene una playlist completa (con todos sus tracks) del servicio.

        Args:
            identifier: ID nativo de la playlist en el servicio.

        Returns:
            Playlist con todos sus tracks como objetos Track.
        """
        ...

    def get_existing_playlist(self, name: str) -> Playlist | None:
        """Busca una playlist por nombre exacto en la biblioteca del usuario.

        Returns:
            La Playlist si se encuentra, None en caso contrario.
        """
        ...

    def search_track(self, track: Track) -> str | None:
        """Busca un track en el servicio y devuelve su ID nativo.

        Prioriza la búsqueda por ISRC si el servicio lo soporta,
        ya que ofrece un matching exacto y sin ambigüedades.

        Returns:
            El ID nativo del track en el servicio, o None si no se encontró.
        """
        ...

    def create_playlist(self, title: str, description: str = "") -> str:
        """Crea una nueva playlist vacía y devuelve su ID nativo."""
        ...

    def add_tracks(self, playlist_id: str, track_ids: list[str]) -> None:
        """Añade tracks a una playlist existente.

        Implementa paginación interna si el servicio limita la cantidad
        de tracks por petición.
        """
        ...

    def clear_playlist(self, playlist_id: str) -> None:
        """Elimina todos los tracks de una playlist (usado en modo --sync)."""
        ...
```

### Modelos Compartidos

Usa siempre los modelos de [`cpmusic/models.py`](../cpmusic/models.py):

| Modelo | Campos clave |
|---|---|
| `Track` | `title`, `artists`, `album`, `duration_ms`, `isrc`, `video_id`, `spotify_id` |
| `Playlist` | `id`, `name`, `description`, `source`, `tracks`, `cover_url` |

El campo `source` de `Playlist` debe ser el nombre legible del servicio (ej: `"My Service"`).

### Manejo de Errores

Usa las excepciones de [`cpmusic/exceptions.py`](../cpmusic/exceptions.py) para que el migrador pueda hacer retry automático:

```python
from cpmusic.exceptions import NetworkError, RateLimitError

# En tus métodos:
if response.status_code == 429:
    raise RateLimitError("MyService rate limit reached")
if response.status_code >= 500:
    raise NetworkError(f"MyService server error: {response.status_code}")
```

Decora los métodos que hacen llamadas externas con `@with_retries`:

```python
from cpmusic.utils import with_retries

@with_retries(max_retries=3, base_delay=1.0)
def search_track(self, track: Track) -> str | None:
    ...
```

---

## 2. Registrar el Proveedor en la CLI

Edita [`cpmusic/cli.py`](../cpmusic/cli.py) en la función `main()` para reconocer el nuevo proveedor:

### 2a. Añadir al argumento `choices`

```python
# En _build_parser(), busca los argumentos --source y --target
migrate.add_argument(
    "--source",
    required=True,
    choices=["spotify", "ytmusic", "myservice"],  # ← añade aquí
    ...
)
migrate.add_argument(
    "--target",
    required=True,
    choices=["spotify", "ytmusic", "myservice"],  # ← y aquí
    ...
)
```

### 2b. Instanciar el cliente

```python
# En main(), dentro del bloque elif args.command == "migrate":
if "myservice" in (args.source, args.target):
    from cpmusic.providers.your_service import YourServiceClient

    providers["myservice"] = YourServiceClient(api_key=os.getenv("MY_SERVICE_API_KEY"))
```

Con esto, el comando ya es funcional:

```bash
uv run python -m cpmusic migrate "PLAYLIST_ID" --source myservice --target spotify
```

---

## 3. Añadir Tests

### 3a. Fixture en `tests/conftest.py`

```python
@pytest.fixture
def mock_myservice() -> MagicMock:
    """Mocked YourServiceClient fixture."""
    mock = MagicMock()
    mock.get_existing_playlist.return_value = None
    mock.create_playlist.return_value = "ms_playlist_001"
    return mock
```

### 3b. Tests en `tests/test_migrator.py`

```python
class TestMigratorMyServiceToSpotify:
    def _make_migrator(self, mock_ms, mock_sp):
        return PlaylistMigrator(providers={"myservice": mock_ms, "spotify": mock_sp})

    @pytest.mark.asyncio
    async def test_new_playlist_created(self, mock_ms, mock_sp):
        tracks = [make_track("Song A"), make_track("Song B")]
        source_pl = make_playlist(name="My PL", tracks=tracks, source="My Service")

        mock_ms.get_playlist.return_value = source_pl
        mock_sp.search_track.side_effect = ["spotify:track:aaa", "spotify:track:bbb"]
        mock_sp.get_existing_playlist.return_value = None
        mock_sp.create_playlist.return_value = "sp_new"

        migrator = self._make_migrator(mock_ms, mock_sp)
        result = await migrator.migrate(
            source_id="myservice", target_id="spotify", playlist_identifier="ms_pl_001"
        )

        assert result.migrated_count == 2
        assert result.target_playlist_id == "sp_new"
```

Asegúrate de cubrir:
- ✅ Nueva playlist creada desde cero
- ✅ Playlist existente con detección de duplicados
- ✅ Playlist vacía en el origen
- ✅ Tracks no encontrados en el destino
- ✅ Manejo de `RateLimitError` y `NetworkError`

---

## 4. Documentar el Proveedor

Crea un archivo `docs/providers/NOMBRE_SERVICIO.md` siguiendo la misma estructura que los proveedores existentes:

- [`docs/providers/SPOTIFY.md`](./providers/SPOTIFY.md) — ejemplo de referencia
- [`docs/providers/YTMUSIC.md`](./providers/YTMUSIC.md) — ejemplo de referencia

El documento debe cubrir:
1. Requisitos previos y tipo de cuenta necesaria
2. Pasos de autenticación (con capturas o instrucciones claras)
3. Cómo obtener el ID de una playlist
4. Ejemplos de uso con el comando `migrate`
5. Limitaciones conocidas de la API del servicio
6. Solución de problemas comunes

Finalmente, añade el nuevo proveedor a la tabla de la sección **"Servicios Disponibles"** en el [`README.md`](../README.md).

---

## Checklist de Integración

```
[ ] Clase que implementa todos los métodos de MusicProvider
[ ] Excepciones del proyecto (NetworkError, RateLimitError) en llamadas externas
[ ] Decorator @with_retries en métodos con llamadas a APIs externas
[ ] choices en --source y --target actualizados en cli.py
[ ] Instanciación del cliente en main() de cli.py
[ ] Fixture mock_<servicio> añadida en tests/conftest.py
[ ] Tests de migración en ambas direcciones en test_migrator.py
[ ] Documentación en docs/providers/<SERVICIO>.md
[ ] Tabla de "Servicios Disponibles" en README.md actualizada
```
