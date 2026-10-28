"""Gráfico mensal de entradas e recebimentos, com barras em 3D desenhadas em Canvas."""
import tkinter as tk
from datetime import date
from tkinter import ttk

from tema import cores
from visual import familia_fonte, misturar, px

MESES = ('jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez')
LARGURA_MAXIMA = 1000  # O gráfico não estica além disso, mesmo com a janela maximizada.
ALTURA = 340
FAIXAS = 6             # Faixas verticais da face frontal, que simulam o brilho de uma superfície curva.


def resumo_mensal(registros, meses=12, hoje=None):
    """Últimos meses até o atual: entradas pela data de aquisição, recebidas pela data do recebimento."""
    hoje = hoje or date.today()
    chaves = []
    ano, mes = hoje.year, hoje.month
    for _ in range(meses):
        chaves.append(f'{ano:04d}-{mes:02d}')
        ano, mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    chaves.reverse()
    totais = {chave: [0, 0] for chave in chaves}
    for registro in registros:
        if registro['aquisicao'][:7] in totais:
            totais[registro['aquisicao'][:7]][0] += 1
        if registro['recebimento'] and registro['recebimento'][:7] in totais:
            totais[registro['recebimento'][:7]][1] += 1
    return [(chave, entradas, recebidas) for chave, (entradas, recebidas) in totais.items()]


def rotulo_mes(chave):
    return f'{MESES[int(chave[5:7]) - 1]}/{chave[2:4]}'


def quantidade(total, singular, plural):
    return f'{total} {singular if total == 1 else plural}'


def escala(maximo):
    """Topo do eixo em quatro passos inteiros e redondos (1, 2 ou 5 × 10ⁿ) que cabe o maior valor."""
    potencia = 1
    while True:
        for fator in (1, 2, 5):
            if fator * potencia * 4 >= maximo:
                return fator * potencia * 4
        potencia *= 10


class GraficoMensal(tk.Canvas):
    def __init__(self, pai, dados):
        super().__init__(pai, highlightthickness=0, bd=0, width=px(pai, LARGURA_MAXIMA), height=px(pai, ALTURA))
        self.dados = dados
        self.fonte = familia_fonte(self)
        self.barras = []
        self.mes_destacado = None
        self.bind('<Configure>', lambda _: self.desenhar())
        self.bind('<Motion>', self.destacar)
        self.bind('<Leave>', lambda _: self.destacar(None))
        self.atualizar_tema()

    def atualizar_tema(self):
        self.configure(bg=cores()['superficie'])
        self.desenhar()

    def cores_barras(self):
        """Recebidas na cor positiva (verde); entradas em tom neutro, para não competir com elas."""
        c = cores()
        return {'entradas': misturar(c['secundario'], c['superficie'], 0.25), 'recebidas': c['verde']}

    def barra_3d(self, x0, x1, y, base, profundidade, cor):
        """Prisma: face frontal com brilho em faixas, topo mais claro e lateral mais escura."""
        dx, dy = profundidade, profundidade * 0.6
        self.create_polygon(x1, y, x1 + dx, y - dy, x1 + dx, base - dy, x1, base,
                            fill=misturar(cor, '#000000', 0.38), outline='')
        largura = (x1 - x0) / FAIXAS
        for faixa in range(FAIXAS):
            # Mais claro perto da borda esquerda, escurecendo para a direita, como luz lateral.
            luz = 0.28 * (1 - faixa / (FAIXAS - 1)) - 0.12 * faixa / (FAIXAS - 1)
            tom = misturar(cor, '#ffffff', luz) if luz >= 0 else misturar(cor, '#000000', -luz)
            self.create_rectangle(x0 + faixa * largura, y, x0 + (faixa + 1) * largura + 0.5, base, fill=tom, outline='')
        self.create_polygon(x0, y, x0 + dx, y - dy, x1 + dx, y - dy, x1, y,
                            fill=misturar(cor, '#ffffff', 0.42), outline='')
        self.create_line(x0, y, x1, y, fill=misturar(cor, '#ffffff', 0.6))

    def desenhar(self):
        c = cores()
        self.delete('all')
        self.barras = []
        p = lambda v: px(self, v)
        largura, altura = max(self.winfo_width(), p(500)), max(self.winfo_height(), p(240))
        esquerda, direita, topo, base = p(44), p(24), p(34), p(34)
        topo_eixo = escala(max([max(e, r) for _, e, r in self.dados] + [0]))
        area = altura - topo - base
        grupo = (largura - esquerda - direita) / len(self.dados)
        barra = min(p(40), grupo * 0.36)
        profundidade = barra * 0.4
        dx, dy = profundidade * 2, profundidade * 1.2  # Fundo do "palco" das barras.
        piso = topo + area
        # Parede do fundo e piso em perspectiva, com a grade em linhas finas.
        self.create_polygon(esquerda, piso, esquerda + dx, piso - dy, largura - direita + dx * 0.4, piso - dy,
                            largura - direita - dx * 0.6, piso, fill=misturar(c['superficie'], c['sage'], 0.9), outline='')
        for passo in range(5):
            y = topo + area * passo / 4
            cor = c['borda'] if passo == 4 else c['borda_suave']
            self.create_line(esquerda + dx, y - dy, largura - direita + dx * 0.4, y - dy, fill=cor,
                             dash=() if passo == 4 else (2, 4))
            self.create_line(esquerda, y, esquerda + dx, y - dy, fill=c['borda_suave'])
            self.create_text(esquerda - p(10), y, text=str(topo_eixo * (4 - passo) // 4), anchor='e',
                             fill=c['secundario'], font=(self.fonte, 9))
        self.create_line(esquerda, topo, esquerda, piso, largura - direita - dx * 0.6, piso, fill=c['borda'])
        tons = self.cores_barras()
        for indice, (chave, entradas, recebidas) in enumerate(self.dados):
            centro = esquerda + grupo * (indice + 0.5)
            for deslocamento, valor, cor in ((-barra / 2 - p(3), entradas, tons['entradas']),
                                             (barra / 2 + p(3), recebidas, tons['recebidas'])):
                if valor:
                    x0 = centro + deslocamento - barra / 2
                    y = piso - area * valor / topo_eixo
                    self.barra_3d(x0, x0 + barra, y, piso, profundidade, cor)
                    self.create_text(x0 + barra / 2 + profundidade / 2, y - profundidade * 0.6 - p(9), text=str(valor),
                                     fill=c['texto'] if cor == tons['recebidas'] else c['secundario'],
                                     font=(self.fonte, 9, 'bold'))
            self.create_text(centro, altura - base + p(18), text=rotulo_mes(chave), fill=c['secundario'],
                             font=(self.fonte, 9))
            self.barras.append((centro - grupo / 2, centro + grupo / 2, chave, entradas, recebidas))

    def destacar(self, evento):
        self.delete('destaque')
        if evento is None:
            self.mes_destacado = None
            self.event_generate('<<MesDestacado>>')
            return
        for inicio, fim, chave, entradas, recebidas in self.barras:
            if inicio <= evento.x < fim:
                c = cores()
                self.create_rectangle(inicio + 2, px(self, 8), fim - 2, self.winfo_height() - px(self, 30), fill='',
                                      outline=c['borda'], dash=(3, 3), tags='destaque')
                self.mes_destacado = (chave, entradas, recebidas)
                self.event_generate('<<MesDestacado>>')
                return


class JanelaGrafico:
    def __init__(self, aplicativo):
        self.app = aplicativo
        registros = aplicativo.banco.listar()
        self.dados = resumo_mensal(registros)
        self.tela = ttk.Frame(aplicativo.janela)
        corpo = ttk.Frame(self.tela, padding=(24, 16, 24, 24))
        corpo.pack(fill='both', expand=True)
        # Toda a página (cabeçalho, legenda, gráfico e detalhe) fica numa coluna centralizada na janela.
        coluna = ttk.Frame(corpo)
        coluna.pack(expand=True)
        entradas = sum(e for _, e, _r in self.dados)
        recebidas = sum(r for _, _e, r in self.dados)
        aplicativo.cabecalho_pagina(coluna, 'Gráfico mensal',
                                    f'Últimos 12 meses: {quantidade(entradas, "entrada", "entradas")} e '
                                    f'{quantidade(recebidas, "recebida", "recebidas")}.')
        legenda = ttk.Frame(coluna)
        legenda.pack(anchor='w', pady=(0, 8))
        for texto, estilo in (('Entradas (data de aquisição)', 'LegendaInvestido.TLabel'),
                              ('Recebidas (data do recebimento)', 'LegendaRecebido.TLabel')):
            ttk.Label(legenda, text='■', style=estilo).pack(side='left', padx=(0, 6))
            ttk.Label(legenda, text=texto).pack(side='left', padx=(0, 20))
        cartao = ttk.Frame(coluna, style='Cartao.TFrame', padding=16)
        cartao.pack(anchor='w')
        self.grafico = GraficoMensal(cartao, self.dados)
        self.grafico.pack()
        # Em janelas estreitas, o gráfico encolhe para caber; nas largas, fica no tamanho máximo.
        corpo.bind('<Configure>', lambda e: self.grafico.configure(
            width=max(px(corpo, 500), min(px(corpo, LARGURA_MAXIMA), e.width - px(corpo, 80)))), add='+')
        self.detalhe = tk.StringVar(value='Passe o mouse sobre um mês para ver os valores.')
        ttk.Label(coluna, textvariable=self.detalhe, style='Discreto.TLabel').pack(anchor='w', pady=(10, 0))
        self.grafico.bind('<<MesDestacado>>', self.mostrar_detalhe)
        aplicativo.abrir_pagina(self.tela, 'Gráfico mensal')

    def mostrar_detalhe(self, _evento=None):
        destaque = self.grafico.mes_destacado
        if destaque is None:
            self.detalhe.set('Passe o mouse sobre um mês para ver os valores.')
            return
        chave, entradas, recebidas = destaque
        self.detalhe.set(f'{rotulo_mes(chave)}: {quantidade(entradas, "entrada", "entradas")} · '
                         f'{quantidade(recebidas, "recebida", "recebidas")}')
