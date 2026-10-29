"""Gera celular/modelo.sqlite3: o banco vazio, criado pelo próprio programa, com que o app começa os dados de
quem usa só o celular. Assim as tabelas são exatamente as do computador (test_celular confere).

Rodar depois de qualquer mudança no esquema do banco: python gerar_modelo_celular.py
"""
import sqlite3
import tempfile
from pathlib import Path

from dados import Banco

DESTINO = Path(__file__).resolve().parent / 'celular' / 'modelo.sqlite3'


def gerar(destino=DESTINO):
    with tempfile.TemporaryDirectory() as pasta:
        caminho = Path(pasta) / 'modelo.sqlite3'
        Banco(caminho)
        con = sqlite3.connect(caminho)
        try:
            con.execute('DELETE FROM configuracoes')  # Nada deste computador vai para o modelo.
            con.commit()
            con.execute('VACUUM')
        finally:
            con.close()
        Path(destino).write_bytes(caminho.read_bytes())


if __name__ == '__main__':
    gerar()
