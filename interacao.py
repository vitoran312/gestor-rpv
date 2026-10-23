"""Menus de contexto e formatação de campos de texto."""
import re
import tkinter as tk
from tkinter import ttk


def capitalizar_inicio(texto):
    return re.sub(r'^(\s*)(\S)', lambda m: m[1] + m[2].upper(), texto, count=1)


def formatar_cpf(texto):
    digitos = re.sub(r'\D', '', texto)
    if len(digitos) > 11:
        return texto
    resultado = digitos[:3]
    if len(digitos) > 3:
        resultado += '.' + digitos[3:6]
    if len(digitos) > 6:
        resultado += '.' + digitos[6:9]
    if len(digitos) > 9:
        resultado += '-' + digitos[9:]
    return resultado


def aplicar_formato(entrada, variavel, funcao):
    def formatar(_evento=None):
        if not entrada.winfo_exists():
            return
        texto = variavel.get()
        novo = funcao(texto)
        if novo != texto:
            cursor = entrada.index('insert')
            selecionado = entrada.selection_present()
            variavel.set(novo)
            entrada.icursor(min(cursor, len(novo)))
            if selecionado:
                entrada.selection_range(0, tk.END)

    entrada.bind('<KeyRelease>', formatar, add='+')
    entrada.bind('<FocusOut>', formatar, add='+')
    entrada.bind('<<Paste>>', lambda _: entrada.after_idle(formatar), add='+')
    formatar()


def aplicar_cpf(entrada, variavel):
    def formatar(_evento=None):
        if not entrada.winfo_exists():
            return
        texto = variavel.get()
        cursor = entrada.index('insert')
        quantidade = len(re.sub(r'\D', '', texto[:cursor]))
        novo = formatar_cpf(texto)
        if novo != texto:
            selecionado = entrada.selection_present()
            variavel.set(novo)
            posicao = 0
            vistos = 0
            for posicao, char in enumerate(novo, 1):
                if char.isdigit():
                    vistos += 1
                if vistos >= quantidade:
                    break
            entrada.icursor(posicao if quantidade else 0)
            if selecionado:
                entrada.selection_range(0, tk.END)

    comando = entrada.register(lambda novo: bool(re.fullmatch(r'[0-9.\-\s]*', novo)) and len(re.sub(r'\D', '', novo)) <= 11)
    entrada.configure(validate='key', validatecommand=(comando, '%P'))
    entrada.bind('<KeyRelease>', formatar, add='+')
    entrada.bind('<FocusOut>', formatar, add='+')
    entrada.bind('<<Paste>>', lambda _: entrada.after_idle(formatar), add='+')
    formatar()


def novo_menu(pai):
    return tk.Menu(pai, tearoff=False, bg='#262a33', fg='#f2f4f8',
                   activebackground='#345777', activeforeground='white')


def mostrar_menu(menu, evento):
    anterior = evento.widget.grab_current()

    def restaurar(_evento=None):
        if anterior is not None and anterior.winfo_exists():
            anterior.after_idle(anterior.grab_set)

    menu.bind('<Unmap>', restaurar)
    menu.tk_popup(evento.x_root, evento.y_root)
    return 'break'


def copiar_texto(widget, texto):
    widget.clipboard_clear()
    widget.clipboard_append(texto)


def menu_copia(widget, obter_texto):
    def abrir(evento):
        menu = novo_menu(widget)
        menu.add_command(label='Copiar', command=lambda: copiar_texto(widget, obter_texto()))
        return mostrar_menu(menu, evento)
    widget.bind('<Button-3>', abrir)


def instalar_menu_texto(raiz):
    def abrir(evento):
        widget = evento.widget
        if not isinstance(widget, (tk.Entry, ttk.Entry, tk.Text, ttk.Spinbox, tk.Spinbox)):
            return
        estado = str(widget.cget('state'))
        editavel = estado not in ('disabled', 'readonly')
        if isinstance(widget, tk.Text):
            selecionado = bool(widget.tag_ranges('sel'))
        else:
            selecionado = widget.selection_present()
        widget.focus_set()
        menu = novo_menu(widget)
        for titulo, virtual, habilitado in (
            ('Recortar', '<<Cut>>', editavel and selecionado),
            ('Copiar', '<<Copy>>', selecionado),
            ('Colar', '<<Paste>>', editavel),
        ):
            menu.add_command(label=titulo, state='normal' if habilitado else 'disabled',
                             command=lambda ev=virtual: widget.event_generate(ev))
        menu.add_separator()

        def selecionar_tudo():
            if isinstance(widget, tk.Text):
                widget.tag_add('sel', '1.0', 'end-1c')
            else:
                widget.selection_range(0, tk.END)
        menu.add_command(label='Selecionar tudo', command=selecionar_tudo)
        return mostrar_menu(menu, evento)

    raiz.bind_all('<Button-3>', abrir, add='+')
