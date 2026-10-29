"""Gera os bancos que acompanham o app do celular, criados pelo próprio programa (as tabelas são exatamente as
do computador; test_celular confere):

- celular/modelo.sqlite3: o banco vazio com que começam os dados de quem usa só o celular;
- celular/demonstracao.sqlite3: os dados fictícios de demonstracao.py, mostrados na primeira abertura do app,
  antes de a pessoa ter dados. As datas ficam as de demonstracao.REFERENCIA (gravada na configuração
  demonstracao_referencia); o app as desloca para o dia em que é aberto, como o programa faz na carga.

Rodar depois de qualquer mudança no esquema do banco ou nos dados fictícios: python gerar_modelo_celular.py
"""
import sqlite3
import tempfile
from pathlib import Path

import demonstracao
from dados import Banco

DESTINO = Path(__file__).resolve().parent / 'celular' / 'modelo.sqlite3'
DESTINO_DEMONSTRACAO = DESTINO.parent / 'demonstracao.sqlite3'
REFERENCIA = 'demonstracao_referencia'


def gerar(destino=DESTINO, com_demonstracao=False):
    with tempfile.TemporaryDirectory() as pasta:
        caminho = Path(pasta) / 'modelo.sqlite3'
        banco = Banco(caminho)
        if com_demonstracao:
            demonstracao.carregar(banco, hoje=demonstracao.REFERENCIA)
        con = sqlite3.connect(caminho)
        try:
            # Nada deste computador vai para o arquivo; a demonstração só leva a própria marca e a data das datas.
            con.execute('DELETE FROM configuracoes WHERE chave != ?', (demonstracao.CHAVE,))
            if com_demonstracao:
                con.execute('INSERT INTO configuracoes (chave, valor) VALUES (?, ?)',
                            (REFERENCIA, demonstracao.REFERENCIA.isoformat()))
            con.commit()
            con.execute('VACUUM')
        finally:
            con.close()
        Path(destino).write_bytes(caminho.read_bytes())


if __name__ == '__main__':
    gerar()
    gerar(DESTINO_DEMONSTRACAO, com_demonstracao=True)
