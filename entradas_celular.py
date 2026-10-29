"""Entradas e contas de recebimento cadastradas no app do celular, trazidas por arquivos ".rpvcelular".

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
from dados import CAMPOS_CONTA, data_br, normalizar, reais
from diario import log

EXTENSAO = '.rpvcelular'
FORMATO = 'gestor-rpv-celular'
IMPORTADAS = 'entradas_celular_importadas'
PASTA_IMPORTADOS = 'importados-do-celular'
LIMITE_ARQUIVO = 1024 * 1024  # Uma entrada tem poucos KB; mais que isso não é um arquivo do app.
IDENTIFICADOR = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
CAMPOS = {'id': str, 'nome': str, 'aquisicao': str, 'custo': int, 'previsto': int, 'conta_id': int, 'conta': str,
          'previsao': str, 'comissao': (int, type(None)), 'observacoes': str, 'criada_em': str}
CAMPOS_DA_CONTA = {'id': str, 'criada_em': str, **{campo: str for campo in CAMPOS_CONTA}}
TIPOS = {'entrada': CAMPOS, 'conta': CAMPOS_DA_CONTA}


def importadas(banco):
    try:
        lista = json.loads(banco.configuracao(IMPORTADAS) or '[]')
    except ValueError:
        return set()
    return {i for i in lista if isinstance(i, str)} if isinstance(lista, list) else set()


def ler(caminho, senha):
    """Abre um arquivo do celular e devolve o que ele traz (com 'tipo': 'entrada' ou 'conta').

    ValueError explica o que estiver errado.
    """
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
    tipos = [t for t in TIPOS if t in pacote]
    if len(tipos) != 1:
        raise ValueError('O arquivo do celular está incompleto.')
    tipo = tipos[0]
    registro = pacote[tipo]
    if not isinstance(registro, dict) or set(registro) != set(TIPOS[tipo]):
        raise ValueError('O arquivo do celular está incompleto.')
    for campo, classe in TIPOS[tipo].items():
        if not isinstance(registro[campo], classe) or isinstance(registro[campo], bool):
            raise ValueError('O arquivo do celular está incompleto.')
    if not IDENTIFICADOR.fullmatch(registro['id']):
        raise ValueError('O arquivo do celular está incompleto.')
    return {**registro, 'tipo': tipo}


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
    """Grava contas e entradas. Devolve (importadas, problemas): a quantidade gravada e (nome, mensagem) das
    recusadas. As contas vêm primeiro: uma entrada feita no celular com uma conta nova a encontra já cadastrada."""
    gravadas, problemas = 0, []
    ja = importadas(banco)
    for arquivo, registro in sorted(encontradas, key=lambda item: item[1]['tipo'] != 'conta'):
        if registro['id'] in ja:
            continue
        try:
            if registro['tipo'] == 'conta':
                banco.salvar_conta({campo: registro[campo] for campo in CAMPOS_CONTA})
            else:
                banco.salvar(dados_da_entrada(banco, registro))
        except ValueError as erro:
            problemas.append((registro['identificacao'] if registro['tipo'] == 'conta' else registro['nome'], str(erro)))
            continue
        ja.add(registro['id'])
        banco.salvar_configuracao(IMPORTADAS, json.dumps(sorted(ja)))
        gravadas += 1
        guardar(arquivo)
    return gravadas, problemas


def dados_da_entrada(banco, entrada):
    dados = {campo: entrada[campo] for campo in ('nome', 'aquisicao', 'custo', 'previsto', 'previsao', 'comissao',
                                                 'observacoes')}
    # A conta é procurada pelo número; se não existir (conta nova feita no celular, ou removida no computador),
    # pelo nome, sem diferença de maiúsculas e acentos.
    contas = {c['id']: c for c in banco.contas()}
    conta = contas.get(entrada['conta_id']) or next(
        (c for c in contas.values() if normalizar(c['identificacao']) == normalizar(entrada['conta'])), None)
    dados['conta_id'] = conta['id'] if conta else -1
    dados['conta'] = conta['identificacao'] if conta else entrada['conta']
    return dados


def contar(encontradas):
    """"2 entradas e 1 conta", só com o que houver."""
    entradas = sum(r['tipo'] == 'entrada' for _, r in encontradas)
    contas = len(encontradas) - entradas
    partes = ([f'{entradas} entrada' + ('s' if entradas > 1 else '')] if entradas else []) + (
        [f'{contas} conta' + ('s' if contas > 1 else '') + ' de recebimento'] if contas else [])
    return ' e '.join(partes)


def resumo(entrada):
    if entrada.get('tipo') == 'conta':
        return f"Conta {entrada['identificacao']} — {entrada['banco']} — titular {entrada['nome']}"
    try:
        previsao = data_br(entrada['previsao'])
    except ValueError:
        previsao = entrada['previsao']
    return f"{entrada['nome']} — {reais(entrada['previsto'])} — previsão {previsao} — conta {entrada['conta']}"
