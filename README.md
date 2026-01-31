# TFG – Inventory Backend

Backend del Trabajo de Fin de Grado (TFG) para una aplicación web de **gestión de inventarios para pequeñas empresas**.

El proyecto está desarrollado en **Python** utilizando **FastAPI** como framework principal y una base de datos **MySQL**. El backend expone una **API REST** consumida por un frontend desarrollado de forma independiente.

---

## Tecnologías principales

- **Python 3**
- **FastAPI** – Framework web
- **SQLAlchemy** – ORM
- **Alembic** – Migraciones de base de datos
- **MySQL** – Base de datos relacional
- **Uvicorn** – Servidor ASGI

---

## Estructura del proyecto

El proyecto sigue una arquitectura en capas, inspirada en patrones habituales de desarrollo backend (similar a Spring Boot):

- `api/` – Rutas y controladores REST (versionadas)
- `services/` – Lógica de negocio
- `repositories/` – Acceso a datos
- `db/` – Configuración de base de datos y modelos
- `schemas/` – DTOs (request / response)
- `core/` – Configuración y seguridad

---

## 🚀 Ejecución en local

1. Crear y activar un entorno virtual
2. Instalar dependencias
3. Configurar el archivo `.env`
4. Lanzar el servidor de desarrollo

```bash
uvicorn app.main:app --reload
```

La API estará disponible en:

- http://localhost:8000
- Documentación Swagger: http://localhost:8000/docs

---

## Estado del proyecto

Proyecto en desarrollo como parte de un **TFG**. Actualmente enfocado en la definición de la arquitectura y el desarrollo del MVP.

---

## Autor

**Mateo Sarria Franco de Sarabia**

Trabajo de Fin de Grado – Grado en Ingeniería de Tecnologías y Servicios de Telecomunicación

