"""Primeira versão do Gestor de RPVs: execute python app.py."""
import sqlite3
import json
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from dados import Banco, centavos, moeda, data_iso, data_br, nome_formatado
from componentes import CampoMoeda, CampoData, centralizar, maximizar
from contas import JanelaContas, dados_para_copiar
from versao import VERSAO
from interacao import instalar_menu_texto, aplicar_formato, capitalizar_inicio, menu_copia, novo_menu, mostrar_menu, copiar_texto


class Aplicativo:
    def __init__(self, janela):
        self.janela = janela
        self.banco = Banco()
        janela.withdraw()
        janela.title('Gestor de RPV')
        janela.resizable(False, False)
        janela.configure(bg='#181a1f')
        self.historico = None
        self.janela_contas = None
        self.configurar_tema()
        instalar_menu_texto(janela)

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

    def configurar_tema(self):
        estilo = ttk.Style()
        estilo.theme_use('clam')
        fundo, campo, texto = '#181a1f', '#262a33', '#f2f4f8'
        estilo.configure('.', font=('Verdana', 10), background=fundo,
                         foreground=texto, bordercolor='#414754',
                         lightcolor=campo, darkcolor=fundo, troughcolor=fundo)
        estilo.configure('TButton', background='#303745', padding=(12, 10))
        estilo.map('TButton', background=[('pressed', '#234f78'), ('active', '#3c526b')],
                   foreground=[('disabled', '#8b929e'), ('!disabled', texto)])
        estilo.configure('Dinheiro.TFrame', background=campo)
        estilo.configure('Dinheiro.TLabel', background=campo)
        estilo.configure('DiaSelecionado.TButton', background='#345777')
        estilo.configure('Recebido.TCheckbutton', foreground='#63df8a', font=('Verdana', 10, 'bold'))
        estilo.map('Recebido.TCheckbutton', foreground=[('!disabled', '#63df8a')])
        estilo.configure('Recebido.TLabel', foreground='#63df8a', font=('Verdana', 10, 'bold'))
        estilo.configure('Celula.TButton', padding=(2, 2))
        estilo.configure('Menu.TButton', font=('Verdana', 16, 'bold'), padding=(20, 15))
        for tipo in ('TEntry', 'TCombobox'):
            estilo.configure(tipo, fieldbackground=campo, foreground=texto,
                             insertcolor=texto, padding=6)
            estilo.map(tipo, fieldbackground=[('readonly', campo)],
                       foreground=[('readonly', texto)],
                       selectbackground=[('!disabled', '#345777')],
                       selectforeground=[('!disabled', texto)])
        estilo.configure('Treeview', background=campo, fieldbackground=campo,
                         foreground=texto, rowheight=34)
        estilo.map('Treeview', background=[('selected', '#345777')],
                   foreground=[('selected', texto)])
        estilo.configure('Treeview.Heading', background='#303745',
                         font=('Verdana', 10, 'bold'), padding=8)
        estilo.map('Treeview.Heading', background=[('active', '#3c526b')])
        self.janela.option_add('*TCombobox*Listbox.background', campo)
        self.janela.option_add('*TCombobox*Listbox.foreground', texto)
        self.janela.option_add('*TCombobox*Listbox.selectBackground', '#345777')
        self.janela.option_add('*TCombobox*Listbox.selectForeground', texto)

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
        self.historico.configure(bg='#181a1f')
        corpo = ttk.Frame(self.historico, padding=20)
        corpo.pack(fill='both', expand=True)
        barra = ttk.Frame(corpo)
        barra.pack(fill='x', pady=(0, 12))
        ttk.Button(barra, text='Nova entrada', command=self.formulario).pack(side='left')
        ttk.Button(barra, text='Editar', command=self.abrir).pack(side='left', padx=8)
        ttk.Button(barra, text='Excluir', command=self.excluir).pack(side='left')
        ttk.Label(barra, text='Buscar nome ou data:').pack(side='left', padx=(20, 6))
        self.busca = tk.StringVar()
        entrada_busca = ttk.Entry(barra, textvariable=self.busca)
        entrada_busca.pack(side='left', fill='x', expand=True)
        aplicar_formato(entrada_busca, self.busca, capitalizar_inicio)
        self.busca.trace_add('write', lambda *_: self.atualizar())

        quadro = ttk.Frame(corpo)
        quadro.pack(fill='both', expand=True)
        colunas = ('nome', 'data', 'custo', 'previsto', 'lucro', 'conta', 'previsao', 'previsao_atual', 'prorrogacao', 'recebido')
        self.tabela = ttk.Treeview(quadro, columns=colunas, show='headings', selectmode='browse')
        titulos = ('Titular original', 'Aquisição', 'Valor de aquisição', 'Recebimento previsto',
                   'Lucro previsto', 'Conta de destino', 'Previsão inicial', 'Previsão atual', 'Prorrogação', 'Recebido')
        for coluna, titulo in zip(colunas, titulos):
            self.tabela.heading(coluna, text=titulo, anchor='center')
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
        ttk.Label(corpo, text='Dados salvos neste computador • Comissão apenas informativa').pack(anchor='w')
        self.atualizar()
        centralizar(self.historico, 1100, 650)
        self.historico.deiconify()
        maximizar(self.historico)

    def atualizar(self):
        if self.historico is None or not self.historico.winfo_exists():
            return
        registros = self.banco.listar(self.busca.get().strip())
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
                f"Adicionar / Ver ({r['total_prorrogacoes']})",
                data_br(r['recebimento']) if r['recebimento'] else 'Não recebido'))
        self.agendar_acoes()
        self.resumo.config(text=f'{len(registros)} registro(s) • '
            f"Investido: R$ {moeda(sum(r['custo'] for r in registros))} • "
            f"Lucro previsto: R$ {moeda(sum(r['previsto'] - r['custo'] for r in registros))}")

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
            caixas = [self.tabela.bbox(linha, coluna) for coluna in ('prorrogacao', 'recebido')]
            visivel = any(caixa and caixa[0] < self.tabela.winfo_width() and caixa[0] + caixa[2] > 0 for caixa in caixas)
            if not visivel:
                for widget in self.acoes_linhas.pop(linha, ()):
                    widget.destroy()
                continue
            if linha not in self.acoes_linhas:
                valores = self.tabela.item(linha, 'values')
                botao = ttk.Button(self.tabela, text=valores[-2], style='Celula.TButton',
                                   command=lambda i=int(linha): self.prorrogar(i))
                recebido = valores[-1] != 'Não recebido'
                estado = tk.BooleanVar(value=recebido)
                caixa = ttk.Checkbutton(self.tabela, variable=estado,
                    text=valores[-1] if recebido else 'Marcar',
                    style='Recebido.TCheckbutton' if recebido else 'TCheckbutton',
                    command=lambda i=int(linha), v=estado, atual=recebido: self.abrir_recebimento(i, v, atual))
                caixa.estado = estado
                for widget in (botao, caixa):
                    widget.bind('<Button-3>', lambda e, i=linha: self.menu_historico(e, i))
                self.acoes_linhas[linha] = (botao, caixa)
            for widget, caixa in zip(self.acoes_linhas[linha], caixas):
                if caixa:
                    x, y, largura, altura = caixa
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
        tela.configure(bg='#181a1f')
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
            menu.add_command(label='Recebido', command=lambda: self.abrir_recebimento(int(linha)))
            menu.add_command(label='Prorrogação', command=lambda: self.prorrogar(int(linha)))
            menu.add_command(label='Copiar', command=lambda: copiar_texto(self.tabela, '\t'.join(self.tabela.item(linha, 'values'))))
            menu.add_separator()
        menu.add_command(label='Nova entrada', command=self.formulario)
        return mostrar_menu(menu, evento)

    def clicar_historico(self, evento):
        if self.tabela.identify_region(evento.x, evento.y) != 'cell':
            return
        coluna = self.tabela.identify_column(evento.x)
        linha = self.tabela.identify_row(evento.y)
        if linha and coluna in ('#9', '#10'):
            self.tabela.selection_set(linha)
            if coluna == '#9':
                self.prorrogar(int(linha))
            else:
                self.abrir_recebimento(int(linha))
            return 'break'

    def duplo_clique_historico(self, evento):
        if self.tabela.identify_region(evento.x, evento.y) != 'cell':
            return 'break'
        if self.tabela.identify_column(evento.x) not in ('#9', '#10'):
            self.abrir()
        return 'break'

    def prorrogar(self, identificador):
        registro = self.banco.obter(identificador)
        if registro is None:
            self.atualizar()
            return
        tela = tk.Toplevel(self.historico)
        tela.withdraw()
        tela.title('Prorrogação')
        tela.configure(bg='#181a1f')
        tela.resizable(False, False)
        tela.transient(self.historico)
        corpo = ttk.Frame(tela, padding=20)
        corpo.pack(fill='both', expand=True)
        ttk.Label(corpo, text=registro['nome'], font=('Verdana', 12, 'bold')).pack(anchor='w')
        ttk.Label(corpo, text='Previsão inicial: ' + data_br(registro['previsao'])).pack(anchor='w', pady=8)
        lista = self.banco.prorrogacoes(identificador)
        quadro = ttk.Frame(corpo)
        quadro.pack(fill='both', expand=True)
        historico = ttk.Treeview(quadro, columns=('ordem', 'data'), show='headings', height=5)
        historico.heading('ordem', text='Prorrogação', anchor='center')
        historico.heading('data', text='Nova previsão', anchor='center')
        for chave in ('ordem', 'data'):
            historico.column(chave, width=160, anchor='center')
        rolagem = ttk.Scrollbar(quadro, orient='vertical', command=historico.yview)
        historico.configure(yscrollcommand=rolagem.set)
        historico.pack(side='left', fill='both', expand=True)
        rolagem.pack(side='right', fill='y')
        for ordem, item in enumerate(lista, 1):
            historico.insert('', 'end', values=(ordem, data_br(item['data'])))
        def nova_prorrogacao():
            entrada = tk.Toplevel(tela)
            entrada.withdraw()
            entrada.title('Nova prorrogação')
            entrada.configure(bg='#181a1f')
            entrada.resizable(False, False)
            entrada.transient(tela)
            campos = ttk.Frame(entrada, padding=20)
            campos.pack(fill='both', expand=True)
            ttk.Label(campos, text='Nova previsão de recebimento').pack(anchor='w', pady=(0, 8))
            valor = tk.StringVar()
            CampoData(campos, valor).pack(fill='x')

            def fechar():
                entrada.destroy()
                tela.grab_set()

            def salvar():
                try:
                    self.banco.prorrogar(identificador, data_iso(valor.get()))
                except ValueError as erro:
                    messagebox.showerror('Confira a data', str(erro), parent=entrada)
                    return
                except sqlite3.Error:
                    messagebox.showerror('Prorrogação', 'Não foi possível salvar a nova data.', parent=entrada)
                    return
                historico.delete(*historico.get_children())
                for ordem, item in enumerate(self.banco.prorrogacoes(identificador), 1):
                    historico.insert('', 'end', values=(ordem, data_br(item['data'])))
                self.atualizar()
                fechar()

            rodape = ttk.Frame(campos)
            rodape.pack(fill='x', pady=(15, 0))
            ttk.Button(rodape, text='Cancelar', command=fechar).pack(side='right')
            ttk.Button(rodape, text='Salvar prorrogação', command=salvar).pack(side='right', padx=8)
            entrada.protocol('WM_DELETE_WINDOW', fechar)
            entrada.bind('<Escape>', lambda _: fechar())
            centralizar(entrada)
            entrada.deiconify()
            entrada.grab_set()

        botoes = ttk.Frame(corpo)
        botoes.pack(fill='x', pady=(15, 0))
        ttk.Button(botoes, text='Nova prorrogação', command=nova_prorrogacao).pack(side='left')
        ttk.Button(botoes, text='Fechar', command=tela.destroy).pack(side='right')
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
            f"Excluir o registro de {registro['nome']}\n"
            f"adquirido em {data_br(registro['aquisicao'])}?\n\n"
            'Esta exclusão é permanente e não pode ser desfeita.',
            parent=self.historico, icon='warning', default='no')
        if not confirmar:
            return
        try:
            self.banco.excluir(identificador)
        except sqlite3.Error:
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
        tela.configure(bg='#181a1f')
        tela.resizable(False, False)
        tela.transient(self.historico if self.historico is not None and self.historico.winfo_exists() else self.janela)
        quadro = ttk.Frame(tela, padding=20)
        quadro.pack(fill='both', expand=True)
        campos = {}
        definicoes = [
            ('nome', 'Nome completo do titular original', ''),
            ('aquisicao', 'Data da aquisição (DD/MM/AAAA)', date.today().strftime('%d/%m/%Y')),
            ('previsto', 'Valor previsto de recebimento (R$)', ''),
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
        rotulo_comissao = ttk.Label(quadro, text='Valor da comissão (só registro)')
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
                              bg='#262a33', fg='#f2f4f8', insertbackground='#f2f4f8',
                              selectbackground='#345777', selectforeground='white',
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
        tela.configure(bg='#181a1f')
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
