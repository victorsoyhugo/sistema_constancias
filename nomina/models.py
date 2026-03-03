from django.db import models
from simple_history.models import HistoricalRecords
import uuid
from django.db import models
from django import forms


class Cargo(models.Model):
    cargo = models.CharField(max_length=150)

    def __str__(self):
        return self.cargo


class Condicion(models.Model):
    condicion = models.CharField(max_length=100)

    def __str__(self):
        return self.condicion


class EscalaSalarial(models.Model):
    nivel = models.CharField(max_length=50)
    sueldo_base = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.nivel} - {self.sueldo_base}"


class Empleado(models.Model):
    cargo = models.ForeignKey(Cargo, on_delete=models.SET_NULL, null=True, related_name="empleados")
    condicion = models.ForeignKey(Condicion, on_delete=models.SET_NULL, null=True, related_name="empleados")
    escala_salarial = models.ForeignKey(EscalaSalarial, on_delete=models.SET_NULL, null=True, related_name="empleados")

    cedula = models.IntegerField(unique=True)
    nombres_y_apellidos = models.CharField(max_length=255)
    unidad_de_adscripcion_y_o_direccion = models.CharField(max_length=200)
    estado_o_ubicacion = models.CharField(max_length=100)
    codigo_del_cargo = models.CharField(max_length=50, null=True)
    fecha_de_ingreso = models.DateField()
    grado_de_instruccion = models.CharField(max_length=100)
    anos_previos = models.IntegerField(default=0)
    anos_en_fundabit = models.IntegerField(default=0)
    total_anos_de_servicios = models.IntegerField(default=0)
    numero_de_hijos = models.IntegerField(default=0)
    discapacitado = models.BooleanField(default=False)
    especialidad = models.CharField(max_length=100, blank=True, null=True)
    sexo = models.CharField(max_length=20)
    fecha_de_nacimiento = models.DateField()

    # ✅ Histórico de cambios
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.nombres_y_apellidos} ({self.cedula})"


class DatosBancarios(models.Model):
    empleado = models.OneToOneField(Empleado, on_delete=models.CASCADE, related_name="datos_bancarios")
    banco = models.CharField(max_length=100)
    numero_de_cuenta = models.BigIntegerField()

    def __str__(self):
        return f"{self.banco} - {self.numero_de_cuenta}"


class Quincena(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name="quincenas")

    periodo = models.IntegerField()
    mes = models.IntegerField()
    ano = models.IntegerField()
    fecha = models.DateField()
    dias_laborados = models.IntegerField(default=0)
    horas_extras_quincena = models.DecimalField(max_digits=100, decimal_places=3, default=0)
    total_retroactivo = models.DecimalField(max_digits=100, decimal_places=3, default=0)
    total_asignacion_primera_quincena = models.DecimalField(max_digits=100, decimal_places=3, default=0)
    total_asignacion_segunda_quincena = models.DecimalField(max_digits=100, decimal_places=3, default=0)
    total_de_asignacion_quincenal_todos_los_conceptos = models.DecimalField(max_digits=100, decimal_places=3, default=0)
    total_mensual = models.DecimalField(max_digits=100, decimal_places=3, default=0)
    total_asignacion_mensual_todos_los_conceptos = models.DecimalField(max_digits=100, decimal_places=3, default=0)
    total_deducciones = models.DecimalField(max_digits=100, decimal_places=3, default=0)
    total_a_cancelar = models.DecimalField(max_digits=100, decimal_places=3, default=0)
    nota = models.TextField(blank=True, null=True)
    bono_alimenticio = models.DecimalField(max_digits=100, decimal_places=3, blank=True, null=True)
    
    is_deleted = models.BooleanField(default=False)
    pending_delete = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Quincena {self.periodo}/{self.mes}/{self.ano} - {self.empleado}"


class AsignacionesMensuales(models.Model):
    quincena = models.OneToOneField(Quincena, on_delete=models.CASCADE, related_name="asignaciones_mensuales")
    sueldo_base_mensual = models.DecimalField(max_digits=10, decimal_places=3)
    prima_de_antiguedad = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    prima_de_profesionalizacion = models.DecimalField(max_digits=10, decimal_places=3)
    prima_por_hijos = models.DecimalField(max_digits=10, decimal_places=3)
    contribucion_para_trabajadoras_y_trabajadores_con_discapacidad = models.DecimalField(max_digits=10, decimal_places=3)
    horas_extras = models.DecimalField(max_digits=10, decimal_places=3)
    complemento_del_salario = models.DecimalField(max_digits=10, decimal_places=3)
    becas_para_hijos = models.DecimalField(max_digits=10, decimal_places=3)
    prima_asistencial_y_del_hogar = models.DecimalField(max_digits=10, decimal_places=3)
    prima_trabajadores_adm_y_obr = models.DecimalField(max_digits=10, decimal_places=3)
    encargaduria = models.DecimalField(max_digits=10, decimal_places=3)


class AsignacionesQuincenales(models.Model):
    quincena = models.OneToOneField(Quincena, on_delete=models.CASCADE, related_name="asignaciones_quincenales")
    sueldo_base_quincenal = models.DecimalField(max_digits=100, decimal_places=3)
    prima_de_antiguedad_quincenal = models.DecimalField(max_digits=100, decimal_places=3)
    prima_de_profesionalizacion_quincenal = models.DecimalField(max_digits=100, decimal_places=3)
    prima_por_hijos_quincenal = models.DecimalField(max_digits=100, decimal_places=3)
    contribucion_para_trabajadoras_y_trabajadores_con_discapacidad_quincenal = models.DecimalField(max_digits=100, decimal_places=3)
    complemento_del_salario_quincenal = models.DecimalField(max_digits=100, decimal_places=3)
    becas_para_hijos_quincenal = models.DecimalField(max_digits=100, decimal_places=3)
    prima_asistencial_y_del_hogar_quincenal = models.DecimalField(max_digits=100, decimal_places=3)
    prima_trabajadores_adm_y_obr_quincenal = models.DecimalField(max_digits=100, decimal_places=3)
    encargaduria_quincenal = models.DecimalField(max_digits=100, decimal_places=3)
    diferencia_por_comisiones_de_servicios = models.DecimalField(max_digits=100, decimal_places=3)
    retroactivo_sueldo_base = models.DecimalField(max_digits=100, decimal_places=3)
    retroactivo_prima_de_antiguedad = models.DecimalField(max_digits=100, decimal_places=3)
    retroactivo_prima_de_profesionalizacion = models.DecimalField(max_digits=100, decimal_places=3)
    retroactivo_prima_por_hijos = models.DecimalField(max_digits=100, decimal_places=3)
    retroactivo_contribucion_para_trabajadoras_y_trabajadores_con_discapacidad = models.DecimalField(max_digits=100, decimal_places=3)
    retroactivo_horas_extras = models.DecimalField(max_digits=100, decimal_places=3)
    retroactivo_becas_para_hijos = models.DecimalField(max_digits=100, decimal_places=3)
    retroactivo_prima_asistencial_y_del_hogar = models.DecimalField(max_digits=100, decimal_places=3)
    retroactivo_prima_trabajadores_adm_y_obr = models.DecimalField(max_digits=100, decimal_places=3)
    retroactivo_encargaduria = models.DecimalField(max_digits=100, decimal_places=3)


class Deducciones(models.Model):
    quincena = models.OneToOneField(Quincena, on_delete=models.CASCADE, related_name="deducciones")
    retencion_por_caja_de_ahorro = models.DecimalField(max_digits=100, decimal_places=3)
    retencion_por_sso = models.DecimalField(max_digits=100, decimal_places=3)
    retencion_rpe = models.DecimalField(max_digits=100, decimal_places=3)
    retencion_por_faov = models.DecimalField(max_digits=100, decimal_places=3)
    retencion_por_fejp = models.DecimalField(max_digits=100, decimal_places=3)
    sinaep = models.DecimalField(max_digits=100, decimal_places=3)
    ipasme = models.DecimalField(max_digits=100, decimal_places=3)
    descuento_por_pago_indebido = models.DecimalField(max_digits=100, decimal_places=3)


class AsignacionAdicionalQuincenal(models.Model):
    quincena = models.ForeignKey(
        Quincena,
        on_delete=models.CASCADE,
        related_name="asignaciones_quincenales_adicionales",
        null=True
    )
    nombre = models.CharField(max_length=100)
    valor = models.DecimalField(max_digits=100, decimal_places=3)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

class AsignacionAdicionalMensual(models.Model):
    quincena = models.ForeignKey(
        Quincena,
        on_delete=models.CASCADE,
        related_name="asignaciones_mensuales_adicionales",
        null=True
    )
    nombre = models.CharField(max_length=100)
    valor = models.DecimalField(max_digits=100, decimal_places=3)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

class DeduccionAdicional(models.Model):
    quincena = models.ForeignKey(
        Quincena,
        on_delete=models.CASCADE,
        related_name="deducciones_adicionales",
        null=True
    )
    nombre = models.CharField(max_length=100)
    valor = models.DecimalField(max_digits=10, decimal_places=3)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

class CodigoPDF(models.Model):
    TIPO_CHOICES = (('constancia','Constancia'), ('recibo','Recibo'),)
    codigo = models.CharField(max_length=64, unique=True, db_index=True)
    quincena = models.ForeignKey('Quincena', on_delete=models.CASCADE, related_name='codigos_pdf')
    empleado = models.ForeignKey('Empleado', on_delete=models.CASCADE, related_name='codigos_pdf')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    creado_en = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def generar_codigo():
        return uuid.uuid4().hex


class AsignacionesMensualesForm(forms.ModelForm):
    class Meta:
        model = AsignacionesMensuales
        exclude = ("quincena",)
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            field.widget.attrs.update({
                "class": "form-control",
                "step": "0.001",
                "min": "0"
            })
            
class AsignacionesQuincenalesForm(forms.ModelForm):
    class Meta:
        model = AsignacionesQuincenales
        exclude = ("quincena",)
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            field.widget.attrs.update({
                "class": "form-control",
                "step": "0.001",
                "min": "0"
            })

class DeduccionesForm(forms.ModelForm):
    class Meta:
        model = Deducciones
        exclude = ("quincena",)
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            field.widget.attrs.update({
                "class": "form-control",
                "step": "0.001",
                "min": "0"
            })
            
class AsignacionAdicionalQuincenalForm(forms.ModelForm):
    class Meta:
        model = AsignacionAdicionalQuincenal
        fields = ("valor",)

class AsignacionAdicionalMensualForm(forms.ModelForm):
    class Meta:
        model = AsignacionAdicionalMensual
        fields = ("valor",)

class DeduccionAdicionalForm(forms.ModelForm):
    class Meta:
        model = DeduccionAdicional
        fields = ("valor",)