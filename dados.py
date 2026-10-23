"""Persistência local. Valores monetários são armazenados em centavos."""
import os
import json
import re
import unicodedata
from contextlib import contextmanager
import sqlite3
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from pathlib import Path


def pasta_dados():
    base = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share'))
    return base / 'GestorRPV'


def centavos(texto):
    texto = texto.strip().replace('R$', '').replace(' ', '')
    if ',' in texto:
        texto = texto.replace('.', '').replace(',', '.')
    elif '.' in texto:
        partes = texto.split('.')
        if 1 <= len(partes[0]) <= 3 and all(len(p) == 3 and p.isdigit() for p in partes[1:]):
            texto = ''.join(partes)
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


def nome_formatado(texto):
    return ' '.join(texto.split()).title()


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', texto).casefold()
                   if c.isalnum() and not unicodedata.combining(c))


def validar_cpf(texto):
    if not texto.strip():
        raise ValueError('Informe o CPF.')
    if re.search(r'[^0-9.\-\s]', texto):
        raise ValueError('CPF inválido.')
    cpf = re.sub(r'\D', '', texto)
    if len(cpf) != 11 or len(set(cpf)) == 1:
        raise ValueError('CPF inválido.')
    for tamanho in (9, 10):
        resto = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho)) * 10 % 11
        if int(cpf[tamanho]) != (0 if resto == 10 else resto):
            raise ValueError('CPF inválido.')
    return cpf


def chave_pix(texto):
    texto = texto.strip().casefold()
    if re.fullmatch(r'[0-9+ ().-]+', texto):
        return re.sub(r'\D', '', texto)
    return texto


class Banco:
    def __init__(self, caminho=None):
        self.caminho = Path(caminho) if caminho else pasta_dados() / 'gestor.sqlite3'
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self.conectar() as con:
            colunas = {r['name'] for r in con.execute('PRAGMA table_info(rpvs)')}
        if colunas and ('conta_id' not in colunas or 'recebimento' not in colunas):
            versao_backup = '0.4.0' if 'conta_id' not in colunas else '0.6.0'
            backup = self.caminho.with_name(f'backup-antes-{versao_backup}-' +
                datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
            with self.conectar() as origem:
                destino = sqlite3.connect(backup)
                try:
                    origem.backup(destino)
                finally:
                    destino.close()
        with self.conectar() as con:
            con.execute('BEGIN IMMEDIATE')
            con.execute('''CREATE TABLE IF NOT EXISTS contas (
                id INTEGER PRIMARY KEY, identificacao TEXT NOT NULL,
                identificacao_chave TEXT NOT NULL UNIQUE,
                nome TEXT NOT NULL DEFAULT '', cpf TEXT UNIQUE,
                endereco TEXT NOT NULL DEFAULT '', banco TEXT NOT NULL DEFAULT '',
                agencia TEXT NOT NULL DEFAULT '', numero TEXT NOT NULL DEFAULT '',
                pix TEXT NOT NULL DEFAULT '', ativa INTEGER NOT NULL DEFAULT 1,
                banco_chave TEXT, agencia_chave TEXT, numero_chave TEXT,
                UNIQUE(banco_chave, agencia_chave, numero_chave))''')
            for nome in (('Vitor', 'Lilian') if not colunas or 'conta_id' not in colunas else ()):
                con.execute('''INSERT OR IGNORE INTO contas (identificacao, identificacao_chave)
                               VALUES (?, ?)''', (nome, normalizar(nome)))
            if colunas and 'conta_id' not in colunas:
                self.criar_rpvs(con, 'rpvs_nova')
                for r in con.execute('SELECT * FROM rpvs').fetchall():
                    conta = con.execute('SELECT * FROM contas WHERE identificacao=?', (r['conta'],)).fetchone()
                    con.execute('''INSERT INTO rpvs_nova
                        (id,nome,aquisicao,previsto,custo,conta,previsao,comissao,observacoes,conta_id,conta_snapshot)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                        tuple(r[k] for k in ('id','nome','aquisicao','previsto','custo','conta','previsao','comissao','observacoes')) +
                        (conta['id'], self.snapshot(conta)))
                con.execute('DROP TABLE rpvs')
                con.execute('ALTER TABLE rpvs_nova RENAME TO rpvs')
            else:
                self.criar_rpvs(con, 'rpvs')
            con.execute('''CREATE TABLE IF NOT EXISTS prorrogacoes (
                id INTEGER PRIMARY KEY, rpv_id INTEGER NOT NULL REFERENCES rpvs(id) ON DELETE CASCADE,
                data TEXT NOT NULL, criada_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(rpv_id, data))''')
            atuais = {r['name'] for r in con.execute('PRAGMA table_info(rpvs)')}
            if 'recebimento' not in atuais:
                con.execute('ALTER TABLE rpvs ADD COLUMN recebimento TEXT')
            con.execute('PRAGMA user_version=2')

    @staticmethod
    def criar_rpvs(con, tabela):
        # tabela é sempre uma constante interna, nunca entrada do usuário.
        con.execute(f'''CREATE TABLE IF NOT EXISTS {tabela} (
            id INTEGER PRIMARY KEY, nome TEXT NOT NULL, aquisicao TEXT NOT NULL,
            previsto INTEGER NOT NULL CHECK(previsto >= 0),
            custo INTEGER NOT NULL CHECK(custo >= 0), conta TEXT NOT NULL,
            previsao TEXT NOT NULL, comissao INTEGER CHECK(comissao >= 0),
            observacoes TEXT NOT NULL DEFAULT '',
            conta_id INTEGER NOT NULL REFERENCES contas(id), conta_snapshot TEXT NOT NULL, recebimento TEXT)''')

    @contextmanager
    def conectar(self):
        con = sqlite3.connect(self.caminho)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        try:
            with con:
                yield con
        finally:
            con.close()

    @staticmethod
    def snapshot(conta):
        campos = ('identificacao', 'nome', 'cpf', 'endereco', 'banco', 'agencia', 'numero', 'pix')
        return json.dumps({k: conta[k] for k in campos}, ensure_ascii=False)

    def contas(self, somente_ativas=False):
        with self.conectar() as con:
            return con.execute('SELECT * FROM contas' + (' WHERE ativa=1' if somente_ativas else '') +
                               ' ORDER BY identificacao COLLATE NOCASE').fetchall()

    def obter_conta(self, identificador):
        with self.conectar() as con:
            return con.execute('SELECT * FROM contas WHERE id=?', (identificador,)).fetchone()

    def salvar_conta(self, dados, identificador=None):
        dados = {k: dados.get(k, '').strip() for k in
                 ('identificacao', 'nome', 'cpf', 'endereco', 'banco', 'agencia', 'numero', 'pix')}
        for campo in ('identificacao', 'nome', 'cpf', 'endereco', 'banco', 'numero', 'pix'):
            if not dados[campo]:
                raise ValueError('Preencha identificação, nome completo, CPF, endereço, banco, conta e chave Pix.')
        dados['nome'] = nome_formatado(dados['nome'])
        dados['endereco'] = nome_formatado(dados['endereco'])
        for campo in ('identificacao', 'endereco', 'banco'):
            dados[campo] = dados[campo][:1].upper() + dados[campo][1:]
        dados['cpf'] = validar_cpf(dados['cpf'])
        dados['identificacao_chave'] = normalizar(dados['identificacao'])
        dados['banco_chave'] = normalizar(dados['banco'])
        dados['agencia_chave'] = (normalizar(dados['agencia']).lstrip('0') or '0') if dados['agencia'] else ''
        dados['numero_chave'] = normalizar(dados['numero']).lstrip('0') or '0'
        if not all(dados[k] for k in ('identificacao_chave', 'banco_chave', 'numero_chave')):
            raise ValueError('Confira a identificação, o banco e a conta.')
        with self.conectar() as con:
            con.execute('BEGIN IMMEDIATE')
            for conta in con.execute('SELECT * FROM contas WHERE id != ?', (identificador or -1,)):
                if conta['identificacao_chave'] == dados['identificacao_chave']:
                    raise ValueError('Já existe uma conta com essa identificação, inclusive entre as desativadas.')
                if dados['cpf'] and conta['cpf'] == dados['cpf']:
                    raise ValueError('Esse CPF já está cadastrado em outra conta.')
                if (conta['banco_chave'] == dados['banco_chave'] and conta['numero_chave'] == dados['numero_chave']
                    and (not conta['agencia_chave'] or not dados['agencia_chave'] or conta['agencia_chave'] == dados['agencia_chave'])):
                    raise ValueError('Essa conta bancária já está cadastrada.')
                if chave_pix(conta['pix']) and chave_pix(conta['pix']) == chave_pix(dados['pix']):
                    raise ValueError('Essa chave Pix já está cadastrada em outra conta.')
            if identificador is None:
                campos = ','.join(dados)
                valores = ','.join(':' + k for k in dados)
                return con.execute(f'INSERT INTO contas ({campos}) VALUES ({valores})', dados).lastrowid
            atribuicoes = ','.join(k + '=:' + k for k in dados)
            con.execute(f'UPDATE contas SET {atribuicoes} WHERE id=:id', dict(dados, id=identificador))
            return identificador

    def ativar_conta(self, identificador, ativa):
        with self.conectar() as con:
            con.execute('UPDATE contas SET ativa=? WHERE id=?', (int(ativa), identificador))

    def remover_conta(self, identificador):
        with self.conectar() as con:
            con.execute('BEGIN IMMEDIATE')
            if con.execute('SELECT 1 FROM rpvs WHERE conta_id=? LIMIT 1', (identificador,)).fetchone():
                raise ValueError('Esta conta está vinculada a uma RPV. Use Desativar para preservar o histórico.')
            con.execute('DELETE FROM contas WHERE id=?', (identificador,))

    def salvar(self, dados, identificador=None):
        dados = dict(dados)
        dados['nome'] = nome_formatado(dados['nome'])
        dados['observacoes'] = dados['observacoes'][:1].upper() + dados['observacoes'][1:]
        if not dados['nome']:
            raise ValueError('Informe o nome completo do titular original.')
        if dados['custo'] <= 0:
            raise ValueError('O valor de aquisição deve ser maior que zero.')
        if dados['custo'] > dados['previsto']:
            raise ValueError('O valor de aquisição não pode superar o recebimento previsto.')
        with self.conectar() as con:
            anterior = con.execute('SELECT * FROM rpvs WHERE id=?', (identificador,)).fetchone() if identificador else None
            if 'conta_id' in dados:
                conta = con.execute('SELECT * FROM contas WHERE id=?', (dados['conta_id'],)).fetchone()
            else:
                conta = con.execute('SELECT * FROM contas WHERE identificacao=?', (dados['conta'],)).fetchone()
            if conta is None:
                raise ValueError('Selecione uma conta cadastrada.')
            mesma_conta = anterior is not None and anterior['conta_id'] == conta['id']
            if not conta['ativa'] and not mesma_conta:
                raise ValueError('A conta foi desativada. Selecione uma conta ativa.')
            dados['conta_id'] = conta['id']
            dados['conta'] = anterior['conta'] if mesma_conta else conta['identificacao']
            dados['conta_snapshot'] = anterior['conta_snapshot'] if mesma_conta else self.snapshot(conta)
            campos = ('nome','aquisicao','previsto','custo','conta','previsao','comissao','observacoes','conta_id','conta_snapshot')
            if anterior:
                if anterior['recebimento'] and dados['aquisicao'] > anterior['recebimento']:
                    raise ValueError('A aquisição não pode ser posterior à data do recebimento.')
                ultima = con.execute('SELECT MIN(data) FROM prorrogacoes WHERE rpv_id=?', (identificador,)).fetchone()[0]
                if ultima and dados['previsao'] >= ultima:
                    raise ValueError('A previsão inicial deve ser anterior às prorrogações já registradas.')
            if identificador is None:
                return con.execute('INSERT INTO rpvs (' + ','.join(campos) + ') VALUES (' +
                                   ','.join(':' + k for k in campos) + ')', dados).lastrowid
            con.execute('UPDATE rpvs SET ' + ','.join(k + '=:' + k for k in campos) + ' WHERE id=:id',
                        dict(dados, id=identificador))
            return identificador

    def listar(self, busca=''):
        with self.conectar() as con:
            registros = con.execute('''SELECT r.*,
                COALESCE((SELECT MAX(data) FROM prorrogacoes WHERE rpv_id=r.id), r.previsao) AS previsao_atual,
                (SELECT COUNT(*) FROM prorrogacoes WHERE rpv_id=r.id) AS total_prorrogacoes
                FROM rpvs r ORDER BY aquisicao DESC, id DESC''').fetchall()
        return [r for r in registros if busca.casefold() in r['nome'].casefold() or busca in data_br(r['aquisicao'])]

    def obter(self, identificador):
        with self.conectar() as con:
            return con.execute('SELECT * FROM rpvs WHERE id=?', (identificador,)).fetchone()

    def excluir(self, identificador):
        with self.conectar() as con:
            con.execute('DELETE FROM rpvs WHERE id=?', (identificador,))

    def prorrogacoes(self, identificador):
        with self.conectar() as con:
            return con.execute('SELECT * FROM prorrogacoes WHERE rpv_id=? ORDER BY data, id', (identificador,)).fetchall()

    def prorrogar(self, identificador, nova_data):
        # Validação também na persistência, independente da interface.
        nova_data = data_iso(data_br(nova_data))
        with self.conectar() as con:
            con.execute('BEGIN IMMEDIATE')
            rpv = con.execute('SELECT * FROM rpvs WHERE id=?', (identificador,)).fetchone()
            if rpv is None:
                raise ValueError('Registro não encontrado.')
            ultima = con.execute('SELECT MAX(data) FROM prorrogacoes WHERE rpv_id=?', (identificador,)).fetchone()[0]
            if nova_data <= max(ultima or rpv['previsao'], rpv['aquisicao'], rpv['previsao']):
                raise ValueError('A nova previsão deve ser posterior à previsão atual e à aquisição.')
            con.execute('INSERT INTO prorrogacoes (rpv_id, data) VALUES (?,?)', (identificador, nova_data))

    def registrar_recebimento(self, identificador, data):
        if data is not None:
            data = data_iso(data_br(data))
        with self.conectar() as con:
            registro = con.execute('SELECT * FROM rpvs WHERE id=?', (identificador,)).fetchone()
            if registro is None:
                raise ValueError('Registro não encontrado.')
            if data is not None:
                if data < registro['aquisicao']:
                    raise ValueError('O recebimento não pode ser anterior à aquisição.')
                if data > date.today().isoformat():
                    raise ValueError('O recebimento não pode estar no futuro.')
            con.execute('UPDATE rpvs SET recebimento=? WHERE id=?', (data, identificador))
