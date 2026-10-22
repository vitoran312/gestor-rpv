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
        janela.title('Gestor de RPVs')
        janela.geometry('1100x650')
        janela.minsize(850, 500)
        estilo = ttk.Style()
        estilo.theme_use('clam')
        estilo.configure('.', font=('Verdana', 10))
        estilo.configure('Titulo.TLabel', font=('Verdana', 20, 'bold'))
        estilo.configure('Treeview', rowheight=32)
        estilo.configure('Treeview.Heading', font=('Verdana', 10, 'bold'))

        corpo = ttk.Frame(janela, padding=20)
        corpo.pack(fill='both', expand=True)
        ttk.Label(corpo, text='Gestor de RPVs', style='Titulo.TLabel').pack(anchor='w')
        ttk.Label(corpo, text='Suas aquisições organizadas em um só lugar.').pack(anchor='w', pady=(4, 18))
        barra = ttk.Frame(corpo)
        barra.pack(fill='x', pady=(0, 12))
        ttk.Button(barra, text='Nova RPV', command=self.formulario).pack(side='left')
        ttk.Button(barra, text='Abrir registro', command=self.abrir).pack(side='left', padx=8)
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

    def formulario(self, identificador=None):
        registro = self.banco.obter(identificador) if identificador else None
        tela = tk.Toplevel(self.janela)
        tela.title('Editar RPV' if registro else 'Nova RPV')
        tela.resizable(False, False)
        tela.transient(self.janela)
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
        observacoes = tk.Text(quadro, height=4, width=32, wrap='word', font=('Verdana', 10))
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
