"""Testes reais do Tkinter: GESTOR_RPV_TESTE_UI=1 python -m unittest test_interface -v."""
import os
import tempfile
import tkinter as tk
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app
from componentes import CampoData, CampoMoeda
from dados import Banco


def filhos(widget):
    for filho in widget.winfo_children():
        yield filho
        yield from filhos(filho)


def botao(widget, texto):
    return next(w for w in filhos(widget) if isinstance(w, app.ttk.Button) and w.cget('text') == texto)


@unittest.skipUnless(os.environ.get('GESTOR_RPV_TESTE_UI') == '1', 'Requer sessão gráfica e GESTOR_RPV_TESTE_UI=1')
class TestInterface(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.banco = Banco(Path(self.pasta.name) / 'teste.sqlite3')
        self.root = tk.Tk()
        self.erros = []
        self.root.report_callback_exception = lambda *args: self.erros.append(args)
        with patch.object(app, 'Banco', return_value=self.banco):
            self.programa = app.Aplicativo(self.root)
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
        nome = next(w for w in filhos(form) if isinstance(w, app.ttk.Entry))
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
            with patch.object(app.messagebox, 'showerror') as erro:
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
        entradas = [w for w in filhos(form) if isinstance(w, app.ttk.Entry)]
        valores = ('Conta teste', 'pessoa DE teste', '52998224725', 'Endereço teste', 'Banco teste', '0001', '12345-6', 'teste@example.com')
        for entrada, valor in zip(entradas, valores):
            entrada.insert(0, valor)
        botao(form, 'Salvar conta').invoke()
        self.root.update()
        conta = next(c for c in self.banco.contas() if c['identificacao'] == 'Conta teste')
        janela.tabela.selection_set(str(conta['id']))
        with patch.object(app.messagebox, 'askyesno', return_value=True):
            janela.alterar_status()
        self.root.update()
        self.assertFalse(self.banco.obter_conta(conta['id'])['ativa'])
        form = self.formulario()
        combo = next(w for w in filhos(form) if isinstance(w, app.ttk.Combobox))
        self.assertNotIn('Conta teste', combo.cget('values'))
        form.destroy()
        janela.tabela.selection_set(str(conta['id']))
        with patch.object(app.messagebox, 'askyesno', return_value=True):
            janela.alterar_status()
        form = self.formulario()
        combo = next(w for w in filhos(form) if isinstance(w, app.ttk.Combobox))
        self.assertIn('Conta teste', combo.cget('values'))

    def test_coluna_prorrogacao_e_historico(self):
        identificador = self.banco.salvar(dict(nome='Teste', aquisicao='2026-10-22', previsto=2000000,
            custo=1200000, conta='Vitor', previsao='2026-12-20', comissao=None, observacoes=''))
        self.programa.mostrar_historico()
        self.root.update()
        tabela = self.programa.tabela
        for coluna in tabela.cget('columns'):
            self.assertEqual(str(tabela.column(coluna, 'anchor')), 'center')
            self.assertEqual(str(tabela.heading(coluna, 'anchor')), 'center')
        tabela.xview_moveto(1)
        self.root.update()
        self.root.update()
        botao_coluna = self.programa.acoes_linhas[str(identificador)][0]
        self.assertIn('Adicionar / Ver', botao_coluna.cget('text'))
        botao_coluna.invoke()
        self.root.update()
        tela = next(w for w in self.programa.historico.winfo_children() if isinstance(w, tk.Toplevel))
        self.assertEqual([w for w in filhos(tela) if isinstance(w, CampoData)], [])
        botao(tela, 'Nova prorrogação').invoke()
        self.root.update()
        entrada = next(w for w in tela.winfo_children() if isinstance(w, tk.Toplevel))
        calendario = next(w for w in filhos(entrada) if isinstance(w, CampoData))
        calendario.abrir()
        self.root.update()
        calendario.selecionar(date(2027, 1, 20))
        botao(entrada, 'Salvar prorrogação').invoke()
        self.root.update()
        self.assertEqual(self.banco.listar()[0]['previsao_atual'], '2027-01-20')
        self.assertEqual(self.root.grab_current(), tela)
        botao(tela, 'Nova prorrogação').invoke()
        self.root.update()
        entrada = next(w for w in tela.winfo_children() if isinstance(w, tk.Toplevel))
        calendario = next(w for w in filhos(entrada) if isinstance(w, CampoData))
        calendario.variavel.set('20/02/2027')
        botao(entrada, 'Salvar prorrogação').invoke()
        self.root.update()
        self.assertEqual(len(self.banco.prorrogacoes(identificador)), 2)
        self.assertIn('2', tabela.item(str(identificador), 'values')[-2])
        botao(tela, 'Fechar').invoke()
        self.programa.historico.destroy()
        self.programa.mostrar_historico()
        self.root.update()
        self.assertEqual(self.banco.listar()[0]['total_prorrogacoes'], 2)

    def test_dados_preservados_copiar_e_grab(self):
        registro = self.banco.salvar(dict(nome='Teste', aquisicao='2026-10-22', previsto=2000000,
            custo=1200000, conta='Vitor', previsao='2026-12-20', comissao=None, observacoes=''))
        self.programa.formulario(registro)
        self.root.update()
        form = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        botao(form, 'Dados de recebimento').invoke()
        self.root.update()
        tela = next(w for w in form.winfo_children() if isinstance(w, tk.Toplevel))
        rotulo = next(w for w in filhos(tela) if isinstance(w, app.ttk.Label) and 'Nome completo:' in w.cget('text'))
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
        self.assertEqual(str(janela.tabela.tag_configure('incompleta', 'foreground')), '#ff6b6b')
        janela.formulario()
        self.root.update()
        tela = next(w for w in janela.tela.winfo_children() if isinstance(w, tk.Toplevel))
        entradas = [w for w in filhos(tela) if isinstance(w, app.ttk.Entry)]
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
        for entrada, valor in zip(entradas[3:], ('rua teste', 'banco teste', '001', '123-4', 'ChaveCaseSensitive')):
            entrada.insert(0, valor)
        cpf.delete(0, tk.END)
        with patch.object(app.messagebox, 'showerror') as erro:
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
        nome = next(w for w in filhos(form) if isinstance(w, app.ttk.Entry))
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
        with patch.object(app.messagebox, 'askyesno', return_value=False):
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
        nome = next(w for w in filhos(form) if isinstance(w, app.ttk.Entry))
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
        self.assertEqual(caixa.cget('text'), '22/10/2026')
        self.assertEqual(caixa.cget('style'), 'Recebido.TCheckbutton')
        estilo = app.ttk.Style()
        self.assertEqual(str(estilo.lookup('Recebido.TCheckbutton', 'foreground')), '#63df8a')
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
        with patch.object(app.messagebox, 'askyesno', return_value=True):
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
        entradas = [w for w in filhos(tela) if isinstance(w, app.ttk.Entry)]
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
        with patch.object(app.messagebox, 'askyesno', return_value=False):
            botao(janela.tela, 'Remover').invoke()
        self.assertIsNotNone(self.banco.obter_conta(conta['id']))
        with patch.object(app.messagebox, 'askyesno', return_value=True):
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


if __name__ == '__main__':
    unittest.main()
