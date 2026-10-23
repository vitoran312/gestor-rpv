"""Paletas compartilhadas por todas as janelas."""
import tkinter as tk
from tkinter import ttk

PALETAS = {
    'escuro': dict(fundo='#181a1f', campo='#262a33', texto='#f2f4f8', botao='#303745',
                   borda='#414754', ativo='#3c526b', selecao='#345777', texto_selecao='#ffffff',
                   verde='#63df8a', vermelho='#ff6b6b', desabilitado='#8b929e'),
    'claro': dict(fundo='#f3f5f8', campo='#ffffff', texto='#202733', botao='#e1e7ef',
                  borda='#b7c1cf', ativo='#c8d8ea', selecao='#c7def7', texto_selecao='#172434',
                  verde='#147a38', vermelho='#b42318', desabilitado='#697586'),
}
_modo = 'escuro'


def definir_modo(modo):
    global _modo
    if modo not in PALETAS:
        raise ValueError('Tema inválido.')
    _modo = modo


def cores():
    return PALETAS[_modo]


def atualizar_widgets(widget):
    c = cores()
    if isinstance(widget, (tk.Tk, tk.Toplevel)):
        widget.configure(bg=c['fundo'])
    elif isinstance(widget, tk.Text):
        widget.configure(bg=c['campo'], fg=c['texto'], insertbackground=c['texto'],
                         selectbackground=c['selecao'], selectforeground=c['texto_selecao'])
    elif isinstance(widget, tk.Menu):
        widget.configure(bg=c['campo'], fg=c['texto'], activebackground=c['selecao'],
                         activeforeground=c['texto_selecao'], disabledforeground=c['desabilitado'])
    elif isinstance(widget, ttk.Combobox):
        popup = widget.tk.call('ttk::combobox::PopdownWindow', str(widget))
        lista = str(popup) + '.f.l'
        if widget.tk.call('winfo', 'exists', lista):
            widget.tk.call(lista, 'configure', '-background', c['campo'], '-foreground', c['texto'],
                           '-selectbackground', c['selecao'], '-selectforeground', c['texto_selecao'])
    # children evita assumir que widgets internos criados pelo Tcl são objetos Python.
    for filho in list(widget.children.values()):
        atualizar_widgets(filho)
