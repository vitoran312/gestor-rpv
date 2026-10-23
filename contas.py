"""Janelas para administrar contas de recebimento."""
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

from componentes import centralizar
from dados import nome_formatado, validar_cpf
from interacao import aplicar_formato, aplicar_cpf, capitalizar_inicio, formatar_cpf, novo_menu, mostrar_menu, copiar_texto


def dados_para_copiar(conta):
    campos = (('nome', 'Nome completo'), ('cpf', 'CPF'), ('endereco', 'Endereço'),
              ('banco', 'Banco'), ('agencia', 'Agência'), ('numero', 'Conta'), ('pix', 'Chave Pix'))
    return '\n'.join(f'{titulo}: {(formatar_cpf(conta[chave]) if chave == "cpf" and conta.get(chave) else conta.get(chave)) or "Não informado"}' for chave, titulo in campos)


class JanelaContas:
    def __init__(self, aplicativo):
        self.app = aplicativo
        self.banco = aplicativo.banco
        self.tela = tk.Toplevel(aplicativo.janela)
        self.tela.withdraw()
        self.tela.title('Contas de recebimento')
        self.tela.configure(bg='#181a1f')
        corpo = ttk.Frame(self.tela, padding=20)
        corpo.pack(fill='both', expand=True)
        barra = ttk.Frame(corpo)
        barra.pack(fill='x', pady=(0, 15))
        ttk.Button(barra, text='Cadastrar nova conta', command=self.formulario).pack(side='left')
        ttk.Button(barra, text='Ver / Editar', command=self.editar).pack(side='left', padx=8)
        ttk.Button(barra, text='Desativar / Reativar', command=self.alterar_status).pack(side='left')
        self.tabela = ttk.Treeview(corpo, columns=('nome', 'banco', 'status'), show='headings', selectmode='browse')
        for chave, titulo in (('nome', 'Identificação'), ('banco', 'Banco'), ('status', 'Situação')):
            self.tabela.heading(chave, text=titulo, anchor='center')
            self.tabela.column(chave, width=210, anchor='center')
        self.tabela.tag_configure('incompleta', foreground='#ff6b6b')
        self.tabela.pack(fill='both', expand=True)
        self.tabela.bind('<Button-3>', self.menu_contexto)
        self.tabela.bind('<Double-1>', lambda _: self.editar())
        ttk.Label(corpo, text='Contas desativadas permanecem no histórico e podem ser reativadas.').pack(pady=(12, 0))
        self.atualizar()
        centralizar(self.tela, 850, 480)
        self.tela.deiconify()

    def atualizar(self):
        self.tabela.delete(*self.tabela.get_children())
        for conta in self.banco.contas():
            status = 'Ativa' if conta['ativa'] else 'Desativada'
            incompleta = any(not conta[c] for c in ('nome', 'cpf', 'endereco', 'banco', 'numero', 'pix'))
            if not incompleta:
                try:
                    validar_cpf(conta['cpf'])
                except ValueError:
                    incompleta = True
            if incompleta:
                status = '⚠ Completar cadastro' + (' — Desativada' if not conta['ativa'] else '')
            self.tabela.insert('', 'end', iid=str(conta['id']), values=(conta['identificacao'], conta['banco'], status),
                               tags=('incompleta',) if incompleta else ())

    def menu_contexto(self, evento):
        linha = self.tabela.identify_row(evento.y)
        menu = novo_menu(self.tabela)
        if linha:
            self.tabela.selection_set(linha)
            conta = self.banco.obter_conta(int(linha))
            menu.add_command(label='Editar', command=self.editar)
            menu.add_command(label='Desativar' if conta['ativa'] else 'Reativar', command=self.alterar_status)
            menu.add_command(label='Copiar', command=lambda: copiar_texto(self.tabela, dados_para_copiar(dict(conta))))
            menu.add_separator()
        menu.add_command(label='Cadastrar nova conta', command=self.formulario)
        return mostrar_menu(menu, evento)

    def selecionada(self):
        itens = self.tabela.selection()
        if not itens:
            messagebox.showinfo('Contas de recebimento', 'Selecione uma conta na lista.', parent=self.tela)
            return None
        return self.banco.obter_conta(int(itens[0]))

    def editar(self):
        conta = self.selecionada()
        if conta is not None:
            self.formulario(conta['id'])

    def alterar_status(self):
        conta = self.selecionada()
        if conta is None:
            return
        acao = 'Desativar' if conta['ativa'] else 'Reativar'
        if not messagebox.askyesno(acao + ' conta', f"{acao} a conta {conta['identificacao']}?",
                                  parent=self.tela, default='no'):
            return
        try:
            self.banco.ativar_conta(conta['id'], not conta['ativa'])
        except sqlite3.Error:
            messagebox.showerror('Contas de recebimento', 'Não foi possível alterar a conta.', parent=self.tela)
            return
        self.atualizar()

    def formulario(self, identificador=None):
        conta = self.banco.obter_conta(identificador) if identificador else None
        tela = tk.Toplevel(self.tela)
        tela.withdraw()
        tela.title('Editar conta' if conta else 'Cadastrar nova conta')
        tela.configure(bg='#181a1f')
        tela.resizable(False, False)
        tela.transient(self.tela)
        quadro = ttk.Frame(tela, padding=20)
        quadro.pack(fill='both', expand=True)
        campos = {}
        definicoes = (('identificacao', 'Identificação (ex.: Vitor)'), ('nome', 'Nome completo'),
                      ('cpf', 'CPF'), ('endereco', 'Endereço'), ('banco', 'Nome do banco'),
                      ('agencia', 'Agência'), ('numero', 'Conta bancária'), ('pix', 'Chave Pix'))
        for linha, (chave, titulo) in enumerate(definicoes):
            ttk.Label(quadro, text=titulo).grid(row=linha, column=0, sticky='w', padx=(0, 16), pady=6)
            campos[chave] = tk.StringVar(value=(conta[chave] or '') if conta else '')
            entrada = ttk.Entry(quadro, textvariable=campos[chave], width=40)
            entrada.grid(row=linha, column=1, sticky='ew', pady=6)
            if chave == 'cpf':
                aplicar_cpf(entrada, campos[chave])
            elif chave in ('identificacao', 'nome', 'endereco', 'banco'):
                aplicar_formato(entrada, campos[chave], str.title if chave == 'nome' else capitalizar_inicio)
        ttk.Label(quadro, text='Alterações não modificam os dados de recebimento guardados nas RPVs antigas.',
                  wraplength=600).grid(row=8, column=0, columnspan=2, pady=12)

        def salvar():
            try:
                self.banco.salvar_conta({k: v.get() for k, v in campos.items()}, identificador)
            except ValueError as erro:
                messagebox.showerror('Confira a conta', str(erro), parent=tela)
                return
            except sqlite3.IntegrityError:
                messagebox.showerror('Confira a conta', 'Já existe uma conta com esses dados únicos.', parent=tela)
                return
            except sqlite3.Error:
                messagebox.showerror('Contas de recebimento', 'Não foi possível salvar a conta.', parent=tela)
                return
            self.atualizar()
            tela.destroy()

        botoes = ttk.Frame(quadro)
        botoes.grid(row=9, column=0, columnspan=2, sticky='e')
        ttk.Button(botoes, text='Cancelar', command=tela.destroy).pack(side='left', padx=5)
        ttk.Button(botoes, text='Salvar conta', command=salvar).pack(side='left')
        centralizar(tela)
        tela.deiconify()
        tela.grab_set()
        tela.bind('<Escape>', lambda _: tela.destroy())
