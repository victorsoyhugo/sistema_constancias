import hashlib
from decimal import Decimal
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from django.db import models
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.template.loader import render_to_string
from weasyprint import HTML, CSS
from io import BytesIO
from django.core.management import call_command
from django.core.files.storage import FileSystemStorage
from django.forms import inlineformset_factory
from .forms import CargaNominaForm
import json
import locale

from .models import (
    Empleado, DatosBancarios, Quincena,
    AsignacionesMensuales, AsignacionesQuincenales,
    Deducciones, CodigoPDF, AsignacionAdicionalMensual, AsignacionAdicionalQuincenal,
    DeduccionAdicional, AsignacionesMensualesForm, AsignacionesQuincenalesForm, DeduccionesForm,
    AsignacionAdicionalMensualForm, AsignacionAdicionalQuincenalForm, DeduccionAdicionalForm
)
from .forms import CedulaCuentaForm, CodigoVerificacionForm, LoginForm
from django.templatetags.static import static
from django.conf import settings
import os

import uuid

def generar_codigo_pdf(empleado, tipo, quincena):
    """
    Genera un código PDF único por cada PDF generado.
    """
    # Determinar prefijo según tipo
    if tipo.lower() == "constancia":
        prefijo = "C"
    else:  # recibo
        prefijo = "R"
    
    # Generar ID único corto
    unique_id = str(uuid.uuid4())[:8].upper()
    
    # Crear código: PREFIJO-IDUNICO
    codigo_completo = f"{prefijo}-{unique_id}"
    
    # Crear nuevo registro en la base de datos
    codigo_obj = CodigoPDF.objects.create(
        empleado=empleado,
        quincena=quincena,
        tipo=tipo,
        codigo=codigo_completo
    )
    
    return codigo_obj.codigo

# --------------------------
# Página principal
# --------------------------
def home(request):
    # Inicializar formularios siempre
    form_verificar = CodigoVerificacionForm()
    form_cedula = CedulaCuentaForm()
    resultado = None
    
    # Determinar qué formulario se envió
    if request.method == "POST":
        if "verificar_codigo" in request.POST:
            # Solo validar formulario de verificación
            form_verificar = CodigoVerificacionForm(request.POST)
            form_cedula = CedulaCuentaForm()  # Formulario vacío sin errores
            
            if form_verificar.is_valid():
                codigo = form_verificar.cleaned_data["codigo"]
                try:
                    registro = CodigoPDF.objects.get(codigo=codigo)
                    quincena = registro.quincena
                    
                    # Determinar formato por prefijo del código
                    if codigo.startswith("C"):
                        # Constancia: solo mes y año
                        meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
                        mes_nombre = meses[quincena.mes - 1]
                        periodo_texto = f"{mes_nombre} de {quincena.ano}"
                    elif codigo.startswith("R"):
                        # Recibo: rango completo
                        if quincena.periodo == 1:
                            periodo_texto = f"1/{quincena.mes}/{quincena.ano} al 15/{quincena.mes}/{quincena.ano}"
                        else:  # periodo 2
                            # Calcular último día
                            if quincena.mes == 2:
                                es_bisiesto = (quincena.ano % 4 == 0 and quincena.ano % 100 != 0) or (quincena.ano % 400 == 0)
                                ultimo_dia = 29 if es_bisiesto else 28
                            elif quincena.mes in [1, 3, 5, 7, 8, 10, 12]:
                                ultimo_dia = 31
                            else:
                                ultimo_dia = 30
                            periodo_texto = f"16/{quincena.mes}/{quincena.ano} al {ultimo_dia}/{quincena.mes}/{quincena.ano}"
                    else:
                        # Código antiguo
                        periodo_texto = f"{quincena.periodo}Q - {quincena.mes}/{quincena.ano}"
                    
                    resultado = {
                        "ok": True,
                        "mensaje": "✅ Código válido",
                        "empleado": registro.empleado.nombres_y_apellidos,
                        "periodo": periodo_texto,
                        "tipo": registro.tipo,
                        "expedicion": registro.creado_en,
                    }
                except CodigoPDF.DoesNotExist:
                    resultado = {"ok": False, "mensaje": "❌ El código ingresado no es válido"}
        
        elif "consultar_cedula" in request.POST:
            # Solo validar formulario de cédula
            form_cedula = CedulaCuentaForm(request.POST)
            form_verificar = CodigoVerificacionForm()  # Formulario vacío sin errores
            
            if form_cedula.is_valid():
                cedula = form_cedula.cleaned_data["cedula"]
                ultimos4 = form_cedula.cleaned_data["ultimos4"]
                try:
                    empleado = Empleado.objects.get(cedula=cedula)
                    if str(empleado.datos_bancarios.numero_de_cuenta).endswith(str(ultimos4)):
                        request.session["empleado_id"] = empleado.id
                        return redirect("nomina:bienvenida")
                    else:
                        messages.error(request, "Número de cuenta incorrecto.")
                except Empleado.DoesNotExist:
                    messages.error(request, "Empleado no encontrado.")
    
    return render(request, "home.html", {
        "form_verificar": form_verificar,
        "form_cedula": form_cedula,
        "resultado": resultado,
    })
    
# --------------------------
# Bienvenida y opciones
# --------------------------
def bienvenida(request):
    empleado_id = request.session.get("empleado_id")
    if not empleado_id:
        return redirect("nomina:home")
    empleado = get_object_or_404(Empleado, id=empleado_id)

    quincenas = Quincena.objects.filter(empleado=empleado)
    tiene_periodo2 = quincenas.filter(periodo=2).exists()

    return render(request, "bienvenida.html", {
        "empleado": empleado,
        "tiene_periodo2": tiene_periodo2,
    })

# --------------------------
# Funcion Auxiliar
# --------------------------

def formato_sin_redondear(valor):
    """Formatea sin redondear, solo trunca a 2 decimales"""
    from decimal import Decimal, ROUND_DOWN
    try:
        d = Decimal(str(valor))
        return format(d.quantize(Decimal('0.00'), rounding=ROUND_DOWN), 'f')
    except:
        return "0.00"

# --------------------------
# Generar Constancia PDF
# --------------------------
def generar_constancia(request):
    empleado_id = request.session.get("empleado_id")
    if not empleado_id:
        return redirect("nomina:home")

    empleado = get_object_or_404(Empleado, id=empleado_id)

    if request.method == "POST":
        periodo = request.POST.get("periodo_seleccionado")
        if not periodo:
            return HttpResponse("Error: no se seleccionó periodo", status=400)

        try:
            mes, ano = map(int, periodo.split("-"))
        except ValueError:
            return HttpResponse("Error en el formato del periodo", status=400)

        # Obtener quincena; lanzar 404 si no existe
        quincena = get_object_or_404(
            Quincena,
            empleado=empleado,
            periodo=2,
            mes=mes,
            ano=ano
        )

        # Obtener asignación mensual (si no existe, informar)
        try:
            asignacion = AsignacionesMensuales.objects.get(quincena=quincena)
        except AsignacionesMensuales.DoesNotExist:
            return HttpResponse("Error: Asignación mensual no encontrada para la quincena.", status=500)

        # ====== OBTENER SOLO LOS VALORES NO CERO DE AsignacionesMensuales ======
        NOMBRES_FORMATO = {
            "sueldo_base_mensual": "SUELDO BASE MENSUAL",
            "prima_de_antiguedad": "PRIMA DE ANTIGÜEDAD",
            "prima_de_profesionalizacion": "PRIMA DE PROFESIONALIZACION",
            "prima_por_hijos": "PRIMA POR HIJOS",
            "contribucion_para_trabajadoras_y_trabajadores_con_discapacidad": 
                "CONTRIBUCION PARA TRABAJADORAS Y TRABAJADORES CON DISCAPACIDAD",
            "horas_extras": "HORAS EXTRAS",
            "complemento_del_salario": "COMPLEMENTO DEL SALARIO",
            "becas_para_hijos": "BECAS PARA HIJOS",
            "prima_asistencial_y_del_hogar": "PRIMA ASISTENCIAL Y DEL HOGAR",
            "prima_trabajadores_adm_y_obr": "PRIMA TRABAJADORES ADM Y OBR",
            "encargaduria": "ENCARGADURIA",
            "total_mensual": "TOTAL MENSUAL",
            "total_asignacion_mensual_todos_los_conceptos": 
                "TOTAL ASIGNACION MENSUAL (TODOS LOS CONCEPTOS)",
        }

        
        CAMPOS_FIJOS = [
            "sueldo_base_mensual",
            "prima_de_profesionalizacion",
            "prima_de_antiguedad",
            "prima_asistencial_y_del_hogar",
            "prima_por_hijos",
            "prima_trabajadores_adm_y_obr",
        ]

        campos_validos = []

        for field in AsignacionesMensuales._meta.fields:
            if field.name in CAMPOS_FIJOS:
                continue  # ← EVITA LAS 6 FILAS FIJAS

            valor = getattr(asignacion, field.name)

            if isinstance(valor, Decimal) and valor != 0:
                campos_validos.append({
                    "nombre": NOMBRES_FORMATO.get(field.name, field.name.replace("_", " ").upper()),
                    "campo": field.name,
                    "valor": valor,
                })

        # Obtener adicionales (QuerySet, puede estar vacío)
        adicionales_qs = AsignacionAdicionalMensual.objects.filter(quincena=quincena)
        adicionales = list(adicionales_qs)  # lista para len() segura

        # ====== CÁLCULO DE FILAS ======
        filas_dinamicas = len(campos_validos)
        filas_base = 6
        filas_adicionales = len(adicionales)
        fila_total = 1
        total_filas = filas_base + filas_adicionales + filas_dinamicas + fila_total

        # ====== CÁLCULO REAL DE ALTURA ======
        # Valores base (ajústalos si tu plantilla usa tamaños distintos)
        PAGE_HEIGHT = 792  # carta a 96dpi (valor de referencia)
        BANNER_SUP = 120
        TEXTO_INICIAL = 150
        FOOTER = 200
        MARGENES = 30

        espacio_disponible = PAGE_HEIGHT - (BANNER_SUP + TEXTO_INICIAL + FOOTER + MARGENES)

        # ----- Ajuste solicitado: encoger la tabla unos pixeles para dejar espacio arriba/abajo -----
        espacio_ajustado = espacio_disponible - 60 # <--- modifica este valor si quieres más/menos espacio
        if espacio_ajustado < 100:
            espacio_ajustado = 100  # protección minima

        # Altura por fila (enteros)
        altura_fila = int(espacio_ajustado / total_filas)

        # Límites razonables para evitar filas gigantes o minúsculas
        if altura_fila > 45:
            altura_fila = 45
        elif altura_fila < 12:
            altura_fila = 12

        # ====== CSS DINÁMICO INYECTADO ======
        estilos_tabla = f"""
            .remuneracion-table td {{
                height: {altura_fila}px !important;
                padding: 2px 4px !important;
                line-height: {max(10, altura_fila - 4)}px !important;
                vertical-align: middle !important;
            }}
            .remuneracion-table {{
                max-height: {espacio_ajustado}px !important;
            }}
        """

        # ====== CÓDIGO PDF, FECHA ======
        codigo = generar_codigo_pdf(empleado, "Constancia", quincena)
        fecha_generacion = timezone.now().strftime("%d/%m/%Y %H:%M")
        
        # Fecha formateada
        locale.setlocale(locale.LC_TIME, 'es_VE.UTF-8')
        now = timezone.now()
        fecha_generacion_formateada = f"{now.day} días del mes de {now.strftime('%B').capitalize()} del año {now.year}"

        # ====== RENDERIZAR HTML ======
        context = {
            "empleado": empleado,
            "asignacion": asignacion,
            "quincena": quincena,
            "codigo_pdf": codigo,
            "fecha_generacion": fecha_generacion,
            "adicionales": adicionales,
            "clase_tabla": "remuneracion-table",
            "estilos_tabla": estilos_tabla,
            "campos_validos": campos_validos,
            "fecha_generacion_formateada": fecha_generacion_formateada
        }

        html = render_to_string("pdf/constancia_template.html", context)

        # ====== RUTA CSS STATIC (asegúrate de que exista) ======
        css_path = os.path.join(settings.BASE_DIR, "nomina", "static", "css", "style.css")
        # Si falla la ruta, fallback a None y dejar que WeasyPrint use estilos embebidos
        stylesheets = []
        if os.path.exists(css_path):
            stylesheets = [CSS(filename=css_path)]

        # ====== GENERAR PDF ======
        try:
            pdf = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf(
                stylesheets=stylesheets
            )
        except Exception as e:
            # Reportar error legible en caso de fallo en la generación PDF
            return HttpResponse(f"Error generando PDF: {e}", status=500)

        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="constancia_{codigo}.pdf"'
        return response

    # GET: render selector de período
    # Obtener todas las quincenas del empleado (periodo 2)
    todas_quincenas = Quincena.objects.filter(
        empleado=empleado, 
        periodo=2,
        is_deleted=False
    ).order_by('-ano', '-mes')

    # Tomar solo las últimas 3 quincenas
    quincenas_limitadas = todas_quincenas[:3]

    return render(request, "seleccionar_periodo.html", {
        "quincenas": quincenas_limitadas,
        "tipo": "constancia",
    })

# --------------------------
# Generar Recibo PDF
# --------------------------

def generar_recibo(request):
    empleado_id = request.session.get("empleado_id")
    if not empleado_id:
        return redirect("nomina:home")
    empleado = get_object_or_404(Empleado, id=empleado_id)

    if request.method == "POST":
        quincena_id = int(request.POST["quincena_id"])
        quincena = get_object_or_404(Quincena, id=quincena_id, empleado=empleado)

        asignacion = AsignacionesQuincenales.objects.get(quincena=quincena)
        deducciones = Deducciones.objects.get(quincena=quincena)
        
        # OBTENER ASIGNACIONES ADICIONALES QUINCENALES
        adicionales_quincenales = AsignacionAdicionalQuincenal.objects.filter(quincena=quincena)
        
        # OBTENER DEDUCCIONES ADICIONALES (si existen)
        deducciones_adicionales = DeduccionAdicional.objects.filter(quincena=quincena)

        # ================================
        # MAPA → nombre legible en PDF
        # ================================
        NOMBRES_ASIGNACIONES = {
            "sueldo_base_quincenal": "SUELDO BASICO",
            "prima_de_profesionalizacion_quincenal": "PRIMA DE PROFESIONALIZACION",
            "prima_por_hijos_quincenal": "PRIMA POR HIJO",
            "prima_de_antiguedad_quincenal": "PRIMA DE ANTIGÜEDAD",
            "contribucion_para_trabajadoras_y_trabajadores_con_discapacidad_quincenal":
                "CONTRIBUCION PARA TRABAJADORAS Y TRABAJADORES CON DISCAPACIDAD",
            "becas_para_hijos_quincenal": "BECA POR HIJO",
            "prima_asistencial_y_del_hogar_quincenal": "PRIMA ASISTENCIAL Y DEL HOGAR",
            "prima_trabajadores_adm_y_obr_quincenal": "PRIMA TRABAJADORES ADM Y OBR",
            "complemento_del_salario_quincenal": "HORAS EXTRAS",
            "diferencia_por_comisiones_de_servicios": "COMISIONES DE SERVICIO",
            "encargaduria_quincenal": "ENCARGADURIA",
            # retroactivos
            "retroactivo_sueldo_base": "RETROACTIVO SUELDO BASE",
            "retroactivo_prima_de_antiguedad": "RETROACTIVO ANTIGÜEDAD",
            "retroactivo_prima_de_profesionalizacion": "RETROACTIVO PROFESIONALIZACION",
            "retroactivo_prima_por_hijos": "RETROACTIVO POR HIJO",
            "retroactivo_contribucion_para_trabajadoras_y_trabajadores_con_discapacidad":
                "RETROACTIVO DISCAPACIDAD",
            "retroactivo_horas_extras": "RETROACTIVO HORAS EXTRAS",
            "retroactivo_becas_para_hijos": "RETROACTIVO BECA POR HIJO",
            "retroactivo_prima_asistencial_y_del_hogar": "RETROACTIVO ASISTENCIAL",
            "retroactivo_prima_trabajadores_adm_y_obr": "RETROACTIVO ADM/OBR",
            "retroactivo_encargaduria": "RETROACTIVO ENCARGADURIA",
        }

        NOMBRES_DEDUCCIONES = {
            "ipasme": "IPASME",
            "sinaep": "SINAEP",
            "retencion_por_caja_de_ahorro": "CAJA DE AHORRO",
            "retencion_por_sso": "SSO",
            "retencion_rpe": "PIDE",
            "retencion_por_faov": "FAOV",
            "retencion_por_fejp": "FONDO ESP. DE JUB. Y PENSIONES",
            "descuento_por_pago_indebido": "DESCUENTO PAGO INDEBIDO",
        }
        
        # ================================
        # 1. ASIGNACIONES REGULARES
        # ================================
        asignaciones_regulares = []
        for field in AsignacionesQuincenales._meta.get_fields():
            if field.name in ["id", "quincena"]:
                continue

            valor = getattr(asignacion, field.name)

            # ⛔ OCULTAR SOLO ESTOS SI ESTÁN EN CERO:
            if (
                field.name.startswith("retroactivo_") or
                field.name == "encargaduria_quincenal" or
                field.name == "diferencia_por_comisiones_de_servicios"
            ):
                if valor == 0:
                    continue  # se omite solo este grupo
                # si tienen valor, pasan normal

            # ✔ TODOS LOS DEMÁS CAMPOS SIEMPRE SE MUESTRAN
            nombre_legible = NOMBRES_ASIGNACIONES.get(
                field.name,
                field.name.replace("_", " ").upper()
            )

            asignaciones_regulares.append({
                "nombre": nombre_legible,
                "asignacion": formato_sin_redondear(valor),
                "apagar": "",
                "tipo": "asignacion_regular"
            })

        # ================================
        # 2. ASIGNACIONES ADICIONALES
        # ================================
        asignaciones_adicionales = []
        for adicional in adicionales_quincenales:
            asignaciones_adicionales.append({
                "nombre": adicional.nombre,
                "asignacion": formato_sin_redondear(adicional.valor),
                "apagar": "",
                "tipo": "asignacion_adicional"
            })

        # ================================
        # 3. DEDUCCIONES REGULARES
        # ================================
        deducciones_regulares = []
        for field in Deducciones._meta.get_fields():
            if field.name in ["id", "quincena"]:
                continue

            valor = getattr(deducciones, field.name)

            # --- Descuento por pago indebido solo si != 0
            if field.name == "descuento_por_pago_indebido" and valor == 0:
                continue

            nombre_legible = NOMBRES_DEDUCCIONES.get(
                field.name,
                field.name.replace("_", " ").upper()
            )

            deducciones_regulares.append({
                "nombre": nombre_legible,
                "deduccion": formato_sin_redondear(valor),
                "apagar": "",
                "tipo": "deduccion_regular"
            })

        # ================================
        # 4. DEDUCCIONES ADICIONALES
        # ================================
        deducciones_adicionales_lista = []
        for deduccion_adic in deducciones_adicionales:
            deducciones_adicionales_lista.append({
                "nombre": deduccion_adic.nombre,
                "deduccion": formato_sin_redondear(deduccion_adic.valor),
                "apagar": "",
                "tipo": "deduccion_adicional"
            })

        # ================================
        # COMBINAR TODO EN EL ORDEN CORRECTO
        # ================================
        conceptos = (
            asignaciones_regulares + 
            asignaciones_adicionales + 
            deducciones_regulares + 
            deducciones_adicionales_lista
        )

        # ================================
        # *** SISTEMA DE ALTURA DINÁMICA ***
        # ================================
        filas_dinamicas = len(conceptos)
        fila_total = 1
        total_filas = filas_dinamicas + fila_total

        PAGE_HEIGHT = 792
        BANNER_SUP = 120
        TEXTO_INICIAL = 150
        FOOTER = 200
        MARGENES = 30

        espacio_disponible = PAGE_HEIGHT - (BANNER_SUP + TEXTO_INICIAL + FOOTER + MARGENES)

        espacio_ajustado = espacio_disponible - 60
        if espacio_ajustado < 100:
            espacio_ajustado = 100

        altura_fila = int(espacio_ajustado / total_filas)

        altura_fila = int(altura_fila * 1.50)

        if altura_fila > 45:
            altura_fila = 45
        elif altura_fila < 12:
            altura_fila = 15

        estilos_tabla = f"""
            .remuneracion-table td {{
                height: {altura_fila}px !important;
                padding: 2px 4px !important;
                line-height: {max(10, altura_fila - 4)}px !important;
                vertical-align: middle !important;
            }}
            .remuneracion-table {{
                max-height: {espacio_ajustado}px !important;
            }}
        """

        # ================================
        # GENERAR PDF
        # ================================
        codigo = generar_codigo_pdf(empleado, "Recibo", quincena)
        fecha_generacion = timezone.now().strftime("%d/%m/%Y %H:%M")

        # ====== RUTA CSS STATIC ======
        css_path = os.path.join(settings.BASE_DIR, "nomina", "static", "css", "style.css")
        stylesheets = []
        if os.path.exists(css_path):
            stylesheets = [CSS(filename=css_path)]

        context = {
            "empleado": empleado,
            "asignacion": asignacion,
            "deducciones": deducciones,
            "quincena": quincena,
            "conceptos": conceptos,
            "asignaciones_regulares": asignaciones_regulares,
            "asignaciones_adicionales": asignaciones_adicionales,
            "deducciones_regulares": deducciones_regulares,
            "deducciones_adicionales": deducciones_adicionales_lista,
            "sueldo_basico_formateado": formato_sin_redondear(asignacion.sueldo_base_quincenal),

            # totales del modelo
            "total_asignaciones": formato_sin_redondear(quincena.total_de_asignacion_quincenal_todos_los_conceptos),
            "total_deducciones": formato_sin_redondear(quincena.total_deducciones),
            "total_pagar": formato_sin_redondear(quincena.total_a_cancelar),

            # estilos dinámicos para tabla
            "clase_tabla": "remuneracion-table",
            "estilos_tabla": estilos_tabla,

            "codigo_pdf": codigo,
            "fecha_generacion": fecha_generacion,
            'banner_superior_url': request.build_absolute_uri(static('img/banner-superior.png')),
            'banner_inferior_url': request.build_absolute_uri(static('img/banner-inferior.png')),
        }

        html = render_to_string("pdf/recibo_template.html", context)

        pdf = HTML(
            string=html,
            base_url=request.build_absolute_uri()
        ).write_pdf()
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="recibo_{codigo}.pdf"'
        return response

    todas_quincenas = Quincena.objects.filter(
        empleado=empleado, 
        is_deleted=False
    ).order_by('-ano', '-mes')

    # Tomar solo las últimas 3 quincenas
    quincenas_limitadas = todas_quincenas[:6]

    quincenas = Quincena.objects.filter(empleado=empleado, is_deleted=False)
    return render(request, "seleccionar_periodo.html", {
        "quincenas": quincenas_limitadas,
        "tipo": "recibo",
    })

# --------------------------
# Login de administrador
# --------------------------
def login_view(request):
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data["username"],
            password=form.cleaned_data["password"],
        )
        if user:
            login(request, user)
            return redirect("nomina:panel_admin")
        else:
            messages.error(request, "Credenciales inválidas.")
    return render(request, "login.html", {"form": form})

def logout_view(request):
    logout(request)
    return redirect("nomina:home")

# --------------------------
# Panel administrativo
# --------------------------
@login_required
def panel_admin(request):
    # Obtener combinaciones únicas de quincenas (portátil para SQLite)
    quincenas = (
        Quincena.objects
        .values("ano", "mes", "periodo")
        .distinct()
        .order_by("-ano", "-mes", "-periodo")
    )

    seleccion = request.GET.get("quincena")
    empleados = []
    texto_quincena = None

    if seleccion:
        periodo, mes, ano = map(int, seleccion.split("-"))
        empleados = (
            Quincena.objects
            .filter(periodo=periodo, mes=mes, ano=ano, is_deleted=False)
            .select_related("empleado")
            .order_by("empleado__nombres_y_apellidos")
        )
        
        # 🔥 Construimos el texto aquí
        MESES = [
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
        ]
        nombre_mes = MESES[mes - 1]

        texto_quincena = (
            f"{'1era' if periodo == 1 else '2da'} "
            f"Quincena de {nombre_mes} de {ano}"
        )

    return render(request, "panel_admin.html", {
        "quincenas": quincenas,
        "empleados": empleados,
        "seleccion": seleccion,
        "texto_quincena": texto_quincena,
    })

###################
# EDITAR QUINCENA #
###################

AsignacionMensualExtraFormSet = inlineformset_factory(
    Quincena,
    AsignacionAdicionalMensual,
    fields=("valor",),
    extra=0,
    can_delete=True
)

AsignacionQuincenalExtraFormSet = inlineformset_factory(
    Quincena,
    AsignacionAdicionalQuincenal,
    fields=("valor",),
    extra=0,
    can_delete=True
)

DeduccionExtraFormSet = inlineformset_factory(
    Quincena,
    DeduccionAdicional,
    fields=("valor",),
    extra=0,
    can_delete=True
)

@login_required
def editar_asignaciones(request, quincena_id, seccion):

    quincena = get_object_or_404(Quincena, id=quincena_id)

    if seccion == "asignacionesMensuales":
        instance = get_object_or_404(AsignacionesMensuales, quincena=quincena)
        form = AsignacionesMensualesForm(instance=instance)
        formset = AsignacionMensualExtraFormSet(instance=quincena)

    elif seccion == "asignacionesQuincenales":
        instance = get_object_or_404(AsignacionesQuincenales, quincena=quincena)
        form = AsignacionesQuincenalesForm(instance=instance)
        formset = AsignacionQuincenalExtraFormSet(instance=quincena)

    elif seccion == "deducciones":
        instance = get_object_or_404(Deducciones, quincena=quincena)
        form = DeduccionesForm(instance=instance)
        formset = DeduccionExtraFormSet(instance=quincena)

    else:
        return HttpResponseBadRequest("Sección inválida")

    return render(
        request,
        "partials/form_asignaciones.html",
        {
            "form": form,
            "formset": formset,
            "quincena_id": quincena_id,
            "seccion": seccion
        }
    )

@login_required
@require_POST
def guardar_asignaciones(request, quincena_id, seccion):
    quincena = get_object_or_404(Quincena, id=quincena_id)

    if seccion == "asignacionesMensuales":
        instance = get_object_or_404(AsignacionesMensuales, quincena=quincena)
        form = AsignacionesMensualesForm(request.POST, instance=instance)
        formset = AsignacionMensualExtraFormSet(request.POST, instance=quincena)

    elif seccion == "asignacionesQuincenales":
        instance = get_object_or_404(AsignacionesQuincenales, quincena=quincena)
        form = AsignacionesQuincenalesForm(request.POST, instance=instance)
        formset = AsignacionQuincenalExtraFormSet(request.POST, instance=quincena)

    elif seccion == "deducciones":
        instance = get_object_or_404(Deducciones, quincena=quincena)
        form = DeduccionesForm(request.POST, instance=instance)
        formset = DeduccionExtraFormSet(request.POST, instance=quincena)

    else:
        return HttpResponseBadRequest("Sección inválida")

    # VALIDAR AMBOS
    if form.is_valid() and formset.is_valid():
        form.save()
        formset.save()
        return JsonResponse({"ok": True})

    # REENDER SI HAY ERROR
    html = render_to_string(
        "partials/form_asignaciones.html",
        {
            "form": form,
            "formset": formset,
            "quincena_id": quincena_id,
            "seccion": seccion,
        },
        request=request,
    )

    return JsonResponse(
        {
            "ok": False,
            "html": html,
        },
        status=400,
    )


@login_required
@require_POST
def confirmar_eliminacion(request):
    ids = request.POST.get("ids", "")
    ids = [int(i) for i in ids.split(",") if i]

    Quincena.objects.filter(id__in=ids).update(
        pending_delete=False,
        is_deleted=True,
        deleted_at=timezone.now()
    )

    return redirect("nomina:panel_admin")


# --------------------------
# Agregar concepto adicional (modal chico)
# --------------------------

@login_required
@require_POST
def agregar_concepto_extra(request, quincena_id, seccion):
    quincena = get_object_or_404(Quincena, id=quincena_id)

    nombre = request.POST.get("nombre", "").strip()
    valor_raw = request.POST.get("valor", "").strip()

    if not nombre or not valor_raw:
        return JsonResponse(
            {"ok": False, "error": "Debe indicar nombre y valor."},
            status=400,
        )

    # Permitir coma o punto como separador decimal
    from decimal import Decimal, InvalidOperation

    try:
        valor = Decimal(valor_raw.replace(",", "."))
    except InvalidOperation:
        return JsonResponse(
            {"ok": False, "error": "Valor numérico inválido."},
            status=400,
        )

    if seccion == "asignacionesMensuales":
        modelo = AsignacionAdicionalMensual
    elif seccion == "asignacionesQuincenales":
        modelo = AsignacionAdicionalQuincenal
    elif seccion == "deducciones":
        modelo = DeduccionAdicional
    else:
        return HttpResponseBadRequest("Sección inválida")

    modelo.objects.create(
        quincena=quincena,
        nombre=nombre,
        valor=valor,
    )

    # Re-renderizar la sección para incluir el nuevo concepto
    if seccion == "asignacionesMensuales":
        instance = get_object_or_404(AsignacionesMensuales, quincena=quincena)
        form = AsignacionesMensualesForm(instance=instance)
        formset = AsignacionMensualExtraFormSet(instance=quincena)
    elif seccion == "asignacionesQuincenales":
        instance = get_object_or_404(AsignacionesQuincenales, quincena=quincena)
        form = AsignacionesQuincenalesForm(instance=instance)
        formset = AsignacionQuincenalExtraFormSet(instance=quincena)
    else:  # deducciones
        instance = get_object_or_404(Deducciones, quincena=quincena)
        form = DeduccionesForm(instance=instance)
        formset = DeduccionExtraFormSet(instance=quincena)

    html = render_to_string(
        "partials/form_asignaciones.html",
        {
            "form": form,
            "formset": formset,
            "quincena_id": quincena_id,
            "seccion": seccion,
        },
        request=request,
    )

    return JsonResponse({"ok": True, "html": html})


# --------------------------
# Cargar Nomina
# --------------------------

@login_required
def cargar_nomina_view(request):
    """
    Vista para cargar nómina o modificar la última carga existente.
    """
    from .models import Quincena  # asegurar import local para evitar bucles

    MESES = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]

    def _ultima_quincena():
        return (
            Quincena.objects
            .filter(is_deleted=False)
            .order_by("-ano", "-mes", "-periodo")
            .first()
        )

    def _siguiente_quincena(base):
        """
        Calcula la siguiente quincena basada en la última cargada:
        - Si última es periodo 1 -> siguiente periodo 2 (mismo mes/año)
        - Si última es periodo 2 -> siguiente periodo 1 (mes+1 con rollover de año)
        """
        if not base:
            now = timezone.now()
            return {"periodo": 1, "mes": now.month, "ano": now.year}

        if int(base.periodo) == 1:
            return {"periodo": 2, "mes": int(base.mes), "ano": int(base.ano)}

        # default: si periodo=2 (o cualquier otro), avanzar mes
        mes = int(base.mes) + 1
        ano = int(base.ano)
        if mes > 12:
            mes = 1
            ano += 1
        return {"periodo": 1, "mes": mes, "ano": ano}

    def _texto_quincena(q):
        periodo_txt = "1era Quincena" if int(q["periodo"]) == 1 else "2da Quincena"
        mes_txt = MESES[int(q["mes"]) - 1] if 1 <= int(q["mes"]) <= 12 else "Mes"
        return f"Se cargará la {periodo_txt} de {mes_txt} de {q['ano']}"

    if request.method == "POST":
        form = CargaNominaForm(request.POST, request.FILES)
        modo = request.POST.get("modo", "nueva")  # 'nueva' o 'modificar'

        if form.is_valid():
            archivo = request.FILES["archivo"]
            bono = form.cleaned_data.get("bono_alimenticio")

            try:
                ultima = _ultima_quincena()

                if modo == "modificar":
                    if not ultima:
                        messages.error(request, "No hay quincenas registradas para modificar.")
                        return redirect("nomina:cargar_nomina")

                    quincena_objetivo = {"periodo": int(ultima.periodo), "mes": int(ultima.mes), "ano": int(ultima.ano)}
                    messages.info(
                        request,
                        f"Se modificará la quincena existente ({ultima.mes}/{ultima.ano} - periodo {ultima.periodo}).",
                    )
                else:
                    quincena_objetivo = _siguiente_quincena(ultima)

                if int(quincena_objetivo["periodo"]) == 2 and bono is None:
                    messages.error(request, "Debe indicar el bono alimenticio para la segunda quincena.")
                    # Re-render (el input file se limpia por seguridad del navegador)
                    siguiente = _siguiente_quincena(ultima)
                    return render(request, "cargar_nomina.html", {
                        "form": form,
                        "tiene_cargas": ultima is not None,
                        "quincena_siguiente": siguiente,
                        "quincena_siguiente_texto": _texto_quincena(siguiente),
                        "quincena_ultima": {"periodo": int(ultima.periodo), "mes": int(ultima.mes), "ano": int(ultima.ano)} if ultima else None,
                        "quincena_ultima_texto": _texto_quincena({"periodo": int(ultima.periodo), "mes": int(ultima.mes), "ano": int(ultima.ano)}) if ultima else None,
                    })

                fs = FileSystemStorage()
                filename = fs.save(archivo.name, archivo)
                file_path = fs.path(filename)

                with transaction.atomic():
                    # Ejecutar el comando existente (sin alterarlo)
                    call_kwargs = {
                        "archivo": file_path,
                        "periodo": int(quincena_objetivo["periodo"]),
                        "mes": int(quincena_objetivo["mes"]),
                        "ano": int(quincena_objetivo["ano"]),
                    }
                    if int(quincena_objetivo["periodo"]) == 2 and bono is not None:
                        call_kwargs["bono_alimenticio"] = str(bono)

                    call_command("importar_quincena", **call_kwargs)

                    if modo == "modificar":
                        messages.success(request, "✅ Última quincena modificada correctamente.")
                    else:
                        messages.success(request, "✅ Nómina cargada correctamente.")

            except Exception as e:
                messages.error(request, f"❌ Error al cargar la nómina: {e}")
                siguiente = _siguiente_quincena(_ultima_quincena())
                ultima_err = _ultima_quincena()
                return render(request, "cargar_nomina.html", {
                    "form": form,
                    "tiene_cargas": ultima_err is not None,
                    "quincena_siguiente": siguiente,
                    "quincena_siguiente_texto": _texto_quincena(siguiente),
                    "quincena_ultima": {"periodo": int(ultima_err.periodo), "mes": int(ultima_err.mes), "ano": int(ultima_err.ano)} if ultima_err else None,
                    "quincena_ultima_texto": _texto_quincena({"periodo": int(ultima_err.periodo), "mes": int(ultima_err.mes), "ano": int(ultima_err.ano)}) if ultima_err else None,
                })
            finally:
                try:
                    if "fs" in locals() and "filename" in locals():
                        fs.delete(filename)
                except Exception:
                    pass

            return redirect("nomina:panel_admin")

    else:
        form = CargaNominaForm()

    # Detectar si hay cargas previas para habilitar el botón de modificar
    ultima = _ultima_quincena()
    siguiente = _siguiente_quincena(ultima)
    tiene_cargas = ultima is not None

    return render(request, "cargar_nomina.html", {
        "form": form,
        "tiene_cargas": tiene_cargas,
        "quincena_siguiente": siguiente,
        "quincena_siguiente_texto": _texto_quincena(siguiente),
        "quincena_ultima": {"periodo": int(ultima.periodo), "mes": int(ultima.mes), "ano": int(ultima.ano)} if ultima else None,
        "quincena_ultima_texto": _texto_quincena({"periodo": int(ultima.periodo), "mes": int(ultima.mes), "ano": int(ultima.ano)}) if ultima else None,
    })
