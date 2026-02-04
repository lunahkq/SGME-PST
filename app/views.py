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
from django.db import transaction
from django.db.models import Q, Count
from django.db.models.functions import TruncYear
from django.contrib.auth import authenticate
from datetime import date

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
            matricula__estado__in=['Activo', 'Regular', 'Nuevo'],
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
            matricula__estado__in=['Activo', 'Regular', 'Nuevo'],
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

        # ELIMINAR ESTUDIANTE + REPRESENTANTE HUÉRFANO (VERSIÓN FINAL CORREGIDA)
        elif accion == "eliminar":
            try:
                estudiante = get_object_or_404(Estudiante, id_estudiante=est_id)
                password = request.POST.get("password")
                
                # Verificar contraseña del usuario logueado
                user = authenticate(username=request.user.username, password=password)
                if user is None:
                    messages.error(request, "❌ Contraseña incorrecta. No se eliminó el estudiante.")
                    return redirect("students")
                
                with transaction.atomic():
                    # OBTENER REPRESENTANTE ANTES DE ELIMINAR
                    matricula_activa = Matricula.objects.filter(
                        id_estudiante=estudiante,
                        id_anio_escolar__activo=True
                    ).select_related('id_representante').first()
                    
                    representante = None
                    if matricula_activa and matricula_activa.id_representante:
                        representante = matricula_activa.id_representante
                    
                    # 1. Eliminar TODAS las matrículas del estudiante PRIMERO
                    Matricula.objects.filter(id_estudiante=estudiante).delete()
                    
                    # 2. Eliminar el estudiante
                    estudiante.delete()
                    
                    messages.success(request, "✅ Estudiante eliminado permanentemente de la base de datos.")
                    
                    # 3. VERIFICAR Y ELIMINAR REPRESENTANTE SOLO SI REALMENTE ESTÁ HUÉRFANO
                    if representante:
                        # CONTAR matrículas restantes del representante (TODAS)
                        count_matriculas = Matricula.objects.filter(
                            id_representante=representante
                        ).count()
                        
                        if count_matriculas == 0:
                            representante.delete()
                            messages.info(request, f"🗑️ Representante {representante.nombres} {representante.apellidos} eliminado (sin estudiantes).")
                        else:
                            messages.info(request, f"ℹ️ Representante conservado (tiene {count_matriculas} matrícula(s) restante(s)).")
                
                return redirect("students")
            except Exception as e:
                messages.error(request, f"Error al eliminar estudiante: {str(e)}")
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

                    if not nombres or not apellidos or not fecha_nacimiento:
                        messages.error(request, "Nombres, apellidos y fecha de nacimiento son obligatorios.")
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

            except Exception as e:
                messages.error(request, f"Error al registrar/actualizar el estudiante: {str(e)}")
                return redirect("students")

    # GET - Listado y filtros (tu código original sin cambios)
    estudiantes = Estudiante.objects.all().order_by("apellidos", "nombres")
    grados = Grado.objects.all().order_by("orden")
    secciones = Seccion.objects.all()
    turnos = Turno.objects.all()
    anios = AnioEscolar.objects.all().order_by('-anio_escolar')  # Orden descendente (más reciente primero)

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

    # Filtrar matrículas por el año seleccionado (o el activo por defecto)
    if anio_filtro:
        matriculas = Matricula.objects.filter(id_anio_escolar=anio_filtro)
    else:
        matriculas = Matricula.objects.all()

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
        # "Activo" para el usuario significa: Activo, Nuevo o Regular
        matriculas = matriculas.filter(estado__in=["Activo", "Nuevo", "Regular"])
    elif selected_estado == "Retirado":
        matriculas = matriculas.filter(estado="Retirado")
    # Si selected_estado == "" (Todos), no filtramos nada
        
    matriculas = matriculas.select_related('id_grado', 'id_seccion', 'id_turno', 'id_representante')

    student_ids = matriculas.values_list('id_estudiante_id', flat=True)
    estudiantes = estudiantes.filter(id_estudiante__in=student_ids)

    matricula_map = {m.id_estudiante_id: m for m in matriculas}
    for est in estudiantes:
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
        "Retirado": selected_estado == "Retirado",
        "Todos": selected_estado == ""
    }

    contexto = {
        "estudiantes": estudiantes,
        "grados": grados_list,
        "secciones": secciones_list,
        "turnos": turnos_list,
        "anios": anios,
        "hay_anio_activo": hay_anio_activo,
        "selected_anio_id": int(selected_anio_id) if selected_anio_id and selected_anio_id.isdigit() else ("" if selected_anio_id == "" else (anio_activo.id_anio_escolar if anio_activo else None)),
        "selected_sexo": context_sexo,
        "selected_estado": context_estado,
        "q": q,
    }
    return render(request, "modules/students.html", contexto)



# MÓDULO DE REPRESENTANTES
from django.contrib import messages  # ← AGREGAR ESTA LÍNEA AL INICIO

def parents_list(request):
    q = request.GET.get('q', '')
    grado = request.GET.get('grado', '')
    seccion = request.GET.get('seccion', '')
    turno = request.GET.get('turno', '')
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
    if turno: # Corrección: ahora filtra por nombre del turno, no 'M'/'T'
        parents = parents.filter(
            matricula__id_turno__nombre=turno
        ).distinct()

    # Filtro por estado de la matrícula
    if estado == 'Activo':
        parents = parents.filter(
            matricula__estado='Activo'
        ).distinct()
    elif estado == 'Inactivo': # Corrección: Inactivo capitalizado para consistencia
        parents = parents.filter(
            matricula__estado='Inactivo'
        ).distinct()

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

    context = {
        'parents': parents,
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
def parent_edit(request, pk):
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
    - Promoción / repetición / egreso
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

    # Promoción / repetición / egreso
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

                origen_grado = Grado.objects.get(id_grado=origen_grado_id)
                origen_seccion = Seccion.objects.get(letra=origen_seccion_id)
                origen_turno = Turno.objects.get(codigo=origen_turno_codigo)

                destino_grado = Grado.objects.get(id_grado=destino_grado_id)
                destino_seccion = Seccion.objects.get(letra=destino_seccion_id)
                destino_turno = Turno.objects.get(codigo=destino_turno_codigo)

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
                    # Caso egreso: 6to grado
                    if origen_grado.orden == 6:
                        m.estado = "Promovido"
                        m.save()
                        total_promovidos += 1
                        continue

                    # Misma combinación de grado -> Repetido
                    if origen_grado.id_grado == destino_grado.id_grado:
                        nuevo_estado = "Repetido"
                        total_repetidos += 1
                    else:
                        nuevo_estado = "Regular"
                        total_regulares += 1

                    Matricula.objects.create(
                        id_estudiante=m.id_estudiante,
                        id_representante=m.id_representante,
                        id_grado=destino_grado,
                        id_seccion=destino_seccion,
                        id_turno=destino_turno,
                        id_anio_escolar=destino_anio,
                        anio_ingreso=destino_anio.fecha_inicio.year,
                        fecha_matricula=m.fecha_matricula,
                        estado=nuevo_estado,
                        observaciones=(
                            f"Promocionado desde {origen_grado.nombre} "
                            f"{origen_seccion.letra} {origen_turno.nombre} ({origen_anio.anio_escolar})"
                        ),
                    )

                messages.success(request, "Se realizó la promoción correctamente.")

        except Exception as e:
            messages.error(request, f"Error en la promoción: {str(e)}")

        return redirect("academic")

    # GET: datos para mostrar formulario
    anios = AnioEscolar.objects.all().order_by("-fecha_inicio")
    anio_activo = AnioEscolar.objects.filter(activo=True).first()
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