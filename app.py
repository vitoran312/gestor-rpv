"""Gestor de RPV: interface desktop em Python."""
import sqlite3
import tkinter as tk
from tkinter import ttk

from dados import Banco
from componentes import centralizar
from contas import JanelaContas
from versao import VERSAO
from tema import cores, definir_modo, atualizar_widgets
from visual import familia_fonte, Icone, icone_tema
from calculadora import JanelaCalculadora
from interacao import instalar_menu_texto
from estilos import criar_estilos
from identidade import aplicar_icone, preparar_windows
from tela_operacoes import OperacoesMixin
from tela_registro import RegistroMixin
from tela_arquivos import ArquivosMixin


class Aplicativo(OperacoesMixin, RegistroMixin, ArquivosMixin):
    def __init__(self, janela):
        self.janela = janela
        self.banco = Banco()
        janela.withdraw()
        janela.title('Gestor de RPV')
        aplicar_icone(janela)
        janela.resizable(False, False)
        janela.configure(bg=cores()['fundo'])
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

        inicio = ttk.Frame(janela,padding=(40,24))
        inicio.pack(fill='both',expand=True)
        topo = ttk.Frame(inicio)
        topo.grid(row=0,column=0,sticky='ew')
        self.texto_alternar_tema = tk.StringVar()
        self.botao_alternar_tema=ttk.Button(topo,textvariable=self.texto_alternar_tema,command=self.alternar_tema,width=15,compound='left')
        self.botao_alternar_tema.pack(side='right')
        ttk.Button(topo,text='Sobre',command=self.mostrar_sobre).pack(side='right',padx=(0,10))
        # O emblema fica centralizado no espaço livre entre o topo e o título, que recebe
        # a maior parte da sobra vertical. Por usar place, ele não aumenta a janela; em telas
        # baixas é ocultado para não empurrar o rodapé.
        inicio.columnconfigure(0,weight=1)
        inicio.rowconfigure(1,weight=3)
        inicio.rowconfigure(4,weight=1)
        espaco_emblema = ttk.Frame(inicio)
        espaco_emblema.grid(row=1,column=0,sticky='nsew')
        self.emblema_inicio = ttk.Label(espaco_emblema,image=janela._marca_cabecalho)
        espaco_emblema.bind('<Configure>',self.posicionar_emblema)
        cabecalho = ttk.Frame(inicio)
        cabecalho.grid(row=2,column=0,sticky='ew',pady=(24,24))
        ttk.Label(cabecalho,text='Gestor de RPV',style='InicioTitulo.TLabel').pack(anchor='w')
        ttk.Label(cabecalho,text='Registros, recebimentos e documentos. Tudo no seu lugar.',style='Subtitulo.TLabel').pack(anchor='w',pady=(10,0))
        self.grade_inicio = ttk.Frame(inicio)
        self.grade_inicio.grid(row=3,column=0,sticky='ew')
        self.cartoes_inicio = []
        for icone,titulo,descricao,rotulo,acao in (
            ('entrada','Uma nova operação','Cadastre sua próxima aquisição\ne reúna os documentos da entrada.','Nova entrada',self.formulario),
            ('historico','Tudo sob controle','Consulte valores, acompanhe prazos\ne confirme seus recebimentos.','Minhas operações',self.mostrar_historico),
            ('contas','Contas de recebimento','Mantenha seus dados bancários\norganizados e sempre à mão.','Contas de recebimento',self.mostrar_contas)):
            cartao = ttk.Frame(self.grade_inicio,style='Cartao.TFrame',padding=(26,24))
            faixa = ttk.Frame(cartao,style='Superficie.TFrame')
            faixa.pack(fill='x')
            Icone(faixa,icone).pack(side='left')
            ttk.Label(cartao,text=titulo,style='CartaoTitulo.TLabel').pack(anchor='w',pady=(14,8))
            ttk.Label(cartao,text=descricao,style='CartaoTexto.TLabel',justify='left').pack(anchor='w')
            ttk.Button(cartao,text=rotulo,style='Inicio.Principal.TButton' if icone=='entrada' else 'Inicio.TButton',command=acao).pack(side='bottom',fill='x',pady=(20,8))
            self.cartoes_inicio.append(cartao)
        self.colunas_inicio = None
        self.grade_inicio.bind('<Configure>',self.organizar_inicio)
        ttk.Frame(inicio).grid(row=4,column=0,sticky='nsew')
        self.texto_aviso_backup = tk.StringVar()
        self.aviso_backup_inicio = ttk.Label(inicio,textvariable=self.texto_aviso_backup,
            style='BackupAviso.TLabel',cursor='hand2',wraplength=760)
        self.aviso_backup_inicio.grid(row=5,column=0,sticky='w',pady=(10,0))
        self.aviso_backup_inicio.bind('<Button-1>',lambda _: self.exportar_backup())
        rodape_inicio = ttk.Frame(inicio)
        rodape_inicio.grid(row=6,column=0,sticky='ew',pady=(22,0))
        ttk.Button(rodape_inicio,text='Sair',command=janela.destroy,width=12).pack(side='left')
        self.assinatura_inicio = ttk.Label(rodape_inicio,text=f'Vitoran Tech · v{VERSAO}',image=janela._marca_rodape,
                                           compound='left',style='Discreto.TLabel')
        self.assinatura_inicio.pack(side='right')
        self.atualizar_alternador_tema()
        self.atualizar_ultimo_backup()
        janela.bind('<FocusIn>',self.atualizar_backup_ao_ativar,add='+')
        self.falha_backup_automatico = False
        self.agendamento_backup = janela.after(1500,self.verificar_backup_automatico)
        janela.bind('<Destroy>',self.cancelar_agendamento_backup,add='+')
        centralizar(janela, 1480, 980)
        janela.deiconify()

    def posicionar_emblema(self,evento):
        if evento.height >= self.emblema_inicio.winfo_reqheight():
            self.emblema_inicio.place(relx=0.5,rely=0.5,anchor='center')
        else:
            self.emblema_inicio.place_forget()

    def alternar_tema(self):
        self.modo_tema.set('escuro' if self.modo_tema.get()=='claro' else 'claro')
        self.configurar_tema()

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

    def organizar_inicio(self,evento):
        colunas = 3 if evento.width>=1050 else 1
        if colunas == self.colunas_inicio:
            return
        self.colunas_inicio = colunas
        for i in range(3):
            self.grade_inicio.columnconfigure(i,weight=1 if i<colunas else 0,
                                               uniform='inicio' if i<colunas else '')
            self.grade_inicio.rowconfigure(i,weight=1 if colunas==1 or i==0 else 0)
        for i,cartao in enumerate(self.cartoes_inicio):
            faixa,titulo,descricao,botao = cartao.winfo_children()
            for filho in (faixa,titulo,descricao,botao):
                filho.pack_forget()
                filho.grid_forget()
            cartao.configure(padding=(26,24) if colunas==3 else (18,12))
            for coluna in range(3):
                cartao.columnconfigure(coluna,weight=1 if coluna==(0 if colunas==3 else 1) else 0)
            if colunas==3:
                faixa.grid(row=0,column=0,sticky='ew')
                titulo.grid(row=1,column=0,sticky='w',pady=(14,8))
                descricao.grid(row=2,column=0,sticky='w')
                botao.grid(row=3,column=0,sticky='ew',pady=(20,8))
            else:
                faixa.grid(row=0,column=0,rowspan=2,sticky='w',padx=(0,18))
                titulo.grid(row=0,column=1,sticky='w')
                descricao.grid(row=1,column=1,sticky='w',pady=(4,0))
                botao.grid(row=0,column=2,rowspan=2,sticky='e',padx=(18,0))
            cartao.grid(row=i//colunas,column=i%colunas,sticky='nsew',padx=(4,4),pady=4)

    def mostrar_contas(self):
        if self.janela_contas is not None and self.janela_contas.tela.winfo_exists():
            self.janela_contas.atualizar()
            self.janela_contas.tela.lift()
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
        ttk.Label(corpo,text='Organização de operações e recebimentos de RPV.',wraplength=430,
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
        self.salvar_tema(modo)
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
            self.tabela.tag_configure('atrasada',foreground=c['vermelho'])
        if self.janela_contas is not None and self.janela_contas.tela.winfo_exists():
            self.janela_contas.atualizar_situacoes()


if __name__ == '__main__':
    preparar_windows()
    janela = tk.Tk()
    Aplicativo(janela)
    janela.mainloop()
