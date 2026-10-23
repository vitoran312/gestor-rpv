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


ESTADOS = ('AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS',
           'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO')

CONSULTA_RPVS = '''SELECT r.*,
    COALESCE(r.previsao_atual_definida,
        (SELECT MAX(data) FROM prorrogacoes WHERE rpv_id=r.id), r.previsao) AS previsao_atual,
    (SELECT COUNT(*) FROM prorrogacoes WHERE rpv_id=r.id) AS total_prorrogacoes
    FROM rpvs r'''


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
            colunas_contas = {r['name'] for r in con.execute('PRAGMA table_info(contas)')}
            cpf_unico = self.cpf_unico(con)
        migrar = ('previsao_atual_definida' not in colunas or 'recebimento' not in colunas or
                  not {'numero_endereco', 'cidade', 'estado'}.issubset(colunas_contas) or
                  'lixeira_em' not in colunas or cpf_unico)
        if colunas and migrar:
            versao_backup = ('0.4.0' if 'conta_id' not in colunas else
                             '0.6.0' if 'recebimento' not in colunas else
                             '0.7.0' if 'previsao_atual_definida' not in colunas or
                             not {'numero_endereco', 'cidade', 'estado'}.issubset(colunas_contas) else '0.9.0')
            backup = self.caminho.with_name(f'backup-antes-{versao_backup}-' +
                datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
            with self.conectar() as origem:
                destino = sqlite3.connect(backup)
                try:
                    origem.backup(destino)
                finally:
                    destino.close()
        with self.conectar() as con:
            # Recriação de contas preserva os IDs referenciados por RPVs.
            con.execute('PRAGMA foreign_keys=OFF')
            con.execute('BEGIN IMMEDIATE')
            con.execute('''CREATE TABLE IF NOT EXISTS contas (
                id INTEGER PRIMARY KEY, identificacao TEXT NOT NULL,
                identificacao_chave TEXT NOT NULL UNIQUE,
                nome TEXT NOT NULL DEFAULT '', cpf TEXT,
                endereco TEXT NOT NULL DEFAULT '', numero_endereco TEXT NOT NULL DEFAULT '',
                cidade TEXT NOT NULL DEFAULT '', estado TEXT NOT NULL DEFAULT '', banco TEXT NOT NULL DEFAULT '',
                agencia TEXT NOT NULL DEFAULT '', numero TEXT NOT NULL DEFAULT '',
                pix TEXT NOT NULL DEFAULT '', ativa INTEGER NOT NULL DEFAULT 1,
                banco_chave TEXT, agencia_chave TEXT, numero_chave TEXT,
                UNIQUE(banco_chave, agencia_chave, numero_chave))''')
            existentes = {r['name'] for r in con.execute('PRAGMA table_info(contas)')}
            for campo in ('numero_endereco', 'cidade', 'estado'):
                if campo not in existentes:
                    con.execute(f"ALTER TABLE contas ADD COLUMN {campo} TEXT NOT NULL DEFAULT ''")
            if cpf_unico:
                esquema = con.execute("SELECT sql FROM sqlite_master WHERE name='contas'").fetchone()[0]
                # O esquema legado é interno ao aplicativo; só removemos a unicidade do CPF.
                esquema = re.sub(r'^CREATE TABLE\s+(?:IF NOT EXISTS\s+)?[\"`\[]?contas[\"`\]]?',
                                 'CREATE TABLE contas_nova', esquema, count=1, flags=re.IGNORECASE)
                esquema = re.sub(r'\bcpf\s+TEXT\s+UNIQUE\b', 'cpf TEXT', esquema, flags=re.IGNORECASE)
                con.execute(esquema)
                campos = ','.join(r['name'] for r in con.execute('PRAGMA table_info(contas)'))
                con.execute(f'INSERT INTO contas_nova ({campos}) SELECT {campos} FROM contas')
                con.execute('DROP TABLE contas')
                con.execute('ALTER TABLE contas_nova RENAME TO contas')
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
            if 'previsao_atual_definida' not in atuais:
                con.execute('ALTER TABLE rpvs ADD COLUMN previsao_atual_definida TEXT')
            if 'lixeira_em' not in atuais:
                con.execute('ALTER TABLE rpvs ADD COLUMN lixeira_em TEXT')
            con.execute('''CREATE TABLE IF NOT EXISTS historico_alteracoes (
                id INTEGER PRIMARY KEY, rpv_id INTEGER NOT NULL REFERENCES rpvs(id) ON DELETE CASCADE,
                quando TEXT NOT NULL, acao TEXT NOT NULL, alteracoes TEXT NOT NULL)''')
            for registro in con.execute('SELECT * FROM rpvs WHERE id NOT IN (SELECT rpv_id FROM historico_alteracoes)').fetchall():
                self.auditar(con, registro['id'], 'Registro anterior à versão 0.9.0', {}, dict(registro))
            if con.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Não foi possível migrar o banco: vínculos inconsistentes.')
            con.execute('PRAGMA user_version=4')

    @staticmethod
    def cpf_unico(con):
        for indice in con.execute('PRAGMA index_list(contas)').fetchall():
            if indice['unique']:
                nome = indice['name'].replace('"', '""')
                campos = [r['name'] for r in con.execute(f'PRAGMA index_info("{nome}")')]
                if campos == ['cpf']:
                    return True
        return False

    @staticmethod
    def auditar(con, identificador, acao, antes, depois):
        diferencas = {k: {'antes': antes.get(k), 'depois': depois.get(k)}
                      for k in sorted(set(antes) | set(depois))
                      if antes.get(k) != depois.get(k)}
        if diferencas:
            con.execute('INSERT INTO historico_alteracoes (rpv_id,quando,acao,alteracoes) VALUES (?,?,?,?)',
                        (identificador, datetime.now().astimezone().isoformat(timespec='seconds'), acao,
                         json.dumps(diferencas, ensure_ascii=False)))

    @staticmethod
    def criar_rpvs(con, tabela):
        # tabela é sempre uma constante interna, nunca entrada do usuário.
        con.execute(f'''CREATE TABLE IF NOT EXISTS {tabela} (
            id INTEGER PRIMARY KEY, nome TEXT NOT NULL, aquisicao TEXT NOT NULL,
            previsto INTEGER NOT NULL CHECK(previsto >= 0),
            custo INTEGER NOT NULL CHECK(custo >= 0), conta TEXT NOT NULL,
            previsao TEXT NOT NULL, comissao INTEGER CHECK(comissao >= 0),
            observacoes TEXT NOT NULL DEFAULT '',
            conta_id INTEGER NOT NULL REFERENCES contas(id), conta_snapshot TEXT NOT NULL, recebimento TEXT, previsao_atual_definida TEXT, lixeira_em TEXT)''')

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
        campos = ('identificacao', 'nome', 'cpf', 'endereco', 'numero_endereco', 'cidade', 'estado', 'banco', 'agencia', 'numero', 'pix')
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
                 ('identificacao', 'nome', 'cpf', 'endereco', 'numero_endereco', 'cidade', 'estado', 'banco', 'agencia', 'numero', 'pix')}
        for campo in ('identificacao', 'nome', 'cpf', 'endereco', 'numero_endereco', 'cidade', 'estado', 'banco', 'numero', 'pix'):
            if not dados[campo]:
                raise ValueError('Preencha identificação, nome completo, CPF, endereço, número, cidade, estado, banco, conta e chave Pix.')
        dados['nome'] = nome_formatado(dados['nome'])
        dados['endereco'] = nome_formatado(dados['endereco'])
        dados['cidade'] = nome_formatado(dados['cidade'])
        dados['estado'] = dados['estado'].upper()
        if dados['estado'] not in ESTADOS:
            raise ValueError('Selecione um estado brasileiro válido.')
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
            raise ValueError('O valor de aquisição não pode superar o Valor Total RPV.')
        with self.conectar() as con:
            con.execute('BEGIN IMMEDIATE')
            anterior = con.execute('SELECT * FROM rpvs WHERE id=?', (identificador,)).fetchone() if identificador else None
            if identificador is not None and (anterior is None or anterior['lixeira_em']):
                raise ValueError('Este registro não está disponível. Confira a lixeira.')
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
                atual = con.execute(CONSULTA_RPVS + ' WHERE r.id=?', (identificador,)).fetchone()
                if (atual['previsao_atual_definida'] or atual['total_prorrogacoes']) and dados['aquisicao'] > atual['previsao_atual']:
                    raise ValueError('A aquisição não pode ser posterior à previsão atual.')
            if identificador is None:
                novo = con.execute('INSERT INTO rpvs (' + ','.join(campos) + ') VALUES (' +
                                   ','.join(':' + k for k in campos) + ')', dados).lastrowid
                self.auditar(con, novo, 'Cadastro', {}, dict(con.execute('SELECT * FROM rpvs WHERE id=?', (novo,)).fetchone()))
                return novo
            con.execute('UPDATE rpvs SET ' + ','.join(k + '=:' + k for k in campos) + ' WHERE id=:id',
                        dict(dados, id=identificador))
            depois = dict(con.execute('SELECT * FROM rpvs WHERE id=?', (identificador,)).fetchone())
            self.auditar(con, identificador, 'Edição', dict(anterior), depois)
            return identificador

    def listar(self, busca=''):
        with self.conectar() as con:
            registros = con.execute(CONSULTA_RPVS + ' WHERE r.lixeira_em IS NULL ORDER BY aquisicao DESC, id DESC').fetchall()
        return [r for r in registros if busca.casefold() in r['nome'].casefold() or busca in data_br(r['aquisicao'])]

    def obter(self, identificador):
        with self.conectar() as con:
            return con.execute(CONSULTA_RPVS + ' WHERE r.id=?', (identificador,)).fetchone()

    def excluir(self, identificador):
        with self.conectar() as con:
            con.execute('BEGIN IMMEDIATE')
            registro = con.execute('SELECT * FROM rpvs WHERE id=?', (identificador,)).fetchone()
            if registro is None or registro['lixeira_em']:
                raise ValueError('Registro não encontrado na lista ativa.')
            agora = datetime.now().astimezone().isoformat(timespec='seconds')
            con.execute('UPDATE rpvs SET lixeira_em=? WHERE id=?', (agora, identificador))
            self.auditar(con, identificador, 'Enviado para lixeira', {'lixeira_em': None}, {'lixeira_em': agora})

    def listar_lixeira(self):
        with self.conectar() as con:
            return con.execute(CONSULTA_RPVS + ' WHERE r.lixeira_em IS NOT NULL ORDER BY lixeira_em DESC,id DESC').fetchall()

    def restaurar(self, identificador):
        with self.conectar() as con:
            con.execute('BEGIN IMMEDIATE')
            registro = con.execute('SELECT * FROM rpvs WHERE id=?', (identificador,)).fetchone()
            if registro is None or not registro['lixeira_em']:
                raise ValueError('Registro não encontrado na lixeira.')
            con.execute('UPDATE rpvs SET lixeira_em=NULL WHERE id=?', (identificador,))
            self.auditar(con, identificador, 'Restaurado da lixeira', {'lixeira_em': registro['lixeira_em']}, {'lixeira_em': None})

    def historico(self, identificador):
        with self.conectar() as con:
            return con.execute('SELECT * FROM historico_alteracoes WHERE rpv_id=? ORDER BY id DESC', (identificador,)).fetchall()

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
            con.execute('BEGIN IMMEDIATE')
            registro = con.execute('SELECT * FROM rpvs WHERE id=?', (identificador,)).fetchone()
            if registro is None or registro['lixeira_em']:
                raise ValueError('Registro não encontrado na lista ativa.')
            if data is not None:
                if data < registro['aquisicao']:
                    raise ValueError('O recebimento não pode ser anterior à aquisição.')
                if data > date.today().isoformat():
                    raise ValueError('O recebimento não pode estar no futuro.')
            con.execute('UPDATE rpvs SET recebimento=? WHERE id=?', (data, identificador))
            self.auditar(con, identificador, 'Recebimento', {'recebimento': registro['recebimento']}, {'recebimento': data})

    def atualizar_previsao(self, identificador, nova_data):
        nova_data = data_iso(data_br(nova_data))
        with self.conectar() as con:
            con.execute('BEGIN IMMEDIATE')
            registro = con.execute('SELECT * FROM rpvs WHERE id=?', (identificador,)).fetchone()
            if registro is None or registro['lixeira_em']:
                raise ValueError('Registro não encontrado na lista ativa.')
            if nova_data < registro['aquisicao']:
                raise ValueError('A previsão atual não pode ser anterior à aquisição.')
            antes = con.execute(CONSULTA_RPVS + ' WHERE r.id=?', (identificador,)).fetchone()['previsao_atual']
            con.execute('UPDATE rpvs SET previsao_atual_definida=? WHERE id=?', (nova_data, identificador))
            self.auditar(con, identificador, 'Previsão atual', {'previsao_atual': antes}, {'previsao_atual': nova_data})
