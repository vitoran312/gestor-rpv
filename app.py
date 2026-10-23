"""Primeira versão do Gestor de RPVs: execute python app.py."""
import sqlite3
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from dados import Banco, centavos, moeda, data_iso, data_br


class Aplicativo:
    def __init__(self, janela):
        self.janela = janela
        self.banco = Banco()
        janela.title('Gestor de RPV')
        largura = min(1100, max(360, janela.winfo_screenwidth() - 100))
        altura = min(850, max(340, janela.winfo_screenheight() - 100))
        janela.geometry(f'{largura}x{altura}')
        janela.resizable(False, False)
        janela.configure(bg='#181a1f')
        self.historico = None
        self.configurar_tema()

        menu = ttk.Frame(janela, padding=40)
        menu.place(relx=0.5, rely=0.5, anchor='center', width=440)
        ttk.Button(menu, text='Nova entrada', style='Menu.TButton',
                   command=self.formulario).pack(fill='x', pady=(12, 16))
        ttk.Button(menu, text='Ver histórico total', style='Menu.TButton',
                   command=self.mostrar_historico).pack(fill='x', pady=(0, 16))
        ttk.Button(menu, text='Sair', style='Menu.TButton',
                   command=janela.destroy).pack(fill='x')

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
            self.historico.lift()
            self.historico.focus_set()
            return
        self.historico = tk.Toplevel(self.janela)
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
        ttk.Entry(barra, textvariable=self.busca).pack(side='left', fill='x', expand=True)
        self.busca.trace_add('write', lambda *_: self.atualizar())

        quadro = ttk.Frame(corpo)
        quadro.pack(fill='both', expand=True)
        colunas = ('nome', 'data', 'custo', 'previsto', 'lucro', 'conta', 'previsao')
        self.tabela = ttk.Treeview(quadro, columns=colunas, show='headings', selectmode='browse')
        titulos = ('Titular original', 'Aquisição', 'Valor de aquisição', 'Recebimento previsto',
                   'Lucro previsto', 'Conta de destino', 'Previsão inicial')
        for coluna, titulo in zip(colunas, titulos):
            self.tabela.heading(coluna, text=titulo)
            self.tabela.column(coluna, width=170 if coluna == 'nome' else 145, minwidth=100)
        vertical = ttk.Scrollbar(quadro, orient='vertical', command=self.tabela.yview)
        horizontal = ttk.Scrollbar(quadro, orient='horizontal', command=self.tabela.xview)
        self.tabela.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tabela.grid(row=0, column=0, sticky='nsew')
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        quadro.rowconfigure(0, weight=1)
        quadro.columnconfigure(0, weight=1)
        self.tabela.bind('<Double-1>', lambda _: self.abrir())
        self.resumo = ttk.Label(corpo)
        self.resumo.pack(anchor='w', pady=(12, 4))
        ttk.Label(corpo, text='Dados salvos neste computador • Comissão apenas informativa').pack(anchor='w')
        self.atualizar()

    def atualizar(self):
        if self.historico is None or not self.historico.winfo_exists():
            return
        registros = self.banco.listar(self.busca.get().strip())
        self.tabela.delete(*self.tabela.get_children())
        for r in registros:
            self.tabela.insert('', 'end', iid=str(r['id']), values=(
                r['nome'], data_br(r['aquisicao']), 'R$ ' + moeda(r['custo']),
                'R$ ' + moeda(r['previsto']), 'R$ ' + moeda(r['previsto'] - r['custo']),
                r['conta'], data_br(r['previsao'])))
        self.resumo.config(text=f'{len(registros)} registro(s) • '
            f"Investido: R$ {moeda(sum(r['custo'] for r in registros))} • "
            f"Lucro previsto: R$ {moeda(sum(r['previsto'] - r['custo'] for r in registros))}")

    def abrir(self):
        selecao = self.tabela.selection()
        if not selecao:
            messagebox.showinfo('Abrir registro', 'Selecione uma RPV na lista.')
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
        tela = tk.Toplevel(self.janela)
        tela.title('Editar registro' if registro else 'Nova entrada')
        tela.configure(bg='#181a1f')
        tela.resizable(False, False)
        tela.transient(self.historico if self.historico is not None and self.historico.winfo_exists() else self.janela)
        tela.grab_set()
        quadro = ttk.Frame(tela, padding=20)
        quadro.pack(fill='both', expand=True)
        campos = {}
        definicoes = [
            ('nome', 'Nome completo do titular original', ''),
            ('aquisicao', 'Data da aquisição (DD/MM/AAAA)', date.today().strftime('%d/%m/%Y')),
            ('previsto', 'Valor previsto de recebimento (R$)', ''),
            ('custo', 'Valor de aquisição (R$)', ''),
            ('conta', 'Receber na conta de', 'Vitor'),
            ('previsao', 'Previsão inicial de recebimento (DD/MM/AAAA)', ''),
        ]
        for linha, (chave, titulo, padrao) in enumerate(definicoes):
            ttk.Label(quadro, text=titulo).grid(row=linha, column=0, sticky='w', pady=6, padx=(0, 16))
            valor = registro[chave] if registro else padrao
            if registro and chave in ('aquisicao', 'previsao'):
                valor = data_br(valor)
            if registro and chave in ('previsto', 'custo'):
                valor = moeda(valor)
            campos[chave] = tk.StringVar(value=valor)
            if chave == 'conta':
                entrada = ttk.Combobox(quadro, textvariable=campos[chave], values=('Vitor', 'Lilian'), state='readonly', width=29)
            else:
                entrada = ttk.Entry(quadro, textvariable=campos[chave], width=32)
            entrada.grid(row=linha, column=1, sticky='ew', pady=6)
            if chave == 'nome':
                entrada.focus_set()

        lucro = tk.StringVar()
        ttk.Label(quadro, text='Lucro previsto').grid(row=6, column=0, sticky='w', pady=6)
        ttk.Label(quadro, textvariable=lucro).grid(row=6, column=1, sticky='w')

        def atualizar_lucro(*_):
            try:
                lucro.set('R$ ' + moeda(centavos(campos['previsto'].get()) - centavos(campos['custo'].get())))
            except ValueError:
                lucro.set('Preencha os dois valores')

        for chave in ('previsto', 'custo'):
            campos[chave].trace_add('write', atualizar_lucro)
        atualizar_lucro()
        ttk.Label(quadro, text='Há comissão?').grid(row=7, column=0, sticky='w', pady=6)
        tem_comissao = tk.StringVar(value='Sim' if registro and registro['comissao'] is not None else 'Não')
        escolha = ttk.Combobox(quadro, textvariable=tem_comissao, values=('Não', 'Sim'), state='readonly', width=29)
        escolha.grid(row=7, column=1, sticky='ew')
        valor_comissao = tk.StringVar(value=moeda(registro['comissao']) if registro and registro['comissao'] is not None else '')
        rotulo_comissao = ttk.Label(quadro, text='Valor da comissão (só registro)')
        entrada_comissao = ttk.Entry(quadro, textvariable=valor_comissao)
        rotulo_comissao.grid(row=8, column=0, sticky='w', pady=6)
        entrada_comissao.grid(row=8, column=1, sticky='ew')

        def exibir_comissao(*_):
            for widget in (rotulo_comissao, entrada_comissao):
                if tem_comissao.get() == 'Sim':
                    widget.grid()
                else:
                    widget.grid_remove()

        tem_comissao.trace_add('write', exibir_comissao)
        exibir_comissao()
        ttk.Label(quadro, text='Observações').grid(row=9, column=0, sticky='nw', pady=10)
        observacoes = tk.Text(quadro, height=4, width=32, wrap='word', font=('Verdana', 10),
                              bg='#262a33', fg='#f2f4f8', insertbackground='#f2f4f8',
                              selectbackground='#345777', selectforeground='white',
                              relief='flat', padx=6, pady=6)
        observacoes.grid(row=9, column=1, pady=10)
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
        botoes.grid(row=10, column=0, columnspan=2, sticky='e', pady=(10, 0))
        ttk.Button(botoes, text='Cancelar', command=tela.destroy).pack(side='left', padx=8)
        ttk.Button(botoes, text='Salvar registro', command=salvar).pack(side='left')
        tela.bind('<Escape>', lambda _: tela.destroy())


if __name__ == '__main__':
    janela = tk.Tk()
    Aplicativo(janela)
    janela.mainloop()
