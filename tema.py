"""Paletas compartilhadas por todas as janelas."""
import tkinter as tk
from tkinter import ttk

PALETAS = {
    'claro': dict(fundo='#f4f1ea', campo='#fffdf8', superficie='#f8f5ef', texto='#20372c',
                  secundario='#616b61', botao='#eeebe3', borda='#d8d9ce', ativo='#dce4d4',
                  selecao='#c5d3bb', texto_selecao='#193b2a', verde='#286443', vermelho='#a33b32',
                  desabilitado='#697263', primario='#254d38', primario_ativo='#316148',
                  primario_pressionado='#193c2a', floresta='#254d38', sage='#dce4d3', linha='#f2f3eb'),
    'escuro': dict(fundo='#171f1b', campo='#222e27', superficie='#202b24', texto='#f1f1e8',
                   secundario='#b7c3b4', botao='#2b3a30', borda='#435347', ativo='#3c5141',
                   selecao='#415e49', texto_selecao='#ffffff', verde='#a5d4ac', vermelho='#f1a49a',
                   desabilitado='#a9b7a4', primario='#a9bea0', primario_ativo='#c1d0b9',
                   primario_pressionado='#91ab87', floresta='#c9dac2', sage='#354b3b', linha='#26332b'),
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
        popup = widget.tk.call('ttk::combobox::PopdownWindow', str(widget))
        lista = str(popup) + '.f.l'
        if widget.tk.call('winfo', 'exists', lista):
            widget.tk.call(lista, 'configure', '-background', c['campo'], '-foreground', c['texto'],
                           '-selectbackground', c['selecao'], '-selectforeground', c['texto_selecao'])
    # children evita assumir que widgets internos criados pelo Tcl são objetos Python.
    for filho in list(widget.children.values()):
        atualizar_widgets(filho)
