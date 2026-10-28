"""Criptografia dos backups com senha: AES-256-GCM em blocos, chave derivada por scrypt.

Formato do arquivo: MAGICO, sal (16 bytes), prefixo do nonce (7 bytes) e, em seguida, blocos de até
1 MiB cifrados, cada um com a etiqueta de autenticação de 16 bytes do GCM. O nonce de cada bloco é o
prefixo, o número do bloco (4 bytes) e um byte que marca o último bloco; assim um arquivo truncado,
reordenado ou alterado é recusado, e backups grandes não precisam caber na memória.
Sem a senha não há como recuperar o conteúdo.
"""
import hashlib
import os

MAGICO = b'GRPVCIF1'
BLOCO = 1024 * 1024
ETIQUETA = 16
SENHA_MINIMA = 6


class SenhaIncorreta(ValueError):
    pass


def _aesgcm(chave):
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as erro:  # Só acontece rodando o código-fonte sem as dependências instaladas.
        raise ValueError('Instale o pacote "cryptography" para criar ou abrir backups com senha.') from erro
    return AESGCM(chave)


def derivar_chave(senha, sal):
    return hashlib.scrypt(senha.encode('utf-8'), salt=sal, n=2 ** 15, r=8, p=1, maxmem=64 * 1024 ** 2, dklen=32)


def _nonce(prefixo, indice, ultimo):
    return prefixo + indice.to_bytes(4, 'big') + (b'\x01' if ultimo else b'\x00')


def cifrado(caminho):
    with open(caminho, 'rb') as arquivo:
        return arquivo.read(len(MAGICO)) == MAGICO


def validar_senha(senha):
    if len(senha) < SENHA_MINIMA:
        raise ValueError(f'A senha precisa ter pelo menos {SENHA_MINIMA} caracteres.')
    return senha


def cifrar_arquivo(origem, destino, senha):
    sal, prefixo = os.urandom(16), os.urandom(7)
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
    from cryptography.exceptions import InvalidTag
    with open(origem, 'rb') as entrada, open(destino, 'wb') as saida:
        cabecalho = entrada.read(len(MAGICO) + 16 + 7)
        if len(cabecalho) != len(MAGICO) + 23 or not cabecalho.startswith(MAGICO):
            raise ValueError('O arquivo não é um backup com senha do Gestor de RPV.')
        sal, prefixo = cabecalho[len(MAGICO):len(MAGICO) + 16], cabecalho[len(MAGICO) + 16:]
        aes = _aesgcm(derivar_chave(senha, sal))
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
