"""O que mudou nas últimas versões, em linguagem de quem usa o programa (mostrado no "Sobre" e no app).

Cada versão nova entra no topo da lista, com o mesmo número de versao.py (test_novidades confere), e
celular/novidades.json é gerado daqui (python novidades.py), para o app mostrar o mesmo texto.
Tipos: 'novidade' (algo que dá para fazer agora) e 'correcao' (algo que não funcionava como devia).
"""
import json
from pathlib import Path

MOSTRAR = 5  # Quantas versões aparecem no "Sobre".

NOVIDADES = [
    ('0.60.0', [
        ('novidade', 'Celular: tema Claro, Escuro ou Automático (o do iPhone), em Mais → Aparência.'),
        ('novidade', 'Celular: "Voltar" em todas as telas, inclusive Operações, Contas e Mais, e nos passos da abertura.'),
        ('novidade', 'Celular: tocar de novo na aba acesa também volta (do detalhe para a lista; da lista, para a '
                     'tela anterior).'),
        ('correcao', 'Celular: contraste reforçado no tema claro (terracota, vermelho e setas).'),
    ]),
    ('0.59.0', [
        ('novidade', 'Celular: novo visual em creme, terracota e azul-marinho, com ícones, cartões mais claros e '
                     'tema escuro combinando.'),
        ('novidade', 'Celular: Início com "Seu panorama" e o lucro previsto em destaque; operações com as iniciais '
                     'e a faixa da situação.'),
        ('novidade', 'Celular: Mais organizado em grupos; abas com a aba escolhida em terracota.'),
        ('novidade', 'Celular: transições suaves entre telas e um aviso rápido depois de gravar algo no celular.'),
    ]),
    ('0.58.0', [
        ('novidade', 'Celular: editar, desativar, reativar e remover contas de recebimento, para quem usa só o '
                     'celular.'),
    ]),
    ('0.57.0', [
        ('novidade', 'Celular: "Excluir permanentemente" na lixeira, para quem usa só o celular; a operação sai de vez, '
                     'com os documentos.'),
    ]),
    ('0.56.0', [
        ('novidade', 'Programa e celular: senha nova com no mínimo 6 caracteres (antes 10), misturando letras, números '
                     'e símbolos.'),
    ]),
    ('0.55.0', [
        ('novidade', 'Celular: nova identidade visual Ledger, igual à do programa: porcelana e nanquim no claro, '
                     'nanquim e marfim no escuro, acento champanhe e títulos em serifa.'),
        ('novidade', 'Celular: Início com a data por extenso e o panorama num cartão em nanquim, com o lucro '
                     'previsto em destaque.'),
        ('novidade', 'Celular: barra de abas flutuante, translúcida e com ícones; cabeçalho translúcido.'),
        ('novidade', 'Celular: operações com filete colorido pela situação e selos em pílula; resumo em imagem '
                     'com as novas cores.'),
    ]),
    ('0.54.0', [
        ('novidade', 'Programa: nova identidade visual Ledger, em nanquim e champanhe, com títulos em serifa e cartões '
                     'com sombra suave.'),
        ('novidade', 'Programa: barra lateral sempre visível com Nova entrada, as páginas, backup, Excel, tema e '
                     'Sobre; recolhe para ícones em janelas estreitas.'),
        ('novidade', 'Programa: tela inicial com a data por extenso e o cartão de destaque em nanquim.'),
        ('novidade', 'Programa: gráfico mensal com barras planas de topo arredondado.'),
    ]),
    ('0.53.0', [
        ('novidade', 'Programa: Minhas operações com os indicadores no topo, busca com lupa e Lixeira identificada.'),
        ('novidade', 'Programa: campos com problema ficam contornados em vermelho ao salvar, até serem corrigidos.'),
        ('novidade', 'Programa: avisos rápidos confirmam o que foi salvo, recebido, excluído ou restaurado.'),
        ('novidade', 'Programa: tabelas realçam a linha sob o mouse e explicam quando não há nada para mostrar.'),
        ('novidade', 'Programa e celular: transições suaves e foco visível pelo teclado, com menos movimento quando '
                     'o sistema pede.'),
    ]),
    ('0.52.0', [
        ('novidade', 'Celular: "Abrir um backup mais novo" em Mais, sem precisar recusar o Face ID.'),
        ('novidade', 'Celular: na primeira abertura, uma demonstração com dados fictícios mostra como o app fica.'),
    ]),
    ('0.51.1', [
        ('correcao', 'Celular: no iPhone, a tela da operação voltava sozinha para cima e escondia os botões do fim '
                     '(anexar, alterar previsão, editar e excluir).'),
    ]),
    ('0.51.0', [
        ('novidade', 'Celular: modo discreto — o olho no topo esconde todos os valores em reais (R$ •••••).'),
        ('novidade', 'Celular: "Colar e preencher" na entrada nova — cole a mensagem do cliente e o app preenche nome, '
                     'valores e datas.'),
        ('novidade', 'Celular: resumo da operação em imagem, com o logo, para mandar no WhatsApp sem dados sensíveis.'),
    ]),
    ('0.50.0', [
        ('novidade', 'Celular: editar os dados de uma entrada, alterar a previsão e excluir operações pelo app.'),
        ('novidade', 'Celular: anexar fotos (direto da câmera) e PDFs às operações e às entradas novas.'),
        ('novidade', 'Celular: agenda das previsões — calendário do mês e, no Início, quantas vencem hoje, amanhã e '
                     'nos próximos 7 dias, além das atrasadas.'),
        ('novidade', 'Programa: importa do celular alterações, previsões, exclusões e documentos, sem gravar por cima '
                     'do que mudou no computador.'),
    ]),
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
