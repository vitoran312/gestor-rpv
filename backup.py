"""Backup portátil: ZIP com banco SQLite consistente, documentos e hashes SHA-256."""
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import tempfile
import time
from datetime import date, datetime
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED, BadZipFile

import cifra
from documentos import EXTENSOES
from versao import VERSAO
from dados import ESQUEMA, VERSAO_BANCO, Banco, limitar_backups


FORMATO = 'gestor-rpv-backup'
PASTA_AUTOMATICA = 'backup_auto_pasta'
PREFIXO_AUTOMATICO = 'GestorRPV-auto-'
SENHA_BACKUP = 'senha_backup'
# Configurações que pertencem a este computador: não vão no backup e não são trocadas ao importar.
CONFIGURACOES_LOCAIS = (PASTA_AUTOMATICA, SENHA_BACKUP)


LIMITE_IMPORTACAO = 4 * 1024 ** 3  # Soma dos arquivos descompactados de um backup.
RAZAO_MAXIMA = 200                  # PDFs e imagens quase não comprimem; razões maiores indicam arquivo forjado.
PREFIXO_TEMPORARIO = '.importar-rpv-'


def limpar_temporarios(pasta, idade_segundos=24 * 60 * 60):
    """Remove pastas de trabalho que um encerramento forçado deixou para trás na pasta de dados."""
    limite = time.time() - idade_segundos
    for prefixo in (PREFIXO_TEMPORARIO, '.restaurar-rpv-', '.excluir-rpv-', '.backup-rpv-'):
        for sobra in Path(pasta).glob(prefixo + '*'):
            try:
                if sobra.is_dir() and not sobra.is_symlink() and sobra.stat().st_mtime < limite:
                    shutil.rmtree(sobra, ignore_errors=True)
            except OSError:
                pass


def conferir_espaco(pasta, necessario):
    if shutil.disk_usage(pasta).free < necessario + 200 * 1024 ** 2:
        raise ValueError('Não há espaço livre suficiente no disco para abrir este backup.')


class SenhaAusente(ValueError):
    """Ainda não há senha definida para proteger os backups."""


class SenhaNecessaria(ValueError):
    """O backup é protegido e a senha informada (ou a falta dela) não o abre."""


def aviso_backup(quando, hoje=None):
    """Lembrete sem interromper o uso; um backup recente dispensa o aviso."""
    if not quando:
        return 'Você ainda não fez um backup. Clique aqui para fazer.'
    try:
        data_backup = datetime.fromisoformat(quando)
        if data_backup.tzinfo is not None:
            data_backup = data_backup.astimezone()
    except (TypeError, ValueError):
        return 'Data do último backup indisponível. Clique aqui para fazer um novo.'
    dias = ((hoje or date.today()) - data_backup.date()).days
    if dias >= 7:
        return f'Há {dias} dias sem backup. Clique aqui para fazer um novo.'
    return ''


def hash_arquivo(caminho):
    digest = hashlib.sha256()
    with open(caminho, 'rb') as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b''):
            digest.update(bloco)
    return digest.hexdigest()


# Tabelas que alguma versão do aplicativo já criou. Qualquer outro objeto (trigger, view, índice próprio)
# não vem do Gestor de RPV: um trigger escondido poderia, por exemplo, trocar a chave Pix de toda conta salva.
TABELAS_CONHECIDAS = {'rpvs', 'contas', 'prorrogacoes', 'documentos', 'previsoes_historico', 'configuracoes',
                      'historico_alteracoes', 'sqlite_sequence', 'sqlite_stat1', 'sqlite_stat4'}
# Ordem de cópia na importação: tabelas referenciadas antes das que apontam para elas.
TABELAS_IMPORTADAS = ('contas', 'rpvs', 'prorrogacoes', 'documentos', 'previsoes_historico', 'configuracoes')


# Nome que o aplicativo dá a cada anexo: pasta da operação, identificador aleatório e extensão permitida.
CAMINHO_DOCUMENTO = re.compile(r'(recebimentos/)?[0-9]+/[0-9a-f]{32}(' +
                               '|'.join(re.escape(e) for e in sorted(EXTENSOES)) + ')')


def verificar_estruturas(con):
    for tipo, nome in con.execute('SELECT type, name FROM sqlite_master'):
        conhecido = (nome in TABELAS_CONHECIDAS if tipo == 'table' else
                     tipo == 'index' and nome.startswith('sqlite_autoindex_'))
        if not conhecido:
            raise ValueError('O backup contém estruturas que o Gestor de RPV não cria e foi recusado por segurança.')


def conexao_leitura(caminho):
    return sqlite3.connect(Path(caminho).resolve().as_uri() + '?mode=ro', uri=True)


def validar_banco(caminho):
    try:
        con = conexao_leitura(caminho)
        try:
            if con.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('O banco do backup está danificado.')
            verificar_estruturas(con)
            versao_banco = con.execute('PRAGMA user_version').fetchone()[0]
            if not 4 <= versao_banco <= VERSAO_BANCO:
                raise ValueError('Este backup exige outra versão do Gestor de RPV.')
            # As colunas vêm do esquema atual (dados.ESQUEMA); versões antigas ainda não tinham algumas tabelas.
            tabelas = {'rpvs', 'contas', 'prorrogacoes'}
            if versao_banco >= 5:
                tabelas.add('documentos')
            if versao_banco >= 7:
                tabelas |= {'previsoes_historico', 'configuracoes'}
            requisitos = {tabela: ESQUEMA[tabela] - ({'tipo'} if tabela == 'documentos' and versao_banco < 6 else set())
                          for tabela in tabelas}
            for tabela, campos in requisitos.items():
                presentes = {r[1] for r in con.execute(f'PRAGMA table_info({tabela})')}
                if not campos.issubset(presentes):
                    raise ValueError('O arquivo não contém um banco compatível.')
            if con.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('O backup contém vínculos inconsistentes.')
            return {'registros': con.execute('SELECT COUNT(*) FROM rpvs WHERE lixeira_em IS NULL').fetchone()[0],
                    'lixeira': con.execute('SELECT COUNT(*) FROM rpvs WHERE lixeira_em IS NOT NULL').fetchone()[0],
                    'contas': con.execute('SELECT COUNT(*) FROM contas').fetchone()[0]}
        finally:
            con.close()
    except sqlite3.Error as erro:
        raise ValueError('Não foi possível validar o banco do backup.') from erro


def criar_backup(banco, pasta, prefixo='GestorRPV-', exigir_senha=True):
    """Grava um backup completo, cifrado com a senha dos backups deste computador.

    Sem senha definida, só as cópias de segurança locais (exigir_senha=False) saem sem criptografia.
    """
    senha = banco.configuracao(SENHA_BACKUP)
    if exigir_senha and not senha:
        raise SenhaAusente('Defina a senha dos backups antes de criar um backup.')
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    quando=datetime.now().astimezone().isoformat(timespec='seconds')
    nome = prefixo + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.rpvbackup'
    destino = pasta / nome
    with tempfile.TemporaryDirectory(prefix='.backup-rpv-', dir=pasta) as temporaria:
        trabalho = Path(temporaria)
        copia = trabalho / 'banco.sqlite3'
        con = sqlite3.connect(copia)
        try:
            with banco.conectar() as origem:
                origem.backup(con)
            con.execute('PRAGMA journal_mode=DELETE')
            if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='configuracoes'").fetchone():
                con.execute("INSERT OR REPLACE INTO configuracoes (chave,valor) VALUES ('ultimo_backup',?)",(quando,))
                con.executemany('DELETE FROM configuracoes WHERE chave=?', [(c,) for c in CONFIGURACOES_LOCAIS])
                con.commit()
                con.execute('VACUUM')  # Não deixa a senha apagada em páginas livres do arquivo.
        finally:
            con.close()
        validar_banco(copia)
        arquivos = {'banco.sqlite3': hash_arquivo(copia)}
        zip_temporario = trabalho / 'pacote.tmp'
        with ZipFile(zip_temporario, 'w', ZIP_DEFLATED) as pacote:
            pacote.write(copia, 'banco.sqlite3')
            documentos = banco.pasta_documentos
            if documentos.is_symlink():
                raise ValueError('A pasta de documentos não pode ser um atalho simbólico.')
            # Só entram os anexos cadastrados; arquivos soltos na pasta não fazem parte dos dados.
            # A lista sai da cópia gravada no backup, que pode ser de um banco antigo, ainda sem anexos.
            con = sqlite3.connect(copia)
            try:
                tem_tabela = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='documentos'").fetchone()
                vinculados = sorted(r[0] for r in con.execute('SELECT caminho FROM documentos')) if tem_tabela else []
            finally:
                con.close()
            if documentos.exists():
                for caminho in vinculados:
                    arquivo = documentos / caminho
                    if arquivo.is_symlink():
                        raise ValueError('Há um atalho simbólico na pasta de documentos.')
                    if arquivo.is_file():
                        relativo = 'documentos/' + caminho
                        # O hash é calculado sobre os mesmos bytes gravados no ZIP, inclusive se a origem mudar
                        # durante a cópia. O nome é montado com barras, sem depender da normalização do Windows.
                        info = ZipInfo(relativo, max(time.localtime(arquivo.stat().st_mtime)[:6], (1980, 1, 1, 0, 0, 0)))
                        info.compress_type = ZIP_DEFLATED
                        digest = hashlib.sha256()
                        with open(arquivo, 'rb') as entrada, pacote.open(info, 'w') as saida:
                            for bloco in iter(lambda: entrada.read(1024 * 1024), b''):
                                digest.update(bloco)
                                saida.write(bloco)
                        arquivos[relativo] = digest.hexdigest()
            manifesto = {'formato': FORMATO, 'versao_formato': 1, 'versao_app': VERSAO,
                         'criado_em': datetime.now().astimezone().isoformat(timespec='seconds'),
                         'arquivos': arquivos}
            pacote.writestr('manifesto.json', json.dumps(manifesto, ensure_ascii=False, indent=2))
        if senha:
            protegido = trabalho / 'protegido.tmp'
            cifra.cifrar_arquivo(zip_temporario, protegido, senha)
            zip_temporario = protegido
        os.replace(zip_temporario, destino)
    banco.registrar_backup(quando)
    return destino


def executar_backup_automatico(banco, forcar=False, hoje=None):
    """Grava um backup na pasta escolhida quando o último tiver sete dias ou mais.

    Só as cópias automáticas entram no limite de 10; backups manuais na mesma pasta são preservados.
    A pasta não é criada: se um disco externo ou pasta sincronizada sumir, o erro é informado.
    """
    pasta = banco.configuracao(PASTA_AUTOMATICA)
    if not pasta or not (forcar or aviso_backup(banco.ultimo_backup(), hoje)):
        return None
    if not Path(pasta).is_dir():
        raise OSError('A pasta do backup automático não está disponível neste computador.')
    arquivo = criar_backup(banco, pasta, prefixo=PREFIXO_AUTOMATICO)
    limitar_backups(pasta, PREFIXO_AUTOMATICO + '*.rpvbackup')
    return arquivo


def copiar_banco(origem, destino):
    inicio = time.monotonic()

    def progresso(status, restantes, total):
        if status in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) and time.monotonic() - inicio > 10:
            raise sqlite3.OperationalError('Banco ocupado por outra execução do aplicativo.')

    fonte = conexao_leitura(origem)
    alvo = sqlite3.connect(destino, timeout=10)
    try:
        fonte.backup(alvo, pages=128, progress=progresso, sleep=0.1)
    finally:
        fonte.close()
        alvo.close()


def copiar_dados(origem, destino):
    """Cria um banco novo com o esquema do aplicativo e copia para ele apenas os valores da origem."""
    Banco(destino)
    con = sqlite3.connect(Path(destino).resolve().as_uri(), uri=True)
    try:
        con.execute('PRAGMA foreign_keys=OFF')
        con.execute('ATTACH DATABASE ? AS origem', (Path(origem).resolve().as_uri() + '?mode=ro',))
        with con:
            for tabela in TABELAS_IMPORTADAS:
                # tabela vem da lista fixa acima; as colunas, do banco novo, criado pelo aplicativo.
                campos = ','.join(r[1] for r in con.execute(f'PRAGMA main.table_info({tabela})'))
                con.execute(f'INSERT INTO main.{tabela} ({campos}) SELECT {campos} FROM origem.{tabela}')
        if con.execute('PRAGMA main.foreign_key_check').fetchall():
            raise ValueError('O backup contém vínculos inconsistentes.')
        con.execute('DETACH DATABASE origem')
    finally:
        con.close()


class BackupPreparado:
    """Valida e extrai em uma pasta temporária; só restaura após confirmação da UI."""
    def __init__(self, arquivo, senha=None, pasta_trabalho=None):
        self.arquivo = Path(arquivo)
        self.senha = senha
        # A cópia extraída fica junto dos dados do aplicativo, não na pasta temporária do sistema.
        self.pasta_trabalho = pasta_trabalho
        self.temporario = None

    def __enter__(self):
        if self.pasta_trabalho is not None:
            Path(self.pasta_trabalho).mkdir(parents=True, exist_ok=True)
        self.temporario = tempfile.TemporaryDirectory(prefix=PREFIXO_TEMPORARIO, dir=self.pasta_trabalho)
        self.pasta = Path(self.temporario.name)
        try:
            self.pacote = self.arquivo
            if cifra.cifrado(self.arquivo):
                if not self.senha:
                    raise SenhaNecessaria('Este backup é protegido por senha.')
                self.pacote = self.pasta / 'pacote.zip'
                conferir_espaco(self.pasta, self.arquivo.stat().st_size)
                try:
                    cifra.decifrar_arquivo(self.arquivo, self.pacote, self.senha)
                except cifra.SenhaIncorreta as erro:
                    raise SenhaNecessaria(str(erro)) from None
            self.validar_extrair()
            return self
        except Exception:
            self.temporario.cleanup()
            raise

    def __exit__(self, *_):
        self.temporario.cleanup()

    def validar_extrair(self):
        try:
            with ZipFile(self.pacote) as pacote:
                infos = pacote.infolist()
                nomes = [i.filename for i in infos]
                if len(nomes) != len({n.casefold() for n in nomes}) or len(nomes) > 20000:
                    raise ValueError('O backup contém arquivos repetidos ou arquivos demais.')
                total = sum(i.file_size for i in infos)
                if total > LIMITE_IMPORTACAO:
                    raise ValueError('O backup excede o limite de 4 GB.')
                if any(i.file_size > 1024 ** 2 and i.file_size > RAZAO_MAXIMA * max(i.compress_size, 1) for i in infos):
                    raise ValueError('O backup contém um arquivo compactado de forma suspeita e foi recusado.')
                conferir_espaco(self.pasta, total)
                for info in infos:
                    caminho = PurePosixPath(info.filename)
                    if (caminho.as_posix() != info.filename or caminho.is_absolute() or '..' in caminho.parts or '\\' in info.filename or
                        ':' in info.filename or stat.S_ISLNK(info.external_attr >> 16) or info.is_dir()):
                        raise ValueError('O backup contém um caminho inválido.')
                    if info.filename not in ('banco.sqlite3', 'manifesto.json') and not info.filename.startswith('documentos/'):
                        raise ValueError('O backup contém arquivos desconhecidos.')
                if 'manifesto.json' not in nomes or pacote.getinfo('manifesto.json').file_size > 8 * 1024**2:
                    raise ValueError('Manifesto do backup ausente ou inválido.')
                manifesto = json.loads(pacote.read('manifesto.json'))
                if manifesto.get('formato') != FORMATO or manifesto.get('versao_formato') != 1:
                    raise ValueError('Formato de backup não reconhecido.')
                hashes = manifesto.get('arquivos')
                if not isinstance(hashes, dict) or set(hashes) != set(nomes) - {'manifesto.json'} or 'banco.sqlite3' not in hashes:
                    raise ValueError('A lista de arquivos do backup está incompleta.')
                for nome, esperado in hashes.items():
                    destino = self.pasta.joinpath(*PurePosixPath(nome).parts)
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    digest = hashlib.sha256()
                    with pacote.open(nome) as entrada, destino.open('wb') as saida:
                        for bloco in iter(lambda: entrada.read(1024 * 1024), b''):
                            digest.update(bloco)
                            saida.write(bloco)
                    if digest.hexdigest() != esperado:
                        raise ValueError('Um arquivo do backup está danificado ou foi alterado.')
                validar_banco(self.pasta / 'banco.sqlite3')
                banco_preparado = Banco(self.pasta / 'banco.sqlite3')
                with banco_preparado.conectar() as con:
                    caminhos = [r['caminho'] for r in con.execute('SELECT caminho FROM documentos')]
                for caminho in caminhos:
                    if not CAMINHO_DOCUMENTO.fullmatch(caminho):
                        raise ValueError('Um documento contém um caminho inválido.')
                    if not (self.pasta / 'documentos' / caminho).is_file():
                        raise ValueError('Um documento vinculado está ausente no backup.')
                # Cada arquivo de documentos/ precisa ser um anexo cadastrado: nada de executáveis, atalhos
                # ou outros arquivos soltos chegando à pasta de documentos da pessoa.
                if {n for n in hashes if n.startswith('documentos/')} != {'documentos/' + c for c in caminhos}:
                    raise ValueError('O backup contém arquivos que não são documentos cadastrados.')
                self.resumo = validar_banco(self.pasta / 'banco.sqlite3')
                self.resumo['documentos'] = sum(n.startswith('documentos/') for n in hashes)
                self.criado_em = manifesto.get('criado_em', '')
                (self.pasta / 'documentos').mkdir(exist_ok=True)
        except (BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError, TypeError, AttributeError) as erro:
            raise ValueError('O arquivo não é um backup válido do Gestor de RPV.') from erro

    def restaurar(self, banco):
        # Esta cópia permanece disponível mesmo se uma falha interromper a importação.
        seguranca = criar_backup(banco, banco.caminho.parent / 'backups_automaticos', exigir_senha=False)
        locais = {chave: banco.configuracao(chave) for chave in CONFIGURACOES_LOCAIS}
        limitar_backups(seguranca.parent, 'GestorRPV-*.rpvbackup')
        with tempfile.TemporaryDirectory(prefix='.restaurar-rpv-', dir=banco.caminho.parent) as temporaria:
            trabalho = Path(temporaria)
            novos = trabalho / 'documentos_novos'
            antigos = trabalho / 'documentos_anteriores'
            destino = banco.pasta_documentos
            if destino.is_symlink():
                raise ValueError('A pasta atual de documentos não pode ser um atalho simbólico.')
            shutil.copytree(self.pasta / 'documentos', novos)
            tinha_documentos = destino.exists()
            if tinha_documentos:
                os.replace(destino, antigos)
            # Só os dados do backup são aproveitados: as tabelas vêm de um banco novo, criado pelo próprio
            # aplicativo, e os valores são copiados linha a linha. Nada do esquema do arquivo importado sobrevive.
            limpo = trabalho / 'banco_limpo.sqlite3'
            copiar_dados(self.pasta / 'banco.sqlite3', limpo)
            try:
                os.replace(novos, destino)
                # SQLite faz a substituição do banco em uma transação própria.
                copiar_banco(limpo, banco.caminho)
                # A pasta do backup automático e a senha pertencem a este computador, não ao arquivo importado.
                for chave, valor in locais.items():
                    if valor is None:
                        banco.remover_configuracao(chave)
                    else:
                        banco.salvar_configuracao(chave, valor)
            except Exception:
                if destino.exists():
                    os.replace(destino, trabalho / 'documentos_importados')
                if tinha_documentos:
                    os.replace(antigos, destino)
                raise
        return seguranca
