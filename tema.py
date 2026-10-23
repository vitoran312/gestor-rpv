"""Paletas compartilhadas por todas as janelas."""
import tkinter as tk
from tkinter import ttk

PALETAS = {
    'claro': dict(fundo='#f0f2f7', campo='#ffffff', superficie='#fafbfe', texto='#191e32',
                  secundario='#525e76', botao='#e3e8f1', borda='#8b96aa', ativo='#d3dbea',
                  selecao='#ffd8c7', texto_selecao='#191e32', verde='#286040', vermelho='#b51a2b',
                  desabilitado='#737e92', primario='#b51a2b', primario_texto='#ffffff', primario_ativo='#951526',
                  primario_pressionado='#551a2b', floresta='#551a2b', sage='#ffe0d3', linha='#eef1f7'),
    'escuro': dict(fundo='#191e32', campo='#1c2339', superficie='#242f49', texto='#f3f5fa',
                   secundario='#b8c2d7', botao='#384358', borda='#6c7a95', ativo='#45516b',
                   selecao='#4b3550', texto_selecao='#fff3ee', verde='#abd5ba', vermelho='#ffa3a9',
                   desabilitado='#a0acc3', primario='#ffa586', primario_texto='#191e32', primario_ativo='#ffc0a8',
                   primario_pressionado='#df8568', floresta='#ffa586', sage='#384358', linha='#252e46'),
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
