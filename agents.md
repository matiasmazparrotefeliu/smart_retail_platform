# 🤖 AI Agent Context & Operational Guidelines

## 1. Rol y Propósito del Sistema
Este repositorio contiene la **Plataforma de Inteligencia y Analítica de Retail**. Es un sistema multi-tenant diseñado para proporcionar insights de mercado, análisis de competencia y gestión de catálogo mediante el uso de scraping y analítica avanzada.

El objetivo principal es permitir que múltiples clientes (`Tenants`) gestionen sus datos de forma aislada, segura y escalable.

## 2. Stack Tecnológico Core
Cualquier código generado debe seguir estrictamente estas versiones y librerías:
- **Lenguaje:** Python 3.11+ (Uso intensivo de *type hinting*).
- **Framework:** FastAPI (Asíncrono donde sea posible).
- **ORM:** SQLAlchemy 2.0 (Estilo declarativo moderno con `Mapped` y `mapped_column`).
- **Validación:** Pydantic v2 (Uso de DTOs estrictos).
- **Base de Datos:** PostgreSQL.
- **Migraciones:** Alembic.
- **Seguridad:** JWT (`python-jose`) y Hashing (`passlib[bcrypt]`).

## 3. Principios de Desarrollo
### 🛡️ Aislamiento Multi-Tenant
- **Regla de Oro:** Ninguna consulta a la base de datos debe ejecutarse sin filtrar por `client_id`. 
- El `client_id` debe extraerse del token JWT y pasarse a través de las dependencias de FastAPI hacia la capa de servicio.

### 📦 Arquitectura de Monolito Modular
- El sistema se divide en dominios independientes: `auth`, `tenant`, `catalog`, `scraping`, `analytics`.
- Cada módulo debe contener sus propios:
    - `models.py`: Definiciones de SQLAlchemy.
    - `schemas.py`: Modelos de Pydantic (Request/Response).
    - `repositories.py`: Acceso a datos (Patrón Repository).
    - `service.py`: Lógica de negocio pura.
    - `router.py`: Endpoints de FastAPI.

### 🗄️ Patrón Repository
- Todo acceso a datos vive en repositorios que heredan de `BaseRepository` (o `TenantScopedRepository` si el modelo tiene `client_id`), definidos en `src/core/repository.py`. Los services **jamás** contienen queries (`db.query`, `db.add`, `db.delete`).
- Los repositorios **no hacen** `commit()`/`rollback()`: solo `flush()`; devuelven `Model | None` y **no** lanzan excepciones HTTP (interpretar `None` es responsabilidad del service). El service es dueño de la transacción (`commit`).
- El scope de tenant se fija con `Repo.for_tenant(client_id)` dentro del service; el `client_id` SIEMPRE proviene del JWT.
- Los routers ensamblan repos vía `Depends()` y se los inyectan al service.
- **Construcción de entidades:** la creación con decisión de negocio (hashing de contraseñas, asignación de tenant/rol) vive en los services; los repos solo la ejecutan para lógica de soporte autocontenida (roles bootstrap `get_or_create`, tokens de verificación `create_for_user`).

## 4. Instrucciones de Contexto para la IA (Coding Standards)
Al generar código, el agente debe:
1. **Estructura de Servicios:** Implementar la lógica de negocio en clases de servicio, no en los routers. El acceso a datos va en repositorios inyectados al service.
   - *Mal:* Lógica de DB directamente en `@router.post`, o queries dentro del service.
   - *Bien:* El router inyecta repos y llama a `service.create_item(data, current_user)`; el service orquesta repos y hace el `commit`.
2. **Inyección de Dependencias:** Usar `Depends()` de FastAPI para manejar la sesión de DB y la autenticación.
3. **Manejo de Excepciones:** Utilizar `fastapi.HTTPException` con códigos de estado HTTP semánticos (400 Bad Request, 403 Forbidden, 404 Not Found).
4. **Tipado Estricto:** Usar `Optional`, `List`, `Dict` de `typing` y asegurar que todas las funciones tengan firmas de tipos completas.

## 5. Límites de Acción y Alcance
- **Estricto Alcance del Requerimiento:** El agente debe limitarse exclusivamente a resolver el requerimiento solicitado. Queda prohibido realizar "mejoras" no solicitadas o refactorizaciones que excedan el alcance de la tarea actual.
- **Restricciones de Infraestructura y Pruebas:** No se debe crear, modificar ni ejecutar tests, ni manipular archivos de Docker o despliegues, a menos que haya una autorización explícita y previa en el prompt del usuario.
