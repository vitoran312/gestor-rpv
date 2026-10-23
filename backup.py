"""Backup portátil: ZIP com banco SQLite consistente, documentos e hashes SHA-256."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import tempfile
import time
from datetime import date, datetime
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile

from versao import VERSAO


FORMATO = 'gestor-rpv-backup'


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


def conexao_leitura(caminho):
    return sqlite3.connect(Path(caminho).resolve().as_uri() + '?mode=ro', uri=True)


def validar_banco(caminho):
    try:
        con = conexao_leitura(caminho)
        try:
            if con.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('O banco do backup está danificado.')
            versao_banco = con.execute('PRAGMA user_version').fetchone()[0]
            if versao_banco not in (4,5,6,7):
                raise ValueError('Este backup exige outra versão do Gestor de RPV.')
            requisitos = {
                'rpvs': {'id','nome','aquisicao','previsto','custo','conta','previsao','comissao',
                         'observacoes','conta_id','conta_snapshot','recebimento','previsao_atual_definida','lixeira_em'},
                'contas': {'id','identificacao','identificacao_chave','nome','cpf','endereco','numero_endereco',
                           'cidade','estado','banco','agencia','numero','pix','ativa','banco_chave','agencia_chave','numero_chave'},
                'historico_alteracoes': {'id','rpv_id','quando','acao','alteracoes'},
                'prorrogacoes': {'id','rpv_id','data','criada_em'},
            }
            if versao_banco >= 5:
                requisitos['documentos'] = {'id','rpv_id','nome','caminho'}
            if versao_banco >= 6:
                requisitos['documentos'].add('tipo')
            if versao_banco>=7:
                requisitos['previsoes_historico']={'id','rpv_id','anterior','nova','alterada_em'}
                requisitos['configuracoes']={'chave','valor'}
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


def criar_backup(banco, pasta):
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    quando=datetime.now().astimezone().isoformat(timespec='seconds')
    nome = 'GestorRPV-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.rpvbackup'
    destino = pasta / nome
    with tempfile.TemporaryDirectory(prefix='.backup-rpv-', dir=pasta) as temporaria:
        trabalho = Path(temporaria)
        copia = trabalho / 'banco.sqlite3'
        con = sqlite3.connect(copia)
        try:
            with banco.conectar() as origem:
                origem.backup(con)
            con.execute('PRAGMA journal_mode=DELETE')
            if con.execute('PRAGMA user_version').fetchone()[0]>=7:
                con.execute("INSERT OR REPLACE INTO configuracoes (chave,valor) VALUES ('ultimo_backup',?)",(quando,))
                con.commit()
        finally:
            con.close()
        validar_banco(copia)
        arquivos = {'banco.sqlite3': hash_arquivo(copia)}
        zip_temporario = trabalho / 'pacote.tmp'
        with ZipFile(zip_temporario, 'w', ZIP_DEFLATED) as pacote:
            pacote.write(copia, 'banco.sqlite3')
            documentos = banco.caminho.parent / 'documentos'
            if documentos.is_symlink():
                raise ValueError('A pasta de documentos não pode ser um atalho simbólico.')
            if documentos.exists():
                for arquivo in sorted(documentos.rglob('*')):
                    if arquivo == trabalho or trabalho in arquivo.parents or arquivo.suffix.casefold() == '.rpvbackup':
                        continue
                    if arquivo.is_symlink():
                        raise ValueError('Há um atalho simbólico na pasta de documentos.')
                    if arquivo.is_file():
                        relativo = 'documentos/' + arquivo.relative_to(documentos).as_posix()
                        pacote.write(arquivo, relativo)
                        # O hash vem da cópia efetivamente escrita, inclusive se a origem mudou.
                        with pacote.open(relativo) as entrada:
                            digest = hashlib.sha256()
                            for bloco in iter(lambda: entrada.read(1024 * 1024), b''):
                                digest.update(bloco)
                        arquivos[relativo] = digest.hexdigest()
            manifesto = {'formato': FORMATO, 'versao_formato': 1, 'versao_app': VERSAO,
                         'criado_em': datetime.now().astimezone().isoformat(timespec='seconds'),
                         'arquivos': arquivos}
            pacote.writestr('manifesto.json', json.dumps(manifesto, ensure_ascii=False, indent=2))
        os.replace(zip_temporario, destino)
    banco.registrar_backup(quando)
    return destino


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


class BackupPreparado:
    """Valida e extrai em uma pasta temporária; só restaura após confirmação da UI."""
    def __init__(self, arquivo):
        self.arquivo = Path(arquivo)
        self.temporario = None

    def __enter__(self):
        self.temporario = tempfile.TemporaryDirectory(prefix='gestor-rpv-importar-')
        self.pasta = Path(self.temporario.name)
        try:
            self.validar_extrair()
            return self
        except Exception:
            self.temporario.cleanup()
            raise

    def __exit__(self, *_):
        self.temporario.cleanup()

    def validar_extrair(self):
        try:
            with ZipFile(self.arquivo) as pacote:
                infos = pacote.infolist()
                nomes = [i.filename for i in infos]
                if len(nomes) != len({n.casefold() for n in nomes}) or len(nomes) > 20000:
                    raise ValueError('O backup contém arquivos repetidos ou arquivos demais.')
                if sum(i.file_size for i in infos) > 8 * 1024**3:
                    raise ValueError('O backup excede o limite de 8 GB.')
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
                from dados import Banco
                banco_preparado = Banco(self.pasta / 'banco.sqlite3')
                with banco_preparado.conectar() as con:
                    for documento in con.execute('SELECT caminho FROM documentos'):
                        relativo = PurePosixPath(documento['caminho'])
                        if (relativo.is_absolute() or '..' in relativo.parts or '\\' in documento['caminho'] or
                            ':' in documento['caminho'] or relativo.as_posix() != documento['caminho']):
                            raise ValueError('Um documento contém um caminho inválido.')
                        caminho_documento = self.pasta / 'documentos' / documento['caminho']
                        if not caminho_documento.is_file():
                            raise ValueError('Um documento vinculado está ausente no backup.')
                self.resumo = validar_banco(self.pasta / 'banco.sqlite3')
                self.resumo['documentos'] = sum(n.startswith('documentos/') for n in hashes)
                self.criado_em = manifesto.get('criado_em', '')
                (self.pasta / 'documentos').mkdir(exist_ok=True)
        except (BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError, TypeError, AttributeError) as erro:
            raise ValueError('O arquivo não é um backup válido do Gestor de RPV.') from erro

    def restaurar(self, banco):
        # Esta cópia permanece disponível mesmo se uma falha interromper a importação.
        seguranca = criar_backup(banco, banco.caminho.parent / 'backups_automaticos')
        with tempfile.TemporaryDirectory(prefix='.restaurar-rpv-', dir=banco.caminho.parent) as temporaria:
            trabalho = Path(temporaria)
            novos = trabalho / 'documentos_novos'
            antigos = trabalho / 'documentos_anteriores'
            destino = banco.caminho.parent / 'documentos'
            if destino.is_symlink():
                raise ValueError('A pasta atual de documentos não pode ser um atalho simbólico.')
            shutil.copytree(self.pasta / 'documentos', novos)
            tinha_documentos = destino.exists()
            if tinha_documentos:
                os.replace(destino, antigos)
            try:
                os.replace(novos, destino)
                # SQLite faz a substituição do banco em uma transação própria.
                copiar_banco(self.pasta / 'banco.sqlite3', banco.caminho)
            except Exception:
                if destino.exists():
                    os.replace(destino, trabalho / 'documentos_importados')
                if tinha_documentos:
                    os.replace(antigos, destino)
                raise
        return seguranca
