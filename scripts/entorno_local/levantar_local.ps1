<#



 Levanta TaxiAsiste completo en este computador: base de datos + backend + panel web y, si se pide, la app movil.







 Uso (desde la carpeta del backend):



   .\scripts\entorno_local\levantar_local.ps1                   # base de datos, backend y panel web



   .\scripts\entorno_local\levantar_local.ps1 -ReiniciarBD      # deja la base de demostracion como nueva



   .\scripts\entorno_local\levantar_local.ps1 -Movil emulador   # ademas abre el emulador y la app



   .\scripts\entorno_local\levantar_local.ps1 -Movil usb        # la app en un telefono conectado por USB
   (agregar -ReinstalarApp si Android rechaza la app por conflicto de version o de firma: desinstala la anterior)







 Estructura esperada (la misma en el escritorio y en el notebook):



   <carpeta>\TaxiAsiste-Backend   <carpeta>\TaxiAsiste_Frontend   <carpeta>\TaxiAsiste_Mobile



#>



param(



    [switch]$ReiniciarBD,
    [switch]$ReinstalarApp,



    [ValidateSet('no', 'emulador', 'usb')][string]$Movil = 'no',



    [string]$Avd = 'Pixel_7'



)



$ErrorActionPreference = 'Stop'



$Aqui = Split-Path -Parent $MyInvocation.MyCommand.Path



$Back = (Resolve-Path (Join-Path $Aqui '..\..')).Path



$Raiz = Split-Path -Parent $Back



$Front = Join-Path $Raiz 'TaxiAsiste_Frontend'



$DirMovil = Join-Path $Raiz 'TaxiAsiste_Mobile'



$Py = Join-Path $Back 'venv\Scripts\python.exe'



$env:PYTHONUTF8 = '1'







function Paso($t) { Write-Host "`n== $t" -ForegroundColor Cyan }



function Ok($t) { Write-Host "   $t" -ForegroundColor Green }



function Aviso($t) { Write-Host "   $t" -ForegroundColor Yellow }



# Se usa 127.0.0.1 (no 'localhost'): en PowerShell 5.1 'localhost' prueba primero IPv6 y cada intento tarda ~2 s.

function Esperar($url, $seg) {



    for ($i = 0; $i -lt $seg; $i++) {



        try { $r = Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 5; if ($r.StatusCode -lt 500) { return $true } } catch { }



        Start-Sleep -Seconds 1



    }



    return $false



}



function Escuchando($puerto) { return [bool](Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue) }







Paso 'Verificando requisitos'



if (-not (Test-Path $Py)) { throw "No existe el entorno virtual del backend. Ejecuta primero: .\scripts\entorno_local\preparar_equipo.ps1" }



if (-not (Test-Path (Join-Path $Back '.env'))) { throw "Falta el archivo .env del backend (copia .env.example y completa POSTGRES_PASSWORD)." }



if (-not (Test-Path (Join-Path $Front 'node_modules'))) { throw "El panel web no tiene dependencias instaladas. Ejecuta: .\scripts\entorno_local\preparar_equipo.ps1" }



$pg = Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue | Select-Object -First 1



if (-not $pg) { Aviso 'No se encontro el servicio de PostgreSQL; se intentara conectar igual.' }



elseif ($pg.Status -ne 'Running') { throw "El servicio $($pg.Name) esta detenido. Inicialo (services.msc) y vuelve a ejecutar." }



else { Ok "PostgreSQL en ejecucion ($($pg.Name))" }







Paso 'Preparando la base de datos'



$args2 = @((Join-Path $Aqui 'preparar_bd.py'))



if ($ReiniciarBD) { $args2 += '--reiniciar' }



& $Py @args2



if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar la base de datos.' }







Paso 'Configurando el panel web para usar el backend local'



$envFront = Join-Path $Front '.env'



$lineas = @()



if (Test-Path $envFront) { $lineas = @(Get-Content $envFront) }



$nuevas = @(); $hayApi = $false; $hayMapa = $false



foreach ($l in $lineas) {



    if ($l -match '^VITE_API_URL=') { $nuevas += 'VITE_API_URL=http://localhost:8000/api'; $hayApi = $true }



    else { $nuevas += $l; if ($l -match '^VITE_GOOGLE_MAPS_API_KEY=.+') { $hayMapa = $true } }



}



if (-not $hayApi) { $nuevas += 'VITE_API_URL=http://localhost:8000/api' }



if (-not $hayMapa) { if (-not ($nuevas -match '^VITE_GOOGLE_MAPS_API_KEY=')) { $nuevas += 'VITE_GOOGLE_MAPS_API_KEY=' }; Aviso 'Falta VITE_GOOGLE_MAPS_API_KEY en el .env del panel web: el mapa no se vera hasta completarla.' }



[IO.File]::WriteAllLines($envFront, $nuevas, (New-Object Text.UTF8Encoding $false))



Ok 'VITE_API_URL = http://localhost:8000/api'







Paso 'Levantando el backend (puerto 8000)'



if (Escuchando 8000) { Aviso 'El puerto 8000 ya esta en uso; se asume que el backend ya esta levantado.' }



else {



    $cmd = "`$Host.UI.RawUI.WindowTitle='TaxiAsiste - Backend (8000)'; Set-Location '$Back'; & '$Py' manage.py runserver 0.0.0.0:8000"



    Start-Process powershell -ArgumentList '-NoExit', '-NoProfile', '-Command', $cmd | Out-Null



}



if (Esperar 'http://127.0.0.1:8000/api/ping/' 120) { Ok 'Backend respondiendo en http://localhost:8000/api/ping/' } else { throw 'El backend no respondio en 120 s. Revisa su ventana.' }







Paso 'Levantando el panel web (puerto 5173)'



if (Escuchando 5173) { Aviso 'El puerto 5173 ya esta en uso; se asume que el panel web ya esta levantado.' }



else {



    $cmd = "`$Host.UI.RawUI.WindowTitle='TaxiAsiste - Panel web (5173)'; Set-Location '$Front'; npm run dev -- --host"



    Start-Process powershell -ArgumentList '-NoExit', '-NoProfile', '-Command', $cmd | Out-Null



}



if (Esperar 'http://127.0.0.1:5173' 90) { Ok 'Panel web en http://localhost:5173' } else { throw 'El panel web no respondio en 90 s. Revisa su ventana.' }







if ($Movil -ne 'no') {



    Paso "Preparando la app movil ($Movil)"



    $sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk'



    $adb = Join-Path $sdk 'platform-tools\adb.exe'



    $emu = Join-Path $sdk 'emulator\emulator.exe'



    if (-not (Test-Path $adb)) { throw 'No se encontro adb (Android SDK). Instala Android Studio o las platform-tools.' }



    if ($Movil -eq 'emulador') {



        if (-not (& $adb devices | Select-String 'emulator-')) {



            Start-Process $emu -ArgumentList '-avd', $Avd | Out-Null



            Ok "Abriendo el emulador $Avd..."



        }



        & $adb wait-for-device



        for ($i = 0; $i -lt 90; $i++) { if ((& $adb shell getprop sys.boot_completed 2>$null) -match '1') { break }; Start-Sleep -Seconds 2 }



    }



    & $adb reverse tcp:8000 tcp:8000 | Out-Null
    if ($ReinstalarApp) { & $adb uninstall com.dortiiz.TaxiAsiste_Mobile | Out-Null; Ok 'App anterior desinstalada del dispositivo' }



    Ok 'adb reverse tcp:8000 -> la app usa http://localhost:8000 sin depender de la red Wi-Fi'



    $extra = if ($Movil -eq 'usb') { ' --device' } else { '' }



    $cmd = "`$Host.UI.RawUI.WindowTitle='TaxiAsiste - App movil'; Set-Location '$DirMovil'; `$env:EXPO_PUBLIC_API_BASE_URL='http://localhost:8000'; npx expo run:android$extra"



    Start-Process powershell -ArgumentList '-NoExit', '-NoProfile', '-Command', $cmd | Out-Null



    Ok 'Compilando e instalando la app (la primera vez tarda varios minutos).'



}







$ip = $null



$cfg = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1



if ($cfg) { $ip = ($cfg.IPv4Address | Select-Object -First 1).IPAddress }







Write-Host "`n==============================================================" -ForegroundColor Green



Write-Host ' TaxiAsiste local listo' -ForegroundColor Green



Write-Host '==============================================================' -ForegroundColor Green



Write-Host ' Panel web ........ http://localhost:5173'



Write-Host ' API .............. http://localhost:8000/api/   (documentacion: http://localhost:8000/api/docs/)'



if ($ip) { Write-Host " Desde otro equipo  http://${ip}:5173  (misma red; puede requerir permitir el puerto en el firewall)" }



Write-Host ''



Write-Host ' Usuarios de demostracion (datos de semilla; clave = <usuario>123):'



Write-Host '   admin  central  tesorero  conductor  paletero'



Write-Host ''



Write-Host ' Para detener todo: .\scripts\entorno_local\detener_local.ps1'



