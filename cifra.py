"""Criptografia dos backups com senha: AES-256-GCM em blocos, chave derivada por scrypt.

Formato do arquivo: MAGICO, sal (16 bytes), prefixo do nonce (7 bytes) e, em seguida, blocos de até
1 MiB cifrados, cada um com a etiqueta de autenticação de 16 bytes do GCM. O nonce de cada bloco é o
prefixo, o número do bloco (4 bytes) e um byte que marca o último bloco; assim um arquivo truncado,
reordenado ou alterado é recusado, e backups grandes não precisam caber na memória.
Sem a senha não há como recuperar o conteúdo.
"""
import base64
import hashlib
import os
import sys
import unicodedata
from pathlib import Path

from diario import log

MAGICO = b'GRPVCIF1'
TAMANHO_SAL = 16
TAMANHO_PREFIXO = 7   # Mais 4 bytes do número do bloco e 1 do marcador de último bloco: nonce de 12 bytes.
CABECALHO = len(MAGICO) + TAMANHO_SAL + TAMANHO_PREFIXO
BLOCO = 1024 * 1024
ETIQUETA = 16
SENHA_MINIMA, SENHA_MAXIMA = 10, 256
# Palavras que, com números ou símbolos em volta, formam as senhas do topo das listas de vazamentos
# ("senha@123", "password1", "brasil2026"): a força bruta começa por elas.
BASES_OBVIAS = {'', 'senha', 'minhasenha', 'password', 'passw', 'qwerty', 'qwertyuiop', 'asdf', 'asdfgh', 'abc', 'abcd',
                'abcdef', 'abcabc', 'abcabcab', 'iloveyou', 'teamo', 'brasil', 'admin', 'teste', 'mudar', 'mudarsenha',
                'gestor', 'gestorrpv', 'rpv', 'vitoran', 'backup', 'dragon', 'monkey', 'letmein', 'welcome'}


class SenhaIncorreta(ValueError):
    """A etiqueta de autenticação não confere: senha errada, ou arquivo alterado, cortado ou reordenado."""


def _aesgcm(chave):
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as erro:  # Só acontece rodando o código-fonte sem as dependências instaladas.
        log.error('Biblioteca de criptografia não carregou.', exc_info=True)
        raise ValueError('Instale o pacote "cryptography" para criar ou abrir backups com senha.') from erro
    return AESGCM(chave)


def derivar_chave(senha, sal):
    # NFC: a mesma senha com acentos dá a mesma chave, seja qual for o jeito como o teclado compôs as letras.
    texto = unicodedata.normalize('NFC', senha).encode('utf-8')
    return hashlib.scrypt(texto, salt=sal, n=2 ** 15, r=8, p=1, maxmem=64 * 1024 ** 2, dklen=32)


def _nonce(prefixo, indice, ultimo):
    return prefixo + indice.to_bytes(4, 'big') + (b'\x01' if ultimo else b'\x00')


def cifrado(caminho):
    with open(caminho, 'rb') as arquivo:
        return arquivo.read(len(MAGICO)) == MAGICO


def validar_senha(senha):
    if senha != senha.strip():
        raise ValueError('A senha não pode começar nem terminar com espaço.')
    if not SENHA_MINIMA <= len(senha) <= SENHA_MAXIMA:
        raise ValueError(f'A senha precisa ter de {SENHA_MINIMA} a {SENHA_MAXIMA} caracteres.')
    letras = ''.join(c for c in unicodedata.normalize('NFKD', senha.casefold()) if c.isalpha())
    # Teclas vizinhas no alfabeto ou repetidas ("abcdefghij", "aaaaaaaaab12", "1234567890"): quase sem acaso.
    passos = sum(abs(ord(a) - ord(b)) <= 1 for a, b in zip(senha.casefold(), senha.casefold()[1:]))
    if len(set(senha)) < 4 or letras in BASES_OBVIAS or passos >= len(senha) - 3:
        raise ValueError('Essa senha é fácil demais de adivinhar. Use uma frase com palavras que só você liga, '
                         'por exemplo "cavalo azul bebe café".')
    return senha


def mesma_senha(uma, outra):
    """Compara como a chave é derivada: acentos compostos de jeitos diferentes contam como iguais."""
    return unicodedata.normalize('NFC', uma) == unicodedata.normalize('NFC', outra)


def _dpapi(dados, proteger):
    """Proteção de dados do Windows: só o mesmo usuário, no mesmo computador, desfaz."""
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    ponteiro = ctypes.POINTER(Blob)
    for funcao in (crypt32.CryptProtectData, crypt32.CryptUnprotectData):
        funcao.argtypes = [ponteiro, ctypes.c_void_p, ponteiro, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ponteiro]
        funcao.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    buffer = ctypes.create_string_buffer(dados, len(dados))
    entrada, saida = Blob(len(dados), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), Blob()
    sem_janela = 0x1  # CRYPTPROTECT_UI_FORBIDDEN
    if proteger:
        descricao = ctypes.c_wchar_p('Gestor de RPV')
        ok = crypt32.CryptProtectData(ctypes.byref(entrada), ctypes.cast(descricao, ctypes.c_void_p), None, None, None,
                                      sem_janela, ctypes.byref(saida))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(entrada), None, None, None, None, sem_janela, ctypes.byref(saida))
    if not ok:
        raise OSError('A proteção de dados do Windows recusou a operação.')
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(saida.pbData, ctypes.c_void_p))


def proteger_senha(senha):
    """Como a senha fica guardada no banco local. No Windows, cifrada para o usuário atual (DPAPI): copiar o
    gestor.sqlite3 para outro computador ou outro usuário não entrega a senha. Fora do Windows, sem esse
    recurso, fica como texto."""
    if sys.platform == 'win32':
        return 'dpapi:' + base64.b64encode(_dpapi(senha.encode('utf-8'), True)).decode('ascii')
    return 'texto:' + senha


def legada(guardada):
    """Senha gravada pela 0.30.0, como texto, antes de existir a proteção."""
    return bool(guardada) and guardada.partition(':')[0] not in ('dpapi', 'texto')


def revelar_senha(guardada):
    """Senha salva neste computador, ou None se não houver ou se ela não puder ser lida aqui."""
    if not guardada:
        return None
    tipo, _, valor = guardada.partition(':')
    if tipo == 'dpapi':
        try:
            return _dpapi(base64.b64decode(valor), False).decode('utf-8')
        except (OSError, ValueError, AttributeError):
            return None  # Banco copiado de outro usuário ou computador: a senha precisa ser criada de novo.
    if tipo == 'texto':
        return valor
    return guardada  # Senha gravada pela 0.30.0, antes da proteção.


def cifrar_arquivo(origem, destino, senha):
    sal, prefixo = os.urandom(TAMANHO_SAL), os.urandom(TAMANHO_PREFIXO)
    cabecalho = MAGICO + sal + prefixo
    aes = _aesgcm(derivar_chave(senha, sal))
    with open(origem, 'rb') as entrada, open(destino, 'wb') as saida:
        saida.write(cabecalho)
        indice, atual = 0, entrada.read(BLOCO)
        while True:
            seguinte = entrada.read(BLOCO)
            ultimo = not seguinte
            saida.write(aes.encrypt(_nonce(prefixo, indice, ultimo), atual, cabecalho))
            if ultimo:
                return
            indice, atual = indice + 1, seguinte


def decifrar_arquivo(origem, destino, senha):
    """Decifra para `destino`; se algo não conferir, o destino é apagado: nada decifrado pela metade fica no disco."""
    try:
        _decifrar(origem, destino, senha)
    except BaseException:
        Path(destino).unlink(missing_ok=True)
        raise


def _decifrar(origem, destino, senha):
    with open(origem, 'rb') as entrada:
        cabecalho = entrada.read(CABECALHO)
        if len(cabecalho) != CABECALHO or not cabecalho.startswith(MAGICO):
            raise ValueError('O arquivo não é um backup com senha do Gestor de RPV.')
        sal = cabecalho[len(MAGICO):len(MAGICO) + TAMANHO_SAL]
        prefixo = cabecalho[len(MAGICO) + TAMANHO_SAL:]
        aes = _aesgcm(derivar_chave(senha, sal))
        from cryptography.exceptions import InvalidTag  # Depois de _aesgcm, que explica se o pacote faltar.
        with open(destino, 'wb') as saida:
            indice, atual = 0, entrada.read(BLOCO + ETIQUETA)
            while True:
                seguinte = entrada.read(BLOCO + ETIQUETA)
                ultimo = not seguinte
                try:
                    saida.write(aes.decrypt(_nonce(prefixo, indice, ultimo), atual, cabecalho))
                except InvalidTag:
                    raise SenhaIncorreta('Senha incorreta, ou o backup foi alterado ou está incompleto.') from None
                if ultimo:
                    return
                indice, atual = indice + 1, seguinte


def autoteste(resultado):
    """Usado pelo CI no .exe gerado: cifra e decifra um arquivo pequeno e grava "ok" ou o erro em `resultado`."""
    import tempfile
    import traceback
    try:
        with tempfile.TemporaryDirectory() as pasta:
            original, cifrado_, volta = (Path(pasta) / nome for nome in ('a', 'b', 'c'))
            original.write_bytes(os.urandom(BLOCO + 123))
            cifrar_arquivo(original, cifrado_, 'autoteste do executavel')
            decifrar_arquivo(cifrado_, volta, 'autoteste do executavel')
            texto = 'ok' if volta.read_bytes() == original.read_bytes() else 'conteúdo diferente'
    except BaseException:
        texto = traceback.format_exc()
    Path(resultado).write_text(texto, encoding='utf-8')
    return 0 if texto == 'ok' else 1
