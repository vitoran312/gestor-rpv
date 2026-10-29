"""Gestor de RPV: interface desktop em Python."""
import os
import sqlite3
import tkinter as tk
import webbrowser
from datetime import date
from tkinter import messagebox, ttk

import cifra
import demonstracao
import novidades
import instancia
from backup import limpar_temporarios, recuperar_interrompidas
from recuperacao import abrir_banco
from componentes import centralizar, maximizar
from contas import JanelaContas
from versao import CONTATO, VERSAO
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
import diario
from dados import pasta_dados
from diario import log


class Aplicativo(NavegacaoMixin, InicioMixin, OperacoesMixin, RegistroMixin, ArquivosMixin):
    def __init__(self, janela):
        self.janela = janela
        janela.withdraw()
        self.banco = abrir_banco(janela)
        recuperar_interrompidas(self.banco)
        limpar_temporarios(self.banco.caminho.parent)
        try:
            # Uma carga da demonstração interrompida (programa fechado à força) é limpa e feita de novo.
            recomecar = demonstracao.limpar_carga_interrompida(self.banco)
            if demonstracao.deve_carregar(self.banco, recomecar):
                demonstracao.carregar(self.banco)
        except (sqlite3.Error, ValueError, OSError):
                log.warning('Dados de demonstração não carregados; o programa abre vazio.', exc_info=True)
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
        self.janela_formulario = None
        self.janela_lixeira = None
        self.janela_recebimento = None
        self.janela_previsao = None
        # Criados pelas telas quando são abertas; até lá, quem os usa confere se já existem.
        self.texto_alternar_tema = None   # Tela inicial.
        self.tabela = None                # Minhas operações.
        self.menus = None
        self.texto_ultimo_backup = None
        self.icone_lixeira = None
        self.ordenacao = None
        self.falha_backup_automatico = False
        tema_salvo = self.banco.configuracao('tema', 'claro')
        self.modo_tema = tk.StringVar(value=tema_salvo if tema_salvo in ('claro', 'escuro') else 'claro')
        self.configurar_tema()
        instalar_menu_texto(janela)
        janela.bind_all('<Map>', self.tematizar_novo_widget, add='+')

        self.construir_inicio(janela)
        self.atualizar_alternador_tema()
        self.atualizar_ultimo_backup()
        self.atualizar_aviso_atrasadas()
        janela.bind('<FocusIn>', self.atualizar_backup_ao_ativar, add='+')
        janela.bind('<Alt-Left>', self.voltar)
        self.data_exibida = date.today()
        self.agendamento_data = janela.after(60 * 1000, self.vigiar_data)
        self.agendamento_tema = janela.after(1200, self.preparar_outro_tema)
        self.agendamento_backup = janela.after(1500, self.verificar_backup_automatico)
        # Entradas cadastradas no celular que chegaram pela pasta do backup automático (Google Drive).
        self.agendamento_celular = janela.after(2500, lambda: self.importar_entradas_celular(automatico=True))
        janela.bind('<Destroy>', self.cancelar_agendamento_backup, add='+')
        janela.protocol('WM_DELETE_WINDOW', self.fechar_programa)
        centralizar(janela, 1480, 980)
        janela.deiconify()
        # As placas de vidro entram logo depois que a janela aparece e ficam paradas ao fim da entrada.
        self.agendamento_arte = janela.after(250, self.arte_inicio.animar)
        self.relogio_inicio.iniciar()
        # As páginas (operações, contas, gráfico) usam a mesma janela; maximizada, a tabela tem espaço para todas as colunas.
        maximizar(janela)

    def alternar_tema(self):
        self.modo_tema.set('escuro' if self.modo_tema.get() == 'claro' else 'claro')
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
            # Sem gravar a preferência, o tema escolhido continua valendo nesta execução.
            log.warning('Preferência de tema não gravada.', exc_info=True)

    def atualizar_alternador_tema(self):
        if self.texto_alternar_tema is not None:
            self.texto_alternar_tema.set('Modo escuro' if self.modo_tema.get() == 'claro' else 'Modo claro')
            self.botao_alternar_tema.configure(image=icone_tema(self.janela, self.modo_tema.get()))

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
        if self.calculadora is not None and self.trazer_se_aberta(self.calculadora.tela):
            return
        self.calculadora = JanelaCalculadora(self.janela)

    def mostrar_sobre(self):
        if self.trazer_se_aberta(self.sobre):
            return
        tela = self.sobre = tk.Toplevel(self.janela)
        tela.withdraw()
        tela.title('Sobre o Gestor de RPV')
        tela.resizable(False, False)
        tela.transient(self.janela_ativa())
        corpo = ttk.Frame(tela, padding=30)
        corpo.pack(fill='both', expand=True)
        ttk.Label(corpo, image=self.janela._marca_vitoran).pack(pady=(0, 12))
        ttk.Label(corpo, text='Gestor de RPV', style='Titulo.TLabel').pack()
        ttk.Label(corpo, text='Organização de operações e recebimentos de RPV.', wraplength=px(tela, 430),
                  justify='center', style='Subtitulo.TLabel').pack(pady=(8, 20))
        ttk.Label(corpo, text='Vitoran Tech', font=(self.fonte, 13, 'bold')).pack()
        ttk.Label(corpo, text='Desenvolvido por Vitor Alves Nascimento').pack(pady=(6, 0))
        ttk.Label(corpo, text=f'Versão {VERSAO}', style='Discreto.TLabel').pack(pady=(8, 16))
        self.criar_novidades(corpo)
        ttk.Label(corpo, text='Sugestões ou dúvidas:', style='Discreto.TLabel').pack()
        contato = ttk.Label(corpo, text=CONTATO, style='Contato.TLabel', cursor='hand2')
        contato.pack(pady=(2, 20))
        contato.bind('<Button-1>', lambda _: webbrowser.open(f'mailto:{CONTATO}'))
        ttk.Button(corpo, text='Fechar', command=tela.destroy).pack()
        tela.bind('<Escape>', lambda _: tela.destroy())
        tela.bind('<Return>', lambda _: tela.destroy())
        centralizar(tela, 550)
        tela.deiconify()
        tela.focus_set()

    def criar_novidades(self, corpo):
        """O que mudou nas últimas versões (novidades.py), com a contagem de novidades e correções de cada uma."""
        ttk.Label(corpo, text='O que mudou nas últimas versões', font=(self.fonte, 11, 'bold')).pack(anchor='w')
        quadro = ttk.Frame(corpo)
        quadro.pack(fill='both', pady=(6, 18))
        c = cores()
        texto = tk.Text(quadro, height=11, width=58, wrap='word', relief='flat', borderwidth=0, padx=10, pady=8,
                        font=(self.fonte, 10), bg=c['campo'], fg=c['texto'], cursor='arrow')
        rolagem = ttk.Scrollbar(quadro, orient='vertical', command=texto.yview)
        texto.configure(yscrollcommand=rolagem.set)
        texto.pack(side='left', fill='both', expand=True)
        rolagem.pack(side='right', fill='y')
        texto.tag_configure('versao', font=(self.fonte, 10, 'bold'), spacing1=6)
        texto.tag_configure('resumo', foreground=c['secundario'])
        texto.tag_configure('item', lmargin1=12, lmargin2=26, spacing1=2)
        for versao, itens in novidades.ultimas():
            texto.insert('end', f'Versão {versao}', 'versao')
            texto.insert('end', f'  ·  {novidades.contagem(itens)}\n', 'resumo')
            for tipo, frase in itens:
                texto.insert('end', ('Novidade: ' if tipo == 'novidade' else 'Correção: ') + frase + '\n', 'item')
        texto.configure(state='disabled')  # Só leitura; ainda dá para selecionar e copiar.
        return texto

    def tematizar_novo_widget(self, evento):
        if isinstance(evento.widget, (tk.Toplevel, tk.Text, tk.Menu)):
            atualizar_widgets(evento.widget)

    def configurar_tema(self):
        estilo = ttk.Style(self.janela)
        modo = self.modo_tema.get()
        definir_modo(modo)
        # A preferência é gravada depois que a tela se redesenha: no Windows, gravar no disco atrasaria a troca.
        self.janela.after_idle(lambda m=modo: self.salvar_tema(m))
        self.fonte = familia_fonte(self.janela)
        fonte = self.fonte
        nome_tema = 'VitoranPro' + modo.title()
        if nome_tema not in estilo.theme_names():
            estilo.theme_create(nome_tema, parent='clam')
            estilo.theme_use(nome_tema)
            criar_estilos(self.janela, estilo, fonte)
        elif estilo.theme_use() != nome_tema:
            estilo.theme_use(nome_tema)
        c = cores()
        campo, texto = c['campo'], c['texto']
        self.janela.option_add('*Menu.font', (fonte, 10))
        self.janela.option_add('*TCombobox*Listbox.background', campo)
        self.janela.option_add('*TCombobox*Listbox.foreground', texto)
        self.janela.option_add('*TCombobox*Listbox.selectBackground', c['selecao'])
        self.janela.option_add('*TCombobox*Listbox.selectForeground', c['texto_selecao'])
        atualizar_widgets(self.janela)
        self.atualizar_alternador_tema()
        if self.icone_lixeira is not None:
            self.desenhar_icone_lixeira()
        if self.tabela is not None and self.tabela.winfo_exists():
            self.colorir_linhas()
        if self.janela_contas is not None and self.janela_contas.tela.winfo_exists():
            self.janela_contas.atualizar_situacoes()


if __name__ == '__main__':
    if os.environ.get('GESTOR_RPV_AUTOTESTE_CIFRA'):
        # Só o CI usa: confere, no .exe já empacotado, que a criptografia dos backups foi incluída.
        raise SystemExit(cifra.autoteste(os.environ['GESTOR_RPV_AUTOTESTE_CIFRA']))
    preparar_windows()
    diario.ativar(pasta_dados())
    janela = tk.Tk()
    janela.withdraw()  # A segunda execução não pisca uma janela vazia antes do aviso.
    janela.report_callback_exception = diario.erro_na_interface
    if not instancia.travar(pasta_dados()):
        messagebox.showinfo('Gestor de RPV', 'O Gestor de RPV já está aberto neste computador. Use a janela que '
                            'já está aberta (veja a barra de tarefas).')
        raise SystemExit(0)
    Aplicativo(janela)
    janela.mainloop()
