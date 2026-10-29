"""Elementos da identidade Ledger: superfícies com sombra suave, cantos arredondados e ícones, só com a
biblioteca padrão (as imagens são PNGs gerados aqui mesmo)."""
import math
import struct
import zlib
from functools import lru_cache
import tkinter as tk
from tkinter import ttk, font as tkfont
from tema import cores


# Abaixo desta largura (em pixels a 100% de escala), telas com cartões lado a lado passam a empilhá-los.
LARGURA_LAYOUT_LARGO = 1100
# Bits de evento.state das teclas que mudam o clique (Shift e Ctrl): com elas, o clique só seleciona.
MODIFICADORES_SELECAO = 0x0001 | 0x0004


def familia_fonte(raiz):
    raiz = raiz._root()
    if hasattr(raiz, '_familia_pro'):
        return raiz._familia_pro
    disponiveis = {f.casefold() for f in tkfont.families(raiz)}
    raiz._familia_pro = next((f for f in ('Segoe UI', 'Inter', 'DejaVu Sans', 'Liberation Sans', 'Helvetica') if f.casefold() in disponiveis), tkfont.nametofont('TkDefaultFont').actual('family'))
    return raiz._familia_pro


def familia_titulo(raiz):
    """Serifada para títulos (o tom editorial de um banco privado); sem nenhuma instalada, a mesma da interface."""
    raiz = raiz._root()
    if not hasattr(raiz, '_familia_titulo'):
        disponiveis = {f.casefold() for f in tkfont.families(raiz)}
        raiz._familia_titulo = next((f for f in ('Georgia', 'Cambria', 'Constantia', 'DejaVu Serif', 'Liberation Serif')
                                     if f.casefold() in disponiveis), familia_fonte(raiz))
    return raiz._familia_titulo


def fator_escala(widget):
    """Quanto a tela amplia em relação a 96 DPI (1,0 em 100%, 1,5 em 150%); nunca reduz."""
    raiz = widget._root()
    if not hasattr(raiz, '_fator_escala'):
        raiz._fator_escala = max(1.0, raiz.winfo_fpixels('1i') / 96)
    return raiz._fator_escala


def px(widget, valor):
    """Converte uma medida pensada para 100% de escala em pixels da tela atual."""
    return round(valor * fator_escala(widget))


def _rgb(cor):
    return tuple(int(cor[i:i + 2], 16) for i in (1, 3, 5))


def misturar(cor, destino, peso):
    """Cor entre `cor` (peso 0) e `destino` (peso 1), em #rrggbb."""
    return '#' + ''.join(f'{round(x + (y - x) * peso):02x}' for x, y in zip(_rgb(cor), _rgb(destino)))


@lru_cache(maxsize=8)
def _mascara_arredondada(largura, altura, raio):
    """Cobertura do preenchimento e do contorno de 1 px, calculada uma vez por geometria."""
    def distancia(x, y):
        qx, qy = abs(x - largura / 2) - (largura / 2 - raio), abs(y - altura / 2) - (altura / 2 - raio)
        return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - raio
    amostras = ((.25, .25), (.75, .25), (.25, .75), (.75, .75))
    mascara = []
    for y in range(altura):
        for x in range(largura):
            dentro = sum(distancia(x + dx, y + dy) <= 0 for dx, dy in amostras) / 4
            miolo = sum(distancia(x + dx, y + dy) <= -1 for dx, dy in amostras) / 4
            mascara.append((dentro, miolo))
    return tuple(mascara)


def _distancia_retangulo(x, y, x0, y0, x1, y1, raio):
    """Distância com sinal até um retângulo arredondado (negativa dentro)."""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    qx, qy = abs(x - cx) - ((x1 - x0) / 2 - raio), abs(y - cy) - ((y1 - y0) / 2 - raio)
    return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - raio


def margens_sombra(sombra):
    """(esquerda, topo, direita, base) que a sombra ocupa em volta da superfície."""
    if not sombra:
        return (0, 0, 0, 0)
    _cor, alcance, queda, _opacidade = sombra
    return (alcance, max(0, alcance - queda), alcance, alcance + queda)


def _pixels_com_sombra(cor, contorno, raio, largura, altura, sombra):
    """Linhas RGBA de uma superfície com sombra: a forma fica recuada pelas margens e a sombra se espalha
    em volta, mais forte embaixo (luz vinda de cima), caindo suavemente até zero no alcance."""
    cor_sombra, alcance, queda, opacidade = sombra
    esquerda, topo, direita, base = margens_sombra(sombra)
    x0, y0, x1, y1 = esquerda, topo, largura - direita, altura - base
    rgb, borda, escura = _rgb(cor), _rgb(contorno or cor), _rgb(cor_sombra)
    amostras = ((.25, .25), (.75, .25), (.25, .75), (.75, .75))
    linhas = []
    for y in range(altura):
        linha = bytearray()
        for x in range(largura):
            dentro = miolo = 0
            for dx, dy in amostras:
                d = _distancia_retangulo(x + dx, y + dy, x0, y0, x1, y1, raio)
                dentro += d <= 0
                miolo += d <= -1
            dentro, miolo = dentro / 4, miolo / 4
            d_sombra = max(0.0, _distancia_retangulo(x + .5, y + .5 - queda, x0, y0, x1, y1, raio))
            alfa_sombra = opacidade * math.exp(-3.2 * (d_sombra / max(1, alcance)) ** 2) * (1 if d_sombra < alcance else 0)
            peso = miolo / dentro if dentro else 0
            superficie = [a * peso + b * (1 - peso) for a, b in zip(rgb, borda)]
            alfa = dentro + alfa_sombra * (1 - dentro)
            if alfa <= 0:
                linha.extend((0, 0, 0, 0))
                continue
            mistura = [(s * dentro + e * alfa_sombra * (1 - dentro)) / alfa for s, e in zip(superficie, escura)]
            linha.extend((*(round(v) for v in mistura), round(255 * alfa)))
        linhas.append(linha)
    return linhas


def _codificar_png(largura, altura, dados):
    def bloco(nome, valor):
        return struct.pack('!I', len(valor)) + nome + valor + struct.pack('!I', zlib.crc32(nome + valor)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + bloco(b'IHDR', struct.pack('!2I5B', largura, altura, 8, 6, 0, 0, 0)) +
            bloco(b'IDAT', zlib.compress(bytes(dados))) + bloco(b'IEND', b''))


def _pixels_arredondados(cor, contorno, raio, largura, altura):
    """Linhas de pixels RGBA de uma superfície pequena, calculada amostra a amostra."""
    rgb, borda = _rgb(cor), _rgb(contorno or cor)
    linhas = []
    for indice, (dentro, miolo) in enumerate(_mascara_arredondada(largura, altura, raio)):
        if indice % largura == 0: linhas.append(bytearray())
        peso = miolo / dentro if dentro else 0
        linhas[-1].extend((*(round(a * peso + b * (1 - peso)) for a, b in zip(rgb, borda)), round(255 * dentro)))
    return linhas


@lru_cache(maxsize=64)
def _png_arredondado(cor, contorno=None, raio=8, largura=40, altura=36, sombra=None):
    """Superfície plana: preenchimento com contorno opcional de 1 px, sem sombra.

    Só os cantos dependem do raio; o resto repete a faixa reta central. Por isso a imagem grande é montada
    a partir de uma pequena, sem calcular pixel a pixel — o que permite gerar superfícies do tamanho real
    dos cartões e botões (veja aplicar_superficies).
    """
    esquerda, topo, direita, fundo_sombra = margens_sombra(sombra)
    lado = raio + 2 + max(esquerda, topo, direita, fundo_sombra)
    # Em formatos de pílula (menores que dois cantos), aquela dimensão é calculada inteira, sem esticar.
    lx = lado if largura >= 2 * lado else None
    ly = lado if altura >= 2 * lado else None
    medidas = (2 * lx if lx else largura, 2 * ly if ly else altura)
    base = (_pixels_com_sombra(cor, contorno, raio, *medidas, sombra) if sombra
            else _pixels_arredondados(cor, contorno, raio, *medidas))
    def linha(j):
        pixels = base[j]
        if not lx:
            return pixels
        return pixels[:4 * lx] + pixels[4 * lx:4 * lx + 4] * (largura - 2 * lx) + pixels[4 * lx:]
    if ly:
        linhas = [linha(j) for j in range(ly)] + [linha(ly)] * (altura - 2 * ly) + [linha(j) for j in range(ly, 2 * ly)]
    else:
        linhas = [linha(j) for j in range(altura)]
    dados = bytearray()
    for pixels in linhas:
        dados.append(0)
        dados.extend(pixels)
    return _codificar_png(largura, altura, dados)


def _png_recebido(c, selecionado):
    """Indicador de 24 px; a margem separa a caixa da data do recebimento."""
    fundo = _rgb(c['primario'] if selecionado else c['campo'])
    borda = _rgb(c['primario'] if selecionado else c['secundario'])
    marca = _rgb(c['primario_texto'])
    def segmento(x, y, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        t = max(0, min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy)))
        return math.hypot(x - a[0] - t * dx, y - a[1] - t * dy)
    dados = bytearray()
    for y in range(26):
        dados.append(0)
        for x in range(31):
            amostras = []
            for dx, dy in ((.25, .25), (.75, .25), (.25, .75), (.75, .75)):
                px, py = x + dx, y + dy
                qx, qy = abs(px - 13) - 8, abs(py - 13) - 8
                d = math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - 4
                if d > 0:
                    continue
                cor = borda if d > -1.5 else fundo
                if selecionado and min(segmento(px, py, (6.5, 13), (11, 17.5)), segmento(px, py, (11, 17.5), (19.5, 8.5))) <= 1.3:
                    cor = marca
                amostras.append(cor)
            if amostras:
                dados.extend((*[round(sum(a[i] for a in amostras) / len(amostras)) for i in range(3)], round(255 * len(amostras) / 4)))
            else:
                dados.extend((0, 0, 0, 0))
    return _codificar_png(31, 26, dados)


def icone_tema(raiz, modo, cor=None):
    """Lua para ativar o escuro e sol para ativar o claro, sem depender de uma fonte de símbolos."""
    cache = getattr(raiz, '_icones_modo', {})
    raiz._icones_modo = cache
    cor = cor or cores()['texto']
    chave = (modo, cor)
    if chave not in cache:
        rgb = _rgb(cor)
        def dentro(x, y):
            if modo == 'claro':
                return math.hypot(x - 10, y - 10) <= 8 and math.hypot(x - 14, y - 7) > 7.5
            if math.hypot(x - 10, y - 10) <= 4:
                return True
            for i in range(8):
                angulo = i * math.pi / 4
                ux, uy = math.cos(angulo), math.sin(angulo)
                proj = max(6.5, min(9, (x - 10) * ux + (y - 10) * uy))
                if math.hypot(x - 10 - proj * ux, y - 10 - proj * uy) <= .75:
                    return True
            return False
        dados = bytearray()
        for y in range(20):
            dados.append(0)
            for x in range(20):
                alpha = round(255 * sum(dentro(x + dx, y + dy) for dx, dy in ((.25, .25), (.75, .25), (.25, .75), (.75, .75))) / 4)
                dados.extend((*rgb, alpha))
        cache[chave] = tk.PhotoImage(master=raiz, data=_codificar_png(20, 20, dados))
    return cache[chave]


def _icone_desenhado(raiz, nome, lado, dentro, cor):
    """Ícone de uma cor só, com bordas suavizadas (quatro amostras por pixel), guardado por nome e cor."""
    cache = getattr(raiz, '_icones_desenhados', {})
    raiz._icones_desenhados = cache
    chave = (nome, lado, cor)
    if chave not in cache:
        rgb = _rgb(cor)
        dados = bytearray()
        for y in range(lado):
            dados.append(0)
            for x in range(lado):
                cobertura = sum(dentro(x + dx, y + dy) for dx, dy in ((.25, .25), (.75, .25), (.25, .75), (.75, .75))) / 4
                dados.extend((*rgb, round(255 * cobertura)))
        cache[chave] = tk.PhotoImage(master=raiz, data=_codificar_png(lado, lado, dados))
    return cache[chave]


def _segmento(x, y, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0, min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - a[0] - t * dx, y - a[1] - t * dy)


def icone_busca(raiz, cor):
    """Lupa de 18 px para o campo de busca."""
    return _icone_desenhado(raiz, 'busca', 18, lambda x, y: abs(math.hypot(x - 7.5, y - 7.5) - 5) <= .8
                            or _segmento(x, y, (11.3, 11.3), (15.5, 15.5)) <= 1, cor)


def icone_limpar(raiz, cor):
    """× de 14 px, para limpar a busca."""
    return _icone_desenhado(raiz, 'limpar', 14, lambda x, y: min(_segmento(x, y, (3.5, 3.5), (10.5, 10.5)),
                                                                _segmento(x, y, (10.5, 3.5), (3.5, 10.5))) <= .8, cor)


def sombra_cartao(c):
    """Sombra dos cartões: tinta quente e leve no claro; preta e mais densa no escuro, onde precisa aparecer."""
    escuro = c['fundo'] < '#808080'
    return (c['sombra'], 12, 4, 0.42 if escuro else 0.09)


def _tracos(segmentos, aneis=(), largura=0.85):
    """Desenho de linha: segmentos [(x0, y0, x1, y1)] e anéis [(cx, cy, raio)], com espessura uniforme."""
    def dentro(x, y):
        return (any(_segmento(x, y, (a, b), (c, d)) <= largura for a, b, c, d in segmentos)
                or any(abs(math.hypot(x - cx, y - cy) - r) <= largura for cx, cy, r in aneis))
    return dentro


def _polilinha(*pontos):
    return [(*pontos[i], *pontos[i + 1]) for i in range(len(pontos) - 1)]


# Ícones da navegação, num quadro de 20 px: traço de 1,7 px, cantos simples, mesma família visual.
DESENHOS = {
    'inicio': _tracos(_polilinha((3, 10), (10, 3.5), (17, 10)) + _polilinha((5, 8.5), (5, 16.5), (15, 16.5), (15, 8.5))
                      + _polilinha((8.5, 16.5), (8.5, 12), (11.5, 12), (11.5, 16.5))),
    'operacoes': _tracos([(7, 5, 17, 5), (7, 10, 17, 10), (7, 15, 17, 15), (3, 5, 3.6, 5), (3, 10, 3.6, 10), (3, 15, 3.6, 15)]),
    'contas': _tracos(_polilinha((3, 7.5), (10, 3), (17, 7.5), (3, 7.5)) + [(5.5, 9.5, 5.5, 14.5), (10, 9.5, 10, 14.5),
                                                                      (14.5, 9.5, 14.5, 14.5), (3, 17, 17, 17)]),
    'grafico': _tracos([(3, 17, 17, 17), (5.5, 14.5, 5.5, 10), (10, 14.5, 10, 5), (14.5, 14.5, 14.5, 8)]),
    'calculadora': _tracos(_polilinha((4.5, 2.5), (15.5, 2.5), (15.5, 17.5), (4.5, 17.5), (4.5, 2.5))
                           + [(7, 6, 13, 6), (7, 10, 7.4, 10), (10, 10, 10.4, 10), (13, 10, 13.4, 10), (7, 14, 7.4, 14),
                              (10, 14, 10.4, 14), (13, 14, 13.4, 14)]),
    'backup': _tracos(_polilinha((3, 12), (3, 17), (17, 17), (17, 12)) + [(10, 3, 10, 13)] + _polilinha((6, 7), (10, 3), (14, 7))),
    'exportar': _tracos(_polilinha((11, 3), (5, 3), (5, 17), (15, 17), (15, 11)) + [(9, 11, 17, 3)] + _polilinha((12, 3), (17, 3), (17, 8))),
    'sobre': _tracos([(10, 9, 10, 14.5), (10, 5.8, 10, 6.2)], [(10, 10, 7.5)]),
    'sair': _tracos(_polilinha((11, 3), (4, 3), (4, 17), (11, 17)) + [(8, 10, 17, 10)] + _polilinha((13.5, 6.5), (17, 10), (13.5, 13.5))),
    'nova': _tracos([(10, 4, 10, 16), (4, 10, 16, 10)], largura=1.0),
}


def icone_navegacao(raiz, nome, cor):
    """Ícone de linha de 20 px para a barra lateral (veja DESENHOS)."""
    return _icone_desenhado(raiz, 'nav-' + nome, 20, DESENHOS[nome], cor)


def aplicar_superficies(raiz):
    """Imagens guardadas pela raiz; estilos nativos mantêm foco, teclado e acessibilidade."""
    c = cores()
    estilo = ttk.Style(raiz)
    cache = getattr(raiz, '_superficies_pro', {})
    raiz._superficies_pro = cache
    chave = c['fundo']
    if chave not in cache:
        imagens = {}
        for nome, cor, contorno in (('botao', c['botao'], c['borda']), ('ativo', c['ativo'], c['borda']),
                                  ('pressionado', c['selecao'], c['marca']),
                                  ('primario', c['primario'], None), ('primario_ativo', c['primario_ativo'], None),
                                  ('primario_pressionado', c['primario_pressionado'], None),
                                  ('inativo', c['fundo'], c['borda_suave']),
                                  ('foco', c['ativo'], c['marca']),
                                  ('primario_foco', c['primario_ativo'], c['texto'])):
            imagens[nome] = tk.PhotoImage(master=raiz, data=_png_arredondado(cor, contorno, 8, 480, 48))
        # O ttk preenche o miolo repetindo a imagem como azulejos; no Windows, centenas de azulejos pequenos
        # com transparência tornavam lenta a troca de tema. Imagens do tamanho real cobrem cada superfície
        # com um ou dois azulejos; os tamanhos mínimos das superfícies continuam os mesmos.
        imagens['filtro'] = tk.PhotoImage(master=raiz, data=_png_arredondado(c['fundo'], c['borda_suave'], 16, 240, 32))
        imagens['filtro_ativo'] = tk.PhotoImage(master=raiz, data=_png_arredondado(c['ativo'], c['borda'], 16, 240, 32))
        imagens['filtro_selecionado'] = tk.PhotoImage(master=raiz, data=_png_arredondado(c['realce'], c['marca'], 16, 240, 32))
        sombra = sombra_cartao(c)
        imagens['cartao'] = tk.PhotoImage(master=raiz, data=_png_arredondado(c['superficie'], c['borda_suave'], 14, 1200, 800,
                                                                             sombra))
        # Barra lateral (fundo herói): itens planos que acendem sob o mouse; o ativo fica num tom mais claro.
        for nome, cor, contorno in (('lateral', c['heroi'], None), ('lateral_hover', c['heroi_hover'], None),
                                    ('lateral_ativo', c['heroi_ativo'], None), ('lateral_foco', c['heroi_hover'], c['acento']),
                                    ('acento', c['acento'], None), ('acento_hover', c['acento_hover'], None),
                                    ('acento_pressionado', c['acento_pressionado'], None),
                                    ('acento_foco', c['acento_hover'], c['heroi_texto'])):
            imagens[nome] = tk.PhotoImage(master=raiz, data=_png_arredondado(cor, contorno, 10, 480, 48))
        prefixo = 'Pro' + chave[1:]
        # Ordem dos estados: o primeiro que valer decide (desativado, pressionado, sob o mouse, com foco).
        for nome, normal, hover, pressionado, foco in (('secundario', 'botao', 'ativo', 'pressionado', 'foco'),
                                                      ('primario', 'primario', 'primario_ativo', 'primario_pressionado',
                                                       'primario_foco')):
            estilo.element_create(prefixo + nome, 'image', imagens[normal],
                                  ('disabled', imagens['inativo']), ('pressed', imagens[pressionado]),
                                  ('active', imagens[hover]), ('focus', imagens[foco]),
                                  border=(10, 10, 10, 10), padding=0, width=40, height=36, sticky='nsew')
        estilo.element_create(prefixo + 'filtro', 'image', imagens['filtro'], ('selected', imagens['filtro_selecionado']),
                              ('active', imagens['filtro_ativo']), border=(16, 14, 16, 14), padding=0, width=40, height=32, sticky='nsew')
        esquerda, topo, direita, base = margens_sombra(sombra)
        # A sombra fica fora da área do conteúdo (padding), que começa na borda visível do cartão.
        estilo.element_create(prefixo + 'cartao', 'image', imagens['cartao'],
                              border=(16 + esquerda, 16 + topo, 16 + direita, 16 + base),
                              padding=(esquerda, topo, direita, base), width=64, height=64, sticky='nsew')
        estilo.element_create(prefixo + 'lateral', 'image', imagens['lateral'], ('pressed', imagens['lateral_ativo']),
                              ('selected', imagens['lateral_ativo']), ('active', imagens['lateral_hover']),
                              ('focus', imagens['lateral_foco']), border=(12, 12, 12, 12), padding=0, width=40, height=36,
                              sticky='nsew')
        estilo.element_create(prefixo + 'acento', 'image', imagens['acento'], ('disabled', imagens['inativo']),
                              ('pressed', imagens['acento_pressionado']), ('active', imagens['acento_hover']),
                              ('focus', imagens['acento_foco']), border=(12, 12, 12, 12), padding=0, width=40, height=36,
                              sticky='nsew')
        for selecionado in (False, True):
            imagens['recebido' + str(selecionado)] = tk.PhotoImage(master=raiz, data=_png_recebido(c, selecionado))
        estilo.element_create(prefixo + 'recebido', 'image', imagens['recebidoFalse'],
                              ('selected', imagens['recebidoTrue']), sticky='')
        cache[chave] = (prefixo, imagens)
    prefixo, _imagens = cache[chave]
    for nome, elemento in (('TButton', 'secundario'), ('Salvar.TButton', 'primario'),
                          ('Principal.TButton', 'primario'), ('DiaSelecionado.TButton', 'primario'),
                          ('Resultado.Calculadora.TButton', 'primario'), ('Menu.TButton', 'secundario'),
                          ('Lateral.TButton', 'lateral'), ('Acento.TButton', 'acento'),
                          ('Destaque.Principal.TButton', 'acento')):
        estilo.layout(nome, [(prefixo + elemento, {'sticky': 'nsew', 'children': [
            ('Button.padding', {'sticky': 'nsew', 'children': [
                ('Button.label', {'sticky': 'nsew'})]})]})])
    def sem_contorno_foco(layout):
        resultado = []
        for elemento, opcoes in layout:
            opcoes = dict(opcoes)
            if 'children' in opcoes:
                opcoes['children'] = sem_contorno_foco(opcoes['children'])
            if elemento.endswith('.focus'):
                resultado.extend(opcoes.get('children', []))
            else:
                resultado.append((elemento, opcoes))
        return resultado
    for nome in ('TRadiobutton', 'TCheckbutton'):
        estilo.layout(nome, sem_contorno_foco(estilo.layout(nome)))
    for nome in ('Recebido.TCheckbutton', 'Operacoes.TCheckbutton'):
        estilo.layout(nome, [('Checkbutton.padding', {'sticky': 'nswe', 'children': [
            (prefixo + 'recebido', {'side': 'left', 'sticky': ''}),
            ('Checkbutton.label', {'side': 'left', 'sticky': 'nswe'})]})])
    for nome in ('Filtro.TRadiobutton', 'FiltroAlerta.TRadiobutton'):
        estilo.layout(nome, [(prefixo + 'filtro', {'sticky': 'nsew', 'children': [
            ('Radiobutton.padding', {'sticky': 'nsew', 'children': [('Radiobutton.label', {'sticky': 'nsew'})]})]})])
    for nome in ('Cartao.TFrame', 'Resumo.TFrame'):
        estilo.layout(nome, [(prefixo + 'cartao', {'sticky': 'nsew', 'children': [('Frame.padding', {'sticky': 'nsew'})]})])
        estilo.configure(nome, background=c['fundo'], borderwidth=0)


class Icone(tk.Canvas):
    """Ícone de linha num ladrilho de cantos arredondados; no cartão de destaque (heroi=True), sobre o nanquim."""

    def __init__(self, pai, nome, heroi=False):
        super().__init__(pai, width=54, height=54, highlightthickness=0, bd=0)
        self.nome = nome
        self.heroi = heroi
        self.atualizar_tema()

    def atualizar_tema(self):
        c = cores()
        fundo = c['heroi'] if self.heroi else c['superficie']
        self.configure(bg=fundo)
        self.delete('all')
        ladrilho = c['heroi_ativo'] if self.heroi else c['realce']
        r = 12
        self.create_polygon(5 + r, 5, 49 - r, 5, 49, 5, 49, 5 + r, 49, 49 - r, 49, 49, 49 - r, 49, 5 + r, 49, 5, 49,
                            5, 49 - r, 5, 5 + r, 5, 5, fill=ladrilho, outline='', smooth=True)
        linha = dict(fill=c['acento'] if self.heroi else c['marca'], width=1.8, capstyle='round', joinstyle='round')
        if self.nome == 'entrada':
            self.create_line(17, 14, 32, 14, 38, 20, 38, 40, 17, 40, 17, 14, **linha)
            self.create_line(31, 14, 31, 21, 38, 21, **linha)
            self.create_line(23, 29, 32, 29, **linha)
            self.create_line(27.5, 24.5, 27.5, 33.5, **linha)
        elif self.nome == 'historico':
            self.create_line(16, 40, 16, 33, 22, 33, 22, 40, **linha)
            self.create_line(25, 40, 25, 26, 31, 26, 31, 40, **linha)
            self.create_line(34, 40, 34, 18, 40, 18, 40, 40, **linha)
            self.create_line(15, 27, 24, 19, 30, 21, 39, 12, **linha)
        else:
            self.create_line(14, 22, 27, 13, 40, 22, 14, 22, **linha)
            for x in (18, 27, 36): self.create_line(x, 27, x, 37, **linha)
            self.create_line(14, 41, 40, 41, **linha)
