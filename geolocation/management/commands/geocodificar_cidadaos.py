"""
Command de gerenciamento para processar cidadãos sem localização
"""
from django.core.management.base import BaseCommand
from cidadaos.models import Cidadao
from geolocation.models import LocalizacaoSaude
from geolocation.geocodificacao_service import processar_cidadao_sem_localizacao


class Command(BaseCommand):
    help = 'Processa cidadãos sem LocalizacaoSaude e tenta geocodificar por CEP/cidade'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra quais cidadãos seriam processados sem executar',
        )
        
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Limite de cidadãos para processar por execução',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']
        
        # Buscar cidadãos sem LocalizacaoSaude
        cidadaos_sem_localizacao = Cidadao.objects.filter(
            localizacoes_saude__isnull=True
        ).exclude(
            ativo=False
        )[:limit]
        
        total = cidadaos_sem_localizacao.count()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Encontrados {total} cidadãos sem localização'
            )
        )
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Modo DRY-RUN ativado - nenhuma mudança será feita'))
            
            for cidadao in cidadaos_sem_localizacao:
                self.stdout.write(
                    f'- {cidadao.nome} ({cidadao.cidade}/{cidadao.estado}) - CEP: {getattr(cidadao, "cep", "N/A")}'
                )
            return
        
        processados = 0
        sucessos = 0
        
        for cidadao in cidadaos_sem_localizacao:
            self.stdout.write(f'Processando: {cidadao.nome}...')
            
            try:
                resultado = processar_cidadao_sem_localizacao(cidadao)
                
                if resultado:
                    sucessos += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ {cidadao.nome}: {resultado.cidade}/{resultado.estado} '
                            f'({resultado.latitude}, {resultado.longitude})'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠️ {cidadao.nome}: Não foi possível geocodificar'
                        )
                    )
                
                processados += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ {cidadao.nome}: Erro - {str(e)}'
                    )
                )
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'Processamento concluído: {sucessos}/{processados} cidadãos geocodificados'
            )
        )