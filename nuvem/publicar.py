"""Publica nuvem/worker.js na conta da Cloudflare (plano gratuito), pela API.

    python nuvem/publicar.py              # atualiza o código, mantendo as chaves dos lembretes
    python nuvem/publicar.py --primeira   # primeira vez: cria o KV e as chaves VAPID dos lembretes

O token vem de CLOUDFLARE_API_TOKEN (permissão "Edit Cloudflare Workers"); no ambiente do Claude Code ele é
posto pelo próprio proxy, como segredo de rede de api.cloudflare.com. A conta vem de CLOUDFLARE_ACCOUNT_ID ou,
se faltar, da primeira conta que o token enxerga.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
import uuid
from pathlib import Path

API = 'https://api.cloudflare.com/client/v4'
NOME = 'gestor-rpv'
KV = 'gestor-rpv-dados'
CRON = '0 11 * * *'  # 8h em Brasília: o lembrete das previsões de amanhã.
PASTA = Path(__file__).resolve().parent


def pedir(metodo, caminho, corpo=None, tipo='application/json'):
    cabecalhos = {'Content-Type': tipo}
    if os.environ.get('CLOUDFLARE_API_TOKEN'):
        cabecalhos['Authorization'] = 'Bearer ' + os.environ['CLOUDFLARE_API_TOKEN']
    if isinstance(corpo, (dict, list)):
        corpo = json.dumps(corpo).encode()
    pedido = urllib.request.Request(API + caminho, data=corpo, method=metodo, headers=cabecalhos)
    try:
        with urllib.request.urlopen(pedido, timeout=60) as resposta:
            dados = json.loads(resposta.read())
    except urllib.error.HTTPError as erro:
        dados = json.loads(erro.read() or b'{}')
    if not dados.get('success'):
        raise SystemExit(f'{metodo} {caminho}: {dados.get("errors")}')
    return dados['result']


def chaves_vapid():
    """Par P-256 para o VAPID: a privada em JWK (segredo do Worker) e a pública em base64url (para o celular)."""
    script = ("const k=await crypto.subtle.generateKey({name:'ECDSA',namedCurve:'P-256'},true,['sign','verify']);"
              "const pub=new Uint8Array(await crypto.subtle.exportKey('raw',k.publicKey));"
              "console.log(JSON.stringify({privada:await crypto.subtle.exportKey('jwk',k.privateKey),"
              "publica:Buffer.from(pub).toString('base64url')}))")
    saida = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True, check=True)
    return json.loads(saida.stdout)


def multipart(metadados, codigo):
    fronteira = uuid.uuid4().hex
    partes = [
        (f'--{fronteira}\r\nContent-Disposition: form-data; name="metadata"; filename="metadata.json"\r\n'
         'Content-Type: application/json\r\n\r\n').encode() + json.dumps(metadados).encode() + b'\r\n',
        (f'--{fronteira}\r\nContent-Disposition: form-data; name="worker.js"; filename="worker.js"\r\n'
         'Content-Type: application/javascript+module\r\n\r\n').encode() + codigo + b'\r\n',
        f'--{fronteira}--\r\n'.encode(),
    ]
    return b''.join(partes), f'multipart/form-data; boundary={fronteira}'


def main():
    primeira = '--primeira' in sys.argv
    conta = os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')
    if not re.fullmatch(r'[0-9a-f]{32}', conta):  # Vazio ou preenchido por engano: a conta vem do próprio token.
        conta = pedir('GET', '/accounts')[0]['id']
    base = f'/accounts/{conta}'
    espacos = {n['title']: n['id'] for n in pedir('GET', f'{base}/storage/kv/namespaces?per_page=100')}
    if KV not in espacos:
        espacos[KV] = pedir('POST', f'{base}/storage/kv/namespaces', {'title': KV})['id']
        print('KV criado.')
    ligacoes = [{'type': 'kv_namespace', 'name': 'DADOS', 'namespace_id': espacos[KV]}]
    metadados = {'main_module': 'worker.js', 'compatibility_date': '2026-10-01', 'bindings': ligacoes,
                 'keep_bindings': ['secret_text', 'plain_text']}
    if primeira:
        vapid = chaves_vapid()
        ligacoes += [{'type': 'secret_text', 'name': 'VAPID_PRIVADA', 'text': json.dumps(vapid['privada'])},
                     {'type': 'plain_text', 'name': 'VAPID_PUBLICA', 'text': vapid['publica']}]
        metadados['keep_bindings'] = []
    # Limite de tentativas da Cloudflare (o Worker também conta sozinho, se a conta não oferecer este).
    limitador = {'type': 'ratelimit', 'name': 'TENTATIVAS', 'namespace_id': '1001', 'simple': {'limit': 30, 'period': 60}}
    codigo = (PASTA / 'worker.js').read_bytes()
    try:
        corpo, tipo = multipart({**metadados, 'bindings': ligacoes + [limitador]}, codigo)
        pedir('PUT', f'{base}/workers/scripts/{NOME}', corpo, tipo)
        print('Com o limitador de tentativas da Cloudflare.')
    except SystemExit as erro:
        print(f'Sem o limitador da Cloudflare ({erro}); fica a contagem do próprio Worker.')
        corpo, tipo = multipart(metadados, codigo)
        pedir('PUT', f'{base}/workers/scripts/{NOME}', corpo, tipo)
    pedir('POST', f'{base}/workers/scripts/{NOME}/subdomain', {'enabled': True, 'previews_enabled': False})
    pedir('PUT', f'{base}/workers/scripts/{NOME}/schedules', [{'cron': CRON}])
    sub = pedir('GET', f'{base}/workers/subdomain')['subdomain']
    print(f'Publicado em https://{NOME}.{sub}.workers.dev')


if __name__ == '__main__':
    main()
