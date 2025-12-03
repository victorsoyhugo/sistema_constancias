from django.urls import path
from . import views

app_name = "nomina"

urlpatterns = [
    # Público
    path("", views.home, name="home"),
    path("bienvenida/", views.bienvenida, name="bienvenida"),

    # Generar PDFs (selección y generación)
    path("generar/constancia/", views.generar_constancia, name="generar_constancia"),
    path("generar/recibo/", views.generar_recibo, name="generar_recibo"),

    # Autenticación admin (usa User)
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("panel_admin/", views.panel_admin, name="panel_admin"),
    
    path("cargar-nomina/", views.cargar_nomina_view, name="cargar_nomina"),
]