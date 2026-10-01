# Contract: Excel de fallidos (salida de una campaña y entrada de un reintento)

## Nombre y ubicación
- `<nombre-original>_fallidos_<AAAAMMDD-HHMM>.xlsx`, en la carpeta del Excel original.
- Si no hay permiso de escritura o el archivo está abierto: se pide otra carpeta (diálogo
  "Guardar como") con el mismo nombre sugerido.

## Hoja `Fallidos` (visible, primera)
| Columnas | Contenido |
|---|---|
| 1..N | Las columnas originales, **mismos encabezados y mismo orden**, valores originales de la fila (no normalizados) |
| N+1 `Estado` | `Fallido` \| `Inválido` \| `Pendiente` \| `No se sabe si se envió` |
| N+2 `Motivo` | Texto en español de la tabla de [send-provider.md](./send-provider.md) o de validación |
| N+3 `Código de campaña` | `C-7F3A` o `C-7F3A-R2` |

- Primera fila: encabezados, en negrita, panel inmovilizado (`freeze_panes`, configurado antes de
  agregar filas porque es write-only — research R7.2).
- Filas: solo las que indica la tabla "Qué filas van al Excel de fallidos" de
  [data-model.md](../data-model.md), en el orden original.
- Si el origen ya era un Excel de fallidos (reintento), las columnas `Estado`, `Motivo` y
  `Código de campaña` previas se **reemplazan**, no se duplican.

## Hoja `_meta` (oculta, `sheet_state = "hidden"`)
| A | B |
|---|---|
| `format_version` | `1` |
| `campaign_id` | `C-7F3A` |
| `attempt` | `2` |
| `email_column` | encabezado de la columna de correo |
| `generated_at` | ISO-8601 |

## Lectura como entrada de reintento (FR-063)
1. Si existe `_meta` con `format_version == 1` → usa `campaign_id` y `email_column`.
2. Si no, si existe la columna `Código de campaña` con un valor que exista en el journal → usa ese.
3. Si no se encuentra la campaña → se trata como una campaña nueva (se ofrece redactar el mensaje).
4. Las columnas `Estado`, `Motivo` y `Código de campaña` se ignoran como datos y variables.
5. Filas agregadas a mano: se tratan como destinatarios normales; filas borradas: no se envían.
