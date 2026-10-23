"""Gráfico mensal de capital investido e valores recebidos, desenhado em Canvas."""
import tkinter as tk
from datetime import date
from tkinter import ttk

from componentes import centralizar
from dados import moeda
from tema import cores
from visual import familia_fonte

MESES = ('jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez')


def resumo_mensal(registros, meses=12, hoje=None):
    """Últimos meses até o atual: investido pela data de aquisição, recebido pela data do recebimento."""
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
            totais[registro['aquisicao'][:7]][0] += registro['custo']
        if registro['recebimento'] and registro['recebimento'][:7] in totais:
            totais[registro['recebimento'][:7]][1] += registro['previsto']
    return [(chave, investido, recebido) for chave, (investido, recebido) in totais.items()]


def rotulo_mes(chave):
    return f'{MESES[int(chave[5:7]) - 1]}/{chave[2:4]}'


def valor_curto(centavos):
    reais = centavos / 100
    if reais >= 1_000_000:
        return f'R$ {reais / 1_000_000:.1f} mi'.replace('.', ',')
    if reais >= 1000:
        milhares = reais / 1000
        return f'R$ {milhares:.0f} mil' if milhares == int(milhares) else f'R$ {milhares:.1f} mil'.replace('.', ',')
    return f'R$ {reais:.0f}'


def escala(maximo):
    """Topo do eixo divisível em quatro passos redondos (1, 2, 4, 6 ou 8 × 10ⁿ) que cabe o maior valor."""
    if maximo <= 100000:
        return 100000  # Eixo mínimo de R$ 1 mil, para valores pequenos não gerarem rótulos sem sentido.
    potencia = 1
    while potencia * 10 <= maximo:
        potencia *= 10
    for fator in (1, 2, 4, 6, 8, 10):
        if fator * potencia >= maximo:
            return int(fator * potencia)


class GraficoMensal(tk.Canvas):
    def __init__(self, pai, dados):
        super().__init__(pai, highlightthickness=0, bd=0, height=360)
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

    def desenhar(self):
        c = cores()
        self.delete('all')
        self.barras = []
        largura, altura = max(self.winfo_width(), 600), max(self.winfo_height(), 300)
        esquerda, direita, topo, base = 84, 20, 20, 36
        topo_eixo = escala(max([max(i, r) for _, i, r in self.dados] + [0]))
        area = altura - topo - base
        for passo in range(5):
            y = topo + area * passo / 4
            self.create_line(esquerda, y, largura - direita, y, fill=c['borda_suave'])
            self.create_text(esquerda - 12, y, text=valor_curto(topo_eixo * (4 - passo) / 4), anchor='e',
                             fill=c['secundario'], font=(self.fonte, 9))
        grupo = (largura - esquerda - direita) / len(self.dados)
        barra = min(22, grupo * 0.3)
        for indice, (chave, investido, recebido) in enumerate(self.dados):
            centro = esquerda + grupo * (indice + 0.5)
            for deslocamento, valor, cor in ((-barra / 2 - 2, investido, c['floresta']), (barra / 2 + 2, recebido, c['verde'])):
                if valor:
                    y = topo + area * (1 - valor / topo_eixo)
                    self.create_rectangle(centro + deslocamento - barra / 2, y, centro + deslocamento + barra / 2,
                                          topo + area, fill=cor, outline='')
            self.create_text(centro, altura - base + 16, text=rotulo_mes(chave), fill=c['secundario'], font=(self.fonte, 9))
            self.barras.append((centro - grupo / 2, centro + grupo / 2, chave, investido, recebido))

    def destacar(self, evento):
        self.delete('destaque')
        if evento is None:
            self.mes_destacado = None
            self.event_generate('<<MesDestacado>>')
            return
        for inicio, fim, chave, investido, recebido in self.barras:
            if inicio <= evento.x < fim:
                c = cores()
                self.create_rectangle(inicio + 2, 12, fim - 2, self.winfo_height() - 32, fill='', outline=c['borda'],
                                      tags='destaque')
                self.mes_destacado = (chave, investido, recebido)
                self.event_generate('<<MesDestacado>>')
                return


class JanelaGrafico:
    def __init__(self, aplicativo):
        self.app = aplicativo
        registros = aplicativo.banco.listar()
        self.dados = resumo_mensal(registros)
        pai = aplicativo.historico if aplicativo.historico is not None and aplicativo.historico.winfo_exists() else aplicativo.janela
        self.tela = tk.Toplevel(pai)
        self.tela.withdraw()
        self.tela.title('Gráfico mensal')
        self.tela.configure(bg=cores()['fundo'])
        self.tela.minsize(760, 520)
        corpo = ttk.Frame(self.tela, padding=24)
        corpo.pack(fill='both', expand=True)
        ttk.Label(corpo, text='Gráfico mensal', style='Titulo.TLabel').pack(anchor='w')
        investido = sum(i for _, i, _r in self.dados)
        recebido = sum(r for _, _i, r in self.dados)
        ttk.Label(corpo, style='Subtitulo.TLabel',
                  text=f'Últimos 12 meses: R$ {moeda(investido)} investidos e R$ {moeda(recebido)} recebidos.'
                  ).pack(anchor='w', pady=(4, 16))
        legenda = ttk.Frame(corpo)
        legenda.pack(anchor='w', pady=(0, 8))
        for texto, estilo in (('Capital investido (data de aquisição)', 'LegendaInvestido.TLabel'),
                              ('Valor recebido (data do recebimento)', 'LegendaRecebido.TLabel')):
            ttk.Label(legenda, text='■', style=estilo).pack(side='left', padx=(0, 6))
            ttk.Label(legenda, text=texto).pack(side='left', padx=(0, 20))
        cartao = ttk.Frame(corpo, style='Cartao.TFrame', padding=16)
        cartao.pack(fill='both', expand=True)
        self.grafico = GraficoMensal(cartao, self.dados)
        self.grafico.pack(fill='both', expand=True)
        self.detalhe = tk.StringVar(value='Passe o mouse sobre um mês para ver os valores.')
        ttk.Label(corpo, textvariable=self.detalhe, style='Discreto.TLabel').pack(anchor='w', pady=(10, 0))
        self.grafico.bind('<<MesDestacado>>', self.mostrar_detalhe)
        self.tela.bind('<Escape>', lambda _: self.tela.destroy())
        centralizar(self.tela, 960, 620)
        self.tela.deiconify()

    def mostrar_detalhe(self, _evento=None):
        destaque = self.grafico.mes_destacado
        if destaque is None:
            self.detalhe.set('Passe o mouse sobre um mês para ver os valores.')
            return
        chave, investido, recebido = destaque
        self.detalhe.set(f'{rotulo_mes(chave)}: R$ {moeda(investido)} investidos · R$ {moeda(recebido)} recebidos')
