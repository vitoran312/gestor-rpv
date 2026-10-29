"""Página e formulário para administrar contas de recebimento."""
from tema import cores
from movimento import surgir
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

from componentes import centralizar, AreaRolavel, AvisoVazio, fechar_com_confirmacao, marcar_erro, notificar
from visual import px
from selecao import arrastar, habilitar_selecao, preparar_realce, pressionar_linha
from dados import ESTADOS, TITULOS_CONTA, validar_cpf
from interacao import aplicar_formato, aplicar_cpf, capitalizar_inicio, formatar_cpf, novo_menu, mostrar_menu, copiar_texto
from mensagens import descrever_erro
import demonstracao


# Palavras das mensagens de Banco.salvar_conta que apontam um campo além do próprio título dele.
PALAVRAS_DO_CAMPO = {'cpf': 'cpf', 'estado': 'estado', 'pix': 'pix', 'identificação': 'identificacao',
                     'conta bancária': 'numero', 'banco': 'banco'}


def campos_da_mensagem(mensagem):
    """Campos citados numa mensagem de erro da conta (para contorná-los em vermelho)."""
    texto = mensagem.casefold()
    chaves = {chave for chave, titulo in TITULOS_CONTA.items() if titulo.casefold() in texto}
    chaves |= {chave for palavra, chave in PALAVRAS_DO_CAMPO.items() if palavra in texto}
    return [chave for chave in TITULOS_CONTA if chave in chaves]


def dados_para_copiar(conta):
    # Fora do formulário, alguns rótulos precisam dizer mais (o "Número" sozinho seria ambíguo no texto copiado).
    rotulos = dict(TITULOS_CONTA, numero_endereco='Número do endereço', estado='Estado', banco='Banco', numero='Conta')
    linhas = []
    for chave, titulo in rotulos.items():
        if chave == 'identificacao':
            continue  # O apelido da conta não é um dado bancário.
        valor = conta.get(chave)
        if chave == 'cpf' and valor:
            valor = formatar_cpf(valor)
        linhas.append(f'{titulo}: {valor or "Não informado"}')
    return '\n'.join(linhas)


class JanelaContas:
    def __init__(self, aplicativo):
        self.app = aplicativo
        self.banco = aplicativo.banco
        self.tela = ttk.Frame(aplicativo.janela)
        corpo = ttk.Frame(self.tela, padding=(20, 16, 20, 20))
        corpo.pack(fill='both', expand=True)
        aplicativo.cabecalho_pagina(corpo, 'Contas de recebimento', 'Dados bancários usados nas suas operações.')
        # Poucas contas não precisam da tela toda: o conteúdo fica num cartão centralizado na área livre.
        self.area = ttk.Frame(corpo)
        self.area.pack(fill='both', expand=True)
        self.cartao = ttk.Frame(self.area, style='Cartao.TFrame', padding=24)
        self.area.bind('<Configure>', self.posicionar_cartao)
        barra = ttk.Frame(self.cartao, style='Superficie.TFrame')
        barra.pack(fill='x', pady=(0, 15))
        ttk.Button(barra, text='Cadastrar nova conta', style='Inicio.Principal.TButton', command=self.formulario).pack(side='left')
        ttk.Button(barra, text='Ver / Editar', style='Inicio.TButton', command=self.editar).pack(side='left', padx=8)
        ttk.Button(barra, text='Desativar / Reativar', style='Inicio.TButton', command=self.alterar_status).pack(side='left')
        ttk.Button(barra, text='Remover', style='Inicio.TButton', command=self.remover).pack(side='left', padx=8)
        self.tabela = ttk.Treeview(self.cartao, style='Contas.Treeview', columns=('nome', 'banco', 'status'), show='headings', selectmode='browse')
        preparar_realce(self.tabela)
        self.vazio = AvisoVazio(self.tabela)
        for chave, titulo, largura in (('nome', 'Identificação', 200), ('banco', 'Banco', 170), ('status', 'Situação', 220)):
            alinhamento = 'center' if chave == 'status' else 'w'
            self.tabela.heading(chave, text=titulo, anchor=alinhamento)
            self.tabela.column(chave, width=largura, minwidth=110, anchor=alinhamento)
        self.situacoes_labels = {}
        self.incompletas = set()
        self.situacoes_pendentes = False
        self.tabela.bind('<Configure>', lambda _: self.agendar_situacoes())
        self.tabela.bind('<<TreeviewSelect>>', lambda _: self.agendar_situacoes())
        self.tabela.configure(yscrollcommand=lambda *_: self.agendar_situacoes(), xscrollcommand=lambda *_: self.agendar_situacoes())
        self.tabela.pack(fill='both', expand=True)
        habilitar_selecao(self.tabela, abrir=self.editar, excluir=self.remover)
        self.tabela.bind('<Button-3>', self.menu_contexto)
        self.tabela.bind('<Double-1>', lambda _: self.editar())
        ttk.Label(self.cartao, text='Contas desativadas permanecem no histórico e podem ser reativadas.',
                  style='CartaoTexto.TLabel').pack(side='bottom', anchor='w', pady=(12, 0), before=self.tabela)
        self.atualizar()
        aplicativo.abrir_pagina(self.tela, 'Contas de recebimento')

    def posicionar_cartao(self, evento):
        """Metade da largura e pouco mais da metade da altura, sem ficar menor que os botões ou maior que a área."""
        largura = min(evento.width, max(px(self.cartao, 660), evento.width // 2))
        altura = min(evento.height, max(px(self.cartao, 380), int(evento.height * 0.6)))
        self.cartao.place(relx=0.5, rely=0.45, anchor='center', width=largura, height=altura)

    def atualizar(self):
        for w in self.situacoes_labels.values(): w.destroy()
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
        if self.tabela.get_children():
            self.vazio.ocultar()
        else:
            self.vazio.mostrar('Nenhuma conta cadastrada', 'Cadastre a conta onde você recebe os valores das RPVs.')

        self.agendar_situacoes()

    def agendar_situacoes(self):
        if not self.situacoes_pendentes:
            self.situacoes_pendentes = True
            self.tela.after_idle(self.atualizar_situacoes)

    def atualizar_situacoes(self):
        self.situacoes_pendentes = False
        if not self.tabela.winfo_exists(): return
        c = cores()
        for linha in self.tabela.get_children():
            caixa = self.tabela.bbox(linha, 'status')
            if not caixa:
                if linha in self.situacoes_labels: self.situacoes_labels[linha].place_forget()
                continue
            if linha not in self.situacoes_labels:
                rotulo = ttk.Label(self.tabela, text=self.tabela.set(linha, 'status'), anchor='center',
                    style='ContaIncompleta.TLabel' if linha in self.incompletas else 'ContaSituacao.TLabel')
                rotulo.bind('<Button-1>', lambda e, i=linha: self.pressionar_situacao(e, i))
                rotulo.bind('<B1-Motion>', lambda e: arrastar(self.tabela, e.y_root - self.tabela.winfo_rooty()))
                rotulo.bind('<Double-1>', lambda _: self.editar())
                rotulo.bind('<Button-3>', lambda e, i=linha: self.menu_contexto(e, i))
                self.situacoes_labels[linha] = rotulo
            rotulo = self.situacoes_labels[linha]
            rotulo.configure(background=c['selecao'] if linha in self.tabela.selection() else c['campo'])
            x, y, largura, altura = caixa
            rotulo.place(x=x + 1, y=y + 1, width=max(1, largura - 2), height=max(1, altura - 2))

    def pressionar_situacao(self, evento, linha):
        pressionar_linha(self.tabela, linha, evento.state)
        return 'break'

    def menu_contexto(self, evento, linha=None):
        linha = linha or self.tabela.identify_row(evento.y)
        menu = novo_menu(self.tabela)
        if linha:
            if linha not in self.tabela.selection():
                self.tabela.selection_set(linha)
            unica = len(self.tabela.selection()) == 1
            conta = self.banco.obter_conta(int(linha))
            menu.add_command(label='Editar', command=self.editar, state='normal' if unica else 'disabled')
            menu.add_command(label='Desativar' if conta['ativa'] else 'Reativar', command=self.alterar_status, state='normal' if unica else 'disabled')
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
            messagebox.showinfo('Contas de recebimento', 'Selecione apenas uma conta para esta ação.', parent=self.tela)
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
        notificar(self.app.janela, f"Conta {conta['identificacao']} {'desativada' if conta['ativa'] else 'reativada'}.")

    def remover(self):
        selecao = self.tabela.selection()
        if not selecao:
            messagebox.showinfo('Remover contas', 'Selecione uma ou mais contas.', parent=self.tela)
            return
        try:
            em_uso = self.banco.operacoes_da_conta(selecao)
        except sqlite3.Error:
            em_uso = 0
        aviso = ('As entradas das operações e os dados bancários já guardados nelas continuarão existentes.' if not em_uso else
                 f'{em_uso} operação(ões) usam esta(s) conta(s). Elas guardam os dados bancários, mas a conta não '
                 'poderá ser escolhida de novo nem reativada. Se for só parar de usar, prefira Desativar.')
        if not messagebox.askyesno('Remover contas', f'Remover permanentemente {len(selecao)} conta(s)?\n\n' + aviso,
                                   parent=self.tela, icon='warning', default='no'):
            return
        try:
            self.banco.remover_contas(selecao)
        except ValueError as erro:
            messagebox.showinfo('Preservar histórico', descrever_erro(erro), parent=self.tela)
            return
        except sqlite3.Error:
            messagebox.showerror('Remover contas', 'Não foi possível remover as contas.', parent=self.tela)
            return
        self.atualizar()
        notificar(self.app.janela, 'Conta removida.' if len(selecao) == 1 else f'{len(selecao)} contas removidas.')

    def formulario(self, identificador=None):
        conta = self.banco.obter_conta(identificador) if identificador else None
        tela = tk.Toplevel(self.tela)
        tela.withdraw()
        tela.title('Editar conta' if conta else 'Cadastrar nova conta')
        tela.configure(bg=cores()['fundo'])
        tela.resizable(False, False)
        tela.transient(self.tela)
        cabecalho = ttk.Frame(tela, padding=(24, 16, 24, 0))
        cabecalho.pack(fill='x')
        ttk.Label(cabecalho, text='Editar conta' if conta else 'Nova conta', style='Titulo.TLabel').pack(anchor='w')
        area = AreaRolavel(tela)
        area.pack(fill='both', expand=True)
        quadro = area.conteudo
        campos, entradas = {}, {}
        for linha, (chave, titulo) in enumerate(TITULOS_CONTA.items()):
            if chave == 'identificacao':
                titulo += ' (ex.: Conta principal)'
            ttk.Label(quadro, text=titulo).grid(row=linha, column=0, sticky='w', padx=(0, 16), pady=6)
            campos[chave] = tk.StringVar(value=(conta[chave] or '') if conta else '')
            if chave == 'estado':
                entrada = ttk.Combobox(quadro, textvariable=campos[chave], values=ESTADOS, state='readonly', height=12, width=37)
            else:
                entrada = ttk.Entry(quadro, textvariable=campos[chave], width=40)
            entrada.grid(row=linha, column=1, sticky='ew', pady=6)
            entradas[chave] = entrada
            if chave == 'cpf':
                aplicar_cpf(entrada, campos[chave])
            elif chave in ('identificacao', 'nome', 'endereco', 'cidade', 'banco'):
                aplicar_formato(entrada, campos[chave], str.title if chave in ('nome', 'endereco', 'cidade') else capitalizar_inicio)
        ttk.Label(quadro, text='Alterações não modificam os dados de recebimento guardados nas RPVs antigas.',
                  wraplength=px(quadro, 600)).grid(row=len(TITULOS_CONTA), column=0, columnspan=2, pady=12)

        def salvar():
            try:
                salva = self.banco.salvar_conta({k: v.get() for k, v in campos.items()}, identificador)
                demonstracao.adotar(self.banco, conta=salva)
            except ValueError as erro:
                marcados = campos_da_mensagem(str(erro))
                for chave in marcados:
                    marcar_erro(entradas[chave], campos[chave])
                messagebox.showerror('Confira a conta', descrever_erro(erro), parent=tela)
                if marcados and tela.winfo_exists():
                    entradas[marcados[0]].focus_set()
                return
            except sqlite3.IntegrityError:
                messagebox.showerror('Confira a conta', 'Já existe uma conta com esses dados únicos.', parent=tela)
                return
            except sqlite3.Error as erro:
                messagebox.showerror('Contas de recebimento', 'Não foi possível salvar a conta. ' + descrever_erro(erro), parent=tela)
                return
            self.atualizar()
            tela.destroy()
            notificar(self.app.janela, 'Alterações da conta salvas.' if identificador else 'Conta cadastrada.')

        ttk.Separator(tela).pack(fill='x', padx=24)
        botoes = ttk.Frame(tela, padding=(24, 8, 24, 12))
        botoes.pack(fill='x')
        fechar = fechar_com_confirmacao(tela, lambda: tuple(variavel.get() for variavel in campos.values()),
                                        'Os dados digitados')
        ttk.Button(botoes, text='Cancelar', command=fechar).pack(side='left', expand=True, fill='x', padx=(0, 8))
        ttk.Button(botoes, text='Salvar conta', style='Salvar.TButton', command=salvar).pack(side='left', expand=True, fill='x')
        centralizar(tela)
        surgir(tela)
        tela.grab_set()
