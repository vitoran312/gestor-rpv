"""Janelas para administrar contas de recebimento."""
from tema import cores
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

from componentes import centralizar, AreaRolavel
from selecao import habilitar_selecao, pressionar_linha, arrastar
from dados import validar_cpf, ESTADOS
from interacao import aplicar_formato, aplicar_cpf, capitalizar_inicio, formatar_cpf, novo_menu, mostrar_menu, copiar_texto


def dados_para_copiar(conta):
    campos = (('nome', 'Nome completo'), ('cpf', 'CPF'), ('endereco', 'Endereço'),
              ('numero_endereco', 'Número do endereço'), ('cidade', 'Cidade'), ('estado', 'Estado'),
              ('banco', 'Banco'), ('agencia', 'Agência'), ('numero', 'Conta'), ('pix', 'Chave Pix'))
    return '\n'.join(f'{titulo}: {(formatar_cpf(conta[chave]) if chave == "cpf" and conta.get(chave) else conta.get(chave)) or "Não informado"}' for chave, titulo in campos)


class JanelaContas:
    def __init__(self, aplicativo):
        self.app = aplicativo
        self.banco = aplicativo.banco
        self.tela = tk.Toplevel(aplicativo.janela)
        self.tela.withdraw()
        self.tela.title('Contas de recebimento')
        self.tela.configure(bg=cores()['fundo'])
        corpo = ttk.Frame(self.tela, padding=20)
        corpo.pack(fill='both', expand=True)
        barra = ttk.Frame(corpo)
        barra.pack(fill='x', pady=(0, 15))
        ttk.Button(barra, text='Cadastrar nova conta', style='Principal.TButton', command=self.formulario).pack(side='left')
        ttk.Button(barra, text='Ver / Editar', command=self.editar).pack(side='left', padx=8)
        ttk.Button(barra, text='Desativar / Reativar', command=self.alterar_status).pack(side='left')
        ttk.Button(barra, text='Remover', command=self.remover).pack(side='left', padx=8)
        self.tabela = ttk.Treeview(corpo, style='Contas.Treeview', columns=('nome', 'banco', 'status'), show='headings', selectmode='browse')
        for chave, titulo in (('nome', 'Identificação'), ('banco', 'Banco'), ('status', 'Situação')):
            alinhamento = 'center' if chave == 'status' else 'w'
            self.tabela.heading(chave, text=titulo, anchor=alinhamento)
            self.tabela.column(chave, width=340 if chave=='status' else 240, anchor=alinhamento)
        self.situacoes_labels={}
        self.incompletas=set()
        self.situacoes_pendentes=False
        self.tabela.bind('<Configure>',lambda _:self.agendar_situacoes())
        self.tabela.bind('<<TreeviewSelect>>',lambda _:self.agendar_situacoes())
        self.tabela.configure(yscrollcommand=lambda *_:self.agendar_situacoes(),xscrollcommand=lambda *_:self.agendar_situacoes())
        self.tabela.pack(fill='both', expand=True)
        habilitar_selecao(self.tabela,abrir=self.editar,excluir=self.remover)
        self.tabela.bind('<Button-3>', self.menu_contexto)
        self.tabela.bind('<Double-1>', lambda _: self.editar())
        ttk.Label(corpo, text='Contas desativadas permanecem no histórico e podem ser reativadas.').pack(side='bottom',pady=(12,0),before=self.tabela)
        self.atualizar()
        centralizar(self.tela, 960, 520)
        self.tela.deiconify()

    def atualizar(self):
        for w in self.situacoes_labels.values():w.destroy()
        self.situacoes_labels.clear()
        self.incompletas.clear()
        self.tabela.delete(*self.tabela.get_children())
        for conta in self.banco.contas():
            status = 'Ativa' if conta['ativa'] else 'Desativada'
            incompleta = any(not conta[c] for c in ('nome', 'cpf', 'endereco', 'numero_endereco', 'cidade', 'estado', 'banco', 'numero', 'pix'))
            if not incompleta:
                try:
                    validar_cpf(conta['cpf'])
                except ValueError:
                    incompleta = True
            if incompleta:
                self.incompletas.add(str(conta['id']))
                status = '⚠ Completar cadastro' + (' — Desativada' if not conta['ativa'] else '')
            self.tabela.insert('', 'end', iid=str(conta['id']), values=(conta['identificacao'], conta['banco'], status),
                               tags=('incompleta',) if incompleta else ())

        self.agendar_situacoes()

    def agendar_situacoes(self):
        if not self.situacoes_pendentes:
            self.situacoes_pendentes=True
            self.tela.after_idle(self.atualizar_situacoes)

    def atualizar_situacoes(self):
        self.situacoes_pendentes=False
        if not self.tabela.winfo_exists():return
        c=cores()
        for linha in self.tabela.get_children():
            caixa=self.tabela.bbox(linha,'status')
            if not caixa:
                if linha in self.situacoes_labels:self.situacoes_labels[linha].place_forget()
                continue
            if linha not in self.situacoes_labels:
                rotulo=ttk.Label(self.tabela,text=self.tabela.set(linha,'status'),anchor='center',
                    style='ContaIncompleta.TLabel' if linha in self.incompletas else 'ContaSituacao.TLabel')
                rotulo.bind('<Button-1>',lambda e,i=linha:self.pressionar_situacao(e,i))
                rotulo.bind('<B1-Motion>',lambda e:arrastar(self.tabela,e.y_root-self.tabela.winfo_rooty()))
                rotulo.bind('<Double-1>',lambda _:self.editar())
                rotulo.bind('<Button-3>',lambda e,i=linha:self.menu_contexto(e,i))
                self.situacoes_labels[linha]=rotulo
            rotulo=self.situacoes_labels[linha]
            rotulo.configure(background=c['selecao'] if linha in self.tabela.selection() else c['campo'])
            x,y,largura,altura=caixa
            rotulo.place(x=x+1,y=y+1,width=max(1,largura-2),height=max(1,altura-2))

    def pressionar_situacao(self,evento,linha):
        pressionar_linha(self.tabela,linha,evento.state)
        return 'break'

    def menu_contexto(self, evento, linha=None):
        linha = linha or self.tabela.identify_row(evento.y)
        menu = novo_menu(self.tabela)
        if linha:
            if linha not in self.tabela.selection():
                self.tabela.selection_set(linha)
            unica = len(self.tabela.selection()) == 1
            conta = self.banco.obter_conta(int(linha))
            menu.add_command(label='Editar', command=self.editar,state='normal' if unica else 'disabled')
            menu.add_command(label='Desativar' if conta['ativa'] else 'Reativar', command=self.alterar_status,state='normal' if unica else 'disabled')
            menu.add_command(label='Remover', command=self.remover)
            menu.add_command(label='Copiar', command=lambda: copiar_texto(self.tabela, '\n\n'.join(dados_para_copiar(dict(self.banco.obter_conta(int(i)))) for i in self.tabela.selection())))
            menu.add_separator()
        menu.add_command(label='Cadastrar nova conta', command=self.formulario)
        return mostrar_menu(menu, evento)

    def selecionada(self):
        itens = self.tabela.selection()
        if not itens:
            messagebox.showinfo('Contas de recebimento', 'Selecione uma conta na lista.', parent=self.tela)
            return None
        if len(itens) != 1:
            messagebox.showinfo('Contas de recebimento','Selecione apenas uma conta para esta ação.',parent=self.tela)
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

    def remover(self):
        selecao = self.tabela.selection()
        if not selecao:
            messagebox.showinfo('Remover contas','Selecione uma ou mais contas.',parent=self.tela)
            return
        if not messagebox.askyesno('Remover contas',f'Remover permanentemente {len(selecao)} conta(s)?\n\n'
            'As entradas das operações e os dados bancários já guardados nelas continuarão existentes.',parent=self.tela,icon='warning',default='no'):
            return
        try:
            self.banco.remover_contas(selecao)
        except ValueError as erro:
            messagebox.showinfo('Preservar histórico',str(erro),parent=self.tela)
            return
        except sqlite3.Error:
            messagebox.showerror('Remover contas','Não foi possível remover as contas.',parent=self.tela)
            return
        self.atualizar()

    def formulario(self, identificador=None):
        conta = self.banco.obter_conta(identificador) if identificador else None
        tela = tk.Toplevel(self.tela)
        tela.withdraw()
        tela.title('Editar conta' if conta else 'Cadastrar nova conta')
        tela.configure(bg=cores()['fundo'])
        tela.resizable(False, False)
        tela.transient(self.tela)
        cabecalho = ttk.Frame(tela,padding=(24,16,24,0))
        cabecalho.pack(fill='x')
        ttk.Label(cabecalho,text='Editar conta' if conta else 'Nova conta',style='Titulo.TLabel').pack(anchor='w')
        area = AreaRolavel(tela)
        area.pack(fill='both',expand=True)
        quadro = area.conteudo
        campos = {}
        definicoes = (('identificacao', 'Identificação (ex.: Vitor)'), ('nome', 'Nome completo'),
                      ('cpf', 'CPF'), ('endereco', 'Endereço'), ('numero_endereco', 'Número'),
                      ('cidade', 'Cidade'), ('estado', 'Estado (UF)'), ('banco', 'Nome do banco'),
                      ('agencia', 'Agência'), ('numero', 'Conta bancária'), ('pix', 'Chave Pix'))
        for linha, (chave, titulo) in enumerate(definicoes):
            ttk.Label(quadro, text=titulo).grid(row=linha, column=0, sticky='w', padx=(0, 16), pady=6)
            campos[chave] = tk.StringVar(value=(conta[chave] or '') if conta else '')
            if chave == 'estado':
                entrada = ttk.Combobox(quadro, textvariable=campos[chave], values=ESTADOS, state='readonly', height=12, width=37)
            else:
                entrada = ttk.Entry(quadro, textvariable=campos[chave], width=40)
            entrada.grid(row=linha, column=1, sticky='ew', pady=6)
            if chave == 'cpf':
                aplicar_cpf(entrada, campos[chave])
            elif chave in ('identificacao', 'nome', 'endereco', 'cidade', 'banco'):
                aplicar_formato(entrada, campos[chave], str.title if chave in ('nome', 'endereco', 'cidade') else capitalizar_inicio)
        ttk.Label(quadro, text='Alterações não modificam os dados de recebimento guardados nas RPVs antigas.',
                  wraplength=600).grid(row=11, column=0, columnspan=2, pady=12)

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

        ttk.Separator(tela).pack(fill='x',padx=24)
        botoes = ttk.Frame(tela,padding=(24,8,24,12))
        botoes.pack(fill='x')
        ttk.Button(botoes, text='Cancelar', command=tela.destroy).pack(side='left',expand=True,fill='x',padx=(0,8))
        ttk.Button(botoes, text='Salvar conta', style='Salvar.TButton', command=salvar).pack(side='left',expand=True,fill='x')
        centralizar(tela)
        tela.deiconify()
        tela.grab_set()
        tela.bind('<Escape>', lambda _: tela.destroy())
