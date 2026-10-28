"""Dados fictícios carregados na primeira abertura, para apresentar o programa sem dados reais.

Nomes, CPFs, contas e chaves Pix são inventados; os CPFs apenas passam na conferência dos dígitos.
As datas acompanham o dia em que os dados são carregados, preservando o mesmo cenário de
operações pendentes, atrasadas e recebidas.
"""
import json
from datetime import date

CHAVE = 'dados_demonstracao'
REFERENCIA = date(2026, 10, 24)

CONTAS = (
    dict(identificacao='Conta principal', nome='Rafael Monteiro Duarte', cpf='31415926590',
         endereco='Rua Das Palmeiras', numero_endereco='120', cidade='Campinas', estado='SP',
         banco='Banco Exemplo', agencia='0001', numero='12345-6', pix='rafael.duarte@exemplo.com'),
    dict(identificacao='Conta reserva', nome='Juliana Prado Nogueira', cpf='27182818205',
         endereco='Avenida Central', numero_endereco='45', cidade='Belo Horizonte', estado='MG',
         banco='Banco Modelo', agencia='0420', numero='98765-4', pix='juliana.nogueira@exemplo.com'),
)

# nome, aquisição, custo, total, conta, previsão inicial, previsão atual (ou None), recebimento (ou None);
# datas em relação a REFERENCIA.
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


def deve_carregar(banco):
    """Somente em um banco recém-criado e ainda vazio; quem já tem dados nunca recebe a demonstração."""
    return getattr(banco, 'novo', False) and not banco.contas() and not banco.listar() and not banco.listar_lixeira()


def carregar(banco, hoje=None):
    deslocamento = (hoje or date.today()) - REFERENCIA

    def data(iso):
        return (date.fromisoformat(iso) + deslocamento).isoformat() if iso else None

    contas = [banco.salvar_conta(conta) for conta in CONTAS]
    operacoes = []
    for nome, aquisicao, custo, total, conta, previsao, atual, recebimento in OPERACOES:
        identificador = banco.salvar(dict(nome=nome, aquisicao=data(aquisicao), custo=custo, previsto=total,
                                          conta_id=contas[conta], conta='', previsao=data(previsao),
                                          comissao=None, observacoes='Operação fictícia de demonstração.'))
        if atual:
            banco.atualizar_previsao(identificador, data(atual))
        if recebimento:
            banco.registrar_recebimento(identificador, data(recebimento))
        operacoes.append(identificador)
    banco.salvar_configuracao(CHAVE, json.dumps({'operacoes': operacoes, 'contas': contas}))


def ativa(banco):
    return bool(banco.configuracao(CHAVE))


def remover(banco):
    """Apaga só o que a demonstração criou; operações cadastradas pela pessoa continuam intactas.

    Os números guardados na carga não bastam: depois de uma exclusão definitiva, o SQLite pode dar o mesmo
    número a um cadastro novo. Por isso só sai o registro que ainda tem o nome fictício (operações) ou o CPF
    fictício (contas) da demonstração. Os anexos das operações apagadas saem junto.
    Se uma operação própria usar uma conta de demonstração, ela preserva a cópia dos dados bancários,
    como em qualquer conta removida.
    """
    registro = banco.configuracao(CHAVE)
    if not registro:
        return
    ids = json.loads(registro)
    nomes = {operacao[0] for operacao in OPERACOES}
    cpfs = {conta['cpf'] for conta in CONTAS}
    with banco.arquivos_para_excluir() as preparar, banco.conectar() as con:
        con.execute('BEGIN IMMEDIATE')
        operacoes = [i for i in ids['operacoes']
                     if (linha := con.execute('SELECT nome FROM rpvs WHERE id=?', (i,)).fetchone()) and linha['nome'] in nomes]
        contas = [i for i in ids['contas']
                  if (linha := con.execute('SELECT cpf FROM contas WHERE id=?', (i,)).fetchone()) and linha['cpf'] in cpfs]
        for identificador in operacoes:
            preparar(con.execute('SELECT * FROM documentos WHERE rpv_id=?', (identificador,)).fetchall())
        con.executemany('DELETE FROM rpvs WHERE id=?', [(i,) for i in operacoes])
        con.executemany('UPDATE rpvs SET conta_id=NULL WHERE conta_id=?', [(i,) for i in contas])
        con.executemany('DELETE FROM contas WHERE id=?', [(i,) for i in contas])
        con.execute('DELETE FROM configuracoes WHERE chave=?', (CHAVE,))
