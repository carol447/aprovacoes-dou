param([Parameter(Mandatory=$true)][string]$OutputPath)

$target = [System.IO.Path]::GetFullPath($OutputPath)
$parent = [System.IO.Path]::GetDirectoryName($target)
[System.IO.Directory]::CreateDirectory($parent) | Out-Null
$text = Get-Clipboard -Raw
[System.IO.File]::WriteAllText($target, $text, [System.Text.UTF8Encoding]::new($false))
Write-Output "Salvo: $($text.Length) caracteres em $target"
