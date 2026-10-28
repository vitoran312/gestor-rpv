"""Base dos testes de interface: abre o aplicativo de verdade (Tkinter) com um banco de teste.

Rodam só com sessão gráfica e GESTOR_RPV_TESTE_UI=1, por exemplo:
GESTOR_RPV_TESTE_UI=1 python -m unittest test_interface_inicio -v
"""
import os
import sys
import tempfile
import tkinter as tk
from tkinter import messagebox, ttk
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from apoio_testes import banco_com_contas


def filhos(widget):
    for filho in widget.winfo_children():
        yield filho
        yield from filhos(filho)


def botao(widget, texto):
    return next(w for w in filhos(widget) if isinstance(w, ttk.Button) and w.cget('text') == texto)


def texto_resumo(programa):
    linhas = []
    for cartao, _rotulo in programa.cartoes_resumo:
        titulo, valor = cartao.winfo_children()
        linhas.append(f"{titulo.cget('text')}: {programa.janela.getvar(valor.cget('textvariable'))}")
    return '\n'.join(linhas)


@unittest.skipUnless(os.environ.get('GESTOR_RPV_TESTE_UI') == '1', 'Requer sessão gráfica e GESTOR_RPV_TESTE_UI=1')
class TesteDeInterface(unittest.TestCase):
    """Cada teste recebe um aplicativo novo; os diálogos respondem sozinhos (ver setUp)."""

    def setUp(self):
        if sys.platform == 'win32':
            # No Windows, tk_popup espera o menu ser fechado por um clique real e travaria o teste.
            # Os menus continuam sendo montados; os testes acionam as opções diretamente.
            menu_sem_espera = patch.object(tk.Menu, 'tk_popup', lambda menu, x, y, entry='': None)
            menu_sem_espera.start()
            self.addCleanup(menu_sem_espera.stop)
        # Uma caixa de diálogo de verdade travaria o teste esperando um clique: por padrão, todas respondem
        # sozinhas (confirmações com "Sim") e ficam anotadas em self.dialogos. Cada teste pode trocar a resposta.
        self.dialogos = []
        for nome, resposta in (('askyesno', True), ('showerror', None), ('showinfo', None), ('showwarning', None)):
            dialogo = patch.object(messagebox, nome, side_effect=lambda *a, n=nome, r=resposta, **k:
                                   self.dialogos.append((n, a)) or r)
            dialogo.start()
            self.addCleanup(dialogo.stop)
        self.pasta = tempfile.TemporaryDirectory()
        self.banco = banco_com_contas(Path(self.pasta.name) / 'teste.sqlite3')
        self.root = tk.Tk()
        self.erros = []
        self.root.report_callback_exception = lambda *args: self.erros.append(args)
        with patch.object(app, 'abrir_banco', return_value=self.banco):
            self.programa = app.Aplicativo(self.root)
        if sys.platform == 'win32':
            self.root.state('normal')  # Maximizada, a janela ignoraria os tamanhos pedidos pelos testes de layout.
        self.root.update()

    def tearDown(self):
        self.root.destroy()
        self.pasta.cleanup()
        self.assertEqual(self.erros, [])

    def formulario(self):
        self.programa.formulario()
        self.root.update()
        return next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)
                    and w.title() == 'Nova entrada')
