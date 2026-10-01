# Data Model: Envío masivo de correos guiado

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

Hay dos representaciones: **en memoria** (núcleo, optimizada para memoria acotada — research R7)
y **persistida** en el journal SQLite (research R6). Las entidades de la spec se mapean así.

## Entidades en memoria

### `SenderAccount`
| Campo | Tipo | Regla |
|---|---|---|
| `email` | `str` | Sintaxis válida; es siempre el `From` (research R3, 5.7.60) |
| `display_name` | `str` | Opcional; por defecto la parte local del correo |
| `provider_id` | `str` | `"m365-smtp-password"` en v1 (principio VII) |

La contraseña **no** es un campo: vive solo en keyring (servicio `EnvioCorreos`, usuario = `email`)
o en memoria dentro del `SendProvider` mientras dura la sesión.

### `RecipientList`
Diseñada para no duplicar datos (FR-075):

| Campo | Tipo | Nota |
|---|---|---|
| `source_path` | `Path` | Excel de origen |
| `sheet_name` | `str` | |
| `headers` | `tuple[str, ...]` | En orden original; vacíos → `"Columna C"` |
| `rows` | `list[tuple]` | **Una tupla por fila**, valores crudos; sin filas totalmente vacías |
| `source_row_numbers` | `array('I')` | Número de fila en Excel, para mensajes y reporte |
| `email_col` | `int` | Índice en `headers`; autodetectado y editable (FR-021) |
| `search_index` | `list[str]` | Una cadena normalizada por fila (casefold + sin tildes), lazy |
| `selected` | `bytearray` | 1 byte por fila: 1 = marcada (FR-024). La búsqueda **no** la toca |
| `status` | `bytearray` | Código de `ValidationStatus` por fila |
| `reason` | `dict[int, str]` | Solo para filas no válidas (disperso) |

`ValidationStatus`: `VALID`, `INVALID_SYNTAX`, `INVALID_DOMAIN` (FR-026), `MULTIPLE_ADDRESSES`,
`EMPTY`, `DUPLICATE`, `ALREADY_SENT` (solo en reintentos, FR-064).

Reglas:
- Normalización de dirección: `strip()`; dominio en minúsculas; parte local tal cual (RFC 5321).
- Duplicado = misma dirección normalizada (comparación case-insensitive); la primera aparición es
  `VALID`, las siguientes `DUPLICATE` y desmarcadas.
- Marcado por defecto: `VALID` → 1; resto → 0. `ALREADY_SENT` → 0 pero se puede marcar (FR-064).
- Las filas `INVALID_*`, `EMPTY` y `MULTIPLE_ADDRESSES` **no se pueden marcar**.
- Destinatarios efectivos = filas con `selected == 1` y `status ∈ {VALID, ALREADY_SENT}`.
- Las columnas agregadas por la app (`Estado`, `Motivo`, `Código de campaña`) se reconocen y no se
  ofrecen como variables ni como columna de correo (US2-AS3).

### `MessageTemplate`
| Campo | Tipo | Regla |
|---|---|---|
| `subject` | `str` | Vacío permitido tras confirmar |
| `body` | `str` | Texto plano |
| `attachments` | `list[AttachmentRef]` | `path`, `size`, `sha256` (para detectar cambios en un reintento) |

Variables: `{Nombre de columna}` exacto (sensible a tildes, no a mayúsculas). `{{` y `}}` escapan
llaves literales. Una variable inexistente es error de validación en el paso Mensaje; un valor
vacío en una fila es advertencia en Revisión (US5-AS2). En modo `ALL_AT_ONCE`, cualquier variable
bloquea el avance (FR-042).

### `SendMode`
`ONE_BY_ONE` | `ALL_AT_ONCE_BCC` | `ALL_AT_ONCE_VISIBLE` (requiere confirmar la advertencia, FR-041).

## Journal persistido (SQLite, WAL)

Ubicación: `platformdirs.user_data_dir("EnvioCorreos", appauthor=False)` → `campaigns.db`.

```text
campaign
  id              TEXT PK       -- "C-7F3A" (4 hex aleatorios, reintento si colisiona)
  created_at      TEXT ISO-8601
  account_email   TEXT
  source_path     TEXT
  sheet_name      TEXT
  headers_json    TEXT          -- lista ordenada de encabezados originales
  email_col       INTEGER
  subject         TEXT
  body            TEXT          -- plantilla (no el texto renderizado)
  attachments_json TEXT         -- [{path,size,sha256}]
  mode            TEXT          -- SendMode

attempt
  campaign_id     TEXT FK
  number          INTEGER       -- 1 = original, 2.. = reintentos → código "C-7F3A-R2"
  started_at, finished_at TEXT
  state           TEXT          -- RUNNING | PAUSED | STOPPED | INTERRUPTED | DONE
  report_path     TEXT NULL
  headers_json    TEXT NULL     -- encabezados del archivo de este intento (un reintento usa el
                                -- Excel de fallidos, cuyas columnas pueden diferir); NULL = los
                                -- de la campaña
  PK (campaign_id, number)

recipient
  campaign_id     TEXT
  attempt_number  INTEGER
  row_seq         INTEGER       -- orden dentro del intento
  source_row      INTEGER       -- fila en el Excel de ese intento
  address         TEXT          -- normalizada
  row_values_json TEXT          -- valores originales de la fila (para el reporte)
  state           TEXT          -- PENDING | SENDING | SENT | FAILED | SKIPPED
  reason_code     TEXT NULL     -- ver contracts/send-provider.md
  reason_text     TEXT NULL     -- mensaje en español
  smtp_code       TEXT NULL     -- p. ej. "550 5.1.1" (sin el texto completo del servidor)
  updated_at      TEXT
  PK (campaign_id, attempt_number, row_seq)
  INDEX (campaign_id, address, state)       -- FR-064 "¿ya enviado?"
  INDEX (state, updated_at)                 -- límite de 24 h (research R2)
```

Retención: al iniciar la app se borran campañas con `created_at` > 30 días (FR-065, FR-077).

## Transiciones de estado

### Destinatario (por intento)
```text
PENDING ──(antes de enviar, commit)──▶ SENDING ──▶ SENT
   │                                      │
   │                                      ├──▶ FAILED   (5xx permanente para ese destinatario)
   │                                      └──▶ PENDING  (4xx transitorio agotado → campaña PAUSED)
   └──▶ SKIPPED (inválido, duplicado, excluido por usuario, detenido por usuario)

Al abrir la app con un intento RUNNING (cierre inesperado):
   SENDING ──▶ "No se sabe si se envió": se muestra aparte, desmarcado por defecto (SC-004)
```

### Intento
```text
RUNNING ──▶ DONE         (todos procesados)
RUNNING ──▶ PAUSED       (transitorio persistente / límite diario) ──▶ RUNNING (continuar)
RUNNING ──▶ STOPPED      (usuario pulsa Detener; pendientes → SKIPPED "Detenido por el usuario")
RUNNING ──▶ INTERRUPTED  (detectado al reabrir) ──▶ RUNNING (continuar) | STOPPED (descartar)
```

## Qué filas van al Excel de fallidos (FR-061)

| Estado final | Motivo | ¿Va al reporte? |
|---|---|---|
| `FAILED` | cualquiera | Sí |
| `SKIPPED` | inválido (sintaxis, dominio, vacío, varias direcciones) | Sí |
| `SKIPPED` | detenido por el usuario / interrumpido | Sí (como "Pendiente") |
| `PENDING` | pausa no reanudada | Sí (como "Pendiente") |
| `SENDING` | "no se sabe si se envió" | Sí, con ese motivo explícito |
| `SKIPPED` | excluido por el usuario | **No** |
| `SKIPPED` | duplicado | **No** |
| `SENT` | — | No |
