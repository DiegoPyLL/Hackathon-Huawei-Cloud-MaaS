# Plantilla de proyecto

Repositorio base para proyectos web nuevos. Trae la doctrina de desarrollo, la biblioteca de skills de Claude como submódulo y una estructura de documentación ya definida, para no volver a decidir lo mismo en cada proyecto.

## Inicio rápido

```powershell
pwsh -File scripts/bootstrap.ps1
```

Inicializa git y monta las skills. En otros sistemas, el equivalente manual:

```bash
git init -b main
git submodule add https://github.com/DiegoPyLL/FullSkills.git .claude/skills
```

Después:

1. Completar el bloque `Objetivo` de [`.claude/CLAUDE.md`](.claude/CLAUDE.md) — es lo único que se edita por proyecto; el resto es doctrina fija.
2. Rellenar los `{{PLACEHOLDER}}` de [`docs/design/design-system.md`](docs/design/design-system.md).
3. Registrar el stack elegido como primer ADR en [`docs/architecture/decisions/`](docs/architecture/decisions/).
4. Borrar las plantillas que el proyecto no vaya a usar.

## Estructura

```
.
├── .claude/
│   ├── CLAUDE.md            Doctrina de desarrollo (versionado)
│   ├── settings.json        Configuración compartida (versionado)
│   ├── settings.local.json  Configuración personal (ignorado)
│   └── skills/              ← submódulo FullSkills
├── .github/
│   └── copilot-instructions.md
├── docs/                    Documentación del proyecto — ver docs/README.md
├── scripts/
│   └── bootstrap.ps1
└── src/                     Lo crea cada proyecto según su stack
```

Reglas de raíz: **ningún documento suelto fuera de `docs/`** salvo este README. Los scripts van a `scripts/`, no a la raíz. Todo lo generado (`node_modules/`, `dist/`, `.env`) está cubierto por [`.gitignore`](.gitignore).

## Documentación

La organización de `docs/` y sus reglas están en [`docs/README.md`](docs/README.md). En resumen:

| Carpeta | Responde a |
| --- | --- |
| `product/` | Qué construimos y para quién |
| `design/` | Cómo se ve y se siente |
| `architecture/` | Cómo está construido y por qué (incluye ADRs) |
| `development/` | Cómo se trabaja en él |
| `performance-seo/` | Cómo se mide la calidad |
| `operations/` | Cómo vive en producción |

## Skills

[`FullSkills`](https://github.com/DiegoPyLL/FullSkills) montado como submódulo en `.claude/skills/`. Cada carpeta queda al primer nivel, que es donde Claude Code descubre las skills.

| Skill | Enfoque |
| --- | --- |
| `/indice` | Enrutador maestro entre skills e inventario del repositorio |
| `/security` | Seguridad ofensiva, defensiva, forense, cloud, contenedores |
| `/backend` | APIs, datos, concurrencia, fiabilidad, rendimiento, entrega |
| `/seo` | Auditoría de SEO técnico |
| `/mobile` | Plataforma y seguridad iOS/Android |

`ai/`, `cloud/` y `frontend-ux-ui/` están reservadas y aún vacías: sin `SKILL.md` no se descubren.

```bash
# Al clonar un proyecto por primera vez, o si .claude/skills aparece vacío
git submodule update --init --recursive

# Traer la última versión de las skills
git submodule update --remote --merge .claude/skills
git add .claude/skills && git commit -m "Actualiza biblioteca de skills"
```

El submódulo apunta a un commit fijo: las skills no cambian bajo los pies del proyecto hasta que se actualiza a propósito. Su contenido **no se edita desde aquí** — los cambios se hacen en el repositorio `FullSkills`.

## Convenciones

- **Commits en español**, resumen en imperativo ("Corrige…", "Agrega…", "Actualiza…"). Ver [`.github/copilot-instructions.md`](.github/copilot-instructions.md).
- **Documentos en kebab-case**, sin acentos ni ñ en los nombres de archivo.
- **Las decisiones técnicas se registran como ADR**, no se explican en un commit.
