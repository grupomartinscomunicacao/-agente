"""
Formulários para o dashboard do sistema de saúde.
"""
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta

from cidadaos.models import Cidadao
from dashboard.models import VisitaAgendada


class VisitaAgendadaForm(forms.ModelForm):
    """
    Formulário para agendamento de visitas domiciliares.
    """
    
    # Campo customizado para seleção de cidadão com busca
    cidadao = forms.ModelChoiceField(
        queryset=Cidadao.objects.filter(ativo=True).order_by('nome'),
        empty_label="Selecione o cidadão...",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'data-placeholder': 'Digite o nome do cidadão...'
        }),
        help_text="Selecione o cidadão que receberá a visita"
    )
    
    # Campo de data e hora com widget customizado
    data_visita = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control',
        }),
        help_text="Data e hora da visita"
    )
    
    # Campo de duração com valor padrão
    duracao_minutos = forms.IntegerField(
        initial=30,
        min_value=15,
        max_value=180,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '15'
        }),
        help_text="Duração estimada da visita em minutos"
    )
    
    # Campo de observações
    observacoes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Observações adicionais sobre a visita...'
        }),
        help_text="Informações adicionais sobre a visita"
    )
    
    class Meta:
        model = VisitaAgendada
        fields = ['cidadao', 'data_visita', 'motivo', 'duracao_minutos', 'observacoes', 'lembrete_agente']
        widgets = {
            'motivo': forms.Select(attrs={'class': 'form-select'}),
            'lembrete_agente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'cidadao': 'Cidadão *',
            'data_visita': 'Data e Hora *', 
            'motivo': 'Motivo da Visita *',
            'duracao_minutos': 'Duração (minutos)',
            'observacoes': 'Observações',
            'lembrete_agente': 'Enviar lembrete para o agente'
        }
        help_texts = {
            'motivo': 'Selecione o motivo principal da visita',
            'lembrete_agente': 'Marque para receber notificação antes da visita'
        }
    
    def __init__(self, *args, **kwargs):
        """
        Inicialização do formulário com configurações customizadas.
        """
        super().__init__(*args, **kwargs)
        
        # Configurar data mínima para hoje
        agora = timezone.now()
        agora_local = agora.strftime('%Y-%m-%dT%H:%M')
        self.fields['data_visita'].widget.attrs.update({
            'min': agora_local
        })
        
        # Filtrar apenas cidadãos ativos e ordenar por nome
        self.fields['cidadao'].queryset = Cidadao.objects.filter(
            ativo=True
        ).select_related().order_by('nome')
        
        # Adicionar classes Bootstrap aos campos
        for field_name, field in self.fields.items():
            if field_name not in ['lembrete_agente']:  # Checkbox tem tratamento especial
                if 'class' not in field.widget.attrs:
                    if isinstance(field.widget, forms.Select):
                        field.widget.attrs['class'] = 'form-select'
                    elif isinstance(field.widget, forms.Textarea):
                        field.widget.attrs['class'] = 'form-control'
                    else:
                        field.widget.attrs['class'] = 'form-control'
    
    def clean_data_visita(self):
        """
        Validação customizada para data da visita.
        """
        data_visita = self.cleaned_data.get('data_visita')
        
        if data_visita:
            agora = timezone.now()
            
            # Não permitir agendamento no passado
            if data_visita < agora:
                raise ValidationError(
                    'Não é possível agendar visitas no passado.'
                )
            
            # Não permitir agendamento em fins de semana (opcional)
            # if data_visita.weekday() >= 5:  # 5=sábado, 6=domingo
            #     raise ValidationError(
            #         'Visitas não podem ser agendadas para fins de semana.'
            #     )
            
            # Não permitir agendamento muito no futuro (6 meses)
            seis_meses = agora + timedelta(days=180)
            if data_visita > seis_meses:
                raise ValidationError(
                    'Não é possível agendar visitas com mais de 6 meses de antecedência.'
                )
            
            # Verificar horário comercial (8h às 17h)
            if data_visita.hour < 8 or data_visita.hour >= 17:
                raise ValidationError(
                    'Visitas devem ser agendadas entre 08:00 e 17:00.'
                )
        
        return data_visita
    
    def clean(self):
        """
        Validação geral do formulário.
        """
        cleaned_data = super().clean()
        cidadao = cleaned_data.get('cidadao')
        data_visita = cleaned_data.get('data_visita')
        
        # Verificar se já existe uma visita para o mesmo cidadão no mesmo horário
        if cidadao and data_visita:
            # Verificar conflito de horário (±30 minutos)
            inicio = data_visita - timedelta(minutes=30)
            fim = data_visita + timedelta(minutes=30)
            
            conflito = VisitaAgendada.objects.filter(
                cidadao=cidadao,
                data_visita__range=[inicio, fim],
                status__in=['agendada', 'confirmada']
            ).exclude(pk=self.instance.pk if self.instance.pk else None)
            
            if conflito.exists():
                raise ValidationError(
                    f'Já existe uma visita agendada para {cidadao.nome} '
                    f'próximo a este horário. Verifique a agenda.'
                )
        
        return cleaned_data


class FiltroVisitasForm(forms.Form):
    """
    Formulário para filtrar visitas na agenda.
    """
    
    PERIODO_CHOICES = [
        ('hoje', 'Hoje'),
        ('semana', 'Esta Semana'),
        ('mes', 'Este Mês'),
        ('todos', 'Todos')
    ]
    
    STATUS_CHOICES = [
        ('', 'Todos os Status'),
        ('agendada', 'Agendada'),
        ('confirmada', 'Confirmada'),
        ('realizada', 'Realizada'),
        ('cancelada', 'Cancelada'),
        ('reagendada', 'Reagendada')
    ]
    
    periodo = forms.ChoiceField(
        choices=PERIODO_CHOICES,
        initial='semana',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        required=False
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        required=False
    )
    
    cidadao = forms.ModelChoiceField(
        queryset=Cidadao.objects.filter(ativo=True).order_by('nome'),
        empty_label="Todos os cidadãos",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        required=False
    )