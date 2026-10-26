"""Gestor de RPV: interface desktop em Python."""
import sqlite3
import tkinter as tk
from datetime import date
from tkinter import ttk

import demonstracao
from dados import Banco
from componentes import centralizar, maximizar
from contas import JanelaContas
from versao import VERSAO
from tema import cores, definir_modo, atualizar_widgets
from visual import familia_fonte, icone_tema, px
from calculadora import JanelaCalculadora
from interacao import instalar_menu_texto
from estilos import criar_estilos
from identidade import aplicar_icone, preparar_windows
from tela_inicio import InicioMixin
from navegacao import NavegacaoMixin
from tela_operacoes import OperacoesMixin
from tela_registro import RegistroMixin
from tela_arquivos import ArquivosMixin


class Aplicativo(NavegacaoMixin, InicioMixin, OperacoesMixin, RegistroMixin, ArquivosMixin):
    def __init__(self, janela):
        self.janela = janela
        self.banco = Banco()
        if demonstracao.deve_carregar(self.banco):
            try:
                demonstracao.carregar(self.banco)
            except (sqlite3.Error, ValueError):
                pass  # Sem a demonstração, o programa abre vazio, como antes.
        janela.withdraw()
        janela.title('Gestor de RPV')
        aplicar_icone(janela)
        janela.minsize(px(janela, 900), px(janela, 620))
        janela.configure(bg=cores()['fundo'])
        self.paginas = []
        self.historico = None
        self.janela_contas = None
        self.calculadora = None
        self.sobre = None
        self.grafico_mensal = None
        tema_salvo = self.banco.configuracao('tema', 'claro')
        self.modo_tema = tk.StringVar(value=tema_salvo if tema_salvo in ('claro', 'escuro') else 'claro')
        self.configurar_tema()
        instalar_menu_texto(janela)
        janela.bind_all('<Map>', self.tematizar_novo_widget, add='+')

        self.construir_inicio(janela)
        self.atualizar_alternador_tema()
        self.atualizar_ultimo_backup()
        self.atualizar_aviso_atrasadas()
        janela.bind('<FocusIn>',self.atualizar_backup_ao_ativar,add='+')
        janela.bind('<Alt-Left>',self.voltar)
        self.data_exibida = date.today()
        self.agendamento_data = janela.after(60 * 1000,self.vigiar_data)
        self.agendamento_tema = janela.after(1200,self.preparar_outro_tema)
        self.falha_backup_automatico = False
        self.agendamento_backup = janela.after(1500,self.verificar_backup_automatico)
        janela.bind('<Destroy>',self.cancelar_agendamento_backup,add='+')
        centralizar(janela, 1480, 980)
        janela.deiconify()
        # As placas de vidro entram logo depois que a janela aparece; o relógio mantém tudo flutuando.
        self.agendamento_arte = janela.after(250,self.arte_inicio.animar)
        self.relogio_inicio.iniciar()
        # As páginas (operações, contas, gráfico) usam a mesma janela; maximizada, a tabela tem o espaço de antes.
        maximizar(janela)

    def alternar_tema(self):
        self.modo_tema.set('escuro' if self.modo_tema.get()=='claro' else 'claro')
        self.configurar_tema()

    def preparar_outro_tema(self):
        """Monta em segundo plano o tema ainda não usado, para a primeira troca ser tão rápida quanto as demais."""
        self.agendamento_tema = None
        estilo = ttk.Style(self.janela)
        atual = self.modo_tema.get()
        outro = 'escuro' if atual == 'claro' else 'claro'
        nome = 'VitoranPro' + outro.title()
        if nome in estilo.theme_names():
            return
        estilo.theme_create(nome, parent='clam')
        definir_modo(outro)
        try:
            # theme settings aplica os estilos ao outro tema sem colocá-lo em uso.
            comando = self.janela.register(lambda: criar_estilos(self.janela, estilo, self.fonte))
            try:
                self.janela.tk.call('ttk::style', 'theme', 'settings', nome, comando)
            finally:
                self.janela.deletecommand(comando)
        finally:
            definir_modo(atual)
        # As superfícies da tela inicial no outro tema também ficam prontas antes da primeira troca.
        self.preparar_superficies_inicio(outro)

    def salvar_tema(self, modo):
        try:
            if self.banco.configuracao('tema') != modo:
                self.banco.salvar_configuracao('tema', modo)
        except sqlite3.Error:
            pass  # Sem gravar a preferência, o tema escolhido continua valendo nesta execução.

    def atualizar_alternador_tema(self):
        if hasattr(self,'texto_alternar_tema'):
            self.texto_alternar_tema.set('Modo escuro' if self.modo_tema.get()=='claro' else 'Modo claro')
            self.botao_alternar_tema.configure(image=icone_tema(self.janela,self.modo_tema.get()))

    def mostrar_atrasadas(self):
        self.mostrar_historico()
        self.filtro.set('atrasada')
        self.atualizar()

    def mostrar_contas(self):
        if self.janela_contas is not None and self.janela_contas.tela.winfo_exists():
            self.trazer_pagina(self.janela_contas.tela)
            self.janela_contas.atualizar()
            return
        self.janela_contas = JanelaContas(self)

    def abrir_calculadora(self):
        if self.calculadora is not None and self.calculadora.tela.winfo_exists():
            self.calculadora.tela.deiconify()
            self.calculadora.tela.lift()
            self.calculadora.tela.focus_set()
            return
        self.calculadora = JanelaCalculadora(self.janela)

    def mostrar_sobre(self):
        if self.sobre is not None and self.sobre.winfo_exists():
            self.sobre.deiconify()
            self.sobre.lift()
            self.sobre.focus_set()
            return
        tela = self.sobre = tk.Toplevel(self.janela)
        tela.withdraw()
        tela.title('Sobre o Gestor de RPV')
        tela.resizable(False,False)
        tela.transient(self.historico if self.historico is not None and self.historico.winfo_exists() else self.janela)
        corpo = ttk.Frame(tela,padding=30)
        corpo.pack(fill='both',expand=True)
        ttk.Label(corpo,image=self.janela._marca_vitoran).pack(pady=(0,12))
        ttk.Label(corpo,text='Gestor de RPV',style='Titulo.TLabel').pack()
        ttk.Label(corpo,text='Organização de operações e recebimentos de RPV.',wraplength=px(tela,430),
                  justify='center',style='Subtitulo.TLabel').pack(pady=(8,20))
        ttk.Label(corpo,text='Vitoran Tech',font=(self.fonte,13,'bold')).pack()
        ttk.Label(corpo,text='Desenvolvido por Vitor Alves Nascimento').pack(pady=(6,0))
        ttk.Label(corpo,text=f'Versão {VERSAO}',style='Discreto.TLabel').pack(pady=(8,20))
        ttk.Button(corpo,text='Fechar',command=tela.destroy).pack()
        tela.bind('<Escape>',lambda _: tela.destroy())
        tela.bind('<Return>',lambda _: tela.destroy())
        centralizar(tela,550)
        tela.deiconify()
        tela.focus_set()

    def tematizar_novo_widget(self, evento):
        if isinstance(evento.widget, (tk.Toplevel, tk.Text, tk.Menu)):
            atualizar_widgets(evento.widget)

    def configurar_tema(self):
        estilo=ttk.Style(self.janela)
        modo=self.modo_tema.get()
        definir_modo(modo)
        # A preferência é gravada depois que a tela se redesenha: no Windows, gravar no disco atrasaria a troca.
        self.janela.after_idle(lambda m=modo: self.salvar_tema(m))
        self.fonte=familia_fonte(self.janela)
        fonte=self.fonte
        nome_tema='VitoranPro'+modo.title()
        if nome_tema not in estilo.theme_names():
            estilo.theme_create(nome_tema,parent='clam')
            estilo.theme_use(nome_tema)
            criar_estilos(self.janela,estilo,fonte)
        elif estilo.theme_use()!=nome_tema:
            estilo.theme_use(nome_tema)
        c=cores()
        campo,texto=c['campo'],c['texto']
        self.janela.option_add('*Menu.font',(fonte,10))
        self.janela.option_add('*TCombobox*Listbox.background',campo)
        self.janela.option_add('*TCombobox*Listbox.foreground',texto)
        self.janela.option_add('*TCombobox*Listbox.selectBackground',c['selecao'])
        self.janela.option_add('*TCombobox*Listbox.selectForeground',c['texto_selecao'])
        atualizar_widgets(self.janela)
        self.atualizar_alternador_tema()
        if hasattr(self,'icone_lixeira'):
            self.desenhar_icone_lixeira()
        if hasattr(self,'tabela') and self.tabela.winfo_exists():
            self.tabela.tag_configure('alternada',background=c['linha'])
            self.tabela.tag_configure('atrasada',foreground=c['vermelho'],background=c['atraso'])
        if self.janela_contas is not None and self.janela_contas.tela.winfo_exists():
            self.janela_contas.atualizar_situacoes()


if __name__ == '__main__':
    preparar_windows()
    janela = tk.Tk()
    Aplicativo(janela)
    janela.mainloop()
