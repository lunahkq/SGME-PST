import random
from django.core.mail import send_mail
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth import login, logout
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.db.models import Q, Count, Value, IntegerField
from django.db.models.functions import TruncYear
from django.contrib.auth import authenticate
from datetime import date
from django.http import HttpResponse
import openpyxl
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
from django.db.models import Prefetch, prefetch_related_objects
from django.core.paginator import Paginator


from django.utils import timezone

# Commit para ver si se arregla la cosa

# Importando modelos de la base de datos
from .models import AnioEscolar
from .models import Estudiante
from .models import Grado
from .models import Matricula
from .models import Representante
from .models import Seccion
from .models import Turno



# Create your views here.


# AUTENTICACIÓN INICIAL
def login_request(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            
            # VERIFICACIÓN DE ROL DESACTIVADO
            if user.groups.filter(name="Desactivado").exists():
                messages.error(request, "Tu usuario está desactivado. Contacta a un directivo.")
                return redirect("login")

            login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")
    else:
        form = AuthenticationForm()

    return render(request, "authentication/login.html", {"form": form})

# *** DASHBOARD CON GRÁFICOS - REEMPLAZA TU FUNCIÓN ANTIGUA ***
@login_required
def home_view(request):
    # CONTADORES PRINCIPALES (para las cards del template)
    total_students = Estudiante.objects.count()
    total_parents = Representante.objects.count()
    total_records = Matricula.objects.count()
    
    # Obtener el Año Escolar Activo
    anio_activo = AnioEscolar.objects.filter(activo=True).first()

    # 1. GRÁFICO: Estudiantes por Grado (solo año activo)
    students_by_grade = (
        Estudiante.objects
        .filter(
            matricula__estado__in=['Activo', 'Regular', 'Nuevo', 'Repetido'],
            matricula__id_anio_escolar=anio_activo
        )
        .values('matricula__id_grado__nombre')
        .annotate(total=Count('id_estudiante'))
        .order_by('matricula__id_grado__nombre')
    )
    grade_labels = [item['matricula__id_grado__nombre'] or 'Sin grado' for item in students_by_grade]
    grade_data = [item['total'] for item in students_by_grade]
    
    # 2. GRÁFICO: Estudiantes por Género (solo activos en el año actual)
    students_by_gender = (
        Estudiante.objects
        .filter(
            matricula__estado__in=['Activo', 'Regular', 'Nuevo', 'Repetido'],
            matricula__id_anio_escolar=anio_activo
        )
        .values('sexo')
        .annotate(total=Count('id_estudiante'))
    )
    gender_labels = [item['sexo'] or 'No especificado' for item in students_by_gender]
    gender_data = [item['total'] for item in students_by_gender]
    
    # 3. GRÁFICO: Matrículas por Año Escolar (últimos 5)
    records_by_year = (
        Matricula.objects
        .values('id_anio_escolar__anio_escolar')
        .annotate(total=Count('id_matricula'))
        .order_by('-id_anio_escolar__fecha_inicio')[:5]  # Últimos 5 cronológicamente
    )
    
    # Convertir a lista e invertir para que en el gráfico salgan de izquierda a derecha (antiguo -> nuevo)
    records_list = list(reversed(records_by_year))
    
    year_labels = [item['id_anio_escolar__anio_escolar'] for item in records_list]
    year_data = [item['total'] for item in records_list]
    
    # CONTEXT EXACTO para tu template narbar.html
    context = {
        # Cards principales
        'total_students': total_students,
        'total_parents': total_parents,
        'total_records': total_records,
        
        # Datos de GRÁFICOS (exactamente como espera tu JavaScript)
        'grade_labels': grade_labels,
        'grade_data': grade_data,
        'gender_labels': gender_labels,
        'gender_data': gender_data,
        'year_labels': year_labels,
        'year_data': year_data,
    }
    
    return render(request, "modules/home.html", context)  # ← CAMBIÉ modules/home.html por narbar.html

# RESTABLECIMIENTO DE CONTRASEÑA
def forgot_password(request):
    # GET: mostrar formulario para escribir el correo
    if request.method == "GET":
        return render(request, "authentication/forgot_password.html")

    # POST: procesar el correo, generar código y enviarlo
    email = request.POST.get("email")

    # Buscar usuario por correo
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        messages.error(request, "No existe un usuario con ese correo.")
        return render(
            request,
            "authentication/forgot_password.html",
            {"email": email},
        )

    # Generar código de 6 dígitos
    codigo = str(random.randint(100000, 999999))

    # Guardar email y código en la sesión
    request.session["reset_email"] = email
    request.session["reset_code"] = codigo

    # Enviar correo con el código
    asunto = "Código para restablecer tu contraseña"
    mensaje = f"Tu código de verificación es: {codigo}"
    send_mail(
        asunto,
        mensaje,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )

    messages.success(
        request,
        "Se ha enviado un código de verificación a tu correo.",
    )

    # Redirigimos a la pantalla de verificación de código
    return redirect("v_code")

def verification_code(request):
    # Asegurarse de que hay correo/código en sesión
    email_guardado = request.session.get("reset_email")
    codigo_guardado = request.session.get("reset_code")

    if not email_guardado or not codigo_guardado:
        messages.error(request, "La sesión de recuperación ha expirado. Inténtalo de nuevo.")
        return redirect("f_password")

    if request.method == "GET":
        # Mostrar formulario para ingresar el código
        return render(
            request,
            "authentication/verification_code.html",
            {"email": email_guardado},
        )

    # POST: el usuario envía el código
    codigo_ingresado = request.POST.get("codigo")

    if codigo_ingresado != codigo_guardado:
        messages.error(request, "El código de verificación es incorrecto.")
        return render(
            request,
            "authentication/verification_code.html",
            {"email": email_guardado},
        )
    # Código correcto: pasamos a resetear contraseña
    messages.success(
        request,
        "Código verificado correctamente. Ahora crea una nueva contraseña.",
    )

    # Marcamos en sesión que el código ya fue verificado
    request.session["reset_verified"] = True

    return redirect("r_password")

def reset_password(request):
    email_guardado = request.session.get("reset_email")
    codigo_guardado = request.session.get("reset_code")
    verificado = request.session.get("reset_verified")

    # Si no hay sesión o no pasó por la verificación de código, lo mandamos al inicio del flujo
    if not email_guardado or not codigo_guardado or not verificado:
        messages.error(request, "Primero debes verificar tu código de recuperación.")
        return redirect("f_password")

    if request.method == "GET":
        return render(request, "authentication/reset_password.html")

    # POST: guardar nueva contraseña
    password1 = request.POST.get("password1")
    password2 = request.POST.get("password2")

    if not password1 or not password2:
        messages.error(request, "Debes completar ambos campos de contraseña.")
        return render(request, "authentication/reset_password.html")

    if password1 != password2:
        messages.error(request, "Las contraseñas no coinciden.")
        return render(request, "authentication/reset_password.html")

    # Validar la contraseña con los validadores de Django
    try:
        validate_password(password1) 
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
        return render(request, "authentication/reset_password.html")

    # Buscar el usuario y cambiar la contraseña
    try:
        user = User.objects.get(email=email_guardado)
    except User.DoesNotExist:
        messages.error(request, "No se encontró el usuario asociado a este correo.")
        return redirect("f_password")

    user.set_password(password1)  # se encarga del hash de forma segura [web:169][web:210]
    user.save()

    # Limpiar datos de sesión de recuperación
    for key in ["reset_email", "reset_code", "reset_verified"]:
        if key in request.session:
            del request.session[key]

    messages.success(request, "Tu contraseña ha sido restablecida correctamente. Ya puedes iniciar sesión.")

    return redirect("login")

# PERFIL
@login_required
def profile_user(request):
    return render(request, "views/profile.html")

# AYUDA
@login_required
def help(request):
    return render(request, "views/help.html")

# CERRAR SESIÓN
def logout_view(request):
    logout(request)
    return redirect("login")


# MÓDULO DE GESTIÓN DE USUARIOS
def es_admin_o_directivo(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=["Administrador", "Directivo"]).exists()

@login_required
@user_passes_test(es_admin_o_directivo, login_url="home")
def users_control(request):
    es_super_admin = request.user.is_superuser

    # Crear usuario nuevo
    if request.method == "POST" and request.POST.get("action") == "create":
        username = request.POST.get("username")
        email = request.POST.get("email")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")
        role = request.POST.get("role")  # "Administrador", "Directivo" o "Docente"

        # Validaciones básicas
        if not username or not password1 or not password2 or not email:
            messages.error(request, "Usuario, correo y ambas contraseñas son obligatorios.")
        elif password1 != password2:
            messages.error(request, "Las contraseñas no coinciden.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, "Ya existe un usuario con ese nombre de usuario.")
        elif User.objects.filter(email=email).exists():
            messages.error(request, "Ya existe un usuario con ese correo.")
        elif role not in ["Administrador", "Directivo", "Docente", "Desactivado"]:
            messages.error(request, "Debes seleccionar un rol válido.")
        elif not (es_super_admin or request.user.groups.filter(name="Administrador").exists()) and role == "Administrador":
            messages.error(request, "Solo un Administrador puede crear otros Administradores.")
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name or "",
                last_name=last_name or "",
            )
            grupo, _ = Group.objects.get_or_create(name=role)
            user.groups.add(grupo)
            
            if role == "Desactivado":
                 messages.warning(request, f"Usuario '{username}' creado como DESACTIVADO.")
            else:
                 messages.success(request, f"Usuario '{username}' creado correctamente.")
        return redirect("users_control")

    # Eliminar usuario
    if request.method == "POST" and request.POST.get("action") == "delete":
        user_id = request.POST.get("user_id")
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, "El usuario no existe.")
            return redirect("users_control")

        if request.user.id == user.id:
            messages.error(request, "No puedes eliminar tu propio usuario.")
        
        # Validar permisos de eliminación: Solo Superuser o Administrador
        elif not (es_super_admin or request.user.groups.filter(name="Administrador").exists()):
            messages.error(request, "No tienes permiso para eliminar usuarios. Solo Administradores.")
            
        # Un directivo/admin no puede borrar superiores (aunque aquí admin borra admin si quiere, pero mantenemos lógica de jerarquía si se desea)
        # La regla solicitada es: "Los administradores son los unicos que podrán eliminar usuarios"
        elif not es_super_admin and user.is_superuser:
             messages.error(request, "No puedes eliminar a un Superusuario.")
             
        else:
            user.delete()
            messages.success(request, "Usuario eliminado correctamente.")

        return redirect("users_control")

    # Asignar rol
    if request.method == "POST" and request.POST.get("action") == "set_role":
        user_id = request.POST.get("user_id")
        role = request.POST.get("role")
        try:
            user = User.objects.get(id=user_id)

            if role not in ["Administrador", "Directivo", "Docente", "Desactivado"]:
                messages.error(request, "Rol no válido. Asigne otro")
            elif not (es_super_admin or request.user.groups.filter(name="Administrador").exists()) and role == "Administrador":
                messages.error(request, "Solo un Administrador puede asignar el rol Administrador.")
            elif user.is_superuser and not es_super_admin:
                messages.error(request, "No tienes permiso para modificar a un Administrador.")
            elif user.groups.filter(name="Administrador").exists() and not (es_super_admin or request.user.groups.filter(name="Administrador").exists()):
                messages.error(request, "No tienes permiso para modificar a un Administrador.")
            elif request.user.id == user.id and role == "Desactivado":
                messages.error(request, "No puedes desactivar tu propio usuario")
            else:
                # Limpiamos grupos relevantes y añadimos el nuevo
                custom_groups = ["Administrador", "Directivo", "Docente", "Desactivado"]
                for nombre in custom_groups:
                    user.groups.remove(*Group.objects.filter(name=nombre))
                
                grupo, _ = Group.objects.get_or_create(name=role)
                user.groups.add(grupo)
                
                if role == "Desactivado":
                    messages.warning(request, f"Usuario {user.username} ha sido DESACTIVADO.")
                else:
                    messages.success(request, "Rol actualizado.")
        except User.DoesNotExist:
            messages.error(request, "El usuario no existe.")
        return redirect("users_control")

    # GET: listar usuarios
    usuarios = User.objects.all().order_by("username")
    grupos = Group.objects.filter(name__in=["Administrador", "Directivo", "Docente", "Desactivado"])

    contexto = {
        "usuarios": usuarios,
        "grupos": grupos,
        "es_super_admin": es_super_admin,
    }
    return render(request, "authentication/users_control.html", contexto)


@login_required
def students_view(request):
    if request.method == "POST":
        # VERIFICACIÓN DE PERMISOS: Solo Admin o Directivo pueden editar/borrar
        if not es_admin_o_directivo(request.user):
            messages.error(request, "No tienes permisos para realizar esta acción.")
            return redirect("students")

        accion = request.POST.get("accion")
        est_id = request.POST.get("est_id")


        # RETIRAR ESTUDIANTE
        if accion == "retirar":
            try:
                estudiante = get_object_or_404(Estudiante, id_estudiante=est_id)
                anio_activo = AnioEscolar.objects.get(activo=True)
                
                # Marcar matrícula como retirado
                matricula = Matricula.objects.filter(
                    id_estudiante=estudiante,
                    id_anio_escolar=anio_activo
                ).first()
                
                if matricula:
                    matricula.estado = "Retirado"
                    matricula.save()
                    messages.success(request, f"Estudiante {estudiante.nombres} {estudiante.apellidos} marcado como RETIRADO correctamente.")
                else:
                    messages.warning(request, "No se encontró matrícula activa para este estudiante.")
                
                return redirect("students")
            except Exception as e:
                messages.error(request, f"Error al retirar estudiante: {str(e)}")
                return redirect("students")

        # CREAR / EDITAR ESTUDIANTE 
        else:
            try:
                with transaction.atomic():
                    # 1. Año escolar activo
                    try:
                        anio_activo = AnioEscolar.objects.get(activo=True)
                    except AnioEscolar.DoesNotExist:
                        messages.error(request, "No hay un año escolar activo. Contacta al administrador.")
                        return redirect("students")

                    # 2. Datos del estudiante
                    nombres = request.POST.get("nombres")
                    apellidos = request.POST.get("apellidos")
                    cedula = request.POST.get("cedula") or None
                    sexo_in = request.POST.get("sexo")
                    fecha_nacimiento = request.POST.get("fecha_nacimiento") or None
                    lugar_nacimiento = request.POST.get("lugar_nacimiento") or ""
                    talla_camisa = request.POST.get("talla_camisa") or ""
                    talla_pantalon = request.POST.get("talla_pantalon") or ""
                    talla_zapato = request.POST.get("talla_zapato") or ""

                    if not nombres or not apellidos or not fecha_nacimiento or not cedula:
                        messages.error(request, "Nombres, apellidos, cédula escolar y fecha de nacimiento son obligatorios.")
                        return redirect("students")

                    sexo = "F" if sexo_in == "Femenino" else "M"

                    # 3. Datos del representante
                    rep_nombres = request.POST.get("rep_nombres")
                    rep_apellidos = request.POST.get("rep_apellidos")
                    rep_cedula = request.POST.get("rep_cedula")
                    rep_telefono = request.POST.get("rep_telefono")
                    rep_correo = request.POST.get("rep_correo") or ""
                    rep_direccion = request.POST.get("rep_direccion") or ""

                    if not rep_nombres or not rep_apellidos or not rep_cedula or not rep_telefono:
                        messages.error(
                            request,
                            "Los datos del representante son obligatorios (nombres, apellidos, cédula y teléfono)."
                        )
                        return redirect("students")

                    representante, created = Representante.objects.get_or_create(
                        cedula=rep_cedula,
                        defaults={
                            'nombres': rep_nombres,
                            'apellidos': rep_apellidos,
                            'telefono': rep_telefono,
                            'correo': rep_correo,
                            'direccion': rep_direccion,
                        }
                    )

                    if not created:
                        representante.nombres = rep_nombres
                        representante.apellidos = rep_apellidos
                        representante.telefono = rep_telefono
                        representante.correo = rep_correo
                        representante.direccion = rep_direccion
                        representante.save()

                    # 4. Crear o actualizar estudiante
                    if est_id:  # EDITAR
                        estudiante = get_object_or_404(Estudiante, id_estudiante=est_id)
                        estudiante.nombres = nombres
                        estudiante.apellidos = apellidos
                        estudiante.cedula = cedula
                        estudiante.sexo = sexo
                        estudiante.fecha_nacimiento = fecha_nacimiento
                        estudiante.lugar_nacimiento = lugar_nacimiento
                        estudiante.talla_camisa = talla_camisa
                        estudiante.talla_pantalon = talla_pantalon
                        estudiante.talla_zapato = talla_zapato
                        estudiante.save()
                    else:       # CREAR
                        estudiante = Estudiante.objects.create(
                            nombres=nombres,
                            apellidos=apellidos,
                            cedula=cedula,
                            sexo=sexo,
                            fecha_nacimiento=fecha_nacimiento,
                            lugar_nacimiento=lugar_nacimiento,
                            talla_camisa=talla_camisa,
                            talla_pantalon=talla_pantalon,
                            talla_zapato=talla_zapato,
                            fecha_registro=timezone.now(),
                        )

                    # 5. Datos de matrícula
                    grado_nombre = request.POST.get("grado")
                    seccion_letra = request.POST.get("seccion")
                    turno_nombre = request.POST.get("turno")
                    observaciones = request.POST.get("observaciones") or ""

                    if not grado_nombre or not seccion_letra or not turno_nombre:
                        messages.error(request, "Debes seleccionar grado, sección y turno.")
                        return redirect("students")

                    try:
                        grado = Grado.objects.get(nombre=grado_nombre)
                    except Grado.DoesNotExist:
                        messages.error(request, f"El grado '{grado_nombre}' no existe en el sistema.")
                        return redirect("students")

                    try:
                        seccion = Seccion.objects.get(letra=seccion_letra)
                    except Seccion.DoesNotExist:
                        messages.error(request, f"La sección '{seccion_letra}' no existe en el sistema.")
                        return redirect("students")

                    try:
                        turno = Turno.objects.get(nombre=turno_nombre)
                    except Turno.DoesNotExist:
                        messages.error(request, f"El turno '{turno_nombre}' no existe en el sistema.")
                        return redirect("students")

                    # 6. Crear o actualizar matrícula activa en este año
                    matricula, mat_created = Matricula.objects.get_or_create(
                        id_estudiante=estudiante,
                        id_anio_escolar=anio_activo,
                        defaults={
                            'id_representante': representante,
                            'id_grado': grado,
                            'id_seccion': seccion,
                            'id_turno': turno,
                            'anio_ingreso': anio_activo.fecha_inicio.year,
                            'fecha_matricula': date.today(),
                            'estado': "Nuevo",
                            'observaciones': observaciones,
                        }
                    )
                    

                    if not mat_created:
                        matricula.id_representante = representante
                        matricula.id_grado = grado
                        matricula.id_seccion = seccion
                        matricula.id_turno = turno
                        matricula.observaciones = observaciones
                        matricula.save()

                    if est_id:
                        messages.success(request, f"Estudiante {nombres} {apellidos} actualizado correctamente.")
                    else:
                        messages.success(request, f"Estudiante {nombres} {apellidos} registrado y matriculado correctamente.")

                    return redirect("students")

            except IntegrityError as e:
                if 'estudiante_cedula_key' in str(e):
                    cedula_val = request.POST.get('cedula', '')
                    messages.error(request, f"Error al registrar/actualizar datos del estudiante: Ya existe un estudiante registrado con la cédula {cedula_val}.")
                else:
                    messages.error(request, f"Error al registrar/actualizar el estudiante: {str(e)}")
                return redirect("students")

            except Exception as e:
                messages.error(request, f"Error al registrar/actualizar el estudiante: {str(e)}")
                return redirect("students")

    # GET - Listado y filtros (tu código original sin cambios)
    estudiantes = Estudiante.objects.all().order_by("apellidos", "nombres")
    grados = Grado.objects.all().order_by("orden")
    secciones = Seccion.objects.all()
    turnos = Turno.objects.all()
    anios = AnioEscolar.objects.exclude(anio_escolar__startswith="OCULTO:").order_by('-anio_escolar')  # Orden descendente (más reciente primero)

    # Búsqueda por nombre/apellido/cedula
    q = request.GET.get("q", "")
    if q:
        estudiantes = estudiantes.filter(
            Q(nombres__icontains=q) |
            Q(apellidos__icontains=q) |
            Q(cedula__icontains=q)
        )

    # 1. Determinar el Año Escolar a filtrar
    anio_activo = AnioEscolar.objects.filter(activo=True).first()
    hay_anio_activo = anio_activo is not None

    selected_anio_id = request.GET.get("anio")
    anio_filtro = None

    if selected_anio_id is None:
        anio_filtro = anio_activo
    elif selected_anio_id == "":
        anio_filtro = None
    else:
        try:
            anio_filtro = AnioEscolar.objects.get(id_anio_escolar=selected_anio_id)
        except AnioEscolar.DoesNotExist:
            anio_filtro = anio_activo

    sexo = request.GET.get("sexo")
    if sexo:
        estudiantes = estudiantes.filter(sexo=sexo)

    # Lógica de Visibilidad de Estudiantes:
    # Solo mostrar estudiantes que tengan matrícula en el año filtrado
    
    if anio_filtro:
        # Estudiantes con matrícula en el año actual (filtro)
        # Y ordenados por Grado (orden) > Sección > Turno > Apellidos
        estudiantes = estudiantes.filter(
            matricula__id_anio_escolar=anio_filtro
        ).order_by(
            'matricula__id_grado__orden',
            'matricula__id_seccion__letra',
            'matricula__id_turno__nombre',
            'apellidos', 
            'nombres'
        ).distinct()
    
    # Filtrar matrículas por el año seleccionado (o el activo por defecto)
    if anio_filtro:
        matriculas = Matricula.objects.filter(id_anio_escolar=anio_filtro).select_related('id_grado', 'id_seccion', 'id_turno', 'id_anio_escolar', 'id_representante')
    else:
        # Si no hay año filtro, ordenamos por apellido por defecto
        # (Aunque students_view ya tenía order_by('apellidos', 'nombres') al inicio, 
        #  el if anio_filtro arriba lo sobrescribe solo para ese caso)
        matriculas = Matricula.objects.all().select_related('id_grado', 'id_seccion', 'id_turno', 'id_anio_escolar', 'id_representante')

    # Filtros adicionales
    grado = request.GET.get("grado")
    if grado:
        matriculas = matriculas.filter(id_grado__nombre=grado)

    seccion = request.GET.get("seccion")
    if seccion:
        matriculas = matriculas.filter(id_seccion__letra=seccion)

    turno = request.GET.get("turno")
    if turno:
        matriculas = matriculas.filter(id_turno__nombre=turno)

    selected_estado = request.GET.get("estado")
    # Si no viene parámetro, por defecto filtramos "Activos"
    if selected_estado is None:
        selected_estado = "Activo"

    # Aplicar filtro de estado
    if selected_estado == "Activo":
        # "Activo" agrupa: Nuevo, Regular, Repetido (y por seguridad "Activo")
        matriculas = matriculas.filter(estado__in=["Activo", "Nuevo", "Regular", "Repetido"])
        # Filtramos estudiantes que tengan esas matrículas
        student_ids = matriculas.values_list('id_estudiante_id', flat=True)
        estudiantes = estudiantes.filter(id_estudiante__in=student_ids)

    elif selected_estado == "Inactivo":
        # "Inactivo" agrupa: Retirados y Egresado en el año filtrado
        if anio_filtro:
            # 1. Identificar estudiantes con matrícula ACTIVA en este año
            active_ids = Matricula.objects.filter(
                id_anio_escolar=anio_filtro,
                estado__in=["Activo", "Nuevo", "Regular", "Repetido"]
            ).values_list('id_estudiante', flat=True)
            
            # 2. Excluir a los activos de la lista de estudiantes visibles
            # (que ya está restringida a Current + Previous year)
            estudiantes = estudiantes.exclude(id_estudiante__in=active_ids)
            
            # Nota: Al excluir a los activos, nos quedan:
            # - Estudiantes con matricula en este año pero estado "Retirado", "Egresado", "Inactivo"
        else:
            # Si no hay año filtro, mostramos los inactivos históricos explícitos
            matriculas = matriculas.filter(estado__in=["Inactivo", "Retirado", "Egresado"])
            student_ids = matriculas.values_list('id_estudiante_id', flat=True)
            estudiantes = estudiantes.filter(id_estudiante__in=student_ids)

    # Si selected_estado == "" (Todos), no filtramos nada, pero:
    elif selected_estado == "":
         pass
         
    
    if grado or seccion or turno:
        # Si hay filtros de atributo de matricula, entonces SÍ debemos restringir a quienes tengan esa matricula
        student_ids_attr = matriculas.values_list('id_estudiante_id', flat=True)
        estudiantes = estudiantes.filter(id_estudiante__in=student_ids_attr)

    
    # Paginación
    paginator = Paginator(estudiantes, 20)  # 20 estudiantes por página
    page_number = request.GET.get('page')
    estudiantes_page = paginator.get_page(page_number)

    # Optimización: Solo buscar matrículas para los estudiantes de la página actual
    page_student_ids = [s.id_estudiante for s in estudiantes_page]
    matriculas_page = matriculas.filter(id_estudiante__in=page_student_ids)

    matricula_map = {m.id_estudiante_id: m for m in matriculas_page}
    for est in estudiantes_page:
        est.matricula_activa = matricula_map.get(est.id_estudiante)

    grados_list = list(grados)
    secciones_list = list(secciones)
    turnos_list = list(turnos)

    # Resto de selects para la vista
    for g in grados_list:
        g.selected = (g.nombre == request.GET.get("grado"))

    for s in secciones_list:
        s.selected = (s.letra == request.GET.get("seccion"))

    for t in turnos_list:
        t.selected = (t.nombre == request.GET.get("turno"))

    selected_sexo = request.GET.get("sexo")
    context_sexo = {
        "F": selected_sexo == "F",
        "M": selected_sexo == "M"
    }

    context_estado = {
        "Activo": selected_estado == "Activo",
        "Inactivo": selected_estado == "Inactivo",
        "Todos": selected_estado == ""
    }

    contexto = {
        "estudiantes": estudiantes_page,
        "grados": grados_list,
        "secciones": secciones_list,
        "turnos": turnos_list,
        "anios": anios,
        "hay_anio_activo": hay_anio_activo,
        "selected_anio_id": int(selected_anio_id) if selected_anio_id and selected_anio_id.isdigit() else ("" if selected_anio_id == "" else (anio_activo.id_anio_escolar if anio_activo else None)),
        "selected_sexo": context_sexo,
        "selected_estado": context_estado,
        "q": q,
        "can_edit": es_admin_o_directivo(request.user),
    }
    return render(request, "modules/students.html", contexto)



# MÓDULO DE REPRESENTANTES

def parents_list(request):
    q = request.GET.get('q', '')
    grado = request.GET.get('grado', '')
    seccion = request.GET.get('seccion', '')
    turno = request.GET.get('turno', '')
    estado = request.GET.get('estado', 'Activo')

    anio_activo = AnioEscolar.objects.filter(activo=True).first()
    active_statuses = ["Activo", "Nuevo", "Regular", "Repetido"]

    parents = (
        Representante.objects.annotate(
            num_estudiantes=Count('matricula__id_estudiante', distinct=True),
            num_activos=Count(
                'matricula',
                filter=Q(matricula__id_anio_escolar=anio_activo, matricula__estado__in=active_statuses),
                distinct=True
            ) if anio_activo else Value(0, output_field=IntegerField())
        )
    )

    if q:
        parents = parents.filter(
            Q(nombres__icontains=q) |
            Q(apellidos__icontains=q) |
            Q(cedula__icontains=q)
        )

    # Filtro por grado (nombre)
    if grado:
        parents = parents.filter(
            matricula__id_grado__nombre=grado
        ).distinct()

    # Filtro por sección (letra)
    if seccion:
        parents = parents.filter(
            matricula__id_seccion__letra=seccion
        ).distinct()

    # Filtro por turno (nombre)
    if turno: 
        parents = parents.filter(
            matricula__id_turno__nombre=turno
        ).distinct()

    # Filtro por estado del Representante (basado en sus estudiantes en el Año Escolar Activo)
    anio_activo = AnioEscolar.objects.filter(activo=True).first()
    active_statuses = ["Activo", "Nuevo", "Regular", "Repetido"]

    if estado == 'Activo':
        if anio_activo:
            parents = parents.filter(
                matricula__id_anio_escolar=anio_activo,
                matricula__estado__in=active_statuses
            ).distinct()
        else:
            # Si no hay año activo, nadie puede estar activo
            parents = parents.none()

    elif estado == 'Inactivo': 
        if anio_activo:
            # Excluir a los que tienen al menos un estudiante activo en el año actual
            active_reps_ids = Representante.objects.filter(
                matricula__id_anio_escolar=anio_activo,
                matricula__estado__in=active_statuses
            ).values_list('id_representante', flat=True)
            
            parents = parents.exclude(id_representante__in=active_reps_ids)
        else:
            # Si no hay año activo, todos son inactivos (no filtramos nada extra, solo devolvemos lo que hay)
            pass

    # Listas para los filtros (Dynamic)
    grados = Grado.objects.all().order_by("orden")
    secciones = Seccion.objects.all()
    turnos = Turno.objects.all()

    # Marcar seleccionados para mantener el estado en el filtro
    grados_list = list(grados)
    for g in grados_list:
        g.selected = (g.nombre == grado)

    secciones_list = list(secciones)
    for s in secciones_list:
        s.selected = (s.letra == seccion)

    turnos_list = list(turnos)
    for t in turnos_list:
        t.selected = (t.nombre == turno) # Ahora comparamos con nombre completo

    # Paginación
    parents = parents.order_by('apellidos', 'nombres')
    paginator = Paginator(parents, 20)
    page_number = request.GET.get('page')
    parents_page = paginator.get_page(page_number)

    # Pre-procesar para evitar duplicados en la vista (mostrar solo la matrícula más reciente de cada estudiante)
    # y convertir a lista para poder iterar en el template con los atributos extra
    
    # Optimización: Prefetch de matrículas para evitar N+1 queries (Solo para la página actual)
    
    # 1. Obtener objetos de la página
    parents_list = list(parents_page.object_list)
    
    # 2. Hacer prefetch manual sobre esta lista
    prefetch_related_objects(
        parents_list,
        Prefetch(
            'matricula_set',
            queryset=Matricula.objects.select_related(
                'id_estudiante', 'id_grado', 'id_seccion', 'id_turno', 'id_anio_escolar'
            ).order_by('-id_anio_escolar__fecha_inicio')
        )
    )

    for p in parents_list:
        # Obtenemos todas las matrículas del representante (ya cacheadas por prefetch_related)
        matriculas = p.matricula_set.all()
        
        unique_students = {}
        processed_students = []
        
        for m in matriculas:
            est_id = m.id_estudiante.id_estudiante
            if est_id not in unique_students:
                unique_students[est_id] = True
                processed_students.append(m)
        
        # Asignamos la lista filtrada al objeto (esto es temporal para la vista)
        p.matriculas_visibles = processed_students

    context = {
        'parents': parents_page, # Pasamos el objeto Page para la navegación
        'parents_list': parents_list, # Pasamos la lista procesada para el loop
        'q': q,
        'grados': grados_list,
        'secciones': secciones_list,
        'turnos': turnos_list,
        'selected_grado': grado,
        'selected_seccion': seccion,
        'selected_turno': turno,
        'selected_estado': estado,
    }
    return render(request, 'modules/parents.html', context)


@require_POST
@login_required
def parent_edit(request, pk):
    # VERIFICACIÓN: Solo Admin/Directivo
    if not es_admin_o_directivo(request.user):
        messages.error(request, "No tienes permisos para realizar esta acción.")
        return redirect("parents")

    parent = get_object_or_404(Representante, id_representante=pk)
    parent.nombres = request.POST.get('nombres', parent.nombres)
    parent.apellidos = request.POST.get('apellidos', parent.apellidos)
    parent.correo = request.POST.get('correo', parent.correo)
    parent.telefono = request.POST.get('telefono', parent.telefono)
    parent.save()
    
    messages.success(request, "Se editó correctamente.")  # LINEA AGREGADA PARA AVISO DE MENSAJES
    
    return redirect('parents')


# MODULO DE MATRÍCULA
@login_required
@user_passes_test(es_admin_o_directivo, login_url="home")
def academic_record(request):
    """
    Vista principal del módulo de Matrícula
    - Crear nuevo año escolar
    - Activar año escolar
    - Reinscripción / repetición / egreso
    - Contador de estudiantes matriculados
    """

    # Crear nuevo año escolar
    if request.method == "POST" and request.POST.get("action") == "create_year":
        anio_escolar = request.POST.get("anio_escolar")  # texto: 2026-2027
        fecha_inicio = request.POST.get("fecha_inicio")
        fecha_fin = request.POST.get("fecha_fin")

        if not anio_escolar or not fecha_inicio or not fecha_fin:
            messages.error(request, "Todos los campos del año escolar son obligatorios.")
        elif AnioEscolar.objects.filter(anio_escolar=anio_escolar).exists():
            messages.error(request, "Ya existe un año escolar con ese nombre.")
        else:
            AnioEscolar.objects.create(
                anio_escolar=anio_escolar,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                activo=False,
            )
            messages.success(request, "El año escolar se creó correctamente.")
        return redirect("academic")

    # Marcar año escolar activo
    if request.method == "POST" and request.POST.get("action") == "set_active":
        anio_id = request.POST.get("anio_id")
        try:
            with transaction.atomic():
                AnioEscolar.objects.update(activo=False)
                anio = AnioEscolar.objects.get(id_anio_escolar=anio_id)
                anio.activo = True
                anio.save()
            messages.success(request, f"Año escolar {anio.anio_escolar} activado.")
        except AnioEscolar.DoesNotExist:
            messages.error(request, "El año escolar seleccionado no existe.")
        return redirect("academic")

    # Desactivar año escolar
    if request.method == "POST" and request.POST.get("action") == "delete_year":
        anio_id = request.POST.get("anio_id")
        password = request.POST.get("password")  # Obtener contraseña del modal

        if not password:
            messages.error(request, "Debes ingresar tu contraseña para confirmar la desactivación.")
            return redirect("academic")

        # Verificar contraseña
        user = authenticate(username=request.user.username, password=password)
        if user is None:
            messages.error(request, "Contraseña incorrecta. No se pudo desactivar el año escolar.")
            return redirect("academic")

        try:
            anio = AnioEscolar.objects.get(id_anio_escolar=anio_id)
            if anio.activo:
                 messages.error(request, "No puedes desactivar el año escolar activo.")
            else:
                 with transaction.atomic():
                     # Soft Delete: Renombrar con prefijo "OCULTO:" y desactivar
                     original_name = anio.anio_escolar
                     # Truncar si es necesario para que quepa el prefijo (max 20 chars)
                     new_name = f"OCULTO:{original_name}"[:20]
                     anio.anio_escolar = new_name
                     anio.activo = False
                     anio.save()
                     # No eliminamos matrículas ni anio, solo ocultamos
                 messages.success(request, "Año escolar ocultado con éxito.")
        except AnioEscolar.DoesNotExist:
            messages.error(request, "El año escolar no existe.")
        except Exception as e:
            messages.error(request, f"Error al desactivar: {str(e)}")
        return redirect("academic")

    # Reinscripción / repetición / egreso
    if request.method == "POST" and request.POST.get("action") == "promote":
        origen_anio_id = request.POST.get("origen_anio")
        origen_grado_id = request.POST.get("origen_grado")
        origen_seccion_id = request.POST.get("origen_seccion")  # "A", "B", "C", "D"
        origen_turno_codigo = request.POST.get("origen_turno")   # "M", "T"

        destino_anio_id = request.POST.get("destino_anio")
        destino_grado_id = request.POST.get("destino_grado")
        destino_seccion_id = request.POST.get("destino_seccion")  # "A", "B", "C", "D"
        destino_turno_codigo = request.POST.get("destino_turno")   # "M", "T"
        cedula_carnet = request.POST.get("cedula_carnet_origen", "").strip().upper()

        try:
            with transaction.atomic():
                origen_anio = AnioEscolar.objects.get(id_anio_escolar=origen_anio_id)
                destino_anio = AnioEscolar.objects.get(id_anio_escolar=destino_anio_id)

                # Usamos IDs directamente porque el template enviado ahora usa IDs (serán dropdowns dinámicos)
                origen_grado = Grado.objects.get(id_grado=origen_grado_id)
                origen_seccion = Seccion.objects.get(id_seccion=origen_seccion_id)
                origen_turno = Turno.objects.get(id_turno=origen_turno_codigo) # La variable se llamaba codigo pero recibiremos ID

                destino_grado = Grado.objects.get(id_grado=destino_grado_id)
                destino_seccion = Seccion.objects.get(id_seccion=destino_seccion_id)
                destino_turno = Turno.objects.get(id_turno=destino_turno_codigo)

                # Filtrar por cédula si se proporciona
                if cedula_carnet:
                    matriculas_origen = (
                        Matricula.objects.filter(
                            id_anio_escolar=origen_anio,
                            id_grado=origen_grado,
                            id_seccion=origen_seccion,
                            id_turno=origen_turno,
                            id_estudiante__cedula=cedula_carnet,
                        )
                        .exclude(estado="Promovido")
                        .select_related("id_estudiante", "id_representante", "id_turno")
                    )
                else:
                    matriculas_origen = (
                        Matricula.objects.filter(
                            id_anio_escolar=origen_anio,
                            id_grado=origen_grado,
                            id_seccion=origen_seccion,
                            id_turno=origen_turno,
                        )
                        .exclude(estado="Promovido")
                        .select_related("id_estudiante", "id_representante", "id_turno")
                    )

                total_regulares = 0
                total_promovidos = 0  # egresados
                total_repetidos = 0

                for m in matriculas_origen:
                    # Caso Especial: EGRESO de 6to Grado
                    # Si el grado es 6to (orden 6) y el año destino es el mismo que el origen,
                    # se considera que el estudiante se ha "Egresado" (Graduado).
                    if origen_grado.orden == 6 and origen_anio.id_anio_escolar == destino_anio.id_anio_escolar:
                         m.estado = "Egresado"
                         # Preservamos observaciones anteriores y añadimos la nota de egreso
                         obs_actual = m.observaciones if m.observaciones else ""
                         m.observaciones = f"{obs_actual} | Marcado como Egresado el {date.today()}"
                         m.save()
                         total_promovidos += 1
                         messages.success(request, "Estudiante marcado como egresado correctamente")
                         continue
                    
                    # REGLA SOLICITADA:
                    # Si el estudiante permanece en el mismo grado que su ultimo año escolar, su estado debe ser REPETIDO
                    # Si el estudiante cambia de grado en el nuevo año escolar, su estado debe pasar a REGULAR
                    
                    if origen_grado.id_grado == destino_grado.id_grado:
                        nuevo_estado = "Repetido"
                        total_repetidos += 1
                    else:
                        nuevo_estado = "Regular"
                        total_regulares += 1
                    
                    # Actualizar fecha de registro (reinscripción)
                    m.id_estudiante.fecha_registro = timezone.now()
                    m.id_estudiante.save()


                    Matricula.objects.create(
                        id_estudiante=m.id_estudiante,
                        id_representante=m.id_representante,
                        id_grado=destino_grado,
                        id_seccion=destino_seccion,
                        id_turno=destino_turno,
                        id_anio_escolar=destino_anio,
                        anio_ingreso=destino_anio.fecha_inicio.year,
                        fecha_matricula=date.today(), # Usar fecha actual
                        estado=nuevo_estado,
                        observaciones=(
                            f"Reinscrito desde {origen_grado.nombre} "
                            f"{origen_seccion.letra} {origen_turno.nombre} ({origen_anio.anio_escolar})"
                        ),
                    )

                if total_regulares > 0 or total_repetidos > 0:
                    messages.success(request, "Se realizó la reinscripción correctamente.")

        except Exception as e:
            messages.error(request, f"Error en la reinscripción: {str(e)}")

        return redirect("academic")

    # GET: datos para mostrar formulario
    anios = AnioEscolar.objects.exclude(anio_escolar__startswith="OCULTO:").order_by("-fecha_inicio")
    anio_activo = AnioEscolar.objects.filter(activo=True).first()
    
    # Listas para los dropdowns dinámicos
    grados = Grado.objects.all().order_by("orden")
    secciones = Seccion.objects.all().order_by("letra")
    turnos = Turno.objects.all().order_by("nombre")

    total_matriculados = (
        Matricula.objects.filter(
            id_anio_escolar=anio_activo,
            estado__in=["Regular", "Repetido"]
        ).count()
        if anio_activo
        else 0
    )

    context = {
        "anios": anios,
        "anio_activo": anio_activo,
        "total_matriculados": total_matriculados,
        "grados": grados,
        "secciones": secciones,
        "turnos": turnos,
    }
    return render(request, "modules/academic_record.html", context)


# VISTA DE REPORTE DE MATRÍCULA (EJEMPLO SIMPLE)
@login_required
@user_passes_test(es_admin_o_directivo, login_url="home")
def reporte_matricula(request):
    """
    Vista de ejemplo para el reporte de matrícula.
    Aquí puedes generar un PDF o Excel con todos los estudiantes matriculados.
    """
    anio_activo = AnioEscolar.objects.filter(activo=True).first()

    if anio_activo:
        estudiantes = (
            Matricula.objects.filter(
                id_anio_escolar=anio_activo,
                estado__in=["Regular", "Repetido"]
            )
            .select_related("id_estudiante", "id_grado", "id_seccion", "id_turno")
        )
    else:
        estudiantes = []

    context = {
        "anio_activo": anio_activo,
        "estudiantes": estudiantes,
    }
    return render(request, "matricula/reporte_matricula.html", context)


# API para verificar representante
from django.http import JsonResponse

@login_required
def check_representative_by_cedula(request, cedula):
    try:
        rep = Representante.objects.get(cedula=cedula)
        data = {
            'found': True,
            'nombres': rep.nombres,
            'apellidos': rep.apellidos,
            'telefono': rep.telefono,
            'correo': rep.correo,
            'direccion': rep.direccion
        }
    except Representante.DoesNotExist:
        data = {'found': False}
    
    return JsonResponse(data)


@login_required
def check_student_last_enrollment(request, cedula):
    """
    API para buscar la última matrícula de un estudiante por cédula.
    Retorna el año escolar, grado, sección y turno de su último registro.
    """
    try:
        # Buscamos al estudiante
        estudiante = Estudiante.objects.get(cedula=cedula)
        
        # Buscamos su última matrícula (ordenada por fecha de matrícula o año descendente)
        # Asumiendo que id_matricula es auto-incremental, el último id será el más reciente.
        # O mejor, usamos el año escolar más reciente.
        ultima_matricula = Matricula.objects.filter(id_estudiante=estudiante).exclude(id_anio_escolar__anio_escolar__startswith="OCULTO:").order_by('-id_anio_escolar__fecha_inicio').first()

        if ultima_matricula:
            data = {
                'found': True,
                'estudiante_nombre': f"{estudiante.nombres} {estudiante.apellidos}",
                'anio_id': ultima_matricula.id_anio_escolar.id_anio_escolar,
                'grado_id': ultima_matricula.id_grado.id_grado,
                'seccion_id': ultima_matricula.id_seccion.id_seccion, # Corregido para usar ID
                'turno_id': ultima_matricula.id_turno.id_turno,
            }
        else:
            data = {
                'found': False,
                'message': "Estudiante encontrado pero sin historial de matrículas."
            }

    except Estudiante.DoesNotExist:
        data = {
            'found': False, 
            'message': "Estudiante no encontrado con esa cédula."
        }
    except Exception as e:
        data = {
            'found': False,
            'message': str(e)
        }
    
    return JsonResponse(data)


# GENERACIÓN DE REPORTES
@login_required
def generar_reporte(request):
    # 1. RECIBIR FILTROS (Misma lógica que students_view)
    q = request.GET.get("q", "")
    
    # Año escolar
    anio_activo = AnioEscolar.objects.filter(activo=True).first()
    selected_anio_id = request.GET.get("anio")
    anio_filtro = None

    if selected_anio_id is None:
        anio_filtro = anio_activo
    elif selected_anio_id == "":
        anio_filtro = None
    else:
        try:
            anio_filtro = AnioEscolar.objects.get(id_anio_escolar=selected_anio_id)
        except AnioEscolar.DoesNotExist:
            anio_filtro = anio_activo
    
    # 2. LÓGICA DE FILTRADO BASE (Solo Matriculados)
    if anio_filtro:
        matriculas = Matricula.objects.filter(id_anio_escolar=anio_filtro)
    else:
        matriculas = Matricula.objects.all()

    # Filtros adicionales
    grado = request.GET.get("grado")
    seccion = request.GET.get("seccion")
    turno = request.GET.get("turno")
    
    if grado:
        matriculas = matriculas.filter(id_grado__nombre=grado)
    if seccion:
        matriculas = matriculas.filter(id_seccion__letra=seccion)
    if turno:
        matriculas = matriculas.filter(id_turno__nombre=turno)
    
    # Filtro de búsqueda textual (q) sobre el Estudiante relacionado
    if q:
        matriculas = matriculas.filter(
            Q(id_estudiante__nombres__icontains=q) |
            Q(id_estudiante__apellidos__icontains=q) |
            Q(id_estudiante__cedula__icontains=q)
        )

    # 3. OPCIONES DEL REPORTE (Modal)
    incluir_retirados = request.GET.get("incluir_retirados") == "true"
    incluir_egresados = request.GET.get("incluir_egresados") == "true"
    formato = request.GET.get("formato", "pdf")

    # 4. APLICAR FILTROS DE ESTADO PARA EL REPORTE
    estados_incluidos = ["Nuevo", "Regular", "Repetido"] # Siempre incluidos (Equivalente a Activo)
    
    if incluir_retirados:
        estados_incluidos.append("Retirado")
    
    if incluir_egresados:
        estados_incluidos.append("Promovido")
    
    matriculas = matriculas.filter(estado__in=estados_incluidos)

    # Ordenamiento Jerárquico: Grado -> Sección -> Turno -> Apellidos -> Nombres
    matriculas = matriculas.order_by(
        "id_grado__orden", 
        "id_seccion__letra", 
        "id_turno__nombre",
        "id_estudiante__apellidos", 
        "id_estudiante__nombres"
    )

    # Prepara datos para el reporte
    registros = []
    for m in matriculas:
        est = m.id_estudiante
        rep = m.id_representante
        
        reg = {
            "apellidos": est.apellidos,
            "nombres": est.nombres,
            "cedula": est.cedula or "N/A",
            "sexo": est.sexo,
            "nacimiento": est.fecha_nacimiento.strftime("%d/%m/%Y") if est.fecha_nacimiento else "",
            "grado": m.id_grado.nombre,
            "seccion": m.id_seccion.letra,
            "turno": m.id_turno.nombre,
            "estado": m.estado,
            "fecha_mat": m.id_estudiante.fecha_registro.strftime("%d/%m/%Y") if m.id_estudiante.fecha_registro else (m.fecha_matricula.strftime("%d/%m/%Y") if m.fecha_matricula else ""),
            "lugar_nac": est.lugar_nacimiento or "",
            "t_camisa": est.talla_camisa or "",
            "t_pantalon": est.talla_pantalon or "",
            "t_zapato": est.talla_zapato or "",
            "rep_nombres": rep.nombres,
            "rep_apellidos": rep.apellidos,
            "rep_cedula": rep.cedula,
            "rep_telefono": rep.telefono,
            "rep_correo": rep.correo or "",
            "rep_direccion": rep.direccion or "",
            "observaciones": m.observaciones or ""
        }
        registros.append(reg)

    # Contexto para encabezados y nombre de archivo
    fecha_hoy = date.today().strftime("%d/%m/%Y")
    nombre_anio = anio_filtro.anio_escolar if anio_filtro else "Todos"
    
    # Textos condicionales
    txt_grado = grado if grado else "Todos los Grados"
    txt_seccion = f"Sección {seccion}" if seccion else "Todas las Secciones"
    txt_turno = f"Turno {turno}" if turno else "Todos los Turnos"

    context_filtros = {
        "fecha": fecha_hoy,
        "anio": nombre_anio,
        "grado": grado if grado else "Todos",
        "seccion": seccion if seccion else "Todas",
        "turno": turno if turno else "Todos",
        "txt_grado": txt_grado,
        "txt_seccion": txt_seccion,
        "txt_turno": txt_turno,
        "titulo_pdf": f"Fecha: {fecha_hoy} - Año: {nombre_anio}" 
    }

    if formato == "excel":
        return generar_excel(registros, context_filtros)
    else:
        # 8. NOMBRE DEL ARCHIVO PDF
        safe_anio = context_filtros['anio'].replace("/", "-")
        filename = f"Reporte del {context_filtros['fecha'].replace('/', '-')} del año escolar {safe_anio} del {context_filtros['txt_grado']} - {context_filtros['txt_seccion']} - {context_filtros['txt_turno']}.pdf"
        filename = filename.replace(":", "")
        
        return generar_pdf(registros, context_filtros, filename)

def generar_excel(registros, context_filtros):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reporte de Estudiantes"
    
    # 1. ENCABEZADO INSTITUCIONAL
    ws.merge_cells('A1:L1')
    ws['A1'] = "REPUBLICA BOLIVARIANA DE VENEZUELA"
    ws.merge_cells('A2:L2')
    ws['A2'] = "MINISTERIO DEL PODER POPULAR PARA LA EDUCACION"
    ws.merge_cells('A3:L3')
    ws['A3'] = 'E.B.E "POLICARPO FARRERA"'
    
    for row in range(1, 4):
        cell = ws[f'A{row}']
        cell.alignment = openpyxl.styles.Alignment(horizontal='center')
        cell.font = openpyxl.styles.Font(bold=True)
        
    # 2. INFORMACIÓN DEL REPORTE
    ws.merge_cells('A4:L4')
    ws['A4'] = f"Fecha de Reporte: {context_filtros['fecha']} - Año Escolar: {context_filtros['anio']}"
    ws['A4'].alignment = openpyxl.styles.Alignment(horizontal='center')
    ws['A4'].font = openpyxl.styles.Font(bold=True, size=11)

    # 3. INFORMACIÓN DE FILTROS
    ws.merge_cells('A5:L5')
    ws['A5'] = f"{context_filtros['txt_grado']} - {context_filtros['txt_seccion']} - {context_filtros['txt_turno']}"
    ws['A5'].alignment = openpyxl.styles.Alignment(horizontal='center')
    ws['A5'].font = openpyxl.styles.Font(bold=True, size=11)

    # 4. ENCABEZADOS DE TABLA
    headers = [
        "Apellidos", "Nombres", "Cédula Escolar", "Sexo", "F. Nacimiento", 
        "Grado", "Sección", "Turno", "Estado", "Fecha Inscripción", 
        "Lugar Nac.", "T. Camisa", "T. Pantalón", "T. Zapato", 
        "Nombres Rep.", "Apellidos Rep.", "Cédula Rep.", "Teléfono", "Correo", "Dirección", 
        "Observaciones"
    ]
    
    row_num = 7
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=row_num, column=col_num, value=header)
        cell.font = openpyxl.styles.Font(bold=True)
        cell.fill = openpyxl.styles.PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")
        cell.border = openpyxl.styles.Border(bottom=openpyxl.styles.Side(style='thin'))
        cell.alignment = openpyxl.styles.Alignment(horizontal='center')

    # 5. DATOS
    for reg in registros:
        row_num += 1
        row = [
            reg["apellidos"], reg["nombres"], reg["cedula"], reg["sexo"], reg["nacimiento"],
            reg["grado"], reg["seccion"], reg["turno"], reg["estado"], reg["fecha_mat"],
            reg["lugar_nac"], reg["t_camisa"], reg["t_pantalon"], reg["t_zapato"],
            reg["rep_nombres"], reg["rep_apellidos"], reg["rep_cedula"], reg["rep_telefono"], reg["rep_correo"], reg["rep_direccion"],
            reg["observaciones"]
        ]
        for col_num, value in enumerate(row, 1):
            ws.cell(row=row_num, column=col_num, value=value)
            
    # 6. ESTADÍSTICAS
    row_num += 3
    
    title_font = openpyxl.styles.Font(bold=True)
    
    total_sexo = {}
    total_grado = {}
    total_seccion = {}
    total_turno = {}
    
    for reg in registros:
        s = reg["sexo"]
        total_sexo[s] = total_sexo.get(s, 0) + 1
        g = reg["grado"]
        total_grado[g] = total_grado.get(g, 0) + 1
        sec = reg["seccion"]
        total_seccion[sec] = total_seccion.get(sec, 0) + 1
        t = reg["turno"]
        total_turno[t] = total_turno.get(t, 0) + 1

    # Bloque 1: Por Grado
    start_row = row_num
    ws.cell(row=start_row, column=1, value="Totales por Grado").font = title_font
    current_row = start_row + 1
    for grado, count in sorted(total_grado.items()):
        ws.cell(row=current_row, column=1, value=grado)
        ws.cell(row=current_row, column=2, value=count)
        current_row += 1
        
    # Bloque 2: Por Sección
    ws.cell(row=start_row, column=4, value="Totales por Sección").font = title_font
    current_row = start_row + 1
    for seccion, count in sorted(total_seccion.items()):
        ws.cell(row=current_row, column=4, value=seccion)
        ws.cell(row=current_row, column=5, value=count)
        current_row += 1

    # Bloque 3: Por Turno
    ws.cell(row=start_row, column=7, value="Totales por Turno").font = title_font
    current_row = start_row + 1
    for turno, count in sorted(total_turno.items()):
        ws.cell(row=current_row, column=7, value=turno)
        ws.cell(row=current_row, column=8, value=count)
        current_row += 1

    # Bloque 4: Por Sexo
    ws.cell(row=start_row, column=10, value="Totales por Sexo").font = title_font
    current_row = start_row + 1
    for sexo, count in sorted(total_sexo.items()):
        ws.cell(row=current_row, column=10, value=sexo)
        ws.cell(row=current_row, column=11, value=count)
        current_row += 1

    # 7. AJUSTAR ANCHO COLUMN
    from openpyxl.utils import get_column_letter

    for col_num, _ in enumerate(headers, 1):
        column_letter = get_column_letter(col_num)
        max_length = 0
        try:
             for cell in ws[column_letter]:
                try:
                    if cell.value and cell.row < row_num:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                except:
                    pass
        except:
             pass
             
        adjusted_width = (max_length + 2)
        if adjusted_width > 40: adjusted_width = 40
        if adjusted_width < 10: adjusted_width = 10
        ws.column_dimensions[column_letter].width = adjusted_width

    # 8. NOMBRE DEL ARCHIVO
    safe_anio = context_filtros['anio'].replace("/", "-")
    filename = f"Reporte del {context_filtros['fecha'].replace('/', '-')} del año escolar {safe_anio} del {context_filtros['txt_grado']} - {context_filtros['txt_seccion']} - {context_filtros['txt_turno']}.xlsx"
    filename = filename.replace(":", "") 
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response

def generar_pdf(registros, context_filtros, filename):
    buffer = BytesIO()
    # Margenes ajustados para dar espacio al encabezado
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=130, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    # --- DEFINICIÓN DE COLUMNAS DINÁMICAS ---
    # Columnas Base (Inicio)
    headers = ["Apellidos", "Nombres", "Cédula\nEscolar"]
    col_widths = [90, 90, 70]
    
    # 1. Determinar qué columnas extras mostrar (si el filtro es "Todos")
    show_grado = context_filtros.get('grado') == 'Todos'
    show_seccion = context_filtros.get('seccion') == 'Todos' or context_filtros.get('seccion') == 'Todas'
    show_turno = context_filtros.get('turno') == 'Todos'
    
    # Insertar columnas condicionales
    if show_grado:
        headers.append("Grado")
        col_widths.append(55)
    
    if show_seccion:
        headers.append("Sección")
        col_widths.append(40)
        
    if show_turno:
        headers.append("Turno")
        col_widths.append(45)
        
    # Columnas Base (Resto)
    headers.extend(["Fecha de\nNacimiento", "Rep.\nApellidos", "Rep.\nNombres", "Teléfono", "Correo Electrónico"])
    
    # Anchos fijos para el resto
    base_rest_widths = [65, 85, 85, 75] 
    # El ancho del correo se calculará para llenar el espacio, pero definimos uno mínimo
    
    col_widths.extend(base_rest_widths)
    
    # Calcular espacio restante para Correo
    total_width_available = 792 - 60 # Page width - margins
    used_width = sum(col_widths)
    email_width = total_width_available - used_width
    if email_width < 80: email_width = 80 # Mínimo razonable
    
    col_widths.append(email_width)

    # --- CONSTRUCCIÓN DE LA TABLA ---
    data = [headers]
    
    for reg in registros:
        row = [
            Paragraph(reg['apellidos'], styles['Normal']),
            Paragraph(reg['nombres'], styles['Normal']),
            reg['cedula']
        ]
        
        # Insertar datos condicionales en el mismo orden
        if show_grado:
            row.append(reg['grado'])
        if show_seccion:
            row.append(reg['seccion'])
        if show_turno:
            row.append(reg['turno'])
            
        row.extend([
            reg['nacimiento'],
            Paragraph(reg['rep_apellidos'], styles['Normal']),
            Paragraph(reg['rep_nombres'], styles['Normal']),
            reg['rep_telefono'],
            Paragraph(reg['rep_correo'], styles['Normal'])
        ])
        
        data.append(row)
    
    table = Table(data, colWidths=col_widths, repeatRows=1)
    
    # Estilos de tabla dinámicos (ajustar alineación según índices)
    table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.white),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        # Alineaciones fijas (Apellidos, Nombres siempre son 0, 1)
        ('ALIGN', (0, 1), (1, -1), 'LEFT'),  
    ]
    
    # Calcular índices para alineación izquierda de Rep. Nombres/Apellidos y Correo
    # Indices actuales:
    # 0: Apellidos
    # 1: Nombres
    # 2: Cedula
    # ... dinámicos ...
    # N: Nacimiento
    # N+1: Rep Apellidos
    # N+2: Rep Nombres
    # N+3: Telefono
    # N+4: Correo
    
    dynamic_count = sum([show_grado, show_seccion, show_turno])
    idx_rep_apellidos = 3 + dynamic_count + 1 # +1 por Nacimiento
    idx_correo = idx_rep_apellidos + 3
    
    table_style.append(('ALIGN', (idx_rep_apellidos, 1), (idx_rep_apellidos + 1, -1), 'LEFT')) # Rep Apellidos y Nombres
    table_style.append(('ALIGN', (idx_correo, 1), (idx_correo, -1), 'LEFT')) # Correo
    
    table.setStyle(TableStyle(table_style))
    
    elements.append(table)

    # --- FUNCIÓN DE ENCABEZADO ---
    def header_footer(canvas, doc):
        canvas.saveState()
        
        # 1. LOGO (Esquina superior izquierda)
        # Coordenadas aprox: x=30 (margen izq), y=530 (cerca del top, letter landscape height es 612)
        logo_path = str(settings.BASE_DIR / 'app/static/images/logo.png')
        try:
            # drawImage(image, x, y, width=None, height=None, mask=None, preserveAspectRatio=False, anchor='sw')
            canvas.drawImage(logo_path, 40, 500, width=80, height=80, mask='auto', preserveAspectRatio=True)
        except Exception as e:
            print(f"Error cargando logo: {e}")
            pass

        # 2. TEXTO INSTITUCIONAL (Centrado)
        # El centro de la página landscape es 792 / 2 = 396
        center_x = 396
        start_y = 570
        
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawCentredString(center_x, start_y, "REPUBLICA BOLIVARIANA DE VENEZUELA")
        canvas.drawCentredString(center_x, start_y - 14, "MINISTERIO DEL PODER POPULAR PARA LA EDUCACION")
        canvas.drawCentredString(center_x, start_y - 28, 'E.B.E "POLICARPO FARRERA"')
        
        # 3. DATOS DEL REPORTE
        canvas.setFont("Helvetica-Bold", 10)
        # Fecha: dd/mm/aaaa - Año: aaaa - aaaa 
        fecha_anio_str = f"Fecha: {context_filtros['fecha']} - Año: {context_filtros['anio']}"
        canvas.drawCentredString(center_x, start_y - 55, fecha_anio_str)
        
        # Grado - Sección - Turno
        filtros_str = f"{context_filtros['txt_grado']} - {context_filtros['txt_seccion']} - {context_filtros['txt_turno']}"
        canvas.drawCentredString(center_x, start_y - 70, filtros_str)
        
        canvas.restoreState()

    # Construir PDF
    doc.build(elements, onFirstPage=header_footer, onLaterPages=header_footer)
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response