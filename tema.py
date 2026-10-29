"""Paletas compartilhadas por todas as janelas."""
import tkinter as tk
from tkinter import ttk

# Ledger: identidade de banco privado. Porcelana quente e tinta azul-nanquim no claro; nanquim profundo e
# marfim no escuro. O acento champanhe marca foco, seleção e o item ativo; o vinho fica só no emblema.
# Barra lateral e cartão de destaque usam a superfície "herói" (nanquim) nos dois temas.
# Texto sobre fundo atende ao contraste WCAG AA (4,5:1); o champanhe sobre branco (marca) é usado em
# contornos, ícones e textos grandes ou em negrito.
PALETAS = {
    'claro': dict(fundo='#f4f2ec', campo='#ffffff', superficie='#ffffff', texto='#12161f',
                  secundario='#5f6571', botao='#ffffff', borda='#d6d0c3', borda_suave='#e7e2d8',
                  ativo='#f1ede4', selecao='#efe4cc', texto_selecao='#12161f', verde='#1c6f4c',
                  vermelho='#ad2e42', desabilitado='#8c919b', primario='#172030', primario_texto='#f7f2e7',
                  primario_ativo='#26314a', primario_pressionado='#0c121c', marca='#8a6a2e',
                  cabecalho='#f8f6f1', realce='#f6efe0', linha='#faf9f5', atraso='#fbeced',
                  recebida='#e8f3ec', hover_linha='#f3efe6', notificacao='#172030', notificacao_texto='#f7f2e7',
                  notificacao_sucesso='#7fd6ac', notificacao_erro='#ff9aa6',
                  heroi='#141b28', heroi_texto='#f5efe2', heroi_secundario='#aab1bf', heroi_borda='#2a3346',
                  heroi_hover='#1e2738', heroi_ativo='#263048', acento='#d8b878', acento_texto='#141b28',
                  acento_hover='#e4c88f', acento_pressionado='#c7a463', sombra='#2b2416'),
    'escuro': dict(fundo='#0b0e14', campo='#0f141c', superficie='#121722', texto='#ece6d8',
                   secundario='#9aa1ae', botao='#161c28', borda='#2b3242', borda_suave='#1d2331',
                   ativo='#1b2232', selecao='#3a3120', texto_selecao='#fff6e2', verde='#6fd2a3',
                   vermelho='#ff8e9b', desabilitado='#687181', primario='#d8b878', primario_texto='#141b28',
                   primario_ativo='#e4c88f', primario_pressionado='#c7a463', marca='#d8b878',
                   cabecalho='#151b27', realce='#272013', linha='#10151e', atraso='#2a1419',
                   recebida='#0f2419', hover_linha='#1a2030', notificacao='#ece6d8', notificacao_texto='#141b28',
                   notificacao_sucesso='#1c6f4c', notificacao_erro='#ad2e42',
                   heroi='#121825', heroi_texto='#f5efe2', heroi_secundario='#a2a9b6', heroi_borda='#2c3446',
                   heroi_hover='#1a2233', heroi_ativo='#222b3e', acento='#d8b878', acento_texto='#141b28',
                   acento_hover='#e4c88f', acento_pressionado='#c7a463', sombra='#000000'),
}
_modo = 'claro'

# Escala de espaçamento (pixels a 100% de escala; use visual.px para converter) e de tipografia (pontos).
# Tudo o que é novo usa estes passos, para as telas manterem o mesmo ritmo.
ESPACO = {'xs': 4, 'sm': 8, 'md': 12, 'lg': 16, 'xl': 24, 'xxl': 32}
TIPO = {'legenda': 9, 'corpo': 10, 'destaque': 11, 'enfase': 12, 'subtitulo': 13, 'titulo': 22, 'display': 34}


def definir_modo(modo):
    global _modo
    if modo not in PALETAS:
        raise ValueError('Tema inválido.')
    _modo = modo


def cores():
    return PALETAS[_modo]


def modo_atual():
    return _modo


def atualizar_widgets(widget):
    c = cores()
    if isinstance(widget, (tk.Tk, tk.Toplevel)):
        widget.configure(bg=c['fundo'])
    elif callable(getattr(widget, 'atualizar_tema', None)):
        widget.atualizar_tema()
    elif isinstance(widget, tk.Text):
        widget.configure(bg=c['campo'], fg=c['texto'], insertbackground=c['texto'],
                         selectbackground=c['selecao'], selectforeground=c['texto_selecao'],
                         highlightthickness=1, highlightbackground=c['borda'], highlightcolor=c['marca'])
    elif isinstance(widget, tk.Menu):
        widget.configure(bg=c['campo'], fg=c['texto'], activebackground=c['selecao'],
                         activeforeground=c['texto_selecao'], disabledforeground=c['desabilitado'])
    elif isinstance(widget, ttk.Combobox):
        popup = str(widget) + '.popdown'
        lista = str(popup) + '.f.l'
        if widget.tk.call('winfo', 'exists', lista):
            widget.tk.call(lista, 'configure', '-background', c['campo'], '-foreground', c['texto'],
                           '-selectbackground', c['selecao'], '-selectforeground', c['texto_selecao'])
    # children evita assumir que widgets internos criados pelo Tcl são objetos Python.
    for filho in list(widget.children.values()):
        atualizar_widgets(filho)
