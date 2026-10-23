"""Ordenação por valores reais, independente da formatação da tabela."""
from dados import normalizar

CHAVES = {
    'nome': lambda r: normalizar(r['nome']),
    'data': lambda r: r['aquisicao'],
    'custo': lambda r: r['custo'],
    'previsto': lambda r: r['previsto'],
    'lucro': lambda r: r['previsto'] - r['custo'],
    'conta': lambda r: normalizar(r['conta']),
    'previsao': lambda r: r['previsao'],
    'previsao_atual': lambda r: r['previsao_atual'],
    'recebido': lambda r: r['recebimento'],
}


def ordenar(registros, coluna=None, direcao=None):
    if coluna is None:
        return list(registros)
    chave = CHAVES[coluna]
    preenchidos = [r for r in registros if chave(r) is not None]
    vazios = [r for r in registros if chave(r) is None]
    return sorted(preenchidos, key=chave, reverse=direcao == 'desc') + vazios
