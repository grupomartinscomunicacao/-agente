from django.core.management.base import BaseCommand
from geolocation.models import LocalizacaoSaude
from geolocation.calculador_risco import CalculadorRisco
from geolocation.geocodificacao_service import GeocodificacaoService


class Command(BaseCommand):
    help = 'Recalcula os riscos de todos os cidadãos com base nos seus dados de saúde'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra o que seria alterado sem executar',
        )

    def handle(self, *args, **options):
        self.stdout.write('🎯 Iniciando recálculo de riscos...\n')
        
        calculador = CalculadorRisco()
        geocod_service = GeocodificacaoService()
        
        localizacoes = LocalizacaoSaude.objects.all()
        self.stdout.write(f"Total de cidadãos: {localizacoes.count()}")
        
        atualizados = 0
        
        for loc in localizacoes:
            try:
                # Calcular risco baseado nos dados de saúde
                resultado = calculador.calcular_risco_cidadao(loc.cidadao)
                nivel_risco = resultado['nivel']
                pontuacao_risco = resultado['pontuacao']
                
                if options['dry_run']:
                    self.stdout.write(
                        f"[DRY RUN] {loc.cidadao.nome}: {loc.nivel_risco} → {nivel_risco.upper()} "
                        f"(pontuação: {pontuacao_risco:.1f})"
                    )
                    continue
                
                # Aplicar dispersão nas coordenadas se necessário
                if loc.cidade and loc.estado:
                    # Verificar se há outros cidadãos na mesma cidade
                    mesma_cidade = LocalizacaoSaude.objects.filter(
                        cidade=loc.cidade,
                        estado=loc.estado
                    ).exclude(id=loc.id)
                    
                    if mesma_cidade.exists():
                        # Aplicar jitter para evitar sobreposição
                        novas_coords = geocod_service.adicionar_jitter_coordenadas(
                            loc.latitude, 
                            loc.longitude,
                            raio_metros=1500  # Raio maior para cidades
                        )
                        loc.latitude = novas_coords[0]
                        loc.longitude = novas_coords[1]
                
                # Atualizar os dados
                loc.nivel_risco = nivel_risco
                loc.pontuacao_risco = pontuacao_risco
                loc.save()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ {loc.cidadao.nome}: {nivel_risco.upper()} (pontuação: {pontuacao_risco:.1f})"
                    )
                )
                atualizados += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Erro ao processar {loc.cidadao.nome}: {e}")
                )
        
        self.stdout.write(
            self.style.SUCCESS(f"\n🎉 Processamento concluído: {atualizados}/{localizacoes.count()} cidadãos atualizados")
        )