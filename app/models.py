# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


# AÑO ESCOLAR
class AnioEscolar(models.Model):
    id_anio_escolar = models.AutoField(primary_key=True)
    anio_escolar = models.CharField(unique=True, max_length=20)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    activo = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'anio_escolar'


# ESTUDIANTES
class Estudiante(models.Model):
    id_estudiante = models.AutoField(primary_key=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    cedula = models.CharField(unique=True, max_length=20, blank=True, null=True)
    fecha_nacimiento = models.DateField()
    sexo = models.CharField(max_length=1)
    lugar_nacimiento = models.CharField(max_length=150, blank=True, null=True)
    fecha_registro = models.DateTimeField(blank=True, null=True)
    talla_camisa = models.CharField(max_length=10, blank=True, null=True)
    talla_pantalon = models.CharField(max_length=10, blank=True, null=True)
    talla_zapato = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'estudiante'


# GRADOS
class Grado(models.Model):
    id_grado = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)
    orden = models.IntegerField()

    class Meta:
        managed = True
        db_table = 'grado'


# MATRÍCULAS
class Matricula(models.Model):
    id_matricula = models.AutoField(primary_key=True)
    id_estudiante = models.ForeignKey(Estudiante, models.DO_NOTHING, db_column='id_estudiante')
    id_representante = models.ForeignKey('Representante', models.DO_NOTHING, db_column='id_representante')
    id_grado = models.ForeignKey(Grado, models.DO_NOTHING, db_column='id_grado')
    id_seccion = models.ForeignKey('Seccion', models.DO_NOTHING, db_column='id_seccion')
    id_turno = models.ForeignKey('Turno', models.DO_NOTHING, db_column='id_turno')
    id_anio_escolar = models.ForeignKey(AnioEscolar, models.DO_NOTHING, db_column='id_anio_escolar')
    anio_ingreso = models.IntegerField()
    fecha_matricula = models.DateField()
    estado = models.CharField(max_length=20)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'matricula'


# REPRESENTANTES
class Representante(models.Model):
    id_representante = models.AutoField(primary_key=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    cedula = models.CharField(unique=True, max_length=20)
    telefono = models.CharField(max_length=20)
    direccion = models.TextField(blank=True, null=True)
    correo = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'representante'


# SECCIÓN
class Seccion(models.Model):
    id_seccion = models.AutoField(primary_key=True)
    letra = models.CharField(max_length=10)

    class Meta:
        managed = True
        db_table = 'seccion'

# TURNO
class Turno(models.Model):
    id_turno = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)

    class Meta:
        managed = True
        db_table = 'turno'
