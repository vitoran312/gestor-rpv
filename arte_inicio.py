"""Arte animada da tela inicial: placas de vidro no cartão Nova entrada e luzes suaves no fundo.

As placas e as luzes são imagens PNG com transparência (recursos/vidro-*.png e luz-*.png, geradas por
scripts/gerar_arte_vidro.py). O Canvas do Tk sobrepõe essas imagens respeitando o canal alfa, então a
translucidez é real, sem depender de transparência da janela.

Ao abrir, as placas entram em sequência (cerca de 4 s); depois flutuam devagar, poucos pixels, sem parar.
As luzes de fundo derivam em ciclos longos. Um único relógio move tudo e fica em pausa quando a tela
inicial não está visível; trocar de tema só troca as imagens, sem reiniciar o movimento.
"""
import math
import time
import tkinter as tk

from identidade import RECURSOS
from tema import cores, modo_atual

CELULA = (230, 280)   # Tamanho de cada placa nas folhas de imagens.
NIVEIS = 6            # Colunas de opacidade crescente nas folhas.
# Leque de placas (do fundo para a frente): deslocamento de cada uma, em pixels, dentro do conjunto.
POSICOES = ((18, 0), (70, 14), (0, 38), (52, 54))
INTERVALO = 0.38      # Segundos entre o início de uma placa e o da seguinte.
DURACAO = 2.1         # Segundos de entrada de cada placa.
ATRASO_BRILHO = 0.5   # A borda acende depois que o vidro já começou a aparecer.
DESLOCAMENTO = (60, 18)  # Pixels de onde cada placa parte, à direita e abaixo da posição final.
# Flutuação depois da entrada: amplitude (x, y) em pixels e período (x, y) em segundos, por placa.
FLUTUACAO = (((3, 4), (9.0, 11.0)), ((4, 3), (10.5, 8.0)), ((3, 5), (8.5, 12.5)), ((5, 4), (11.5, 9.5)))
LUZ = 520             # Lado de cada mancha de luz.
# Luzes de fundo: centro em frações da tela, amplitude da deriva em pixels e período em segundos.
LUZES = (((0.16, 0.10), (50, 30), (37.0, 29.0)), ((0.82, 0.94), (60, 34), (43.0, 33.0)))
# Ritmo de cada animação, em milissegundos: a entrada das placas é fluida; a flutuação e a deriva das luzes,
# lentíssimas, avançam menos de 1 px por quadro e não precisam de mais quadros. Luzes grandes custam caro
# para redesenhar, então só mudam de lugar 5 vezes por segundo.
QUADRO_ENTRADA_MS = 40
QUADRO_FLUTUACAO_MS = 80
QUADRO_LUZES_MS = 200
QUADRO_MS = 40        # Batida do relógio: cada animação decide se é a sua vez.
PAUSA_MS = 400        # Fora da tela inicial, só confere de vez em quando se ela voltou.


def suavizar(t):
    """Desaceleração suave no fim do movimento (ease-out cúbico)."""
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def duracao_total():
    return INTERVALO * (len(POSICOES) - 1) + DURACAO + ATRASO_BRILHO


def nivel(progresso):
    """Coluna de opacidade para o progresso; None enquanto a camada ainda está invisível."""
    return None if progresso <= 0 else min(NIVEIS - 1, int(progresso * NIVEIS - 1e-9))


def _recortar(raiz, folha, largura, altura, coluna, linha):
    imagem = tk.PhotoImage(master=raiz, width=largura, height=altura)
    x, y = coluna * largura, linha * altura
    imagem.tk.call(imagem, 'copy', folha, '-from', x, y, x + largura, y + altura)
    return imagem


def imagens_vidro(raiz, modo):
    """Recorta a folha do tema em imagens por placa, camada e nível; guardadas na raiz para reaproveitar."""
    cache = getattr(raiz, '_vidro_inicio', {})
    raiz._vidro_inicio = cache
    if modo not in cache:
        folha = tk.PhotoImage(master=raiz, file=str(RECURSOS / f'vidro-{modo}.png'))
        cache[modo] = {(placa, camada, coluna): _recortar(raiz, folha, *CELULA, coluna, placa * 2 + camada)
                       for placa in range(len(POSICOES)) for camada in (0, 1) for coluna in range(NIVEIS)}
    return cache[modo]


def imagens_luz(raiz, modo):
    cache = getattr(raiz, '_luz_inicio', {})
    raiz._luz_inicio = cache
    if modo not in cache:
        folha = tk.PhotoImage(master=raiz, file=str(RECURSOS / f'luz-{modo}.png'))
        cache[modo] = [_recortar(raiz, folha, LUZ, LUZ, indice, 0) for indice in range(len(LUZES))]
    return cache[modo]


def flutuacao(indice, segundos):
    (ax, ay), (px, py) = FLUTUACAO[indice]
    return ax * math.sin(2 * math.pi * segundos / px), ay * math.sin(2 * math.pi * segundos / py + 1.3)


class ArteVidro(tk.Canvas):
    """Placas de vidro em leque: entrada em sequência e, depois, flutuação contínua e mínima."""

    def __init__(self, pai):
        super().__init__(pai, highlightthickness=0, bd=0)
        self.inicio = None
        # Do fundo para a frente; em cada placa, o brilho fica atrás do vidro.
        self.itens = [(self.create_image(0, 0, anchor='nw', state='hidden'),
                       self.create_image(0, 0, anchor='nw', state='hidden')) for _ in POSICOES]
        self.aplicado = {}  # Último estado de cada item, para não redesenhar o que não mudou.
        self.bind('<Configure>', lambda _: self.desenhar())
        self.atualizar_tema()

    def atualizar_tema(self):
        self.configure(bg=cores()['superficie'])
        self.imagens = imagens_vidro(self._root(), modo_atual())
        self.aplicado.clear()
        self.desenhar()

    def intervalo(self):
        return QUADRO_ENTRADA_MS if self.tempo() < duracao_total() else QUADRO_FLUTUACAO_MS

    def animar(self):
        """Começa a entrada das placas; chamar de novo não reinicia."""
        if self.inicio is None:
            self.inicio = time.monotonic()

    def tempo(self):
        return 0.0 if self.inicio is None else time.monotonic() - self.inicio

    def desenhar(self):
        largura, altura = self.winfo_width(), self.winfo_height()
        if largura < 20 or altura < 20:
            return
        agora = self.tempo()
        depois = max(0.0, agora - duracao_total())
        conjunto = (CELULA[0] + max(x for x, _ in POSICOES), CELULA[1] + max(y for _, y in POSICOES))
        base_x = max(0, (largura - conjunto[0]) // 2)
        base_y = (altura - conjunto[1]) // 2
        for indice, ((fx, fy), (brilho, vidro)) in enumerate(zip(POSICOES, self.itens)):
            entrada = suavizar((agora - indice * INTERVALO) / DURACAO)
            acender = suavizar((agora - indice * INTERVALO - ATRASO_BRILHO) / DURACAO)
            # Placas do fundo se deslocam menos, reforçando a sensação de profundidade.
            profundidade = 0.55 + 0.45 * indice / (len(POSICOES) - 1)
            ox, oy = flutuacao(indice, depois)
            x = base_x + fx + DESLOCAMENTO[0] * profundidade * (1 - entrada) + ox
            y = base_y + fy + DESLOCAMENTO[1] * profundidade * (1 - entrada) + oy
            for item, camada, progresso in ((vidro, 0, entrada), (brilho, 1, acender)):
                coluna = nivel(progresso)
                estado = (round(x), round(y), coluna)
                if self.aplicado.get(item) == estado:
                    continue
                self.aplicado[item] = estado
                self.coords(item, round(x), round(y))
                if coluna is None:
                    self.itemconfigure(item, state='hidden')
                else:
                    self.itemconfigure(item, image=self.imagens[indice, camada, coluna], state='normal')


class LuzesFundo:
    """Manchas de luz translúcidas no Canvas da tela inicial, abaixo de todo o resto, em deriva lenta."""

    def __init__(self, canvas):
        self.canvas = canvas
        self.inicio = time.monotonic()
        self.itens = [canvas.create_image(0, 0, anchor='center', tags='luz') for _ in LUZES]
        canvas.tag_lower('luz')
        self.aplicado = {}
        self.atualizar_tema()

    def intervalo(self):
        return QUADRO_LUZES_MS

    def atualizar_tema(self):
        imagens = imagens_luz(self.canvas._root(), modo_atual())
        for item, imagem in zip(self.itens, imagens):
            self.canvas.itemconfigure(item, image=imagem)
        self.desenhar()

    def desenhar(self):
        largura, altura = self.canvas.winfo_width(), self.canvas.winfo_height()
        segundos = time.monotonic() - self.inicio
        for item, ((fx, fy), (ax, ay), (px, py)) in zip(self.itens, LUZES):
            x = fx * largura + ax * math.sin(2 * math.pi * segundos / px)
            y = fy * altura + ay * math.sin(2 * math.pi * segundos / py + 0.7)
            posicao = (round(x), round(y))
            if self.aplicado.get(item) != posicao:
                self.aplicado[item] = posicao
                self.canvas.coords(item, *posicao)


class Relogio:
    """Um único laço de animação para a tela inicial, em pausa quando ela não está à vista."""

    def __init__(self, canvas, *animados):
        self.canvas = canvas
        self.animados = animados
        self.agendamento = None
        self.proximos = {}  # Quando cada animação deve desenhar de novo (relógio monotônico).
        canvas.bind('<Destroy>', lambda e: self.parar() if e.widget is canvas else None, add='+')

    def iniciar(self):
        if self.agendamento is None:
            self.agendamento = self.canvas.after(QUADRO_MS, self.quadro)

    def parar(self):
        if self.agendamento is not None:
            self.canvas.after_cancel(self.agendamento)
            self.agendamento = None

    def quadro(self):
        self.agendamento = None
        if not self.canvas.winfo_exists():
            return
        visivel = self.canvas.winfo_viewable() and self.canvas.winfo_toplevel().state() != 'iconic'
        if visivel:
            agora = time.monotonic()
            for animado in self.animados:
                if agora >= self.proximos.get(id(animado), 0):
                    animado.desenhar()
                    intervalo = getattr(animado, 'intervalo', lambda: QUADRO_MS)()
                    self.proximos[id(animado)] = agora + intervalo / 1000 - 0.005
        self.agendamento = self.canvas.after(QUADRO_MS if visivel else PAUSA_MS, self.quadro)
