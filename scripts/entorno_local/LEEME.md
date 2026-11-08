# Entorno local de TaxiAsiste (escritorio y notebook)

Todo el sistema corre en un solo computador, sin depender del servidor: **PostgreSQL local + backend Django (8000) + panel web (5173) + app móvil** (emulador o teléfono por USB). Sirve para desarrollar y para presentar en el instituto sin necesitar internet para la parte propia del sistema (solo los mapas y la geocodificación usan Google).

Estructura de carpetas (igual en ambos equipos):

```
C:\TaxiAsisteAPP\
  TaxiAsiste-Backend\     (este repositorio; aquí están los scripts)
  TaxiAsiste_Frontend\    (panel web)
  TaxiAsiste_Mobile\      (app móvil)
```

## Primera vez en un equipo (por ejemplo, el notebook)
Requisitos: Git, Python 3.12+, Node 20+, PostgreSQL 14+ (y Android Studio solo si se usará la app móvil).

```powershell
mkdir C:\TaxiAsisteAPP ; cd C:\TaxiAsisteAPP
git clone https://github.com/Mcontreras-c/TaxiAsiste-Backend.git
cd TaxiAsiste-Backend
.\scripts\entorno_local\preparar_equipo.ps1
```
El script clona los otros dos proyectos, instala dependencias, crea los `.env` (pide la contraseña de PostgreSQL y la clave de Google Maps; **las escribes tú**) y prepara las bases.

## Uso diario
```powershell
cd C:\TaxiAsisteAPP\TaxiAsiste-Backend
.\scripts\entorno_local\levantar_local.ps1                  # base + backend + panel web
.\scripts\entorno_local\levantar_local.ps1 -ReiniciarBD     # deja la base de demostración como nueva
.\scripts\entorno_local\levantar_local.ps1 -Movil emulador  # + emulador Pixel_7 y la app
.\scripts\entorno_local\levantar_local.ps1 -Movil usb       # + la app en un teléfono conectado por USB
.\scripts\entorno_local\probar_todo.ps1                     # todas las pruebas automatizadas + informe del equipo
.\scripts\entorno_local\detener_local.ps1                   # detiene backend, panel web y Metro
```

- Panel web: <http://localhost:5173> · API: <http://localhost:8000/api/> · Documentación: <http://localhost:8000/api/docs/>
- Usuarios de demostración (datos de semilla; clave = `<usuario>123`): `admin`, `central`, `tesorero`, `conductor`, `paletero`.

## Respaldo de la base de datos
```powershell
.\venv\Scripts\python.exe scripts\entorno_local\respaldo_local.py            # respalda la base y los documentos en C:\TaxiAsisteAPP\respaldos
.\venv\Scripts\python.exe scripts\entorno_local\respaldo_local.py --probar   # además restaura en una base temporal y compara los registros de las 16 tablas
.\venv\Scripts\python.exe scripts\entorno_local\respaldo_local.py --destino D:\respaldos   # a un pendrive u otro disco
```
Conserva 7 días y verifica cada respaldo con `pg_restore -l`. Copiar la carpeta a un pendrive o a la nube da una copia fuera del computador.

## La app móvil sin depender de la red Wi‑Fi
El script usa `adb reverse tcp:8000 tcp:8000` y compila la app con `EXPO_PUBLIC_API_BASE_URL=http://localhost:8000`. Así la app (en el emulador o en un teléfono conectado por cable) llega al backend del computador aunque cambie la red (por ejemplo, la del instituto). La primera compilación de la app tarda varios minutos.

Si se prefiere un teléfono por Wi‑Fi (sin cable), hay que generar un APK con la IP del computador (perfil `preview-local` de `eas.json`, ajustando la IP) y permitir el puerto 8000 en el firewall de Windows.

## Qué cambia respecto del servidor
- Sin HTTPS ni dominio; el panel y la API quedan en `localhost`.
- Sin correo saliente (no hay credenciales SMTP): crear una persona funciona, pero el correo de bienvenida no se envía (la clave provisoria se puede restablecer desde el panel).
- Mapas y geocodificación requieren internet y la clave de Google Maps en los `.env`.
- Las bases son `taxiasiste_dev` (demostración) y `taxiasiste_test` (pruebas automatizadas); no se mezclan.

## Problemas frecuentes
| Síntoma | Causa y solución |
|---|---|
| «El servicio postgresql… está detenido» | Iniciar PostgreSQL desde `services.msc`. |
| «El puerto 8000 ya está en uso» | Ya hay un backend levantado: usar `detener_local.ps1` y volver a ejecutar. |
| El mapa se ve en gris/negro | Falta `VITE_GOOGLE_MAPS_API_KEY` (panel) o la clave del backend en su `.env`. |
| La app no conecta | Revisar que haya un solo dispositivo/emulador en `adb devices` y repetir `adb reverse tcp:8000 tcp:8000`. |
| Una prueba falla en un equipo y no en el otro | Comparar los informes de `scripts\entorno_local\resultados\` (incluyen versiones y commits). |
