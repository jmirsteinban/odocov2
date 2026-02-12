# ODOCO Coding Standard

## 1️⃣ File Header Rule (Mandatory)

Every `.py` file must start with the following structure:

``` python
# relative/path/to/file.py
# Module: Short and clear module description
```

### Rules:

-   Line 1 → Full relative path from project root
-   Line 2 → Clear module description
-   No empty lines before header
-   No decorative characters
-   Must be consistent across entire project

### Example:

``` python
# backend/routers/servers.py
# Module: API Router for Server management
```

------------------------------------------------------------------------

## 2️⃣ Project Structure Convention

    backend/
      core/        → configuration, logging, constants
      db/          → database models, session, init, deps
      routers/     → API endpoints only
      schemas/     → Pydantic request/response models
      services/    → business logic layer

### Responsibilities:

  Folder     Responsibility
  ---------- -----------------------
  routers    HTTP layer only
  services   Business logic
  db         Database access
  schemas    API validation models
  core       App configuration

------------------------------------------------------------------------

## 3️⃣ Separation of Concerns

-   Routers must NOT contain business logic.
-   Routers must NOT directly manipulate database models beyond CRUD.
-   Complex logic must live in `services/`.
-   Database session must come from `db/deps.py`.

------------------------------------------------------------------------

## 4️⃣ Database Rules

-   Only one SQLite file allowed:

        /db/odoco.db

-   DB path must be defined in a central config file.

-   No duplicate databases in project root.

------------------------------------------------------------------------

## 5️⃣ API Prefix Rule (Recommended)

All API routes should be grouped under:

    /api/...

Example:

    /api/servers
    /api/targets

This prevents conflicts with frontend HTML routes.

------------------------------------------------------------------------

## 6️⃣ Naming Conventions

  Type        Convention
  ----------- ---------------------------------
  Files       snake_case
  Classes     PascalCase
  Functions   snake_case
  DB Models   Singular (Server, SystemTarget)
  Tables      snake_case

------------------------------------------------------------------------

## 7️⃣ Logging Rule (Future Ready)

Critical operations (activation, deletion, network changes) should log
actions.

Example:

``` python
logger.info(f"Server {server_id} activated")
```

------------------------------------------------------------------------

## 8️⃣ Refactor Safety Rule

Before deleting or moving files: - Update imports - Test server
startup - Test all endpoints

------------------------------------------------------------------------

# Philosophy

ODOCO is built as a modular, router-grade backend system.

Clarity \> Cleverness\
Structure \> Speed\
Consistency \> Personal Preference
