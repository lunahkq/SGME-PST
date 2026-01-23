import random
from django.core.mail import send_mail
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, logout
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
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
    # Más adelante pasaremos datos contextuales (grados, turnos, etc.)
    return render(request, "modules/students.html")

@login_required
def students_view(request):
    if request.method == "POST":
        nombres = request.POST.get("nombres")
        apellidos = request.POST.get("apellidos")
        cedula = request.POST.get("cedula") or None
        sexo_in = request.POST.get("sexo")
        fecha_nacimiento = request.POST.get("fecha_nacimiento") or None
        lugar_nacimiento = request.POST.get("lugar_nacimiento") or ""
        talla_camisa = request.POST.get("talla_camisa") or ""
        talla_pantalon = request.POST.get("talla_pantalon") or ""
        talla_zapato = request.POST.get("talla_zapato") or ""

        # Convertimos a "F"/"M"
        sexo = "F" if sexo_in == "Femenino" else "M"

        Estudiante.objects.create(
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

        return redirect("students")

    estudiantes = Estudiante.objects.all().order_by("apellidos", "nombres")
    return render(request, "modules/students.html", {"estudiantes": estudiantes})

@login_required
def students_view(request):
    if request.method == "POST":
        nombres = request.POST.get("nombres")
        apellidos = request.POST.get("apellidos")
        cedula = request.POST.get("cedula") or None
        sexo_in = request.POST.get("sexo")
        fecha_nacimiento = request.POST.get("fecha_nacimiento") or None
        lugar_nacimiento = request.POST.get("lugar_nacimiento") or ""
        talla_camisa = request.POST.get("talla_camisa") or ""
        talla_pantalon = request.POST.get("talla_pantalon") or ""
        talla_zapato = request.POST.get("talla_zapato") or ""

        sexo = "F" if sexo_in == "Femenino" else "M"

        Estudiante.objects.create(
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
        messages.success(request, "Estudiante registrado correctamente.")
        return redirect("students")

    estudiantes = Estudiante.objects.all().order_by("apellidos", "nombres")
    return render(request, "modules/students.html", {"estudiantes": estudiantes})
