"""Persistência local. Valores monetários são armazenados em centavos."""
import os
import sqlite3
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


def pasta_dados():
    base = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share'))
    return base / 'GestorRPV'


def centavos(texto):
    texto = texto.strip().replace('R$', '').replace(' ', '')
    if ',' in texto:
        texto = texto.replace('.', '').replace(',', '.')
    try:
        valor = Decimal(texto)
        if not valor.is_finite() or valor < 0 or valor > Decimal('999999999999.99'):
            raise ValueError
        if valor != valor.quantize(Decimal('.01')):
            raise ValueError
        return int(valor * 100)
    except (InvalidOperation, ValueError):
        raise ValueError('Informe um valor positivo ou zero, com até duas casas decimais.') from None


def moeda(valor):
    inteiro, fracao = divmod(abs(valor), 100)
    prefixo = '-' if valor < 0 else ''
    return prefixo + f'{inteiro:,}'.replace(',', '.') + f',{fracao:02d}'


def data_iso(texto):
    try:
        return datetime.strptime(texto.strip(), '%d/%m/%Y').date().isoformat()
    except ValueError:
        raise ValueError('Informe uma data válida no formato DD/MM/AAAA.') from None


def data_br(texto):
    return datetime.strptime(texto, '%Y-%m-%d').strftime('%d/%m/%Y')


class Banco:
    def __init__(self, caminho=None):
        self.caminho = Path(caminho) if caminho else pasta_dados() / 'gestor.sqlite3'
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self.conectar() as con:
            con.execute('''CREATE TABLE IF NOT EXISTS rpvs (
                id INTEGER PRIMARY KEY,
                nome TEXT NOT NULL,
                aquisicao TEXT NOT NULL,
                previsto INTEGER NOT NULL CHECK(previsto >= 0),
                custo INTEGER NOT NULL CHECK(custo >= 0),
                conta TEXT NOT NULL CHECK(conta IN ('Vitor', 'Lilian')),
                previsao TEXT NOT NULL,
                comissao INTEGER CHECK(comissao >= 0),
                observacoes TEXT NOT NULL DEFAULT ''
            )''')

    def conectar(self):
        con = sqlite3.connect(self.caminho)
        con.row_factory = sqlite3.Row
        return con

    def salvar(self, dados, identificador=None):
        with self.conectar() as con:
            if identificador is None:
                cursor = con.execute('''INSERT INTO rpvs
                    (nome, aquisicao, previsto, custo, conta, previsao, comissao, observacoes)
                    VALUES (:nome, :aquisicao, :previsto, :custo, :conta, :previsao, :comissao, :observacoes)''', dados)
                return cursor.lastrowid
            con.execute('''UPDATE rpvs SET nome=:nome, aquisicao=:aquisicao,
                previsto=:previsto, custo=:custo, conta=:conta, previsao=:previsao,
                comissao=:comissao, observacoes=:observacoes WHERE id=:id''',
                dict(dados, id=identificador))
            return identificador

    def listar(self, busca=''):
        with self.conectar() as con:
            registros = con.execute('SELECT * FROM rpvs ORDER BY aquisicao DESC, id DESC').fetchall()
        return [r for r in registros if busca.casefold() in r['nome'].casefold()
                or busca in data_br(r['aquisicao'])]

    def obter(self, identificador):
        with self.conectar() as con:
            return con.execute('SELECT * FROM rpvs WHERE id=?', (identificador,)).fetchone()

    def excluir(self, identificador):
        with self.conectar() as con:
            con.execute('DELETE FROM rpvs WHERE id=?', (identificador,))
