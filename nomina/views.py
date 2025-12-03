import hashlib
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML, CSS
from io import BytesIO
from django.core.management import call_command
from django.core.files.storage import FileSystemStorage
from .forms import CargaNominaForm

from .models import (
    Empleado, DatosBancarios, Quincena,
    AsignacionesMensuales, AsignacionesQuincenales,
    Deducciones, CodigoPDF, AsignacionAdicionalMensual
)
from .forms import CedulaCuentaForm, CodigoVerificacionForm, LoginForm
from django.templatetags.static import static
from django.conf import settings
import os

def generar_codigo_pdf(empleado, tipo, quincena):
    """
    Genera un código PDF único y persistente por empleado, tipo y quincena.
    Si ya existe, devuelve el mismo código.
    """
    # Verificar si ya existe un código para ese empleado, tipo y quincena
    codigo_obj, creado = CodigoPDF.objects.get_or_create(
        empleado=empleado,
        quincena=quincena,
        tipo=tipo,
        defaults={
            "codigo": hashlib.sha256(
                f"{empleado.id}-{tipo}-{quincena.id}".encode()
            ).hexdigest()[:10]  # solo 10 caracteres del hash
        }
    )
    return codigo_obj.codigo

# --------------------------
# Página principal
# --------------------------
def home(request):
    form_verificar = CodigoVerificacionForm(request.POST or None)
    form_cedula = CedulaCuentaForm(request.POST or None)
    resultado = None

    # Validación de código PDF
    if "verificar_codigo" in request.POST and form_verificar.is_valid():
        codigo = form_verificar.cleaned_data["codigo"]
        try:
            registro = CodigoPDF.objects.get(codigo=codigo)
            resultado = {
                "ok": True,
                "mensaje": "✅ Código válido",
                "empleado": registro.empleado.nombres_y_apellidos,
                "periodo": f"{registro.periodo}Q - {registro.mes}/{registro.ano}",
                "tipo": registro.tipo,
            }
        except CodigoPDF.DoesNotExist:
            resultado = {"ok": False, "mensaje": "❌ El código ingresado no es válido"}

    # Validación de cédula + cuenta
    elif "consultar_cedula" in request.POST and form_cedula.is_valid():
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

        quincena = get_object_or_404(
            Quincena,
            empleado=empleado,
            periodo=2,
            mes=mes,
            ano=ano
        )
        asignacion = AsignacionesMensuales.objects.get(quincena=quincena)
        
        adicionales = AsignacionAdicionalMensual.objects.filter(quincena=quincena)

        codigo = generar_codigo_pdf(empleado, "Constancia", quincena)
        fecha_generacion = timezone.now().strftime("%d/%m/%Y %H:%M")

        html = render_to_string("pdf/constancia_template.html", {
            "empleado": empleado,
            "asignacion": asignacion,
            "quincena": quincena,
            "codigo_pdf": codigo,
            "fecha_generacion": fecha_generacion,
            "adicionales": adicionales,
        })
        css_path = os.path.join(settings.BASE_DIR, "nomina", "static", "css","style.css")
        pdf = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf(
            stylesheets=[CSS(filename=css_path)]
        )
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename=\"constancia_{codigo}.pdf\"'
        return response

    quincenas = Quincena.objects.filter(empleado=empleado, periodo=2)
    return render(request, "seleccionar_periodo.html", {
        "quincenas": quincenas,
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

        codigo = generar_codigo_pdf(empleado, "Recibo", quincena)
        fecha_generacion = timezone.now().strftime("%d/%m/%Y %H:%M")

        html = render_to_string("pdf/recibo_template.html", {
            "empleado": empleado,
            "asignacion": asignacion,
            "deducciones": deducciones,
            "quincena": quincena,
            "codigo_pdf": codigo,
            "fecha_generacion": fecha_generacion,
        })
        pdf = HTML(string=html).write_pdf()
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="recibo_{codigo}.pdf"'
        return response

    quincenas = Quincena.objects.filter(empleado=empleado)
    return render(request, "seleccionar_periodo.html", {
        "quincenas": quincenas,
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

    if seleccion:
        periodo, mes, ano = map(int, seleccion.split("-"))
        empleados = (
            Quincena.objects
            .filter(periodo=periodo, mes=mes, ano=ano)
            .select_related("empleado")
            .order_by("empleado__nombres_y_apellidos")
        )

    return render(request, "panel_admin.html", {
        "quincenas": quincenas,
        "empleados": empleados,
    })

@login_required
def cargar_nomina_view(request):
    """
    Vista para cargar nómina o modificar la última carga existente.
    """
    from .models import Quincena  # asegurar import local para evitar bucles

    if request.method == "POST":
        form = CargaNominaForm(request.POST, request.FILES)
        modo = request.POST.get("modo", "nueva")  # 'nueva' o 'modificar'

        if form.is_valid():
            archivo = request.FILES["archivo"]
            periodo = int(form.cleaned_data["periodo"])
            bono = form.cleaned_data.get("bono_alimenticio")

            fs = FileSystemStorage()
            filename = fs.save(archivo.name, archivo)
            file_path = fs.path(filename)

            try:
                with transaction.atomic():
                    if modo == "modificar":
                        # Detecta automáticamente la última quincena registrada
                        ultima = (
                            Quincena.objects.order_by("-ano", "-mes", "-periodo").first()
                        )
                        if not ultima:
                            messages.error(request, "No hay quincenas registradas para modificar.")
                            return redirect("nomina:cargar_nomina")

                        periodo = ultima.periodo
                        messages.info(request, f"Se modificará la quincena existente ({ultima.mes}/{ultima.ano} - periodo {ultima.periodo}).")

                    # Ejecutar el comando existente (sin alterarlo)
                    if periodo == 2 and bono is not None:
                        call_command("importar_quincena", archivo=file_path, periodo=periodo, bono_alimenticio=bono)
                    else:
                        call_command("importar_quincena", archivo=file_path, periodo=periodo)

                    if modo == "modificar":
                        messages.success(request, "✅ Última quincena modificada correctamente.")
                    else:
                        messages.success(request, f"✅ Nómina cargada correctamente (periodo {periodo}).")

            except Exception as e:
                messages.error(request, f"❌ Error al cargar la nómina: {e}")

            fs.delete(filename)
            return redirect("nomina:panel_admin")

    else:
        form = CargaNominaForm()

    # Detectar si hay cargas previas para habilitar el botón de modificar
    tiene_cargas = Quincena.objects.exists()

    return render(request, "cargar_nomina.html", {
        "form": form,
        "tiene_cargas": tiene_cargas,
    })
