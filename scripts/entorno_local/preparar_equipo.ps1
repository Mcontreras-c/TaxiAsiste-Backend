<#
 Deja un computador listo para trabajar y presentar TaxiAsiste (escritorio o notebook).
 Instala las dependencias de los tres proyectos y crea los archivos .env. NO instala programas del sistema:
 si falta alguno, avisa cual y como instalarlo.

 Uso (PowerShell):
   # En un equipo nuevo, sin nada clonado todavia:
   mkdir C:\TaxiAsisteAPP ; cd C:\TaxiAsisteAPP
   git clone https://github.com/Mcontreras-c/TaxiAsiste-Backend.git
   .\TaxiAsiste-Backend\scripts\entorno_local\preparar_equipo.ps1

 Las claves (contrasena de PostgreSQL, clave de Google Maps) las escribes tu cuando el script las pide;
 no se muestran ni se guardan en ningun otro lugar que no sea el .env local (que git ignora).
#>
$ErrorActionPreference = 'Stop'
$Aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
$Back = (Resolve-Path (Join-Path $Aqui '..\..')).Path
$Raiz = Split-Path -Parent $Back
$Repos = [ordered]@{
    'TaxiAsiste_Frontend' = 'https://github.com/Mcontreras-c/TaxiAsiste-Frontend.git'
    'TaxiAsiste_Mobile'   = 'https://github.com/Mcontreras-c/TaxiAsiste-Mobile.git'
}
function Paso($t) { Write-Host "`n== $t" -ForegroundColor Cyan }
function Ok($t) { Write-Host "   $t" -ForegroundColor Green }
function Aviso($t) { Write-Host "   $t" -ForegroundColor Yellow }
function Falta($t) { Write-Host "   FALTA: $t" -ForegroundColor Red; $script:faltan += $t }
function LeerSecreto($pregunta) {
    $s = Read-Host $pregunta -AsSecureString
    return [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
}

Paso 'Verificando programas necesarios'
$faltan = @()
if (Get-Command git -ErrorAction SilentlyContinue) { Ok (git --version) } else { Falta 'Git (https://git-scm.com/download/win)' }
$pyGlobal = $null
foreach ($c in 'py -3.12', 'python') {
    try { $v = Invoke-Expression "$c --version" 2>$null; if ($v -match 'Python 3\.(1[2-9]|[2-9]\d)') { $pyGlobal = $c; Ok "$v ($c)"; break } } catch { }
}
if (-not $pyGlobal) { Falta 'Python 3.12 o superior (https://www.python.org/downloads/)' }
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nv = (node --version); Ok "Node $nv"
    if ([int]($nv.TrimStart('v').Split('.')[0]) -lt 20) { Falta 'Node 20 o superior (https://nodejs.org)' }
} else { Falta 'Node.js 20 o superior (https://nodejs.org)' }
$pg = Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($pg) { Ok "PostgreSQL: servicio $($pg.Name) ($($pg.Status))" } else { Falta 'PostgreSQL 14 o superior (https://www.postgresql.org/download/windows/)' }
$sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
if (Test-Path $sdk) { Ok 'Android SDK (adb) encontrado' } else { Aviso 'Android SDK no encontrado: solo hace falta para la app movil en emulador/telefono (Android Studio).' }
if ($faltan.Count -gt 0) { throw "Instala lo que falta y vuelve a ejecutar:`n - " + ($faltan -join "`n - ") }

Paso 'Clonando los proyectos que falten'
foreach ($n in $Repos.Keys) {
    $d = Join-Path $Raiz $n
    if (Test-Path (Join-Path $d '.git')) { Ok "$n ya existe" }
    else { git clone $Repos[$n] $d; Ok "$n clonado" }
}

Paso 'Backend: entorno virtual y dependencias'
$venv = Join-Path $Back 'venv'
if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) { Invoke-Expression "$pyGlobal -m venv '$venv'" }
& (Join-Path $venv 'Scripts\python.exe') -m pip install --quiet --upgrade pip
& (Join-Path $venv 'Scripts\python.exe') -m pip install --quiet -r (Join-Path $Back 'requirements.txt')
Ok 'Dependencias de Python instaladas'

Paso 'Backend: archivo .env'
$envBack = Join-Path $Back '.env'
if (Test-Path $envBack) { Ok '.env ya existe (no se modifica)' }
else {
    $clave = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 50 | ForEach-Object { [char]$_ })
    $pw = LeerSecreto 'Contrasena del usuario postgres de ESTE equipo (la escribes tu; no se muestra)'
    $maps = Read-Host 'Clave de Google Maps del backend (Enter para dejarla vacia; los mapas no funcionaran sin ella)'
    $txt = @"
SECRET_KEY=$clave
DEBUG=True
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=taxiasiste_dev
POSTGRES_USER=postgres
POSTGRES_PASSWORD=$pw
POSTGRES_TEST_DB=taxiasiste_test
GOOGLE_MAPS_API_KEY=$maps
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=
APK_DOWNLOAD_URL=
PANEL_WEB_URL=http://localhost:5173
"@
    [IO.File]::WriteAllText($envBack, $txt, (New-Object Text.UTF8Encoding $false))
    Ok '.env creado (sin correo: el envio de credenciales por email no funcionara en local)'
}

Paso 'Panel web: dependencias y .env'
$Front = Join-Path $Raiz 'TaxiAsiste_Frontend'
Push-Location $Front; npm ci --no-audit --no-fund 2>&1 | Select-Object -Last 2; Pop-Location
$envFront = Join-Path $Front '.env'
if (Test-Path $envFront) { Ok '.env del panel web ya existe (levantar_local.ps1 lo ajusta a localhost)' }
else {
    $mapsF = Read-Host 'Clave de Google Maps del panel web (Enter para dejarla vacia)'
    [IO.File]::WriteAllLines($envFront, @('VITE_API_URL=http://localhost:8000/api', "VITE_GOOGLE_MAPS_API_KEY=$mapsF"), (New-Object Text.UTF8Encoding $false))
    Ok '.env del panel web creado'
}

Paso 'App movil: dependencias'
$DirMovil = Join-Path $Raiz 'TaxiAsiste_Mobile'
Push-Location $DirMovil; npm ci --no-audit --no-fund 2>&1 | Select-Object -Last 2; Pop-Location
Ok 'Dependencias de la app movil instaladas'

Paso 'Base de datos'
$env:PYTHONUTF8 = '1'
& (Join-Path $venv 'Scripts\python.exe') (Join-Path $Aqui 'preparar_bd.py') --test

Write-Host "`nEquipo listo. Ahora puedes ejecutar:" -ForegroundColor Green
Write-Host '   .\scripts\entorno_local\levantar_local.ps1     (levanta todo)'
Write-Host '   .\scripts\entorno_local\probar_todo.ps1        (corre todas las pruebas)'
