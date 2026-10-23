"""Primeira versão do Gestor de RPVs: execute python app.py."""
import sqlite3
import json
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk, filedialog

from dados import Banco, centavos, moeda, data_iso, data_br, nome_formatado
from componentes import CampoMoeda, CampoData, centralizar, maximizar
from contas import JanelaContas, dados_para_copiar
from versao import VERSAO
from tema import cores, definir_modo, atualizar_widgets
from calculadora import JanelaCalculadora
from backup import criar_backup, BackupPreparado
from ordenacao import ordenar
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
        self.modo_tema = tk.StringVar(value='escuro')
        self.configurar_tema()
        instalar_menu_texto(janela)
        janela.bind_all('<Map>', self.tematizar_novo_widget, add='+')

        menu = ttk.Frame(janela, padding=40)
        menu.place(relx=0.5, rely=0.5, anchor='center', width=440)
        ttk.Button(menu, text='Nova entrada', style='Menu.TButton',
                   command=self.formulario).pack(fill='x', pady=(12, 16))
        ttk.Button(menu, text='Ver histórico total', style='Menu.TButton',
                   command=self.mostrar_historico).pack(fill='x', pady=(0, 16))
        ttk.Button(menu, text='Contas de recebimento', style='Menu.TButton',
                   command=self.mostrar_contas).pack(fill='x', pady=(0, 16))
        ttk.Button(menu, text='Sair', style='Menu.TButton',
                   command=janela.destroy).pack(fill='x')
        ttk.Label(janela, text=f'Versão {VERSAO}').place(relx=1, rely=1, anchor='se', x=-18, y=-14)
        centralizar(janela, 1480, 980)
        janela.deiconify()

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
        arquivo.add_command(label='Fechar histórico', command=self.historico.destroy)
        editar = novo_menu(barra)
        editar.add_command(label='Editar registro', command=self.abrir)
        editar.add_command(label='Excluir registro', command=self.excluir)
        editar.add_command(label='Histórico de alterações', command=self.historico_selecionado)
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
        fundo, campo, texto = c['fundo'], c['campo'], c['texto']
        estilo.configure('.', font=('Verdana', 10), background=fundo,
                         foreground=texto, bordercolor=c['borda'],
                         lightcolor=campo, darkcolor=fundo, troughcolor=fundo)
        estilo.configure('TButton', background=c['botao'], padding=(12, 10))
        estilo.map('TButton', background=[('pressed', c['selecao']), ('active', c['ativo'])],
                   foreground=[('disabled', c['desabilitado']), ('!disabled', texto)])
        estilo.configure('Dinheiro.TFrame', background=campo)
        estilo.configure('Dinheiro.TLabel', background=campo)
        estilo.configure('DiaSelecionado.TButton', background=c['selecao'])
        estilo.configure('Recebido.TCheckbutton', foreground=c['verde'], font=('Verdana', 10, 'bold'))
        estilo.map('Recebido.TCheckbutton', foreground=[('!disabled', c['verde'])])
        estilo.configure('Previsao.TLabel', background=campo, anchor='center')
        estilo.configure('PrevisaoAdiada.TLabel', background=campo, foreground=c['vermelho'], anchor='center')
        estilo.configure('Recebido.TLabel', foreground=c['verde'], font=('Verdana', 10, 'bold'))
        estilo.configure('Calculadora.TButton', font=('Verdana', 14, 'bold'), padding=(6, 8))
        estilo.configure('Menu.TButton', font=('Verdana', 16, 'bold'), padding=(20, 15))
        for tipo in ('TEntry', 'TCombobox'):
            estilo.configure(tipo, fieldbackground=campo, foreground=texto,
                             insertcolor=texto, padding=6)
            estilo.map(tipo, fieldbackground=[('readonly', campo)],
                       foreground=[('readonly', texto)],
                       selectbackground=[('!disabled', c['selecao'])],
                       selectforeground=[('!disabled', c['texto_selecao'])])
        estilo.configure('Treeview', background=campo, fieldbackground=campo,
                         foreground=texto, rowheight=34)
        estilo.map('Treeview', background=[('selected', c['selecao'])],
                   foreground=[('selected', c['texto_selecao'])])
        estilo.configure('Treeview.Heading', background=c['botao'],
                         font=('Verdana', 10, 'bold'), padding=8)
        estilo.map('Treeview.Heading', background=[('active', c['ativo'])])
        self.janela.option_add('*TCombobox*Listbox.background', campo)
        self.janela.option_add('*TCombobox*Listbox.foreground', texto)
        self.janela.option_add('*TCombobox*Listbox.selectBackground', c['selecao'])
        self.janela.option_add('*TCombobox*Listbox.selectForeground', c['texto_selecao'])
        atualizar_widgets(self.janela)
        if self.janela_contas is not None and self.janela_contas.tela.winfo_exists():
            self.janela_contas.tabela.tag_configure('incompleta', foreground=c['vermelho'])

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
        barra = ttk.Frame(corpo)
        barra.pack(fill='x', pady=(0, 12))
        protecao = ttk.Frame(barra)
        protecao.pack(side='right', padx=(24, 0))
        ttk.Button(protecao, text='Backup', command=self.exportar_backup).pack(side='left', padx=4)
        ttk.Button(protecao, text='Importar dados', command=self.importar_dados).pack(side='left', padx=4)
        ttk.Button(protecao, text='Lixeira', command=self.mostrar_lixeira).pack(side='left', padx=4)
        ttk.Label(barra, text='Buscar nome ou data:').pack(side='left', padx=(0, 6))
        self.busca = tk.StringVar()
        entrada_busca = ttk.Entry(barra, textvariable=self.busca)
        entrada_busca.pack(side='left', fill='x', expand=True)
        aplicar_formato(entrada_busca, self.busca, capitalizar_inicio)
        self.busca.trace_add('write', lambda *_: self.atualizar())

        quadro = ttk.Frame(corpo)
        quadro.pack(fill='both', expand=True)
        colunas = ('nome', 'data', 'custo', 'previsto', 'lucro', 'conta', 'previsao', 'previsao_atual', 'recebido')
        self.tabela = ttk.Treeview(quadro, columns=colunas, show='headings', selectmode='browse')
        titulos = ('Titular original', 'Data de Aquisição', 'Valor de aquisição', 'Valor Total RPV',
                   'Lucro previsto', 'Conta de destino', 'Previsão inicial', 'Previsão atual', 'Recebido')
        self.ordenacao = None
        self.titulos_colunas = dict(zip(colunas, titulos))
        for coluna, titulo in zip(colunas, titulos):
            self.tabela.heading(coluna, text=titulo, anchor='center', command=lambda c=coluna: self.ordenar_coluna(c))
            self.tabela.column(coluna, width=170 if coluna == 'nome' else 145, minwidth=100, anchor='center')
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
        self.tabela.bind('<Button-3>', self.menu_historico)
        self.tabela.bind('<ButtonRelease-1>', self.clicar_historico)
        self.tabela.bind('<Double-1>', self.duplo_clique_historico)
        self.resumo = ttk.Label(corpo)
        self.resumo.pack(anchor='w', pady=(12, 4))
        ttk.Label(corpo, text='Dados salvos neste computador').pack(anchor='w')
        self.atualizar()
        centralizar(self.historico, 1100, 650)
        self.historico.deiconify()
        maximizar(self.historico)

    def atualizar(self):
        if self.historico is None or not self.historico.winfo_exists():
            return
        registros = self.banco.listar(self.busca.get().strip())
        if self.ordenacao:
            registros = ordenar(registros, *self.ordenacao)
        self.recebimentos = {str(r['id']): r['recebimento'] for r in registros}
        for widgets in self.acoes_linhas.values():
            for widget in widgets:
                widget.destroy()
        self.acoes_linhas.clear()
        self.tabela.delete(*self.tabela.get_children())
        for r in registros:
            self.tabela.insert('', 'end', iid=str(r['id']), values=(
                r['nome'], data_br(r['aquisicao']), 'R$ ' + moeda(r['custo']),
                'R$ ' + moeda(r['previsto']), 'R$ ' + moeda(r['previsto'] - r['custo']),
                r['conta'], data_br(r['previsao']), data_br(r['previsao_atual']),
                ''))
        self.agendar_acoes()
        self.resumo.config(text=f'{len(registros)} registro(s) • '
            f"Lucro previsto: R$ {moeda(sum(r['previsto'] - r['custo'] for r in registros))}")

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

    def historico_selecionado(self):
        selecao = self.tabela.selection()
        if not selecao:
            messagebox.showinfo('Histórico de alterações', 'Selecione uma RPV na lista.', parent=self.historico)
            return
        self.mostrar_auditoria(int(selecao[0]))

    def mostrar_auditoria(self, identificador):
        registro = self.banco.obter(identificador)
        if registro is None:
            return
        tela = tk.Toplevel(self.historico)
        tela.withdraw()
        tela.title('Histórico de alterações — ' + registro['nome'])
        tela.configure(bg=cores()['fundo'])
        corpo = ttk.Frame(tela, padding=20)
        corpo.pack(fill='both', expand=True)
        ttk.Label(corpo, text='Alterações registradas a partir da versão 0.9.0.').pack(anchor='w', pady=(0, 10))
        quadro = ttk.Frame(corpo)
        quadro.pack(fill='both', expand=True)
        tabela = ttk.Treeview(quadro, columns=('quando','acao','campo','antes','depois'), show='headings')
        for chave, titulo in (('quando','Data e hora'), ('acao','Ação'), ('campo','Campo'), ('antes','Antes'), ('depois','Depois')):
            tabela.heading(chave, text=titulo)
            tabela.column(chave, width=180, anchor='center')
        scroll = ttk.Scrollbar(quadro, orient='vertical', command=tabela.yview)
        tabela.configure(yscrollcommand=scroll.set)
        tabela.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        nomes = {'nome':'Titular', 'aquisicao':'Data de Aquisição', 'previsto':'Valor Total RPV',
                 'custo':'Valor de aquisição', 'comissao':'Comissão', 'conta':'Conta de destino',
                 'previsao':'Previsão inicial', 'previsao_atual':'Previsão atual', 'recebimento':'Recebimento',
                 'observacoes':'Observações', 'lixeira_em':'Lixeira', 'conta_snapshot':'Dados de recebimento',
                 'conta_id':'Identificador da conta', 'previsao_atual_definida':'Previsão atual'}

        def exibir(campo, valor):
            if valor is None:
                return '—'
            if campo in ('previsto','custo','comissao'):
                return 'R$ ' + moeda(valor)
            if campo in ('aquisicao','previsao','previsao_atual','previsao_atual_definida','recebimento'):
                return data_br(valor)
            return str(valor)

        for evento in self.banco.historico(identificador):
            quando = datetime.fromisoformat(evento['quando']).astimezone().strftime('%d/%m/%Y %H:%M:%S')
            for campo, valores in json.loads(evento['alteracoes']).items():
                tabela.insert('', 'end', values=(quando, evento['acao'], nomes.get(campo,campo),
                    exibir(campo,valores['antes']), exibir(campo,valores['depois'])))
        detalhe = tk.Text(corpo, height=5, wrap='word', state='disabled', font=('Verdana',10))
        detalhe.pack(fill='x', pady=(12, 0))

        def selecionar(_evento):
            linhas = tabela.selection()
            if linhas:
                valores = tabela.item(linhas[0], 'values')
                detalhe.configure(state='normal')
                detalhe.delete('1.0', tk.END)
                detalhe.insert('1.0', '\n'.join(str(v) for v in valores))
                detalhe.configure(state='disabled')
        tabela.bind('<<TreeviewSelect>>', selecionar)
        centralizar(tela, 1050, 600)
        tela.deiconify()

    def mostrar_lixeira(self):
        tela = tk.Toplevel(self.historico)
        tela.withdraw()
        tela.title('Lixeira')
        tela.configure(bg=cores()['fundo'])
        corpo = ttk.Frame(tela, padding=20)
        corpo.pack(fill='both', expand=True)
        tabela = ttk.Treeview(corpo, columns=('nome','data','removido'), show='headings', selectmode='browse')
        for chave,titulo in (('nome','Titular'),('data','Data de Aquisição'),('removido','Enviado à lixeira')):
            tabela.heading(chave,text=titulo)
            tabela.column(chave,width=220,anchor='center')
        tabela.pack(fill='both',expand=True)

        def atualizar():
            tabela.delete(*tabela.get_children())
            for registro in self.banco.listar_lixeira():
                quando = datetime.fromisoformat(registro['lixeira_em']).strftime('%d/%m/%Y %H:%M:%S')
                tabela.insert('', 'end', iid=str(registro['id']), values=(registro['nome'],data_br(registro['aquisicao']),quando))

        def restaurar():
            selecao = tabela.selection()
            if not selecao:
                messagebox.showinfo('Lixeira','Selecione uma entrada para restaurar.',parent=tela)
                return
            try:
                self.banco.restaurar(int(selecao[0]))
            except (sqlite3.Error,ValueError) as erro:
                messagebox.showerror('Lixeira',str(erro),parent=tela)
                return
            atualizar()
            self.atualizar()

        ttk.Button(corpo,text='Restaurar entrada',command=restaurar).pack(anchor='e',pady=(12,0))
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
                botao.bind('<Button-1>', lambda _, i=int(linha): self.editar_previsao(i))
                data_recebimento = self.recebimentos[linha]
                recebido = data_recebimento is not None
                estado = tk.BooleanVar(value=recebido)
                caixa = ttk.Checkbutton(self.tabela, variable=estado,
                    text=data_br(data_recebimento) if recebido else 'Marcar',
                    style='Recebido.TCheckbutton' if recebido else 'TCheckbutton',
                    command=lambda i=int(linha), v=estado, atual=recebido: self.abrir_recebimento(i, v, atual))
                caixa.estado = estado
                for widget in (botao, caixa):
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

        def salvar():
            try:
                self.banco.registrar_recebimento(identificador, data_iso(valor.get()))
            except ValueError as erro:
                messagebox.showerror('Confira o recebimento', str(erro), parent=tela)
                return
            except sqlite3.Error:
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
        ttk.Button(botoes, text='Salvar recebimento', command=salvar).pack(side='right', padx=8)
        centralizar(tela)
        tela.deiconify()
        tela.grab_set()
        tela.bind('<Escape>', lambda _: tela.destroy())

    def menu_historico(self, evento, linha=None):
        linha = linha or self.tabela.identify_row(evento.y)
        menu = novo_menu(self.tabela)
        if linha:
            self.tabela.selection_set(linha)
            menu.add_command(label='Editar', command=self.abrir)
            menu.add_command(label='Excluir', command=self.excluir)
            menu.add_command(label='Histórico de alterações', command=lambda: self.mostrar_auditoria(int(linha)))
            menu.add_command(label='Recebido', command=lambda: self.abrir_recebimento(int(linha)))
            menu.add_command(label='Editar previsão atual', command=lambda: self.editar_previsao(int(linha)))
            menu.add_command(label='Copiar', command=lambda: self.copiar_linha(linha))
            menu.add_separator()
        menu.add_command(label='Nova entrada', command=self.formulario)
        return mostrar_menu(menu, evento)

    def copiar_linha(self, linha):
        valores = list(self.tabela.item(linha, 'values'))
        data = self.recebimentos.get(linha)
        valores[-1] = data_br(data) if data else 'Não recebido'
        copiar_texto(self.tabela, '\t'.join(valores))

    def clicar_historico(self, evento):
        if self.tabela.identify_region(evento.x, evento.y) != 'cell':
            return
        coluna = self.tabela.identify_column(evento.x)
        linha = self.tabela.identify_row(evento.y)
        if linha and coluna in ('#8', '#9'):
            self.tabela.selection_set(linha)
            if coluna == '#8':
                self.editar_previsao(int(linha))
            else:
                self.abrir_recebimento(int(linha))
            return 'break'

    def duplo_clique_historico(self, evento):
        if self.tabela.identify_region(evento.x, evento.y) != 'cell':
            return 'break'
        if self.tabela.identify_column(evento.x) not in ('#8', '#9'):
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
        ttk.Button(rodape, text='Salvar previsão', command=salvar).pack(side='right', padx=8)
        centralizar(tela)
        tela.deiconify()
        tela.grab_set()
        tela.bind('<Escape>', lambda _: tela.destroy())

    def abrir(self):
        selecao = self.tabela.selection()
        if not selecao:
            messagebox.showinfo('Editar registro', 'Selecione uma RPV na lista.', parent=self.historico)
            return
        self.formulario(int(selecao[0]))

    def excluir(self):
        selecao = self.tabela.selection()
        if not selecao:
            messagebox.showinfo('Excluir registro', 'Selecione uma RPV na lista.',
                                parent=self.historico)
            return
        identificador = int(selecao[0])
        registro = self.banco.obter(identificador)
        if registro is None:
            self.atualizar()
            return
        confirmar = messagebox.askyesno(
            'Excluir registro',
            f"Mover para a lixeira o registro de {registro['nome']}\n"
            f"adquirido em {data_br(registro['aquisicao'])}?\n\n"
            'Você poderá recuperar a entrada pela Lixeira.',
            parent=self.historico, icon='warning', default='no')
        if not confirmar:
            return
        try:
            self.banco.excluir(identificador)
        except (sqlite3.Error, ValueError):
            messagebox.showerror('Não foi possível excluir',
                                 'O registro não foi excluído. Tente novamente.',
                                 parent=self.historico)
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
        quadro = ttk.Frame(tela, padding=20)
        quadro.pack(fill='both', expand=True)
        campos = {}
        definicoes = [
            ('nome', 'Nome completo do titular original', ''),
            ('aquisicao', 'Data da aquisição (DD/MM/AAAA)', date.today().strftime('%d/%m/%Y')),
            ('previsto', 'Valor Total RPV', ''),
            ('custo', 'Valor de aquisição (R$)', ''),
            ('conta', 'Receber na conta de', conta_inicial),
            ('previsao', 'Previsão inicial de recebimento (DD/MM/AAAA)', ''),
        ]
        for linha, (chave, titulo, padrao) in enumerate(definicoes):
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
            if chave == 'nome':
                entrada.focus_set()
                aplicar_formato(entrada, campos['nome'], str.title)

        lucro = tk.StringVar()
        ttk.Label(quadro, text='Lucro previsto').grid(row=6, column=0, sticky='w', pady=6)
        ttk.Label(quadro, textvariable=lucro).grid(row=6, column=1, sticky='w')

        def atualizar_lucro(*_):
            try:
                lucro.set('R$ ' + moeda(centavos(campos['previsto'].get()) - centavos(campos['custo'].get())))
            except ValueError:
                lucro.set('Preencha os dois valores')

        for chave in ('previsto', 'custo'):
            campos[chave].trace_add('write', lambda *_: tela.after_idle(atualizar_lucro))
        atualizar_lucro()
        ttk.Label(quadro, text='Há comissão?').grid(row=7, column=0, sticky='w', pady=6)
        tem_comissao = tk.StringVar(value='Sim' if registro and registro['comissao'] is not None else 'Não')
        escolha = ttk.Combobox(quadro, textvariable=tem_comissao, values=('Não', 'Sim'), state='readonly', width=29)
        escolha.grid(row=7, column=1, sticky='ew')
        valor_comissao = tk.StringVar(value=moeda(registro['comissao']) if registro and registro['comissao'] is not None else '')
        rotulo_comissao = ttk.Label(quadro, text='Valor da comissão')
        entrada_comissao = CampoMoeda(quadro, valor_comissao)
        rotulo_comissao.grid(row=8, column=0, sticky='w', pady=6)
        entrada_comissao.grid(row=8, column=1, sticky='ew')

        def exibir_comissao(*_):
            for widget in (rotulo_comissao, entrada_comissao):
                if tem_comissao.get() == 'Sim':
                    widget.grid()
                else:
                    widget.grid_remove()
            tela.after_idle(lambda: centralizar(tela))

        tem_comissao.trace_add('write', exibir_comissao)
        exibir_comissao()
        ttk.Label(quadro, text='Observações').grid(row=9, column=0, sticky='nw', pady=10)
        observacoes = tk.Text(quadro, height=4, width=32, wrap='word', font=('Verdana', 10),
                              bg=cores()['campo'], fg=cores()['texto'], insertbackground=cores()['texto'],
                              selectbackground=cores()['selecao'], selectforeground=cores()['texto_selecao'],
                              relief='flat', padx=6, pady=6)
        observacoes.grid(row=9, column=1, pady=10)

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

        def salvar():
            try:
                dados = {chave: variavel.get().strip() for chave, variavel in campos.items()}
                if not dados['nome']:
                    raise ValueError('Informe o nome completo do titular original.')
                for chave in ('aquisicao', 'previsao'):
                    dados[chave] = data_iso(dados[chave])
                if dados['previsao'] < dados['aquisicao']:
                    raise ValueError('A previsão não pode ser anterior à aquisição.')
                for chave in ('previsto', 'custo'):
                    dados[chave] = centavos(dados[chave])
                dados['conta_id'] = mapa_contas.get(dados['conta'])
                dados['comissao'] = centavos(valor_comissao.get()) if tem_comissao.get() == 'Sim' else None
                dados['observacoes'] = observacoes.get('1.0', 'end-1c').strip()
                self.banco.salvar(dados, identificador)
            except ValueError as erro:
                messagebox.showerror('Confira o cadastro', str(erro), parent=tela)
                return
            except sqlite3.Error:
                messagebox.showerror('Não foi possível salvar', 'Confira o acesso à pasta de dados e tente novamente.', parent=tela)
                return
            self.atualizar()
            tela.destroy()

        botoes = ttk.Frame(quadro)
        botoes.grid(row=11, column=0, columnspan=2, sticky='e', pady=(10, 0))
        ttk.Button(botoes, text='Dados de recebimento',
                   command=lambda: self.ver_dados_recebimento(tela, registro, mapa_contas.get(campos['conta'].get()))).pack(side='left', padx=8)
        ttk.Button(botoes, text='Cancelar', command=tela.destroy).pack(side='left', padx=8)
        ttk.Button(botoes, text='Salvar registro', command=salvar).pack(side='left')
        tela.bind('<Escape>', lambda _: tela.destroy())
        centralizar(tela)
        tela.deiconify()
        tela.grab_set()

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
