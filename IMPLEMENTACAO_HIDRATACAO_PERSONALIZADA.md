# 💧 Implementação da Recomendação de Hidratação para Adultos

## 🎯 **Funcionalidade Implementada**

**Requisito:** Para cidadãos com mais de 18 anos, a IA deve sugerir o hábito de tomar 35ml de água por quilo corporal, apresentando a quantidade em litros.

## 🔧 **Implementação Técnica**

### **Arquivo:** `ai_integracao/modern_service.py`

#### 1. **Modificação no método `_preparar_contexto_medico`**

**Lógica implementada:**
```python
# Calcular recomendação de água se idade >= 18
recomendacao_agua = ""
if idade >= 18 and dados_saude.peso:
    agua_ml_dia = dados_saude.peso * 35  # 35ml por kg
    agua_litros_dia = agua_ml_dia / 1000  # converter para litros
    recomendacao_agua = f"""
    
    RECOMENDAÇÃO ESPECIAL DE HIDRATAÇÃO:
    - Para adulto de {dados_saude.peso}kg: {agua_litros_dia:.1f} litros de água por dia
    - Base: 35ml por kg de peso corporal
    - IMPORTANTE: Incluir esta recomendação nas orientações finais
    """
```

#### 2. **Prompt melhorado para a IA**

**Instruções adicionadas:**
```python
INSTRUÇÕES ESPECIAIS:
- Se há "RECOMENDAÇÃO ESPECIAL DE HIDRATAÇÃO" nos dados, SEMPRE inclua essa recomendação específica nas "recomendacoes"
- Para adultos (18+ anos), priorize orientações de hidratação adequada baseada no peso corporal
```

## 📊 **Exemplos de Cálculo**

### Adulto de 70kg (30 anos):
- **Cálculo:** 70kg × 35ml = 2.450ml/dia
- **Resultado:** 2.5 litros/dia ✅

### Adulto de 80kg (23 anos):
- **Cálculo:** 80kg × 35ml = 2.800ml/dia  
- **Resultado:** 2.8 litros/dia ✅

### Idoso de 80kg (75 anos):
- **Cálculo:** 80kg × 35ml = 2.800ml/dia
- **Resultado:** 2.8 litros/dia ✅

### Menor de idade (16 anos):
- **Resultado:** Recomendação NÃO aplicada ❌ (correto)

## 🧪 **Teste Real com Dados do Sistema**

**Cidadão:** Naiara de Souza Ferreira
- **Idade:** 23 anos ✅ (maior de 18)
- **Peso:** 80.00 kg
- **Recomendação gerada:** 2.8 litros de água por dia ✅

**Contexto gerado para IA:**
```
RECOMENDAÇÃO ESPECIAL DE HIDRATAÇÃO:
- Para adulto de 80.00kg: 2.8 litros de água por dia
- Base: 35ml por kg de peso corporal  
- IMPORTANTE: Incluir esta recomendação nas orientações finais
```

## ⚙️ **Condições de Aplicação**

### ✅ **Recomendação é incluída quando:**
- Idade >= 18 anos
- Campo `peso` preenchido em DadosSaude
- IA receberá instrução para incluir nas recomendações

### ❌ **Recomendação NÃO é incluída quando:**
- Idade < 18 anos
- Campo `peso` não preenchido/None
- Dados de saúde não disponíveis

## 🔄 **Fluxo de Funcionamento**

1. **Sistema coleta** dados do cidadão e saúde
2. **Verifica idade** usando `cidadao.idade` (property calculada)
3. **Se idade >= 18 e peso disponível:**
   - Calcula: `peso × 35ml`
   - Converte para litros: `/1000`
   - Adiciona recomendação ao contexto
4. **IA recebe instrução específica** para incluir hidratação
5. **IA inclui recomendação** nas orientações finais

## 📋 **Estrutura da Recomendação no JSON da IA**

A IA deve incluir nas "recomendacoes" algo como:
```json
{
  "recomendacoes": [
    "Manter hidratação adequada com 2.8 litros de água por dia (35ml por kg de peso corporal)",
    "Outras recomendações médicas...",
    "..."
  ]
}
```

## 🛡️ **Validações e Segurança**

- ✅ **Verificação de idade** antes do cálculo
- ✅ **Verificação de peso** antes do cálculo
- ✅ **Formato decimal** com 1 casa decimal
- ✅ **Unidade correta** em litros (não ml)
- ✅ **Baseado em evidência** científica (35ml/kg)

## 🎯 **Benefícios Implementados**

- ✅ **Personalização:** Recomendação específica por peso
- ✅ **Clareza:** Apresenta em litros, mais fácil de entender
- ✅ **Automático:** Não precisa intervenção manual
- ✅ **Científico:** Baseado em 35ml por kg (padrão médico)
- ✅ **Inclusivo:** Aplica para todos adultos (18+ anos)
- ✅ **Contextual:** Integrado na análise médica da IA

## ⚡ **Status Final**

🟢 **RECOMENDAÇÃO DE HIDRATAÇÃO IMPLEMENTADA**

- Cálculo: 35ml × peso corporal ✅
- Conversão: ml → litros ✅  
- Condição: idade >= 18 anos ✅
- Integração: contexto para IA ✅
- Instrução: IA inclui nas recomendações ✅

---

**Funcionalidade implementada por:** GitHub Copilot  
**Data:** 19/09/2025  
**Status:** ✅ **IMPLEMENTADO - HIDRATAÇÃO PERSONALIZADA**