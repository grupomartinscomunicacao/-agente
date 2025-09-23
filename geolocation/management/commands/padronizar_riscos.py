from django.core.management.base import BaseCommand
from geolocation.models import LocalizacaoSaude
from collections import Counter


class Command(BaseCommand):
    help = 'Padroniza os níveis de risco removendo acentos e inconsistências'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra o que seria alterado sem executar',
        )

    def handle(self, *args, **options):
        self.stdout.write('🎯 Padronizando níveis de risco...\n')
        
        # Mapeamento de correções
        correcoes = {
            'médio': 'medio',
            'MÉDIO': 'medio', 
            'Médio': 'medio',
            'MEDIO': 'medio',
            'Medio': 'medio',
            'baixo': 'baixo',
            'BAIXO': 'baixo',
            'Baixo': 'baixo',
            'alto': 'alto',
            'ALTO': 'alto',
            'Alto': 'alto',
            'critico': 'critico',
            'CRITICO': 'critico',
            'Critico': 'critico'
        }
        
        localizacoes = LocalizacaoSaude.objects.all()
        corrigidos = 0
        
        self.stdout.write(f"Total de registros: {localizacoes.count()}")
        
        # Mostrar distribuição atual
        riscos_atuais = [loc.nivel_risco for loc in localizacoes]
        distribuicao_atual = Counter(riscos_atuais)
        
        self.stdout.write("\n📊 Distribuição atual:")
        for risco, qtd in sorted(distribuicao_atual.items()):
            self.stdout.write(f"   '{risco}': {qtd} cidadãos")
        
        self.stdout.write("\n🔧 Processando correções:")
        
        for loc in localizacoes:
            risco_original = loc.nivel_risco
            risco_corrigido = correcoes.get(risco_original, risco_original.lower())
            
            if risco_original != risco_corrigido:
                if options['dry_run']:
                    self.stdout.write(
                        f"[DRY RUN] {loc.cidadao.nome}: '{risco_original}' → '{risco_corrigido}'"
                    )
                else:
                    loc.nivel_risco = risco_corrigido
                    loc.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ {loc.cidadao.nome}: '{risco_original}' → '{risco_corrigido}'"
                        )
                    )
                corrigidos += 1
            else:
                self.stdout.write(f"🔹 {loc.cidadao.nome}: '{risco_original}' (já correto)")
        
        if not options['dry_run']:
            # Mostrar distribuição final
            riscos_finais = [loc.nivel_risco for loc in LocalizacaoSaude.objects.all()]
            distribuicao_final = Counter(riscos_finais)
            
            self.stdout.write("\n📊 Distribuição final:")
            for risco, qtd in sorted(distribuicao_final.items()):
                self.stdout.write(f"   '{risco}': {qtd} cidadãos")
        
        self.stdout.write(
            self.style.SUCCESS(f"\n🎉 Processamento concluído: {corrigidos} registros {'seriam corrigidos' if options['dry_run'] else 'corrigidos'}")
        )