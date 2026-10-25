"""Paletas compartilhadas por todas as janelas."""
import tkinter as tk
from tkinter import ttk

# Vitoran Pro: base neutra e um único acento de marca por tema (carmim no claro, pêssego no escuro).
PALETAS = {
    'claro': dict(fundo='#f5f6f8', campo='#ffffff', superficie='#ffffff', texto='#14171f',
                  secundario='#5c6576', botao='#ffffff', borda='#c9ced8', borda_suave='#e3e6ec',
                  ativo='#eef0f4', selecao='#f6e4e8', texto_selecao='#14171f', verde='#1d7a4c',
                  vermelho='#c02a3b', desabilitado='#8a93a3', primario='#8c1d34', primario_texto='#ffffff',
                  primario_ativo='#a3243f', primario_pressionado='#6a1527', floresta='#8c1d34',
                  sage='#f0f2f5', realce='#fbeae4', linha='#f9fafb', atraso='#fde8eb'),
    'escuro': dict(fundo='#0e1117', campo='#141820', superficie='#161a22', texto='#e9ecf1',
                   secundario='#9aa3b2', botao='#1b2029', borda='#333a47', borda_suave='#232935',
                   ativo='#232935', selecao='#3a2a27', texto_selecao='#fff4ef', verde='#5fd39d',
                   vermelho='#ff7b86', desabilitado='#6b7484', primario='#ffa586', primario_texto='#1b100c',
                   primario_ativo='#ffb79e', primario_pressionado='#e98d6f', floresta='#ffa586',
                   sage='#181d26', realce='#2b201d', linha='#12161d', atraso='#2c1519'),
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
