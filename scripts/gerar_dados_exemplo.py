"""Gera um backup .rpvbackup com dados fictícios para demonstração.

Uso: python scripts/gerar_dados_exemplo.py [pasta_de_saida]
O arquivo pode ser importado em Minhas operações → Arquivo → Importar dados.
Nomes, CPFs, contas e chaves Pix são inventados; os CPFs apenas passam na conferência dos dígitos.
"""
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from backup import criar_backup  # noqa: E402
from dados import Banco  # noqa: E402

CONTAS = (
    dict(identificacao='Conta principal', nome='Rafael Monteiro Duarte', cpf='31415926590',
         endereco='Rua Das Palmeiras', numero_endereco='120', cidade='Campinas', estado='SP',
         banco='Banco Exemplo', agencia='0001', numero='12345-6', pix='rafael.duarte@exemplo.com'),
    dict(identificacao='Conta reserva', nome='Juliana Prado Nogueira', cpf='27182818205',
         endereco='Avenida Central', numero_endereco='45', cidade='Belo Horizonte', estado='MG',
         banco='Banco Modelo', agencia='0420', numero='98765-4', pix='juliana.nogueira@exemplo.com'),
)

# nome, aquisição, custo, total, conta, previsão inicial, previsão atual (ou None), recebimento (ou None)
OPERACOES = (
    ('Helena Batista Correia', '2026-10-09', 530000, 800000, 0, '2026-10-29', None, None),
    ('Otavio Lins Carvalho', '2026-10-09', 530000, 800000, 0, '2026-10-29', None, None),
    ('Beatriz Fontes Sampaio', '2026-09-02', 1300000, 2000000, 0, '2026-09-17', '2026-10-08', None),
    ('Caio Mendes Rocha', '2026-09-01', 1300000, 2000000, 0, '2026-09-17', '2026-10-14', None),
    ('Lorena Vidal Araujo', '2026-08-31', 1300000, 2000000, 0, '2026-09-10', '2026-11-12', None),
    ('Mateus Queiroz Lima', '2026-08-28', 700000, 1200000, 0, '2026-09-18', '2026-10-02', '2026-10-07'),
    ('Tais Moreira Bastos', '2026-08-28', 1200000, 2000000, 0, '2026-09-15', None, None),
    ('Igor Siqueira Pacheco', '2026-08-27', 1200000, 2000000, 1, '2026-09-11', '2026-10-30', None),
    ('Natalia Freitas Couto', '2026-08-27', 1100000, 2000000, 0, '2026-09-17', '2026-10-27', None),
    ('Diego Barreto Leal', '2026-08-27', 1100000, 2000000, 0, '2026-09-17', None, None),
    ('Priscila Antunes Mota', '2026-08-24', 1300000, 2000000, 0, '2026-08-28', '2026-09-02', '2026-09-02'),
    ('Renato Tavares Cunha', '2026-08-24', 1300000, 2000000, 0, '2026-08-28', None, '2026-08-28'),
    ('Sofia Calixto Ramos', '2026-08-24', 1300000, 2000000, 0, '2026-08-28', None, '2026-08-28'),
)


def gerar(saida):
    with tempfile.TemporaryDirectory() as pasta:
        banco = Banco(Path(pasta) / 'gestor.sqlite3')
        contas = [banco.salvar_conta(conta) for conta in CONTAS]
        for nome, aquisicao, custo, total, conta, previsao, atual, recebimento in OPERACOES:
            identificador = banco.salvar(dict(nome=nome, aquisicao=aquisicao, custo=custo, previsto=total,
                                              conta_id=contas[conta], conta='', previsao=previsao,
                                              comissao=None, observacoes='Dados fictícios para demonstração.'))
            if atual:
                banco.atualizar_previsao(identificador, atual)
            if recebimento:
                banco.registrar_recebimento(identificador, recebimento)
        arquivo = criar_backup(banco, pasta)
        destino = Path(saida) / 'GestorRPV-dados-ficticios.rpvbackup'
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(arquivo.read_bytes())
    return destino


if __name__ == '__main__':
    print(gerar(sys.argv[1] if len(sys.argv) > 1 else RAIZ / 'exemplos'))
