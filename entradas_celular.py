"""Entradas cadastradas no app do celular, trazidas ao programa por arquivos ".rpvcelular".

O app grava cada entrada num arquivo pequeno, cifrado com a chave do backup que estava aberto nele (o mesmo
formato de cifra.py), e a pessoa salva esse arquivo na pasta do backup automático (por exemplo, no Google
Drive). Aqui o programa encontra esses arquivos, abre com a senha dos backups, confere tudo pelas mesmas regras
do formulário e, depois da confirmação, grava as entradas. Cada entrada tem um identificador próprio, anotado
nas configurações depois de importada: o mesmo arquivo nunca entra duas vezes, e o próximo backup leva essa
lista ao celular, que então apaga a cópia que guardava.
"""
import json
import os
import re
import tempfile
from pathlib import Path

import cifra
from backup import PASTA_AUTOMATICA, senha_salva
from dados import data_br, reais
from diario import log

EXTENSAO = '.rpvcelular'
FORMATO = 'gestor-rpv-celular'
IMPORTADAS = 'entradas_celular_importadas'
PASTA_IMPORTADOS = 'importados-do-celular'
LIMITE_ARQUIVO = 1024 * 1024  # Uma entrada tem poucos KB; mais que isso não é um arquivo do app.
IDENTIFICADOR = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
CAMPOS = {'id': str, 'nome': str, 'aquisicao': str, 'custo': int, 'previsto': int, 'conta_id': int, 'conta': str,
          'previsao': str, 'comissao': (int, type(None)), 'observacoes': str, 'criada_em': str}


def importadas(banco):
    try:
        lista = json.loads(banco.configuracao(IMPORTADAS) or '[]')
    except ValueError:
        return set()
    return {i for i in lista if isinstance(i, str)} if isinstance(lista, list) else set()


def ler(caminho, senha):
    """Abre um arquivo do celular e devolve a entrada que ele traz. ValueError explica o que estiver errado."""
    caminho = Path(caminho)
    if caminho.stat().st_size > LIMITE_ARQUIVO:
        raise ValueError('O arquivo é grande demais para ser uma entrada do celular.')
    if not cifra.cifrado(caminho):
        raise ValueError('O arquivo não é uma entrada do app do celular.')
    if not senha:
        raise ValueError('Defina a senha dos backups para abrir as entradas do celular.')
    with tempfile.TemporaryDirectory(prefix='.celular-rpv-') as pasta:
        aberto = Path(pasta) / 'entrada.json'
        try:
            cifra.decifrar_arquivo(caminho, aberto, senha)
        except cifra.SenhaIncorreta:
            raise ValueError('O arquivo não abre com a senha dos backups deste computador (foi feito com um backup '
                             'de outra senha, ou foi alterado).') from None
        try:
            pacote = json.loads(aberto.read_text(encoding='utf-8'))
        except (UnicodeDecodeError, ValueError):
            raise ValueError('O conteúdo do arquivo do celular está ilegível.') from None
    if not isinstance(pacote, dict) or pacote.get('formato') != FORMATO or pacote.get('versao_formato') != 1:
        raise ValueError('Formato de arquivo do celular não reconhecido. Atualize o programa.')
    entrada = pacote.get('entrada')
    if not isinstance(entrada, dict) or set(entrada) != set(CAMPOS):
        raise ValueError('O arquivo do celular está incompleto.')
    for campo, tipo in CAMPOS.items():
        if not isinstance(entrada[campo], tipo) or isinstance(entrada[campo], bool):
            raise ValueError('O arquivo do celular está incompleto.')
    if not IDENTIFICADOR.fullmatch(entrada['id']):
        raise ValueError('O arquivo do celular está incompleto.')
    return entrada


def procurar(banco, pasta=None):
    """Arquivos do celular na pasta do backup automático ainda não importados.

    Devolve (encontradas, problemas): encontradas é uma lista de (arquivo, entrada); problemas, de
    (arquivo, mensagem) para os que não puderam ser lidos.
    """
    pasta = pasta or banco.configuracao(PASTA_AUTOMATICA)
    if not pasta or not Path(pasta).is_dir():
        return [], []
    return conferir(banco, sorted(Path(pasta).glob('*' + EXTENSAO)))


def conferir(banco, arquivos):
    senha, ja = senha_salva(banco), importadas(banco)
    encontradas, problemas, vistos = [], [], set()
    for arquivo in arquivos:
        if not Path(arquivo).is_file() or Path(arquivo).is_symlink():
            continue
        try:
            entrada = ler(arquivo, senha)
        except (OSError, ValueError) as erro:
            problemas.append((Path(arquivo), str(erro) if isinstance(erro, ValueError) else 'Arquivo inacessível.'))
            continue
        if entrada['id'] in ja or entrada['id'] in vistos:
            guardar(arquivo)  # Já importada (o arquivo voltou pela sincronização): só sai da pasta.
            continue
        vistos.add(entrada['id'])
        encontradas.append((Path(arquivo), entrada))
    return encontradas, problemas


def guardar(arquivo):
    """Tira o arquivo importado da pasta principal (fica em importados-do-celular, como registro)."""
    arquivo = Path(arquivo)
    destino = arquivo.parent / PASTA_IMPORTADOS
    try:
        destino.mkdir(exist_ok=True)
        os.replace(arquivo, destino / arquivo.name)
    except OSError:
        log.warning('Arquivo do celular importado não foi movido.', exc_info=True)


def importar(banco, encontradas):
    """Grava as entradas. Devolve (importadas, problemas): a quantidade gravada e (nome, mensagem) das recusadas."""
    gravadas, problemas = 0, []
    ja = importadas(banco)
    for arquivo, entrada in encontradas:
        if entrada['id'] in ja:
            continue
        dados = {campo: entrada[campo] for campo in ('nome', 'aquisicao', 'custo', 'previsto', 'previsao', 'comissao',
                                                     'observacoes')}
        # A conta é procurada pelo número; se ela tiver sido removida no computador, pelo nome.
        contas = {c['id']: c for c in banco.contas()}
        conta = contas.get(entrada['conta_id']) or next(
            (c for c in contas.values() if c['identificacao'] == entrada['conta']), None)
        dados['conta_id'] = conta['id'] if conta else -1
        dados['conta'] = conta['identificacao'] if conta else entrada['conta']
        try:
            banco.salvar(dados)
        except ValueError as erro:
            problemas.append((entrada['nome'], str(erro)))
            continue
        ja.add(entrada['id'])
        banco.salvar_configuracao(IMPORTADAS, json.dumps(sorted(ja)))
        gravadas += 1
        guardar(arquivo)
    return gravadas, problemas


def resumo(entrada):
    try:
        previsao = data_br(entrada['previsao'])
    except ValueError:
        previsao = entrada['previsao']
    return f"{entrada['nome']} — {reais(entrada['previsto'])} — previsão {previsao} — conta {entrada['conta']}"
