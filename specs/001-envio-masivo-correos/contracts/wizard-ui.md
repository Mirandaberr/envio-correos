# Contract: Asistente (UI)

Contrato entre la GUI y el núcleo: cada paso tiene un *presenter* sin Tk (testeable) que expone
estado y validaciones; la vista solo dibuja y reenvía eventos. Textos en español, sin jerga.

| # | Paso | Entra con | Puede avanzar si | Sale con |
|---|---|---|---|---|
| 0 | Inicio | — | — | "Nuevo envío" · "Reintentar fallidos de una campaña anterior" · aviso "Hay un envío sin terminar" (US7) |
| 1 | Cuenta | cuenta recordada (opcional) | `test_connection() == OK` | `SenderAccount` + provider abierto |
| 2 | Destinatarios | archivo `.xlsx` | ≥ 1 destinatario efectivo | `RecipientList` con selección |
| 3 | Mensaje | borrador (FR-033) o plantilla de la campaña (reintento) | variables existentes; adjuntos ≤ límite | `MessageTemplate` |
| 4 | Modo | — | una opción elegida (ninguna por defecto); sin variables si `ALL_AT_ONCE` | `SendMode` |
| 5 | Revisión | todo lo anterior | confirmación explícita (cantidad + modo + tiempo estimado + aviso de límite diario) | `Campaign` creada en journal |
| 6 | Envío | `Campaign` | — (Detener disponible) | intento en `DONE` / `STOPPED` / `PAUSED` |
| 7 | Resultado | intento | — | "Abrir Excel de fallidos" · "Corregir y reintentar" · "Nuevo envío" · "Abrir carpeta de registros" |

## Paso 2 — Destinatarios (detalle por FR-022/024/025/026)
- Barra superior: selector de hoja, selector de columna de correo, **buscador** (filtra al
  escribir, con un *debounce* de 200 ms; ícono de lupa y botón ✕ para limpiar).
- Tabla: columna de casilla + columna "Estado" + columnas originales. Clic o barra espaciadora
  alterna la casilla; filas no marcables se ven en gris con el motivo como tooltip.
- Botones "Marcar visibles" / "Desmarcar visibles" (actúan sobre el resultado de la búsqueda).
- Pie: `Se enviará a N` · `Válidos X` · `Inválidos Y` · `Duplicados Z` · `Excluidos W`, y
  filtros rápidos por estado.
- Verificación de dominios en segundo plano con indicador "Verificando dominios… 12/40".

## Paso 4 — Modo
Dos tarjetas grandes lado a lado, distintas en ícono y color:
- **"Uno por uno"** — "Cada persona recibe su propio correo, con su nombre. Nadie ve a los demás."
- **"Todos a la vez"** — "Un mismo correo para todos. Por defecto nadie ve a los demás (copia
  oculta)." + casilla "Mostrar los destinatarios entre sí" → advertencia de privacidad.

## Paso 7 — "Corregir y reintentar" (US3)
1. Abre el Excel de fallidos con la aplicación predeterminada (`os.startfile`).
2. Muestra: "Corregí el archivo, guardalo y cerralo. Después pulsá **Continuar**."
3. Continuar → relee (si el archivo sigue abierto/bloqueado: "Cerrá el archivo en Excel para
   continuar") → Paso 2 con la lista del reintento → Paso 3 precargado → … (intento N+1).

## Accesibilidad mínima
Navegable con teclado (Tab/Enter/Espacio), contraste suficiente, tamaño de fuente ≥ 11 pt.
