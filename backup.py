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
from dados import ESQUEMA, PREFIXO_EXCLUSAO, TABELAS_LEGADAS, VERSAO_BANCO, Banco, limitar_backups
from diario import log


FORMATO = 'gestor-rpv-backup'
PASTA_AUTOMATICA = 'backup_auto_pasta'
PREFIXO_AUTOMATICO = 'GestorRPV-auto-'
SENHA_BACKUP = 'senha_backup'
# Configurações que pertencem a este computador: não vão no backup e não são trocadas ao importar.
# Marca, no banco novo, qual restauração o gravou: se o programa for fechado à força no meio de uma, a próxima
# abertura sabe se a troca do banco chegou ao fim e devolve os anexos que combinam com ele.
RESTAURACAO = 'restauracao_em_andamento'
DESCARTAR = 'descartar'
# Resumo dos dados no último backup: ao fechar o programa, um backup novo só é feito se algo mudou desde então.
ASSINATURA = 'assinatura_ultimo_backup'
CONFIGURACOES_LOCAIS = (PASTA_AUTOMATICA, SENHA_BACKUP, RESTAURACAO, ASSINATURA)


LIMITE_IMPORTACAO = 4 * 1024 ** 3  # Soma dos arquivos descompactados de um backup.
RAZAO_MAXIMA = 200                  # PDFs e imagens quase não comprimem; razões maiores indicam arquivo forjado.
LIMITE_ARQUIVOS = 20000
LIMITE_MANIFESTO = 8 * 1024 ** 2
FOLGA_DISCO = 200 * 1024 ** 2       # Espaço livre que sempre sobra depois de extrair.
BLOCO_LEITURA = 1024 * 1024
PREFIXO_TEMPORARIO = '.importar-rpv-'
PREFIXO_RESTAURACAO = '.restaurar-rpv-'
PREFIXO_BACKUP = '.backup-rpv-'


def limpar_temporarios(pasta, idade_segundos=24 * 60 * 60):
    """Remove pastas de trabalho que um encerramento forçado deixou para trás na pasta de dados."""
    limite = time.time() - idade_segundos
    for prefixo in (PREFIXO_TEMPORARIO, PREFIXO_RESTAURACAO, PREFIXO_EXCLUSAO, PREFIXO_BACKUP):
        for sobra in Path(pasta).glob(prefixo + '*'):
            try:
                if sobra.is_dir() and not sobra.is_symlink() and sobra.stat().st_mtime < limite:
                    shutil.rmtree(sobra, ignore_errors=True)
            except OSError:
                log.warning('Sobra de importação não removida.', exc_info=True)


def recuperar_interrompidas(banco):
    """Desfaz o que um encerramento forçado deixou pela metade, antes de limpar_temporarios apagar as sobras.

    Restauração: o SQLite desfaz sozinho a troca do banco que não terminou, mas a pasta de anexos já pode ter
    sido trocada. Logo depois da troca do banco, os anexos anteriores passam a se chamar "descartar": pasta
    com "documentos_anteriores" é restauração sem esse passo. Se o banco atual é o daquela restauração
    (marca RESTAURACAO), ela terminou e só falta renomear; senão, os anexos anteriores voltam ao lugar.
    Exclusão: os anexos cujo cadastro continua no banco voltam para a pasta de documentos.
    """
    try:
        concluida = banco.configuracao(RESTAURACAO)
        for pasta in sorted(banco.caminho.parent.glob(PREFIXO_RESTAURACAO + '*')):
            antigos = pasta / 'documentos_anteriores'
            if pasta.is_symlink() or not antigos.is_dir() or antigos.is_symlink():
                continue
            if pasta.name == concluida:
                os.replace(antigos, pasta / DESCARTAR)
                continue
            destino = banco.pasta_documentos
            if destino.exists():
                os.replace(destino, Path(tempfile.mkdtemp(prefix='documentos_importados-', dir=pasta)) / 'documentos')
            os.replace(antigos, destino)
            log.warning('Anexos de uma restauração interrompida devolvidos à pasta de documentos.')
        banco.devolver_exclusoes()
    except (OSError, sqlite3.Error):
        log.error('Sobras de uma restauração ou exclusão interrompida não foram conferidas.', exc_info=True)


def conferir_espaco(pasta, necessario):
    if shutil.disk_usage(pasta).free < necessario + FOLGA_DISCO:
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
    if dias < -2:
        # Data bem no futuro (relógio muito adiantado ou arquivo adulterado) não pode calar o lembrete nem o
        # backup automático. Um ou dois dias de diferença são só fuso ou relógio do computador.
        return 'Data do último backup inválida. Clique aqui para fazer um novo.'
    if dias >= 7:
        return f'Há {dias} dias sem backup. Clique aqui para fazer um novo.'
    return ''


def copiar_com_hash(entrada, saida=None, limite=None):
    """Lê em blocos de 1 MiB, grava em `saida` (se houver) e devolve o SHA-256 dos bytes lidos.

    Com `limite`, recusa passar desse número de bytes: o arquivo não pode crescer depois de conferido.
    """
    digest, lidos = hashlib.sha256(), 0
    for bloco in iter(lambda: entrada.read(BLOCO_LEITURA), b''):
        lidos += len(bloco)
        if limite is not None and lidos > limite:
            raise ValueError('O arquivo de backup mudou durante a importação.')
        digest.update(bloco)
        if saida is not None:
            saida.write(bloco)
    return digest.hexdigest()


def hash_arquivo(caminho):
    with open(caminho, 'rb') as arquivo:
        return copiar_com_hash(arquivo)


# Tabelas que alguma versão do aplicativo já criou. Qualquer outro objeto (trigger, view, índice próprio)
# não vem do Gestor de RPV: um trigger escondido poderia, por exemplo, trocar a chave Pix de toda conta salva.
TABELAS_CONHECIDAS = set(ESQUEMA) | TABELAS_LEGADAS
VERSAO_MAIS_ANTIGA = 4  # Backups da 0.9.0 em diante.

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


def tem_tabela(con, nome):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nome,)).fetchone() is not None


def validar_banco(caminho, migrado=False):
    """Confere um banco de backup e devolve as quantidades para a confirmação.

    Antes da migração, só o que não depende da versão: integridade, estruturas conhecidas, faixa de versões e
    vínculos. Depois de migrado (migrado=True), também as colunas do esquema atual (dados.ESQUEMA).
    """
    try:
        con = conexao_leitura(caminho)
        try:
            if con.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('O banco do backup está danificado.')
            verificar_estruturas(con)
            if not VERSAO_MAIS_ANTIGA <= con.execute('PRAGMA user_version').fetchone()[0] <= VERSAO_BANCO:
                raise ValueError('Este backup exige outra versão do Gestor de RPV.')
            obrigatorias = ESQUEMA if migrado else {'rpvs': ESQUEMA['rpvs'], 'contas': ESQUEMA['contas']}
            for tabela, campos in obrigatorias.items():
                if not campos.issubset({r[1] for r in con.execute(f'PRAGMA table_info({tabela})')}):
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


def documentos_sem_arquivo(banco):
    """Anexos cadastrados cujo arquivo sumiu da pasta de documentos (apagado por fora, antivírus, sincronização)."""
    with banco.conectar() as con:
        caminhos = [r['caminho'] for r in con.execute('SELECT caminho FROM documentos')]
    return [c for c in caminhos if not (banco.pasta_documentos / c).is_file()]


def copia_para_backup(banco, destino, quando):
    """Copia consistente do banco, sem as configurações deste computador (a senha não viaja no backup).

    Anexos cujo arquivo sumiu saem da cópia: um backup que cita um arquivo que não carrega seria recusado na
    importação, e todos os backups seguintes ficariam impossíveis de restaurar.
    """
    con = sqlite3.connect(destino)
    try:
        with banco.conectar() as origem:
            origem.backup(con)
        con.execute('PRAGMA journal_mode=DELETE')
        if tem_tabela(con, 'documentos'):
            ausentes = [(c,) for (c,) in con.execute('SELECT caminho FROM documentos')
                        if not (banco.pasta_documentos / c).is_file()]
            con.executemany('DELETE FROM documentos WHERE caminho=?', ausentes)
        if tem_tabela(con, 'configuracoes'):
            con.execute("INSERT OR REPLACE INTO configuracoes (chave,valor) VALUES ('ultimo_backup',?)", (quando,))
            con.executemany('DELETE FROM configuracoes WHERE chave=?', [(c,) for c in CONFIGURACOES_LOCAIS])
        con.commit()
        con.execute('VACUUM')  # Não deixa a senha apagada em páginas livres do arquivo.
        vinculados = sorted(r[0] for r in con.execute('SELECT caminho FROM documentos')) if tem_tabela(con, 'documentos') else []
    finally:
        con.close()
    return vinculados


def gravar_documentos(pacote, documentos, vinculados):
    """Só entram os anexos cadastrados; arquivos soltos na pasta não fazem parte dos dados."""
    if documentos.is_symlink():
        raise ValueError('A pasta de documentos não pode ser um atalho simbólico.')
    hashes = {}
    for caminho in vinculados:
        arquivo = documentos / caminho
        if arquivo.is_symlink():
            raise ValueError('Há um atalho simbólico na pasta de documentos.')
        if not arquivo.is_file():
            # Sumiu entre a cópia do banco e este ponto: sem o arquivo, o backup sairia impossível de restaurar.
            raise ValueError('Um anexo foi apagado enquanto o backup era criado. Tente de novo.')
        relativo = 'documentos/' + caminho
        # O hash é calculado sobre os mesmos bytes gravados no ZIP, inclusive se a origem mudar durante a cópia.
        # O nome é montado com barras, sem depender da normalização do Windows.
        info = ZipInfo(relativo, max(time.localtime(arquivo.stat().st_mtime)[:6], (1980, 1, 1, 0, 0, 0)))
        info.compress_type = ZIP_DEFLATED
        with open(arquivo, 'rb') as entrada, pacote.open(info, 'w') as saida:
            hashes[relativo] = copiar_com_hash(entrada, saida)
    return hashes


def limpar_parciais(pasta, idade_segundos=60 * 60):
    """Cópias interrompidas (".…rpvbackup.parcial") deixadas na pasta escolhida; já cifradas, mas inúteis."""
    limite = time.time() - idade_segundos
    for sobra in Path(pasta).glob('.*.rpvbackup.parcial'):
        try:
            if sobra.is_file() and not sobra.is_symlink() and sobra.stat().st_mtime < limite:
                sobra.unlink()
        except OSError:
            log.warning('Cópia interrompida não removida da pasta do backup.')


def criar_backup(banco, pasta, prefixo='GestorRPV-', exigir_senha=True, registrar=True):
    """Grava um backup completo, cifrado com a senha dos backups deste computador.

    Todo o trabalho acontece na pasta dos dados do programa; na pasta escolhida (que pode ser sincronizada
    com a nuvem) só chega o arquivo final, já cifrado. Sem senha definida, só as cópias de segurança locais
    (exigir_senha=False) saem sem criptografia. Cópias de segurança internas usam registrar=False: não contam
    como "último backup" para o lembrete.
    """
    senha = senha_salva(banco)
    if exigir_senha and not senha:
        raise SenhaAusente('Defina a senha dos backups antes de criar um backup.')
    assinatura = assinatura_dados(banco) if registrar else None
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    limpar_parciais(pasta)
    agora = datetime.now().astimezone()
    quando = agora.isoformat(timespec='seconds')
    destino = pasta / (prefixo + agora.strftime('%Y%m%d-%H%M%S-%f') + '.rpvbackup')
    with tempfile.TemporaryDirectory(prefix=PREFIXO_BACKUP, dir=banco.caminho.parent,
                                     ignore_cleanup_errors=True) as temporaria:
        trabalho = Path(temporaria)
        copia = trabalho / 'banco.sqlite3'
        vinculados = copia_para_backup(banco, copia, quando)
        validar_banco(copia)
        arquivos = {'banco.sqlite3': hash_arquivo(copia)}
        pronto = trabalho / 'pacote.tmp'
        with ZipFile(pronto, 'w', ZIP_DEFLATED) as pacote:
            pacote.write(copia, 'banco.sqlite3')
            arquivos.update(gravar_documentos(pacote, banco.pasta_documentos, vinculados))
            manifesto = {'formato': FORMATO, 'versao_formato': 1, 'versao_app': VERSAO, 'criado_em': quando,
                         'arquivos': arquivos}
            pacote.writestr('manifesto.json', json.dumps(manifesto, ensure_ascii=False, indent=2))
        if senha:
            protegido = trabalho / 'protegido.tmp'
            cifra.cifrar_arquivo(pronto, protegido, senha)
            pronto = protegido
        # Cópia para um nome provisório na pasta escolhida e troca no fim: o arquivo nunca fica pela metade.
        parcial = pasta / f'.{destino.name}.parcial'
        try:
            shutil.copyfile(pronto, parcial)
            os.replace(parcial, destino)
        finally:
            parcial.unlink(missing_ok=True)
    if registrar:
        banco.registrar_backup(quando)
        banco.salvar_configuracao(ASSINATURA, assinatura)
    return destino


def senha_salva(banco):
    guardada = banco.configuracao(SENHA_BACKUP)
    senha = cifra.revelar_senha(guardada)
    if cifra.legada(guardada):
        # Senha da 0.30.0, gravada como texto: passa a ser guardada protegida na primeira leitura.
        try:
            banco.salvar_configuracao(SENHA_BACKUP, cifra.proteger_senha(senha))
        except (OSError, sqlite3.Error):
            log.warning('Senha antiga dos backups não pôde ser protegida agora; nova tentativa na próxima leitura.')
    return senha


def salvar_senha(banco, senha):
    banco.salvar_configuracao(SENHA_BACKUP, cifra.proteger_senha(cifra.validar_senha(senha)))


def assinatura_dados(banco):
    """Resumo (SHA-256) de tudo o que o backup leva, menos as configurações: muda a cada cadastro, edição,
    recebimento, exclusão ou anexo."""
    resumo = hashlib.sha256()
    with banco.conectar() as con:
        for tabela in ESQUEMA:
            if tabela == 'configuracoes' or not tem_tabela(con, tabela):
                continue
            resumo.update(tabela.encode())
            # tabela vem do esquema do aplicativo, nunca de fora.
            for linha in con.execute(f'SELECT * FROM {tabela} ORDER BY rowid'):
                resumo.update(repr(tuple(linha)).encode())
    return resumo.hexdigest()


def executar_backup_automatico(banco, forcar=False, hoje=None, ao_fechar=False):
    """Grava um backup na pasta escolhida quando o último tiver sete dias ou mais, ou, ao fechar o programa,
    quando algo mudou desde o último backup.

    Só as cópias automáticas entram no limite de 10; backups manuais na mesma pasta são preservados.
    A pasta não é criada: se um disco externo ou pasta sincronizada sumir, o erro é informado.
    """
    pasta = banco.configuracao(PASTA_AUTOMATICA)
    if not pasta:
        return None
    if ao_fechar:
        if banco.configuracao(ASSINATURA) == assinatura_dados(banco):
            return None
    elif not (forcar or aviso_backup(banco.ultimo_backup(), hoje)):
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
            for tabela in ESQUEMA:
                # tabela vem do esquema do aplicativo; as colunas, do banco novo, criado por ele.
                campos = ','.join(r[1] for r in con.execute(f'PRAGMA main.table_info({tabela})'))
                con.execute(f'INSERT INTO main.{tabela} ({campos}) SELECT {campos} FROM origem.{tabela}')
        if con.execute('PRAGMA main.foreign_key_check').fetchall():
            raise ValueError('O backup contém vínculos inconsistentes.')
        con.execute('DETACH DATABASE origem')
    finally:
        con.close()


def remover_documentos(caminho, caminhos):
    con = sqlite3.connect(caminho)
    try:
        with con:
            con.executemany('DELETE FROM documentos WHERE caminho=?', [(c,) for c in caminhos])
    finally:
        con.close()


def gravar_configuracoes(caminho, valores):
    con = sqlite3.connect(caminho)
    try:
        with con:
            for chave, valor in valores.items():
                if valor is None:
                    con.execute('DELETE FROM configuracoes WHERE chave=?', (chave,))
                else:
                    con.execute('INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?)', (chave, valor))
    finally:
        con.close()


def conferir_nomes(infos):
    """Nomes, tamanhos e caminhos do ZIP, antes de ler qualquer conteúdo."""
    nomes = [i.filename for i in infos]
    if len(nomes) != len({n.casefold() for n in nomes}) or len(nomes) > LIMITE_ARQUIVOS:
        raise ValueError('O backup contém arquivos repetidos ou arquivos demais.')
    if sum(i.file_size for i in infos) > LIMITE_IMPORTACAO:
        raise ValueError('O backup excede o limite de 4 GB.')
    if any(i.file_size > BLOCO_LEITURA and i.file_size > RAZAO_MAXIMA * max(i.compress_size, 1) for i in infos):
        raise ValueError('O backup contém um arquivo compactado de forma suspeita e foi recusado.')
    for info in infos:
        caminho = PurePosixPath(info.filename)
        if (caminho.as_posix() != info.filename or caminho.is_absolute() or '..' in caminho.parts or
                '\\' in info.filename or ':' in info.filename or stat.S_ISLNK(info.external_attr >> 16) or info.is_dir()):
            raise ValueError('O backup contém um caminho inválido.')
        if info.filename not in ('banco.sqlite3', 'manifesto.json') and not info.filename.startswith('documentos/'):
            raise ValueError('O backup contém arquivos desconhecidos.')
    return nomes


def ler_manifesto(pacote, nomes):
    if 'manifesto.json' not in nomes or pacote.getinfo('manifesto.json').file_size > LIMITE_MANIFESTO:
        raise ValueError('Manifesto do backup ausente ou inválido.')
    manifesto = json.loads(pacote.read('manifesto.json'))
    if not isinstance(manifesto, dict) or manifesto.get('formato') != FORMATO or manifesto.get('versao_formato') != 1:
        raise ValueError('Formato de backup não reconhecido.')
    hashes = manifesto.get('arquivos')
    if not isinstance(hashes, dict) or set(hashes) != set(nomes) - {'manifesto.json'} or 'banco.sqlite3' not in hashes:
        raise ValueError('A lista de arquivos do backup está incompleta.')
    return manifesto, hashes


def conferir_hash(pacote, nome, esperado, destino=None, limite=None):
    with pacote.open(nome) as entrada:
        if destino is None:
            obtido = copiar_com_hash(entrada, limite=limite)
        else:
            with destino.open('wb') as saida:
                obtido = copiar_com_hash(entrada, saida, limite)
    if obtido != esperado:
        raise ValueError('Um arquivo do backup está danificado ou foi alterado.')


class BackupPreparado:
    """Confere o backup numa pasta temporária; os anexos só são gravados em restaurar(), após a confirmação."""

    def __init__(self, arquivo, senha=None, pasta_trabalho=None):
        self.arquivo = Path(arquivo)
        self.senha = senha
        # A pasta de trabalho fica junto dos dados do aplicativo, não na pasta temporária do sistema.
        self.pasta_trabalho = pasta_trabalho
        self.temporario = None
        self.cifrado = False
        self.ausentes = []

    def __enter__(self):
        if self.pasta_trabalho is not None:
            Path(self.pasta_trabalho).mkdir(parents=True, exist_ok=True)
        self.temporario = tempfile.TemporaryDirectory(prefix=PREFIXO_TEMPORARIO, dir=self.pasta_trabalho,
                                                      ignore_cleanup_errors=True)
        self.pasta = Path(self.temporario.name)
        try:
            self.pacote = self.decifrar()
            self.validar()
            return self
        except Exception:
            self.temporario.cleanup()
            raise

    def __exit__(self, *_):
        self.temporario.cleanup()

    def decifrar(self):
        self.cifrado = cifra.cifrado(self.arquivo)
        if not self.cifrado:
            return self.arquivo
        if not self.senha:
            raise SenhaNecessaria('Este backup é protegido por senha.')
        pacote = self.pasta / 'pacote.zip'
        conferir_espaco(self.pasta, self.arquivo.stat().st_size)
        try:
            cifra.decifrar_arquivo(self.arquivo, pacote, self.senha)
        except cifra.SenhaIncorreta as erro:
            raise SenhaNecessaria(str(erro)) from None
        return pacote

    def validar(self):
        """Confere tudo sem gravar os anexos: só o banco é extraído; os anexos têm o hash lido em fluxo."""
        try:
            with ZipFile(self.pacote) as pacote:
                nomes = conferir_nomes(pacote.infolist())
                manifesto, hashes = ler_manifesto(pacote, nomes)
                banco = self.pasta / 'banco.sqlite3'
                conferir_espaco(self.pasta, pacote.getinfo('banco.sqlite3').file_size)
                conferir_hash(pacote, 'banco.sqlite3', hashes['banco.sqlite3'], banco)
                for nome in hashes:
                    if nome.startswith('documentos/'):
                        conferir_hash(pacote, nome, hashes[nome])
                self.documentos = {nome: hashes[nome] for nome in hashes if nome.startswith('documentos/')}
                self.tamanhos = {nome: pacote.getinfo(nome).file_size for nome in self.documentos}
        except (BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError, TypeError, AttributeError) as erro:
            raise ValueError('O arquivo não é um backup válido do Gestor de RPV.') from erro
        validar_banco(banco)
        with Banco(banco).conectar() as con:  # Migra a cópia extraída para o esquema atual.
            caminhos = [r['caminho'] for r in con.execute('SELECT caminho FROM documentos')]
        if not all(CAMINHO_DOCUMENTO.fullmatch(caminho) for caminho in caminhos):
            raise ValueError('Um documento contém um caminho inválido.')
        # Cada arquivo de documentos/ precisa ser um anexo cadastrado, e cada anexo cadastrado precisa estar lá:
        # nada de executáveis, atalhos ou outros arquivos soltos chegando à pasta de documentos da pessoa.
        cadastrados = {'documentos/' + c for c in caminhos}
        if set(self.documentos) - cadastrados:
            raise ValueError('O backup contém arquivos que não são documentos cadastrados.')
        # Anexo cadastrado sem o arquivo (backups das versões até a 0.32.0 podiam sair assim quando um anexo
        # tinha sumido da pasta): os dados entram, e só a referência a esse anexo fica de fora, com aviso.
        self.ausentes = sorted(c for c in caminhos if 'documentos/' + c not in self.documentos)
        self.resumo = validar_banco(banco, migrado=True)
        self.resumo['documentos'] = len(self.documentos)
        self.resumo['documentos_ausentes'] = len(self.ausentes)
        self.criado_em = manifesto.get('criado_em', '')

    def extrair_documentos(self, destino):
        conferir_espaco(destino.parent, sum(self.tamanhos.values()))
        destino.mkdir()
        try:
            with ZipFile(self.pacote) as pacote:
                for nome, esperado in self.documentos.items():
                    arquivo = destino.joinpath(*PurePosixPath(nome).parts[1:])
                    arquivo.parent.mkdir(parents=True, exist_ok=True)
                    conferir_hash(pacote, nome, esperado, arquivo, limite=self.tamanhos[nome])
        except BadZipFile as erro:
            raise ValueError('O arquivo de backup mudou durante a importação.') from erro

    def restaurar(self, banco, copia_de_seguranca=True):
        """Troca os dados de `banco` pelos do backup. Devolve a cópia de segurança dos dados anteriores."""
        seguranca = None
        if copia_de_seguranca:
            # Esta cópia permanece disponível mesmo se uma falha interromper a importação.
            seguranca = criar_backup(banco, banco.caminho.parent / 'backups_automaticos', exigir_senha=False,
                                     registrar=False)
            limitar_backups(seguranca.parent, 'GestorRPV-*.rpvbackup')
        locais = {chave: banco.configuracao(chave) for chave in CONFIGURACOES_LOCAIS}
        # Depois da troca, uma falha ao apagar a pasta de trabalho (antivírus segurando um arquivo) não pode
        # aparecer como importação que falhou: a sobra sai na limpeza de uma próxima abertura.
        with tempfile.TemporaryDirectory(prefix=PREFIXO_RESTAURACAO, dir=banco.caminho.parent,
                                         ignore_cleanup_errors=True) as temporaria:
            trabalho = Path(temporaria)
            novos, antigos, destino = trabalho / 'documentos_novos', trabalho / 'documentos_anteriores', banco.pasta_documentos
            if destino.is_symlink():
                raise ValueError('A pasta atual de documentos não pode ser um atalho simbólico.')
            self.extrair_documentos(novos)
            # Só os dados do backup são aproveitados: as tabelas vêm de um banco novo, criado pelo próprio
            # aplicativo, e os valores são copiados linha a linha. Nada do esquema do arquivo importado sobrevive.
            limpo = trabalho / 'banco_limpo.sqlite3'
            copiar_dados(self.pasta / 'banco.sqlite3', limpo)
            remover_documentos(limpo, self.ausentes)
            # A pasta do backup automático e a senha pertencem a este computador, não ao arquivo importado. Elas
            # já entram no banco novo, para que a troca abaixo seja uma só: ou tudo muda, ou nada muda.
            gravar_configuracoes(limpo, {**locais, RESTAURACAO: trabalho.name})
            tinha_documentos = destino.exists()
            if tinha_documentos:
                os.replace(destino, antigos)
            try:
                os.replace(novos, destino)
                # SQLite faz a substituição do banco em uma transação própria.
                copiar_banco(limpo, banco.caminho)
            except BaseException:
                if destino.exists():
                    os.replace(destino, trabalho / 'documentos_importados')
                if tinha_documentos:
                    os.replace(antigos, destino)
                raise
            if tinha_documentos:
                # A troca terminou: a partir daqui, recuperar_interrompidas nunca devolve estes anexos. Se o
                # Windows segurar a pasta, a marca no banco faz a próxima abertura completar a renomeação; a
                # importação deu certo e não pode ser mostrada como falha.
                try:
                    os.replace(antigos, trabalho / DESCARTAR)
                except OSError:
                    log.warning('Anexos anteriores não marcados para descarte; a próxima abertura completa.')
        # A marca da restauração fica no banco até a próxima abertura (recuperar_interrompidas a apaga): nada é
        # gravado depois da troca. Ela nunca vai para um backup, por estar em CONFIGURACOES_LOCAIS.
        return seguranca
