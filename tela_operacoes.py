"""Tela Minhas operações: tabela, resumo, ações por linha e lixeira."""
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk, font as tkfont

from dados import data_br, reais, situacao
from grafico import JanelaGrafico
import demonstracao
from componentes import centralizar
from visual import px
from tema import cores
from ordenacao import ordenar
from selecao import habilitar_selecao, pressionar_linha, arrastar
from interacao import aplicar_formato, capitalizar_inicio, novo_menu, mostrar_menu, copiar_texto
from mensagens import descrever_erro


# Colunas de Minhas operações: título e alinhamento. Texto à esquerda, valores à direita e datas
# centralizadas, como em uma planilha. A ordem aqui é a ordem na tela e nos valores de cada linha.
COLUNAS_OPERACOES = {
    'nome': ('Titular original', 'w'), 'data': ('Data de Aquisição', 'center'),
    'custo': ('Valor de aquisição', 'e'), 'comissao': ('Comissão', 'e'), 'previsto': ('Valor Total RPV', 'e'),
    'lucro': ('Lucro previsto', 'e'), 'conta': ('Conta de destino', 'w'), 'previsao': ('Previsão inicial', 'center'),
    'previsao_atual': ('Previsão atual', 'center'), 'recebido': ('Recebido', 'center'),
}


class OperacoesMixin:
    def criar_barra_historico(self):
        # A barra pertence à janela principal e só é exibida enquanto a página de operações está à frente.
        anterior = self.menus
        if anterior and anterior['barra'].winfo_exists():
            anterior['barra'].destroy()
        barra = novo_menu(self.janela)
        arquivo = novo_menu(barra)
        arquivo.add_command(label='Nova entrada', command=self.formulario)
        arquivo.add_command(label='Contas de recebimento', command=self.mostrar_contas)
        arquivo.add_separator()
        arquivo.add_command(label='Fazer backup', command=self.exportar_backup)
        arquivo.add_command(label='Backup automático…', command=self.configurar_backup_automatico)
        arquivo.add_command(label='Importar dados', command=self.importar_dados)
        arquivo.add_command(label='Exportar para Excel', command=self.exportar_excel)
        arquivo.add_command(label='Abrir pasta dos documentos', command=self.abrir_pasta_documentos)
        arquivo.add_separator()
        arquivo.add_command(label='Voltar ao início', command=lambda: self.historico.destroy())
        editar = novo_menu(barra)
        editar.add_command(label='Editar registro', command=self.abrir)
        editar.add_command(label='Excluir registro', command=self.excluir)
        exibir = novo_menu(barra)
        exibir.add_command(label='Gráfico mensal', command=self.mostrar_grafico)
        exibir.add_separator()
        exibir.add_radiobutton(label='Tema claro', variable=self.modo_tema, value='claro', command=self.configurar_tema)
        exibir.add_radiobutton(label='Tema escuro', variable=self.modo_tema, value='escuro', command=self.configurar_tema)
        ajuda = novo_menu(barra)
        ajuda.add_command(label='Sobre o Gestor de RPV',command=self.mostrar_sobre)
        barra.add_cascade(label='Arquivo', menu=arquivo)
        barra.add_cascade(label='Editar', menu=editar)
        barra.add_cascade(label='Exibir', menu=exibir)
        barra.add_command(label='Calculadora', command=self.abrir_calculadora)
        barra.add_cascade(label='Ajuda',menu=ajuda)
        self.menus = {'Arquivo': arquivo, 'Editar': editar, 'Exibir': exibir, 'Ajuda': ajuda, 'barra': barra}

    def apagar_demonstracao(self):
        if not messagebox.askyesno('Apagar dados de demonstração',
            'Apagar as operações e contas fictícias?\n\n'
            'O que você cadastrou continua salvo. Depois disso, o programa fica pronto para os seus dados.',
            parent=self.historico,default='no'):
            return
        try:
            demonstracao.remover(self.banco)
        except sqlite3.Error:
            messagebox.showerror('Apagar dados de demonstração','Não foi possível apagar os dados.',parent=self.historico)
            return
        self.atualizar()
        if self.janela_contas is not None and self.janela_contas.tela.winfo_exists():
            self.janela_contas.atualizar()

    def mostrar_grafico(self):
        # Reabre com os dados atuais; se o gráfico já estiver aberto, ele é substituído na mesma posição.
        if self.grafico_mensal is not None and self.grafico_mensal.tela.winfo_exists():
            self.trazer_pagina(self.grafico_mensal.tela)
            self.grafico_mensal.tela.destroy()
        self.grafico_mensal = JanelaGrafico(self)

    def mostrar_historico(self):
        if self.historico is not None and self.historico.winfo_exists():
            self.trazer_pagina(self.historico)
            return
        self.historico = ttk.Frame(self.janela)
        self.criar_barra_historico()
        corpo = ttk.Frame(self.historico, padding=(20,16,20,20))
        corpo.pack(fill='both', expand=True)
        self.cabecalho_pagina(corpo, 'Minhas operações', 'Acompanhe cada operação, do cadastro ao recebimento.')
        self.aviso_demonstracao = ttk.Frame(corpo,style='Demonstracao.TFrame',padding=(16,10))
        ttk.Label(self.aviso_demonstracao,style='Demonstracao.TLabel',
                  text='Você está vendo dados de demonstração, com nomes e valores fictícios.').pack(side='left')
        ttk.Button(self.aviso_demonstracao,text='Apagar dados de demonstração',style='Demonstracao.TButton',
                   command=self.apagar_demonstracao).pack(side='right')
        entrada_busca = self.criar_busca_e_filtros(corpo)
        quadro = self.criar_tabela(corpo)
        self.criar_rodape(corpo, quadro)
        # Atalhos ficam na janela principal e só agem com a página de operações à frente.
        for sequencia, acao in (('<Control-f>', entrada_busca.focus_set), ('<Control-n>', self.formulario),
                                ('<F5>', self.atualizar)):
            self.janela.bind(sequencia, lambda _, a=acao: a() if self.pagina_atual() is self.historico else None)
        self.atualizar()
        self.abrir_pagina(self.historico, 'Minhas operações')

    def criar_busca_e_filtros(self, corpo):
        barra = self.barra_busca = ttk.Frame(corpo)
        barra.pack(fill='x', pady=(0, 12))
        ttk.Label(barra, text='Buscar nome ou data:').pack(side='left', padx=(0, 6))
        self.busca = tk.StringVar()
        entrada_busca = ttk.Entry(barra, textvariable=self.busca)
        entrada_busca.pack(side='left', fill='x', expand=True)
        aplicar_formato(entrada_busca, self.busca, capitalizar_inicio)
        self.busca.trace_add('write', lambda *_: self.atualizar())
        filtros = ttk.Frame(corpo)
        filtros.pack(fill='x', pady=(0, 12))
        self.filtro = tk.StringVar(value='todas')
        self.botoes_filtro = {}
        for valor in ('todas', 'pendente', 'atrasada', 'recebida'):
            botao = ttk.Radiobutton(filtros, variable=self.filtro, value=valor, style='Filtro.TRadiobutton',
                                    command=self.atualizar, takefocus=False)
            botao.pack(side='left', padx=(0, 8))
            self.botoes_filtro[valor] = botao
        return entrada_busca

    def criar_tabela(self, corpo):
        quadro = ttk.Frame(corpo)
        quadro.pack(fill='both', expand=True)
        self.tabela = ttk.Treeview(quadro, style='Operacoes.Treeview', columns=tuple(COLUNAS_OPERACOES),
                                   show='headings', selectmode='browse')
        self.ordenacao = None
        self.titulos_colunas = {coluna: titulo for coluna, (titulo, _alinhamento) in COLUNAS_OPERACOES.items()}
        for coluna, (titulo, alinhamento) in COLUNAS_OPERACOES.items():
            self.tabela.heading(coluna, text=titulo, anchor=alinhamento, command=lambda c=coluna: self.ordenar_coluna(c))
            largura = max(px(self.janela,280 if coluna=='nome' else 160),tkfont.Font(font=(self.fonte,18)).measure(titulo)+px(self.janela,40))
            self.tabela.column(coluna,width=largura,minwidth=100,anchor=alinhamento)
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
        return quadro

    def criar_rodape(self, corpo, quadro):
        rodape = ttk.Frame(corpo)
        rodape.pack(side='bottom',fill='x',pady=(12,0),before=quadro)
        rodape.columnconfigure(0,weight=1)
        self.resumo = ttk.Frame(rodape)
        self.resumo.grid(row=0,column=0,sticky='ew')
        self.indicadores_resumo = {}
        self.cartoes_resumo = []
        for chave,titulo in (('registros','Registros'),('previsto','Lucro previsto'),
                             ('aberto','Capital investido em aberto'),('realizado','Lucro realizado')):
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
        self.botao_lixeira.grid(row=0,column=1,rowspan=3,sticky='se',padx=(16,0))
        self.texto_ultimo_backup=tk.StringVar()
        ttk.Label(rodape,textvariable=self.texto_ultimo_backup,style='Discreto.TLabel').grid(row=1,column=0,sticky='w',padx=6,pady=(8,0))
        aviso = ttk.Label(rodape,textvariable=self.texto_aviso_backup,style='BackupAviso.TLabel',cursor='hand2',wraplength=px(rodape,760))
        aviso.grid(row=2,column=0,sticky='w',padx=6)
        aviso.bind('<Button-1>',lambda _: self.exportar_backup())

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

    def colorir_linhas(self):
        """Cores das linhas no tema atual: alternada, atrasada (vermelha) e recebida (verde)."""
        c = cores()
        self.tabela.tag_configure('alternada', background=c['linha'])
        self.tabela.tag_configure('atrasada', foreground=c['vermelho'], background=c['atraso'])
        self.tabela.tag_configure('recebida', foreground=c['verde'], background=c['recebida'])

    def atualizar(self):
        if self.historico is None or not self.historico.winfo_exists():
            return
        self.atualizar_ultimo_backup()
        if demonstracao.ativa(self.banco):
            if not self.aviso_demonstracao.winfo_manager():
                self.aviso_demonstracao.pack(fill='x', pady=(0, 16), before=self.barra_busca)
        else:
            self.aviso_demonstracao.pack_forget()
        selecionados = self.tabela.selection()
        foco = self.tabela.focus()
        registros = self.banco.listar(self.busca.get().strip())
        if self.ordenacao:
            registros = ordenar(registros, *self.ordenacao)
        situacoes = {str(r['id']): situacao(r) for r in registros}
        totais = {valor: sum(s == valor for s in situacoes.values()) for valor in ('pendente', 'atrasada', 'recebida')}
        totais['todas'] = len(registros)
        for valor, titulo in (('todas', 'Todas'), ('pendente', 'Pendentes'), ('atrasada', 'Atrasadas'), ('recebida', 'Recebidas')):
            self.botoes_filtro[valor].configure(text=f'{titulo}  {totais[valor]}', style='FiltroAlerta.TRadiobutton'
                                                if valor == 'atrasada' and totais[valor] else 'Filtro.TRadiobutton')
        if self.filtro.get() != 'todas':
            registros = [r for r in registros if situacoes[str(r['id'])] == self.filtro.get()]
        self.atrasadas = {i for i, s in situacoes.items() if s == 'atrasada'}
        self.recebimentos = {str(r['id']): r['recebimento'] for r in registros}
        # Comparação em ISO, direto do banco: o texto exibido não precisa ser relido como data.
        self.adiadas = {str(r['id']) for r in registros if r['previsao_atual'] > r['previsao']}
        for widgets in self.acoes_linhas.values():
            for widget in widgets:
                widget.destroy()
        self.acoes_linhas.clear()
        self.tabela.delete(*self.tabela.get_children())
        self.colorir_linhas()
        for indice,r in enumerate(registros):
            # Linha atrasada inteira em vermelho e recebida inteira em verde; o tom alternado não se aplica a elas.
            etiquetas = (('atrasada',) if str(r['id']) in self.atrasadas else ('recebida',) if r['recebimento']
                         else ('alternada',) if indice%2 else ())
            self.tabela.insert('', 'end', iid=str(r['id']), tags=etiquetas, values=(
                r['nome'], data_br(r['aquisicao']), reais(r['custo']),
                reais(r['comissao'] or 0),
                reais(r['previsto']), reais(r['previsto'] - r['custo']),
                r['conta'], data_br(r['previsao']), data_br(r['previsao_atual']),
                ''))
        disponiveis = set(self.tabela.get_children())
        self.tabela.selection_set([i for i in selecionados if i in disponiveis])
        if foco in disponiveis:
            self.tabela.focus(foco)
        self.agendar_acoes()
        self.indicadores_resumo['registros'].set(str(len(registros)))
        self.indicadores_resumo['previsto'].set(reais(sum(r['previsto']-r['custo'] for r in registros)))
        self.indicadores_resumo['realizado'].set(reais(sum(r['previsto']-r['custo'] for r in registros if r['recebimento'])))
        self.indicadores_resumo['aberto'].set(reais(sum(r['custo'] for r in registros if not r['recebimento'])))
        # Com a lixeira aberta ao lado, o que acabou de ser excluído aparece nela na hora.
        if self.janela_lixeira is not None and self.janela_lixeira.winfo_exists():
            self.janela_lixeira.atualizar_lista()

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
                atrasada = linha in self.atrasadas
                adiada = linha in self.adiadas
                botao = ttk.Label(self.tabela, text=self.tabela.set(linha, 'previsao_atual'), anchor='center', cursor='hand2',
                                  style='PrevisaoAtrasada.TLabel' if atrasada else
                                  'PrevisaoRecebida.TLabel' if self.recebimentos[linha] else
                                  'PrevisaoAdiada.TLabel' if adiada else 'Previsao.TLabel')
                data_recebimento = self.recebimentos[linha]
                recebido = data_recebimento is not None
                estado = tk.BooleanVar(value=recebido)
                caixa = ttk.Checkbutton(self.tabela, variable=estado,
                    text=data_br(data_recebimento) if recebido else '',
                    style='Recebida.Recebido.TCheckbutton' if recebido else
                    'Atrasada.Operacoes.TCheckbutton' if atrasada else 'Operacoes.TCheckbutton',
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

    def texto_da_linha(self, linha):
        """Colunas da linha separadas por tabulação, com o recebimento por extenso (a célula fica vazia na tela)."""
        data = self.recebimentos.get(linha)
        return '\t'.join(data_br(data) if data else 'Não recebido' if coluna == 'recebido' else self.tabela.set(linha, coluna)
                         for coluna in self.tabela['columns'])

    def copiar_selecao(self):
        selecionados = set(self.tabela.selection())
        linhas = [self.texto_da_linha(linha) for linha in self.tabela.get_children() if linha in selecionados]
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
            messagebox.showerror('Lixeira',descrever_erro(erro),parent=self.historico)
            return
        self.atualizar()

    def desenhar_icone_lixeira(self):
        if self.icone_lixeira is None:
            self.icone_lixeira = tk.PhotoImage(master=self.janela,width=24,height=24)
        self.icone_lixeira.blank()
        cor = cores()['texto']
        for retangulo in ((4,5,20,7),(9,2,15,4),(6,8,8,21),(16,8,18,21),
                          (6,20,18,22),(10,9,11,18),(13,9,14,18)):
            self.icone_lixeira.put(cor,to=retangulo)

    def mostrar_lixeira(self):
        if self.janela_lixeira is not None and self.janela_lixeira.winfo_exists():
            self.janela_lixeira.atualizar_lista()
            self.janela_lixeira.deiconify()
            self.janela_lixeira.lift()
            self.janela_lixeira.focus_set()
            return
        tela = self.janela_lixeira = tk.Toplevel(self.historico)
        tela.withdraw()
        tela.title('Lixeira')
        tela.configure(bg=cores()['fundo'])
        tela.minsize(px(tela,620),px(tela,350))
        corpo = ttk.Frame(tela,padding=20)
        corpo.pack(fill='both',expand=True)
        corpo.rowconfigure(0,weight=1)
        corpo.columnconfigure(0,weight=1)
        tabela = ttk.Treeview(corpo,columns=('nome','data','removido'),show='headings')
        for chave,titulo in (('nome','Titular'),('data','Data de Aquisição'),('removido','Enviado à lixeira')):
            tabela.heading(chave,text=titulo)
            tabela.column(chave,width=px(tabela,220),anchor='center')
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
                messagebox.showerror('Lixeira',descrever_erro(erro),parent=tela)
                return
            atualizar()
            self.atualizar()

        def excluir_definitivamente():
            selecao=tabela.selection()
            if not selecao:
                messagebox.showinfo('Lixeira','Selecione as entradas que deseja excluir.',parent=tela)
                return
            if not messagebox.askyesno('Exclusão permanente',
                f'Excluir permanentemente {len(selecao)} entrada(s) e todos os seus documentos?\n\n'
                'Não será possível restaurar pela lixeira.',parent=tela,icon='warning',default='no'):
                return
            try:
                self.banco.excluir_permanentemente(selecao)
            except (OSError,sqlite3.Error,ValueError) as erro:
                messagebox.showerror('Exclusão permanente',descrever_erro(erro),parent=tela)
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
            menu.add_command(label='Excluir permanentemente',command=excluir_definitivamente)
            return mostrar_menu(menu,evento)

        tela.atualizar_lista = atualizar
        habilitar_selecao(tabela,abrir=restaurar,excluir=excluir_definitivamente)
        tabela.bind('<Button-3>',contexto)
        rodape = ttk.Frame(corpo,padding=(0,12,0,0))
        rodape.grid(row=1,column=0,columnspan=2,sticky='ew')
        ttk.Button(rodape,text='Excluir permanentemente',command=excluir_definitivamente).pack(side='left')
        ttk.Button(rodape,text='Restaurar entradas',style='Restaurar.TButton',width=22,
                   command=restaurar).pack(side='right')
        atualizar()
        centralizar(tela,800,450)
        tela.deiconify()
