# Runs after Write/Edit tool calls: formats/lints touched Python files if tools are available.
if (Get-Command ruff -ErrorAction SilentlyContinue) {
    ruff check --fix src 2>$null
    ruff format src 2>$null
} else {
    Write-Output "ruff not installed — skipping auto-lint (pip install ruff to enable)."
}
