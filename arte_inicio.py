"""Arte animada da tela inicial: placas de vidro no cartão Nova entrada e luzes suaves no fundo.

As placas e as luzes são imagens PNG com transparência (recursos/vidro-*.png e luz-*.png, geradas por
scripts/gerar_arte_vidro.py). O Canvas do Tk sobrepõe essas imagens respeitando o canal alfa, então a
translucidez é real, sem depender de transparência da janela.

Ao abrir, as placas entram em sequência (cerca de 4 s) e depois ficam paradas. As luzes de fundo são fixas.
O relógio da entrada fica em pausa quando a tela inicial não está visível e para de vez quando a entrada
termina; trocar de tema só troca as imagens, sem reiniciar a animação.
"""
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
LUZ = 520             # Lado de cada mancha de luz.
# Luzes de fundo: centro de cada mancha, em frações da tela.
LUZES = ((0.16, 0.10), (0.82, 0.94))
QUADRO_MS = 40        # Um quadro a cada 40 ms durante a entrada.
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


class ArteVidro(tk.Canvas):
    """Placas de vidro em leque: entrada em sequência e, depois, paradas na posição final."""

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

    def animar(self):
        """Começa a entrada das placas; chamar de novo não reinicia."""
        if self.inicio is None:
            self.inicio = time.monotonic()

    def tempo(self):
        return 0.0 if self.inicio is None else time.monotonic() - self.inicio

    def terminou(self):
        return self.inicio is not None and self.tempo() >= duracao_total()

    def desenhar(self):
        largura, altura = self.winfo_width(), self.winfo_height()
        if largura < 20 or altura < 20:
            return
        agora = self.tempo()
        conjunto = (CELULA[0] + max(x for x, _ in POSICOES), CELULA[1] + max(y for _, y in POSICOES))
        base_x = max(0, (largura - conjunto[0]) // 2)
        base_y = (altura - conjunto[1]) // 2
        for indice, ((fx, fy), (brilho, vidro)) in enumerate(zip(POSICOES, self.itens)):
            entrada = suavizar((agora - indice * INTERVALO) / DURACAO)
            acender = suavizar((agora - indice * INTERVALO - ATRASO_BRILHO) / DURACAO)
            # Placas do fundo se deslocam menos, reforçando a sensação de profundidade.
            profundidade = 0.55 + 0.45 * indice / (len(POSICOES) - 1)
            x = base_x + fx + DESLOCAMENTO[0] * profundidade * (1 - entrada)
            y = base_y + fy + DESLOCAMENTO[1] * profundidade * (1 - entrada)
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
    """Manchas de luz translúcidas e fixas no Canvas da tela inicial, abaixo de todo o resto."""

    def __init__(self, canvas):
        self.canvas = canvas
        self.itens = [canvas.create_image(0, 0, anchor='center', tags='luz') for _ in LUZES]
        canvas.tag_lower('luz')
        self.area = None
        self.atualizar_tema()

    def atualizar_tema(self):
        imagens = imagens_luz(self.canvas._root(), modo_atual())
        for item, imagem in zip(self.itens, imagens):
            self.canvas.itemconfigure(item, image=imagem)
        self.desenhar()

    def desenhar(self, area=None):
        """Posiciona as luzes na área (x, y, largura, altura) da composição; sem área, no Canvas inteiro."""
        self.area = area or self.area or (0, 0, self.canvas.winfo_width(), self.canvas.winfo_height())
        x, y, largura, altura = self.area
        for item, (fx, fy) in zip(self.itens, LUZES):
            self.canvas.coords(item, round(x + fx * largura), round(y + fy * altura))


class Relogio:
    """Laço da animação de entrada: em pausa fora da tela inicial e encerrado quando tudo termina."""

    def __init__(self, canvas, *animados):
        self.canvas = canvas
        self.animados = animados
        self.agendamento = None
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
            for animado in self.animados:
                animado.desenhar()
            # Depois do último quadro, tudo fica parado: o laço não volta a rodar.
            if all(getattr(animado, 'terminou', lambda: False)() for animado in self.animados):
                return
        self.agendamento = self.canvas.after(QUADRO_MS if visivel else PAUSA_MS, self.quadro)
