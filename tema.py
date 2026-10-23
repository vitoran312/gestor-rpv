"""Paletas compartilhadas por todas as janelas."""
import tkinter as tk
from tkinter import ttk

PALETAS = {
    'claro': dict(fundo='#e1d4c2', campo='#faf5ed', superficie='#f0e6d9', texto='#291c0e',
                  secundario='#695447', botao='#e9ddce', borda='#a78d78', ativo='#d6c2ae',
                  selecao='#d2b8a2', texto_selecao='#291c0e', verde='#305d3c', vermelho='#993c30',
                  desabilitado='#7a6a5b', primario='#6e473b', primario_texto='#fff8ef', primario_ativo='#59372d',
                  primario_pressionado='#41281f', floresta='#6e473b', sage='#beb5a9', linha='#f0e8dc'),
    'escuro': dict(fundo='#21180f', campo='#291c0e', superficie='#33251b', texto='#f2e6d6',
                   secundario='#c7b6a4', botao='#463227', borda='#806653', ativo='#533c2f',
                   selecao='#654a3b', texto_selecao='#fff5e7', verde='#acd1a5', vermelho='#f3aaa0',
                   desabilitado='#ae9985', primario='#c6a68c', primario_texto='#291c0e', primario_ativo='#dfc3a8',
                   primario_pressionado='#a78d78', floresta='#dfc3a8', sage='#4a3729', linha='#302217'),
}
_modo = 'claro'


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
    elif callable(getattr(widget,'atualizar_tema',None)):
        widget.atualizar_tema()
    elif isinstance(widget, tk.Text):
        widget.configure(bg=c['campo'], fg=c['texto'], insertbackground=c['texto'],
                         selectbackground=c['selecao'], selectforeground=c['texto_selecao'])
    elif isinstance(widget, tk.Menu):
        widget.configure(bg=c['campo'], fg=c['texto'], activebackground=c['selecao'],
                         activeforeground=c['texto_selecao'], disabledforeground=c['desabilitado'])
    elif isinstance(widget, ttk.Combobox):
        popup = str(widget)+'.popdown'
        lista = str(popup) + '.f.l'
        if widget.tk.call('winfo', 'exists', lista):
            widget.tk.call(lista, 'configure', '-background', c['campo'], '-foreground', c['texto'],
                           '-selectbackground', c['selecao'], '-selectforeground', c['texto_selecao'])
    # children evita assumir que widgets internos criados pelo Tcl são objetos Python.
    for filho in list(widget.children.values()):
        atualizar_widgets(filho)
