import random
from django.core.mail import send_mail
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.contrib.auth import login, logout
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Count
from django.contrib.auth import authenticate

# Importando modelos de la base de datos
from .models import AnioEscolar
from .models import Estudiante
from .models import Grado
from .models import Matricula
from .models import Representante
from .models import Seccion
from .models import Turno

# Create your views here.

# Autenticación inicial
def login_request(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")
    else:
        form = AuthenticationForm(request)

    return render(request, "authentication/login.html", {"form": form})

# Login requerido para mostrar el dashboard
@login_required
def home_view(request):
    return render(request, "modules/home.html")


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

@login_required
def profile_user(request):
    return render(request, "views/profile.html")

@login_required
def help(request):
    return render(request, "views/help.html")

@login_required
def academic_record(request):
    return render(request, "modules/academic_record.html")

def logout_view(request):
    logout(request)
    return redirect("login")

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
        elif role not in ["Administrador", "Directivo", "Docente"]:
            messages.error(request, "Debes seleccionar un rol válido.")
        elif not es_super_admin and role == "Administrador":
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
        # Un directivo no puede borrar administradores
        elif not es_super_admin and user.groups.filter(name="Administrador").exists():
            messages.error(request, "No tienes permiso para eliminar Administradores.")
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

            if role not in ["Administrador", "Directivo", "Docente"]:
                messages.error(request, "Rol no válido.")
            elif not es_super_admin and role == "Administrador":
                messages.error(request, "Solo un Administrador puede asignar el rol Administrador.")
            else:
                # Limpiamos grupos relevantes y añadimos el nuevo
                for nombre in ["Administrador", "Directivo", "Docente"]:
                    user.groups.remove(*Group.objects.filter(name=nombre))
                grupo, _ = Group.objects.get_or_create(name=role)
                user.groups.add(grupo)
                messages.success(request, "Rol actualizado.")
        except User.DoesNotExist:
            messages.error(request, "El usuario no existe.")
        return redirect("users_control")

    # GET: listar usuarios
    usuarios = User.objects.all().order_by("username")
    grupos = Group.objects.filter(name__in=["Administrador", "Directivo", "Docente"])

    contexto = {
        "usuarios": usuarios,
        "grupos": grupos,
        "es_super_admin": es_super_admin,
    }
    return render(request, "authentication/users_control.html", contexto)

@login_required
def students_view(request):
    if request.method == "POST":
        try:
            with transaction.atomic():
                # 1. Verificar que existe un año escolar activo
                try:
                    anio_activo = AnioEscolar.objects.get(activo=True)
                except AnioEscolar.DoesNotExist:
                    messages.error(request, "No hay un año escolar activo. Contacta al administrador.")
                    return redirect("students")

                # 2. Capturar datos del estudiante
                nombres = request.POST.get("nombres")
                apellidos = request.POST.get("apellidos")
                cedula = request.POST.get("cedula") or None
                sexo_in = request.POST.get("sexo")
                fecha_nacimiento = request.POST.get("fecha_nacimiento") or None
                lugar_nacimiento = request.POST.get("lugar_nacimiento") or ""
                talla_camisa = request.POST.get("talla_camisa") or ""
                talla_pantalon = request.POST.get("talla_pantalon") or ""
                talla_zapato = request.POST.get("talla_zapato") or ""

                # Validaciones básicas
                if not nombres or not apellidos or not fecha_nacimiento:
                    messages.error(request, "Nombres, apellidos y fecha de nacimiento son obligatorios.")
                    return redirect("students")

                # Convertir sexo
                sexo = "F" if sexo_in == "Femenino" else "M"

                # 3. Capturar datos del representante
                rep_nombres = request.POST.get("rep_nombres")
                rep_apellidos = request.POST.get("rep_apellidos")
                rep_cedula = request.POST.get("rep_cedula")
                rep_telefono = request.POST.get("rep_telefono")
                rep_correo = request.POST.get("rep_correo") or ""
                rep_direccion = request.POST.get("rep_direccion") or ""

                # Validar datos del representante
                if not rep_nombres or not rep_apellidos or not rep_cedula or not rep_telefono:
                    messages.error(request, "Los datos del representante son obligatorios (nombres, apellidos, cédula y teléfono).")
                    return redirect("students")

                # 4. Buscar o crear representante
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

                # Si ya existía, actualizar sus datos
                if not created:
                    representante.nombres = rep_nombres
                    representante.apellidos = rep_apellidos
                    representante.telefono = rep_telefono
                    representante.correo = rep_correo
                    representante.direccion = rep_direccion
                    representante.save()

                # 5. Crear el estudiante
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
                )

                # 6. Capturar datos de matrícula
                grado_nombre = request.POST.get("grado")
                seccion_letra = request.POST.get("seccion")
                turno_nombre = request.POST.get("turno")
                observaciones = request.POST.get("observaciones") or ""

                # Validar que se hayan seleccionado grado, sección y turno
                if not grado_nombre or not seccion_letra or not turno_nombre:
                    messages.error(request, "Debes seleccionar grado, sección y turno.")
                    return redirect("students")

                # 7. Buscar grado, sección y turno en la base de datos
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

                # 8. Crear la matrícula vinculando todo
                from datetime import date
                
                Matricula.objects.create(
                    id_estudiante=estudiante,
                    id_representante=representante,
                    id_grado=grado,
                    id_seccion=seccion,
                    id_turno=turno,
                    id_anio_escolar=anio_activo,
                    anio_ingreso=anio_activo.fecha_inicio.year,
                    fecha_matricula=date.today(),
                    estado="Activo",
                    observaciones=observaciones
                )

                messages.success(request, f"Estudiante {nombres} {apellidos} registrado y matriculado correctamente.")
                return redirect("students")

        except Exception as e:
            messages.error(request, f"Error al registrar el estudiante: {str(e)}")
            return redirect("students")

    # GET: Mostrar formulario con datos necesarios
    estudiantes = Estudiante.objects.all().order_by("apellidos", "nombres")
    grados = Grado.objects.all().order_by("orden")
    secciones = Seccion.objects.all()
    turnos = Turno.objects.all()
    
    # Verificar si hay año escolar activo
    anio_activo = AnioEscolar.objects.filter(activo=True).first()
    hay_anio_activo = anio_activo is not None

    # Filtros de Estudiante (Sexo)
    sexo = request.GET.get("sexo")
    if sexo:
        estudiantes = estudiantes.filter(sexo=sexo)

    # Adjuntar matrícula activa a cada estudiante y filtrar por matrícula
    if hay_anio_activo:
        # Base query: matrículas del año escolar activo
        matriculas = Matricula.objects.filter(id_anio_escolar=anio_activo)

        # Filtros de Matrícula
        grado = request.GET.get("grado")
        if grado:
             matriculas = matriculas.filter(id_grado__nombre=grado)

        seccion = request.GET.get("seccion")
        if seccion:
             matriculas = matriculas.filter(id_seccion__letra=seccion)

        turno = request.GET.get("turno")
        if turno:
             matriculas = matriculas.filter(id_turno__nombre=turno)
        
        # Filtro de Estado (Default: Activo)
        estado = request.GET.get("estado")
        if estado is None:
            estado = "Activo"
        
        if estado: # Si es "" (Todos), no filtramos
            matriculas = matriculas.filter(estado=estado)

        # Optimización
        matriculas = matriculas.select_related('id_grado', 'id_seccion', 'id_turno', 'id_representante')
        
        # Filtramos la lista de estudiantes para mostrar solo los que quedaron tras los filtros de matrícula
        # Esto nos asegura que si filtro por "1er Grado", no me salgan estudiantes de otros grados sin matrícula adjunta.
        student_ids = matriculas.values_list('id_estudiante_id', flat=True)
        estudiantes = estudiantes.filter(id_estudiante__in=student_ids)

        # Creamos mapa y adjuntamos
        matricula_map = {m.id_estudiante_id: m for m in matriculas}
        for est in estudiantes:
            est.matricula_activa = matricula_map.get(est.id_estudiante)
            
    else:
        # Si no hay año activo, no hay matrículas, pero mostramos los estudiantes (o lista vacía si filtramos por algo que requiere matrícula?)
        # Si el usuario filtra por grado y no hay año activo, la lista sale vacía.
        # Pero los filtros de grado/sección dependen de la matrícula, así que técnicamente no deberían devolver nada.
        # El comportamiento actual es: si no hay año activo, matricula_map no existe, matricula_activa es None.
        for est in estudiantes:
            est.matricula_activa = None
    
    # Convertimos a listas para poder agregar attributos dinámicos 'selected' sin tocar el modelo
    grados_list = list(Grado.objects.all().order_by("orden"))
    secciones_list = list(Seccion.objects.all())
    turnos_list = list(Turno.objects.all())

    # Funciones auxiliares para marcar selección
    selected_grado = request.GET.get("grado")
    for g in grados_list:
        g.selected = (g.nombre == selected_grado)

    selected_seccion = request.GET.get("seccion")
    for s in secciones_list:
        s.selected = (s.letra == selected_seccion)

    selected_turno = request.GET.get("turno")
    for t in turnos_list:
        t.selected = (t.nombre == selected_turno)

    # Para sexo y estado, pasamos el valor seleccionado directo al contexto para compararlo fácil o usamos diccionarios
    # Pero sexo y estado son hardcoded en el template. 
    # Para simplificar el template y evitar el probelma de espacios, pasamos flags booleanos
    selected_sexo = request.GET.get("sexo")
    context_sexo = {
        "F": selected_sexo == "F",
        "M": selected_sexo == "M"
    }

    selected_estado = request.GET.get("estado")
    # Si es None, es Activo por defecto en la lógica de filtrado, 
    # pero en el dropdown queremos que marques lo que el usuario envió.
    # Si el usuario no envió nada, el filtro por defecto es Activo, así que marcamos Activo.
    if selected_estado is None: 
        selected_estado = "Activo"
        
    context_estado = {
        "Activo": selected_estado == "Activo",
        "Retirado": selected_estado == "Retirado",
        "Todos": selected_estado == ""
    }
    
    contexto = {
        "estudiantes": estudiantes,
        "grados": grados_list,
        "secciones": secciones_list,
        "turnos": turnos_list,
        "hay_anio_activo": hay_anio_activo,
        "selected_sexo": context_sexo,
        "selected_estado": context_estado,
    }
    
    return render(request, "modules/students.html", contexto)

def parents_list(request):
    q = request.GET.get('q', '')
    grado = request.GET.get('grado', '')
    seccion = request.GET.get('seccion', '')
    estado = request.GET.get('estado', '')

    parents = (
        Representante.objects
        .annotate(num_estudiantes=Count('matricula__id_estudiante', distinct=True))
    )

    if q:
        parents = parents.filter(
            Q(nombres__icontains=q) |
            Q(apellidos__icontains=q) |
            Q(cedula__icontains=q)
        )

    # Si todavía no quieres que filtren por grado/sección/estado, 
    # puedes comentar esto para simplificar:
    # if grado:
    #     parents = parents.filter(matricula__id_grado__id_grado=grado).distinct()
    # if seccion:
    #     parents = parents.filter(matricula__id_seccion__letra=seccion).distinct()
    # if estado == 'activo':
    #     parents = parents.filter(matricula__estado='Activo').distinct()
    # elif estado == 'inactivo':
    #     parents = parents.filter(matricula__estado='Inactivo').distinct()

    context = {
        'parents': parents,
        'q': q,
        'grado': grado,
        'seccion': seccion,
        'estado': estado,
    }
    return render(request, 'modules/parents.html', context)

@require_POST
def parent_edit(request, pk):
    parent = get_object_or_404(Representante, id_representante=pk)
    parent.nombres = request.POST.get('nombres', parent.nombres)
    parent.apellidos = request.POST.get('apellidos', parent.apellidos)
    parent.correo = request.POST.get('correo', parent.correo)
    parent.telefono = request.POST.get('telefono', parent.telefono)
    parent.save()
    return redirect('parents_list')


@require_POST
def parent_delete(request, pk):
    parent = get_object_or_404(Representante, id_representante=pk)
    parent.delete()
    return redirect('parents_list')
