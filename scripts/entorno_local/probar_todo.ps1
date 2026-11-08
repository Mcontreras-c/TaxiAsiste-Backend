<#
 Ejecuta todas las pruebas automatizadas de TaxiAsiste en este computador y guarda un informe con los resultados
 y las caracteristicas del equipo (sirve como evidencia para el informe: escritorio vs notebook).

 Uso (desde la carpeta del backend):
   .\scripts\entorno_local\probar_todo.ps1               # backend (pytest) + panel web (vitest + compilacion) + app movil (jest)
   .\scripts\entorno_local\probar_todo.ps1 -SinCompilar  # omite la compilacion del panel web
#>
param([switch]$SinCompilar)
$ErrorActionPreference = 'Continue'
$Aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
$Back = (Resolve-Path (Join-Path $Aqui '..\..')).Path
$Raiz = Split-Path -Parent $Back
$Front = Join-Path $Raiz 'TaxiAsiste_Frontend'
$DirMovil = Join-Path $Raiz 'TaxiAsiste_Mobile'
$Py = Join-Path $Back 'venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
$env:CI = 'true'   # evita modos interactivos (watch) en vitest/jest

function Paso($t) { Write-Host "`n== $t" -ForegroundColor Cyan }
function Commit($dir) { try { (git -C $dir rev-parse --short HEAD 2>$null) + ' (' + (git -C $dir rev-parse --abbrev-ref HEAD 2>$null) + ')' } catch { '?' } }

$resultados = @()
function Correr($nombre, $dir, $bloque, $patron, $unidad = 'pruebas') {
    Paso $nombre
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Push-Location $dir
    $salida = & $bloque 2>&1 | Out-String
    $codigo = $LASTEXITCODE
    Pop-Location
    $sw.Stop()
    $ok = 0; $m = [regex]::Match($salida, $patron); if ($m.Success) { $ok = [int]$m.Groups[1].Value }
    $estado = if ($codigo -eq 0) { 'APROBADO' } else { 'FALLO' }
    Write-Host ("   {0}: {1} {2}, {3:N1} s" -f $estado, $ok, $unidad, $sw.Elapsed.TotalSeconds) -ForegroundColor $(if ($codigo -eq 0) { 'Green' } else { 'Red' })
    if ($codigo -ne 0) { ($salida -split "`n" | Select-Object -Last 25) -join "`n" | Write-Host }
    $script:resultados += [pscustomobject]@{ Componente = $nombre; Resultado = "$ok $unidad"; Pruebas = $(if ($unidad -eq 'pruebas') { $ok } else { 0 }); Estado = $estado; Segundos = [math]::Round($sw.Elapsed.TotalSeconds, 1) }
}

Paso 'Preparando la base de pruebas (taxiasiste_test)'
& $Py (Join-Path $Aqui 'preparar_bd.py') --test --sin-seed | Select-Object -Last 4

Correr 'Backend (pytest)' $Back { & $Py -m pytest -q -p no:cacheprovider --no-header -o addopts='' } '(\d+) passed'
Correr 'Panel web (vitest)' $Front { npm test } 'Tests\s+(\d+) passed'
if (-not $SinCompilar) { Correr 'Panel web (compilacion tsc + vite)' $Front { npm run build } '(\d+) modules transformed' 'modulos' }
Correr 'App movil (jest)' $DirMovil { npm test } 'Tests:\s+(\d+) passed'

$cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1)
$ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
$so = (Get-CimInstance Win32_OperatingSystem).Caption
$lineas = @()
$lineas += "Pruebas automatizadas de TaxiAsiste - $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$lineas += "Equipo: $env:COMPUTERNAME | $($cpu.Name.Trim()) ($($cpu.NumberOfCores) nucleos) | $ram GB RAM | $so"
$lineas += "Versiones: $(& $Py --version) | node $(node --version) | PostgreSQL local"
$lineas += "Commits: backend $(Commit $Back) | panel web $(Commit $Front) | app movil $(Commit $DirMovil)"
$lineas += ''
$lineas += ($resultados | Select-Object Componente, Resultado, Estado, Segundos | Format-Table -AutoSize | Out-String).TrimEnd()
$total = ($resultados | Measure-Object -Property Pruebas -Sum).Sum
$fallos = @($resultados | Where-Object { $_.Estado -ne 'APROBADO' }).Count
$lineas += ''
$lineas += "Total de pruebas automatizadas: $total | Componentes con fallos: $fallos"

$dirRes = Join-Path $Aqui 'resultados'
New-Item -ItemType Directory -Force $dirRes | Out-Null
$archivo = Join-Path $dirRes ("pruebas_{0}_{1}.txt" -f $env:COMPUTERNAME, (Get-Date -Format 'yyyyMMdd_HHmm'))
[IO.File]::WriteAllLines($archivo, $lineas, (New-Object Text.UTF8Encoding $false))

Write-Host "`n==============================================================" -ForegroundColor Green
$lineas | ForEach-Object { Write-Host $_ }
Write-Host "`nInforme guardado en: $archivo" -ForegroundColor Green
if ($fallos -gt 0) { exit 1 }
