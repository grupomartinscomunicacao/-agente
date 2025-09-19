"""
Testes para app LGPD.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta

from cidadaos.models import Cidadao
from lgpd.models import ConsentimentoLGPD, AuditoriaAcesso, ViolacaoDados
from utils.lgpd import AnonimizadorLGPD, ConsentimentoLGPD as ConsentimentoUtil


class AnonimizadorLGPDTest(TestCase):
    """Testes para o anonimizador LGPD."""
    
    def test_anonimizar_cpf(self):
        """Testa anonimização de CPF."""
        cpf = "123.456.789-10"
        resultado = AnonimizadorLGPD.anonimizar_cpf(cpf)
        self.assertEqual(resultado, "***.***.***-10")
    
    def test_anonimizar_nome(self):
        """Testa anonimização de nome."""
        nome = "João Silva Santos"
        resultado = AnonimizadorLGPD.anonimizar_nome(nome)
        self.assertEqual(resultado, "J. S. S.")
    
    def test_anonimizar_email(self):
        """Testa anonimização de email."""
        email = "joao@email.com"
        resultado = AnonimizadorLGPD.anonimizar_email(email)
        self.assertEqual(resultado, "j***@email.com")
    
    def test_anonimizar_telefone(self):
        """Testa anonimização de telefone."""
        telefone = "(11) 99999-9999"
        resultado = AnonimizadorLGPD.anonimizar_telefone(telefone)
        self.assertEqual(resultado, "(11) ****-9999")


class ConsentimentoLGPDTest(TestCase):
    """Testes para o modelo de consentimento."""
    
    def setUp(self):
        self.cidadao = Cidadao.objects.create(
            nome="Teste Silva",
            cpf="123.456.789-10",
            data_nascimento="1990-01-01",
            sexo="M"
        )
    
    def test_criar_consentimento(self):
        """Testa criação de consentimento."""
        consentimento = ConsentimentoLGPD.objects.create(
            cidadao=self.cidadao,
            finalidade='ATENDIMENTO_MEDICO',
            token_consentimento='abc123',
            valido_ate=timezone.now() + timedelta(days=365)
        )
        
        self.assertTrue(consentimento.ativo)
        self.assertEqual(consentimento.cidadao, self.cidadao)
    
    def test_revogar_consentimento(self):
        """Testa revogação de consentimento."""
        consentimento = ConsentimentoLGPD.objects.create(
            cidadao=self.cidadao,
            finalidade='ATENDIMENTO_MEDICO',
            token_consentimento='abc123',
            valido_ate=timezone.now() + timedelta(days=365)
        )
        
        consentimento.revogar()
        
        self.assertFalse(consentimento.ativo)
        self.assertIsNotNone(consentimento.data_revogacao)
    
    def test_consentimento_expirado(self):
        """Testa consentimento expirado."""
        consentimento = ConsentimentoLGPD.objects.create(
            cidadao=self.cidadao,
            finalidade='ATENDIMENTO_MEDICO',
            token_consentimento='abc123',
            valido_ate=timezone.now() - timedelta(days=1)  # Expirado
        )
        
        self.assertFalse(consentimento.ativo)


class AuditoriaAcessoTest(TestCase):
    """Testes para auditoria de acesso."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.cidadao = Cidadao.objects.create(
            nome="Teste Silva",
            cpf="123.456.789-10",
            data_nascimento="1990-01-01",
            sexo="M"
        )
    
    def test_criar_auditoria(self):
        """Testa criação de registro de auditoria."""
        auditoria = AuditoriaAcesso.objects.create(
            usuario=self.user,
            cidadao=self.cidadao,
            tipo_acao='ACESSO_DADOS',
            ip_address='127.0.0.1'
        )
        
        self.assertEqual(auditoria.usuario, self.user)
        self.assertEqual(auditoria.cidadao, self.cidadao)
        self.assertEqual(auditoria.tipo_acao, 'ACESSO_DADOS')


class ViolacaoDadosTest(TestCase):
    """Testes para violação de dados."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_criar_violacao(self):
        """Testa criação de violação."""
        violacao = ViolacaoDados.objects.create(
            tipo_violacao='ACESSO_NAO_AUTORIZADO',
            severidade='ALTA',
            descricao='Tentativa de acesso não autorizado detectada',
            detectado_por=self.user
        )
        
        self.assertEqual(violacao.tipo_violacao, 'ACESSO_NAO_AUTORIZADO')
        self.assertEqual(violacao.severidade, 'ALTA')
        self.assertFalse(violacao.resolvida)
    
    def test_deve_notificar_anpd(self):
        """Testa se deve notificar ANPD."""
        violacao = ViolacaoDados.objects.create(
            tipo_violacao='VAZAMENTO_DADOS',
            severidade='CRITICA',
            descricao='Vazamento crítico detectado',
            detectado_por=self.user
        )
        
        # Para severidade crítica, deve notificar ANPD
        self.assertTrue(violacao.deve_notificar_anpd)


class ViewsLGPDTest(TestCase):
    """Testes para views LGPD."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.cidadao = Cidadao.objects.create(
            nome="Teste Silva",
            cpf="123.456.789-10",
            data_nascimento="1990-01-01",
            sexo="M"
        )
    
    def test_dashboard_lgpd_requires_login(self):
        """Testa que dashboard requer login."""
        response = self.client.get(reverse('lgpd:dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect para login
    
    def test_dashboard_lgpd_authenticated(self):
        """Testa dashboard com usuário autenticado."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('lgpd:dashboard'))
        self.assertEqual(response.status_code, 200)
    
    def test_termo_consentimento_get(self):
        """Testa exibição do termo de consentimento."""
        response = self.client.get(
            reverse('lgpd:termo_consentimento_cidadao', args=[self.cidadao.id])
        )
        self.assertEqual(response.status_code, 200)
    
    def test_api_verificar_consentimento(self):
        """Testa API de verificação de consentimento."""
        # Criar consentimento
        ConsentimentoLGPD.objects.create(
            cidadao=self.cidadao,
            finalidade='ATENDIMENTO_MEDICO',
            token_consentimento='abc123',
            valido_ate=timezone.now() + timedelta(days=365)
        )
        
        response = self.client.post(
            reverse('lgpd:api_verificar_consentimento'),
            data={
                'cidadao_id': str(self.cidadao.id),
                'finalidade': 'ATENDIMENTO_MEDICO'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['consentimento_valido'])


class IntegracaoLGPDTest(TestCase):
    """Testes de integração LGPD com outros módulos."""
    
    def setUp(self):
        self.cidadao = Cidadao.objects.create(
            nome="João Silva Santos",
            cpf="123.456.789-10",
            data_nascimento="1990-01-01",
            sexo="M",
            email="joao@email.com",
            telefone="(11) 99999-9999"
        )
    
    def test_anonimizacao_completa_cidadao(self):
        """Testa anonimização completa dos dados do cidadão."""
        # Dados originais
        nome_original = self.cidadao.nome
        cpf_original = self.cidadao.cpf
        
        # Anonimizar
        self.cidadao.nome = AnonimizadorLGPD.anonimizar_nome(self.cidadao.nome)
        self.cidadao.cpf = AnonimizadorLGPD.anonimizar_cpf(self.cidadao.cpf)
        self.cidadao.email = AnonimizadorLGPD.anonimizar_email(self.cidadao.email)
        self.cidadao.telefone = AnonimizadorLGPD.anonimizar_telefone(self.cidadao.telefone)
        self.cidadao.save()
        
        # Verificar anonimização
        self.assertNotEqual(self.cidadao.nome, nome_original)
        self.assertNotEqual(self.cidadao.cpf, cpf_original)
        self.assertEqual(self.cidadao.nome, "J. S. S.")
        self.assertEqual(self.cidadao.cpf, "***.***.***-10")