"""Página e formulário para administrar contas de recebimento."""
from tema import cores
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

from componentes import centralizar, AreaRolavel
from selecao import habilitar_selecao, pressionar_linha, arrastar
from dados import validar_cpf, ESTADOS, moeda, data_br, situacao
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
        self.tela = ttk.Frame(aplicativo.janela)
        corpo = ttk.Frame(self.tela, padding=(20, 16, 20, 20))
        corpo.pack(fill='both', expand=True)
        aplicativo.cabecalho_pagina(corpo, 'Contas de recebimento', 'Dados bancários usados nas suas operações.')
        barra = ttk.Frame(corpo)
        barra.pack(fill='x', pady=(0, 14))
        self.texto_resumo = tk.StringVar()
        ttk.Label(barra, textvariable=self.texto_resumo, style='ContasResumo.TLabel').pack(side='left')
        ttk.Button(barra, text='Cadastrar nova conta', style='Principal.TButton', command=self.formulario).pack(side='right')
        # Lista à esquerda e detalhes da conta selecionada à direita, com as operações que a usam.
        area = ttk.Frame(corpo)
        area.pack(fill='both', expand=True)
        area.columnconfigure(0, weight=2, minsize=440)
        area.columnconfigure(1, weight=3)
        area.rowconfigure(0, weight=1)
        lista = ttk.Frame(area)
        lista.grid(row=0, column=0, sticky='nsew', padx=(0, 20))
        self.tabela = ttk.Treeview(lista, style='Contas.Treeview', columns=('nome', 'banco', 'status'), show='headings', selectmode='browse')
        for chave, titulo, largura in (('nome', 'Identificação', 190), ('banco', 'Banco', 150), ('status', 'Situação', 200)):
            alinhamento = 'center' if chave == 'status' else 'w'
            self.tabela.heading(chave, text=titulo, anchor=alinhamento)
            self.tabela.column(chave, width=largura, minwidth=110, anchor=alinhamento)
        self.tabela.pack(fill='both', expand=True)
        ttk.Label(lista, text='Contas desativadas permanecem no histórico e podem ser reativadas.',
                  style='Discreto.TLabel', wraplength=440).pack(anchor='w', pady=(10, 0))
        self.detalhe = ttk.Frame(area, style='Cartao.TFrame', padding=(28, 24))
        self.detalhe.grid(row=0, column=1, sticky='nsew')
        self.situacoes_labels={}
        self.incompletas=set()
        self.situacoes_pendentes=False
        self.tabela.bind('<Configure>',lambda _:self.agendar_situacoes())
        self.tabela.bind('<<TreeviewSelect>>',lambda _:(self.agendar_situacoes(),self.mostrar_detalhe()))
        self.tabela.configure(yscrollcommand=lambda *_:self.agendar_situacoes(),xscrollcommand=lambda *_:self.agendar_situacoes())
        habilitar_selecao(self.tabela,abrir=self.editar,excluir=self.remover)
        self.tabela.bind('<Button-3>', self.menu_contexto)
        self.tabela.bind('<Double-1>', lambda _: self.editar())
        self.atualizar()
        aplicativo.abrir_pagina(self.tela, 'Contas de recebimento')

    def atualizar(self):
        selecionadas = self.tabela.selection()
        for w in self.situacoes_labels.values():w.destroy()
        self.situacoes_labels.clear()
        self.incompletas.clear()
        self.tabela.delete(*self.tabela.get_children())
        contas = self.banco.contas()
        for conta in contas:
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
        ativas = sum(1 for conta in contas if conta['ativa'])
        partes = [f"{len(contas)} conta{'s' if len(contas) != 1 else ''}", f"{ativas} ativa{'s' if ativas != 1 else ''}"]
        if self.incompletas:
            partes.append(f"{len(self.incompletas)} a completar")
        self.texto_resumo.set(' · '.join(partes) if contas else 'Nenhuma conta cadastrada.')
        # Mantém a conta que estava selecionada; sem ela, mostra a primeira para o painel não ficar vazio.
        disponiveis = self.tabela.get_children()
        manter = [i for i in selecionadas if i in disponiveis]
        if manter or disponiveis:
            self.tabela.selection_set(manter or disponiveis[0])
            self.tabela.focus(manter[0] if manter else disponiveis[0])
        self.mostrar_detalhe()
        self.agendar_situacoes()

    def mostrar_detalhe(self):
        for filho in self.detalhe.winfo_children():
            filho.destroy()
        selecao = self.tabela.selection()
        if len(selecao) != 1:
            texto = ('Cadastre a primeira conta para receber suas operações.' if not self.tabela.get_children()
                     else 'Selecione uma conta na lista para ver os detalhes.')
            ttk.Label(self.detalhe, text=texto, style='CartaoTexto.TLabel').pack(anchor='w')
            return
        conta = self.banco.obter_conta(int(selecao[0]))
        if conta is None:
            return
        c = dict(conta)
        topo = ttk.Frame(self.detalhe, style='Superficie.TFrame')
        topo.pack(fill='x')
        ttk.Label(topo, text=c['identificacao'], style='DetalheTitulo.TLabel').pack(side='left')
        if selecao[0] in self.incompletas:
            selo, estilo = '⚠ Completar cadastro', 'SeloIncompleta.TLabel'
        elif c['ativa']:
            selo, estilo = '● Ativa', 'SeloAtiva.TLabel'
        else:
            selo, estilo = '● Desativada', 'SeloDesativada.TLabel'
        ttk.Label(topo, text=selo, style=estilo).pack(side='right')
        ttk.Label(self.detalhe, text=c['nome'] or 'Nome não informado', style='CartaoTexto.TLabel').pack(anchor='w', pady=(2, 18))

        campos = ttk.Frame(self.detalhe, style='Superficie.TFrame')
        campos.pack(fill='x')
        endereco = ', '.join(p for p in (c['endereco'], c['numero_endereco']) if p)
        local = '/'.join(p for p in (c['cidade'], c['estado']) if p)
        for indice, (rotulo, valor) in enumerate((
                ('CPF', formatar_cpf(c['cpf']) if c['cpf'] else ''), ('Chave Pix', c['pix']),
                ('Banco', c['banco']), ('Agência', c['agencia']),
                ('Conta', c['numero']), ('Endereço', ' — '.join(p for p in (endereco, local) if p)))):
            celula = ttk.Frame(campos, style='Superficie.TFrame')
            celula.grid(row=indice // 2, column=indice % 2, sticky='nw', padx=(0, 24), pady=(0, 14))
            ttk.Label(celula, text=rotulo, style='DetalheRotulo.TLabel').pack(anchor='w')
            ttk.Label(celula, text=valor or 'Não informado', style='DetalheValor.TLabel', wraplength=320).pack(anchor='w')
        campos.columnconfigure((0, 1), weight=1, uniform='campos')

        botoes = ttk.Frame(self.detalhe, style='Superficie.TFrame')
        botoes.pack(fill='x', pady=(4, 20))
        ttk.Button(botoes, text='Editar', style='Inicio.Principal.TButton', command=self.editar).pack(side='left')
        copiar = ttk.Button(botoes, text='Copiar dados', style='Inicio.TButton')
        copiar.configure(command=lambda: self.copiar_dados(c, copiar))
        copiar.pack(side='left', padx=8)
        ttk.Button(botoes, text='Desativar' if c['ativa'] else 'Reativar', style='Inicio.TButton',
                   command=self.alterar_status).pack(side='left')
        ttk.Button(botoes, text='Remover', style='Inicio.TButton', command=self.remover).pack(side='right')

        ttk.Separator(self.detalhe).pack(fill='x', pady=(0, 16))
        # O que pede atenção vem primeiro: atrasadas, depois pendentes pela previsão; recebidas por último.
        prioridade = {'atrasada': 0, 'pendente': 1, 'recebida': 2}
        operacoes = sorted((r for r in self.banco.listar() if r['conta_id'] == c['id']),
                           key=lambda r: (prioridade[situacao(r)], r['previsao_atual']))
        a_receber = sum(r['previsto'] for r in operacoes if not r['recebimento'])
        recebido = sum(r['previsto'] for r in operacoes if r['recebimento'])
        ttk.Label(self.detalhe, text=f'Operações nesta conta ({len(operacoes)})', style='DetalheSecao.TLabel').pack(anchor='w')
        ttk.Label(self.detalhe, style='CartaoTexto.TLabel',
                  text=f'R$ {moeda(a_receber)} a receber · R$ {moeda(recebido)} já recebidos').pack(anchor='w', pady=(2, 10))
        if not operacoes:
            ttk.Label(self.detalhe, text='Nenhuma operação usa esta conta.', style='CartaoTexto.TLabel').pack(anchor='w')
            return
        quadro = ttk.Frame(self.detalhe, style='Superficie.TFrame')
        quadro.pack(fill='both', expand=True)
        lista = ttk.Treeview(quadro, style='ContaOperacoes.Treeview', columns=('nome', 'total', 'previsao', 'situacao'),
                             show='headings', selectmode='none', height=6)
        for chave, titulo, largura, alinhamento in (('nome', 'Titular', 200, 'w'), ('total', 'Valor Total RPV', 130, 'e'),
                                                     ('previsao', 'Previsão atual', 120, 'center'), ('situacao', 'Situação', 110, 'center')):
            lista.heading(chave, text=titulo, anchor=alinhamento)
            lista.column(chave, width=largura, minwidth=80, anchor=alinhamento)
        lista.tag_configure('atrasada', foreground=cores()['vermelho'], background=cores()['atraso'])
        lista.tag_configure('recebida', foreground=cores()['secundario'])
        rotulos = {'pendente': 'Pendente', 'atrasada': 'Atrasada', 'recebida': 'Recebida'}
        for r in operacoes:
            estado = situacao(r)
            lista.insert('', 'end', values=(r['nome'], 'R$ ' + moeda(r['previsto']), data_br(r['previsao_atual']),
                                            rotulos[estado]), tags=(estado,))
        rolagem = ttk.Scrollbar(quadro, orient='vertical', command=lista.yview)
        lista.configure(yscrollcommand=rolagem.set)
        lista.pack(side='left', fill='both', expand=True)
        rolagem.pack(side='right', fill='y')

    def copiar_dados(self, conta, botao):
        copiar_texto(self.tabela, dados_para_copiar(conta))
        botao.configure(text='Copiado ✓')
        botao.after(1500, lambda: botao.winfo_exists() and botao.configure(text='Copiar dados'))

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
