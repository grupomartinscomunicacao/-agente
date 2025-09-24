# Generated manually

from django.db import migrations

def criar_categorias_e_migrar_dados(apps, schema_editor):
    """
    Cria as categorias padrão e migra os dados existentes
    """
    CategoriaTreinamento = apps.get_model('dashboard', 'CategoriaTreinamento')
    Treinamento = apps.get_model('dashboard', 'Treinamento')
    
    # Mapeamento das categorias antigas para as novas
    categoria_mapping = {
        'procedimentos': 'Procedimentos de Saúde',
        'prevencao': 'Prevenção e Cuidados', 
        'emergencia': 'Atendimento de Emergência',
        'doencas_cronicas': 'Doenças Crônicas',
        'saude_mental': 'Saúde Mental',
        'vacinacao': 'Vacinação',
        'higiene': 'Higiene e Sanitização',
        'comunicacao': 'Comunicação com Pacientes',
        'lgpd': 'LGPD e Privacidade',
        'outros': 'Outros'
    }
    
    # Criar categorias padrão
    categorias_padrao = [
        {'nome': 'Procedimentos de Saúde', 'descricao': 'Técnicas e procedimentos básicos de saúde pública', 'ordem': 1},
        {'nome': 'Prevenção e Cuidados', 'descricao': 'Estratégias de prevenção de doenças e cuidados preventivos', 'ordem': 2},
        {'nome': 'Atendimento de Emergência', 'descricao': 'Procedimentos para situações de emergência e urgência', 'ordem': 3},
        {'nome': 'Doenças Crônicas', 'descricao': 'Acompanhamento e manejo de doenças crônicas', 'ordem': 4},
        {'nome': 'Saúde Mental', 'descricao': 'Abordagem e cuidados em saúde mental na atenção básica', 'ordem': 5},
        {'nome': 'Vacinação', 'descricao': 'Protocolos de vacinação e calendário vacinal', 'ordem': 6},
        {'nome': 'Higiene e Sanitização', 'descricao': 'Práticas de higiene e sanitização em unidades de saúde', 'ordem': 7},
        {'nome': 'Comunicação com Pacientes', 'descricao': 'Técnicas de comunicação efetiva com pacientes e familiares', 'ordem': 8},
        {'nome': 'LGPD e Privacidade', 'descricao': 'Lei Geral de Proteção de Dados aplicada à saúde', 'ordem': 9},
        {'nome': 'Outros', 'descricao': 'Outros assuntos relacionados à saúde pública', 'ordem': 10}
    ]
    
    categorias_objetos = {}
    for dados in categorias_padrao:
        categoria = CategoriaTreinamento.objects.create(**dados)
        categorias_objetos[dados['nome']] = categoria
    
    # Migrar treinamentos existentes
    for treinamento in Treinamento.objects.all():
        categoria_antiga = treinamento.categoria
        categoria_nova_nome = categoria_mapping.get(categoria_antiga, 'Outros')
        categoria_nova = categorias_objetos[categoria_nova_nome]
        
        # Usar SQL direto para evitar problemas de validação
        schema_editor.execute(
            "UPDATE dashboard_treinamento SET categoria_id = %s WHERE id = %s",
            [categoria_nova.id, treinamento.id]
        )

def reverter_migracao(apps, schema_editor):
    """
    Remove as categorias criadas
    """
    CategoriaTreinamento = apps.get_model('dashboard', 'CategoriaTreinamento')
    CategoriaTreinamento.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0005_categoriatreinamento_alter_treinamento_categoria'),
    ]

    operations = [
        migrations.RunPython(criar_categorias_e_migrar_dados, reverter_migracao),
    ]