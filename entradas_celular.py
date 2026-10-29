"""Entradas, contas e mudanças feitas no app do celular, trazidas por arquivos ".rpvcelular".

O app grava cada entrada num arquivo pequeno, cifrado com a chave do backup que estava aberto nele (o mesmo
formato de cifra.py), e a pessoa salva esse arquivo na pasta do backup automático (por exemplo, no Google
Drive). Aqui o programa encontra esses arquivos, abre com a senha dos backups, confere tudo pelas mesmas regras
do formulário e, depois da confirmação, grava as entradas. Cada entrada tem um identificador próprio, anotado
nas configurações depois de importada: o mesmo arquivo nunca entra duas vezes, e o próximo backup leva essa
lista ao celular, que então apaga a cópia que guardava.

Além de entradas e contas novas, o celular manda mudanças em operações que já existem: alteração dos dados,
nova previsão, exclusão (vai para a lixeira) e documentos anexados. Cada mudança leva os valores que o celular
via; se a operação mudou no computador depois daquele backup, a mudança não é aplicada (o computador não perde
o que foi feito nele) e a pessoa é avisada.
"""
import base64
import binascii
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

import cifra
from backup import PASTA_AUTOMATICA, senha_salva
from dados import CAMPOS_CONTA, data_br, normalizar, reais
from diario import log
from documentos import EXTENSOES

EXTENSAO = '.rpvcelular'
FORMATO = 'gestor-rpv-celular'
IMPORTADAS = 'entradas_celular_importadas'
PASTA_IMPORTADOS = 'importados-do-celular'
LIMITE_ARQUIVO = 40 * 1024 * 1024  # Uma entrada tem poucos KB; um documento, até uns 25 MB (PDF) em base64.
IDENTIFICADOR = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
CAMPOS = {'id': str, 'nome': str, 'aquisicao': str, 'custo': int, 'previsto': int, 'conta_id': int, 'conta': str,
          'previsao': str, 'comissao': (int, type(None)), 'observacoes': str, 'criada_em': str}
CAMPOS_DA_CONTA = {'id': str, 'criada_em': str, **{campo: str for campo in CAMPOS_CONTA}}
# Campos de uma operação que o celular pode alterar (os valores como estão gravados no banco).
CAMPOS_EDITAVEIS = {'nome': str, 'aquisicao': str, 'custo': int, 'previsto': int, 'conta_id': (int, type(None)),
                    'conta': str, 'previsao': str, 'comissao': (int, type(None)), 'observacoes': str}
TITULOS_EDITAVEIS = {'nome': 'titular', 'aquisicao': 'data de aquisição', 'custo': 'valor de aquisição',
                     'previsto': 'Valor Total RPV', 'conta_id': 'conta de destino', 'conta': 'conta de destino',
                     'previsao': 'previsão inicial', 'comissao': 'comissão', 'observacoes': 'observações'}
MUDANCA = {'id': str, 'operacao_id': int, 'nome': str, 'criada_em': str}
TIPOS = {
    'entrada': CAMPOS, 'conta': CAMPOS_DA_CONTA,
    'alteracao': {**MUDANCA, 'antes': dict, 'depois': dict},
    'previsao': {**MUDANCA, 'anterior': str, 'nova': str},
    'exclusao': MUDANCA,
    'anexo': {**MUDANCA, 'arquivo': str, 'conteudo': str},
}
OPCIONAIS = {'entrada': {'anexos': list}}  # Documentos que vêm junto com uma entrada nova.
DOCUMENTO = {'arquivo': str, 'conteudo': str}
# Ordem de importação: contas antes das entradas que as usam, e mudanças depois das entradas.
ORDEM = {'conta': 0, 'entrada': 1, 'alteracao': 2, 'previsao': 3, 'anexo': 4, 'exclusao': 5}
NOMES_TIPOS = {'entrada': ('entrada', 'entradas'), 'conta': ('conta de recebimento', 'contas de recebimento'),
               'alteracao': ('alteração', 'alterações'), 'previsao': ('nova previsão', 'novas previsões'),
               'anexo': ('documento', 'documentos'), 'exclusao': ('exclusão', 'exclusões')}


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
    if not conforme(registro, TIPOS[tipo], OPCIONAIS.get(tipo, {})) or not IDENTIFICADOR.fullmatch(registro['id']):
        raise ValueError('O arquivo do celular está incompleto.')
    registro = {**registro, 'tipo': tipo}
    if tipo == 'alteracao' and not all(conforme(registro[lado], CAMPOS_EDITAVEIS) for lado in ('antes', 'depois')):
        raise ValueError('O arquivo do celular está incompleto.')
    if tipo == 'anexo':
        registro['conteudo'] = documento(registro)
    if tipo == 'entrada':
        anexos = registro.get('anexos', [])
        if not all(conforme(a, DOCUMENTO) for a in anexos):
            raise ValueError('O arquivo do celular está incompleto.')
        registro['anexos'] = [{'arquivo': a['arquivo'], 'conteudo': documento(a)} for a in anexos]
    return registro


def conforme(registro, esquema, opcionais=None):
    """O registro tem exatamente os campos do esquema (mais os opcionais presentes), cada um do tipo certo."""
    opcionais = opcionais or {}
    if not isinstance(registro, dict) or not set(esquema) <= set(registro) <= set(esquema) | set(opcionais):
        return False
    tipos = {**esquema, **opcionais}
    return all(isinstance(valor, tipos[campo]) and not isinstance(valor, bool) for campo, valor in registro.items())


def documento(registro):
    """Bytes de um documento mandado pelo celular (em base64), com nome e tipo aceitos pelo programa."""
    nome_do_documento(registro['arquivo'])
    try:
        return base64.b64decode(registro['conteudo'], validate=True)
    except (binascii.Error, ValueError):
        raise ValueError('Um documento do arquivo do celular está ilegível.') from None


def nome_do_documento(arquivo):
    """Nome seguro para gravar no Windows: sem pastas nem caracteres proibidos, e só PDF ou imagem."""
    nome = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', arquivo.replace('\\', '/').rsplit('/', 1)[-1]).strip(' .')[-120:]
    extensao = Path(nome).suffix.lower()
    if extensao not in EXTENSOES:
        raise ValueError('O celular mandou um documento que não é PDF nem imagem.')
    return nome if Path(nome).stem.strip(' .') else 'documento' + extensao


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
    """Grava contas, entradas e mudanças. Devolve (importadas, problemas): a quantidade gravada e (nome, mensagem)
    das recusadas. As contas vêm primeiro: uma entrada feita no celular com uma conta nova a encontra já cadastrada.

    Uma entrada ou conta recusada continua na pasta (corrigida no celular, chega de novo); uma mudança recusada
    (a operação mudou no computador, ou saiu da lista) não teria como dar certo depois: sai da pasta como as
    importadas, para não ser perguntada de novo a cada abertura.
    """
    gravadas, problemas = 0, []
    ja = importadas(banco)
    for arquivo, registro in sorted(encontradas, key=lambda item: (ORDEM[item[1]['tipo']], item[1]['criada_em'])):
        if registro['id'] in ja:
            continue
        try:
            APLICAR[registro['tipo']](banco, registro)
            gravadas += 1
        except ValueError as erro:
            problemas.append((nome_do_registro(registro), str(erro)))
            if registro['tipo'] in ('entrada', 'conta'):
                continue
        ja.add(registro['id'])
        banco.salvar_configuracao(IMPORTADAS, json.dumps(sorted(ja)))
        guardar(arquivo)
    return gravadas, problemas


def nome_do_registro(registro):
    return registro['identificacao'] if registro['tipo'] == 'conta' else registro['nome']


def aplicar_conta(banco, registro):
    banco.salvar_conta({campo: registro[campo] for campo in CAMPOS_CONTA})


def aplicar_entrada(banco, registro):
    with documentos_temporarios(registro.get('anexos', [])) as anexos:
        banco.salvar(dados_da_entrada(banco, registro), anexos=anexos)


def operacao_ativa(banco, registro):
    atual = banco.obter(registro['operacao_id'])
    if atual is None or atual['lixeira_em']:
        raise ValueError('A operação não está mais na lista ativa do computador; a mudança do celular não foi aplicada.')
    return atual


def aplicar_alteracao(banco, registro):
    """Só os campos que o celular mudou são gravados, e só se o computador ainda tem o que o celular via."""
    atual = operacao_ativa(banco, registro)
    antes, depois = registro['antes'], registro['depois']
    mudou = [campo for campo in CAMPOS_EDITAVEIS if antes[campo] != depois[campo]]
    conflitos = dict.fromkeys(TITULOS_EDITAVEIS[c] for c in mudou if atual[c] != antes[c])
    if conflitos:
        raise ValueError(f'Alterada no computador depois do backup usado no celular ({", ".join(conflitos)}); '
                         'a alteração do celular não foi aplicada.')
    if not mudou:
        return
    dados = {campo: atual[campo] for campo in ('nome', 'aquisicao', 'custo', 'previsto', 'previsao', 'comissao',
                                                'observacoes', 'conta_id', 'conta')}
    dados.update({campo: depois[campo] for campo in mudou})
    if {'conta_id', 'conta'} & set(mudou):
        conta = conta_do_celular(banco, depois['conta_id'], depois['conta'])
        dados['conta_id'] = conta['id'] if conta else -1
        dados['conta'] = conta['identificacao'] if conta else depois['conta']
    banco.salvar(dados, registro['operacao_id'])


def aplicar_previsao(banco, registro):
    atual = operacao_ativa(banco, registro)
    if atual['previsao_atual'] == registro['nova']:
        return
    if atual['previsao_atual'] != registro['anterior']:
        raise ValueError(f'A previsão foi alterada no computador (agora {data_br(atual["previsao_atual"])}); '
                         'a nova previsão do celular não foi aplicada.')
    banco.atualizar_previsao(registro['operacao_id'], registro['nova'])


def aplicar_exclusao(banco, registro):
    atual = banco.obter(registro['operacao_id'])
    if atual is None:
        raise ValueError('A operação não existe mais no computador.')
    if not atual['lixeira_em']:
        banco.excluir(registro['operacao_id'])


def aplicar_anexo(banco, registro):
    operacao_ativa(banco, registro)
    with documentos_temporarios([registro]) as anexos:
        banco.anexar(registro['operacao_id'], anexos)


APLICAR = {'conta': aplicar_conta, 'entrada': aplicar_entrada, 'alteracao': aplicar_alteracao,
           'previsao': aplicar_previsao, 'exclusao': aplicar_exclusao, 'anexo': aplicar_anexo}


@contextmanager
def documentos_temporarios(documentos):
    """Grava os documentos do celular em arquivos temporários, com o nome original, para o banco copiar."""
    with tempfile.TemporaryDirectory(prefix='.celular-rpv-') as pasta:
        caminhos = []
        for numero, item in enumerate(documentos):
            subpasta = Path(pasta) / str(numero)  # Dois documentos com o mesmo nome não se sobrepõem.
            subpasta.mkdir()
            caminho = subpasta / nome_do_documento(item['arquivo'])
            caminho.write_bytes(item['conteudo'])
            caminhos.append(caminho)
        yield caminhos


def conta_do_celular(banco, conta_id, nome):
    # A conta é procurada pelo número; se não existir (conta nova feita no celular, ou removida no computador),
    # pelo nome, sem diferença de maiúsculas e acentos.
    contas = {c['id']: c for c in banco.contas()}
    return contas.get(conta_id) or next(
        (c for c in contas.values() if normalizar(c['identificacao']) == normalizar(nome)), None)


def dados_da_entrada(banco, entrada):
    dados = {campo: entrada[campo] for campo in ('nome', 'aquisicao', 'custo', 'previsto', 'previsao', 'comissao',
                                                 'observacoes')}
    conta = conta_do_celular(banco, entrada['conta_id'], entrada['conta'])
    dados['conta_id'] = conta['id'] if conta else -1
    dados['conta'] = conta['identificacao'] if conta else entrada['conta']
    return dados


def contar(encontradas):
    """"2 entradas, 1 alteração e 1 documento", só com o que houver."""
    partes = []
    for tipo, (singular, plural) in NOMES_TIPOS.items():
        quantos = sum(r['tipo'] == tipo for _, r in encontradas)
        if quantos:
            partes.append(f'{quantos} {singular if quantos == 1 else plural}')
    return ', '.join(partes[:-1]) + ' e ' + partes[-1] if len(partes) > 1 else ''.join(partes)


def resumo(entrada):
    tipo = entrada.get('tipo')
    if tipo == 'conta':
        return f"Conta {entrada['identificacao']} — {entrada['banco']} — titular {entrada['nome']}"
    if tipo == 'alteracao':
        mudou = dict.fromkeys(TITULOS_EDITAVEIS[c] for c in CAMPOS_EDITAVEIS
                              if entrada['antes'][c] != entrada['depois'][c])
        return f"Alteração em {entrada['nome']} — {', '.join(mudou) or 'nada mudou'}"
    if tipo == 'previsao':
        return f"Nova previsão de {entrada['nome']} — {data_ou_texto(entrada['anterior'])} → {data_ou_texto(entrada['nova'])}"
    if tipo == 'exclusao':
        return f"Excluir {entrada['nome']} (vai para a lixeira)"
    if tipo == 'anexo':
        return f"Documento para {entrada['nome']} — {entrada['arquivo']}"
    texto = (f"{entrada['nome']} — {reais(entrada['previsto'])} — previsão {data_ou_texto(entrada['previsao'])} — "
             f"conta {entrada['conta']}")
    anexos = len(entrada.get('anexos', []))
    return texto + (f' — {anexos} documento' + ('s' if anexos > 1 else '') if anexos else '')


def data_ou_texto(texto):
    try:
        return data_br(texto)
    except ValueError:
        return texto
