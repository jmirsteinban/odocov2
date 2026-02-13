# ODOCO Coding Standard

## 1. Header por archivo Python (obligatorio)

Cada archivo `.py` debe comenzar con:

```python
# relative/path/to/file.py
# Module: Descripcion corta y clara
```

Reglas:
- Línea 1: ruta relativa desde la raíz del proyecto
- Línea 2: descripción breve del módulo
- Sin líneas vacías antes del header

## 2. Estructura del proyecto

```text
backend/
  core/       configuración, logging, constantes
  db/         modelos, sesión, init, deps
  routers/    capa HTTP
  schemas/    request/response models
  services/   lógica de negocio
```

Responsabilidades:
- `routers`: validación HTTP y orquestación
- `services`: lógica de negocio
- `db`: acceso a datos y persistencia
- `schemas`: contrato de API
- `core`: configuración transversal

## 3. Separación de responsabilidades

- Los routers no deben contener lógica de negocio compleja.
- La lógica de negocio debe vivir en `services/`.
- La sesión de DB debe provenir de `backend/db/deps.py` cuando aplique.

## 4. Convención de API

Preferido:
- Exponer endpoints bajo `/api/...` para evitar conflictos con rutas de UI.

Estado actual:
- Hay rutas con prefijo (`/api/summary`) y sin prefijo (`/servers`, `/targets`, `/wan/...`).
- Se permite temporalmente por compatibilidad, pero la dirección recomendada es converger a `/api`.

## 5. Reglas de base de datos

- Definir una única ubicación de SQLite y usarla en todo el proyecto.
- Evitar archivos duplicados (`odoco.db` en raíz y `db/odoco.db` al mismo tiempo).
- Centralizar el path en configuración.

## 6. Convenciones de nombres

- Archivos: `snake_case`
- Clases: `PascalCase`
- Funciones: `snake_case`
- Modelos DB: singular (`Server`, `SystemTarget`, `Mode`)
- Tablas: `snake_case`

## 7. Logging

Registrar operaciones críticas:
- activación/desactivación
- cambios de red
- cambios de configuración sensible

Ejemplo:

```python
logger.info("Server %s activated", server_id)
```

## 8. Seguridad de refactors

Antes de mover/eliminar código:
- actualizar imports
- validar arranque del backend
- validar endpoints afectados

## Principios

- Claridad > complejidad
- Estructura > velocidad puntual
- Consistencia > preferencia individual
