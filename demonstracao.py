"""Dados fictícios carregados na primeira abertura, para apresentar o programa sem dados reais.

Nomes, CPFs, contas e chaves Pix são inventados; os CPFs apenas passam na conferência dos dígitos.
As datas acompanham o dia em que os dados são carregados, preservando o mesmo cenário de
operações pendentes, atrasadas e recebidas.
"""
import json
from datetime import date

from diario import log

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


def deve_carregar(banco, recomecar=False):
    """Somente em um banco recém-criado (ou cuja carga foi interrompida) e ainda vazio; quem já tem dados
    nunca recebe a demonstração."""
    return ((getattr(banco, 'novo', False) or recomecar) and not banco.contas() and not banco.listar()
            and not banco.listar_lixeira())


def ids_registrados(banco):
    """Registros fictícios anotados na configuração; qualquer coisa fora do formato (por exemplo, vinda de um
    backup adulterado) é tratada como lista vazia, em vez de travar quem salva ou apaga."""
    try:
        ids = json.loads(banco.configuracao(CHAVE) or 'null')
    except ValueError:
        return None
    if not isinstance(ids, dict):
        return None
    limpar = lambda chave: [i for i in ids.get(chave, []) if isinstance(i, int)] if isinstance(ids.get(chave), list) else []
    return {'operacoes': limpar('operacoes'), 'contas': limpar('contas'), 'carregando': ids.get('carregando') is True}


def anotar(banco, contas, operacoes, carregando=False):
    banco.salvar_configuracao(CHAVE, json.dumps({'operacoes': operacoes, 'contas': contas, 'carregando': carregando}))


def carregar(banco, hoje=None):
    deslocamento = (hoje or date.today()) - REFERENCIA

    def data(iso):
        return (date.fromisoformat(iso) + deslocamento).isoformat() if iso else None

    # Cada registro criado é anotado na hora: mesmo que o programa seja fechado à força no meio da carga,
    # a próxima abertura sabe o que é fictício e termina a limpeza (ver limpar_carga_interrompida).
    contas, operacoes = [], []
    anotar(banco, contas, operacoes, carregando=True)
    try:
        _carregar(banco, data, contas, operacoes)
    except BaseException:
        remover(banco)
        raise
    anotar(banco, contas, operacoes)


def limpar_carga_interrompida(banco):
    """Apaga o que uma carga interrompida deixou. Devolve True se havia o que limpar."""
    ids = ids_registrados(banco)
    if ids and ids['carregando']:
        remover(banco)
        return True
    return False


def _carregar(banco, data, contas, operacoes):
    for conta in CONTAS:
        contas.append(banco.salvar_conta(conta))
        anotar(banco, contas, operacoes, carregando=True)
    for nome, aquisicao, custo, total, conta, previsao, atual, recebimento in OPERACOES:
        identificador = banco.salvar(dict(nome=nome, aquisicao=data(aquisicao), custo=custo, previsto=total,
                                          conta_id=contas[conta], conta='', previsao=data(previsao),
                                          comissao=None, observacoes='Operação fictícia de demonstração.'))
        operacoes.append(identificador)
        anotar(banco, contas, operacoes, carregando=True)
        if atual:
            banco.atualizar_previsao(identificador, data(atual))
        if recebimento:
            banco.registrar_recebimento(identificador, data(recebimento))


def adotar(banco, operacao=None, conta=None):
    """Registro editado ou cadastrado pela pessoa deixa de ser fictício: "Apagar dados de demonstração" o preserva.

    Cobre também o número reaproveitado pelo SQLite depois de uma exclusão definitiva. Nunca falha: o registro
    já foi gravado, e um erro aqui não pode fazer a pessoa salvar de novo.
    """
    try:
        ids = ids_registrados(banco)
        if not ids:
            return
        novo = {'operacoes': [i for i in ids['operacoes'] if i != operacao], 'contas': [i for i in ids['contas'] if i != conta]}
        if novo['operacoes'] != ids['operacoes'] or novo['contas'] != ids['contas']:
            anotar(banco, novo['contas'], novo['operacoes'], ids['carregando'])
    except Exception:
        log.warning('Não foi possível marcar o registro como da pessoa.', exc_info=True)


def ativa(banco):
    return bool(banco.configuracao(CHAVE))


def operacoes_proprias_em_contas_ficticias(banco):
    """Quantas operações da pessoa usam uma conta fictícia (ficarão como "conta removida" ao apagar)."""
    ids = ids_registrados(banco)
    if not ids or not ids['contas']:
        return 0
    with banco.conectar() as con:
        usam = [r['id'] for r in con.execute(
            f'SELECT id FROM rpvs WHERE conta_id IN ({",".join("?" * len(ids["contas"]))})', ids['contas'])]
    return len([i for i in usam if i not in ids['operacoes']])


def remover(banco):
    """Apaga só o que a demonstração criou; operações cadastradas pela pessoa continuam intactas.

    Os números guardados na carga não bastam: depois de uma exclusão definitiva, o SQLite pode dar o mesmo
    número a um cadastro novo. Por isso só sai o registro que ainda está na lista (o que a pessoa salva pelo
    formulário ou com comprovante sai dela, em adotar) e ainda tem o nome fictício (operações) ou o CPF
    fictício (contas). Os anexos das operações apagadas saem junto. Se uma operação própria usar uma conta de
    demonstração, ela preserva a cópia dos dados bancários, como em qualquer conta removida.
    """
    ids = ids_registrados(banco)
    if ids is None:
        banco.remover_configuracao(CHAVE)
        return
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
