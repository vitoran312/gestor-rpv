"""Dados e bancos de exemplo usados pelos testes."""
from dados import Banco


def dados_rpv(**valores):
    dados = dict(nome='pessoa DE teste', aquisicao='2026-10-22', previsto=2000000,
                 custo=1200000, conta='Vitor', previsao='2026-12-20', comissao=None, observacoes='')
    dados.update(valores)
    return dados


SENHA_TESTE = 'senha-de-teste'


def prorrogacao_antiga(banco, rpv, data):
    """Prorrogação no formato das versões até a 0.6, que ainda pode existir em bancos antigos."""
    with banco.conectar() as con:
        con.execute('INSERT INTO prorrogacoes (rpv_id, data) VALUES (?, ?)', (rpv, data))


def banco_com_contas(caminho):
    """Banco novo com as contas usadas nos dados de exemplo dos testes e a senha dos backups definida."""
    banco = Banco(caminho)
    banco.salvar_configuracao('senha_backup', SENHA_TESTE)
    with banco.conectar() as con:
        for nome in ('Vitor', 'Lilian'):
            con.execute('INSERT OR IGNORE INTO contas (identificacao, identificacao_chave) VALUES (?, ?)',
                        (nome, nome.casefold()))
    return banco


def dados_conta(**valores):
    dados = dict(identificacao='Conta teste', nome='titular DE teste', cpf='52998224725', endereco='Endereço compartilhado', numero_endereco='12', cidade='Cidade Teste', estado='SP',
                 banco='Banco Teste', agencia='0001', numero='12345-6', pix='teste@example.com')
    dados.update(valores)
    return dados
