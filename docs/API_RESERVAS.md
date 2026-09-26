# API de Reservas (viajes programados)

Contrato para la app mobile (conductor) y el panel web (Central). Todo bajo `/api/`, con el
mismo JWT del resto de la API. Las horas viajan en **UTC con `Z`** (ej. `2026-09-27T21:30:00Z`):
convertir a hora local solo al mostrarlas, siempre en **formato 24 h**.

## Reglas de negocio (viven en el servidor; la app solo las muestra)

| Regla | Valor | Ajustable en `settings.py` |
|---|---|---|
| Anticipación mínima al crear | 30 min | `RESERVA_ANTICIPACION_MIN` |
| Horizonte máximo | 24 h | `RESERVA_HORIZONTE_HORAS` |
| Máximo de reservas activas por conductor | 3 | `RESERVA_MAX_ACTIVAS` |
| Margen antes y después de cada reserva | 15 min | `RESERVA_MARGEN_MIN` |
| Soltar sin consecuencia hasta | 2 h antes | `RESERVA_SOLTAR_SIN_PENALIZACION_H` |

**Franja que ocupa una reserva** (todos los viajes terminan en el hospital, por eso el mismo
`duracion_estimada_s` sirve para la ida y para el viaje):

```
salida_base_maxima = recogida - duracion - margen     (hora límite para salir del hospital)
libre_desde        = recogida + duracion + margen     (vuelve a quedar libre)
```

Un conductor no puede tener dos reservas cuyas franjas se cruzan. Justo en el límite se permite.

## Estados

`PROGRAMADA` (sin conductor) → `ASIGNADA` (la tomó un conductor) → `EN_CAMINO` → `COMPLETADA`.
También `CANCELADA` (Central) e `INCUMPLIDA`. Soltar devuelve `ASIGNADA` → `PROGRAMADA`.
`EN_CAMINO`, `COMPLETADA` e `INCUMPLIDA` los produce la etapa 3 (aún no hay endpoints para eso).

## Objeto Reserva

```json
{
  "id_reserva": 12.0,
  "folio": "RES-2026-00012",
  "estado": "PROGRAMADA",
  "origen": "Av. Pajaritos 3000",
  "origen_lat": "-33.450000", "origen_lng": "-70.660000",
  "destino": "Hospital Félix Bulnes, Cerro Navia",
  "fecha_hora_recogida": "2026-09-27T21:30:00Z",
  "duracion_estimada_s": 1200,
  "distancia_estimada_m": 6000,
  "tarifa_estimada": 6500,
  "salida_base_maxima": "2026-09-27T20:55:00Z",
  "libre_desde": "2026-09-27T22:05:00Z",
  "pasajero": 4, "pasajero_nombre": "Luis Soto", "pasajero_telefono": "+56911111111",
  "movil": null, "movil_patente": null, "conductor_nombre": null,
  "observaciones": "Silla de ruedas",
  "fecha_creacion": "...", "fecha_tomada": null, "fecha_termino": null
}
```

Ojo: los `id_*` llegan como número con decimal (`12.0`) en este proyecto. En las URLs se usa
tal cual vienen (`/api/reservas/12.0/tomar/`), igual que en solicitudes.

## Conductor (rol `Conductor`) — lo que necesita la app

Usan el móvil del socio del conductor; no hay que mandarlo. No se exige que esté conectado
(`INACTIVO`): reservar es comprometerse para más tarde. Un móvil `BLOQUEADO` no puede tomar.

### `GET /api/reservas/disponibles/`
Reservas sin conductor a las que aún se llega a tiempo, ordenadas por hora. **Sin datos del
pasajero** (`pasajero_nombre` y `pasajero_telefono` vienen `null`). Cada una agrega:

- `puede_tomar` (bool)
- `motivo_bloqueo` (texto o `null`), listo para mostrar. Por ejemplo
  `"Se cruza con tu reserva de las 18:30 (RES-2026-00010)."` o `"Ya tienes 3 reservas activas."`

Mostrar las que no se pueden tomar deshabilitadas, con su motivo.

### `GET /api/reservas/mias/`
Reservas activas del conductor (`ASIGNADA`, `EN_CAMINO`), **con** nombre y teléfono del pasajero.

### `POST /api/reservas/{id}/tomar/`
Sin cuerpo. `200` con la reserva (`ASIGNADA`). Errores, todos con `{"detail": "..."}` listo para mostrar:

| Código | Cuándo |
|---|---|
| `403` | La cuenta no tiene móvil disponible (sin móvil, socio inactivo o móvil bloqueado) |
| `409` | Otro conductor la tomó, ya pasó la hora máxima de salida, ya tiene 3 activas, o se cruza con otra suya |

### `POST /api/reservas/{id}/soltar/`
Sin cuerpo. `200` con la reserva de vuelta en `PROGRAMADA`, más `"soltada_tarde": true|false`.
Si `soltada_tarde` es `true` (faltaban menos de 2 h) queda registrado como incumplimiento; la
app debería **avisar antes de soltar** cuando falte menos de 2 h. `403` si no es suya, `409` si
ya no está `ASIGNADA`.

## Central (roles `Administrador` y `Central`)

### `POST /api/reservas/`
```json
{ "origen": "Av. Pajaritos 3000", "fecha_hora_recogida": "2026-09-27T21:30:00Z",
  "pasajero": 4, "observaciones": "Silla de ruedas" }
```
`pasajero` y `observaciones` son opcionales. El servidor ubica el origen (Google), calcula duración,
distancia y tarifa estimada con el tráfico previsto para esa hora, y guarda todo. `201` con la
reserva. Errores `400` (menos de 30 min o más de 24 h), `404` (origen no ubicable), `502` (Google caído).

### `GET /api/reservas/`
Vigentes por defecto (`PROGRAMADA`, `ASIGNADA`, `EN_CAMINO`). `?estado=CANCELADA` filtra por uno;
`?estado=todas` trae todo.

### `POST /api/reservas/{id}/cancelar/`
`{"motivo": "..."}` opcional. Solo `PROGRAMADA` o `ASIGNADA`.

## Auditoría

Cada cambio queda en la tabla `RESERVA_EVENTOS` (`CREADA`, `TOMADA`, `SOLTADA`, `SOLTADA_TARDE`,
`CANCELADA`). Es la base del registro de incumplimientos (etapa 3).

## Para la salida automática de la fila

`salida_base_maxima` de la reserva activa más próxima del conductor es el momento en que debe salir
de la fila virtual.

## Base de datos

Requiere `scripts/migrar_reservas_postgres.sql` (tablas `RESERVAS` y `RESERVA_EVENTOS`, y sus
secuencias). Es idempotente. En una base nueva hay que correrlo además del esquema principal.
