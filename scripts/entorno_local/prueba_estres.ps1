<#
 Prueba de estres local de TaxiAsiste (la misma del informe, seccion 5.1), repetible en cualquier equipo.
 Crea una base temporal (taxiasiste_stress), simula 100 conductores enviando GPS, usuarios de Central consultando
 el mapa y la fila, con 1x, 2x y 4x la carga, y con/sin conexiones persistentes. Al terminar borra la base temporal.
 No toca taxiasiste_dev ni taxiasiste_test.

 Uso (desde la carpeta del backend; cierra otros programas pesados para no distorsionar las mediciones):
   .\scripts\entorno_local\prueba_estres.ps1            # completa: 6 etapas de 90 s (~12 minutos)
   .\scripts\entorno_local\prueba_estres.ps1 -Rapida    # 6 etapas de 30 s (~5 minutos), solo orientativa
#>
param([switch]$Rapida)
$ErrorActionPreference = 'Stop'
$Aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
$Back = (Resolve-Path (Join-Path $Aqui '..\..')).Path
$Py = Join-Path $Back 'venv\Scripts\python.exe'
$Est = Join-Path $Aqui 'estres'
$env:PYTHONUTF8 = '1'
if ($Rapida) { $env:STRESS_DURACION = '30' } else { $env:STRESS_DURACION = '90' }

Write-Host "`n== Instalando las herramientas de la prueba en el venv (locust, waitress)" -ForegroundColor Cyan
& $Py -m pip install --quiet locust waitress
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar locust/waitress (se necesita internet).' }

Write-Host "`n== Creando la base temporal taxiasiste_stress" -ForegroundColor Cyan
& $Py (Join-Path $Est 'preparar_estres.py')
if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar la base de la prueba.' }

Write-Host "`n== Ejecutando las 6 etapas (no uses el equipo mientras corre)" -ForegroundColor Cyan
try {
    & $Py (Join-Path $Est 'run_all.py') | ForEach-Object { if ($_ -match '^\{') { $r = $_ | ConvertFrom-Json; Write-Host ("   config {0} x{1}: {2} usuarios | {3} peticiones/s | p95 {4} ms | errores {5} | CPU servidor {6}%" -f $r.config, $r.mult, $r.usuarios, $r.rps, $r.p95, $r.errores, $r.cpu_proceso) } else { Write-Host $_ } }
}
finally {
    Write-Host "`n== Eliminando la base temporal" -ForegroundColor Cyan
    & $Py (Join-Path $Est 'preparar_estres.py') --soltar
}

$json = Join-Path $Est 'resultados.json'
$dirRes = Join-Path $Aqui 'resultados'
New-Item -ItemType Directory -Force $dirRes | Out-Null
$dest = Join-Path $dirRes ("estres_{0}_{1}.json" -f $env:COMPUTERNAME, (Get-Date -Format 'yyyyMMdd_HHmm'))
Copy-Item $json $dest -Force
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
Write-Host "`nEquipo: $env:COMPUTERNAME | $($cpu.Name.Trim()) ($($cpu.NumberOfCores) nucleos) | $ram GB RAM" -ForegroundColor Green
Write-Host "Resultados guardados en: $dest" -ForegroundColor Green
