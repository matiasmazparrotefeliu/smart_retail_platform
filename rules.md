# 📏 Project Technical Rules & Governance

## 1. Reglas de Arquitectura Modular
- **Cero Referencias Circulares:** Un módulo de negocio (ej. `catalog`) no puede importar directamente desde otro módulo de negocio (ej. `analytics`) si esto crea una dependencia circular. 
- **Capa Core:** El directorio `src/core/` es el único lugar permitido para:
    - Configuraciones globales (`config.py`).
    - Seguridad y JWT (`security.py`).
    - Conexión y sesión de base de datos (`database.py`).
- **Flujo de Datos:** `Router` $\rightarrow$ `Service` $\rightarrow$ `Repository/Model` $\rightarrow$ `Database`.

## 2. Estándares de Base de Datos y ORM
- **SQLAlchemy 2.0:** Es obligatorio el uso de anotaciones de tipo.
    - *Ejemplo Correcto:* `name: Mapped[str] = mapped_column(String(255))`
- **Gobernanza de Tenants:** Todas las tablas que almacenen datos de negocio deben incluir la columna `client_id`.
- **Migraciones:** 
    - Prohibido el uso de `Base.metadata.create_all()`.
    - Todo cambio de esquema debe pasar por un script de migración de Alembic (`alembic revision --autogenerate`).

## 3. Convenciones de Código y Estilo
- **Orientación a Objetos:** Los servicios deben implementarse como clases para facilitar la inyección de dependencias y el testing.
    - *Patrón:* `class ProductService: def __init__(self, db: Session): self.db = db`
- **Pydantic DTOs:** Separación obligatoria de esquemas:
    - `CreateSchema`: Campos requeridos para creación.
    - `UpdateSchema`: Todos los campos opcionales.
    - `ResponseSchema`: Campos que se devuelven al cliente (evitar exponer passwords o IDs internos sensibles).
- **FastAPI Routing:** 
    - Uso de `APIRouter` con `prefix` y `tags` definidos en la instanciación del router.
    - Nombres de rutas en `kebab-case`.

## 4. Seguridad y RBAC (Role-Based Access Control)
- **Validación de Tokens:** Ninguna ruta de negocio puede estar expuesta sin la dependencia de validación de JWT.
- **Control de Acceso:**
    - `tenant_admin`: Acceso total a la configuración del tenant y gestión de usuarios.
    - `analyst`: Acceso a lectura de datos y ejecución de reportes/analítica.
    - `viewer`: Acceso restringido a lectura de dashboards y catálogos.
- **Verificación de Pertenencia:** El sistema debe validar que el recurso solicitado pertenece al `client_id` del token, independientemente del rol.

## 5. Gobernanza de Cambios y Ejecución
- **Alcance:** Todo commit o modificación debe estar estrictamente alineada con el requerimiento técnico. Los cambios "fuera de alcance" se consideran ruido y deben evitarse.
- **Prohibiciones sin Autorización:** 
    - 🚫 **Tests:** Prohibido crear, editar o ejecutar suites de pruebas.
    - 🚫 **Docker:** Prohibido modificar `Dockerfile`, `docker-compose.yml` o ejecutar comandos de contenedores.
    - 🚫 **Pruebas de Sistema:** Prohibido ejecutar scripts de prueba en el entorno sin consentimiento previo.
