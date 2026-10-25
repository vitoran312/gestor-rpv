"""Testes reais do Tkinter: GESTOR_RPV_TESTE_UI=1 python -m unittest test_interface -v."""
import os
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, font as tkfont
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app
import estilos
import tela_arquivos
import tela_registro
from componentes import CampoData, CampoMoeda, AreaRolavel
from dados import Banco
from test_contas import banco_com_contas
from tema import cores, PALETAS


def filhos(widget):
    for filho in widget.winfo_children():
        yield filho
        yield from filhos(filho)


def botao(widget, texto):
    return next(w for w in filhos(widget) if isinstance(w, ttk.Button) and w.cget('text') == texto)


def texto_resumo(programa):
    linhas = []
    for cartao,_rotulo in programa.cartoes_resumo:
        titulo,valor = cartao.winfo_children()
        linhas.append(f"{titulo.cget('text')}: {programa.janela.getvar(valor.cget('textvariable'))}")
    return '\n'.join(linhas)


@unittest.skipUnless(os.environ.get('GESTOR_RPV_TESTE_UI') == '1', 'Requer sessão gráfica e GESTOR_RPV_TESTE_UI=1')
class TestInterface(unittest.TestCase):
    def setUp(self):
        if sys.platform == 'win32':
            # No Windows, tk_popup espera o menu ser fechado por um clique real e travaria o teste.
            # Os menus continuam sendo montados; os testes acionam as opções diretamente.
            menu_sem_espera = patch.object(tk.Menu, 'tk_popup', lambda menu, x, y, entry='': None)
            menu_sem_espera.start()
            self.addCleanup(menu_sem_espera.stop)
        self.pasta = tempfile.TemporaryDirectory()
        self.banco = banco_com_contas(Path(self.pasta.name) / 'teste.sqlite3')
        self.root = tk.Tk()
        self.erros = []
        self.root.report_callback_exception = lambda *args: self.erros.append(args)
        with patch.object(app, 'Banco', return_value=self.banco):
            self.programa = app.Aplicativo(self.root)
        if sys.platform == 'win32':
            self.root.state('normal')  # Maximizada, a janela ignoraria os tamanhos pedidos pelos testes de layout.
        self.root.update()

    def tearDown(self):
        self.root.destroy()
        self.pasta.cleanup()
        self.assertEqual(self.erros, [])

    def formulario(self):
        self.programa.formulario()
        self.root.update()
        return next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)
                    and w.title() == 'Nova entrada')

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
        datas[0].variavel.set('01/02/2028')
        datas[1].abrir()
        self.root.update()
        datas[1].ano, datas[1].mes = 2028, 2
        datas[1].desenhar()
        botao(datas[1].calendario, '29').invoke()
        self.root.update()
        self.assertEqual(datas[1].variavel.get(), '29/02/2028')
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
        self.banco.prorrogar(identificador, '2027-01-20')
        self.banco.prorrogar(identificador, '2027-02-20')
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
        self.assertEqual(len(self.banco.prorrogacoes(identificador)), 2)
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
        self.assertEqual(str(ttk.Style().lookup('ContaIncompleta.TLabel','foreground')),cores()['vermelho'])
        self.assertEqual(str(janela.tabela.tag_configure('incompleta','foreground')),'')
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

    def test_menu_historico_seleciona_linha_certa(self):
        dados = dict(nome='Primeiro', aquisicao='2026-10-22', previsto=2000000,
                     custo=1200000, conta='Vitor', previsao='2026-12-20', comissao=None, observacoes='')
        primeiro = self.banco.salvar(dados)
        segundo = self.banco.salvar(dict(dados, nome='Segundo'))
        self.programa.mostrar_historico()
        self.root.update()
        tabela = self.programa.tabela
        tabela.selection_set(str(segundo))
        x, y, largura, altura = tabela.bbox(str(primeiro), 'nome')
        tabela.event_generate('<Button-3>', x=x+5, y=y+5)
        self.root.update()
        self.assertEqual(tabela.selection(), (str(primeiro),))
        menu = next(w for w in tabela.winfo_children() if isinstance(w, tk.Menu))
        menu.invoke('Copiar')
        menu.unpost()
        self.root.update()
        self.assertIn('Primeiro', tabela.clipboard_get())
        tabela.event_generate('<Button-3>', x=x+5, y=y+5)
        self.root.update()
        menu = [w for w in tabela.winfo_children() if isinstance(w, tk.Menu)][-1]
        with patch.object(messagebox, 'askyesno', return_value=False):
            menu.invoke('Excluir')
        menu.unpost()
        self.root.update()
        self.assertEqual(len(self.banco.listar()), 2)

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
        self.assertLessEqual(abs((caixa.winfo_x() + caixa.winfo_width()/2) - (x + largura/2)), 1)
        self.assertEqual(caixa.cget('text'), '22/10/2026')
        self.assertEqual(caixa.cget('style'), 'Recebido.TCheckbutton')
        estilo = ttk.Style()
        self.assertEqual(str(estilo.lookup('Recebido.TCheckbutton', 'foreground')), cores()['verde'])
        self.assertIn('bold', str(estilo.lookup('Recebido.TCheckbutton', 'font')))
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

    def test_botoes_de_linha_acompanham_rolagem_e_busca(self):
        for indice in range(35):
            self.banco.salvar(dict(nome=f'Pessoa {indice}', aquisicao='2026-10-01', previsto=2000000,
                custo=1200000, conta='Vitor', previsao='2026-12-20', comissao=None, observacoes=''))
        self.programa.mostrar_historico()
        self.root.update()
        tabela = self.programa.tabela
        tabela.xview_moveto(1)
        tabela.yview_moveto(1)
        self.root.update()
        ultima = tabela.get_children()[-1]
        self.assertIn(ultima, self.programa.acoes_linhas)
        botao, caixa = self.programa.acoes_linhas[ultima]
        self.assertTrue(botao.winfo_ismapped())
        self.assertTrue(caixa.winfo_ismapped())
        self.programa.busca.set('Pessoa 0')
        self.root.update()
        self.assertEqual(len(tabela.get_children()), 1)
        self.assertEqual(set(self.programa.acoes_linhas), set(tabela.get_children()))

    def test_barra_menus_temas_e_calculadora(self):
        self.programa.mostrar_historico()
        self.root.update()
        menus = self.programa.menus
        self.assertEqual(str(self.root.cget('menu')), str(menus['barra']))
        self.assertEqual(self.programa.tabela.heading('previsto', 'text'), 'Valor Total RPV')
        self.assertEqual(self.programa.tabela.heading('data', 'text'), 'Data de Aquisição')
        textos = [w.cget('text') for w in filhos(self.programa.historico) if isinstance(w, ttk.Label)]
        self.assertFalse(any('Comissão apenas informativa' in texto for texto in textos))
        menus['Arquivo'].invoke('Nova entrada')
        self.root.update()
        form = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == 'Nova entrada')
        textos = [w.cget('text') for w in filhos(form) if isinstance(w, ttk.Label)]
        self.assertIn('Valor Total RPV', textos)
        observacoes = next(w for w in filhos(form) if isinstance(w, tk.Text))
        menus['Exibir'].invoke('Tema claro')
        self.root.update()
        self.assertEqual(self.root.cget('bg'), PALETAS['claro']['fundo'])
        self.assertEqual(form.cget('bg'), PALETAS['claro']['fundo'])
        self.assertEqual(observacoes.cget('bg'), PALETAS['claro']['campo'])
        self.assertEqual(str(ttk.Style().lookup('Treeview', 'fieldbackground')), PALETAS['claro']['campo'])
        form.destroy()
        menus['barra'].invoke('Calculadora')
        self.root.update()
        calculadora = self.programa.calculadora
        self.assertEqual(calculadora.tela.cget('bg'), PALETAS['claro']['fundo'])
        for tecla in ('1', ',', '5', '+', '2', '='):
            botao(calculadora.tela, tecla).invoke()
        self.assertEqual(calculadora.texto.get(), '3,5')
        menus['barra'].invoke('Calculadora')
        self.assertIs(self.programa.calculadora, calculadora)
        menus['Exibir'].invoke('Tema escuro')
        self.root.update()
        self.assertEqual(calculadora.tela.cget('bg'), PALETAS['escuro']['fundo'])
        self.assertEqual(calculadora.texto.get(), '3,5')
        botao(calculadora.tela, 'C').invoke()
        calculadora.tela.focus_force()
        self.root.update()
        for tecla in ('1', '2', 'plus', '3', 'Return'):
            calculadora.tela.event_generate('<KeyPress>', keysym=tecla)
        self.root.update()
        self.assertEqual(calculadora.texto.get(), '15')
        calculadora.tela.destroy()
        menus['barra'].invoke('Calculadora')
        self.root.update()
        self.assertEqual(self.programa.calculadora.texto.get(), '0')

    def test_recebido_sem_texto_sobreposto_apos_desmarcar(self):
        identificador = self.banco.salvar(dict(nome='Teste', aquisicao='2026-10-01', previsto=2000000,
            custo=1200000, conta='Vitor', previsao='2026-12-20', comissao=None, observacoes=''))
        self.banco.registrar_recebimento(identificador, '2026-10-22')
        self.programa.mostrar_historico()
        self.root.update()
        self.programa.tabela.xview_moveto(1)
        self.root.update()
        self.assertEqual(self.programa.tabela.set(str(identificador), 'recebido'), '')
        caixa = self.programa.acoes_linhas[str(identificador)][1]
        caixa.invoke()
        self.root.update()
        tela = next(w for w in self.programa.historico.winfo_children() if isinstance(w, tk.Toplevel))
        with patch.object(messagebox, 'askyesno', return_value=True):
            botao(tela, 'Desmarcar recebimento').invoke()
        self.root.update()
        caixa = self.programa.acoes_linhas[str(identificador)][1]
        self.assertFalse(caixa.estado.get())
        self.assertEqual(caixa.cget('text'), '')
        self.assertEqual(self.programa.tabela.set(str(identificador), 'recebido'), '')
        self.programa.copiar_linha(str(identificador))
        self.assertIn('Não recebido', self.programa.tabela.clipboard_get())
        self.programa.busca.set('Teste')
        self.root.update()
        self.programa.menus['Exibir'].invoke('Tema claro')
        self.root.update()
        self.assertEqual(self.programa.tabela.set(str(identificador), 'recebido'), '')

    def test_lixeira_restauracao_e_historico_pela_interface(self):
        dados = dict(nome='Teste', aquisicao='2026-10-01', previsto=2000000,
            custo=1200000, conta='Vitor', previsao='2026-12-20', comissao=None, observacoes='')
        identificador = self.banco.salvar(dados)
        self.banco.atualizar_previsao(identificador,'2027-01-20')
        self.programa.mostrar_historico()
        self.root.update()
        self.assertNotIn('Investido',texto_resumo(self.programa))
        self.programa.tabela.selection_set(str(identificador))
        with patch.object(messagebox,'askyesno',return_value=True):
            self.programa.excluir()
        self.root.update()
        self.assertEqual(self.programa.tabela.get_children(),())
        botao(self.programa.historico,'Lixeira').invoke()
        self.root.update()
        tela = next(w for w in self.programa.historico.winfo_children() if isinstance(w,tk.Toplevel) and w.title()=='Lixeira')
        tabela = next(w for w in filhos(tela) if isinstance(w,ttk.Treeview))
        tabela.selection_set(str(identificador))
        botao(tela,'Restaurar entradas').invoke()
        self.root.update()
        self.assertEqual(self.programa.tabela.get_children(),(str(identificador),))
        self.assertEqual(self.banco.obter(identificador)['previsao_atual'],'2027-01-20')
        self.assertFalse(hasattr(self.programa,'mostrar_auditoria'))

    def test_ordenacao_colunas_tres_cliques_e_filtro(self):
        ids = []
        for nome,total,dia in (('Álvaro',9000000,1),('Bruno',10000000,2),('Carlos',200000,3)):
            ids.append(str(self.banco.salvar(dict(nome=nome,aquisicao=f'2026-01-0{dia}',previsto=total,
                custo=100,conta='Vitor',previsao='2026-12-20',comissao=None,observacoes=''))))
        self.programa.mostrar_historico()
        self.root.update()
        tabela = self.programa.tabela
        normal = tuple(reversed(ids))
        self.assertEqual(tabela.get_children(),normal)

        def clicar(coluna):
            self.root.tk.call(tabela.heading(coluna,'command'))
            self.root.update()

        clicar('previsto')
        self.assertEqual(tabela.get_children(),(ids[1],ids[0],ids[2]))
        clicar('previsto')
        self.assertEqual(tabela.get_children(),(ids[2],ids[0],ids[1]))
        clicar('previsto')
        self.assertEqual(tabela.get_children(),normal)
        self.assertEqual(tabela.heading('previsto','text'),'Valor Total RPV')
        clicar('nome')
        self.assertEqual(tabela.get_children(),tuple(ids))
        clicar('nome')
        self.assertEqual(tabela.get_children(),normal)
        clicar('nome')
        self.assertIsNone(self.programa.ordenacao)
        clicar('data')
        self.assertEqual(tabela.get_children(),normal)
        clicar('data')
        self.assertEqual(tabela.get_children(),tuple(ids))
        self.programa.busca.set('Bruno')
        self.root.update()
        self.assertEqual(tabela.get_children(),(ids[1],))

    def test_backup_importacao_cancelada_e_confirmada_pela_interface(self):
        dados = dict(nome='Primeira',aquisicao='2026-10-01',previsto=2000000,
                     custo=1200000,conta='Vitor',previsao='2026-12-20',comissao=None,observacoes='')
        self.banco.salvar(dados)
        botoes_iniciais = [w.cget('text') for w in filhos(self.root) if isinstance(w,ttk.Button)]
        self.assertNotIn('Backup',botoes_iniciais)
        self.assertNotIn('Lixeira',botoes_iniciais)
        self.programa.mostrar_historico()
        self.root.update()
        botoes = [w.cget('text') for w in filhos(self.programa.historico) if isinstance(w,ttk.Button)]
        self.assertNotIn('Backup',botoes)
        self.assertNotIn('Importar dados',botoes)
        pasta = Path(self.pasta.name)/'exportados'
        with patch.object(filedialog,'askdirectory',return_value=str(pasta)), patch.object(messagebox,'showinfo'):
            self.programa.menus['Arquivo'].invoke('Fazer backup')
        arquivo = next(pasta.glob('*.rpvbackup'))
        self.banco.salvar(dict(dados,nome='Segunda'))
        with patch.object(filedialog,'askopenfilename',return_value=str(arquivo)), patch.object(messagebox,'askyesno',return_value=False):
            self.programa.menus['Arquivo'].invoke('Importar dados')
        self.assertEqual(len(self.banco.listar()),2)
        with patch.object(filedialog,'askopenfilename',return_value=str(arquivo)), patch.object(messagebox,'askyesno',return_value=True), patch.object(messagebox,'showinfo'):
            self.programa.menus['Arquivo'].invoke('Importar dados')
        self.root.update()
        self.assertEqual(len(self.banco.listar()),1)
        self.assertEqual(self.banco.listar()[0]['nome'],'Primeira')
        self.assertEqual(len(self.programa.tabela.get_children()),1)

    def test_selecao_mouse_teclado_exclusao_e_restauracao_em_lote(self):
        from test_contas import dados_rpv
        ids = [str(self.banco.salvar(dados_rpv(nome=f'Pessoa {n}'))) for n in range(4)]
        self.programa.mostrar_historico()
        self.root.geometry('1100x900')
        self.root.update()
        tabela = self.programa.tabela
        linhas = list(tabela.get_children())
        def clicar(linha, estado=0):
            x,y,w,h = tabela.bbox(linha,'nome')
            tabela.event_generate('<ButtonPress-1>',x=x+8,y=y+h//2,state=estado)
            tabela.event_generate('<ButtonRelease-1>',x=x+8,y=y+h//2,state=estado)
            self.root.update()
        clicar(linhas[0])
        clicar(linhas[2],4)
        self.assertEqual(set(tabela.selection()),{linhas[0],linhas[2]})
        clicar(linhas[3],1)
        self.assertEqual(set(tabela.selection()),{linhas[2],linhas[3]})
        clicar(linhas[0])
        x,y,w,h = tabela.bbox(linhas[2],'nome')
        tabela.event_generate('<B1-Motion>',x=x+8,y=y+h//2,state=256)
        tabela.event_generate('<ButtonRelease-1>',x=x+8,y=y+h//2)
        self.root.update()
        self.assertEqual(set(tabela.selection()),set(linhas[:3]))
        # O arrasto também pode começar no espaço vazio abaixo das linhas.
        tabela.event_generate('<ButtonPress-1>',x=20,y=tabela.winfo_height()-20)
        for linha in reversed(linhas[1:]):
            x,y,w,h = tabela.bbox(linha,'nome')
            tabela.event_generate('<B1-Motion>',x=x+8,y=y+h//2,state=256)
        tabela.event_generate('<ButtonRelease-1>',x=x+8,y=y+h//2)
        self.root.update()
        self.assertEqual(set(tabela.selection()),set(linhas[1:]))
        tabela.focus_force()
        tabela.event_generate('<KeyPress>',keysym='Home')
        tabela.event_generate('<KeyPress>',keysym='Down',state=1)
        self.root.update()
        self.assertEqual(set(tabela.selection()),set(linhas[:2]))
        with patch.object(messagebox,'askyesno',return_value=True):
            tabela.event_generate('<KeyPress>',keysym='Delete')
            self.root.update()
        self.assertEqual(len(self.banco.listar_lixeira()),2)
        self.programa.mostrar_lixeira()
        self.root.update()
        tela = next(w for w in self.programa.historico.winfo_children()
                    if isinstance(w,tk.Toplevel) and w.title()=='Lixeira')
        restaurar = botao(tela,'Restaurar entradas')
        self.assertTrue(restaurar.winfo_ismapped())
        self.assertGreater(restaurar.winfo_width(),150)
        self.assertLess(restaurar.winfo_rooty()+restaurar.winfo_height(),tela.winfo_rooty()+tela.winfo_height()+1)
        estilo = ttk.Style(self.root)
        self.assertNotEqual(estilo.lookup('Restaurar.TButton','foreground'),estilo.lookup('Restaurar.TButton','background'))
        lixeira = next(w for w in filhos(tela) if isinstance(w,ttk.Treeview))
        lixeira.focus_force()
        self.root.update()
        lixeira.event_generate('<Control-a>')
        lixeira.event_generate('<Return>')
        self.root.update()
        self.assertEqual(len(self.banco.listar()),4)
        self.assertEqual(str(self.programa.botao_lixeira.cget('compound')),'image')

    def test_anexar_visualizar_salvar_reabrir_e_cancelar_documentos(self):
        from test_contas import dados_rpv
        identificador = self.banco.salvar(dados_rpv())
        arquivo = Path(self.pasta.name)/'contrato.pdf'
        arquivo.write_bytes(b'%PDF-1.4 teste')
        self.programa.formulario(identificador)
        self.root.update()
        form = next(w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel))
        with patch.object(filedialog,'askopenfilenames',return_value=(str(arquivo),)):
            botao(form,'Anexar documentos').invoke()
            botao(form,'Anexar documentos').invoke()
        self.root.update()
        self.assertEqual(self.banco.documentos(identificador),[])
        documentos = next(w for w in filhos(form) if isinstance(w,ttk.Button)
                          and w.cget('textvariable') and self.root.getvar(w.cget('textvariable'))=='Documentos (1)')
        documentos.invoke()
        self.root.update()
        janela = next(w for w in form.winfo_children() if isinstance(w,tk.Toplevel))
        lista = next(w for w in filhos(janela) if isinstance(w,ttk.Treeview))
        self.assertEqual(len(lista.get_children()),1)
        lista.selection_set(lista.get_children()[0])
        with patch.object(tela_registro,'abrir_arquivo') as abrir:
            botao(janela,'Abrir documento').invoke()
            abrir.assert_called_once_with(arquivo.resolve())
        botao(janela,'Fechar').invoke()
        botao(form,'Salvar registro').invoke()
        self.root.update()
        self.assertEqual(len(self.banco.documentos(identificador)),1)
        arquivo.unlink()
        self.programa.formulario(identificador)
        self.root.update()
        form = next(w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel))
        documento = self.banco.documentos(identificador)[0]
        self.assertTrue(self.banco.caminho_documento(documento['id']).exists())
        botao(form,'Cancelar').invoke()

    def test_comprovantes_recebimento_salvar_cancelar_e_reabrir(self):
        from test_contas import dados_rpv
        identificador = self.banco.salvar(dados_rpv())
        entrada = Path(self.pasta.name)/'contrato.pdf'
        entrada.write_bytes(b'%PDF contrato')
        self.banco.salvar(dados_rpv(),identificador,anexos=[entrada])
        recibo = Path(self.pasta.name)/'recibo.pdf'
        recibo.write_bytes(b'%PDF recibo')
        self.programa.mostrar_historico()
        self.root.update()
        def abrir():
            self.programa.abrir_recebimento(identificador)
            self.root.update()
            return next(w for w in self.programa.historico.winfo_children()
                        if isinstance(w,tk.Toplevel) and w.title()=='Recebimento')
        tela = abrir()
        with patch.object(filedialog,'askopenfilenames',return_value=(str(recibo),)):
            botao(tela,'Anexar documentos').invoke()
        botao(tela,'Cancelar').invoke()
        self.assertEqual(self.banco.documentos(identificador,tipo='recebimento'),[])
        tela = abrir()
        with patch.object(filedialog,'askopenfilenames',return_value=(str(recibo),)):
            botao(tela,'Anexar documentos').invoke()
        botao(tela,'Salvar recebimento').invoke()
        self.root.update()
        self.assertEqual(len(self.banco.documentos(identificador)),1)
        recibos = self.banco.documentos(identificador,tipo='recebimento')
        self.assertEqual(len(recibos),1)
        recibo.unlink()
        tela = abrir()
        documentos = next(w for w in filhos(tela) if isinstance(w,ttk.Button)
                          and w.cget('textvariable') and self.root.getvar(w.cget('textvariable'))=='Documentos (1)')
        documentos.invoke()
        self.root.update()
        janela = next(w for w in tela.winfo_children() if isinstance(w,tk.Toplevel))
        lista = next(w for w in filhos(janela) if isinstance(w,ttk.Treeview))
        self.assertEqual([lista.item(i,'values')[0] for i in lista.get_children()],['recibo.pdf'])
        lista.selection_set(lista.get_children()[0])
        with patch.object(tela_registro,'abrir_arquivo') as abrir_arquivo:
            botao(janela,'Abrir documento').invoke()
            abrir_arquivo.assert_called_once_with(self.banco.caminho_documento(recibos[0]['id']))
        botao(janela,'Fechar').invoke()
        with patch.object(messagebox,'askyesno',return_value=True):
            botao(tela,'Desmarcar recebimento').invoke()
        self.root.update()
        self.assertIsNone(self.banco.obter(identificador)['recebimento'])
        self.assertTrue(self.banco.caminho_documento(recibos[0]['id']).exists())

    def test_prazo_calcula_data_sincroniza_calendario_valida_e_persiste(self):
        form = self.formulario()
        prazo = next(w for w in filhos(form) if isinstance(w,ttk.Entry) and w.winfo_name()=='prazo_dias')
        datas = [w for w in filhos(form) if isinstance(w,CampoData)]
        datas[0].variavel.set('28/02/2028')
        self.assertTrue(prazo.instate(['disabled']))
        self.assertFalse(datas[1].botao.instate(['disabled']))
        modos = {w.cget('value'):w for w in filhos(form) if isinstance(w,ttk.Radiobutton)}
        modos['dias'].invoke()
        self.assertFalse(prazo.instate(['disabled']))
        self.assertTrue(datas[1].entrada.instate(['disabled']))
        self.assertTrue(datas[1].botao.instate(['disabled']))
        datas[1].abrir()
        self.assertIsNone(datas[1].calendario)
        prazo.insert(0,'1')
        self.root.update()
        self.assertEqual(datas[1].variavel.get(),'29/02/2028')
        datas[0].variavel.set('28/12/2028')
        self.assertEqual(datas[1].variavel.get(),'29/12/2028')
        prazo.delete(0,'end')
        prazo.insert(0,'10')
        self.assertEqual(datas[1].variavel.get(),'07/01/2029')
        resultado = next(w for w in filhos(form) if w.winfo_name()=='data_calculada')
        self.assertEqual(self.root.getvar(resultado.cget('textvariable')),'07/01/2029')
        anterior = datas[1].variavel.get()
        datas[1].entrada.insert(0,'999')
        self.assertEqual(datas[1].variavel.get(),anterior)
        modos['calendario'].invoke()
        self.assertTrue(prazo.instate(['disabled']))
        prazo.insert(0,'999')
        self.assertEqual(prazo.get(),'10')
        datas[1].abrir()
        self.root.update()
        datas[1].selecionar(date(2029,1,10))
        self.assertEqual(prazo.get(),'13')
        nome = next(w for w in filhos(form) if isinstance(w,ttk.Entry))
        nome.insert(0,'teste prazo')
        moedas = [w for w in filhos(form) if isinstance(w,CampoMoeda)]
        moedas[0].variavel.set('20.000,00')
        moedas[1].variavel.set('12.000,00')
        modos['dias'].invoke()
        for invalido in ('','abc','-1','1,5','999999999999999'):
            prazo.delete(0,'end')
            prazo.insert(0,invalido)
            with patch.object(messagebox,'showerror') as erro:
                botao(form,'Salvar registro').invoke()
                erro.assert_called_once()
            self.assertEqual(self.banco.listar(),[])
        prazo.delete(0,'end')
        prazo.insert(0,'10')
        modos['calendario'].invoke()
        datas[1].variavel.set('31/02/2029')
        with patch.object(messagebox,'showerror') as erro:
            botao(form,'Salvar registro').invoke()
            erro.assert_called_once()
        self.assertEqual(self.banco.listar(),[])
        datas[1].variavel.set('07/01/2029')
        botao(form,'Salvar registro').invoke()
        self.root.update()
        registro = self.banco.listar()[0]
        self.assertEqual(registro['previsao'],'2029-01-07')
        self.programa.formulario(registro['id'])
        self.root.update()
        form = next(w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel))
        prazo = next(w for w in filhos(form) if isinstance(w,ttk.Entry) and w.winfo_name()=='prazo_dias')
        self.assertEqual(prazo.get(),'10')

    def test_comissao_e_saldos_recebimento_filtro_lixeira_e_colunas(self):
        from test_contas import dados_rpv
        recebido = self.banco.salvar(dados_rpv(nome='Recebido',comissao=50000))
        aberto = self.banco.salvar(dados_rpv(nome='Aberto',previsto=1000000,custo=700000))
        self.banco.registrar_recebimento(recebido,'2026-10-22')
        self.programa.mostrar_historico()
        self.root.update()
        tabela = self.programa.tabela
        self.assertEqual(tabela['columns'][2:5],('custo','comissao','previsto'))
        self.assertEqual(tabela.set(str(recebido),'comissao'),'R$ 500,00')
        self.assertEqual(tabela.set(str(aberto),'comissao'),'R$ 0,00')
        texto = texto_resumo(self.programa)
        self.assertIn('Registros: 2',texto)
        self.assertIn('Lucro previsto: R$ 11.000,00',texto)
        self.assertIn('Lucro realizado: R$ 8.000,00',texto)
        self.assertIn('Capital investido em aberto: R$ 7.000,00',texto)
        self.programa.ordenar_coluna('comissao')
        self.assertEqual(tabela.get_children(),(str(recebido),str(aberto)))
        self.programa.ordenar_coluna('comissao')
        self.assertEqual(tabela.get_children(),(str(aberto),str(recebido)))
        self.programa.busca.set('Aberto')
        self.root.update()
        self.assertIn('Lucro realizado: R$ 0,00',texto_resumo(self.programa))
        self.programa.busca.set('')
        self.banco.excluir(aberto)
        self.programa.atualizar()
        self.assertIn('Capital investido em aberto: R$ 0,00',texto_resumo(self.programa))
        self.banco.restaurar(aberto)
        self.banco.registrar_recebimento(recebido,None)
        self.programa.atualizar()
        self.root.update()
        self.assertIn('Capital investido em aberto: R$ 19.000,00',texto_resumo(self.programa))
        self.assertIn('Lucro realizado: R$ 0,00',texto_resumo(self.programa))
        # A coluna adicionada não desloca as ações de calendário/recebimento.
        tabela.xview_moveto(1)
        self.root.update()
        for coluna,titulo in (('previsao_atual','Previsão atual'),('recebido','Recebimento')):
            x,y,w,h = tabela.bbox(str(aberto),coluna)
            tabela.event_generate('<ButtonPress-1>',x=x+w//2,y=y+h//2)
            tabela.event_generate('<ButtonRelease-1>',x=x+w//2,y=y+h//2)
            self.root.update()
            janela = next(w for w in self.programa.historico.winfo_children()
                          if isinstance(w,tk.Toplevel) and w.title()==titulo)
            botao(janela,'Cancelar').invoke() if titulo=='Recebimento' else janela.destroy()
            self.root.update()
        self.root.geometry('900x620')
        self.root.update()
        self.assertTrue(self.programa.botao_lixeira.winfo_ismapped())
        self.assertLess(self.programa.botao_lixeira.winfo_rootx()+self.programa.botao_lixeira.winfo_width(),
                        self.root.winfo_rootx()+self.root.winfo_width()+1)

    def test_layout_responsivo_indicadores_e_botoes_e_salvamento_por_dias(self):
        from test_contas import dados_rpv
        identificador = self.banco.salvar(dados_rpv())
        self.programa.mostrar_historico()
        self.root.update()
        for largura,colunas in ((1600,4),(900,2)):
            self.root.geometry(f'{largura}x650')
            self.root.update()
            self.assertEqual(self.programa.colunas_resumo,colunas)
            cartoes = [c for c,_ in self.programa.cartoes_resumo]
            self.assertLessEqual(max(c.winfo_width() for c in cartoes)-min(c.winfo_width() for c in cartoes),1)
            for inicio in range(0,4,colunas):
                self.assertEqual(len({c.winfo_rooty() for c in cartoes[inicio:inicio+colunas]}),1)
                valores = [c.winfo_children()[1] for c in cartoes[inicio:inicio+colunas]]
                self.assertEqual(len({v.winfo_rooty() for v in valores}),1)
            self.assertGreaterEqual(self.programa.botao_lixeira.winfo_rootx(),
                                    self.programa.resumo.winfo_rootx()+self.programa.resumo.winfo_width())
        self.programa.formulario(identificador)
        self.root.update()
        form = next(w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel) and w.title()=='Editar registro')
        botoes = [botao(form,t) for t in ('Dados de recebimento','Cancelar','Salvar registro')]
        self.assertEqual(len({b.winfo_rooty() for b in botoes}),1)
        self.assertEqual(len({b.winfo_height() for b in botoes}),1)
        self.assertLessEqual(max(b.winfo_width() for b in botoes)-min(b.winfo_width() for b in botoes),1)
        modos = {w.cget('value'):w for w in filhos(form) if isinstance(w,ttk.Radiobutton)}
        modos['dias'].invoke()
        prazo = next(w for w in filhos(form) if w.winfo_name()=='prazo_dias')
        prazo.delete(0,'end')
        prazo.insert(0,'30')
        datas = [w for w in filhos(form) if isinstance(w,CampoData)]
        self.assertTrue(datas[1].entrada.instate(['disabled']))
        self.programa.menus['Exibir'].invoke('Tema claro')
        self.root.update()
        self.assertTrue(datas[1].entrada.instate(['disabled']))
        self.assertEqual(str(ttk.Style().lookup('ResumoRealizado.TLabel','foreground')),PALETAS['claro']['verde'])
        botao(form,'Salvar registro').invoke()
        self.root.update()
        self.assertEqual(self.banco.obter(identificador)['previsao'],'2026-11-21')

    def test_previsao_legivel_com_mouse_nos_dois_temas(self):
        form = self.formulario()
        opcoes = [w for w in filhos(form) if isinstance(w,ttk.Radiobutton)]
        self.assertEqual(len(opcoes),2)
        assinatura = [w.cget('text') for w in filhos(self.root) if isinstance(w,ttk.Label)]
        self.assertIn(f'Vitoran Tech · v{app.VERSAO}',assinatura)
        def luminancia(cor):
            canais = [n/65535 for n in self.root.winfo_rgb(cor)]
            canais = [n/12.92 if n<=0.04045 else ((n+0.055)/1.055)**2.4 for n in canais]
            return sum(a*b for a,b in zip(canais,(0.2126,0.7152,0.0722)))
        estilo = ttk.Style(self.root)
        for modo in ('escuro','claro'):
            self.programa.modo_tema.set(modo)
            self.programa.configurar_tema()
            self.root.update()
            self.assertEqual(str(estilo.lookup('DataCalculada.TLabel','background',('disabled',))),form.cget('bg'))
            for opcao in opcoes:
                opcao.event_generate('<Motion>',x=5,y=5,warp=True)
                self.root.update()
                opcao.event_generate('<Enter>',x=5,y=5)
                self.root.update()
                self.assertTrue(opcao.instate(['active']))
                for pressionado in (False,True):
                    if pressionado:
                        opcao.state(['pressed'])
                        self.root.update()
                        self.assertTrue(opcao.instate(['pressed']))
                    estado = opcao.state()
                    fundo = str(estilo.lookup('TRadiobutton','background',estado))
                    frente = str(estilo.lookup('TRadiobutton','foreground',estado))
                    a,b = sorted((luminancia(fundo),luminancia(frente)))
                    self.assertGreaterEqual((b+0.05)/(a+0.05),4.5)
                    if modo=='escuro':
                        self.assertNotEqual(self.root.winfo_rgb(fundo),(65535,65535,65535))
                opcao.state(['!pressed'])
                opcao.invoke()
                opcao.event_generate('<Leave>')
                self.root.update()

    def test_inicio_pro_acoes_visiveis_e_temas_sem_recriar_imagens(self):
        self.assertEqual(self.programa.modo_tema.get(),'claro')
        self.assertEqual([w for w in filhos(self.root) if isinstance(w,ttk.Entry)],[])
        for largura,colunas in ((1286,3),(944,1)):
            self.root.geometry(f'{largura}x668')
            self.root.update()
            self.assertEqual(self.programa.colunas_inicio,colunas)
            for texto in ('Nova entrada','Minhas operações','Contas de recebimento','Sair'):
                b=botao(self.root,texto)
                self.assertTrue(b.winfo_ismapped())
                self.assertGreaterEqual(b.winfo_rooty(),self.root.winfo_rooty())
                self.assertLessEqual(b.winfo_rooty()+b.winfo_height(),self.root.winfo_rooty()+self.root.winfo_height())
                self.assertLessEqual(b.winfo_rootx()+b.winfo_width(),self.root.winfo_rootx()+self.root.winfo_width())
        self.programa.alternar_tema()
        self.root.update()
        self.assertEqual(self.programa.texto_alternar_tema.get(),'Modo claro')
        imagens = self.root.tk.call('image','names')
        self.programa.alternar_tema()
        self.programa.alternar_tema()
        self.root.update()
        self.assertEqual(len(self.root._superficies_pro),2)
        # Ícones de Canvas não criam novas imagens; as superfícies são reutilizadas.
        self.assertEqual(set(self.root.tk.call('image','names')),set(imagens))

    def test_formularios_rolaveis_com_acoes_fixas_em_tela_menor(self):
        with patch.object(tk.Misc,'winfo_screenheight',return_value=768):
            form=self.formulario()
            area=next(w for w in filhos(form) if isinstance(w,AreaRolavel))
            self.assertLess(area.canvas.yview()[1],1)
            antes=area.canvas.yview()[0]
            area.canvas.event_generate('<MouseWheel>',delta=-120,x=10,y=10,
                rootx=area.canvas.winfo_rootx()+10,rooty=area.canvas.winfo_rooty()+10)
            self.root.update()
            self.assertGreater(area.canvas.yview()[0],antes)
            observacoes=next(w for w in filhos(form) if isinstance(w,tk.Text))
            observacoes.focus_force()
            self.root.update()
            self.assertGreaterEqual(observacoes.winfo_rooty(),area.canvas.winfo_rooty())
            self.assertLessEqual(observacoes.winfo_rooty()+observacoes.winfo_height(),area.canvas.winfo_rooty()+area.canvas.winfo_height())
            salvar=botao(form,'Salvar registro')
            self.assertTrue(salvar.winfo_ismapped())
            self.assertLessEqual(salvar.winfo_rooty()+salvar.winfo_height(),form.winfo_rooty()+form.winfo_height())
            self.programa.alternar_tema()
            self.root.update()
            self.assertEqual(area.canvas.cget('bg'),cores()['fundo'])
            botao(form,'Cancelar').invoke()
            self.programa.mostrar_contas()
            self.root.update()
            janela=self.programa.janela_contas
            botao(janela.tela,'Cadastrar nova conta').invoke()
            self.root.update()
            conta=next(w for w in janela.tela.winfo_children() if isinstance(w,tk.Toplevel))
            area=next(w for w in filhos(conta) if isinstance(w,AreaRolavel))
            self.assertLess(area.canvas.yview()[1],1)
            salvar=botao(conta,'Salvar conta')
            self.assertLessEqual(salvar.winfo_rooty()+salvar.winfo_height(),conta.winfo_rooty()+conta.winfo_height())
            botao(conta,'Cancelar').invoke()

    def test_baloes_documentos_distintos_preservam_modal_e_cancelam_ao_sair(self):
        form=self.formulario()
        rotulos=[w.cget('text') for w in filhos(form) if isinstance(w,ttk.Label)]
        self.assertIn('Valor de aquisição',rotulos)
        self.assertNotIn('Valor de aquisição (R$)',rotulos)
        entrada=next(w for w in filhos(form) if isinstance(w,ttk.Entry))
        entrada.focus_force()
        self.root.update()
        foco=self.root.focus_get()
        b=botao(form,'Anexar documentos')
        ajuda=b.balao
        ajuda.agendar()
        self.assertIsNotNone(ajuda.agendado)
        b.event_generate('<Leave>')
        self.assertIsNone(ajuda.agendado)
        ajuda.agendar()
        ajuda.mostrar()
        self.root.update()
        self.assertTrue(ajuda.janela.winfo_ismapped())
        self.assertIn('contratos e protocolos',ajuda.texto)
        self.assertEqual(self.root.grab_current(),form)
        self.assertEqual(self.root.focus_get(),foco)
        with patch.object(filedialog,'askopenfilenames',return_value=()):
            b.event_generate('<ButtonPress-1>',x=5,y=5)
            self.root.update()
            self.assertIsNone(ajuda.janela)
            b.event_generate('<ButtonRelease-1>',x=5,y=5)
        ajuda.agendar()
        botao(form,'Cancelar').invoke()
        self.root.update()
        self.assertIsNone(ajuda.agendado)
        from test_contas import dados_rpv
        identificador=self.banco.salvar(dados_rpv())
        self.programa.mostrar_historico()
        self.programa.abrir_recebimento(identificador)
        self.root.update()
        tela=next(w for w in self.programa.historico.winfo_children() if isinstance(w,tk.Toplevel))
        ajuda=botao(tela,'Anexar documentos').balao
        self.assertIn('confirmações de transferência',ajuda.texto)
        self.assertIn('extratos bancários',ajuda.texto)
        ajuda.mostrar()
        self.root.update()
        self.assertEqual(self.root.grab_current(),tela)
        self.assertLessEqual(ajuda.janela.winfo_rootx()+ajuda.janela.winfo_width(),self.root.winfo_screenwidth())
        self.programa.alternar_tema()
        self.root.update()
        self.assertEqual(str(ttk.Style().lookup('Ajuda.TLabel','foreground')),cores()['texto'])
        ajuda.ocultar()
        botao(tela,'Cancelar').invoke()

    def test_temas_reutilizados_icones_e_fonte_das_contas(self):
        textos=[w.cget('text') for w in filhos(self.root) if isinstance(w,ttk.Label)]
        self.assertFalse(any(t in ('01','02','03') or t.startswith('VITORAN') for t in textos))
        claro=str(self.programa.botao_alternar_tema.cget('image'))
        self.assertTrue(claro)
        self.programa.botao_alternar_tema.invoke()
        self.root.update()
        escuro=str(self.programa.botao_alternar_tema.cget('image'))
        self.assertNotEqual(claro,escuro)
        with patch.object(estilos,'aplicar_superficies',side_effect=AssertionError('Superfícies não devem ser recriadas')), \
             patch('visual.tkfont.families',side_effect=AssertionError('Fontes não devem ser enumeradas novamente')):
            for _ in range(3):
                self.programa.alternar_tema()
                self.root.update()
        self.assertEqual(str(self.programa.botao_alternar_tema.cget('image')),claro)
        self.programa.mostrar_contas()
        self.root.update()
        tabela=self.programa.janela_contas.tabela
        estilo=ttk.Style()
        fonte=tkfont.Font(font=estilo.lookup(tabela.cget('style'),'font'))
        self.assertEqual(fonte.actual('size'),12)
        self.assertGreaterEqual(int(estilo.lookup(tabela.cget('style'),'rowheight')),40)

    def test_lixeira_exclui_permanentemente_apos_confirmacao(self):
        from test_contas import dados_rpv
        arquivo=Path(self.pasta.name)/'contrato.pdf'
        arquivo.write_bytes(b'%PDF exemplo')
        identificador=self.banco.salvar(dados_rpv(),anexos=[arquivo])
        caminho=self.banco.caminho_documento(self.banco.documentos(identificador)[0]['id'])
        self.banco.excluir(identificador)
        self.programa.mostrar_historico()
        self.programa.mostrar_lixeira()
        self.root.update()
        tela=next(w for w in self.programa.historico.winfo_children() if isinstance(w,tk.Toplevel))
        tabela=next(w for w in filhos(tela) if isinstance(w,ttk.Treeview))
        tabela.selection_set(str(identificador))
        with patch.object(messagebox,'askyesno',return_value=False):
            botao(tela,'Excluir permanentemente').invoke()
        self.assertIsNotNone(self.banco.obter(identificador))
        with patch.object(messagebox,'askyesno',return_value=True):
            botao(tela,'Excluir permanentemente').invoke()
        self.root.update()
        self.assertIsNone(self.banco.obter(identificador))
        self.assertFalse(caminho.exists())
        self.assertTrue(arquivo.exists())

    def test_remover_anexos_salvos_de_entrada_e_recebimento(self):
        from test_contas import dados_rpv
        arquivo=Path(self.pasta.name)/'comprovante.pdf'
        arquivo.write_bytes(b'%PDF exemplo')
        identificador=self.banco.salvar(dados_rpv(),anexos=[arquivo])
        self.banco.registrar_recebimento(identificador,'2026-10-22',anexos=[arquivo])
        self.programa.mostrar_historico()
        for tipo in ('entrada','recebimento'):
            if tipo=='entrada':self.programa.formulario(identificador)
            else:self.programa.abrir_recebimento(identificador)
            self.root.update()
            dono=self.root if tipo=='entrada' else self.programa.historico
            tela=next(w for w in dono.winfo_children() if isinstance(w,tk.Toplevel) and w.title() in ('Editar registro','Recebimento'))
            abrir=next(w for w in filhos(tela) if isinstance(w,ttk.Button) and w.cget('textvariable') and self.root.getvar(w.cget('textvariable'))=='Documentos (1)')
            abrir.invoke()
            self.root.update()
            documentos=next(w for w in tela.winfo_children() if isinstance(w,tk.Toplevel))
            lista=next(w for w in filhos(documentos) if isinstance(w,ttk.Treeview))
            lista.selection_set(lista.get_children()[0])
            with patch.object(messagebox,'askyesno',return_value=False):botao(documentos,'Remover documento').invoke()
            self.assertEqual(len(self.banco.documentos(identificador,tipo)),1)
            with patch.object(messagebox,'askyesno',return_value=True):botao(documentos,'Remover documento').invoke()
            self.root.update()
            self.assertEqual(self.banco.documentos(identificador,tipo),[])
            self.assertEqual(lista.get_children(),())
            botao(documentos,'Fechar').invoke()
            botao(tela,'Cancelar').invoke()
        self.assertTrue(arquivo.exists())

    def test_conta_removida_edita_rpv_e_so_situacao_e_vermelha(self):
        from test_contas import dados_rpv
        conta=self.banco.contas()[0]
        identificador=self.banco.salvar(dados_rpv(conta_id=conta['id']))
        copia=self.banco.obter(identificador)['conta_snapshot']
        self.programa.mostrar_contas()
        self.root.update()
        janela=self.programa.janela_contas
        linha=str(conta['id'])
        rotulo=janela.situacoes_labels[linha]
        self.assertEqual(str(rotulo.cget('style')),'ContaIncompleta.TLabel')
        self.assertIn('bold',str(ttk.Style().lookup('ContaIncompleta.TLabel','font')))
        self.assertEqual(str(janela.tabela.tag_configure('incompleta','foreground')),'')
        janela.tabela.selection_set(linha)
        with patch.object(messagebox,'askyesno',return_value=True):botao(janela.tela,'Remover').invoke()
        self.root.update()
        self.assertIsNone(self.banco.obter_conta(conta['id']))
        self.assertEqual(self.banco.obter(identificador)['conta_snapshot'],copia)
        self.banco.remover_contas([c['id'] for c in self.banco.contas()])
        self.programa.formulario(identificador)
        self.root.update()
        tela=next(w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel) and w.title()=='Editar registro')
        escolha=next(w for w in filhos(tela) if isinstance(w,ttk.Combobox))
        self.assertIn('conta removida',escolha.get())
        botao(tela,'Salvar registro').invoke()
        self.root.update()
        self.assertIsNone(self.banco.obter(identificador)['conta_id'])
        self.assertEqual(self.banco.obter(identificador)['conta_snapshot'],copia)

    def test_sobre_marca_versao_tema_e_janela_unica(self):
        self.assertTrue(self.root._icones_vitoran)
        self.assertEqual(self.root._marca_vitoran.width(),128)
        botao(self.root,'Sobre').invoke()
        self.root.update()
        tela=self.programa.sobre
        textos=[w.cget('text') for w in filhos(tela) if isinstance(w,ttk.Label)]
        for texto in ('Gestor de RPV','Vitoran Tech','Desenvolvido por Vitor Alves Nascimento',f'Versão {app.VERSAO}'):
            self.assertIn(texto,textos)
        fechar=botao(tela,'Fechar')
        self.assertTrue(fechar.winfo_ismapped())
        self.assertLessEqual(fechar.winfo_rooty()+fechar.winfo_height(),tela.winfo_rooty()+tela.winfo_height())
        self.programa.alternar_tema()
        self.root.update()
        self.assertEqual(tela.cget('bg'),PALETAS['escuro']['fundo'])
        self.programa.mostrar_historico()
        self.programa.menus['Ajuda'].invoke('Sobre o Gestor de RPV')
        self.root.update()
        self.assertIs(self.programa.sobre,tela)
        fechar.invoke()
        self.programa.menus['Ajuda'].invoke('Sobre o Gestor de RPV')
        self.root.update()
        self.assertIsNot(self.programa.sobre,tela)
        # Sem gerenciador de janelas, o foco do teclado segue o ponteiro, que outro teste pode ter movido.
        self.programa.sobre.focus_force()
        self.root.update()
        self.programa.sobre.event_generate('<Escape>')
        self.root.update()
        self.assertFalse(self.programa.sobre.winfo_exists())

    def test_lembrete_backup_no_inicio_e_historico_ate_exportar(self):
        self.assertIn('ainda não fez',self.programa.texto_aviso_backup.get())
        with patch.object(filedialog,'askdirectory',return_value=''):
            self.programa.exportar_backup()
        self.assertIn('ainda não fez',self.programa.texto_aviso_backup.get())
        self.banco.registrar_backup('2020-01-01T12:00:00')
        self.root.event_generate('<FocusIn>')
        self.root.update()
        self.assertIn('dias sem backup',self.programa.texto_aviso_backup.get())
        self.programa.mostrar_historico()
        self.root.update()
        self.assertIn('dias sem backup',self.programa.texto_aviso_backup.get())
        destino=str(Path(self.pasta.name)/'exportados')
        with patch.object(filedialog,'askdirectory',return_value=destino),patch.object(messagebox,'showerror'),patch.object(tela_arquivos,'criar_backup',side_effect=OSError('Sem espaço')):
            self.programa.exportar_backup()
        self.assertIn('dias sem backup',self.programa.texto_aviso_backup.get())
        self.programa.historico.destroy()
        with patch.object(filedialog,'askdirectory',return_value=destino),patch.object(messagebox,'showinfo'):
            self.programa.aviso_backup_inicio.event_generate('<Button-1>')
            self.root.update()
        self.assertEqual(self.programa.texto_aviso_backup.get(),'')
        self.assertTrue(list(Path(destino).glob('*.rpvbackup')))
        self.programa.mostrar_historico()
        self.root.update()
        self.assertEqual(self.programa.texto_aviso_backup.get(),'')

    def test_menu_abre_pasta_documentos_sem_alterar_anexos(self):
        from test_contas import dados_rpv
        self.programa.mostrar_historico()
        pasta=self.banco.caminho.parent/'documentos'
        self.assertFalse(pasta.exists())
        with patch.object(tela_arquivos,'abrir_pasta') as abrir:
            self.programa.menus['Arquivo'].invoke('Abrir pasta dos documentos')
        abrir.assert_called_once_with(pasta)
        self.assertTrue(pasta.is_dir())
        pdf=Path(self.pasta.name)/'contrato.pdf'
        pdf.write_bytes(b'%PDF-exemplo')
        i=self.banco.salvar(dados_rpv(),anexos=[pdf])
        documento=self.banco.documentos(i)[0]
        with patch.object(tela_arquivos,'abrir_pasta',side_effect=OSError('Explorador indisponível')),patch.object(messagebox,'showerror') as erro:
            self.programa.menus['Arquivo'].invoke('Abrir pasta dos documentos')
        erro.assert_called_once()
        self.assertEqual(self.banco.caminho_documento(documento['id']).read_bytes(),b'%PDF-exemplo')

    def test_fontes_indicadores_previsao_e_ultimo_backup_na_interface(self):
        from test_contas import dados_rpv
        identificador=self.banco.salvar(dados_rpv())
        self.banco.atualizar_previsao(identificador,'2027-01-20')
        self.banco.atualizar_previsao(identificador,'2026-11-20')
        self.programa.mostrar_historico()
        self.root.update()
        estilo=ttk.Style()
        self.assertEqual(tkfont.Font(font=estilo.lookup('Operacoes.Treeview','font')).actual('size'),12)
        self.assertEqual(tkfont.Font(font=estilo.lookup('Operacoes.Treeview.Heading','font')).actual('size'),18)
        ultimo=self.programa.cartoes_resumo[-1][1]
        self.assertEqual(ultimo.cget('text'),'Lucro realizado')
        self.assertIn('ainda não realizado',self.programa.texto_ultimo_backup.get())
        destino=str(Path(self.pasta.name)/'exportados')
        with patch.object(filedialog,'askdirectory',return_value=destino),patch.object(messagebox,'showinfo'):
            self.programa.exportar_backup()
        self.assertRegex(self.programa.texto_ultimo_backup.get(),r'Último backup: \d{2}/\d{2}/\d{4}')
        self.programa.editar_previsao(identificador)
        self.root.update()
        tela=next(w for w in self.programa.historico.winfo_children() if isinstance(w,tk.Toplevel))
        historico=next(w for w in filhos(tela) if isinstance(w,ttk.Treeview))
        self.assertEqual(len(historico.get_children()),2)
        self.assertEqual(historico.item(historico.get_children()[0],'values')[:2],('20/01/2027','20/11/2026'))

    def test_tema_escolhido_volta_ao_reabrir(self):
        self.programa.alternar_tema()
        self.assertEqual(self.banco.configuracao('tema'), 'escuro')
        self.root.destroy()
        self.root = tk.Tk()
        self.root.report_callback_exception = lambda *args: self.erros.append(args)
        with patch.object(app, 'Banco', return_value=self.banco):
            self.programa = app.Aplicativo(self.root)
        self.root.update()
        self.assertEqual(self.programa.modo_tema.get(), 'escuro')
        self.assertEqual(self.programa.texto_alternar_tema.get(), 'Modo claro')
        self.programa.alternar_tema()
        self.assertEqual(self.banco.configuracao('tema'), 'claro')

    def test_emblema_no_inicio_e_assinatura_com_icone(self):
        self.assertEqual([str(i) for i in self.programa.emblema_inicio.cget('image')], [str(self.root._marca_cabecalho)])
        self.root.update()
        emblema = self.programa.emblema_inicio
        centro_emblema = emblema.winfo_rootx() + emblema.winfo_width() / 2
        centro_janela = self.root.winfo_rootx() + self.root.winfo_width() / 2
        self.assertLessEqual(abs(centro_emblema - centro_janela), 2)
        self.programa.posicionar_emblema(SimpleNamespace(height=emblema.winfo_reqheight() - 1))
        self.assertFalse(emblema.winfo_manager())
        self.programa.posicionar_emblema(SimpleNamespace(height=emblema.winfo_reqheight()))
        self.assertEqual(emblema.winfo_manager(), 'place')
        assinatura = self.programa.assinatura_inicio
        self.assertEqual(assinatura.cget('text'), f'Vitoran Tech · v{app.VERSAO}')
        self.assertEqual([str(i) for i in assinatura.cget('image')], [str(self.root._marca_rodape)])
        self.assertEqual(str(assinatura.cget('compound')), 'left')

    def test_exportar_excel_pelo_menu(self):
        from test_contas import dados_rpv
        self.programa.mostrar_historico()
        menu = self.programa.menus['Arquivo']
        rotulos = [menu.entrycget(i, 'label') for i in range(menu.index('end') + 1) if menu.type(i) == 'command']
        self.assertIn('Exportar para Excel', rotulos)
        with patch.object(messagebox, 'showinfo') as aviso, patch.object(filedialog, 'asksaveasfilename') as escolher:
            self.programa.exportar_excel()
        escolher.assert_not_called()
        self.assertIn('Ainda não há operações', aviso.call_args.args[1])
        self.banco.salvar(dados_rpv(nome='Primeira'))
        self.banco.salvar(dados_rpv(nome='Segunda', aquisicao='2026-10-23'))
        with patch.object(filedialog, 'asksaveasfilename', return_value=''), patch.object(messagebox, 'showinfo') as aviso:
            self.programa.exportar_excel()
        aviso.assert_not_called()
        destino = Path(self.pasta.name) / 'planilhas' / 'operacoes.xlsx'
        with patch.object(filedialog, 'asksaveasfilename', return_value=str(destino)), \
                patch.object(messagebox, 'showinfo') as aviso:
            self.programa.exportar_excel()
        self.assertTrue(destino.is_file())
        self.assertIn('2 operação(ões)', aviso.call_args.args[1])

    def test_filtros_por_situacao_com_contagem_e_atrasadas_em_vermelho(self):
        from test_contas import dados_rpv
        atrasada = str(self.banco.salvar(dados_rpv(nome='Atrasada', aquisicao='2020-01-01', previsao='2020-02-01')))
        pendente = str(self.banco.salvar(dados_rpv(nome='Pendente', aquisicao='2020-01-02', previsao='2099-01-01')))
        recebida = str(self.banco.salvar(dados_rpv(nome='Recebida', aquisicao='2020-01-03', previsao='2020-02-01')))
        self.banco.registrar_recebimento(int(recebida), '2020-03-01')
        self.programa.mostrar_historico()
        self.root.update()
        tabela = self.programa.tabela
        botoes = self.programa.botoes_filtro
        self.assertEqual([botoes[v].cget('text') for v in ('todas', 'pendente', 'atrasada', 'recebida')],
                         ['Todas  3', 'Pendentes  1', 'Atrasadas  1', 'Recebidas  1'])
        self.assertEqual(str(botoes['atrasada'].cget('style')), 'FiltroAlerta.TRadiobutton')
        self.assertIn('atrasada', tabela.item(atrasada, 'tags'))
        self.assertNotIn('atrasada', tabela.item(pendente, 'tags'))
        self.assertEqual(str(tabela.tag_configure('atrasada', 'foreground')), cores()['vermelho'])
        tabela.xview_moveto(1)
        self.root.update()
        self.assertEqual(str(self.programa.acoes_linhas[atrasada][0].cget('style')), 'PrevisaoAtrasada.TLabel')
        self.assertEqual(str(self.programa.acoes_linhas[atrasada][1].cget('style')), 'Atrasada.Operacoes.TCheckbutton')
        self.assertEqual(str(tabela.tag_configure('atrasada', 'background')), cores()['atraso'])
        self.assertEqual(list(tabela.item(atrasada, 'tags')), ['atrasada'])
        self.assertEqual(str(self.programa.acoes_linhas[pendente][0].cget('style')), 'Previsao.TLabel')
        for valor, esperado in (('atrasada', [atrasada]), ('pendente', [pendente]), ('recebida', [recebida]),
                                ('todas', [recebida, pendente, atrasada])):
            botoes[valor].invoke()
            self.root.update()
            self.assertEqual(list(tabela.get_children()), esperado)
        botoes['recebida'].invoke()
        self.assertIn('Registros: 1', texto_resumo(self.programa))
        self.programa.busca.set('Pendente')
        self.root.update()
        self.assertEqual(botoes['todas'].cget('text'), 'Todas  1')
        self.assertEqual(str(botoes['atrasada'].cget('style')), 'Filtro.TRadiobutton')
        self.assertEqual(list(tabela.get_children()), [])
        self.programa.alternar_tema()
        self.assertEqual(str(tabela.tag_configure('atrasada', 'foreground')), cores()['vermelho'])

    def test_grafico_mensal_pelo_menu_exibir(self):
        from test_contas import dados_rpv
        hoje = date.today().isoformat()
        identificador = self.banco.salvar(dados_rpv(aquisicao=hoje, previsao=hoje, custo=150000, previsto=200000))
        self.banco.registrar_recebimento(identificador, hoje)
        self.programa.mostrar_historico()
        menu = self.programa.menus['Exibir']
        indice = next(i for i in range(menu.index('end') + 1)
                      if menu.type(i) == 'command' and menu.entrycget(i, 'label') == 'Gráfico mensal')
        menu.invoke(indice)
        self.root.update()
        janela = self.programa.grafico_mensal
        self.assertTrue(janela.tela.winfo_viewable())
        self.assertEqual(janela.dados[-1][1:], (150000, 200000))
        self.assertTrue(janela.grafico.find_all())
        grafico = janela.grafico
        inicio, fim = grafico.barras[-1][:2]
        grafico.event_generate('<Motion>', x=int((inicio + fim) / 2), y=50)
        self.root.update()
        self.assertIn('R$ 1.500,00 investidos', janela.detalhe.get())
        grafico.event_generate('<Leave>')
        self.root.update()
        self.assertIn('Passe o mouse', janela.detalhe.get())
        self.programa.alternar_tema()
        self.assertEqual(grafico.cget('bg'), cores()['superficie'])
        self.programa.mostrar_grafico()
        self.root.update()
        self.assertFalse(janela.tela.winfo_exists())
        self.assertTrue(self.programa.grafico_mensal.tela.winfo_exists())

    def test_instalacao_nova_abre_com_demonstracao_e_apaga_pelo_aviso(self):
        self.programa.mostrar_historico()
        self.root.update()
        self.assertFalse(self.programa.aviso_demonstracao.winfo_ismapped())
        self.root.destroy()
        self.root = tk.Tk()
        self.root.report_callback_exception = lambda *args: self.erros.append(args)
        novo = Banco(Path(self.pasta.name) / 'novo' / 'gestor.sqlite3')
        with patch.object(app, 'Banco', return_value=novo):
            self.programa = app.Aplicativo(self.root)
        self.programa.mostrar_historico()
        self.root.update()
        self.assertTrue(self.programa.aviso_demonstracao.winfo_ismapped())
        self.assertEqual(len(self.programa.tabela.get_children()), 13)
        with patch.object(messagebox, 'askyesno', return_value=False):
            botao(self.programa.historico, 'Apagar dados de demonstração').invoke()
        self.assertEqual(len(self.programa.tabela.get_children()), 13)
        with patch.object(messagebox, 'askyesno', return_value=True):
            botao(self.programa.historico, 'Apagar dados de demonstração').invoke()
        self.root.update()
        self.assertEqual(self.programa.tabela.get_children(), ())
        self.assertEqual(novo.contas(), [])
        self.assertFalse(self.programa.aviso_demonstracao.winfo_ismapped())

    def test_paginas_na_mesma_janela_com_seta_para_voltar(self):
        inicio = self.programa.inicio
        self.assertEqual([w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)], [])
        self.programa.mostrar_historico()
        self.root.update()
        historico = self.programa.historico
        self.assertIsInstance(historico, ttk.Frame)
        self.assertIs(historico.master, self.root)
        self.assertFalse(inicio.winfo_ismapped())
        self.assertTrue(historico.winfo_ismapped())
        self.assertEqual(self.root.title(), 'Gestor de RPV — Minhas operações')
        self.assertEqual(str(self.root.cget('menu')), str(self.programa.menus['barra']))
        self.programa.menus['Exibir'].invoke('Gráfico mensal')
        self.root.update()
        grafico = self.programa.grafico_mensal.tela
        self.assertTrue(grafico.winfo_ismapped())
        self.assertFalse(historico.winfo_ismapped())
        self.assertEqual(str(self.root.cget('menu')), '')
        self.assertEqual(self.root.title(), 'Gestor de RPV — Gráfico mensal')
        botao(grafico, '←  Voltar').invoke()
        self.root.update()
        self.assertFalse(grafico.winfo_exists())
        self.assertTrue(historico.winfo_ismapped())
        self.assertEqual(str(self.root.cget('menu')), str(self.programa.menus['barra']))
        self.programa.menus['Arquivo'].invoke('Contas de recebimento')
        self.root.update()
        contas = self.programa.janela_contas.tela
        self.assertTrue(contas.winfo_ismapped())
        self.programa.mostrar_historico()
        self.root.update()
        self.assertFalse(contas.winfo_exists())
        self.assertTrue(historico.winfo_ismapped())
        self.root.event_generate('<Alt-Left>')
        self.root.update()
        self.assertFalse(historico.winfo_exists())
        self.assertTrue(inicio.winfo_ismapped())
        self.assertEqual(self.root.title(), 'Gestor de RPV')
        self.assertEqual(str(self.root.cget('menu')), '')
        self.programa.voltar()
        self.assertTrue(inicio.winfo_ismapped())
        botao(self.root, 'Contas de recebimento').invoke()
        self.root.update()
        self.assertTrue(self.programa.janela_contas.tela.winfo_ismapped())
        botao(self.programa.janela_contas.tela, '←  Voltar').invoke()
        self.root.update()
        self.assertTrue(inicio.winfo_ismapped())

    def test_inicio_avisa_atrasadas_e_abre_lista_filtrada(self):
        from test_contas import dados_rpv
        self.assertFalse(self.programa.aviso_atrasadas_inicio.winfo_ismapped())
        for nome in ('Primeira', 'Segunda'):
            self.banco.salvar(dados_rpv(nome=nome, aquisicao='2020-01-01', previsao='2020-02-01'))
        self.banco.salvar(dados_rpv(nome='Em dia', aquisicao='2020-01-01', previsao='2099-01-01'))
        self.programa.mostrar_historico()
        self.root.update()
        self.programa.voltar()
        self.root.update()
        self.assertEqual(self.programa.texto_aviso_atrasadas.get(), '2 operações atrasadas. Clique para ver.')
        self.assertTrue(self.programa.aviso_atrasadas_inicio.winfo_ismapped())
        self.programa.aviso_atrasadas_inicio.event_generate('<Button-1>')
        self.root.update()
        self.assertTrue(self.programa.historico.winfo_ismapped())
        self.assertEqual(self.programa.filtro.get(), 'atrasada')
        self.assertEqual(len(self.programa.tabela.get_children()), 2)

    def test_virada_do_dia_recalcula_atrasadas_com_programa_aberto(self):
        from test_contas import dados_rpv
        amanha = date.fromordinal(date.today().toordinal() + 1)
        identificador = str(self.banco.salvar(dados_rpv(aquisicao='2020-01-01', previsao=date.today().isoformat())))
        self.programa.mostrar_historico()
        self.root.update()
        self.assertNotIn('atrasada', self.programa.tabela.item(identificador, 'tags'))
        dia_seguinte = type('Dia', (date,), {'today': classmethod(lambda cls: amanha)})
        with patch('navegacao.date', dia_seguinte), patch('dados.date', dia_seguinte):
            self.programa.vigiar_data()
        self.root.update()
        self.assertIn('atrasada', self.programa.tabela.item(identificador, 'tags'))
        self.assertEqual(self.programa.botoes_filtro['atrasada'].cget('text'), 'Atrasadas  1')

    def test_backup_automatico_ativar_desativar_e_falha_discreta(self):
        from backup import PASTA_AUTOMATICA
        self.programa.mostrar_historico()
        self.programa.configurar_backup_automatico()
        self.root.update()
        tela = [w for w in self.programa.historico.winfo_children() if isinstance(w, tk.Toplevel)][-1]
        pasta = Path(self.pasta.name) / 'nuvem'
        pasta.mkdir()
        with patch.object(filedialog, 'askdirectory', return_value=str(pasta)), patch.object(messagebox, 'showinfo') as aviso:
            botao(tela, 'Escolher pasta…').invoke()
        self.assertEqual(self.banco.configuracao(PASTA_AUTOMATICA), str(pasta))
        self.assertEqual(len(list(pasta.glob('GestorRPV-auto-*.rpvbackup'))), 1)
        self.assertIn('ativado', aviso.call_args.args[1])
        self.assertIn('Backup automático semanal ativo', self.programa.texto_ultimo_backup.get())
        self.assertEqual(self.programa.texto_aviso_backup.get(), '')
        ausente = Path(self.pasta.name) / 'ausente'
        with patch.object(filedialog, 'askdirectory', return_value=str(ausente)), patch.object(messagebox, 'showerror') as erro:
            botao(tela, 'Escolher pasta…').invoke()
        self.assertIn('Não foi possível usar esta pasta', erro.call_args.args[1])
        self.assertEqual(self.banco.configuracao(PASTA_AUTOMATICA), str(pasta))
        botao(tela, 'Desativar').invoke()
        self.assertIsNone(self.banco.configuracao(PASTA_AUTOMATICA))
        self.assertNotIn('automático', self.programa.texto_ultimo_backup.get())
        tela.destroy()
        self.banco.salvar_configuracao(PASTA_AUTOMATICA, str(ausente))
        self.banco.registrar_backup('2020-01-01T12:00:00')
        self.programa.verificar_backup_automatico()
        self.assertTrue(self.programa.falha_backup_automatico)
        self.assertIn('backup automático não conseguiu gravar', self.programa.texto_aviso_backup.get())


if __name__ == '__main__':
    unittest.main()
