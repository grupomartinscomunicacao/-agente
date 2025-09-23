"""
Serviço de Geocodificação por CEP
Integra APIs brasileiras para obter coordenadas a partir do CEP
"""

import requests
import logging
from typing import Dict, Optional, Tuple
from django.conf import settings
import time
import random
import math

logger = logging.getLogger(__name__)


class GeocodificacaoService:
    """Serviço para geocodificação usando CEP brasileiro."""
    
    def __init__(self):
        self.viacep_url = "https://viacep.com.br/ws/{}/json/"
        self.nominatim_url = "https://nominatim.openstreetmap.org/search"
        self.timeout = 10
    
    def adicionar_jitter_coordenadas(self, lat: float, lng: float, raio_metros: int = 500) -> Tuple[float, float]:
        """
        Adiciona dispersão aleatória às coordenadas para evitar sobreposição.
        
        Args:
            lat: Latitude original
            lng: Longitude original  
            raio_metros: Raio máximo de dispersão em metros
            
        Returns:
            Tuple (nova_lat, nova_lng) com dispersão aplicada
        """
        try:
            # Converter para float caso sejam Decimal
            lat = float(lat)
            lng = float(lng)
            
            # Conversão aproximada: 1 grau ≈ 111km
            # Ajustar para latitude (varia com a posição)
            metros_por_grau_lat = 111000
            metros_por_grau_lng = 111000 * math.cos(math.radians(lat))
            
            # Gerar dispersão aleatória em círculo
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(0, raio_metros)
            
            # Calcular offset em graus
            delta_lat = (distance * math.cos(angle)) / metros_por_grau_lat
            delta_lng = (distance * math.sin(angle)) / metros_por_grau_lng
            
            nova_lat = lat + delta_lat
            nova_lng = lng + delta_lng
            
            logger.info(f"Jitter aplicado: {lat:.6f},{lng:.6f} → {nova_lat:.6f},{nova_lng:.6f} (raio: {distance:.1f}m)")
            
            return nova_lat, nova_lng
            
        except Exception as e:
            logger.error(f"Erro ao aplicar jitter: {e}")
            return lat, lng
    
    def buscar_endereco_por_cep(self, cep: str) -> Optional[Dict]:
        """
        Busca informações do endereço usando a API ViaCEP.
        
        Args:
            cep: CEP no formato "12345678" ou "12345-678"
            
        Returns:
            Dict com informações do endereço ou None se não encontrado
        """
        try:
            # Limpar CEP
            cep_limpo = cep.replace("-", "").replace(".", "").strip()
            
            if len(cep_limpo) != 8 or not cep_limpo.isdigit():
                logger.warning(f"CEP inválido: {cep}")
                return None
            
            logger.info(f"Buscando endereco para CEP: {cep_limpo}")
            
            response = requests.get(
                self.viacep_url.format(cep_limpo),
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # ViaCEP retorna {"erro": true} se CEP não existe
            if data.get('erro'):
                logger.warning(f"CEP não encontrado: {cep_limpo}")
                return None
            
            endereco = {
                'cep': data.get('cep'),
                'logradouro': data.get('logradouro'),
                'complemento': data.get('complemento'),
                'bairro': data.get('bairro'),
                'cidade': data.get('localidade'),
                'estado': data.get('uf'),
                'ibge': data.get('ibge'),
                'gia': data.get('gia'),
                'ddd': data.get('ddd'),
                'siafi': data.get('siafi')
            }
            
            logger.info(f"Endereco encontrado: {endereco['cidade']}/{endereco['estado']}")
            return endereco
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na requisição ViaCEP para {cep}: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar CEP {cep}: {e}")
            return None
    
    def geocodificar_endereco(self, endereco: Dict) -> Optional[Tuple[float, float]]:
        """
        Obtém coordenadas geográficas usando Nominatim OpenStreetMap.
        
        Args:
            endereco: Dict com informações do endereço
            
        Returns:
            Tuple (latitude, longitude) ou None se não encontrado
        """
        try:
            # Construir query de busca
            cidade = endereco.get('cidade', '')
            estado = endereco.get('estado', '')
            logradouro = endereco.get('logradouro', '')
            bairro = endereco.get('bairro', '')
            
            # Tentar diferentes combinações de endereço
            queries = [
                f"{logradouro}, {bairro}, {cidade}, {estado}, Brasil",
                f"{bairro}, {cidade}, {estado}, Brasil",
                f"{cidade}, {estado}, Brasil",
            ]
            
            for query in queries:
                logger.info(f"Geocodificando: {query}")
                
                params = {
                    'q': query,
                    'format': 'json',
                    'limit': 1,
                    'countrycodes': 'BR',  # Limitar ao Brasil
                    'addressdetails': 1
                }
                
                response = requests.get(
                    self.nominatim_url,
                    params=params,
                    timeout=self.timeout,
                    headers={
                        'User-Agent': 'Sistema-Saude-Publica/1.0 (Django)'
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data and len(data) > 0:
                    result = data[0]
                    lat = float(result['lat'])
                    lon = float(result['lon'])
                    
                    logger.info(f"Coordenadas encontradas: {lat}, {lon}")
                    return lat, lon
                
                # Aguardar entre requests (boas práticas Nominatim)
                time.sleep(1)
            
            logger.warning(f"Coordenadas não encontradas para: {endereco}")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na requisição Nominatim: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado na geocodificação: {e}")
            return None
    
    def geocodificar_por_cep(self, cep: str) -> Optional[Dict]:
        """
        Processo completo: CEP -> Endereço -> Coordenadas.
        
        Args:
            cep: CEP a ser geocodificado
            
        Returns:
            Dict com endereco e coordenadas ou None se erro
        """
        try:
            logger.info(f"Iniciando geocodificação completa para CEP: {cep}")
            
            # 1. Buscar endereço por CEP
            endereco = self.buscar_endereco_por_cep(cep)
            if not endereco:
                return None
            
            # 2. Geocodificar endereço
            coordenadas = self.geocodificar_endereco(endereco)
            if not coordenadas:
                return None
            
            # 3. Aplicar dispersão para evitar sobreposição
            coordenadas_dispersas = self.adicionar_jitter_coordenadas(
                coordenadas[0], 
                coordenadas[1],
                raio_metros=800  # Raio maior para CEPs
            )
            
            # 4. Combinar resultados
            resultado = {
                'endereco': endereco,
                'latitude': coordenadas_dispersas[0],
                'longitude': coordenadas_dispersas[1],
                'latitude_original': coordenadas[0],
                'longitude_original': coordenadas[1],
                'fonte': 'ViaCEP + OpenStreetMap Nominatim + Jitter'
            }
            
            logger.info(f"Geocodificação completa: {resultado['endereco']['cidade']}/{resultado['endereco']['estado']} -> {resultado['latitude']}, {resultado['longitude']}")
            
            return resultado
            
        except Exception as e:
            logger.error(f"Erro na geocodificação completa do CEP {cep}: {e}")
            return None


# Instância global do serviço
geocodificacao_service = GeocodificacaoService()


def geocodificar_cep(cep: str) -> Optional[Dict]:
    """
    Função de conveniência para geocodificação por CEP.
    
    Args:
        cep: CEP a ser geocodificado
        
    Returns:
        Dict com informações completas ou None
    """
    return geocodificacao_service.geocodificar_por_cep(cep)


def processar_cidadao_sem_localizacao(cidadao):
    """
    Processa cidadão que não tem LocalizacaoSaude.
    Tenta geocodificar usando CEP e criar LocalizacaoSaude.
    
    Args:
        cidadao: Instância do modelo Cidadao
        
    Returns:
        LocalizacaoSaude criada ou None
    """
    from .models import LocalizacaoSaude
    from .calculador_risco import calcular_risco_cidadao
    
    try:
        logger.info(f"Processando cidadão sem localização: {cidadao.nome}")
        
        # Verificar se já tem LocalizacaoSaude
        if LocalizacaoSaude.objects.filter(cidadao=cidadao).exists():
            logger.info(f"Cidadão {cidadao.nome} já possui localização")
            return None
        
        # Calcular risco baseado nos dados de saúde
        risco_calculado = calcular_risco_cidadao(cidadao)
        nivel_risco = risco_calculado['nivel']
        pontuacao_risco = int(risco_calculado['pontuacao'])
        
        logger.info(f"Risco calculado para {cidadao.nome}: {nivel_risco} ({pontuacao_risco})")
        
        # Tentar geocodificar por CEP
        if hasattr(cidadao, 'cep') and cidadao.cep:
            resultado = geocodificar_cep(cidadao.cep)
            
            if resultado:
                # Criar LocalizacaoSaude com risco calculado
                localizacao = LocalizacaoSaude.objects.create(
                    cidadao=cidadao,
                    latitude=resultado['latitude'],
                    longitude=resultado['longitude'],
                    endereco_completo=f"{resultado['endereco']['logradouro']}, {resultado['endereco']['bairro']}, {resultado['endereco']['cidade']}/{resultado['endereco']['estado']}",
                    cidade=resultado['endereco']['cidade'],
                    estado=resultado['endereco']['estado'],
                    cep=resultado['endereco']['cep'],
                    bairro=resultado['endereco']['bairro'],
                    nivel_risco=nivel_risco,
                    pontuacao_risco=pontuacao_risco,
                    ativo=True
                )
                
                logger.info(f"LocalizacaoSaude criada para {cidadao.nome}: {localizacao.id} (Risco: {nivel_risco})")
                return localizacao
        
        # Tentar geocodificar por cidade/estado
        if cidadao.cidade and cidadao.estado:
            endereco_fake = {
                'cidade': cidadao.cidade,
                'estado': cidadao.estado,
                'logradouro': '',
                'bairro': cidadao.bairro if hasattr(cidadao, 'bairro') else ''
            }
            
            coordenadas = geocodificacao_service.geocodificar_endereco(endereco_fake)
            
            if coordenadas:
                # Aplicar jitter também para coordenadas por cidade
                coordenadas_dispersas = geocodificacao_service.adicionar_jitter_coordenadas(
                    coordenadas[0], 
                    coordenadas[1],
                    raio_metros=1500  # Raio maior para cidades
                )
                
                localizacao = LocalizacaoSaude.objects.create(
                    cidadao=cidadao,
                    latitude=coordenadas_dispersas[0],
                    longitude=coordenadas_dispersas[1],
                    endereco_completo=f"{cidadao.cidade}/{cidadao.estado}",
                    cidade=cidadao.cidade,
                    estado=cidadao.estado,
                    bairro=cidadao.bairro if hasattr(cidadao, 'bairro') else '',
                    nivel_risco=nivel_risco,
                    pontuacao_risco=pontuacao_risco,
                    ativo=True
                )
                
                logger.info(f"LocalizacaoSaude criada por cidade para {cidadao.nome}: {localizacao.id} (Risco: {nivel_risco})")
                return localizacao
        
        logger.warning(f"Não foi possível geocodificar cidadão: {cidadao.nome}")
        return None
        
    except Exception as e:
        logger.error(f"Erro ao processar cidadão {cidadao.nome}: {e}")
        return None