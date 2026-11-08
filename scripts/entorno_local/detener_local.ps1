<#
 Detiene el backend (8000), el panel web (5173) y el servidor de la app movil (8081) de TaxiAsiste en este computador.
 No toca PostgreSQL ni el emulador.
#>
$puertos = 8000, 5173, 8081
foreach ($p in $puertos) {
    $con = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $con) {
        $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $proc.Id -Force
            Write-Host "Detenido: $($proc.ProcessName) (puerto $p)" -ForegroundColor Yellow
        }
    }
}
Write-Host 'Listo. (Las ventanas de PowerShell abiertas pueden cerrarse a mano.)' -ForegroundColor Green
