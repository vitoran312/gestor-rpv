"""Páginas dentro da janela principal: início, operações, contas e gráfico, com a seta para voltar."""
import tkinter as tk
from datetime import date
from tkinter import ttk


class NavegacaoMixin:
    """Pilha de páginas sobre o início; voltar fecha a página do topo e mostra a anterior."""

    def pagina_atual(self):
        return self.paginas[-1] if self.paginas else self.inicio

    def abrir_pagina(self, pagina, titulo):
        self.pagina_atual().pack_forget()
        pagina.titulo_pagina = titulo
        self.paginas.append(pagina)
        pagina.bind('<Destroy>', lambda evento, p=pagina: self.pagina_fechada(p) if evento.widget is p else None, add='+')
        pagina.pack(fill='both', expand=True)
        self.atualizar_navegacao()

    def trazer_pagina(self, pagina):
        """Volta a uma página já aberta, fechando as que estão por cima dela."""
        while self.paginas and self.paginas[-1] is not pagina:
            self.paginas[-1].destroy()

    def voltar(self, _evento=None):
        if self.paginas:
            self.paginas[-1].destroy()
        return 'break'

    def pagina_fechada(self, pagina):
        # Também cobre páginas destruídas por outro caminho, como a importação de um backup.
        if pagina not in self.paginas:
            return
        indice = self.paginas.index(pagina)
        acima = self.paginas[indice + 1:]
        del self.paginas[indice:]
        for outra in acima:
            outra.destroy()
        try:
            self.pagina_atual().pack(fill='both', expand=True)
            self.atualizar_navegacao()
            self.pagina_reexibida()
        except tk.TclError:
            pass  # A janela principal está sendo fechada.

    def atualizar_navegacao(self):
        atual = self.pagina_atual()
        self.janela.title('Gestor de RPV' + (f' — {atual.titulo_pagina}' if self.paginas else ''))
        # A barra de menus age sobre a tabela de operações, por isso só aparece nessa página.
        menus = getattr(self, 'menus', None)
        self.janela.configure(menu=menus['barra'] if menus and atual is self.historico else '')

    def pagina_reexibida(self):
        atual = self.pagina_atual()
        if atual is self.historico:
            self.atualizar()
        elif atual is self.inicio:
            self.atualizar_ultimo_backup()
            self.atualizar_aviso_atrasadas()

    def cabecalho_pagina(self, pai, titulo, subtitulo):
        ttk.Button(pai, text='←  Voltar', style='Voltar.TButton', command=self.voltar,
                   takefocus=False).pack(anchor='w', pady=(0, 14))
        ttk.Label(pai, text=titulo, style='Titulo.TLabel').pack(anchor='w', pady=(0, 4))
        ttk.Label(pai, text=subtitulo, style='Subtitulo.TLabel').pack(anchor='w', pady=(0, 20))

    def vigiar_data(self):
        """Se o programa ficar aberto na virada do dia, recalcula as operações atrasadas."""
        if date.today() != self.data_exibida:
            self.data_exibida = date.today()
            self.pagina_reexibida()
        self.agendamento_data = self.janela.after(60 * 1000, self.vigiar_data)
