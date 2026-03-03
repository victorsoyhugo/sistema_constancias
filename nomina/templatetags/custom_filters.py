# En tu archivo de filtros personalizados (ej: nomina/templatetags/custom_filters.py)
from django import template
import decimal

register = template.Library()

@register.filter
def truncate_decimal(value, decimals=2):
    """
    Trunca un número decimal a 'decimals' lugares sin redondear.
    """
    if value is None:
        return "0.00"
    
    try:
        # Convertir a Decimal si es string o float
        d = decimal.Decimal(str(value))
        # Usar quantize para truncar (ROUND_DOWN en lugar de ROUND_HALF_UP)
        truncated = d.quantize(
            decimal.Decimal('0.' + '0' * decimals),
            rounding=decimal.ROUND_DOWN
        )
        # Formatear con 2 decimales fijos
        return f"{truncated:.{decimals}f}"
    except (ValueError, TypeError, decimal.InvalidOperation):
        return f"0.{'0' * decimals}"