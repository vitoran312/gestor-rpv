"""Movimento discreto da interface: curvas, duração e o respeito à preferência por menos animação.

As decisões seguem a skill animate (Emil Kowalski): entradas e saídas com ease-out forte, interface abaixo de
300 ms, nada animado em ações repetidas o dia todo, e menos movimento quando o sistema pede. No Tkinter, o que
dá para animar sem custo é a opacidade de janelas e a posição de elementos colocados com place().
"""
import os
import sys
import tkinter as tk

# Duração (ms) por tipo de elemento, dentro das faixas da skill: janelas 150–250 ms, avisos ~200 ms.
DURACAO_JANELA = 180
DURACAO_AVISO = 220
QUADRO_MS = 16  # ~60 quadros por segundo.


def bezier(x1, y1, x2, y2):
    """Função de tempo cubic-bezier(x1, y1, x2, y2), como no CSS: recebe o progresso (0–1) e devolve o efeito."""
    def coordenada(t, a, b):
        return 3 * a * (1 - t) ** 2 * t + 3 * b * (1 - t) * t ** 2 + t ** 3

    def curva(x):
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        inicio, fim = 0.0, 1.0
        for _ in range(30):  # Bisseção: precisão bem abaixo de um pixel ou de 1% de opacidade.
            t = (inicio + fim) / 2
            if coordenada(t, x1, x2) < x:
                inicio = t
            else:
                fim = t
        return coordenada((inicio + fim) / 2, y1, y2)
    return curva


EASE_OUT = bezier(0.23, 1, 0.32, 1)  # --ease-out da skill: forte, para entradas e saídas.


def movimento_reduzido():
    """True quando o sistema pede menos animação (Windows: "Mostrar animações" desligado) ou o ambiente desliga."""
    if os.environ.get('GESTOR_RPV_SEM_ANIMACAO') == '1':
        return True
    if sys.platform == 'win32':
        try:
            import ctypes
            ativo = ctypes.c_bool(True)
            SPI_GETCLIENTAREAANIMATION = 0x1042
            if ctypes.windll.user32.SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(ativo), 0):
                return not ativo.value
        except (AttributeError, OSError):
            pass
    return False


def animar(widget, duracao, ao_avancar, ao_terminar=None, curva=EASE_OUT):
    """Chama ao_avancar(efeito 0–1) a cada quadro durante `duracao` ms; com movimento reduzido, vai direto ao fim."""
    if movimento_reduzido() or duracao <= 0:
        ao_avancar(1.0)
        if ao_terminar:
            ao_terminar()
        return
    passos = max(1, round(duracao / QUADRO_MS))

    def quadro(n):
        if not widget.winfo_exists():
            return
        ao_avancar(curva(n / passos))
        if n < passos:
            widget.after(QUADRO_MS, quadro, n + 1)
        elif ao_terminar:
            ao_terminar()
    quadro(1)


def surgir(janela):
    """Mostra uma janela (diálogo ou formulário) esmaecendo de 0 a 100% de opacidade, em ease-out.

    Modais não saem do botão que os abriu: ficam centralizados e só a opacidade muda. Onde o sistema não
    suporta transparência de janela, ela simplesmente aparece.
    """
    try:
        janela.attributes('-alpha', 0.0 if not movimento_reduzido() else 1.0)
    except tk.TclError:
        janela.deiconify()
        return
    janela.deiconify()

    def opacidade(efeito):
        try:
            janela.attributes('-alpha', efeito)
        except tk.TclError:
            pass
    animar(janela, DURACAO_JANELA, opacidade)
