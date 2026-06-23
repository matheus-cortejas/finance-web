from __future__ import annotations

from django import forms

from core.models import PerfilInvestidor
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class PerfilInvestidorForm(forms.ModelForm):
    setores_preferidos_text = forms.CharField(
        required=False,
        label="Setores preferidos",
        help_text="Separe os setores por vírgula.",
    )

    class Meta:
        model = PerfilInvestidor
        fields = [
            "perfil_risco",
            "horizonte",
            "frequencia_alertas",
            "alerta_min_prioridade",
            "sensibilidade_negativo",
            "notificacao_email",      # NOVO
            "notificacao_push",       # NOVO
            "notificacao_dashboard",  # NOVO
        ]
        widgets = {
            "perfil_risco": forms.Select(attrs={"class": "form-select"}),
            "horizonte": forms.Select(attrs={"class": "form-select"}),
            "frequencia_alertas": forms.Select(attrs={"class": "form-select"}),
            "alerta_min_prioridade": forms.Select(attrs={"class": "form-select"}),
            "sensibilidade_negativo": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "max": "1", "step": "0.05"}
            ),
            "notificacao_email": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notificacao_push": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notificacao_dashboard": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        setores = []
        if self.instance and self.instance.setores_preferidos:
            setores = [str(item).strip() for item in self.instance.setores_preferidos if str(item).strip()]
        self.fields["setores_preferidos_text"].initial = ", ".join(setores)
        self.fields["setores_preferidos_text"].widget = forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Ex.: bancos, energia, varejo"}
        )

    def clean_setores_preferidos_text(self) -> list[str]:
        raw = self.cleaned_data.get("setores_preferidos_text", "")
        if not raw:
            return []
        parts = [item.strip() for item in raw.replace(";", ",").split(",")]
        return [item for item in parts if item]

    def save(self, commit: bool = True):
        instance = super().save(commit=False)
        instance.setores_preferidos = self.cleaned_data.get("setores_preferidos_text", [])
        if commit:
            instance.save()
        return instance
    
class RegistroForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        help_text="Informe um e-mail válido.",
        widget=forms.EmailInput(attrs={"class": "form-control form-control-lg", "placeholder": "Digite seu e-mail"})
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Estiliza os campos automáticos
        self.fields["username"].widget.attrs.update({
            "class": "form-control form-control-lg",
            "placeholder": "Digite seu usuário",
            "autofocus": True,
        })
        self.fields["password1"].widget.attrs.update({
            "class": "form-control form-control-lg",
            "placeholder": "Digite sua senha",
        })
        self.fields["password2"].widget.attrs.update({
            "class": "form-control form-control-lg",
            "placeholder": "Confirme sua senha",
        })    
