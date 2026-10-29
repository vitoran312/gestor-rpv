"""O que mudou nas últimas versões, em linguagem de quem usa o programa (mostrado no "Sobre" e no app).

Cada versão nova entra no topo da lista, com o mesmo número de versao.py (test_novidades confere), e
celular/novidades.json é gerado daqui (python novidades.py), para o app mostrar o mesmo texto.
Tipos: 'novidade' (algo que dá para fazer agora) e 'correcao' (algo que não funcionava como devia).
"""
import json
from pathlib import Path

MOSTRAR = 5  # Quantas versões aparecem no "Sobre".

NOVIDADES = [
    ('0.49.0', [
        ('novidade', 'Celular: usar o app sem computador — cada pessoa cria a própria senha e começa com os dados '
                     'vazios.'),
        ('novidade', 'Celular: sem computador, as contas, as entradas e os recebimentos são gravados no próprio '
                     'celular.'),
        ('novidade', 'Celular: cópia de segurança dos dados do celular, trancada com a senha, para guardar no iCloud '
                     'ou no Google Drive.'),
        ('novidade', 'Celular: "Convidar alguém" em Mais, com link e QR code para mandar o app.'),
    ]),
    ('0.48.0', [
        ('novidade', 'Celular: a abertura do app passa a mostrar o nome GESTOR RPV.'),
    ]),
    ('0.47.0', [
        ('novidade', 'Celular: cadastrar novas contas de recebimento pelo app (aba Contas).'),
        ('novidade', 'Celular: a conta nova já pode ser usada numa entrada, antes mesmo de chegar ao computador.'),
        ('novidade', 'Programa: importa também as contas feitas no celular, junto com as entradas.'),
    ]),
    ('0.46.0', [
        ('correcao', 'Celular: o logo da abertura ficava atrás da janela do Face ID; agora fica mais alto, à vista.'),
    ]),
    ('0.45.0', [
        ('correcao', 'Celular: a janela do Face ID cobria a animação de abertura; agora o logo aparece primeiro e o '
                     'Face ID vem logo depois, com o logo ao fundo.'),
    ]),
    ('0.44.0', [
        ('novidade', 'Celular: os valores ganham a pontuação sozinhos enquanto você digita (1.500,00).'),
        ('novidade', 'Celular: abertura com o logo do app.'),
        ('novidade', 'Celular: com o backup guardado, o app abre direto no Face ID ou na senha, sem a tela de '
                     'escolher arquivo.'),
        ('novidade', 'Lista do que mudou nas últimas versões, no "Sobre" do programa e no app.'),
    ]),
    ('0.43.0', [
        ('novidade', 'Celular: cadastrar novas entradas pelo app.'),
        ('novidade', 'Programa: importar as entradas feitas no celular, que chegam pela pasta do backup no '
                     'Google Drive.'),
    ]),
    ('0.42.0', [
        ('novidade', 'Programa: ao fechar, faz um backup se algo mudou — o celular sempre encontra os dados do '
                     'último uso.'),
        ('correcao', 'Celular: "Sobre este backup" mostrava a versão do programa como se fosse a do app.'),
        ('correcao', 'Celular: PDFs com certas fontes podiam aparecer sem o texto no iPhone.'),
    ]),
    ('0.41.0', [
        ('novidade', 'Celular: a versão do app aparece na tela de abertura.'),
        ('correcao', 'Celular: em alguns iPhones o PDF não abria no app.'),
    ]),
    ('0.40.0', [
        ('novidade', 'Celular: zoom nos PDFs e nas imagens dos anexos.'),
        ('correcao', 'Celular: o PDF abria ampliado, sem caber na tela.'),
    ]),
]

ARQUIVO_APP = Path(__file__).resolve().parent / 'celular' / 'novidades.json'


def contagem(itens):
    """"2 novidades · 1 correção", só com o que houver."""
    novas = sum(tipo == 'novidade' for tipo, _ in itens)
    correcoes = sum(tipo == 'correcao' for tipo, _ in itens)
    partes = []
    if novas:
        partes.append(f'{novas} novidade' + ('s' if novas > 1 else ''))
    if correcoes:
        partes.append(f'{correcoes} ' + ('correções' if correcoes > 1 else 'correção'))
    return ' · '.join(partes)


def ultimas(quantidade=MOSTRAR):
    return NOVIDADES[:quantidade]


def para_o_app():
    return {'versoes': [{'versao': versao, 'resumo': contagem(itens),
                         'itens': [{'tipo': tipo, 'texto': texto} for tipo, texto in itens]}
                        for versao, itens in ultimas()]}


def gerar_json():
    ARQUIVO_APP.write_text(json.dumps(para_o_app(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    gerar_json()
