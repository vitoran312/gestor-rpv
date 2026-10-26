"""Arte de placas de vidro atrás do cartão Nova entrada, com animação de abertura única.

As placas são imagens PNG com transparência (recursos/vidro-claro.png e vidro-escuro.png, geradas por
scripts/gerar_arte_vidro.py). O Canvas do Tk sobrepõe essas imagens respeitando o canal alfa, então a
translucidez entre placas é real, sem depender de transparência da janela. O fade-in troca entre níveis
de opacidade já prontos e o deslocamento só move as imagens: pouco trabalho por quadro.
A animação dura cerca de 2,5 s, roda uma única vez ao abrir o programa e termina parada.
"""
import time
import tkinter as tk

from identidade import RECURSOS
from tema import cores, modo_atual

CELULA = (136, 164)   # Tamanho de cada placa nas folhas de imagens.
NIVEIS = 6            # Colunas de opacidade crescente nas folhas.
# Leque de placas (do fundo para a frente): deslocamento de cada uma, em pixels, dentro do conjunto.
# O conjunto fica centralizado na área livre; se ela for estreita, a sobra à direita é cortada.
POSICOES = ((10, 0), (40, 8), (0, 22), (30, 30))
INTERVALO = 0.22      # Segundos entre o início de uma placa e o da seguinte.
DURACAO = 1.25        # Segundos de entrada de cada placa.
ATRASO_BRILHO = 0.35  # A borda acende depois que o vidro já começou a aparecer.
QUADRO_MS = 33        # Cerca de 30 quadros por segundo.
DESLOCAMENTO = (46, 14)  # Pixels de onde cada placa parte, à direita e abaixo da posição final.


def suavizar(t):
    """Desaceleração suave no fim do movimento (ease-out cúbico)."""
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def duracao_total():
    return INTERVALO * (len(POSICOES) - 1) + DURACAO + ATRASO_BRILHO


def nivel(progresso):
    """Coluna de opacidade para o progresso; None enquanto a camada ainda está invisível."""
    return None if progresso <= 0 else min(NIVEIS - 1, int(progresso * NIVEIS - 1e-9))


def imagens_vidro(raiz, modo):
    """Recorta a folha do tema em imagens por placa, camada e nível; guardadas na raiz para reaproveitar."""
    cache = getattr(raiz, '_vidro_inicio', {})
    raiz._vidro_inicio = cache
    if modo not in cache:
        folha = tk.PhotoImage(master=raiz, file=str(RECURSOS / f'vidro-{modo}.png'))
        largura, altura = CELULA
        recortes = {}
        for placa in range(len(POSICOES)):
            for camada in (0, 1):  # 0: vidro e borda fina; 1: brilho desfocado.
                for coluna in range(NIVEIS):
                    imagem = tk.PhotoImage(master=raiz, width=largura, height=altura)
                    x, y = coluna * largura, (placa * 2 + camada) * altura
                    imagem.tk.call(imagem, 'copy', folha, '-from', x, y, x + largura, y + altura)
                    recortes[placa, camada, coluna] = imagem
        cache[modo] = recortes
    return cache[modo]


class ArteVidro(tk.Canvas):
    def __init__(self, pai):
        super().__init__(pai, highlightthickness=0, bd=0)
        self.inicio = None
        self.agendamento = None
        self.concluida = False
        # Do fundo para a frente; em cada placa, o brilho fica atrás do vidro.
        self.itens = [(self.create_image(0, 0, anchor='nw', state='hidden'),
                       self.create_image(0, 0, anchor='nw', state='hidden')) for _ in POSICOES]
        self.bind('<Configure>', lambda _: self.desenhar())
        self.bind('<Destroy>', self.cancelar)
        self.atualizar_tema()

    def atualizar_tema(self):
        self.configure(bg=cores()['superficie'])
        self.imagens = imagens_vidro(self._root(), modo_atual())
        self.desenhar()

    def animar(self):
        """Começa a entrada das placas; chamar de novo não repete a animação."""
        if self.inicio is not None or self.concluida:
            return
        self.inicio = time.monotonic()
        self.quadro()

    def finalizar(self):
        self.cancelar()
        self.concluida = True
        self.desenhar()

    def cancelar(self, _evento=None):
        if self.agendamento is not None:
            self.after_cancel(self.agendamento)
            self.agendamento = None

    def tempo(self):
        if self.concluida:
            return duracao_total()
        return 0.0 if self.inicio is None else time.monotonic() - self.inicio

    def quadro(self):
        self.agendamento = None
        if not self.winfo_exists():
            return
        if self.tempo() >= duracao_total():
            self.concluida = True
        self.desenhar()
        if not self.concluida:
            self.agendamento = self.after(QUADRO_MS, self.quadro)

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
                self.coords(item, round(x), round(y))
                if coluna is None:
                    self.itemconfigure(item, state='hidden')
                else:
                    self.itemconfigure(item, image=self.imagens[indice, camada, coluna], state='normal')
