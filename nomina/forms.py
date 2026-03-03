from django import forms

class CedulaCuentaForm(forms.Form):
    cedula = forms.IntegerField(
        label="Cédula",
        min_value=1,
        max_value=99999999,
        widget=forms.NumberInput(attrs={"placeholder": "Cédula (solo números)"})
    )
    ultimos4 = forms.CharField(
        label="Últimos 4 dígitos",
        min_length=1,
        max_length=4,
        widget=forms.TextInput(attrs={"placeholder": "Últimos 4 dígitos de la cuenta"})
    )

    def clean_ultimos4(self):
        v = self.cleaned_data["ultimos4"]
        if not v.isdigit():
            raise forms.ValidationError("Los últimos dígitos deben ser numéricos.")
        return v.zfill(4)  # rellena por si envían menos de 4 dígitos


class CodigoVerificacionForm(forms.Form):
    codigo = forms.CharField(
        label='Código de verificación',
        max_length=50,
        widget=forms.TextInput(attrs={
            'style': 'text-transform: uppercase;',
            'oninput': 'this.value = this.value.toUpperCase()',
        })
    )


class LoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={"placeholder": "Usuario"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Contraseña"}))

class CargaNominaForm(forms.Form):
    archivo = forms.FileField(label="Archivo XLSX")
    bono_alimenticio = forms.DecimalField(
        label="Bono Alimenticio (solo para periodo 2)",
        required=False,
        decimal_places=2,
        max_digits=10,
    )
