param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9.:-]*$')]
    [string]$ServerHost,

    [ValidatePattern('^[a-zA-Z_][a-zA-Z0-9_-]*$')]
    [string]$SshUser = 'root',

    [ValidatePattern('^(~/|/)[a-zA-Z0-9_./-]+$')]
    [string]$RemoteDirectory = '~/nuur-ai-assistant'
)

$ErrorActionPreference = 'Stop'
$pdfDirectory = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\app\data'))
$pdfs = @(Get-ChildItem -LiteralPath $pdfDirectory -File | Where-Object { $_.Extension -ieq '.pdf' })
if ($pdfs.Count -eq 0) {
    throw "No PDF files were found in $pdfDirectory."
}
$scpCommand = Get-Command scp -ErrorAction Stop
$remoteHost = if ($ServerHost.Contains(':')) { "[$ServerHost]" } else { $ServerHost }
$destination = "${SshUser}@${remoteHost}:${RemoteDirectory}/app/data/"
foreach ($pdf in $pdfs) {
    & $scpCommand.Source $pdf.FullName $destination
    if ($LASTEXITCODE -ne 0) {
        throw "Upload failed for $($pdf.Name)."
    }
}
Write-Output "Uploaded $($pdfs.Count) private PDFs. Run bash deploy/start.sh --https on the Droplet."
