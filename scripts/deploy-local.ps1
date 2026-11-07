param( 
    [string]$ServerName = 'localhost',
    [string]$DatabaseName ='RemittanceDb'
)
$ErrorActionPreference = 'Stop'
$projectFolder = Join-Path $PSScriptRoot '..\database\RemittanceDb'
$projectFile = Join-Path $projectFolder 'RemittanceDb.sqlproj'
$dacpacFile = Join-Path $projectFolder 'bin\Release\RemittanceDb.dacpac'
Write-Host 'Building dacpac...'
dotnet build $projectFile --configuration Release --nologo
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
Write-Host "Deploying to $DatabaseName on $ServerName..."
sqlpackage /Action:Publish "/SourceFile:$dacpacFile" "/TargetServerName:$ServerName" "/TargetDatabaseName:$DatabaseName" /TargetTrustServerCertificate:True
if ($LASTEXITCODE -ne 0) { throw 'Deployment failed.' }

Write-Host 'Deployment succeeded.'