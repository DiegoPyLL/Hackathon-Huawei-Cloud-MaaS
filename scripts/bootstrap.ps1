# Inicializa el repositorio y monta la biblioteca de skills como submódulo.
# Es idempotente: se puede ejecutar varias veces sin efectos secundarios.
#
#   pwsh -File scripts/bootstrap.ps1

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path '.git')) {
    git init -b main
    Write-Host 'Repositorio git inicializado.' -ForegroundColor Green
}

if (Test-Path '.gitmodules') {
    git submodule update --init --recursive
    Write-Host 'Submódulo de skills sincronizado.' -ForegroundColor Green
} else {
    git submodule add https://github.com/DiegoPyLL/FullSkills.git .claude/skills
    Write-Host 'Skills añadidas como submódulo.' -ForegroundColor Green
}

Write-Host ''
Write-Host 'Listo. Skills disponibles en .claude/skills/' -ForegroundColor Cyan
Write-Host 'Siguiente paso: completar el bloque Objetivo de .claude/CLAUDE.md'
