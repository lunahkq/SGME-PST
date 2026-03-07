# Sistema de Gestión de Matrícula Escolar (SGME)
Aplicación web elaborada por equipo Tecno Capibara 

## Descripción General
El **SGME** es una aplicación web integral para la administración de matrículas de instituciones educativas. Permite gestionar estudiantes, representantes, usuarios, años escolares y generar reportes detallados.  
  
El sistema está diseñado con una arquitectura robusta utilizando Django como framework principal; listo para ser implementado en una red local (LAN).

## Tecnologías Utilizadas

### Frontend

- Framework: Django Templates
- CSS Framework: Bootstrap 5.3.2
- Iconografía: Bootstrap Icons 1.10.5
- JavaScript: Vanilla JS para interactividad básica

### Backend

- Framework: Django 5.2.10
- Lenguaje: Python 3.10+
- ORM: Django ORM con soporte para PostgreSQL
- Autenticación: Sistema integrado de Django con extensión de grupos/permisos
- Validación: Validadores de Django

### Base de Datos
- **Motor:** PostgreSQL 8+
- **Driver:** psycopg2-binary 2.9.11
- **Encoding:** UTF-8
- **Template:** template1

## Infraestructura y Despliegue

- Servidor de Desarrollo: Django Development Server (Puerto 8000)
- Gestión de Variables: python-dotenv 1.2.1
- Control de Versiones: Git & GitHub
- Scripts de Automatización: Disponibles para Windows y Linux

### Servicios Externos

- Servidor de Correo: Gmail SMTP (TLS en puerto 587)
- Uso: Recuperación de contraseñas mediante código de verificación

---

## Estructura del Proyecto

```
SGME-PST/
├── sgme_app/                    # Aplicación principal Django
│   ├── templates/               # Plantillas HTML
│   ├── static/                  # Archivos estáticos (CSS, JS, imágenes)
│   ├── models.py               # Modelos de base de datos
│   ├── views.py                # Vistas y lógica de negocio
│   ├── forms.py                # Formularios Django
│   └── urls.py                 # Rutas de la aplicación
├── fixtures/                    # Datos iniciales
│   ├── datos_iniciales.json    # Grados, secciones, turnos
│   └── grupos.json             # Roles de usuario
├── Windows/                     # Scripts de automatización Windows
│   ├── runserver.bat           # Iniciar servidor
│   ├── stopserver.bat          # Detener servidor
│   ├── update_repo.bat         # Actualizar repositorio
│   ├── update_assets.bat       # Actualizar assets
│   └── clean_log.bat           # Limpiar logs
├── Linux/                       # Scripts de automatización Linux
│   ├── runserver.sh            # Iniciar servidor
│   ├── stopserver.sh           # Detener servidor
│   ├── update_repo.sh          # Actualizar repositorio
│   ├── update_assets.sh        # Actualizar assets
│   └── clean_log.sh            # Limpiar logs
├── manage.py                    # Utilidad de gestión Django
├── requirements.txt             # Dependencias del proyecto
└── .env                        # Variables de entorno (no incluido)
```

---

## Características Principales

### 1. Sistema de Autenticación y Control de Acceso (RBAC)
- **Roles disponibles:** Administrador, Directivo, Docente
- **Recuperación de contraseña** mediante código enviado por correo electrónico
- **Gestión de sesiones** con almacenamiento en base de datos
- **Permisos diferenciados** según el rol del usuario

### 2. Gestión de Usuarios
- Creación de usuarios con asignación de roles
- Listado y búsqueda de usuarios
- Modificación de roles (Administrador, Directivo, Docente)
- Desactivación de usuarios
- Restricciones según nivel de privilegios

### 3. Gestión de Estudiantes
- Registro completo de estudiantes con datos personales y académicos
- Actualización de información
- Consulta y búsqueda avanzada
- Gestión de tallas de uniformes
- Estados: Nuevo, Regular, Repetido, Retirado, Egresado
- Sistema de Soft Delete (retiro de estudiantes)

### 4. Gestión de Representantes
- Registro de representantes legales
- Vinculación con estudiantes (relación uno a muchos)
- Actualización de datos de contacto
- Estado automático (Activo/Inactivo según estudiantes matriculados)

### 5. Gestión de Matrícula y Años Escolares
- Creación y gestión de años escolares
- Inscripción de estudiantes por año escolar
- Asignación de grado, sección y turno
- Reinscripción automática de estudiantes
- Seguimiento de estado (Nuevo, Regular, Repetido, Egresado)
- Validaciones de seguridad para eliminación de años escolares

### 6. Sistema de Reportes
- **Generación de reportes** de matrícula en PDF y Excel
- **Estadísticas** por grado, sección, turno, sexo
- **Filtros avanzados** para personalizar reportes
- **Exportación** a formatos PDF y Excel (.xlsx)

### 7. Panel de Control (Dashboard)
- Visualización de gráficos institucionales
- Distribución de estudiantes por grado
- Distribución por sexo
- Estadísticas de matriculados por año
- Accesos directos a funciones principales

---

# Instalación y Ejecución

### Requisitos

- Python 3.10
- PostgreSQL
- Git

## Clonar el repositorio
```bash
git clone https://github.com/lunahkq/SGME-PST.git
cd "SGME-PST"
```

## Crear entorno virtual
_virtualenv recomendado_  
  
- Windows:
``` bash
pip install virtualenv 
python -m venv venv
venv\Scripts\activate.bat o
.\venv\Scripts\Activate.ps1
```
  
- Linux/macOS:
``` bash
pip install virtualenv
virtualenv venv
source venv/bin/activate
```

## Dependencias y Migraciones
Con el entorno virtual activado, ejecuta: `pip install -r requirements.txt`

## Crear archivo .env
Dentro de la carpeta raiz del proyecto crear archivo .env con lo siguiente  
  
### Terminal:
- Windows:  
`notepad .env`

- Linux/macOS:  
`nano .env`


Puedes también en la carpeta hacer click derecho "crear nuevo archivo de texto" y simplemente ponerle .env (sin .txt) y agregarlo con lo siguiente:
``` env
EMAIL_HOST_USER=correo@ejemplo.com  
EMAIL_HOST_PASSWORD=clave_app  

DB_NAME=sgme_bd  
DB_USER=tu_usuariod_de_postgresql  
DB_PASSWORD=tu_clave_de_postgresql  
DB_HOST=localhost  
DB_PORT=5432  
```

> NOTA: Para `EMAIL_HOST_PASSWORD` debes usar una **contraseña de aplicación** de Gmail, no tu contraseña normal

## Crear base de datos

En PostgreSQL:
``` sql
CREATE DATABASE sgme_bd
WITH ENCODING 'UTF8'
TEMPLATE template1;
```

## Importar base de datos  

``` bash
python manage.py migrate
```

> NOTA: Asegurarse que el usuario de PostgreSQL que esta usando sea el anotado anteriormente en el .env y que tenga permisos para crear tablas en el esquema public de la base de datos sgme_bd para evitar errores.

## Importar datos iniciales
Grados, secciones y turnos
``` bash
python manage.py loaddata fixtures/datos_iniciales.json
```

# Importar roles
Para poder porbar los accesos diferenciados de la aplicación, importar los grupos con:
``` bash
python manage.py loaddata fixtures/grupos.json
``` 

# Crear super usuario
Con el entorno virtual activado, ejecuta:
`python manage.py createsuperuser`  

Ya puedes acceder al sistema y crear nuevos usuarios!

- Opcional _(En el entorno virtual)_
``` bash
python manage.py shell  

from django.contrib.auth.models import User, Group

user = User.objects.get(username="TU_NOMBRE_DE_USUARIO")
grupo_admin, _ = Group.objects.get_or_create(name="Directivo")
user.groups.add(grupo_admin)
```

> Esto para aparecer en el sistema con rol "Directivo" apenas accedas. En el panel de usuarios también te puedes asignar ese rol o el que tu prefieras.

## Iniciar el Servidor Local

#### Opción 1 - Comando manual:

Con el entorno virtual activado, ejecuta:

```bash
python manage.py runserver 0.0.0.0:8000
```

#### Opción 2 - Scripts de automatización:

**Windows:**
- Doble clic en `Windows/runserver.bat`

**Linux:**
- Clic derecho en `Linux/runserver.sh` > "Ejecutar como programa"
- O desde la terminal:
  ```bash
  chmod +x Linux/runserver.sh
  ./Linux/runserver.sh
  ```

---

## Acceder al Sistema

Abre tu navegador y accede a:

- **Localmente:** `http://127.0.0.1:8000/`
- **Desde otros dispositivos en la red local:** `http://TU_IP:8000`

Para conocer tu IP:
- **Windows:** Abre CMD y ejecuta `ipconfig` (busca IPv4)
- **Linux:** Ejecuta `ip addr` o `hostname -I`

---

## Scripts de Mantenimiento

El sistema incluye scripts de automatización para facilitar tareas comunes de mantenimiento:

### Windows (carpeta `Windows/`)

| Script | Descripción |
|--------|-------------|
| `runserver.bat` | Inicia el servidor de desarrollo |
| `stopserver.bat` | Detiene el servidor de desarrollo |
| `update_repo.bat` | Actualiza el repositorio desde GitHub |
| `update_assets.bat` | Actualiza archivos estáticos |
| `clean_log.bat` | Limpia archivos de log |

### Linux (carpeta `Linux/`)

| Script | Descripción |
|--------|-------------|
| `runserver.sh` | Inicia el servidor de desarrollo |
| `stopserver.sh` | Detiene el servidor de desarrollo |
| `update_repo.sh` | Actualiza el repositorio desde GitHub |
| `update_assets.sh` | Actualiza archivos estáticos |
| `clean_log.sh` | Limpia archivos de log |

#### Uso de scripts en Linux:

```bash
# Dar permisos de ejecución (primera vez)
chmod +x Linux/*.sh

# Ejecutar un script
./Linux/runserver.sh
```
