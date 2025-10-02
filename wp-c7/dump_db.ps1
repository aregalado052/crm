# wp-c7/dump_db.ps1  (MySQL + ZIP + rotación 14 días)
param(
  [string]$DbName = "local",
  [string]$DbUser = "root",
  [string]$DbPass = "root",
  [string]$DbHost = "127.0.0.1",
  [int]$Port = 10025,               # cambia a 3306 si es tu caso
  [string]$MySqlDump = "mysqldump", # o ruta completa al exe
  [int]$RetentionDays = 14,
  [switch]$KeepSql = $false,
  [string]$BackupDir = 'C:\Desarrollo\crm_backups'   # <- NUEVO DESTINO
)
$ErrorActionPreference = 'Stop'

# 1) Carpeta de backups
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

# 2) Nombre por timestamp
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$sqlFile = Join-Path $BackupDir "wp_${DbName}_${ts}.sql"
$zipFile = "$sqlFile.zip"

# 3) Volcado con mysqldump
& $MySqlDump "--host=$DbHost" "--port=$Port" "--user=$DbUser" "--password=$DbPass" `
  $DbName "--result-file=$sqlFile"
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $sqlFile)) {
  throw "mysqldump falló (exit=$LASTEXITCODE) o no creó $sqlFile"
}

# 4) Comprimir a ZIP y (opcional) borrar el .sql
if (Test-Path $zipFile) { Remove-Item $zipFile -Force }
Compress-Archive -Path $sqlFile -DestinationPath $zipFile -Force
if (-not $KeepSql) { Remove-Item $sqlFile -Force }

Write-Host "[DUMP] Backup OK -> $zipFile"

# 5) Rotación: borra .sql/.zip más antiguos que RetentionDays
$cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem $BackupDir -File -ErrorAction SilentlyContinue |
  Where-Object {
    ($_.Extension -in @('.sql', '.zip')) -and ($_.LastWriteTime -lt $cutoff)
  } | Remove-Item -Force
