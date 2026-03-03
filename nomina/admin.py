from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import (
    Cargo,
    Condicion,
    EscalaSalarial,
    Empleado,
    DatosBancarios,
    Quincena,
    AsignacionesMensuales,
    AsignacionesQuincenales,
    Deducciones,
    AsignacionAdicionalQuincenal,
    AsignacionAdicionalMensual,
    DeduccionAdicional,
    CodigoPDF,
)


# -----------------------------
# MODELOS BÁSICOS
# -----------------------------
@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ("id", "cargo")
    search_fields = ("cargo",)
    ordering = ("cargo",)


@admin.register(Condicion)
class CondicionAdmin(admin.ModelAdmin):
    list_display = ("id", "condicion")
    search_fields = ("condicion",)
    ordering = ("condicion",)


@admin.register(EscalaSalarial)
class EscalaSalarialAdmin(admin.ModelAdmin):
    list_display = ("id", "nivel", "sueldo_base")
    search_fields = ("nivel",)
    ordering = ("nivel",)


# -----------------------------
# EMPLEADO (con historial)
# -----------------------------
@admin.register(Empleado)
class EmpleadoAdmin(SimpleHistoryAdmin):  # ✅ usa django-simple-history
    list_display = (
        "id",
        "nombres_y_apellidos",
        "cedula",
        "cargo",
        "condicion",
        "unidad_de_adscripcion_y_o_direccion",
        "estado_o_ubicacion",
        "fecha_de_ingreso",
        "escala_salarial",
    )
    list_filter = (
        "cargo",
        "condicion",
        "estado_o_ubicacion",
        "escala_salarial",
        "sexo",
    )
    search_fields = ("nombres_y_apellidos", "cedula", "unidad_de_adscripcion_y_o_direccion")
    ordering = ("nombres_y_apellidos",)
    history_list_display = ["cedula", "nombres_y_apellidos"]  # columnas visibles en historial


@admin.register(DatosBancarios)
class DatosBancariosAdmin(admin.ModelAdmin):
    list_display = ("id", "empleado", "banco", "numero_de_cuenta")
    search_fields = ("empleado__nombres_y_apellidos", "banco", "numero_de_cuenta")
    ordering = ("empleado__nombres_y_apellidos",)


# -----------------------------
# QUINCENAS Y RELACIONADOS
# -----------------------------
class AsignacionesMensualesInline(admin.StackedInline):
    model = AsignacionesMensuales
    extra = 0


class AsignacionesQuincenalesInline(admin.StackedInline):
    model = AsignacionesQuincenales
    extra = 0


class DeduccionesInline(admin.StackedInline):
    model = Deducciones
    extra = 0


@admin.register(Quincena)
class QuincenaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "empleado",
        "periodo",
        "mes",
        "ano",
        "fecha",
        "total_a_cancelar",
        "is_deleted"
    )
    list_filter = ("mes", "ano")
    search_fields = ("empleado__nombres_y_apellidos", "empleado__cedula")
    ordering = ("-ano", "-mes", "periodo")
    inlines = [AsignacionesMensualesInline, AsignacionesQuincenalesInline, DeduccionesInline]


# -----------------------------
# ASIGNACIONES Y DEDUCCIONES
# -----------------------------
@admin.register(AsignacionesMensuales)
class AsignacionesMensualesAdmin(admin.ModelAdmin):
    list_display = ("id", "quincena", "sueldo_base_mensual", "prima_de_antiguedad")
    search_fields = ("quincena__empleado__nombres_y_apellidos",)
    ordering = ("-id",)


@admin.register(AsignacionesQuincenales)
class AsignacionesQuincenalesAdmin(admin.ModelAdmin):
    list_display = ("id", "quincena", "sueldo_base_quincenal", "prima_de_antiguedad_quincenal")
    search_fields = ("quincena__empleado__nombres_y_apellidos",)
    ordering = ("-id",)


@admin.register(Deducciones)
class DeduccionesAdmin(admin.ModelAdmin):
    list_display = ("id", "quincena", "retencion_por_sso", "total_deducciones")
    search_fields = ("quincena__empleado__nombres_y_apellidos",)
    ordering = ("-id",)

    def total_deducciones(self, obj):
        return (
            obj.retencion_por_caja_de_ahorro
            + obj.retencion_por_sso
            + obj.retencion_rpe
            + obj.retencion_por_faov
            + obj.retencion_por_fejp
            + obj.sinaep
            + obj.ipasme
            + obj.descuento_por_pago_indebido
        )
    total_deducciones.short_description = "Total Deducciones"


# -----------------------------
# ADICIONALES
# -----------------------------
@admin.register(AsignacionAdicionalMensual)
class AsignacionAdicionalAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "valor")
    search_fields = ("nombre",)
    ordering = ("nombre",)
    

@admin.register(AsignacionAdicionalQuincenal)
class AsignacionAdicionalAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "valor")
    search_fields = ("nombre",)
    ordering = ("nombre",)


@admin.register(DeduccionAdicional)
class DeduccionAdicionalAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "valor")
    search_fields = ("nombre",)
    ordering = ("nombre",)

@admin.register(CodigoPDF)
class CodigoPDFAdmin(admin.ModelAdmin):
    list_display = ("codigo", "quincena", "empleado", "tipo", "creado_en")
    search_fields = ("empleado",)
    ordering = ("creado_en",)
