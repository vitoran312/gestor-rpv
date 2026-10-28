"""Persistência local. Valores monetários são armazenados em centavos."""
import os
import shutil
import tempfile
import uuid
from documentos import validar_anexo
import json
import re
import unicodedata
from contextlib import contextmanager
import sqlite3
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from diario import log


ESTADOS = ('AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS',
           'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO')

CONSULTA_RPVS = '''SELECT r.*,
    COALESCE(r.previsao_atual_definida,
        (SELECT MAX(data) FROM prorrogacoes WHERE rpv_id=r.id), r.previsao) AS previsao_atual,
    (SELECT COUNT(*) FROM prorrogacoes WHERE rpv_id=r.id) AS total_prorrogacoes
    FROM rpvs r'''


MANTER_BACKUPS = 10
VALOR_MAXIMO = Decimal('999999999999.99')
PREFIXO_EXCLUSAO = '.excluir-rpv-'  # Pasta de trabalho da exclusão de anexos; sobras são limpas na abertura.
LIMITE_NOME, LIMITE_OBSERVACOES = 150, 5000
VERSAO_BANCO = 8  # PRAGMA user_version gravado pela versão atual do esquema.


# Etapas de migração em ordem: versão do aplicativo que introduziu a mudança e como saber se ela falta.
# A primeira que falta dá nome à cópia guardada antes de migrar (backup-antes-<versão>-…).
ETAPAS = (
    ('0.4.0', lambda e: 'conta_id' not in e['rpvs']),
    ('0.6.0', lambda e: 'recebimento' not in e['rpvs']),
    ('0.7.0', lambda e: 'previsao_atual_definida' not in e['rpvs'] or
                        not {'numero_endereco', 'cidade', 'estado'}.issubset(e['contas'])),
    ('0.9.0', lambda e: 'lixeira_em' not in e['rpvs'] or e['cpf_unico']),
    ('0.10.0', lambda e: not e['tem_documentos']),
    ('0.11.0', lambda e: 'tipo' not in e['documentos']),
    ('0.16.0', lambda e: e['versao'] < 7),
    ('0.21.0', lambda e: e['versao'] < VERSAO_BANCO),
)

# Campos de uma conta de recebimento, na ordem do formulário, com o rótulo de cada um.
TITULOS_CONTA = {'identificacao': 'Identificação', 'nome': 'Nome completo', 'cpf': 'CPF', 'endereco': 'Endereço',
                 'numero_endereco': 'Número', 'cidade': 'Cidade', 'estado': 'Estado (UF)', 'banco': 'Nome do banco',
                 'agencia': 'Agência', 'numero': 'Conta bancária', 'pix': 'Chave Pix'}
CAMPOS_CONTA = tuple(TITULOS_CONTA)
# Esquema atual, em um lugar só: colunas que cada tabela precisa ter. A importação de backup confere por ele
# e copia as tabelas nesta ordem (as referenciadas vêm antes das que apontam para elas).
ESQUEMA = {
    'contas': {'id', 'identificacao_chave', 'ativa', 'banco_chave', 'agencia_chave', 'numero_chave', *CAMPOS_CONTA},
    'rpvs': {'id', 'nome', 'aquisicao', 'previsto', 'custo', 'conta', 'previsao', 'comissao', 'observacoes',
             'conta_id', 'conta_snapshot', 'recebimento', 'previsao_atual_definida', 'lixeira_em'},
    'prorrogacoes': {'id', 'rpv_id', 'data', 'criada_em'},
    'documentos': {'id', 'rpv_id', 'nome', 'caminho', 'tipo'},
    'previsoes_historico': {'id', 'rpv_id', 'anterior', 'nova', 'alterada_em'},
    'configuracoes': {'chave', 'valor'},
}
# Tabelas de versões antigas que a migração ainda reconhece (e remove), além das internas do SQLite.
TABELAS_LEGADAS = {'historico_alteracoes', 'sqlite_sequence', 'sqlite_stat1', 'sqlite_stat4'}


class VersaoMaisNova(ValueError):
    """O banco foi gravado por uma versão mais nova do aplicativo e não deve ser aberto por esta."""


def pasta_dados():
    base = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share'))
    return base / 'GestorRPV'


def limitar_backups(pasta, padrao, manter=MANTER_BACKUPS):
    """Mantém somente as cópias automáticas mais recentes que seguem o padrão."""
    arquivos = sorted((a for a in Path(pasta).glob(padrao) if a.is_file() and not a.is_symlink()),
                      key=lambda a: (a.stat().st_mtime, a.name), reverse=True)
    for antigo in arquivos[manter:]:
        try:
            antigo.unlink()
        except OSError:
            log.warning('Backup antigo não removido: %s', antigo, exc_info=True)


def centavos(texto):
    texto = texto.strip().replace('R$', '').replace(' ', '')
    if ',' in texto:
        texto = texto.replace('.', '').replace(',', '.')
    elif '.' in texto:
        partes = texto.split('.')
        if 1 <= len(partes[0]) <= 3 and all(len(p) == 3 and p.isdigit() for p in partes[1:]):
            texto = ''.join(partes)
    try:
        # Só dígitos 0-9 e um separador decimal: Decimal aceitaria também "1e3", "1_000" e dígitos de
        # outros alfabetos, que não são formas de escrever dinheiro.
        if not re.fullmatch(r'[0-9]+(\.[0-9]+)?', texto):
            raise ValueError
        valor = Decimal(texto)
        if valor > VALOR_MAXIMO:
            raise ValueError(f'O valor máximo é R$ {moeda(int(VALOR_MAXIMO * 100))}.')
        if valor != valor.quantize(Decimal('.01')):
            raise ValueError
        return int(valor * 100)
    except ValueError as erro:
        if str(erro):
            raise
        raise ValueError('Informe um valor positivo ou zero, com até duas casas decimais.') from None
    except InvalidOperation:
        raise ValueError('Informe um valor positivo ou zero, com até duas casas decimais.') from None


def moeda(valor):
    inteiro, fracao = divmod(abs(valor), 100)
    prefixo = '-' if valor < 0 else ''
    return prefixo + f'{inteiro:,}'.replace(',', '.') + f',{fracao:02d}'


def reais(valor):
    return 'R$ ' + moeda(valor)


def previsao_por_prazo(aquisicao, prazo):
    """Soma dias corridos à aquisição e retorna a previsão em DD/MM/AAAA."""
    if not re.fullmatch(r'[0-9]+', prazo.strip()):
        raise ValueError('Informe o prazo em dias como um número inteiro maior ou igual a zero.')
    inicio = date.fromisoformat(data_iso(aquisicao))
    try:
        resultado = inicio + timedelta(days=int(prazo))
    except OverflowError:
        resultado = date.max
    if not ANO_MINIMO <= resultado.year <= ANO_MAXIMO:
        raise ValueError(f'O prazo leva a previsão para depois de {ANO_MAXIMO}. Confira o número de dias.')
    return data_br(resultado.isoformat())


ANO_MINIMO, ANO_MAXIMO = 1900, 2100  # Fora disso é erro de digitação; datas fora da faixa quebram o Excel.


def data_iso(texto):
    try:
        valor = datetime.strptime(texto.strip(), '%d/%m/%Y').date()
    except ValueError:
        raise ValueError('Informe uma data válida no formato DD/MM/AAAA.') from None
    if not ANO_MINIMO <= valor.year <= ANO_MAXIMO:
        raise ValueError(f'Informe uma data entre {ANO_MINIMO} e {ANO_MAXIMO}.')
    return valor.isoformat()


def validar_data_iso(texto, campo):
    """Confere uma data já em ISO (vinda da interface ou de outra rotina) antes de gravar."""
    try:
        valor = date.fromisoformat(texto)
    except (TypeError, ValueError):
        raise ValueError(f'{campo}: informe uma data válida.') from None
    if not ANO_MINIMO <= valor.year <= ANO_MAXIMO:
        raise ValueError(f'{campo}: informe uma data entre {ANO_MINIMO} e {ANO_MAXIMO}.')
    return valor.isoformat()


def data_br(texto):
    # Sem strftime: no Linux, '%Y' não completa anos com zeros à esquerda.
    valor = date.fromisoformat(texto)
    return f'{valor.day:02d}/{valor.month:02d}/{valor.year:04d}'


def situacao(registro, hoje=None):
    """Recebida, atrasada (previsão atual vencida sem recebimento) ou pendente."""
    if registro['recebimento']:
        return 'recebida'
    if registro['previsao_atual'] < (hoje or date.today()).isoformat():
        return 'atrasada'
    return 'pendente'


def nome_formatado(texto):
    return ' '.join(texto.split()).title()


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', texto).casefold()
                   if c.isalnum() and not unicodedata.combining(c))


def chave_texto(texto):
    """Para ordenar: sem acentos nem maiúsculas, mas com os espaços ("Ana Maria" antes de "Anabela")."""
    return ' '.join(normalizar(palavra) for palavra in texto.split())


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
    """Forma comparável de uma chave Pix: (tipo, valor).

    Chaves só com números são comparadas pelos dígitos. O tipo vem da pontuação: "." ou "/" indicam CPF ou
    CNPJ; parênteses, "+" ou espaços indicam telefone; só dígitos (e hífen) podem ser qualquer um dos dois.
    """
    texto = texto.strip().casefold()
    if not re.fullmatch(r'[0-9+ ().\-/]+', texto):
        return 'texto', texto
    digitos = re.sub(r'\D', '', texto)
    tipo = 'documento' if re.search(r'[./]', texto) else 'telefone' if re.search(r'[()+ ]', texto) else 'numero'
    # Telefone com DDI do Brasil (12 ou 13 dígitos começando por 55) é a mesma chave sem o +55.
    # CPF (11) e CNPJ (14) têm outros tamanhos e não são afetados.
    if tipo != 'documento' and len(digitos) in (12, 13) and digitos.startswith('55'):
        digitos = digitos[2:]
    return tipo, digitos


def mesma_chave_pix(uma, outra):
    (tipo_a, valor_a), (tipo_b, valor_b) = chave_pix(uma), chave_pix(outra)
    if not valor_a or valor_a != valor_b:
        return False
    # CPF e celular podem ter os mesmos 11 dígitos sem serem a mesma chave.
    return tipo_a == tipo_b or 'numero' in (tipo_a, tipo_b)


class Banco:
    def __init__(self, caminho=None):
        self.caminho = Path(caminho) if caminho else pasta_dados() / 'gestor.sqlite3'
        self.novo = not self.caminho.exists()  # Banco criado agora: instalação nova neste computador.
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self.conectar() as con:
            estado = self.estado_do_esquema(con)
        if estado['versao'] > VERSAO_BANCO:
            # Abrir e regravar como versão antiga apagaria em silêncio o que a versão nova acrescentou.
            raise VersaoMaisNova('Estes dados foram gravados por uma versão mais nova do Gestor de RPV. '
                                 'Atualize o programa para abri-los.')
        pendente = next((rotulo for rotulo, falta in ETAPAS if falta(estado)), None)
        if estado['rpvs'] and pendente:
            self.copiar_antes_de_migrar(pendente)
        with self.conectar() as con:
            # Recriar tabelas preserva os IDs referenciados por outras; as chaves voltam a valer no fim.
            con.execute('PRAGMA foreign_keys=OFF')
            con.execute('BEGIN IMMEDIATE')
            self.remover_estruturas_estranhas(con)
            self.migrar_contas(con, estado)
            self.migrar_rpvs(con, estado)
            self.criar_tabelas_auxiliares(con, estado)
            if con.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Não foi possível migrar o banco: vínculos inconsistentes.')
            con.execute(f'PRAGMA user_version={VERSAO_BANCO}')

    @classmethod
    def estado_do_esquema(cls, con):
        """O que já existe no arquivo: colunas de cada tabela, versão gravada e particularidades antigas."""
        colunas = lambda tabela: {r['name'] for r in con.execute(f'PRAGMA table_info({tabela})')}
        return {'rpvs': colunas('rpvs'), 'contas': colunas('contas'), 'documentos': colunas('documentos'),
                'tem_documentos': bool(colunas('documentos')), 'cpf_unico': cls.cpf_unico(con),
                'versao': con.execute('PRAGMA user_version').fetchone()[0]}

    def copiar_antes_de_migrar(self, versao):
        """Antes de mexer no esquema, guarda o banco como estava; ficam as 10 cópias mais recentes."""
        backup = self.caminho.with_name(f'backup-antes-{versao}-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
        with self.conectar() as origem:
            destino = sqlite3.connect(backup)
            try:
                origem.backup(destino)
            finally:
                destino.close()
        limitar_backups(self.caminho.parent, 'backup-antes-*.sqlite3')

    @staticmethod
    def remover_estruturas_estranhas(con):
        # O aplicativo nunca cria triggers nem views; se algum existir, veio de fora e é removido.
        for tipo, nome in con.execute("SELECT type, name FROM sqlite_master WHERE type IN ('trigger','view')").fetchall():
            con.execute(f'DROP {tipo.upper()} IF EXISTS "{nome.replace(chr(34), chr(34) * 2)}"')

    def migrar_contas(self, con, estado):
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
        for campo in ('numero_endereco', 'cidade', 'estado'):  # 0.7.0
            if campo not in existentes:
                con.execute(f"ALTER TABLE contas ADD COLUMN {campo} TEXT NOT NULL DEFAULT ''")
        if estado['cpf_unico']:  # 0.9.0: o mesmo CPF pode ter mais de uma conta.
            esquema = con.execute("SELECT sql FROM sqlite_master WHERE name='contas'").fetchone()[0]
            esquema = re.sub(r'^CREATE TABLE\s+(?:IF NOT EXISTS\s+)?[\"`\[]?contas[\"`\]]?',
                             'CREATE TABLE contas_nova', esquema, count=1, flags=re.IGNORECASE)
            esquema = re.sub(r'\bcpf\s+TEXT\s+UNIQUE\b', 'cpf TEXT', esquema, flags=re.IGNORECASE)
            con.execute(esquema)
            self.trocar_tabela(con, 'contas', 'contas_nova')

    def migrar_rpvs(self, con, estado):
        if estado['rpvs'] and 'conta_id' not in estado['rpvs']:
            # 0.4.0: a conta era só um nome; cada nome vira uma conta a completar.
            for (nome,) in con.execute('SELECT DISTINCT conta FROM rpvs').fetchall():
                con.execute('''INSERT OR IGNORE INTO contas (identificacao, identificacao_chave)
                               VALUES (?, ?)''', (nome, normalizar(nome)))
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
        atuais = {r['name'] for r in con.execute('PRAGMA table_info(rpvs)')}
        for coluna in ('recebimento', 'previsao_atual_definida', 'lixeira_em'):  # 0.6.0, 0.7.0 e 0.9.0
            if coluna not in atuais:
                con.execute(f'ALTER TABLE rpvs ADD COLUMN {coluna} TEXT')
        if any(r['name'] == 'conta_id' and r['notnull'] for r in con.execute('PRAGMA table_info(rpvs)')):
            # 0.16.0: a conta removida deixa a operação sem conta, com a cópia dos dados bancários.
            self.criar_rpvs(con, 'rpvs_nova')
            self.trocar_tabela(con, 'rpvs', 'rpvs_nova')

    @staticmethod
    def criar_tabelas_auxiliares(con, estado):
        con.execute('''CREATE TABLE IF NOT EXISTS prorrogacoes (
            id INTEGER PRIMARY KEY, rpv_id INTEGER NOT NULL REFERENCES rpvs(id) ON DELETE CASCADE,
            data TEXT NOT NULL, criada_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(rpv_id, data))''')
        # O histórico geral de alterações foi descontinuado na 0.10.0 e removido na 0.21.0;
        # a cópia backup-antes-0.21.0 preserva registros antigos, se houver.
        con.execute('DROP TABLE IF EXISTS historico_alteracoes')
        con.execute('''CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY, rpv_id INTEGER NOT NULL REFERENCES rpvs(id) ON DELETE CASCADE,
            nome TEXT NOT NULL, caminho TEXT NOT NULL UNIQUE)''')
        if 'tipo' not in estado['documentos']:  # 0.11.0
            con.execute("ALTER TABLE documentos ADD COLUMN tipo TEXT NOT NULL DEFAULT 'entrada' CHECK(tipo IN ('entrada','recebimento'))")
        con.execute('''CREATE TABLE IF NOT EXISTS previsoes_historico (
            id INTEGER PRIMARY KEY, rpv_id INTEGER NOT NULL REFERENCES rpvs(id) ON DELETE CASCADE,
            anterior TEXT NOT NULL, nova TEXT NOT NULL, alterada_em TEXT NOT NULL)''')
        con.execute('CREATE TABLE IF NOT EXISTS configuracoes (chave TEXT PRIMARY KEY,valor TEXT NOT NULL)')

    @staticmethod
    def trocar_tabela(con, tabela, nova):
        """Copia os dados para a tabela nova, já com o esquema certo, e a põe no lugar da antiga."""
        # Os nomes vêm sempre de constantes internas, nunca do usuário.
        campos = ','.join(r['name'] for r in con.execute(f'PRAGMA table_info({tabela})'))
        con.execute(f'INSERT INTO {nova} ({campos}) SELECT {campos} FROM {tabela}')
        con.execute(f'DROP TABLE {tabela}')
        con.execute(f'ALTER TABLE {nova} RENAME TO {tabela}')

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
    def criar_rpvs(con, tabela):
        # tabela é sempre uma constante interna, nunca entrada do usuário.
        con.execute(f'''CREATE TABLE IF NOT EXISTS {tabela} (
            id INTEGER PRIMARY KEY, nome TEXT NOT NULL, aquisicao TEXT NOT NULL,
            previsto INTEGER NOT NULL CHECK(previsto >= 0),
            custo INTEGER NOT NULL CHECK(custo >= 0), conta TEXT NOT NULL,
            previsao TEXT NOT NULL, comissao INTEGER CHECK(comissao >= 0),
            observacoes TEXT NOT NULL DEFAULT '',
            conta_id INTEGER REFERENCES contas(id) ON DELETE SET NULL, conta_snapshot TEXT NOT NULL, recebimento TEXT, previsao_atual_definida TEXT, lixeira_em TEXT)''')

    @property
    def pasta_documentos(self):
        return self.caminho.parent / 'documentos'

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
        return json.dumps({k: conta[k] for k in CAMPOS_CONTA}, ensure_ascii=False)

    def contas(self, somente_ativas=False):
        with self.conectar() as con:
            return con.execute('SELECT * FROM contas' + (' WHERE ativa=1' if somente_ativas else '') +
                               ' ORDER BY identificacao COLLATE NOCASE').fetchall()

    def obter_conta(self, identificador):
        with self.conectar() as con:
            return con.execute('SELECT * FROM contas WHERE id=?', (identificador,)).fetchone()

    def salvar_conta(self, dados, identificador=None):
        dados = {k: dados.get(k, '').strip() for k in CAMPOS_CONTA}
        for campo in CAMPOS_CONTA:
            if campo != 'agencia' and not dados[campo]:  # A agência é a única informação opcional.
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
                if mesma_chave_pix(conta['pix'], dados['pix']):
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

    def operacoes_da_conta(self, identificadores):
        """Quantas operações (inclusive na lixeira) usam alguma das contas."""
        ids = [int(i) for i in identificadores]
        with self.conectar() as con:
            return con.execute(f'SELECT COUNT(*) FROM rpvs WHERE conta_id IN ({",".join("?" * len(ids))})', ids).fetchone()[0]

    def remover_contas(self, identificadores):
        ids = list(dict.fromkeys(int(i) for i in identificadores))
        with self.conectar() as con:
            con.execute('BEGIN IMMEDIATE')
            con.executemany('UPDATE rpvs SET conta_id=NULL WHERE conta_id=?',[(i,) for i in ids])
            con.executemany('DELETE FROM contas WHERE id=?',[(i,) for i in ids])

    def salvar(self, dados, identificador=None, anexos=()):
        criados = []
        try:
            return self._salvar(dados, identificador, anexos, criados)
        except Exception:
            for arquivo in criados:
                arquivo.unlink(missing_ok=True)
            raise

    @staticmethod
    def problemas_da_entrada(dados):
        """Todas as regras de uma entrada, conferidas de uma vez: devolve a lista do que está errado.

        As regras ficam aqui, e não só na interface, para valerem em qualquer caminho de gravação.
        """
        problemas = []
        if not dados['nome']:
            problemas.append('Informe o nome completo do titular original.')
        elif len(dados['nome']) > LIMITE_NOME:
            problemas.append(f'O nome do titular pode ter até {LIMITE_NOME} caracteres.')
        if len(dados['observacoes']) > LIMITE_OBSERVACOES:
            problemas.append(f'As observações podem ter até {LIMITE_OBSERVACOES} caracteres.')
        datas_validas = True
        for chave, rotulo in (('aquisicao', 'Data da aquisição'), ('previsao', 'Previsão de recebimento')):
            try:
                dados[chave] = validar_data_iso(dados[chave], rotulo)
            except ValueError as erro:
                problemas.append(str(erro))
                datas_validas = False
        if datas_validas:
            if dados['aquisicao'] > date.today().isoformat():
                problemas.append('A data da aquisição não pode estar no futuro.')
            if dados['previsao'] < dados['aquisicao']:
                problemas.append('A previsão não pode ser anterior à aquisição.')
        if dados['comissao'] is not None and dados['comissao'] < 0:
            problemas.append('A comissão não pode ser negativa.')
        elif dados['comissao'] is not None and dados['comissao'] > dados['previsto']:
            problemas.append('A comissão não pode superar o Valor Total RPV.')
        if dados['custo'] <= 0:
            problemas.append('O valor de aquisição deve ser maior que zero.')
        elif dados['custo'] > dados['previsto']:
            problemas.append('O valor de aquisição não pode superar o Valor Total RPV.')
        return problemas

    def _salvar(self, dados, identificador, anexos, criados):
        dados = dict(dados)
        dados['nome'] = nome_formatado(dados['nome'])
        problemas = self.problemas_da_entrada(dados)
        if problemas:
            raise ValueError('\n'.join(problemas))
        # A maiúscula inicial vem depois da conferência do tamanho ("ß" vira "SS" e passaria do limite).
        dados['observacoes'] = dados['observacoes'][:1].upper() + dados['observacoes'][1:]
        with self.conectar() as con:
            con.execute('BEGIN IMMEDIATE')
            anterior = con.execute('SELECT * FROM rpvs WHERE id=?', (identificador,)).fetchone() if identificador else None
            if identificador is not None and (anterior is None or anterior['lixeira_em']):
                raise ValueError('Este registro não está disponível. Confira a lixeira.')
            if 'conta_id' in dados:
                conta = con.execute('SELECT * FROM contas WHERE id=?', (dados['conta_id'],)).fetchone()
            else:
                conta = con.execute('SELECT * FROM contas WHERE identificacao=?', (dados['conta'],)).fetchone()
            removida_preservada=(anterior is not None and anterior['conta_id'] is None and conta is None and
                                (dados.get('conta_id','ausente') is None or dados.get('conta')==anterior['conta']))
            if conta is None and not removida_preservada:
                raise ValueError('Selecione uma conta cadastrada.')
            mesma_conta=removida_preservada or (anterior is not None and anterior['conta_id']==conta['id'])
            if conta is not None and not conta['ativa'] and not mesma_conta:
                raise ValueError('A conta foi desativada. Selecione uma conta ativa.')
            dados['conta_id']=None if removida_preservada else conta['id']
            dados['conta']=anterior['conta'] if mesma_conta else conta['identificacao']
            dados['conta_snapshot']=anterior['conta_snapshot'] if mesma_conta else self.snapshot(conta)
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
                self.copiar_anexos(con, novo, anexos, criados)
                return novo
            con.execute('UPDATE rpvs SET ' + ','.join(k + '=:' + k for k in campos) + ' WHERE id=:id',
                        dict(dados, id=identificador))
            self.copiar_anexos(con, identificador, anexos, criados)
            return identificador

    def listar(self, busca=''):
        with self.conectar() as con:
            registros = con.execute(CONSULTA_RPVS + ' WHERE r.lixeira_em IS NULL ORDER BY aquisicao DESC, id DESC').fetchall()
        # Sem acentos, maiúsculas nem pontuação: "jose" acha "José" e "davila" acha "D'Ávila".
        # A busca também procura na conta; buscas só de símbolos comparam o texto como foi digitado.
        termo = normalizar(busca)
        if not termo:
            return [r for r in registros if busca.casefold() in r['nome'].casefold() or busca in data_br(r['aquisicao'])]
        return [r for r in registros if termo in normalizar(r['nome']) or termo in normalizar(r['conta'])
                or busca.strip() in data_br(r['aquisicao'])]

    def obter(self, identificador):
        with self.conectar() as con:
            return con.execute(CONSULTA_RPVS + ' WHERE r.id=?', (identificador,)).fetchone()

    def excluir(self, identificador):
        self.excluir_varios([identificador])

    def excluir_varios(self, identificadores):
        ids = list(dict.fromkeys(int(i) for i in identificadores))
        with self.conectar() as con:
            con.execute('BEGIN IMMEDIATE')
            self.conferir_lixeira(con, ids, False, 'Uma entrada não está mais na lista ativa. Atualize a lista e tente novamente.')
            agora = datetime.now().astimezone().isoformat(timespec='seconds')
            con.executemany('UPDATE rpvs SET lixeira_em=? WHERE id=?',[(agora,i) for i in ids])

    @staticmethod
    def conferir_lixeira(con, ids, na_lixeira, mensagem):
        """Todas as entradas precisam existir e estar (ou não) na lixeira; senão nada é alterado."""
        for identificador in ids:
            registro = con.execute('SELECT lixeira_em FROM rpvs WHERE id=?', (identificador,)).fetchone()
            if registro is None or bool(registro['lixeira_em']) != na_lixeira:
                raise ValueError(mensagem)

    def listar_lixeira(self):
        with self.conectar() as con:
            return con.execute(CONSULTA_RPVS + ' WHERE r.lixeira_em IS NOT NULL ORDER BY lixeira_em DESC,id DESC').fetchall()

    def restaurar(self, identificador):
        self.restaurar_varios([identificador])

    def restaurar_varios(self, identificadores):
        ids = list(dict.fromkeys(int(i) for i in identificadores))
        with self.conectar() as con:
            con.execute('BEGIN IMMEDIATE')
            self.conferir_lixeira(con, ids, True, 'Uma entrada não está mais na lixeira. Reabra a lista e tente novamente.')
            con.executemany('UPDATE rpvs SET lixeira_em=NULL WHERE id=?',[(i,) for i in ids])

    def registrar_recebimento(self, identificador, data, anexos=()):
        criados = []
        try:
            self._registrar_recebimento(identificador, data, anexos, criados)
        except Exception:
            for arquivo in criados:
                arquivo.unlink(missing_ok=True)
            raise

    def _registrar_recebimento(self, identificador, data, anexos, criados):
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
            if data is None and anexos:
                raise ValueError('Informe a data do recebimento para anexar comprovantes.')
            con.execute('UPDATE rpvs SET recebimento=? WHERE id=?', (data, identificador))
            self.copiar_anexos(con, identificador, anexos, criados, tipo='recebimento')

    def atualizar_previsao(self, identificador, nova_data):
        nova_data = data_iso(data_br(nova_data))
        with self.conectar() as con:
            con.execute('BEGIN IMMEDIATE')
            registro = con.execute('SELECT * FROM rpvs WHERE id=?', (identificador,)).fetchone()
            if registro is None or registro['lixeira_em']:
                raise ValueError('Registro não encontrado na lista ativa.')
            if nova_data < registro['aquisicao']:
                raise ValueError('A previsão atual não pode ser anterior à aquisição.')
            atual=con.execute(CONSULTA_RPVS+' WHERE r.id=?',(identificador,)).fetchone()['previsao_atual']
            if atual != nova_data:
                con.execute('INSERT INTO previsoes_historico (rpv_id,anterior,nova,alterada_em) VALUES (?,?,?,?)',
                            (identificador,atual,nova_data,datetime.now().astimezone().isoformat(timespec='seconds')))
            con.execute('UPDATE rpvs SET previsao_atual_definida=? WHERE id=?', (nova_data, identificador))

    def copiar_anexos(self, con, identificador, anexos, criados, tipo='entrada'):
        if tipo not in ('entrada','recebimento'):
            raise ValueError('Tipo de documento inválido.')
        for origem in anexos:
            origem = validar_anexo(origem)
            relativo = f'{identificador}/{uuid.uuid4().hex}{origem.suffix.lower()}'
            if tipo == 'recebimento':
                relativo = 'recebimentos/' + relativo
            destino = self.pasta_documentos / relativo
            destino.parent.mkdir(parents=True, exist_ok=True)
            criados.append(destino)
            shutil.copyfile(origem, destino)
            con.execute('INSERT INTO documentos (rpv_id,nome,caminho,tipo) VALUES (?,?,?,?)',
                        (identificador,origem.name,relativo,tipo))

    def documentos(self, identificador, tipo='entrada'):
        with self.conectar() as con:
            return con.execute('SELECT * FROM documentos WHERE rpv_id=? AND tipo=? ORDER BY id',(identificador,tipo)).fetchall()

    def caminho_documento(self, identificador):
        with self.conectar() as con:
            documento = con.execute('SELECT * FROM documentos WHERE id=?',(identificador,)).fetchone()
        if documento is None:
            raise ValueError('Documento não encontrado.')
        raiz = self.pasta_documentos.resolve()
        caminho = (raiz / documento['caminho']).resolve()
        if not caminho.is_relative_to(raiz) or not caminho.is_file():
            raise ValueError('O arquivo deste documento não está disponível.')
        return caminho


    def historico_previsoes(self,identificador):
        with self.conectar() as con:
            return con.execute('SELECT * FROM previsoes_historico WHERE rpv_id=? ORDER BY id DESC',(identificador,)).fetchall()

    def configuracao(self, chave, padrao=None):
        with self.conectar() as con:
            linha = con.execute('SELECT valor FROM configuracoes WHERE chave=?', (chave,)).fetchone()
        return linha['valor'] if linha else padrao

    def salvar_configuracao(self, chave, valor):
        with self.conectar() as con:
            con.execute('INSERT OR REPLACE INTO configuracoes (chave,valor) VALUES (?,?)', (chave, valor))

    def remover_configuracao(self, chave):
        with self.conectar() as con:
            con.execute('DELETE FROM configuracoes WHERE chave=?', (chave,))

    def ultimo_backup(self):
        return self.configuracao('ultimo_backup')

    def registrar_backup(self, quando):
        self.salvar_configuracao('ultimo_backup', quando)

    @contextmanager
    def arquivos_para_excluir(self):
        movidos=[]
        with tempfile.TemporaryDirectory(prefix=PREFIXO_EXCLUSAO,dir=self.caminho.parent) as pasta:
            def preparar(documentos):
                raiz=self.pasta_documentos.resolve()
                for documento in documentos:
                    arquivo=(raiz/documento['caminho']).resolve()
                    if not arquivo.is_relative_to(raiz):
                        raise ValueError('Caminho de documento inválido.')
                    if arquivo.is_file():
                        destino=Path(pasta)/str(len(movidos))
                        os.replace(arquivo,destino)
                        movidos.append((arquivo,destino))
            try:
                yield preparar
            except Exception:
                for arquivo,destino in reversed(movidos):
                    os.replace(destino,arquivo)
                raise

    def remover_documento(self,identificador):
        with self.arquivos_para_excluir() as preparar:
            with self.conectar() as con:
                con.execute('BEGIN IMMEDIATE')
                documento=con.execute('SELECT * FROM documentos WHERE id=?',(identificador,)).fetchone()
                if documento is None:
                    raise ValueError('Documento não encontrado.')
                preparar([documento])
                con.execute('DELETE FROM documentos WHERE id=?',(identificador,))

    def excluir_permanentemente(self,identificadores):
        ids=list(dict.fromkeys(int(i) for i in identificadores))
        with self.arquivos_para_excluir() as preparar:
            with self.conectar() as con:
                con.execute('BEGIN IMMEDIATE')
                self.conferir_lixeira(con, ids, True, 'Somente entradas na lixeira podem ser excluídas permanentemente.')
                for identificador in ids:
                    preparar(con.execute('SELECT * FROM documentos WHERE rpv_id=?',(identificador,)).fetchall())
                con.executemany('DELETE FROM rpvs WHERE id=?',[(i,) for i in ids])
