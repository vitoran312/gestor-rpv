"""Gestor de RPV: interface desktop em Python."""
import sqlite3
import json
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk, filedialog, font as tkfont

from dados import Banco, centavos, moeda, data_iso, data_br, nome_formatado, previsao_por_prazo
from componentes import CampoMoeda, CampoData, centralizar, maximizar, AreaRolavel
from contas import JanelaContas, dados_para_copiar
from versao import VERSAO
from tema import cores, definir_modo, atualizar_widgets
from visual import aplicar_superficies, familia_fonte, Icone
from calculadora import JanelaCalculadora
from backup import criar_backup, BackupPreparado
from ordenacao import ordenar
from selecao import habilitar_selecao, pressionar_linha, arrastar
from documentos import validar_anexo, abrir_arquivo
from interacao import instalar_menu_texto, aplicar_formato, capitalizar_inicio, menu_copia, novo_menu, mostrar_menu, copiar_texto


class Aplicativo:
    def __init__(self, janela):
        self.janela = janela
        self.banco = Banco()
        janela.withdraw()
        janela.title('Gestor de RPV')
        janela.resizable(False, False)
        janela.configure(bg=cores()['fundo'])
        self.historico = None
        self.janela_contas = None
        self.calculadora = None
        self.modo_tema = tk.StringVar(value='claro')
        self.configurar_tema()
        instalar_menu_texto(janela)
        janela.bind_all('<Map>', self.tematizar_novo_widget, add='+')

        inicio = ttk.Frame(janela,padding=(40,24))
        inicio.pack(fill='both',expand=True)
        topo = ttk.Frame(inicio)
        topo.pack(fill='x')
        ttk.Label(topo,text='VITORAN  /  TECH',style='Marca.TLabel').pack(side='left')
        self.texto_alternar_tema = tk.StringVar()
        ttk.Button(topo,textvariable=self.texto_alternar_tema,command=self.alternar_tema,width=15).pack(side='right')
        ttk.Frame(inicio).pack(fill='both',expand=True)
        cabecalho = ttk.Frame(inicio)
        cabecalho.pack(fill='x',pady=(24,24))
        ttk.Label(cabecalho,text='Gestor de RPV',style='InicioTitulo.TLabel').pack(anchor='w')
        ttk.Label(cabecalho,text='Registros, recebimentos e documentos. Tudo no seu lugar.',style='Subtitulo.TLabel').pack(anchor='w',pady=(10,0))
        self.grade_inicio = ttk.Frame(inicio)
        self.grade_inicio.pack(fill='x')
        self.cartoes_inicio = []
        for icone,numero,titulo,descricao,rotulo,acao in (
            ('entrada','01','Uma nova operação','Cadastre sua próxima aquisição\ne reúna os documentos da entrada.','Nova entrada',self.formulario),
            ('historico','02','Tudo sob controle','Consulte valores, acompanhe prazos\ne confirme seus recebimentos.','Ver histórico total',self.mostrar_historico),
            ('contas','03','Contas de recebimento','Mantenha seus dados bancários\norganizados e sempre à mão.','Contas de recebimento',self.mostrar_contas)):
            cartao = ttk.Frame(self.grade_inicio,style='Cartao.TFrame',padding=(26,24))
            faixa = ttk.Frame(cartao,style='Superficie.TFrame')
            faixa.pack(fill='x')
            Icone(faixa,icone).pack(side='left')
            ttk.Label(faixa,text=numero,style='CartaoNumero.TLabel').pack(side='right')
            ttk.Label(cartao,text=titulo,style='CartaoTitulo.TLabel').pack(anchor='w',pady=(14,8))
            ttk.Label(cartao,text=descricao,style='CartaoTexto.TLabel',justify='left').pack(anchor='w')
            ttk.Button(cartao,text=rotulo,style='Inicio.Principal.TButton' if icone=='entrada' else 'Inicio.TButton',command=acao).pack(side='bottom',fill='x',pady=(20,8))
            self.cartoes_inicio.append(cartao)
        self.colunas_inicio = None
        self.grade_inicio.bind('<Configure>',self.organizar_inicio)
        ttk.Frame(inicio).pack(fill='both',expand=True)
        rodape_inicio = ttk.Frame(inicio)
        rodape_inicio.pack(fill='x',pady=(22,0))
        ttk.Button(rodape_inicio,text='Sair',command=janela.destroy,width=12).pack(side='left')
        ttk.Label(rodape_inicio,text=f'Vitoran Tech · v{VERSAO}',style='Discreto.TLabel').pack(side='right')
        self.atualizar_alternador_tema()
        centralizar(janela, 1480, 980)
        janela.deiconify()

    def alternar_tema(self):
        self.modo_tema.set('escuro' if self.modo_tema.get()=='claro' else 'claro')
        self.configurar_tema()

    def atualizar_alternador_tema(self):
        if hasattr(self,'texto_alternar_tema'):
            self.texto_alternar_tema.set('Modo escuro' if self.modo_tema.get()=='claro' else 'Modo claro')

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

    def criar_barra_historico(self):
        barra = novo_menu(self.historico)
        arquivo = novo_menu(barra)
        arquivo.add_command(label='Nova entrada', command=self.formulario)
        arquivo.add_command(label='Contas de recebimento', command=self.mostrar_contas)
        arquivo.add_separator()
        arquivo.add_command(label='Backup', command=self.exportar_backup)
        arquivo.add_command(label='Importar dados', command=self.importar_dados)
        arquivo.add_separator()
        arquivo.add_command(label='Fechar histórico', command=self.historico.destroy)
        editar = novo_menu(barra)
        editar.add_command(label='Editar registro', command=self.abrir)
        editar.add_command(label='Excluir registro', command=self.excluir)
        exibir = novo_menu(barra)
        exibir.add_radiobutton(label='Tema claro', variable=self.modo_tema, value='claro', command=self.configurar_tema)
        exibir.add_radiobutton(label='Tema escuro', variable=self.modo_tema, value='escuro', command=self.configurar_tema)
        barra.add_cascade(label='Arquivo', menu=arquivo)
        barra.add_cascade(label='Editar', menu=editar)
        barra.add_cascade(label='Exibir', menu=exibir)
        barra.add_command(label='Calculadora', command=self.abrir_calculadora)
        self.menus = {'Arquivo': arquivo, 'Editar': editar, 'Exibir': exibir, 'barra': barra}
        self.historico.configure(menu=barra)

    def tematizar_novo_widget(self, evento):
        if isinstance(evento.widget, (tk.Toplevel, tk.Text, tk.Menu)):
            atualizar_widgets(evento.widget)

    def configurar_tema(self):
        estilo = ttk.Style()
        estilo.theme_use('clam')
        definir_modo(self.modo_tema.get())
        c = cores()
        fundo,campo,texto = c['fundo'],c['campo'],c['texto']
        fonte = familia_fonte(self.janela)
        self.fonte = fonte
        primario_texto = '#fffdf8' if self.modo_tema.get()=='claro' else '#193623'
        estilo.configure('.',font=(fonte,10),background=fundo,foreground=texto,
                         bordercolor=c['borda'],lightcolor=campo,darkcolor=fundo,troughcolor=fundo)
        aplicar_superficies(self.janela)
        estilo.configure('TButton',padding=(18,10),background=fundo,foreground=texto,anchor='center',focuscolor=c['floresta'])
        estilo.map('TButton',background=[('disabled',fundo),('!disabled',fundo)],foreground=[('disabled',c['desabilitado']),('!disabled',texto)])
        estilo.configure('Inicio.TButton',background=c['superficie'])
        estilo.map('Inicio.TButton',background=[('disabled',c['superficie']),('!disabled',c['superficie'])])
        estilo.configure('Inicio.Principal.TButton',background=c['superficie'])
        estilo.map('Inicio.Principal.TButton',background=[('disabled',c['superficie']),('!disabled',c['superficie'])])
        for nome in ('Salvar.TButton','Principal.TButton','DiaSelecionado.TButton','Resultado.Calculadora.TButton'):
            estilo.configure(nome,font=(fonte,10,'bold'),padding=(18,10),foreground=primario_texto,focuscolor=primario_texto)
            estilo.map(nome,foreground=[('disabled',c['desabilitado']),('!disabled',primario_texto)])
        estilo.configure('Menu.TButton',font=(fonte,16,'bold'),padding=(22,16))
        for tipo in ('TRadiobutton','TCheckbutton'):
            estilo.configure(tipo,background=fundo,foreground=texto,indicatorbackground=campo,indicatorforeground=texto,padding=3)
            estilo.map(tipo,background=[('disabled',fundo),('active',c['ativo']),('!disabled',fundo)],
                       foreground=[('disabled',c['desabilitado']),('!disabled',texto)],
                       indicatorbackground=[('disabled',fundo),('selected',c['primario']),('!disabled',campo)],
                       indicatorforeground=[('disabled',c['desabilitado']),('selected',primario_texto),('!disabled',texto)])
        for nome,tamanho,peso,cor in (
            ('Marca.TLabel',12,'bold',c['floresta']),('InicioTitulo.TLabel',36,'bold',c['floresta']),
            ('Titulo.TLabel',24,'bold',c['floresta']),('Subtitulo.TLabel',11,'normal',c['secundario']),
            ('Discreto.TLabel',9,'normal',c['secundario'])):
            estilo.configure(nome,font=(fonte,tamanho,peso),foreground=cor,background=fundo)
        estilo.configure('Superficie.TFrame',background=c['superficie'])
        for nome,tamanho,peso,cor in (
            ('CartaoTitulo.TLabel',16,'bold',texto),('CartaoTexto.TLabel',10,'normal',c['secundario']),
            ('CartaoNumero.TLabel',11,'normal',c['secundario']),('ResumoTitulo.TLabel',10,'normal',c['secundario']),
            ('ResumoValor.TLabel',19,'bold',texto),('ResumoRealizado.TLabel',19,'bold',c['verde'])):
            estilo.configure(nome,background=c['superficie'],font=(fonte,tamanho,peso),foreground=cor)
        estilo.configure('DataCalculada.TLabel',background=fundo,font=(fonte,10,'bold'))
        estilo.map('DataCalculada.TLabel',background=[('disabled',fundo),('!disabled',fundo)],foreground=[('disabled',c['desabilitado']),('!disabled',texto)])
        estilo.configure('Dinheiro.TFrame',background=campo)
        estilo.configure('Dinheiro.TLabel',background=campo)
        estilo.configure('DiaSelecionado.TButton',font=(fonte,10,'bold'))
        estilo.configure('Recebido.TCheckbutton',foreground=c['verde'],font=(fonte,10,'bold'),background=campo)
        estilo.map('Recebido.TCheckbutton',foreground=[('!disabled',c['verde'])],background=[('active',c['ativo']),('!disabled',campo)])
        estilo.configure('Previsao.TLabel',background=campo,anchor='center')
        estilo.configure('PrevisaoAdiada.TLabel',background=campo,foreground=c['vermelho'],anchor='center')
        estilo.configure('Recebido.TLabel',foreground=c['verde'],font=(fonte,10,'bold'))
        estilo.configure('Restaurar.TButton',font=(fonte,10,'bold'),padding=(18,10))
        estilo.configure('Calculadora.TButton',font=(fonte,15),padding=(8,10))
        estilo.configure('Resultado.Calculadora.TButton',font=(fonte,15,'bold'),padding=(8,10))
        for tipo in ('TEntry','TCombobox'):
            estilo.configure(tipo,fieldbackground=campo,foreground=texto,insertcolor=texto,padding=(10,8),borderwidth=1,relief='flat',arrowsize=14)
            estilo.map(tipo,fieldbackground=[('disabled',fundo),('readonly',campo)],
                       foreground=[('disabled',c['desabilitado']),('readonly',texto)],
                       bordercolor=[('focus',c['floresta']),('!focus',c['borda'])],
                       selectbackground=[('!disabled',c['selecao'])],selectforeground=[('!disabled',c['texto_selecao'])])
        estilo.configure('Treeview',background=campo,fieldbackground=campo,foreground=texto,rowheight=40,borderwidth=0)
        estilo.map('Treeview',background=[('selected',c['selecao'])],foreground=[('selected',c['texto_selecao'])])
        estilo.configure('Treeview.Heading',background=c['sage'],foreground=texto,font=(fonte,10,'bold'),padding=(12,12),relief='flat',borderwidth=0)
        estilo.map('Treeview.Heading',background=[('active',c['ativo'])],foreground=[('active',texto)])
        estilo.configure('TScrollbar',background=c['borda'],troughcolor=fundo,borderwidth=0,arrowsize=12)
        estilo.map('TScrollbar',background=[('active',c['secundario'])])
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
        if self.janela_contas is not None and self.janela_contas.tela.winfo_exists():
            self.janela_contas.tabela.tag_configure('incompleta',foreground=c['vermelho'])

    def mostrar_historico(self):
        if self.historico is not None and self.historico.winfo_exists():
            maximizar(self.historico)
            self.historico.lift()
            self.historico.focus_set()
            return
        self.historico = tk.Toplevel(self.janela)
        self.historico.withdraw()
        self.historico.title('Histórico total — Gestor de RPV')
        self.historico.geometry('1100x650')
        self.historico.minsize(850, 500)
        self.historico.configure(bg=cores()['fundo'])
        self.criar_barra_historico()
        corpo = ttk.Frame(self.historico, padding=20)
        corpo.pack(fill='both', expand=True)
        ttk.Label(corpo,text='Histórico de RPV',style='Titulo.TLabel').pack(anchor='w',pady=(0,4))
        ttk.Label(corpo,text='Acompanhe cada operação, do cadastro ao recebimento.',style='Subtitulo.TLabel').pack(anchor='w',pady=(0,20))
        barra = ttk.Frame(corpo)
        barra.pack(fill='x', pady=(0, 12))
        ttk.Label(barra, text='Buscar nome ou data:').pack(side='left', padx=(0, 6))
        self.busca = tk.StringVar()
        entrada_busca = ttk.Entry(barra, textvariable=self.busca)
        entrada_busca.pack(side='left', fill='x', expand=True)
        aplicar_formato(entrada_busca, self.busca, capitalizar_inicio)
        self.busca.trace_add('write', lambda *_: self.atualizar())

        quadro = ttk.Frame(corpo)
        quadro.pack(fill='both', expand=True)
        colunas = ('nome', 'data', 'custo', 'comissao', 'previsto', 'lucro', 'conta', 'previsao', 'previsao_atual', 'recebido')
        self.tabela = ttk.Treeview(quadro, columns=colunas, show='headings', selectmode='browse')
        titulos = ('Titular original', 'Data de Aquisição', 'Valor de aquisição', 'Comissão', 'Valor Total RPV',
                   'Lucro previsto', 'Conta de destino', 'Previsão inicial', 'Previsão atual', 'Recebido')
        self.ordenacao = None
        self.titulos_colunas = dict(zip(colunas, titulos))
        for coluna, titulo in zip(colunas, titulos):
            self.tabela.heading(coluna, text=titulo, anchor='center', command=lambda c=coluna: self.ordenar_coluna(c))
            largura = max(190 if coluna=='nome' else 145,tkfont.Font(font=(self.fonte,10,'bold')).measure(titulo)+32)
            self.tabela.column(coluna,width=largura,minwidth=100,anchor='center')
        self.acoes_linhas = {}
        self.reposicionar_pendente = False
        vertical = ttk.Scrollbar(quadro, orient='vertical', command=self.tabela.yview)
        horizontal = ttk.Scrollbar(quadro, orient='horizontal', command=self.tabela.xview)
        def rolar_vertical(*args):
            vertical.set(*args)
            self.agendar_acoes()

        def rolar_horizontal(*args):
            horizontal.set(*args)
            self.agendar_acoes()

        self.tabela.configure(yscrollcommand=rolar_vertical, xscrollcommand=rolar_horizontal)
        self.tabela.bind('<Configure>', lambda _: self.agendar_acoes())
        self.tabela.grid(row=0, column=0, sticky='nsew')
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        quadro.rowconfigure(0, weight=1)
        quadro.columnconfigure(0, weight=1)
        habilitar_selecao(self.tabela, abrir=self.abrir, excluir=self.excluir, copiar=self.copiar_selecao)
        self.tabela.bind('<Button-3>', self.menu_historico)
        self.tabela.bind('<ButtonRelease-1>', self.clicar_historico)
        self.tabela.bind('<Double-1>', self.duplo_clique_historico)
        rodape = ttk.Frame(corpo)
        rodape.pack(side='bottom',fill='x',pady=(12,0),before=quadro)
        rodape.columnconfigure(0,weight=1)
        self.resumo = ttk.Frame(rodape)
        self.resumo.grid(row=0,column=0,sticky='ew')
        self.indicadores_resumo = {}
        self.cartoes_resumo = []
        for chave,titulo in (('registros','Registros'),('previsto','Lucro previsto'),
                             ('realizado','Lucro realizado'),('aberto','Capital investido em aberto')):
            cartao = ttk.Frame(self.resumo,style='Resumo.TFrame',padding=(22,20))
            rotulo = ttk.Label(cartao,text=titulo,style='ResumoTitulo.TLabel',anchor='sw')
            cartao.columnconfigure(0,weight=1)
            cartao.rowconfigure(0,minsize=2*tkfont.Font(font=(self.fonte,10)).metrics('linespace'))
            rotulo.grid(row=0,column=0,sticky='sw')
            valor = tk.StringVar()
            ttk.Label(cartao,textvariable=valor,style='ResumoRealizado.TLabel' if chave=='realizado' else 'ResumoValor.TLabel').grid(row=1,column=0,sticky='ew',pady=(6,0))
            self.indicadores_resumo[chave] = valor
            self.cartoes_resumo.append((cartao,rotulo))
        self.colunas_resumo = None
        self.resumo.bind('<Configure>',self.organizar_resumo)
        self.desenhar_icone_lixeira()
        self.botao_lixeira = ttk.Button(rodape, text='Lixeira', image=self.icone_lixeira, compound='image',
                                       width=3, command=self.mostrar_lixeira)
        self.botao_lixeira.grid(row=0,column=1,sticky='se',padx=(16,0))
        self.historico.bind('<Control-f>',lambda _: entrada_busca.focus_set())
        self.historico.bind('<Control-n>',lambda _: self.formulario())
        self.historico.bind('<F5>',lambda _: self.atualizar())
        self.atualizar()
        centralizar(self.historico, 1100, 650)
        self.historico.deiconify()
        maximizar(self.historico)

    def organizar_resumo(self, evento):
        colunas = 4 if evento.width >= 1100 else 2
        if colunas != self.colunas_resumo:
            self.colunas_resumo = colunas
            for coluna in range(4):
                self.resumo.columnconfigure(coluna,weight=1 if coluna<colunas else 0,
                                            uniform='indicadores' if coluna<colunas else '')
            for indice,(cartao,_rotulo) in enumerate(self.cartoes_resumo):
                cartao.grid(row=indice//colunas,column=indice%colunas,sticky='nsew',
                            padx=(4,4),
                            pady=(0,8) if indice//colunas==0 and colunas==2 else 0)
        largura = max(100,evento.width//colunas-36)
        for cartao,rotulo in self.cartoes_resumo:
            rotulo.configure(wraplength=largura)
            for valor in cartao.winfo_children()[1:]:
                valor.configure(wraplength=largura)

    def atualizar(self):
        if self.historico is None or not self.historico.winfo_exists():
            return
        selecionados = self.tabela.selection()
        foco = self.tabela.focus()
        registros = self.banco.listar(self.busca.get().strip())
        if self.ordenacao:
            registros = ordenar(registros, *self.ordenacao)
        self.recebimentos = {str(r['id']): r['recebimento'] for r in registros}
        for widgets in self.acoes_linhas.values():
            for widget in widgets:
                widget.destroy()
        self.acoes_linhas.clear()
        self.tabela.delete(*self.tabela.get_children())
        self.tabela.tag_configure('alternada',background=cores()['linha'])
        for indice,r in enumerate(registros):
            self.tabela.insert('', 'end', iid=str(r['id']), tags=('alternada',) if indice%2 else (), values=(
                r['nome'], data_br(r['aquisicao']), 'R$ ' + moeda(r['custo']),
                'R$ ' + moeda(r['comissao'] or 0),
                'R$ ' + moeda(r['previsto']), 'R$ ' + moeda(r['previsto'] - r['custo']),
                r['conta'], data_br(r['previsao']), data_br(r['previsao_atual']),
                ''))
        disponiveis = set(self.tabela.get_children())
        self.tabela.selection_set([i for i in selecionados if i in disponiveis])
        if foco in disponiveis:
            self.tabela.focus(foco)
        self.agendar_acoes()
        self.indicadores_resumo['registros'].set(str(len(registros)))
        self.indicadores_resumo['previsto'].set('R$ '+moeda(sum(r['previsto']-r['custo'] for r in registros)))
        self.indicadores_resumo['realizado'].set('R$ '+moeda(sum(r['previsto']-r['custo'] for r in registros if r['recebimento'])))
        self.indicadores_resumo['aberto'].set('R$ '+moeda(sum(r['custo'] for r in registros if not r['recebimento'])))

    def ordenar_coluna(self, coluna):
        primeira = 'asc' if coluna in ('nome', 'conta') else 'desc'
        segunda = 'desc' if primeira == 'asc' else 'asc'
        if self.ordenacao is None or self.ordenacao[0] != coluna:
            self.ordenacao = (coluna, primeira)
        elif self.ordenacao[1] == primeira:
            self.ordenacao = (coluna, segunda)
        else:
            self.ordenacao = None
        for chave, titulo in self.titulos_colunas.items():
            seta = ''
            if self.ordenacao and chave == self.ordenacao[0]:
                seta = ' ▼' if self.ordenacao[1] == 'desc' else ' ▲'
            self.tabela.heading(chave, text=titulo + seta)
        self.atualizar()

    def exportar_backup(self):
        pasta = filedialog.askdirectory(parent=self.historico, title='Escolha onde salvar o backup')
        if not pasta:
            return
        try:
            arquivo = criar_backup(self.banco, pasta)
        except (OSError, sqlite3.Error, ValueError) as erro:
            messagebox.showerror('Backup', 'Não foi possível criar o backup. ' + str(erro), parent=self.historico)
            return
        messagebox.showinfo('Backup concluído', f'Backup salvo em:\n{arquivo}', parent=self.historico)

    def importar_dados(self):
        arquivo = filedialog.askopenfilename(parent=self.historico, title='Importar backup do Gestor de RPV',
                                             filetypes=[('Backup do Gestor de RPV', '*.rpvbackup')])
        if not arquivo:
            return
        try:
            with BackupPreparado(arquivo) as pacote:
                resumo = pacote.resumo
                if not messagebox.askyesno('Importar dados',
                    f"O backup contém {resumo['registros']} entrada(s), {resumo['lixeira']} na lixeira, "
                    f"{resumo['contas']} conta(s) e {resumo['documentos']} documento(s).\n\n"
                    'Ele substituirá os dados deste computador, sem juntar os históricos. '
                    'Uma cópia automática dos dados atuais será salva antes. Continuar?',
                    parent=self.historico, icon='warning', default='no'):
                    return
                seguranca = pacote.restaurar(self.banco)
        except (OSError, sqlite3.Error, ValueError, RuntimeError) as erro:
            messagebox.showerror('Importar dados', 'Não foi possível importar o backup. ' + str(erro), parent=self.historico)
            return
        # Formulários antigos não podem continuar editando IDs do banco substituído.
        for janela in list(self.janela.winfo_children()):
            if isinstance(janela, tk.Toplevel) and janela != self.historico and (
                self.calculadora is None or janela != self.calculadora.tela):
                janela.destroy()
        for janela in list(self.historico.winfo_children()):
            if isinstance(janela, tk.Toplevel):
                janela.destroy()
        self.busca.set('')
        self.ordenacao = None
        for chave, titulo in self.titulos_colunas.items():
            self.tabela.heading(chave, text=titulo)
        self.atualizar()
        messagebox.showinfo('Importação concluída', 'Dados recuperados. Backup anterior salvo em:\n' + str(seguranca),
                            parent=self.historico)

    def desenhar_icone_lixeira(self):
        if not hasattr(self,'icone_lixeira'):
            self.icone_lixeira = tk.PhotoImage(master=self.janela,width=24,height=24)
        self.icone_lixeira.blank()
        cor = cores()['texto']
        for retangulo in ((4,5,20,7),(9,2,15,4),(6,8,8,21),(16,8,18,21),
                          (6,20,18,22),(10,9,11,18),(13,9,14,18)):
            self.icone_lixeira.put(cor,to=retangulo)

    def mostrar_lixeira(self):
        tela = tk.Toplevel(self.historico)
        tela.withdraw()
        tela.title('Lixeira')
        tela.configure(bg=cores()['fundo'])
        tela.minsize(620,350)
        corpo = ttk.Frame(tela,padding=20)
        corpo.pack(fill='both',expand=True)
        corpo.rowconfigure(0,weight=1)
        corpo.columnconfigure(0,weight=1)
        tabela = ttk.Treeview(corpo,columns=('nome','data','removido'),show='headings')
        for chave,titulo in (('nome','Titular'),('data','Data de Aquisição'),('removido','Enviado à lixeira')):
            tabela.heading(chave,text=titulo)
            tabela.column(chave,width=220,anchor='center')
        tabela.grid(row=0,column=0,sticky='nsew')
        scroll = ttk.Scrollbar(corpo,orient='vertical',command=tabela.yview)
        tabela.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0,column=1,sticky='ns')

        def atualizar():
            tabela.delete(*tabela.get_children())
            for registro in self.banco.listar_lixeira():
                quando = datetime.fromisoformat(registro['lixeira_em']).strftime('%d/%m/%Y %H:%M:%S')
                tabela.insert('','end',iid=str(registro['id']),values=(registro['nome'],data_br(registro['aquisicao']),quando))

        def restaurar():
            selecao = tabela.selection()
            if not selecao:
                messagebox.showinfo('Lixeira','Selecione uma ou mais entradas para restaurar.',parent=tela)
                return
            try:
                self.banco.restaurar_varios(selecao)
            except (sqlite3.Error,ValueError) as erro:
                messagebox.showerror('Lixeira',str(erro),parent=tela)
                return
            atualizar()
            self.atualizar()

        def contexto(evento):
            linha = tabela.identify_row(evento.y)
            if not linha:
                return
            if linha not in tabela.selection():
                tabela.selection_set(linha)
            menu = novo_menu(tabela)
            menu.add_command(label='Restaurar entradas',command=restaurar)
            return mostrar_menu(menu,evento)

        habilitar_selecao(tabela,abrir=restaurar)
        tabela.bind('<Button-3>',contexto)
        rodape = ttk.Frame(corpo,padding=(0,12,0,0))
        rodape.grid(row=1,column=0,columnspan=2,sticky='ew')
        ttk.Button(rodape,text='Restaurar entradas',style='Restaurar.TButton',width=22,
                   command=restaurar).pack(side='right')
        atualizar()
        centralizar(tela,800,450)
        tela.deiconify()

    def agendar_acoes(self):
        if self.historico is None or not self.historico.winfo_exists():
            return
        if not self.reposicionar_pendente:
            self.reposicionar_pendente = True
            self.tabela.after_idle(self.posicionar_acoes)

    def posicionar_acoes(self):
        self.reposicionar_pendente = False
        if not self.tabela.winfo_exists():
            return
        for linha in self.tabela.get_children():
            caixas = [self.tabela.bbox(linha, coluna) for coluna in ('previsao_atual', 'recebido')]
            visivel = any(caixa and caixa[0] < self.tabela.winfo_width() and caixa[0] + caixa[2] > 0 for caixa in caixas)
            if not visivel:
                for widget in self.acoes_linhas.pop(linha, ()):
                    widget.destroy()
                continue
            if linha not in self.acoes_linhas:
                valores = self.tabela.item(linha, 'values')
                adiada = data_iso(valores[-2]) > data_iso(valores[-3])
                botao = ttk.Label(self.tabela, text=valores[-2], anchor='center', cursor='hand2',
                                  style='PrevisaoAdiada.TLabel' if adiada else 'Previsao.TLabel')
                data_recebimento = self.recebimentos[linha]
                recebido = data_recebimento is not None
                estado = tk.BooleanVar(value=recebido)
                caixa = ttk.Checkbutton(self.tabela, variable=estado,
                    text=data_br(data_recebimento) if recebido else 'Marcar',
                    style='Recebido.TCheckbutton' if recebido else 'TCheckbutton',
                    command=lambda i=int(linha), v=estado, atual=recebido: self.abrir_recebimento(i, v, atual))
                caixa.estado = estado
                for widget in (botao, caixa):
                    widget.bind('<Button-1>',lambda e,i=linha: self.pressionar_controle(e,i))
                    widget.bind('<B1-Motion>',lambda e: arrastar(self.tabela,e.y_root-self.tabela.winfo_rooty()))
                    widget.bind('<ButtonRelease-1>',lambda e,i=linha,w=widget: self.soltar_controle(e,i,w))
                    widget.bind('<Button-3>', lambda e, i=linha: self.menu_historico(e, i))
                self.acoes_linhas[linha] = (botao, caixa)
            for widget, caixa in zip(self.acoes_linhas[linha], caixas):
                if caixa:
                    x, y, largura, altura = caixa
                    if isinstance(widget, ttk.Checkbutton):
                        tamanho = min(widget.winfo_reqwidth(), max(1, largura-4))
                        widget.place(x=x+(largura-tamanho)//2, y=y+2, width=tamanho, height=max(1, altura-4))
                    else:
                        widget.place(x=x+2, y=y+2, width=max(1, largura-4), height=max(1, altura-4))
                else:
                    widget.place_forget()

    def pressionar_controle(self,evento,linha):
        pressionar_linha(self.tabela,linha,evento.state)
        return 'break'

    def soltar_controle(self,evento,linha,widget):
        if not getattr(self.tabela,'_arrastando',False) and not getattr(self.tabela,'_modificadores_mouse',0):
            if isinstance(widget,ttk.Checkbutton):
                widget.invoke()
            else:
                self.editar_previsao(int(linha))
        return 'break'

    def abrir_recebimento(self, identificador, variavel=None, atual=False):
        if variavel is not None:
            variavel.set(atual)
        registro = self.banco.obter(identificador)
        if registro is None:
            self.atualizar()
            return
        tela = tk.Toplevel(self.historico)
        tela.withdraw()
        tela.title('Recebimento')
        tela.configure(bg=cores()['fundo'])
        tela.resizable(False, False)
        tela.transient(self.historico)
        corpo = ttk.Frame(tela, padding=20)
        corpo.pack(fill='both', expand=True)
        ttk.Label(corpo, text=registro['nome']).pack(anchor='w')
        ttk.Label(corpo, text='Data do recebimento', style='Recebido.TLabel').pack(anchor='w', pady=(15, 6))
        valor = tk.StringVar(value=data_br(registro['recebimento']) if registro['recebimento'] else date.today().strftime('%d/%m/%Y'))
        CampoData(corpo, valor).pack(fill='x')
        ttk.Label(corpo, text='Comprovantes de recebimento').pack(anchor='w', pady=(15,6))
        painel_documentos = ttk.Frame(corpo)
        painel_documentos.pack(fill='x')
        anexos_pendentes = self.criar_painel_documentos(painel_documentos, tela, identificador, tipo='recebimento')

        def salvar():
            try:
                self.banco.registrar_recebimento(identificador, data_iso(valor.get()), anexos=anexos_pendentes)
            except ValueError as erro:
                messagebox.showerror('Confira o recebimento', str(erro), parent=tela)
                return
            except (sqlite3.Error,OSError):
                messagebox.showerror('Recebimento', 'Não foi possível salvar.', parent=tela)
                return
            self.atualizar()
            tela.destroy()

        def desmarcar():
            if not messagebox.askyesno('Desmarcar recebimento', 'Remover a confirmação de recebimento desta RPV?',
                                      parent=tela, default='no'):
                return
            try:
                self.banco.registrar_recebimento(identificador, None)
            except (sqlite3.Error, ValueError):
                messagebox.showerror('Recebimento', 'Não foi possível desmarcar.', parent=tela)
                return
            self.atualizar()
            tela.destroy()

        botoes = ttk.Frame(corpo)
        botoes.pack(fill='x', pady=(15, 0))
        if registro['recebimento']:
            ttk.Button(botoes, text='Desmarcar recebimento', command=desmarcar).pack(side='left', padx=(0, 8))
        ttk.Button(botoes, text='Cancelar', command=tela.destroy).pack(side='right')
        ttk.Button(botoes, text='Salvar recebimento', style='Salvar.TButton', command=salvar).pack(side='right', padx=8)
        centralizar(tela)
        tela.deiconify()
        tela.grab_set()
        tela.bind('<Escape>', lambda _: tela.destroy())

    def menu_historico(self, evento, linha=None):
        linha = linha or self.tabela.identify_row(evento.y)
        menu = novo_menu(self.tabela)
        if linha:
            if linha not in self.tabela.selection():
                self.tabela.selection_set(linha)
            unica = len(self.tabela.selection()) == 1
            menu.add_command(label='Editar', command=self.abrir, state='normal' if unica else 'disabled')
            menu.add_command(label='Excluir', command=self.excluir)
            menu.add_command(label='Recebido', command=lambda: self.abrir_recebimento(int(linha)),state='normal' if unica else 'disabled')
            menu.add_command(label='Editar previsão atual', command=lambda: self.editar_previsao(int(linha)),state='normal' if unica else 'disabled')
            menu.add_command(label='Copiar', command=self.copiar_selecao)
            menu.add_separator()
        menu.add_command(label='Nova entrada', command=self.formulario)
        return mostrar_menu(menu, evento)

    def copiar_linha(self, linha):
        valores = list(self.tabela.item(linha, 'values'))
        data = self.recebimentos.get(linha)
        valores[-1] = data_br(data) if data else 'Não recebido'
        copiar_texto(self.tabela, '\t'.join(valores))

    def copiar_selecao(self):
        selecionados = set(self.tabela.selection())
        linhas = []
        for linha in self.tabela.get_children():
            if linha in selecionados:
                valores = list(self.tabela.item(linha,'values'))
                data = self.recebimentos.get(linha)
                valores[-1] = data_br(data) if data else 'Não recebido'
                linhas.append('\t'.join(valores))
        if linhas:
            copiar_texto(self.tabela,'\n'.join(linhas))

    def clicar_historico(self, evento):
        if getattr(self.tabela,'_arrastando',False) or evento.state & 5 or len(self.tabela.selection()) > 1:
            return
        if self.tabela.identify_region(evento.x, evento.y) != 'cell':
            return
        coluna = self.tabela.column(self.tabela.identify_column(evento.x), 'id')
        linha = self.tabela.identify_row(evento.y)
        if linha and coluna in ('previsao_atual', 'recebido'):
            self.tabela.selection_set(linha)
            if coluna == 'previsao_atual':
                self.editar_previsao(int(linha))
            else:
                self.abrir_recebimento(int(linha))
            return 'break'

    def duplo_clique_historico(self, evento):
        if self.tabela.identify_region(evento.x, evento.y) != 'cell':
            return 'break'
        if self.tabela.column(self.tabela.identify_column(evento.x), 'id') not in ('previsao_atual', 'recebido'):
            self.abrir()
        return 'break'

    def editar_previsao(self, identificador):
        registro = self.banco.obter(identificador)
        if registro is None:
            self.atualizar()
            return
        tela = tk.Toplevel(self.historico)
        tela.withdraw()
        tela.title('Previsão atual')
        tela.configure(bg=cores()['fundo'])
        tela.resizable(False, False)
        tela.transient(self.historico)
        corpo = ttk.Frame(tela, padding=20)
        corpo.pack(fill='both', expand=True)
        ttk.Label(corpo, text=registro['nome']).pack(anchor='w')
        ttk.Label(corpo, text='Previsão inicial: ' + data_br(registro['previsao'])).pack(anchor='w', pady=10)
        ttk.Label(corpo, text='Previsão atual de recebimento').pack(anchor='w', pady=(0, 6))
        valor = tk.StringVar(value=data_br(registro['previsao_atual']))
        CampoData(corpo, valor).pack(fill='x')

        def salvar():
            try:
                self.banco.atualizar_previsao(identificador, data_iso(valor.get()))
            except ValueError as erro:
                messagebox.showerror('Confira a previsão', str(erro), parent=tela)
                return
            except sqlite3.Error:
                messagebox.showerror('Previsão atual', 'Não foi possível salvar.', parent=tela)
                return
            self.atualizar()
            tela.destroy()

        rodape = ttk.Frame(corpo)
        rodape.pack(fill='x', pady=(15, 0))
        ttk.Button(rodape, text='Cancelar', command=tela.destroy).pack(side='right')
        ttk.Button(rodape, text='Salvar previsão', style='Salvar.TButton', command=salvar).pack(side='right', padx=8)
        centralizar(tela)
        tela.deiconify()
        tela.grab_set()
        tela.bind('<Escape>', lambda _: tela.destroy())

    def abrir(self):
        selecao = self.tabela.selection()
        if not selecao:
            messagebox.showinfo('Editar registro', 'Selecione uma RPV na lista.', parent=self.historico)
            return
        if len(selecao) != 1:
            messagebox.showinfo('Editar registro','Selecione apenas uma entrada para editar.',parent=self.historico)
            return
        self.formulario(int(selecao[0]))

    def excluir(self):
        selecao = self.tabela.selection()
        if not selecao:
            messagebox.showinfo('Excluir registro', 'Selecione uma RPV na lista.',
                                parent=self.historico)
            return
        confirmar = messagebox.askyesno('Enviar para a lixeira',
            f'Mover {len(selecao)} entrada(s) selecionada(s) para a lixeira?\n\n'
            'Você poderá recuperá-las pela Lixeira.',parent=self.historico,default='no')
        if not confirmar:
            return
        try:
            self.banco.excluir_varios(selecao)
        except (sqlite3.Error,ValueError) as erro:
            messagebox.showerror('Lixeira',str(erro),parent=self.historico)
            return
        self.atualizar()

    def formulario(self, identificador=None):
        registro = self.banco.obter(identificador) if identificador else None
        contas = list(self.banco.contas(somente_ativas=True))
        if registro and all(c['id'] != registro['conta_id'] for c in contas):
            contas.append(self.banco.obter_conta(registro['conta_id']))
        if not contas:
            messagebox.showinfo('Contas de recebimento', 'Cadastre ou reative uma conta antes de criar uma entrada.', parent=self.janela)
            return
        mapa_contas = {c['identificacao']: c['id'] for c in contas}
        conta_inicial = self.banco.obter_conta(registro['conta_id'])['identificacao'] if registro else ('Vitor' if 'Vitor' in mapa_contas else contas[0]['identificacao'])
        tela = tk.Toplevel(self.janela)
        tela.withdraw()
        tela.title('Editar registro' if registro else 'Nova entrada')
        tela.configure(bg=cores()['fundo'])
        tela.resizable(False, False)
        tela.transient(self.historico if self.historico is not None and self.historico.winfo_exists() else self.janela)
        cabecalho = ttk.Frame(tela,padding=(24,16,24,0))
        cabecalho.pack(fill='x')
        ttk.Label(cabecalho,text='Editar registro' if registro else 'Nova entrada',style='Titulo.TLabel').pack(anchor='w')
        area = AreaRolavel(tela)
        area.pack(fill='both',expand=True)
        quadro = area.conteudo
        campos = {}
        modo_previsao = tk.StringVar(value='calendario')
        definicoes = [
            ('nome', 'Nome completo do titular original', ''),
            ('aquisicao', 'Data da aquisição (DD/MM/AAAA)', date.today().strftime('%d/%m/%Y')),
            ('previsto', 'Valor Total RPV', ''),
            ('custo', 'Valor de aquisição (R$)', ''),
            ('conta', 'Receber na conta de', conta_inicial),
            ('previsao', 'Previsão inicial de recebimento (DD/MM/AAAA)', ''),
        ]
        for linha, (chave, titulo, padrao) in enumerate(definicoes):
            if chave == 'previsao':
                ttk.Radiobutton(quadro,text='Previsão inicial por calendário',variable=modo_previsao,value='calendario').grid(row=linha,column=0,sticky='w',pady=6,padx=(0,16))
            else:
                ttk.Label(quadro, text=titulo).grid(row=linha, column=0, sticky='w', pady=6, padx=(0, 16))
            valor = conta_inicial if chave == 'conta' else (registro[chave] if registro else padrao)
            if registro and chave in ('aquisicao', 'previsao'):
                valor = data_br(valor)
            if registro and chave in ('previsto', 'custo'):
                valor = moeda(valor)
            campos[chave] = tk.StringVar(value=valor)
            if chave in ('previsto', 'custo'):
                entrada = CampoMoeda(quadro, campos[chave])
            elif chave in ('aquisicao', 'previsao'):
                entrada = CampoData(quadro, campos[chave])
            elif chave == 'conta':
                entrada = ttk.Combobox(quadro, textvariable=campos[chave], values=tuple(mapa_contas), state='readonly', width=29)
            else:
                entrada = ttk.Entry(quadro, textvariable=campos[chave], width=32)
            entrada.grid(row=linha, column=1, sticky='ew', pady=6)
            if chave == 'previsao':
                campo_previsao = entrada
            if chave == 'nome':
                entrada.focus_set()
                aplicar_formato(entrada, campos['nome'], str.title)

        ttk.Radiobutton(quadro,text='Previsão inicial de recebimento em',variable=modo_previsao,value='dias').grid(row=6,column=0,sticky='w',pady=6,padx=(0,16))
        linha_prazo = ttk.Frame(quadro)
        linha_prazo.grid(row=6,column=1,sticky='ew',pady=6)
        prazo = tk.StringVar()
        entrada_prazo = ttk.Entry(linha_prazo,textvariable=prazo,width=6,justify='center',name='prazo_dias')
        entrada_prazo.pack(side='left')
        ttk.Label(linha_prazo,text='dias.').pack(side='left',padx=(8,12))
        data_calculada = tk.StringVar(value='dd/mm/aaaa')
        resultado_prazo = ttk.Label(linha_prazo,textvariable=data_calculada,style='DataCalculada.TLabel',name='data_calculada')
        resultado_prazo.pack(side='left')
        sincronizando_prazo = False

        def calcular_data(*_):
            nonlocal sincronizando_prazo
            if sincronizando_prazo or modo_previsao.get() != 'dias':
                return
            try:
                prevista = previsao_por_prazo(campos['aquisicao'].get(),prazo.get())
            except ValueError:
                data_calculada.set('dd/mm/aaaa')
                return
            sincronizando_prazo = True
            try:
                campos['previsao'].set(prevista)
                data_calculada.set(prevista)
            finally:
                sincronizando_prazo = False

        def calcular_dias(*_):
            nonlocal sincronizando_prazo
            if sincronizando_prazo or modo_previsao.get() != 'calendario':
                return
            sincronizando_prazo = True
            try:
                dias = (date.fromisoformat(data_iso(campos['previsao'].get())) -
                        date.fromisoformat(data_iso(campos['aquisicao'].get()))).days
                prazo.set(str(dias) if dias >= 0 else '')
                data_calculada.set(campos['previsao'].get() if dias >= 0 else 'dd/mm/aaaa')
            except ValueError:
                prazo.set('')
                data_calculada.set('dd/mm/aaaa')
            finally:
                sincronizando_prazo = False

        def escolher_modo(*_):
            por_dias = modo_previsao.get() == 'dias'
            campo_previsao.habilitar(not por_dias)
            entrada_prazo.state(['!disabled' if por_dias else 'disabled'])
            resultado_prazo.state(['!disabled' if por_dias else 'disabled'])
            calcular_data() if por_dias else calcular_dias()

        prazo.trace_add('write',calcular_data)
        campos['aquisicao'].trace_add('write',lambda *_: calcular_data() if modo_previsao.get()=='dias' else calcular_dias())
        campos['previsao'].trace_add('write',calcular_dias)
        modo_previsao.trace_add('write',escolher_modo)
        escolher_modo()

        lucro = tk.StringVar()
        ttk.Label(quadro, text='Lucro previsto').grid(row=7, column=0, sticky='w', pady=6)
        ttk.Label(quadro, textvariable=lucro).grid(row=7, column=1, sticky='w')

        def atualizar_lucro(*_):
            try:
                lucro.set('R$ ' + moeda(centavos(campos['previsto'].get()) - centavos(campos['custo'].get())))
            except ValueError:
                lucro.set('Preencha os dois valores')

        for chave in ('previsto', 'custo'):
            campos[chave].trace_add('write', lambda *_: tela.after_idle(atualizar_lucro))
        atualizar_lucro()
        ttk.Label(quadro, text='Há comissão?').grid(row=8, column=0, sticky='w', pady=6)
        tem_comissao = tk.StringVar(value='Sim' if registro and registro['comissao'] is not None else 'Não')
        escolha = ttk.Combobox(quadro, textvariable=tem_comissao, values=('Não', 'Sim'), state='readonly', width=29)
        escolha.grid(row=8, column=1, sticky='ew')
        valor_comissao = tk.StringVar(value=moeda(registro['comissao']) if registro and registro['comissao'] is not None else '')
        rotulo_comissao = ttk.Label(quadro, text='Valor da comissão')
        entrada_comissao = CampoMoeda(quadro, valor_comissao)
        rotulo_comissao.grid(row=9, column=0, sticky='w', pady=6)
        entrada_comissao.grid(row=9, column=1, sticky='ew')

        def exibir_comissao(*_):
            for widget in (rotulo_comissao, entrada_comissao):
                if tem_comissao.get() == 'Sim':
                    widget.grid()
                else:
                    widget.grid_remove()
            tela.after_idle(lambda: centralizar(tela))

        tem_comissao.trace_add('write', exibir_comissao)
        exibir_comissao()
        ttk.Label(quadro, text='Observações').grid(row=10, column=0, sticky='nw', pady=10)
        observacoes = tk.Text(quadro, height=4, width=32, wrap='word', font=(self.fonte, 10),
                              bg=cores()['campo'], fg=cores()['texto'], insertbackground=cores()['texto'],
                              selectbackground=cores()['selecao'], selectforeground=cores()['texto_selecao'],
                              relief='flat', padx=6, pady=6)
        observacoes.grid(row=10, column=1, sticky='ew',pady=10)

        def capitalizar_observacoes(_evento=None):
            texto = observacoes.get('1.0', 'end-1c')
            novo = capitalizar_inicio(texto)
            if texto != novo:
                posicao = observacoes.index('insert')
                observacoes.delete('1.0', tk.END)
                observacoes.insert('1.0', novo)
                observacoes.mark_set('insert', posicao)
        observacoes.bind('<KeyRelease>', capitalizar_observacoes)
        observacoes.bind('<<Paste>>', lambda _: observacoes.after_idle(capitalizar_observacoes))
        if registro:
            observacoes.insert('1.0', registro['observacoes'])

        painel_documentos = ttk.Frame(quadro)
        painel_documentos.grid(row=11,column=0,columnspan=2,sticky='ew',pady=(8,0))
        anexos_pendentes = self.criar_painel_documentos(painel_documentos, tela, identificador)

        def salvar():
            try:
                dados = {chave: variavel.get().strip() for chave, variavel in campos.items()}
                if not dados['nome']:
                    raise ValueError('Informe o nome completo do titular original.')
                if modo_previsao.get() == 'dias':
                    dados['previsao'] = previsao_por_prazo(dados['aquisicao'],prazo.get())
                for chave in ('aquisicao', 'previsao'):
                    dados[chave] = data_iso(dados[chave])
                if dados['previsao'] < dados['aquisicao']:
                    raise ValueError('A previsão não pode ser anterior à aquisição.')
                for chave in ('previsto', 'custo'):
                    dados[chave] = centavos(dados[chave])
                dados['conta_id'] = mapa_contas.get(dados['conta'])
                dados['comissao'] = centavos(valor_comissao.get()) if tem_comissao.get() == 'Sim' else None
                dados['observacoes'] = observacoes.get('1.0', 'end-1c').strip()
                self.banco.salvar(dados, identificador, anexos=anexos_pendentes)
            except ValueError as erro:
                messagebox.showerror('Confira o cadastro', str(erro), parent=tela)
                return
            except (sqlite3.Error,OSError):
                messagebox.showerror('Não foi possível salvar', 'Confira o acesso à pasta de dados e tente novamente.', parent=tela)
                return
            self.atualizar()
            tela.destroy()

        ttk.Separator(tela).pack(fill='x',padx=24)
        botoes = ttk.Frame(tela,padding=(20,8,20,12))
        botoes.pack(fill='x')
        for coluna in range(3):
            botoes.columnconfigure(coluna,weight=1,uniform='acoes')
        ttk.Button(botoes,text='Dados de recebimento',width=20,
                   command=lambda: self.ver_dados_recebimento(tela,registro,mapa_contas.get(campos['conta'].get()))).grid(row=0,column=0,sticky='ew',padx=(0,8))
        ttk.Button(botoes,text='Cancelar',width=20,command=tela.destroy).grid(row=0,column=1,sticky='ew',padx=(4,4))
        ttk.Button(botoes,text='Salvar registro',width=20,style='Salvar.TButton',command=salvar).grid(row=0,column=2,sticky='ew',padx=(8,0))
        tela.bind('<Escape>', lambda _: tela.destroy())
        centralizar(tela)
        tela.deiconify()
        tela.grab_set()

    def criar_painel_documentos(self, painel_documentos, tela, identificador=None, tipo='entrada'):
        anexos_pendentes = []
        texto_documentos = tk.StringVar()

        def atualizar_contagem():
            total = len(anexos_pendentes) + (len(self.banco.documentos(identificador, tipo=tipo)) if identificador else 0)
            texto_documentos.set(f'Documentos ({total})')

        def anexar():
            arquivos = filedialog.askopenfilenames(parent=tela,title='Anexar documentos',
                filetypes=[('PDFs e imagens','*.pdf *.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff')])
            try:
                novos = [validar_anexo(arquivo) for arquivo in arquivos]
            except (OSError,ValueError) as erro:
                messagebox.showerror('Anexar documentos',str(erro),parent=tela)
                return
            for arquivo in novos:
                if arquivo not in anexos_pendentes:
                    anexos_pendentes.append(arquivo)
            atualizar_contagem()

        def ver_documentos():
            janela = tk.Toplevel(tela)
            janela.withdraw()
            janela.title('Comprovantes de recebimento' if tipo == 'recebimento' else 'Documentos da entrada')
            janela.configure(bg=cores()['fundo'])
            janela.transient(tela)
            corpo = ttk.Frame(janela,padding=15)
            corpo.pack(fill='both',expand=True)
            lista = ttk.Treeview(corpo,columns=('nome','situacao'),show='headings',selectmode='browse')
            lista.heading('nome',text='Documento')
            lista.heading('situacao',text='Situação')
            lista.column('nome',width=370)
            lista.column('situacao',width=160)
            lista.pack(fill='both',expand=True)
            caminhos = {}

            def atualizar_lista():
                lista.delete(*lista.get_children())
                caminhos.clear()
                if identificador:
                    for documento in self.banco.documentos(identificador, tipo=tipo):
                        iid = 'salvo:' + str(documento['id'])
                        lista.insert('','end',iid=iid,values=(documento['nome'],'Salvo'))
                        caminhos[iid] = ('salvo',documento['id'])
                for indice,arquivo in enumerate(anexos_pendentes):
                    iid = 'novo:' + str(indice)
                    lista.insert('','end',iid=iid,values=(arquivo.name,'Salvar com o recebimento' if tipo == 'recebimento' else 'Salvar com a entrada'))
                    caminhos[iid] = ('novo',arquivo)

            def abrir_documento():
                selecao = lista.selection()
                if len(selecao) != 1:
                    return
                tipo,valor = caminhos[selecao[0]]
                try:
                    caminho = self.banco.caminho_documento(valor) if tipo == 'salvo' else valor
                    abrir_arquivo(caminho)
                except (OSError,ValueError) as erro:
                    messagebox.showerror('Abrir documento',str(erro),parent=janela)

            def retirar():
                selecao = lista.selection()
                if not selecao:
                    return
                tipo,valor = caminhos[selecao[0]]
                if tipo != 'novo':
                    messagebox.showinfo('Documentos','Somente anexos ainda não salvos podem ser retirados nesta tela.',parent=janela)
                    return
                anexos_pendentes.remove(valor)
                atualizar_lista()
                atualizar_contagem()

            def fechar():
                janela.destroy()
                tela.grab_set()

            rodape = ttk.Frame(corpo)
            rodape.pack(fill='x',pady=(12,0))
            ttk.Button(rodape,text='Abrir documento',command=abrir_documento).pack(side='left')
            ttk.Button(rodape,text='Retirar da seleção',command=retirar).pack(side='left',padx=8)
            ttk.Button(rodape,text='Fechar',command=fechar).pack(side='right')
            lista.bind('<Double-1>',lambda _: abrir_documento())
            lista.bind('<Return>',lambda _: abrir_documento())
            janela.protocol('WM_DELETE_WINDOW',fechar)
            janela.bind('<Escape>',lambda _: fechar())
            atualizar_lista()
            centralizar(janela,650,400)
            janela.deiconify()
            janela.grab_set()

        ttk.Button(painel_documentos,text='Anexar documentos',command=anexar).pack(side='left')
        ttk.Button(painel_documentos,textvariable=texto_documentos,command=ver_documentos).pack(side='left',padx=8)
        atualizar_contagem()

        return anexos_pendentes

    def ver_dados_recebimento(self, pai, registro, conta_id):
        if registro and registro['conta_id'] == conta_id:
            conta = json.loads(registro['conta_snapshot'])
        else:
            atual = self.banco.obter_conta(conta_id)
            if atual is None:
                return
            conta = dict(atual)
        tela = tk.Toplevel(pai)
        tela.withdraw()
        tela.title('Dados de recebimento usados nesta RPV')
        tela.configure(bg=cores()['fundo'])
        tela.transient(pai)
        tela.resizable(False, False)
        corpo = ttk.Frame(tela, padding=20)
        corpo.pack(fill='both', expand=True)
        texto = dados_para_copiar(conta)
        rotulo_dados = ttk.Label(corpo, text=texto, wraplength=550)
        rotulo_dados.pack(anchor='w', pady=(0, 15))
        menu_copia(rotulo_dados, lambda: texto)
        if registro and registro['conta_id'] == conta_id:
            ttk.Label(corpo, text='Dados preservados do cadastro desta operação.', wraplength=550).pack(anchor='w', pady=(0, 15))

        def fechar():
            tela.destroy()
            if pai.winfo_exists():
                pai.grab_set()

        ttk.Button(corpo, text='Fechar', command=fechar).pack(side='right')
        tela.protocol('WM_DELETE_WINDOW', fechar)
        tela.bind('<Escape>', lambda _: fechar())
        centralizar(tela)
        tela.deiconify()
        tela.grab_set()


if __name__ == '__main__':
    janela = tk.Tk()
    Aplicativo(janela)
    janela.mainloop()
