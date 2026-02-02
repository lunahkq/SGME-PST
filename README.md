## Requisitos

- Python 3.10
- PostgreSQL
- Git

---

## Clonar el repositorio
```bash
git clone https://github.com/lunahkq/SGME-PST.git
cd "SGME-PST"
```

---

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

---

## Dependencias y Migraciones
Con el entorno virtual activado, ejecuta: `pip install -r requirements.txt`

---

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

---

## Crear base de datos

En PostgreSQL:
``` sql
CREATE DATABASE sgme_bd
WITH ENCODING 'UTF8'
TEMPLATE template1;
```

---

## Importar base de datos  

``` bash
python manage.py migrate
```

> NOTA: Asegurarse que el usuario de PostgreSQL que esta usando sea el anotado anteriormente en el .env y que tenga permisos para crear tablas en el esquema public de la base de datos sgme_bd para evitar errores.


---
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

---

# Crear super usuario
Con el entorno virtual activado, ejecuta:
`python manage.py createsuperuser`  

Ya puedes acceder al sistema y crear nuevos usuarios!

- Opcional _(En el entorno virtual)_
``` bash
python manage.py shell  

from django.contrib.auth.models import User, Group

user = User.objects.get(username="TU_NOMBRE_DE_USUARIO")
grupo_admin, _ = Group.objects.get_or_create(name="Administrador")
user.groups.add(grupo_admin)
```

> Esto para aparecer en el sistema con rol "administrativo" apenas accedas. En el panel de usuarios también te puedes asignar ese rol o el que tu prefieras.

---

## Inicializar servidor local

Con el entorno virtual activado, ejecuta: `python manage.py runserver`  

Entra en tu navegador a http://127.0.0.1:8000/
