# Lightweight secret scanner run before Bash/Write/Edit tool calls.
# Blocks obvious credential patterns from being introduced into the repo.
$patterns = @(
    'sk-[A-Za-z0-9]{20,}',
    'AKIA[0-9A-Z]{16}',
    'ghp_[A-Za-z0-9]{30,}',
    '-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----'
)

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$staged = Get-ChildItem -Path $root -Recurse -Include *.py,*.ts,*.js,*.json,*.env -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch '\\node_modules\\|\\.git\\|\\.venv\\' }

foreach ($file in $staged) {
    $content = Get-Content -Raw -Path $file.FullName -ErrorAction SilentlyContinue
    if (-not $content) { continue }
    foreach ($pattern in $patterns) {
        if ($content -match $pattern) {
            Write-Error "Potential secret matching '$pattern' found in $($file.FullName). Aborting."
            exit 1
        }
    }
}
exit 0
