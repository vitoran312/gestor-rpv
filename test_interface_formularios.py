"""Testes de interface: formulários de entrada, recebimento, previsão e contas."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import unittest
from datetime import date
from unittest.mock import patch

from componentes import CampoData, CampoMoeda, AreaRolavel
from apoio_testes import dados_rpv, prorrogacao_antiga
from tema import cores
from apoio_interface import TesteDeInterface, botao, filhos


@unittest.skipUnless(os.environ.get('GESTOR_RPV_TESTE_UI') == '1', 'Requer sessão gráfica e GESTOR_RPV_TESTE_UI=1')
class TestFormularios(TesteDeInterface):
    def test_digitacao_rapida_cursor_e_validacao_de_aquisicao(self):
        form = self.formulario()
        moedas = [w for w in filhos(form) if isinstance(w, CampoMoeda)]
        campo = moedas[0]
        campo.entrada.focus_force()
        self.root.update()
        campo.entrada.selection_range(0, tk.END)
        for tecla in '1056050':
            campo.entrada.event_generate('<KeyPress>', keysym=tecla)
        self.root.update()
        self.assertEqual(campo.variavel.get(), '10.560,50')
        self.assertEqual(campo.entrada.index('insert'), 9)
        campo.entrada.icursor(1)
        campo.entrada.event_generate('<KeyPress>', keysym='2')
        self.root.update()
        self.assertEqual(campo.entrada.index('insert'), 2)
        self.assertEqual(campo.variavel.get(), '120.560,50')
        campo.variavel.set('10.560,50')
        moedas[1].entrada.focus_force()
        self.root.update()
        self.assertEqual(campo.variavel.get(), '10.560,50')
        nome = next(w for w in filhos(form) if isinstance(w, ttk.Entry))
        nome.insert(0, 'pessoa de TESTE')
        datas = [w for w in filhos(form) if isinstance(w, CampoData)]
        datas[0].variavel.set('01/02/2024')
        datas[1].abrir()
        self.root.update()
        datas[1].ano, datas[1].mes = 2024, 2
        datas[1].desenhar()
        botao(datas[1].calendario, '29').invoke()
        self.root.update()
        self.assertEqual(datas[1].variavel.get(), '29/02/2024')
        self.assertEqual(self.root.grab_current(), form)
        for custo in ('0', '20000'):
            moedas[1].variavel.set(custo)
            with patch.object(messagebox, 'showerror') as erro:
                botao(form, 'Salvar registro').invoke()
                self.root.update()
                erro.assert_called_once()
            self.assertEqual(self.banco.listar(), [])
        moedas[1].variavel.set('6000')
        botao(form, 'Salvar registro').invoke()
        self.root.update()
        registro = self.banco.listar()[0]
        self.assertEqual(registro['custo'], 600000)
        self.assertEqual(registro['nome'], 'Pessoa De Teste')

    def test_contas_cadastro_edicao_status_e_lista_dinamica(self):
        self.programa.mostrar_contas()
        self.root.update()
        janela = self.programa.janela_contas
        botao(janela.tela, 'Cadastrar nova conta').invoke()
        self.root.update()
        form = next(w for w in janela.tela.winfo_children() if isinstance(w, tk.Toplevel))
        entradas = [w for w in filhos(form) if isinstance(w, ttk.Entry)]
        self.assertEqual(str(entradas[6].cget('state')), 'readonly')
        self.assertEqual(len(entradas[6].cget('values')), 27)
        self.assertIn('SP', entradas[6].cget('values'))
        self.assertIn('PR', entradas[6].cget('values'))
        valores = ('Conta teste', 'pessoa DE teste', '52998224725', 'Endereço teste', '12', 'Cidade Teste', 'SP', 'Banco teste', '0001', '12345-6', 'teste@example.com')
        for entrada, valor in zip(entradas, valores):
            if isinstance(entrada, ttk.Combobox):
                entrada.set(valor)
            else:
                entrada.insert(0, valor)
        botao(form, 'Salvar conta').invoke()
        self.root.update()
        conta = next(c for c in self.banco.contas() if c['identificacao'] == 'Conta teste')
        janela.tabela.selection_set(str(conta['id']))
        with patch.object(messagebox, 'askyesno', return_value=True):
            janela.alterar_status()
        self.root.update()
        self.assertFalse(self.banco.obter_conta(conta['id'])['ativa'])
        form = self.formulario()
        combo = next(w for w in filhos(form) if isinstance(w, ttk.Combobox))
        self.assertNotIn('Conta teste', combo.cget('values'))
        form.destroy()
        janela.tabela.selection_set(str(conta['id']))
        with patch.object(messagebox, 'askyesno', return_value=True):
            janela.alterar_status()
        form = self.formulario()
        combo = next(w for w in filhos(form) if isinstance(w, ttk.Combobox))
        self.assertIn('Conta teste', combo.cget('values'))

    def test_previsao_atual_edicao_cor_e_preservacao_historico(self):
        identificador = self.banco.salvar(dict(nome='Teste', aquisicao='2026-10-22', previsto=2000000,
            custo=1200000, conta='Vitor', previsao='2026-12-20', comissao=None, observacoes=''))
        prorrogacao_antiga(self.banco, identificador, '2027-01-20')
        prorrogacao_antiga(self.banco, identificador, '2027-02-20')
        self.programa.mostrar_historico()
        self.root.update()
        tabela = self.programa.tabela
        self.assertNotIn('prorrogacao', tabela.cget('columns'))
        esperado = {'nome': 'w', 'conta': 'w', 'custo': 'e', 'comissao': 'e', 'previsto': 'e', 'lucro': 'e'}
        for coluna in tabela.cget('columns'):
            self.assertEqual(str(tabela.column(coluna, 'anchor')), esperado.get(coluna, 'center'))
            self.assertEqual(str(tabela.heading(coluna, 'anchor')), str(tabela.column(coluna, 'anchor')))
        tabela.xview_moveto(1)
        self.root.update()
        rotulo = self.programa.acoes_linhas[str(identificador)][0]
        self.assertEqual(rotulo.cget('text'), '20/02/2027')
        self.assertEqual(rotulo.cget('style'), 'PrevisaoAdiada.TLabel')
        self.assertEqual(str(ttk.Style().lookup('PrevisaoAdiada.TLabel', 'foreground')), cores()['vermelho'])
        rotulo.event_generate('<Button-1>')
        rotulo.event_generate('<ButtonRelease-1>')
        self.root.update()
        tela = next(w for w in self.programa.historico.winfo_children() if isinstance(w, tk.Toplevel))
        campo = next(w for w in filhos(tela) if isinstance(w, CampoData))
        campo.abrir()
        self.root.update()
        campo.selecionar(date(2027, 3, 20))
        botao(tela, 'Salvar previsão').invoke()
        self.root.update()
        registro = self.banco.obter(identificador)
        self.assertEqual(registro['previsao_atual'], '2027-03-20')
        self.assertEqual(registro['previsao'], '2026-12-20')
        self.assertEqual(self.banco.obter(identificador)['total_prorrogacoes'], 2)
        self.programa.acoes_linhas[str(identificador)][0].event_generate('<Button-1>')
        self.programa.acoes_linhas[str(identificador)][0].event_generate('<ButtonRelease-1>')
        self.root.update()
        tela = next(w for w in self.programa.historico.winfo_children() if isinstance(w, tk.Toplevel))
        campo = next(w for w in filhos(tela) if isinstance(w, CampoData))
        campo.variavel.set('20/12/2026')
        botao(tela, 'Salvar previsão').invoke()
        self.root.update()
        self.assertEqual(self.programa.acoes_linhas[str(identificador)][0].cget('style'), 'Previsao.TLabel')
        self.programa.historico.destroy()
        self.programa.mostrar_historico()
        self.root.update()
        self.assertEqual(self.banco.obter(identificador)['previsao_atual'], '2026-12-20')

    def test_dados_preservados_copiar_e_grab(self):
        registro = self.banco.salvar(dict(nome='Teste', aquisicao='2026-10-22', previsto=2000000,
            custo=1200000, conta='Vitor', previsao='2026-12-20', comissao=None, observacoes=''))
        self.programa.formulario(registro)
        self.root.update()
        form = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        botao(form, 'Dados de recebimento').invoke()
        self.root.update()
        tela = next(w for w in form.winfo_children() if isinstance(w, tk.Toplevel))
        rotulo = next(w for w in filhos(tela) if isinstance(w, ttk.Label) and 'Nome completo:' in w.cget('text'))
        rotulo.event_generate('<Button-3>', x=5, y=5)
        self.root.update()
        menu = next(w for w in rotulo.winfo_children() if isinstance(w, tk.Menu))
        menu.invoke('Copiar')
        menu.unpost()
        self.root.update()
        self.assertIn('Nome completo:', tela.clipboard_get())
        botao(tela, 'Fechar').invoke()
        self.root.update()
        self.assertEqual(self.root.grab_current(), form)

    def test_cpf_obrigatorio_mascara_e_nomes_durante_digitacao(self):
        self.programa.mostrar_contas()
        self.root.update()
        janela = self.programa.janela_contas
        for linha in janela.tabela.get_children():
            self.assertIn('Completar cadastro', janela.tabela.item(linha, 'values')[-1])
            self.assertIn('incompleta', janela.tabela.item(linha, 'tags'))
        self.assertEqual(str(ttk.Style().lookup('ContaIncompleta.TLabel', 'foreground')), cores()['vermelho'])
        self.assertEqual(str(janela.tabela.tag_configure('incompleta', 'foreground')), '')
        janela.formulario()
        self.root.update()
        tela = next(w for w in janela.tela.winfo_children() if isinstance(w, tk.Toplevel))
        entradas = [w for w in filhos(tela) if isinstance(w, ttk.Entry)]
        cpf = entradas[2]
        cpf.focus_force()
        self.root.update()
        for digito in '52998224725':
            cpf.event_generate('<KeyPress>', keysym=digito)
            cpf.event_generate('<KeyRelease>', keysym=digito)
        self.root.update()
        self.assertEqual(cpf.get(), '529.982.247-25')
        self.assertEqual(cpf.index('insert'), 14)
        cpf.event_generate('<KeyPress>', keysym='1')
        self.root.update()
        self.assertEqual(cpf.get(), '529.982.247-25')
        nome = entradas[1]
        nome.focus_force()
        self.root.update()
        for char in 'vitor silva':
            tecla = 'space' if char == ' ' else char
            nome.event_generate('<KeyPress>', keysym=tecla)
            nome.event_generate('<KeyRelease>', keysym=tecla)
        self.root.update()
        self.assertEqual(nome.get(), 'Vitor Silva')
        entradas[0].focus_force()
        self.root.update()
        entradas[0].insert(0, 'conta teste')
        entradas[0].event_generate('<KeyRelease>', keysym='e')
        self.assertEqual(entradas[0].get(), 'Conta teste')
        for entrada, valor in zip(entradas[3:], ('rua teste', '12', 'cidade teste', 'SP', 'banco teste', '001', '123-4', 'ChaveCaseSensitive')):
            if isinstance(entrada, ttk.Combobox):
                entrada.set(valor)
            else:
                entrada.insert(0, valor)
        cpf.delete(0, tk.END)
        with patch.object(messagebox, 'showerror') as erro:
            botao(tela, 'Salvar conta').invoke()
            self.root.update()
            erro.assert_called_once()
        self.assertEqual(len(self.banco.contas()), 2)
        cpf.focus_force()
        self.root.update()
        cpf.insert(0, '52998224725')
        cpf.event_generate('<KeyRelease>', keysym='5')
        botao(tela, 'Salvar conta').invoke()
        self.root.update()
        conta = next(c for c in self.banco.contas() if c['identificacao'] == 'Conta teste')
        self.assertEqual(conta['cpf'], '52998224725')
        self.assertEqual(conta['pix'], 'ChaveCaseSensitive')

    def test_menu_texto_recorta_copia_cola_e_preserva_modal(self):
        form = self.formulario()
        nome = next(w for w in filhos(form) if isinstance(w, ttk.Entry))
        nome.insert(0, 'Vitor Silva')
        nome.selection_range(0, 5)

        def contexto(acao):
            nome.event_generate('<Button-3>', x=5, y=5)
            self.root.update()
            menu = [w for w in nome.winfo_children() if isinstance(w, tk.Menu)][-1]
            menu.invoke(acao)
            menu.unpost()
            self.root.update()
            self.assertEqual(self.root.grab_current(), form)

        contexto('Copiar')
        self.assertEqual(nome.clipboard_get(), 'Vitor')
        contexto('Recortar')
        self.assertEqual(nome.get(), ' Silva')
        nome.icursor(0)
        contexto('Colar')
        self.assertEqual(nome.get(), 'Vitor Silva')
        contexto('Selecionar tudo')
        self.assertEqual(nome.index('sel.first'), 0)
        self.assertEqual(nome.index('sel.last'), len(nome.get()))

    def test_valores_em_centavos_colagem_recorte_e_persistencia(self):
        form = self.formulario()
        moedas = [w for w in filhos(form) if isinstance(w, CampoMoeda)]
        esperado = ('52.000,00', '15.236,59')
        for campo, digitos, resultado in zip(moedas[:2], ('5200000', '1523659'), esperado):
            campo.entrada.focus_force()
            self.root.update()
            campo.entrada.selection_clear()
            campo.entrada.icursor(0)
            for tecla in digitos:
                campo.entrada.event_generate('<KeyPress>', keysym=tecla)
            self.root.update()
            self.assertEqual(campo.variavel.get(), resultado)
        custo = moedas[1]
        custo.entrada.selection_range(0, tk.END)
        custo.entrada.event_generate('<<Cut>>')
        self.root.update()
        self.assertEqual(custo.variavel.get(), '0,00')
        self.assertEqual(custo.entrada.clipboard_get(), '15.236,59')
        custo.entrada.selection_range(0, tk.END)
        custo.entrada.event_generate('<<Paste>>')
        self.root.update()
        self.assertEqual(custo.variavel.get(), '15.236,59')
        # Colar troca o valor inteiro, mesmo com o cursor no fim do campo; número sem vírgula são reais.
        for colado, resultado in (('5,00', '5,00'), ('1500', '1.500,00'), ('15.236,59', '15.236,59')):
            custo.entrada.selection_clear()
            custo.entrada.icursor(tk.END)
            custo.entrada.clipboard_clear()
            custo.entrada.clipboard_append(colado)
            custo.entrada.event_generate('<<Paste>>')
            self.root.update()
            self.assertEqual(custo.variavel.get(), resultado)
        custo.entrada.clipboard_clear()
        custo.entrada.clipboard_append('9' * 20)
        with patch.object(messagebox, 'showwarning') as aviso:
            custo.entrada.event_generate('<<Paste>>')
        self.assertIn('valor máximo', aviso.call_args.args[1])
        nome = next(w for w in filhos(form) if isinstance(w, ttk.Entry))
        nome.insert(0, 'Titular Teste')
        datas = [w for w in filhos(form) if isinstance(w, CampoData)]
        datas[0].variavel.set('01/01/2026')
        datas[1].variavel.set('01/01/2027')
        botao(form, 'Salvar registro').invoke()
        self.root.update()
        registro = self.banco.listar()[0]
        self.assertEqual(registro['previsto'], 5200000)
        self.assertEqual(registro['custo'], 1523659)

    def test_recebimento_caixa_data_cor_e_reabertura(self):
        identificador = self.banco.salvar(dict(nome='Teste', aquisicao='2026-10-01', previsto=2000000,
            custo=1200000, conta='Vitor', previsao='2026-12-20', comissao=None, observacoes=''))
        self.programa.mostrar_historico()
        self.root.update()
        tabela = self.programa.tabela
        self.assertEqual(tabela.cget('columns')[-1], 'recebido')
        tabela.xview_moveto(1)
        self.root.update()
        caixa = self.programa.acoes_linhas[str(identificador)][1]
        self.assertFalse(caixa.estado.get())
        caixa.invoke()
        self.root.update()
        tela = next(w for w in self.programa.historico.winfo_children() if isinstance(w, tk.Toplevel))
        campo = next(w for w in filhos(tela) if isinstance(w, CampoData))
        campo.abrir()
        self.root.update()
        campo.selecionar(date(2026, 10, 22))
        botao(tela, 'Salvar recebimento').invoke()
        self.root.update()
        self.assertEqual(self.banco.obter(identificador)['recebimento'], '2026-10-22')
        caixa = self.programa.acoes_linhas[str(identificador)][1]
        self.assertTrue(caixa.estado.get())
        x, y, largura, altura = tabela.bbox(str(identificador), 'recebido')
        self.assertLessEqual(abs((caixa.winfo_x() + caixa.winfo_width() / 2) - (x + largura / 2)), 1)
        self.assertEqual(caixa.cget('text'), '22/10/2026')
        self.assertEqual(caixa.cget('style'), 'Recebida.Recebido.TCheckbutton')
        estilo = ttk.Style()
        self.assertEqual(str(estilo.lookup('Recebida.Recebido.TCheckbutton', 'foreground')), cores()['verde'])
        self.assertIn('bold', str(estilo.lookup('Recebida.Recebido.TCheckbutton', 'font')))
        # Recebida: a linha inteira fica verde, como a atrasada fica vermelha.
        self.assertEqual(tabela.item(str(identificador), 'tags'), ('recebida',))
        self.assertEqual(str(tabela.tag_configure('recebida', 'background')), cores()['recebida'])
        self.assertEqual(self.programa.acoes_linhas[str(identificador)][0].cget('style'), 'PrevisaoRecebida.TLabel')
        caixa.invoke()
        self.root.update()
        tela = next(w for w in self.programa.historico.winfo_children() if isinstance(w, tk.Toplevel))
        botao(tela, 'Cancelar').invoke()
        self.root.update()
        self.assertEqual(self.banco.obter(identificador)['recebimento'], '2026-10-22')
        self.programa.historico.destroy()
        self.programa.mostrar_historico()
        self.root.update()
        self.programa.tabela.xview_moveto(1)
        self.root.update()
        caixa = self.programa.acoes_linhas[str(identificador)][1]
        self.assertTrue(caixa.estado.get())
        caixa.invoke()
        self.root.update()
        tela = next(w for w in self.programa.historico.winfo_children() if isinstance(w, tk.Toplevel))
        with patch.object(messagebox, 'askyesno', return_value=True):
            botao(tela, 'Desmarcar recebimento').invoke()
        self.root.update()
        self.assertIsNone(self.banco.obter(identificador)['recebimento'])

    def test_remover_conta_confirmacao_e_endereco_capitalizado(self):
        self.programa.mostrar_contas()
        self.root.update()
        janela = self.programa.janela_contas
        janela.formulario()
        self.root.update()
        tela = next(w for w in janela.tela.winfo_children() if isinstance(w, tk.Toplevel))
        entradas = [w for w in filhos(tela) if isinstance(w, ttk.Entry)]
        endereco = entradas[3]
        endereco.focus_force()
        self.root.update()
        for char in 'rua das flores':
            tecla = 'space' if char == ' ' else char
            endereco.event_generate('<KeyPress>', keysym=tecla)
            endereco.event_generate('<KeyRelease>', keysym=tecla)
        self.root.update()
        self.assertEqual(endereco.get(), 'Rua Das Flores')
        tela.destroy()
        conta = self.banco.contas()[0]
        janela.tabela.selection_set(str(conta['id']))
        with patch.object(messagebox, 'askyesno', return_value=False):
            botao(janela.tela, 'Remover').invoke()
        self.assertIsNotNone(self.banco.obter_conta(conta['id']))
        with patch.object(messagebox, 'askyesno', return_value=True):
            botao(janela.tela, 'Remover').invoke()
        self.root.update()
        self.assertIsNone(self.banco.obter_conta(conta['id']))

    def test_formulario_lista_todos_os_problemas_com_o_nome_do_campo(self):
        form = self.formulario()
        datas = [w for w in filhos(form) if isinstance(w, CampoData)]
        datas[0].variavel.set('31/02/2026')
        datas[1].variavel.set('01/01/0001')
        with patch.object(messagebox, 'showerror') as erro:
            botao(form, 'Salvar registro').invoke()
        texto = erro.call_args.args[1]
        # Formato (com o nome do campo) e regras (nome vazio, valor zerado) na mesma mensagem.
        for trecho in ('nome completo do titular', 'Data da aquisição: Informe uma data válida',
                       'Previsão inicial: Informe uma data entre', 'deve ser maior que zero'):
            self.assertIn(trecho, texto)
        moedas = [w for w in filhos(form) if isinstance(w, CampoMoeda)]
        moedas[0].entrada.clipboard_clear()
        moedas[0].entrada.clipboard_append('1e9')
        with patch.object(messagebox, 'showwarning') as aviso:
            moedas[0].entrada.event_generate('<<Paste>>')
        self.assertIn('não foi colado', aviso.call_args.args[1])
        self.assertEqual(moedas[0].variavel.get(), '0,00')

    def test_fechar_formulario_alterado_pergunta_antes_de_descartar(self):
        form = self.formulario()
        form.event_generate('<Escape>')
        self.root.update()
        self.assertFalse(form.winfo_exists())  # Sem alterações, fecha direto.
        self.assertEqual(self.dialogos, [])
        form = self.formulario()
        next(w for w in filhos(form) if isinstance(w, ttk.Entry)).insert(0, 'Digitado')
        with patch.object(messagebox, 'askyesno', return_value=False) as pergunta:
            botao(form, 'Cancelar').invoke()
            form.event_generate('<Escape>')
            self.root.update()
        self.assertEqual(pergunta.call_count, 2)
        self.assertEqual(pergunta.call_args.args[0], 'Descartar alterações?')
        self.assertTrue(form.winfo_exists())
        with patch.object(messagebox, 'askyesno', return_value=True):
            botao(form, 'Cancelar').invoke()
        self.assertFalse(form.winfo_exists())

    def test_prazo_calcula_data_sincroniza_calendario_valida_e_persiste(self):
        form = self.formulario()
        prazo = next(w for w in filhos(form) if isinstance(w, ttk.Entry) and w.winfo_name() == 'prazo_dias')
        datas = [w for w in filhos(form) if isinstance(w, CampoData)]
        datas[0].variavel.set('28/02/2024')
        self.assertTrue(prazo.instate(['disabled']))
        self.assertFalse(datas[1].botao.instate(['disabled']))
        modos = {w.cget('value'): w for w in filhos(form) if isinstance(w, ttk.Radiobutton)}
        modos['dias'].invoke()
        self.assertFalse(prazo.instate(['disabled']))
        self.assertTrue(datas[1].entrada.instate(['disabled']))
        self.assertTrue(datas[1].botao.instate(['disabled']))
        datas[1].abrir()
        self.assertIsNone(datas[1].calendario)
        prazo.insert(0, '1')
        self.root.update()
        self.assertEqual(datas[1].variavel.get(), '29/02/2024')
        datas[0].variavel.set('28/12/2024')
        self.assertEqual(datas[1].variavel.get(), '29/12/2024')
        prazo.delete(0, 'end')
        prazo.insert(0, '10')
        self.assertEqual(datas[1].variavel.get(), '07/01/2025')
        resultado = next(w for w in filhos(form) if w.winfo_name() == 'data_calculada')
        self.assertEqual(self.root.getvar(resultado.cget('textvariable')), '07/01/2025')
        anterior = datas[1].variavel.get()
        datas[1].entrada.insert(0, '999')
        self.assertEqual(datas[1].variavel.get(), anterior)
        modos['calendario'].invoke()
        self.assertTrue(prazo.instate(['disabled']))
        prazo.insert(0, '999')
        self.assertEqual(prazo.get(), '10')
        datas[1].abrir()
        self.root.update()
        datas[1].selecionar(date(2025, 1, 10))
        self.assertEqual(prazo.get(), '13')
        nome = next(w for w in filhos(form) if isinstance(w, ttk.Entry))
        nome.insert(0, 'teste prazo')
        moedas = [w for w in filhos(form) if isinstance(w, CampoMoeda)]
        moedas[0].variavel.set('20.000,00')
        moedas[1].variavel.set('12.000,00')
        modos['dias'].invoke()
        for invalido in ('', 'abc', '-1', '1,5', '999999999999999'):
            prazo.delete(0, 'end')
            prazo.insert(0, invalido)
            with patch.object(messagebox, 'showerror') as erro:
                botao(form, 'Salvar registro').invoke()
                erro.assert_called_once()
            self.assertEqual(self.banco.listar(), [])
        prazo.delete(0, 'end')
        prazo.insert(0, '10')
        modos['calendario'].invoke()
        datas[1].variavel.set('31/02/2025')
        with patch.object(messagebox, 'showerror') as erro:
            botao(form, 'Salvar registro').invoke()
            erro.assert_called_once()
        self.assertEqual(self.banco.listar(), [])
        datas[1].variavel.set('07/01/2025')
        botao(form, 'Salvar registro').invoke()
        self.root.update()
        registro = self.banco.listar()[0]
        self.assertEqual(registro['previsao'], '2025-01-07')
        self.programa.formulario(registro['id'])
        self.root.update()
        form = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        prazo = next(w for w in filhos(form) if isinstance(w, ttk.Entry) and w.winfo_name() == 'prazo_dias')
        self.assertEqual(prazo.get(), '10')

    def test_formularios_rolaveis_com_acoes_fixas_em_tela_menor(self):
        with patch.object(tk.Misc, 'winfo_screenheight', return_value=768):
            form = self.formulario()
            area = next(w for w in filhos(form) if isinstance(w, AreaRolavel))
            self.assertLess(area.canvas.yview()[1], 1)
            antes = area.canvas.yview()[0]
            area.canvas.event_generate('<MouseWheel>', delta=-120, x=10, y=10,
                rootx=area.canvas.winfo_rootx() + 10, rooty=area.canvas.winfo_rooty() + 10)
            self.root.update()
            self.assertGreater(area.canvas.yview()[0], antes)
            observacoes = next(w for w in filhos(form) if isinstance(w, tk.Text))
            observacoes.focus_force()
            self.root.update()
            self.assertGreaterEqual(observacoes.winfo_rooty(), area.canvas.winfo_rooty())
            self.assertLessEqual(observacoes.winfo_rooty() + observacoes.winfo_height(), area.canvas.winfo_rooty() + area.canvas.winfo_height())
            salvar = botao(form, 'Salvar registro')
            self.assertTrue(salvar.winfo_ismapped())
            self.assertLessEqual(salvar.winfo_rooty() + salvar.winfo_height(), form.winfo_rooty() + form.winfo_height())
            self.programa.alternar_tema()
            self.root.update()
            self.assertEqual(area.canvas.cget('bg'), cores()['fundo'])
            botao(form, 'Cancelar').invoke()
            self.programa.mostrar_contas()
            self.root.update()
            janela = self.programa.janela_contas
            botao(janela.tela, 'Cadastrar nova conta').invoke()
            self.root.update()
            conta = next(w for w in janela.tela.winfo_children() if isinstance(w, tk.Toplevel))
            area = next(w for w in filhos(conta) if isinstance(w, AreaRolavel))
            self.assertLess(area.canvas.yview()[1], 1)
            salvar = botao(conta, 'Salvar conta')
            self.assertLessEqual(salvar.winfo_rooty() + salvar.winfo_height(), conta.winfo_rooty() + conta.winfo_height())
            botao(conta, 'Cancelar').invoke()

    def test_baloes_documentos_distintos_preservam_modal_e_cancelam_ao_sair(self):
        form = self.formulario()
        rotulos = [w.cget('text') for w in filhos(form) if isinstance(w, ttk.Label)]
        self.assertIn('Valor de aquisição', rotulos)
        self.assertNotIn('Valor de aquisição (R$)', rotulos)
        entrada = next(w for w in filhos(form) if isinstance(w, ttk.Entry))
        entrada.focus_force()
        self.root.update()
        foco = self.root.focus_get()
        b = botao(form, 'Anexar documentos')
        ajuda = b.balao
        ajuda.agendar()
        self.assertIsNotNone(ajuda.agendado)
        b.event_generate('<Leave>')
        self.assertIsNone(ajuda.agendado)
        ajuda.agendar()
        ajuda.mostrar()
        self.root.update()
        self.assertTrue(ajuda.janela.winfo_ismapped())
        self.assertIn('contratos e protocolos', ajuda.texto)
        self.assertEqual(self.root.grab_current(), form)
        self.assertEqual(self.root.focus_get(), foco)
        with patch.object(filedialog, 'askopenfilenames', return_value=()):
            b.event_generate('<ButtonPress-1>', x=5, y=5)
            self.root.update()
            self.assertIsNone(ajuda.janela)
            b.event_generate('<ButtonRelease-1>', x=5, y=5)
        ajuda.agendar()
        botao(form, 'Cancelar').invoke()
        self.root.update()
        self.assertIsNone(ajuda.agendado)
        identificador = self.banco.salvar(dados_rpv())
        self.programa.mostrar_historico()
        self.programa.abrir_recebimento(identificador)
        self.root.update()
        tela = next(w for w in self.programa.historico.winfo_children() if isinstance(w, tk.Toplevel))
        ajuda = botao(tela, 'Anexar documentos').balao
        self.assertIn('confirmações de transferência', ajuda.texto)
        self.assertIn('extratos bancários', ajuda.texto)
        ajuda.mostrar()
        self.root.update()
        self.assertEqual(self.root.grab_current(), tela)
        self.assertLessEqual(ajuda.janela.winfo_rootx() + ajuda.janela.winfo_width(), self.root.winfo_screenwidth())
        self.programa.alternar_tema()
        self.root.update()
        self.assertEqual(str(ttk.Style().lookup('Ajuda.TLabel', 'foreground')), cores()['texto'])
        ajuda.ocultar()
        botao(tela, 'Cancelar').invoke()

    def test_conta_removida_edita_rpv_e_so_situacao_e_vermelha(self):
        conta = self.banco.contas()[0]
        identificador = self.banco.salvar(dados_rpv(conta_id=conta['id']))
        copia = self.banco.obter(identificador)['conta_snapshot']
        self.programa.mostrar_contas()
        self.root.update()
        janela = self.programa.janela_contas
        linha = str(conta['id'])
        rotulo = janela.situacoes_labels[linha]
        self.assertEqual(str(rotulo.cget('style')), 'ContaIncompleta.TLabel')
        self.assertIn('bold', str(ttk.Style().lookup('ContaIncompleta.TLabel', 'font')))
        self.assertEqual(str(janela.tabela.tag_configure('incompleta', 'foreground')), '')
        janela.tabela.selection_set(linha)
        with patch.object(messagebox, 'askyesno', return_value=True): botao(janela.tela, 'Remover').invoke()
        self.root.update()
        self.assertIsNone(self.banco.obter_conta(conta['id']))
        self.assertEqual(self.banco.obter(identificador)['conta_snapshot'], copia)
        self.banco.remover_contas([c['id'] for c in self.banco.contas()])
        self.programa.formulario(identificador)
        self.root.update()
        tela = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == 'Editar registro')
        escolha = next(w for w in filhos(tela) if isinstance(w, ttk.Combobox))
        self.assertIn('conta removida', escolha.get())
        botao(tela, 'Salvar registro').invoke()
        self.root.update()
        self.assertIsNone(self.banco.obter(identificador)['conta_id'])
        self.assertEqual(self.banco.obter(identificador)['conta_snapshot'], copia)


if __name__ == '__main__':
    unittest.main()
