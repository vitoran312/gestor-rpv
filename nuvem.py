"""Backup na nuvem (Cloudflare Worker em nuvem/worker.js): o app do celular, quando é o principal, envia o backup a
cada gravação; o programa baixa o mais novo ao abrir e passa a mostrar esses dados, só para consulta.

O backup viaja e fica guardado cifrado com a senha dos backups (o mesmo arquivo .rpvbackup). A pessoa é
reconhecida por um identificador e uma chave de acesso derivados da mesma senha, aqui e no celular
(celular/nuvem.js faz a mesma conta): não há cadastro nem pareamento, e quem não sabe a senha não acha nem
baixa nada.
"""
import hashlib
import json
import os
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

ENDERECO = 'https://gestor-rpv.gestor-rpv-vitor.workers.dev'
SAL = b'gestor-rpv/nuvem/v1'
ESPERA = 30  # Segundos por pedido: o computador pode estar com internet lenta.

VERSAO = 'nuvem_versao'        # Versão do backup da nuvem que está aplicada neste computador.
CRIADO = 'nuvem_criado_em'     # Quando o celular gravou esse backup.
ESPELHO = 'nuvem_espelho'      # '1': os dados vêm do celular; o programa fica só para consulta.
CONFIGURACOES = (VERSAO, CRIADO, ESPELHO)

SO_CONSULTA = ('Este computador mostra os dados do app do celular, que é o principal: aqui é só para consulta. '
               'Faça entradas e alterações no celular; elas chegam aqui na próxima vez que o programa abrir.')


class NuvemIndisponivel(OSError):
    """Sem internet, servidor fora do ar ou resposta inesperada: o programa segue com os dados que já tem."""


def endereco():
    return os.environ.get('GESTOR_RPV_NUVEM', ENDERECO).rstrip('/')


def desligada():
    return endereco() == 'desligada'


def credenciais(senha):
    """(identificador, chave de acesso) derivados da senha, como celular/nuvem.js."""
    texto = unicodedata.normalize('NFC', senha).encode('utf-8')
    base = hashlib.scrypt(texto, salt=SAL, n=2 ** 15, r=8, p=1, maxmem=64 * 1024 ** 2, dklen=32)
    return hashlib.sha256(base + b'id').hexdigest()[:32], hashlib.sha256(base + b'acesso').hexdigest()


def _pedir(caminho, chave):
    pedido = urllib.request.Request(endereco() + caminho, headers={'X-Gestor-Chave': chave,
                                                                   'User-Agent': 'GestorRPV-PC'})
    try:
        with urllib.request.urlopen(pedido, timeout=ESPERA) as resposta:
            return resposta.read()
    except urllib.error.HTTPError as erro:
        if erro.code == 404:
            return None
        raise NuvemIndisponivel(f'A nuvem respondeu {erro.code}.') from erro
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        raise NuvemIndisponivel('Sem conexão com a nuvem.') from erro


def consultar(acesso):
    """Dados do último backup enviado pelo celular ({versao, partes, tamanho, resumo, criado_em, ...}) ou None."""
    identificador, chave = acesso
    corpo = _pedir(f'/v1/backup/{identificador}', chave)
    if corpo is None:
        return None
    try:
        meta = json.loads(corpo)
        int(meta['partes']), str(meta['versao']), str(meta['resumo'])
    except (ValueError, KeyError, TypeError) as erro:
        raise NuvemIndisponivel('Resposta inesperada da nuvem.') from erro
    return meta


def baixar(acesso, meta, destino):
    """Grava o backup em `destino`, parte por parte, e confere o resumo SHA-256 informado pelo celular."""
    identificador, chave = acesso
    destino = Path(destino)
    resumo = hashlib.sha256()
    with open(destino, 'wb') as arquivo:
        for numero in range(int(meta['partes'])):
            parte = _pedir(f"/v1/backup/{identificador}/{meta['versao']}/{numero}", chave)
            if parte is None:
                raise NuvemIndisponivel('O backup da nuvem mudou durante o download; tente de novo.')
            resumo.update(parte)
            arquivo.write(parte)
    if resumo.hexdigest() != meta['resumo']:
        destino.unlink(missing_ok=True)
        raise NuvemIndisponivel('O backup baixado da nuvem não confere.')
    return destino
