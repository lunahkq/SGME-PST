from flask import Flask, render_template, request, redirect, session, url_for, jsonify, flash
import sqlite3
from functools import wraps
# 🔑 CORRECCIÓN 1: Se importa correctamente desde werkzeug.security
from werkzeug.security import generate_password_hash, check_password_hash 

app = Flask(__name__)
app.secret_key = "clave_super_secreta"

DB = "registro.db"

# -----------------------------
# Helpers
# -----------------------------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'usuario' not in session:
                return redirect(url_for('login'))
            if role and session.get('role') not in role:
                flash("No tienes permisos para acceder a esta sección.", "danger")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return wrapped
    return decorator

# -----------------------------
# Crear / migrar base de datos (Estructura con campos de Seguridad)
# -----------------------------
def crear_base():
    conn = get_db()
    cur = conn.cursor()

    try:
        # Tabla representantes
        cur.execute("""
            CREATE TABLE IF NOT EXISTS representantes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombres TEXT,
                apellidos TEXT,
                cedula TEXT UNIQUE,
                telefono TEXT,
                correo TEXT,
                direccion TEXT
            )
        """)

        # Tabla estudiantes
        cur.execute("""
            CREATE TABLE IF NOT EXISTS estudiantes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombres TEXT,
                apellidos TEXT,
                cedula TEXT UNIQUE,
                sexo TEXT,
                fecha_nacimiento TEXT,
                lugar_nacimiento TEXT,
                direccion TEXT,
                telefono TEXT,
                correo TEXT,
                talla_camisa TEXT,
                talla_pantalon TEXT,
                talla_zapato TEXT,
                observaciones TEXT,
                grado TEXT,
                seccion TEXT,
                turno TEXT,
                representante_id INTEGER,
                FOREIGN KEY(representante_id) REFERENCES representantes(id)
            )
        """)

        # Usuarios y roles (ATENCIÓN: Se incluyen campos de seguridad)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT,
                security_question TEXT,
                security_answer_hash TEXT 
            )
        """)

        # Seed: crear usuario admin si no existe
        cur.execute("SELECT id FROM users WHERE username = ?", ("admin",))
        if not cur.fetchone():
            # 🔑 CORRECCIÓN 2: Uso del método de hashing compatible 'pbkdf2:sha256'
            hashed_password = generate_password_hash("1234", method='pbkdf2:sha256') 
            # Respuesta secreta hasheada
            hashed_answer = generate_password_hash("UNETI", method='pbkdf2:sha256') 
            
            cur.execute("""INSERT INTO users (username, password, role, security_question, security_answer_hash) 
                            VALUES (?, ?, ?, ?, ?)""",
                        ("admin", hashed_password, "Administrador", 
                         "¿Nombre de la institución?", hashed_answer)) 

        conn.commit()
    except sqlite3.Error as e:
        print(f"Error al crear la base de datos: {e}")
        conn.rollback()
    finally:
        conn.close()

# -----------------------------
# RUTAS: LOGIN, LOGOUT
# -----------------------------
@app.route('/', methods=['GET', 'POST'])
def login():
    mensaje = ""
    if request.method == 'POST':
        usuario = request.form['usuario'] 
        contrasena = request.form['contrasena']
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM users WHERE username=?", (usuario,))
        user = cur.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], contrasena):
            session['usuario'] = usuario
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            mensaje = "Usuario o contraseña incorrectos"
            
    return render_template('login.html', mensaje=mensaje)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -----------------------------
# RECUPERACIÓN DE CONTRASEÑA (Lógica de dos pasos robusta)
# -----------------------------
@app.route('/recuperar_contrasena', methods=['GET', 'POST'])
def recuperar_contrasena():
    if request.method == 'POST':
        # Usamos .get() para OBTENER los valores o None si no existen, EVITANDO EL KeyError.
        usuario = request.form.get('usuario')
        respuesta = request.form.get('respuesta_secreta')
        nueva_contrasena = request.form.get('nueva_contrasena')
        
        conn = get_db()
        cur = conn.cursor()

        # ----------------------------------------------------
        # CASO 1: PASO INICIAL (Se envía solo el 'usuario')
        # ----------------------------------------------------
        if usuario and not respuesta and not nueva_contrasena:
            cur.execute("SELECT * FROM users WHERE username=?", (usuario,))
            user = cur.fetchone()
            conn.close()
            
            if user and user['security_question']:
                # Almacenamos el usuario en la sesión para el paso 2
                session['recovery_user'] = usuario
                return render_template('recuperar_contrasena.html', 
                                       step=2, 
                                       pregunta=user['security_question'])
            else:
                flash("Usuario no encontrado o no tiene una pregunta de seguridad configurada.", "danger")
                return redirect(url_for('recuperar_contrasena'))

        # ----------------------------------------------------
        # CASO 2: CAMBIO DE CONTRASEÑA (Se envían respuesta y nueva clave)
        # ----------------------------------------------------
        elif respuesta and nueva_contrasena and 'recovery_user' in session:
            usuario = session.pop('recovery_user') # Recuperar y eliminar de la sesión
            
            cur.execute("SELECT * FROM users WHERE username=?", (usuario,))
            user = cur.fetchone()
            
            # Verificamos la respuesta secreta (tambien hasheada con pbkdf2:sha256)
            if user and check_password_hash(user['security_answer_hash'], respuesta):
                # Procede a cambiar la contraseña
                hashed_new_password = generate_password_hash(nueva_contrasena, method='pbkdf2:sha256')
                cur.execute("UPDATE users SET password=? WHERE username=?", 
                            (hashed_new_password, usuario))
                conn.commit()
                conn.close()
                
                flash("¡Contraseña restablecida con éxito! Ya puedes iniciar sesión.", "success")
                return redirect(url_for('login'))
            else:
                # Si falla la verificación, cerramos la conexión y la sesión de recuperación
                if 'recovery_user' in session:
                     session.pop('recovery_user') 
                conn.close()
                flash("Respuesta secreta incorrecta. El proceso de recuperación ha finalizado por seguridad.", "danger")
                return redirect(url_for('recuperar_contrasena'))

        # ----------------------------------------------------
        # CASO 3: Falla genérica
        # ----------------------------------------------------
        else:
            conn.close()
            flash("Faltan datos o la sesión de recuperación ha expirado. Intente de nuevo.", "danger")
            return redirect(url_for('recuperar_contrasena'))

    # GET (default): Muestra el primer paso del formulario
    return render_template('recuperar_contrasena.html', step=1)

# -----------------------------
# REGISTRO EXTERNO DE ESTUDIANTES (Matrícula)
# -----------------------------
@app.route('/registrar', methods=['GET', 'POST'])
def registrar_estudiante():
    if request.method == 'POST':
        data = request.form 
        conn = get_db()
        cur = conn.cursor()
        
        try:
            # --- 1. Gestionar el Representante ---
            rep_id = None
            rep_cedula = data.get('rep_cedula')
            
            if rep_cedula:
                cur.execute("SELECT id FROM representantes WHERE cedula = ?", (rep_cedula,))
                r = cur.fetchone()
                
                if r:
                    rep_id = r['id']
                else:
                    cur.execute("""INSERT INTO representantes (nombres, apellidos, cedula, telefono, correo, direccion)
                                    VALUES (?, ?, ?, ?, ?, ?)""",
                                (data.get('rep_nombres'), data.get('rep_apellidos'), rep_cedula,
                                data.get('rep_telefono'), data.get('rep_correo'), data.get('rep_direccion')))
                    rep_id = cur.lastrowid

            # --- 2. Insertar el Estudiante ---
            cur.execute("""
                INSERT INTO estudiantes (nombres, apellidos, cedula, sexo, fecha_nacimiento, lugar_nacimiento,
                                         direccion, telefono, correo, talla_camisa, talla_pantalon, talla_zapato,
                                         observaciones, grado, seccion, turno, representante_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('nombres'), data.get('apellidos'), data.get('cedula_estudiante'), data.get('sexo'), 
                data.get('fecha_nacimiento'), data.get('lugar_nacimiento'), data.get('direccion_estudiante'), 
                data.get('telefono_estudiante'), data.get('correo_estudiante'), 
                data.get('talla_camisa'), data.get('talla_pantalon'), data.get('talla_zapato'),
                data.get('observaciones'),
                data.get('grado'), data.get('seccion'), data.get('turno'), rep_id
            ))
            
            conn.commit()
            flash("¡Registro completado con éxito! Su solicitud de matrícula está siendo procesada.", "success")
            return redirect(url_for('registrar_estudiante'))

        except sqlite3.IntegrityError:
            flash("Error: Ya existe un estudiante o representante con la cédula ingresada. Revise los datos.", "danger")
            conn.rollback()
        except sqlite3.Error as e:
            flash(f"Error al procesar el registro. Detalles: {e}", "danger")
            conn.rollback()
        finally:
            conn.close()

    # GET request: Muestra el formulario
    return render_template('registro_estudiante.html')

# -----------------------------
# DASHBOARD: resumen y gráficas
# -----------------------------
@app.route('/dashboard')
@login_required()
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/dashboard_counts')
@login_required()
def api_dashboard_counts():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT grado, seccion, turno, COUNT(*) as total FROM estudiantes GROUP BY grado, seccion, turno")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)

# -----------------------------
# ESTUDIANTES: listado, filtros, CRUD
# -----------------------------
@app.route('/estudiantes')
@login_required()
def estudiantes_page():
    return render_template('estudiantes.html')

@app.route('/api/estudiantes', methods=['GET'])
@login_required()
def api_estudiantes():
    # filtros: grado, seccion, turno
    grado = request.args.get('grado') or ""
    seccion = request.args.get('seccion') or ""
    turno = request.args.get('turno') or ""
    sexo = request.args.get('sexo') or ""

    conn = get_db()
    cur = conn.cursor()
    # 🔑 CORRECCIÓN 3: La estructura de la consulta está limpia y correcta para evitar errores de sintaxis
    query = """
        SELECT e.*, r.nombres as rep_nombres, r.apellidos as rep_apellidos, r.cedula as rep_cedula 
        FROM estudiantes e 
        LEFT JOIN representantes r ON e.representante_id = r.id 
        WHERE 1=1
    """
    params = []
    
    if grado:
        query += " AND grado = ?"
        params.append(grado)
    if seccion:
        query += " AND seccion = ?"
        params.append(seccion)
    if turno:
        query += " AND turno = ?"
        params.append(turno)
    if sexo:
        query += " AND sexo = ?"
        params.append(sexo)
        
    query += " ORDER BY grado, seccion, apellidos"
    
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/api/estudiante', methods=['POST'])
@login_required(role=['Administrador','Soporte','Directivo'])
def api_crear_estudiante():
    data = request.json
    conn = get_db()
    cur = conn.cursor()

    # Si se proporciona representante_cedula y existe, obtener su id. Si no existe, crear representante.
    rep_id = None
    rep_cedula = data.get('rep_cedula')
    if rep_cedula:
        cur.execute("SELECT id FROM representantes WHERE cedula = ?", (rep_cedula,))
        r = cur.fetchone()
        if r:
            rep_id = r['id']
        else:
            cur.execute("""INSERT INTO representantes (nombres, apellidos, cedula, telefono, correo, direccion)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                        (data.get('rep_nombres'), data.get('rep_apellidos'), rep_cedula,
                         data.get('rep_telefono'), data.get('rep_correo'), data.get('rep_direccion')))
            rep_id = cur.lastrowid

    cur.execute("""
        INSERT INTO estudiantes (nombres, apellidos, cedula, sexo, fecha_nacimiento, lugar_nacimiento,
                                 direccion, telefono, correo, talla_camisa, talla_pantalon, talla_zapato,
                                 observaciones, grado, seccion, turno, representante_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('nombres'), data.get('apellidos'), data.get('cedula'), data.get('sexo'),
        data.get('fecha_nacimiento'), data.get('lugar_nacimiento'), data.get('direccion'),
        data.get('telefono'), data.get('correo'),
        data.get('talla_camisa'), data.get('talla_pantalon'), data.get('talla_zapato'),
        data.get('observaciones'),
        data.get('grado'), data.get('seccion'), data.get('turno'), rep_id
    ))
    conn.commit()
    conn.close()
    return jsonify({"ok": True}), 201

@app.route('/api/estudiante/<int:id>', methods=['PUT'])
@login_required(role=['Administrador','Soporte','Directivo'])
def api_editar_estudiante(id):
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE estudiantes SET nombres=?, apellidos=?, cedula=?, sexo=?, fecha_nacimiento=?, lugar_nacimiento=?,
            direccion=?, telefono=?, correo=?, talla_camisa=?, talla_pantalon=?, talla_zapato=?, observaciones=?,
            grado=?, seccion=?, turno=? WHERE id=?
    """, (
        data.get('nombres'), data.get('apellidos'), data.get('cedula'), data.get('sexo'),
        data.get('fecha_nacimiento'), data.get('lugar_nacimiento'), data.get('direccion'),
        data.get('telefono'), data.get('correo'), data.get('talla_camisa'), data.get('talla_pantalon'),
        data.get('talla_zapato'), data.get('observaciones'), data.get('grado'), data.get('seccion'),
        data.get('turno'), id
    ))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route('/api/estudiante/<int:id>', methods=['DELETE'])
@login_required(role=['Administrador','Soporte'])
def api_eliminar_estudiante(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM estudiantes WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# -----------------------------
# REPRESENTANTES
# -----------------------------
@app.route('/representantes')
@login_required()
def representantes_page():
    return render_template('representantes.html')

@app.route('/api/representantes', methods=['GET'])
@login_required()
def api_representantes():
    grado = request.args.get('grado') or ""
    seccion = request.args.get('seccion') or ""
    turno = request.args.get('turno') or ""
    conn = get_db()
    cur = conn.cursor()
    # obtener representantes y cuantos estudiantes asociados
    query = """
        SELECT r.*, COUNT(e.id) as total_estudiantes
        FROM representantes r
        LEFT JOIN estudiantes e ON e.representante_id = r.id
    """
    params = []
    if grado or seccion or turno:
        query += " WHERE 1=1 "
        if grado:
            query += " AND EXISTS (SELECT 1 FROM estudiantes e2 WHERE e2.representante_id = r.id AND e2.grado = ?)"
            params.append(grado)
        if seccion:
            query += " AND EXISTS (SELECT 1 FROM estudiantes e2 WHERE e2.representante_id = r.id AND e2.seccion = ?)"
            params.append(seccion)
        if turno:
            query += " AND EXISTS (SELECT 1 FROM estudiantes e2 WHERE e2.representante_id = r.id AND e2.turno = ?)"
            params.append(turno)
    query += " GROUP BY r.id ORDER BY r.apellidos"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)

# -----------------------------
# Estadísticas (por sexo, grado, turno)
# -----------------------------
@app.route('/api/stats')
@login_required()
def api_stats():
    conn = get_db()
    cur = conn.cursor()
    # por sexo
    cur.execute("SELECT sexo, COUNT(*) as total FROM estudiantes GROUP BY sexo")
    sexo = [dict(r) for r in cur.fetchall()]
    # por grado
    cur.execute("SELECT grado, COUNT(*) as total FROM estudiantes GROUP BY grado")
    grado = [dict(r) for r in cur.fetchall()]
    # por turno
    cur.execute("SELECT turno, COUNT(*) as total FROM estudiantes GROUP BY turno")
    turno = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify({"sexo": sexo, "grado": grado, "turno": turno})


# -----------------------------
# PERFIL DEL ADMIN / SECRETARIA / DIRECCIÓN
# -----------------------------
@app.route('/perfil')
@login_required()
def perfil():
    # Datos del usuario actual
    usuario = session.get('usuario')
    rol = session.get('role')

    # Datos del colegio (puedes modificar los valores)
    colegio = {
        "nombre": "E.B.E. POLICARPO FARRERA",
        "direccion": "Charallave",
        "directora": "Lcda. ",
        "turnos": "Mañana / Tarde",
        "telefono": "(000) 000-0000"
    }

    return render_template('perfil.html',
                           usuario=usuario,
                           rol=rol,
                           colegio=colegio)


# -----------------------------
# Run
# -----------------------------
if __name__ == '__main__':
    crear_base()
    app.run(host='0.0.0.0', port=5000, debug=True)