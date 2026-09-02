# AI Cloud Deployment Guardian

## Descripción

**AI Cloud Deployment Guardian** es un agente de IA basado en LLM que analiza cambios de infraestructura antes de que sean desplegados en Huawei Cloud.

El objetivo es detectar configuraciones inseguras, sobreaprovisionamiento, exposición pública innecesaria, secretos embebidos y cambios de alto impacto antes de que lleguen a producción.

La solución utiliza **Huawei Cloud MaaS** como motor de razonamiento y combina análisis del `git diff` con reglas deterministas y herramientas ligeras.

La propuesta evita arquitecturas costosas y mantiene el consumo computacional bajo.

---

## Problema

Los cambios de infraestructura suelen revisarse manualmente mediante Pull Requests.

Un cambio aparentemente simple puede introducir problemas como:

- Bases de datos expuestas públicamente.
- Puertos administrativos abiertos a Internet.
- Credenciales hardcodeadas.
- Aumentos innecesarios de réplicas.
- Instancias sobredimensionadas.
- Incrementos significativos de costos.
- Configuraciones incompatibles con políticas internas.
- Ausencia de autoscaling.
- Cambios peligrosos en ambientes de producción.

Ejemplo:

```diff
- replicas: 2
+ replicas: 15

- instance: c7.large
+ instance: c7.8xlarge

- database_public_access: false
+ database_public_access: true
```

El cambio parece mejorar capacidad, pero puede generar:

- Exposición de la base de datos.
- Incremento significativo de costos.
- Sobreaprovisionamiento.
- Mayor superficie de ataque.

---

## Objetivo

Crear un agente capaz de:

1. Leer el `git diff` de un Pull Request. (Script para traer el código)
2. Identificar archivos relevantes. (índice de relevancia, que tanto importa un archivo)


3. Analizar riesgos técnicos.
5. Validar reglas deterministas.
4. Consultar herramientas cuando necesite información adicional.
7. Asignar severidad a los problemas encontrados.


6. Estimar impacto en costos.

8. Aprobar, advertir o bloquear el despliegue.

9. Generar automáticamente un parche seguro.

---

## Arquitectura

```text
                    GitHub
                       |
                       |
                  Pull Request
                       |
                       v
                   Git Diff
                       |
                       v
                  Backend API
                    FastAPI
                       |
                       v
              Huawei Cloud MaaS
                   LLM Agent
                       |
          +------------+------------+
          |            |            |
          v            v            v
       Files        Policies     Cost Tool
          |            |            |
          +------------+------------+
                       |
                       v
                  Risk Analysis
                       |
             +---------+---------+
             |         |         |
             v         v         v
          APPROVE     WARN      BLOCK
                                  |
                                  v
                           Generate Patch
```

---

## Componentes

### 1. GitHub

El sistema obtiene únicamente los cambios realizados en el Pull Request.

```bash
git diff HEAD~1 HEAD
```

Esto reduce considerablemente la cantidad de tokens enviados al modelo.

---

### 2. Backend

Un backend ligero basado en FastAPI recibe el cambio y coordina el flujo.

Ejemplo:

```text
POST /analyze
```

Entrada:

```json
{
  "repository": "cloud-infrastructure",
  "environment": "production",
  "diff": "..."
}
```

---

### 3. Huawei Cloud MaaS

Huawei Cloud MaaS funciona como motor de razonamiento.

El LLM analiza:

- Seguridad.
- Costos.
- Arquitectura.
- Configuración.
- Secretos.
- Impacto operacional.
- Compatibilidad con políticas.
- Riesgo del despliegue.

El LLM no debe tener autoridad absoluta.

Las decisiones críticas deben estar respaldadas por reglas deterministas.

---

## Tool Calling

El agente puede disponer de herramientas simples.

```python
tools = [
    read_changed_file,
    get_git_diff,
    calculate_cost,
    validate_policy,
    generate_patch
]
```

### `read_changed_file`

Permite obtener el contenido completo de un archivo cuando el `git diff` no proporciona suficiente contexto.

### `get_git_diff`

Obtiene los cambios asociados al Pull Request.

### `calculate_cost`

Calcula una estimación del cambio relativo en costos.

Ejemplo:

```json
{
  "previous_cost": 100,
  "estimated_cost": 700,
  "increase_percent": 600
}
```

### `validate_policy`

Compara la configuración con reglas internas.

Ejemplo:

```json
{
  "database_public_access": true
}
```

Respuesta:

```json
{
  "allowed": false,
  "policy": "POLICY-DB-004",
  "reason": "Production databases cannot be publicly accessible."
}
```

### `generate_patch`

Genera una modificación segura para resolver los problemas detectados.

---

## Policy Engine

Las reglas críticas deben mantenerse fuera del LLM.

Ejemplo:

```json
{
  "production": {
    "public_database": false,
    "allow_ssh_from_anywhere": false,
    "hardcoded_secrets": false,
    "max_replicas": 10,
    "max_cost_increase_percent": 50
  }
}
```

Arquitectura de decisión:

```text
                 Deployment Change
                        |
             +----------+----------+
             |                     |
             v                     v
        Rule Engine               LLM
      Deterministic            Reasoning
             |                     |
             +----------+----------+
                        |
                        v
                     Decision
```

El Rule Engine controla reglas no negociables.

El LLM analiza situaciones ambiguas y aporta contexto.

---

## Ejemplo de análisis

Configuración recibida:

```yaml
instance:
  flavor: c7.16xlarge

replicas: 20

environment:
  DB_PASSWORD: "supersecret123"

security_group:
  ingress:
    - 0.0.0.0/0
```

Resultado:

```text
Finding #1
Hardcoded credential
Severity: CRITICAL

Finding #2
Possible infrastructure overprovisioning
Severity: HIGH

Finding #3
Public network exposure
Severity: HIGH

Finding #4
No autoscaling configuration
Severity: MEDIUM
```

Decisión:

```text
DEPLOYMENT BLOCKED
```

---

## Generación automática de corrección

El agente puede generar una versión corregida.

```yaml
replicas: 2

environment:
  DB_PASSWORD_SECRET: "db-password"

autoscaling:
  min: 2
  max: 10

security_group:
  ingress:
    - 10.0.0.0/24
```

El usuario puede revisar el cambio antes de aplicarlo.

---

## Flujo Agentic

El agente no debe analizar todo el repositorio en una sola llamada.

Debe decidir qué información necesita.

```text
Receive Git Diff
       |
       v
Analyze Changes
       |
       v
Need More Context?
   |          |
  YES         NO
   |          |
   v          |
Read File     |
   |          |
   +----------+
       |
       v
Validate Policies
       |
       v
Estimate Cost
       |
       v
Calculate Risk
       |
       v
Make Decision
       |
       v
Generate Patch
```

Esto permite demostrar comportamiento agentic sin utilizar múltiples agentes.

---

## Modelo de decisión

El resultado puede clasificarse en tres niveles.

### APPROVE

El cambio no contiene problemas relevantes.

```json
{
  "decision": "APPROVE",
  "risk_score": 12
}
```

### WARN

El cambio contiene riesgos no críticos.

```json
{
  "decision": "WARN",
  "risk_score": 48
}
```

### BLOCK

El cambio viola políticas críticas o presenta riesgo alto.

```json
{
  "decision": "BLOCK",
  "risk_score": 94
}
```

---

## Risk Score

Se puede utilizar una puntuación entre `0` y `100`.

Ejemplo:

| Severidad | Puntos |
|---|---:|
| LOW | 5 |
| MEDIUM | 15 |
| HIGH | 30 |
| CRITICAL | 50 |

Ejemplo:

```text
CRITICAL secret exposed        +50
HIGH public SSH                +30
HIGH excessive cost            +30

Total raw score                110
Final score                    100
```

---

## Escenario de Demo

Pull Request:

```text
feat: improve production scalability
```

Cambios:

```text
replicas:
3 -> 30

database:
private -> public

SSH:
10.0.0.0/24 -> 0.0.0.0/0

credentials:
Secret Manager -> hardcoded password

instance:
small -> 16xlarge
```

El desarrollador intenta aprobar el Pull Request.

El agente analiza automáticamente el cambio.

Resultado:

```text
AI CLOUD DEPLOYMENT GUARDIAN

Risk Score: 94/100

CRITICAL
Production database exposed publicly.

CRITICAL
Credential detected in configuration.

HIGH
SSH exposed to Internet.

HIGH
Estimated compute increase: 5900%.

DECISION

DEPLOYMENT BLOCKED

Suggested remediation available.
```

El usuario selecciona:

```text
Generate Safe Patch
```

El agente genera una propuesta corregida.

---

## Ejemplo de salida estructurada

```json
{
  "decision": "BLOCK",
  "risk_score": 94,
  "findings": [
    {
      "type": "PUBLIC_DATABASE",
      "severity": "CRITICAL",
      "message": "Production database exposed publicly."
    },
    {
      "type": "HARDCODED_SECRET",
      "severity": "CRITICAL",
      "message": "Credential detected in configuration."
    },
    {
      "type": "PUBLIC_SSH",
      "severity": "HIGH",
      "message": "SSH exposed to Internet."
    },
    {
      "type": "COST_INCREASE",
      "severity": "HIGH",
      "message": "Estimated infrastructure cost increase exceeds policy."
    }
  ],
  "suggested_action": "GENERATE_PATCH"
}
```

---

## Recursos Computacionales

La arquitectura está diseñada para ser ligera.

```text
Huawei MaaS:
1-3 requests por análisis

Backend:
1 instancia pequeña

Database:
No requerida

Vector Database:
No requerida

GPU:
No requerida

Kubernetes:
No requerido

Cloud monitoring:
No requerido

Multi-agent architecture:
No requerida
```

El consumo principal es únicamente el uso de la API del LLM.

---

## Optimización de Tokens

Para reducir costos:

### No enviar todo el repositorio

Enviar únicamente:

```text
git diff
```

### Leer archivos bajo demanda

Solo cuando el modelo determine que necesita contexto adicional.

### Limitar Tool Calls

Ejemplo:

```text
MAX_TOOL_CALLS = 5
```

### Respuestas estructuradas

Utilizar JSON para reducir texto innecesario.

---

## Tecnologías

### Huawei Cloud

- Huawei Cloud MaaS.
- FunctionGraph, opcional.
- IAM, opcional.
- API Gateway, opcional.

### Aplicación

- Python.
- FastAPI.
- GitHub API.
- Git.
- JSON Policies.
- Terraform o YAML como infraestructura de ejemplo.

---

## MVP

El MVP requiere únicamente:

```text
GitHub
   |
   v
FastAPI
   |
   v
Huawei MaaS
   |
   +--> Policy Engine
   |
   +--> Cost Calculator
   |
   v
Risk Report
```

Funciones mínimas:

- Leer `git diff`.
- Enviar el cambio al LLM.
- Detectar riesgos.
- Validar políticas.
- Calcular un Risk Score.
- Emitir `APPROVE`, `WARN` o `BLOCK`.
- Generar una propuesta de corrección.

---

## Posibles Extensiones

Si queda tiempo durante la hackathon:

- Comentarios automáticos en Pull Requests.
- Integración con GitHub Actions.
- Historial de análisis.
- Dashboard web.
- Comparación de costos antes y después.
- Soporte para Terraform.
- Soporte para Kubernetes YAML.
- Soporte para Docker Compose.
- Auto-fix mediante Pull Request.
- Explicación del riesgo en lenguaje natural.
- Policies específicas por entorno.

---

## Diferenciador

La propuesta no utiliza el LLM únicamente como chatbot.

El LLM funciona como un agente capaz de:

```text
Observe
   |
   v
Reason
   |
   v
Use Tools
   |
   v
Validate
   |
   v
Decide
   |
   v
Act
```

La complejidad está en el razonamiento y la toma de decisiones, no en consumir grandes cantidades de infraestructura.

---

## Pitch

> **AI Cloud Deployment Guardian is an AI agent that prevents unsafe and unnecessarily expensive cloud deployments before they happen.**

---

## Valor para una Hackathon

Este caso permite demostrar:

- Integración real con Huawei Cloud MaaS.
- LLM reasoning.
- Tool calling.
- Guardrails.
- Policy enforcement.
- Análisis de infraestructura.
- Generación de código.
- Automatización DevOps.
- Optimización de costos.
- Seguridad Cloud.

Todo esto puede implementarse con una arquitectura pequeña y un consumo computacional reducido.
