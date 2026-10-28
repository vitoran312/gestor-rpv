"""Janelas de uma operação: cadastro, recebimento, previsão atual e documentos."""
import sqlite3
import json
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk, filedialog

from dados import centavos, moeda, data_iso, data_br, previsao_por_prazo, reais
from visual import px
from componentes import CampoMoeda, CampoData, centralizar, AreaRolavel, BalaoAjuda, fechar_com_confirmacao
from contas import dados_para_copiar
from tema import cores
from documentos import validar_anexo, abrir_arquivo
from interacao import aplicar_formato, capitalizar_inicio, menu_copia
from mensagens import descrever_erro
import demonstracao


# A janela de entrada é cerca de 30% maior que as demais: fontes de 10 para 13 pontos, campos e
# espaçamentos na mesma proporção. Campos de texto crescem junto com a fonte, pois a largura é em caracteres.
AMPLIACAO = 1.3
ESTILOS_AMPLIADOS = {'': 'Form', 'Titulo.TLabel': 'FormTitulo.TLabel', 'DataCalculada.TLabel': 'FormDataCalculada.TLabel',
                     'Dinheiro.TLabel': 'FormDinheiro.TLabel', 'Salvar.TButton': 'Form.Salvar.TButton'}


def ampliar_formulario(widget, fonte):
    """Aplica as versões ampliadas dos estilos a todos os elementos já criados na janela."""
    if isinstance(widget, (ttk.Entry, ttk.Combobox)):
        widget.configure(font=(fonte, 13), style='Form.' + widget.winfo_class())
    elif isinstance(widget, tk.Text):
        widget.configure(font=(fonte, 13), padx=8, pady=8)
    elif isinstance(widget, (ttk.Label, ttk.Button, ttk.Radiobutton)):
        estilo = str(widget.cget('style'))
        novo = ESTILOS_AMPLIADOS.get(estilo)
        if novo == 'Form':
            novo = 'Form.' + widget.winfo_class()
        if novo:
            widget.configure(style=novo)
    for filho in widget.winfo_children():
        if not isinstance(filho, tk.Toplevel):
            ampliar_formulario(filho, fonte)


def pad(valor):
    return round(valor * AMPLIACAO) if isinstance(valor, int) else tuple(round(v * AMPLIACAO) for v in valor)



def criar_campos_principais(quadro, registro, conta_inicial, mapa_contas, modo_previsao):
    """Nome, datas, valores e conta, uma linha cada; a previsão pode vir do calendário ou do prazo."""
    campos = {}
    definicoes = [
        ('nome', 'Nome completo do titular original', ''),
        ('aquisicao', 'Data da aquisição (DD/MM/AAAA)', date.today().strftime('%d/%m/%Y')),
        ('previsto', 'Valor Total RPV', ''),
        ('custo', 'Valor de aquisição', ''),
        ('conta', 'Receber na conta de', conta_inicial),
        ('previsao', 'Previsão inicial de recebimento (DD/MM/AAAA)', ''),
    ]
    for linha, (chave, titulo, padrao) in enumerate(definicoes):
        if chave == 'previsao':
            ttk.Radiobutton(quadro,text='Previsão inicial por calendário',variable=modo_previsao,value='calendario').grid(row=linha,column=0,sticky='w',pady=pad(6),padx=pad((0,16)))
        else:
            ttk.Label(quadro, text=titulo).grid(row=linha, column=0, sticky='w', pady=pad(6), padx=pad((0,16)))
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
        entrada.grid(row=linha, column=1, sticky='ew', pady=pad(6))
        if chave == 'previsao':
            campo_previsao = entrada
        if chave == 'nome':
            entrada.focus_set()
            aplicar_formato(entrada, campos['nome'], str.title)
    return campos, campo_previsao


def criar_linha_prazo(quadro, linha, campos, modo_previsao, campo_previsao):
    """Previsão por prazo em dias, sincronizada nos dois sentidos com a data escolhida no calendário."""
    ttk.Radiobutton(quadro,text='Previsão inicial de recebimento em',variable=modo_previsao,value='dias').grid(row=linha,column=0,sticky='w',pady=pad(6),padx=pad((0,16)))
    linha_prazo = ttk.Frame(quadro)
    linha_prazo.grid(row=linha,column=1,sticky='ew',pady=pad(6))
    prazo = tk.StringVar()
    entrada_prazo = ttk.Entry(linha_prazo,textvariable=prazo,width=6,justify='center',name='prazo_dias')
    entrada_prazo.pack(side='left')
    ttk.Label(linha_prazo,text='dias.').pack(side='left',padx=pad((8,12)))
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
    return prazo


def criar_lucro(quadro, linha, campos, tela):
    lucro = tk.StringVar()
    ttk.Label(quadro, text='Lucro previsto').grid(row=linha, column=0, sticky='w', pady=pad(6))
    ttk.Label(quadro, textvariable=lucro).grid(row=linha, column=1, sticky='w')

    def atualizar_lucro(*_):
        try:
            lucro.set(reais(centavos(campos['previsto'].get()) - centavos(campos['custo'].get())))
        except ValueError:
            lucro.set('Preencha os dois valores')

    for chave in ('previsto', 'custo'):
        campos[chave].trace_add('write', lambda *_: tela.after_idle(atualizar_lucro))
    atualizar_lucro()


def criar_comissao(quadro, linha, registro, tela):
    """Pergunta se há comissão (linha) e, só quando há, mostra o valor (linha seguinte)."""
    ttk.Label(quadro, text='Há comissão?').grid(row=linha, column=0, sticky='w', pady=pad(6))
    tem_comissao = tk.StringVar(value='Sim' if registro and registro['comissao'] is not None else 'Não')
    escolha = ttk.Combobox(quadro, textvariable=tem_comissao, values=('Não', 'Sim'), state='readonly', width=29)
    escolha.grid(row=linha, column=1, sticky='ew')
    valor_comissao = tk.StringVar(value=moeda(registro['comissao']) if registro and registro['comissao'] is not None else '')
    rotulo_comissao = ttk.Label(quadro, text='Valor da comissão')
    entrada_comissao = CampoMoeda(quadro, valor_comissao)
    rotulo_comissao.grid(row=linha + 1, column=0, sticky='w', pady=pad(6))
    entrada_comissao.grid(row=linha + 1, column=1, sticky='ew')

    def exibir_comissao(*_):
        for widget in (rotulo_comissao, entrada_comissao):
            if tem_comissao.get() == 'Sim':
                widget.grid()
            else:
                widget.grid_remove()
        tela.after_idle(lambda: centralizar(tela))

    tem_comissao.trace_add('write', exibir_comissao)
    exibir_comissao()
    return tem_comissao, valor_comissao


def criar_observacoes(quadro, linha, registro, fonte):
    ttk.Label(quadro, text='Observações').grid(row=linha, column=0, sticky='nw', pady=pad(10))
    observacoes = tk.Text(quadro, height=4, width=32, wrap='word', font=(fonte, 10),
                          bg=cores()['campo'], fg=cores()['texto'], insertbackground=cores()['texto'],
                          selectbackground=cores()['selecao'], selectforeground=cores()['texto_selecao'],
                          relief='flat', padx=pad(6), pady=pad(6))
    observacoes.grid(row=linha, column=1, sticky='ew',pady=pad(10))

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
    return observacoes

class RegistroMixin:
    def formulario(self, identificador=None):
        # Um formulário por vez: Ctrl+N repetido (ou a tecla presa) traz o que já está aberto,
        # em vez de abrir outro e salvar a mesma entrada duas vezes.
        if self.trazer_se_aberta(self.janela_formulario):
            return
        registro = self.banco.obter(identificador) if identificador else None
        contas=list(self.banco.contas(somente_ativas=True))
        conta_original=self.banco.obter_conta(registro['conta_id']) if registro and registro['conta_id'] is not None else None
        if conta_original is not None and all(c['id']!=conta_original['id'] for c in contas):
            contas.append(conta_original)
        if not contas and registro is None:
            messagebox.showinfo('Contas de recebimento','Cadastre ou reative uma conta antes de criar uma entrada.',parent=self.janela)
            return
        mapa_contas={c['identificacao']:c['id'] for c in contas}
        if registro:
            conta_inicial=conta_original['identificacao'] if conta_original else registro['conta']+' (conta removida)'
            if conta_original is None:
                mapa_contas[conta_inicial]=None
        else:
            conta_inicial=contas[0]['identificacao']
        tela = self.janela_formulario = tk.Toplevel(self.janela)
        tela.withdraw()
        tela.title('Editar registro' if registro else 'Nova entrada')
        tela.configure(bg=cores()['fundo'])
        tela.resizable(False, False)
        tela.transient(self.janela_ativa())
        cabecalho = ttk.Frame(tela,padding=pad((24,16,24,0)))
        cabecalho.pack(fill='x')
        ttk.Label(cabecalho,text='Editar registro' if registro else 'Nova entrada',style='Titulo.TLabel').pack(anchor='w')
        area = AreaRolavel(tela)
        area.pack(fill='both',expand=True)
        quadro = area.conteudo
        modo_previsao = tk.StringVar(value='calendario')
        campos, campo_previsao = criar_campos_principais(quadro, registro, conta_inicial, mapa_contas, modo_previsao)
        linha = len(campos)
        prazo = criar_linha_prazo(quadro, linha, campos, modo_previsao, campo_previsao)
        criar_lucro(quadro, linha + 1, campos, tela)
        tem_comissao, valor_comissao = criar_comissao(quadro, linha + 2, registro, tela)
        observacoes = criar_observacoes(quadro, linha + 4, registro, self.fonte)
        painel_documentos = ttk.Frame(quadro)
        painel_documentos.grid(row=linha + 5,column=0,columnspan=2,sticky='ew',pady=pad((8,0)))
        anexos_pendentes = self.criar_painel_documentos(painel_documentos, tela, identificador)

        def salvar():
            dados = {chave: variavel.get().strip() for chave, variavel in campos.items()}
            # Todos os campos são conferidos de uma vez, e cada problema diz em qual campo está.
            problemas = [] if dados['nome'] else ['Nome do titular: informe o nome completo.']

            def converter(chave, rotulo, funcao, *valores):
                try:
                    dados[chave] = funcao(*valores)
                except ValueError as erro:
                    problemas.append(f'{rotulo}: {erro}')

            converter('aquisicao', 'Data da aquisição', data_iso, dados['aquisicao'])
            if modo_previsao.get() == 'dias':
                converter('previsao', 'Prazo em dias', lambda: data_iso(previsao_por_prazo(campos['aquisicao'].get(), prazo.get())))
            else:
                converter('previsao', 'Previsão inicial', data_iso, dados['previsao'])
            converter('previsto', 'Valor Total RPV', centavos, dados['previsto'])
            converter('custo', 'Valor de aquisição', centavos, dados['custo'])
            dados['comissao'] = None
            if tem_comissao.get() == 'Sim':
                converter('comissao', 'Comissão', centavos, valor_comissao.get())
            if problemas:
                messagebox.showerror('Confira o cadastro', '\n'.join(problemas), parent=tela)
                return
            dados['conta_id'] = mapa_contas.get(dados['conta'])
            dados['observacoes'] = observacoes.get('1.0', 'end-1c').strip()
            try:
                salvo = self.banco.salvar(dados, identificador, anexos=anexos_pendentes)
                demonstracao.adotar(self.banco, operacao=salvo)
            except ValueError as erro:
                messagebox.showerror('Confira o cadastro', descrever_erro(erro), parent=tela)
                return
            except (sqlite3.Error,OSError) as erro:
                messagebox.showerror('Não foi possível salvar', descrever_erro(erro), parent=tela)
                return
            self.atualizar()
            tela.destroy()

        ttk.Separator(tela).pack(fill='x',padx=pad(24))
        botoes = ttk.Frame(tela,padding=pad((20,8,20,12)))
        botoes.pack(fill='x')
        for coluna in range(3):
            botoes.columnconfigure(coluna,weight=1,uniform='acoes')
        ttk.Button(botoes,text='Dados de recebimento',width=20,
                   command=lambda: self.ver_dados_recebimento(tela,registro,mapa_contas.get(campos['conta'].get()))).grid(row=0,column=0,sticky='ew',padx=pad((0,8)))
        fechar = fechar_com_confirmacao(tela, lambda: (
            tuple(variavel.get() for variavel in campos.values()), modo_previsao.get(), prazo.get(), tem_comissao.get(),
            valor_comissao.get(), observacoes.get('1.0', 'end-1c'), len(anexos_pendentes)))
        ttk.Button(botoes,text='Cancelar',width=20,command=fechar).grid(row=0,column=1,sticky='ew',padx=pad((4,4)))
        ttk.Button(botoes,text='Salvar registro',width=20,style='Salvar.TButton',command=salvar).grid(row=0,column=2,sticky='ew',padx=pad((8,0)))
        ampliar_formulario(tela, self.fonte)
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
                messagebox.showerror('Anexar documentos',descrever_erro(erro),parent=tela)
                return
            for arquivo in novos:
                if arquivo not in anexos_pendentes:
                    anexos_pendentes.append(arquivo)
            atualizar_contagem()

        botao_anexar=ttk.Button(painel_documentos,text='Anexar documentos',command=anexar)
        botao_anexar.pack(side='left')
        explicacao=('Anexe comprovantes do recebimento, como confirmações de transferência e extratos bancários.'
                    if tipo=='recebimento' else 'Anexe PDFs e imagens desta entrada, como contratos e protocolos.')
        BalaoAjuda(botao_anexar,explicacao)
        ttk.Button(painel_documentos,textvariable=texto_documentos,
                   command=lambda: self.ver_documentos(tela, identificador, tipo, anexos_pendentes, atualizar_contagem)).pack(side='left',padx=8)
        atualizar_contagem()

        return anexos_pendentes

    def ver_documentos(self, tela, identificador, tipo, anexos_pendentes, ao_mudar):
        """Lista os documentos salvos e os ainda pendentes; permite abrir e remover."""
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
        lista.column('nome',width=px(lista,370))
        lista.column('situacao',width=px(lista,160))
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
            origem,valor = caminhos[selecao[0]]
            try:
                caminho = self.banco.caminho_documento(valor) if origem == 'salvo' else valor
                abrir_arquivo(caminho)
            except (OSError,ValueError) as erro:
                messagebox.showerror('Abrir documento',descrever_erro(erro),parent=janela)

        def retirar():
            selecao = lista.selection()
            if not selecao:
                return
            origem,valor = caminhos[selecao[0]]
            if origem=='salvo':
                if not messagebox.askyesno('Excluir anexo',
                    'Excluir definitivamente a cópia deste documento guardada no programa?\n\n'
                    'A exclusão será aplicada agora. O arquivo original fora do programa será preservado.',
                    parent=janela,icon='warning',default='no'):
                    return
                try:
                    self.banco.remover_documento(valor)
                except (OSError,sqlite3.Error,ValueError) as erro:
                    messagebox.showerror('Excluir anexo',descrever_erro(erro),parent=janela)
                    return
            else:
                anexos_pendentes.remove(valor)
            atualizar_lista()
            ao_mudar()

        def fechar():
            janela.destroy()
            tela.grab_set()

        rodape = ttk.Frame(corpo)
        rodape.pack(fill='x',pady=(12,0))
        ttk.Button(rodape,text='Abrir documento',command=abrir_documento).pack(side='left')
        ttk.Button(rodape,text='Remover documento',command=retirar).pack(side='left',padx=8)
        ttk.Button(rodape,text='Fechar',command=fechar).pack(side='right')
        lista.bind('<Double-1>',lambda _: abrir_documento())
        lista.bind('<Return>',lambda _: abrir_documento())
        janela.protocol('WM_DELETE_WINDOW',fechar)
        janela.bind('<Escape>',lambda _: fechar())
        atualizar_lista()
        centralizar(janela,650,400)
        janela.deiconify()
        janela.grab_set()

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
        rotulo_dados = ttk.Label(corpo, text=texto, wraplength=px(corpo, 550))
        rotulo_dados.pack(anchor='w', pady=(0, 15))
        menu_copia(rotulo_dados, lambda: texto)
        if registro and registro['conta_id'] == conta_id:
            ttk.Label(corpo, text='Dados preservados do cadastro desta operação.', wraplength=px(corpo, 550)).pack(anchor='w', pady=(0, 15))

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

    def abrir_recebimento(self, identificador, variavel=None, atual=False):
        if variavel is not None:
            variavel.set(atual)
        registro = self.banco.obter(identificador)
        if registro is None:
            self.atualizar()
            return
        if self.trazer_se_aberta(self.janela_recebimento):
            return
        tela = self.janela_recebimento = tk.Toplevel(self.historico)
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
                messagebox.showerror('Confira o recebimento', descrever_erro(erro), parent=tela)
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
        fechar = fechar_com_confirmacao(tela, lambda: (valor.get(), len(anexos_pendentes)))
        ttk.Button(botoes, text='Cancelar', command=fechar).pack(side='right')
        ttk.Button(botoes, text='Salvar recebimento', style='Salvar.TButton', command=salvar).pack(side='right', padx=8)
        centralizar(tela)
        tela.deiconify()
        tela.grab_set()

    def editar_previsao(self, identificador):
        registro = self.banco.obter(identificador)
        if registro is None:
            self.atualizar()
            return
        if self.trazer_se_aberta(self.janela_previsao):
            return
        tela = self.janela_previsao = tk.Toplevel(self.historico)
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

        ttk.Label(corpo,text='Alterações de previsão').pack(anchor='w',pady=(16,6))
        quadro_historico=ttk.Frame(corpo)
        quadro_historico.pack(fill='both',expand=True)
        historico=ttk.Treeview(quadro_historico,columns=('anterior','nova','quando'),show='headings',height=4)
        for coluna,titulo in (('anterior','Previsão anterior'),('nova','Nova previsão'),('quando','Alterada em')):
            historico.heading(coluna,text=titulo)
            historico.column(coluna,width=px(historico,180),anchor='center')
        historico.pack(side='left',fill='both',expand=True)
        for item in self.banco.historico_previsoes(identificador):
            historico.insert('','end',values=(data_br(item['anterior']),data_br(item['nova']),
                datetime.fromisoformat(item['alterada_em']).strftime('%d/%m/%Y %H:%M')))
        barra=ttk.Scrollbar(quadro_historico,orient='vertical',command=historico.yview)
        historico.configure(yscrollcommand=barra.set)
        barra.pack(side='right',fill='y')
        def salvar():
            try:
                self.banco.atualizar_previsao(identificador, data_iso(valor.get()))
            except ValueError as erro:
                messagebox.showerror('Confira a previsão', descrever_erro(erro), parent=tela)
                return
            except sqlite3.Error:
                messagebox.showerror('Previsão atual', 'Não foi possível salvar.', parent=tela)
                return
            self.atualizar()
            tela.destroy()

        rodape = ttk.Frame(corpo)
        rodape.pack(fill='x', pady=(15, 0))
        fechar = fechar_com_confirmacao(tela, valor.get)
        ttk.Button(rodape, text='Cancelar', command=fechar).pack(side='right')
        ttk.Button(rodape, text='Salvar previsão', style='Salvar.TButton', command=salvar).pack(side='right', padx=8)
        centralizar(tela)
        tela.deiconify()
        tela.grab_set()
