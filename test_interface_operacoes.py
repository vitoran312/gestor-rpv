"""Testes de interface: Minhas operações (tabela, seleção, lixeira, filtros e menus)."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, font as tkfont
import unittest
from pathlib import Path
from unittest.mock import patch

from componentes import CampoData
from apoio_testes import dados_rpv
from tema import cores, PALETAS
from apoio_interface import TesteDeInterface, botao, filhos, texto_resumo


@unittest.skipUnless(os.environ.get('GESTOR_RPV_TESTE_UI') == '1', 'Requer sessão gráfica e GESTOR_RPV_TESTE_UI=1')
class TestOperacoes(TesteDeInterface):
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
        tabela.event_generate('<Button-3>', x=x + 5, y=y + 5)
        self.root.update()
        self.assertEqual(tabela.selection(), (str(primeiro),))
        menu = next(w for w in tabela.winfo_children() if isinstance(w, tk.Menu))
        menu.invoke('Copiar')
        menu.unpost()
        self.root.update()
        self.assertIn('Primeiro', tabela.clipboard_get())
        tabela.event_generate('<Button-3>', x=x + 5, y=y + 5)
        self.root.update()
        menu = [w for w in tabela.winfo_children() if isinstance(w, tk.Menu)][-1]
        with patch.object(messagebox, 'askyesno', return_value=False):
            menu.invoke('Excluir')
        menu.unpost()
        self.root.update()
        self.assertEqual(len(self.banco.listar()), 2)

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
        self.programa.tabela.selection_set(str(identificador))
        self.programa.copiar_selecao()
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
        self.banco.atualizar_previsao(identificador, '2027-01-20')
        self.programa.mostrar_historico()
        self.root.update()
        self.assertNotIn('Investido', texto_resumo(self.programa))
        self.programa.tabela.selection_set(str(identificador))
        with patch.object(messagebox, 'askyesno', return_value=True):
            self.programa.excluir()
        self.root.update()
        self.assertEqual(self.programa.tabela.get_children(), ())
        botao(self.programa.historico, 'Lixeira').invoke()
        self.root.update()
        tela = next(w for w in self.programa.historico.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == 'Lixeira')
        tabela = next(w for w in filhos(tela) if isinstance(w, ttk.Treeview))
        tabela.selection_set(str(identificador))
        botao(tela, 'Restaurar entradas').invoke()
        self.root.update()
        self.assertEqual(self.programa.tabela.get_children(), (str(identificador),))
        self.assertEqual(self.banco.obter(identificador)['previsao_atual'], '2027-01-20')
        self.assertFalse(hasattr(self.programa, 'mostrar_auditoria'))

    def test_ctrl_n_e_lixeira_repetidos_abrem_uma_janela_so(self):
        self.programa.mostrar_historico()
        self.root.update()
        for _ in range(3):
            self.programa.historico.event_generate('<Control-n>')
            self.root.update()
        formularios = [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == 'Nova entrada']
        self.assertEqual(len(formularios), 1)
        formularios[0].destroy()
        identificador = self.banco.salvar(dados_rpv(nome='Primeira'))
        for _ in range(2):
            botao(self.programa.historico, 'Lixeira').invoke()
            self.root.update()
        lixeiras = [w for w in self.programa.historico.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == 'Lixeira']
        self.assertEqual(len(lixeiras), 1)
        # Excluir com a lixeira aberta: a entrada aparece nela sem reabrir.
        self.programa.atualizar()
        self.programa.tabela.selection_set(str(identificador))
        with patch.object(messagebox, 'askyesno', return_value=True):
            self.programa.excluir()
        self.root.update()
        tabela = next(w for w in filhos(lixeiras[0]) if isinstance(w, ttk.Treeview))
        self.assertEqual(tabela.get_children(), (str(identificador),))

    def test_ordenacao_colunas_tres_cliques_e_filtro(self):
        ids = []
        for nome, total, dia in (('Álvaro', 9000000, 1), ('Bruno', 10000000, 2), ('Carlos', 200000, 3)):
            ids.append(str(self.banco.salvar(dict(nome=nome, aquisicao=f'2026-01-0{dia}', previsto=total,
                custo=100, conta='Vitor', previsao='2026-12-20', comissao=None, observacoes=''))))
        self.programa.mostrar_historico()
        self.root.update()
        tabela = self.programa.tabela
        normal = tuple(reversed(ids))
        self.assertEqual(tabela.get_children(), normal)

        def clicar(coluna):
            self.root.tk.call(tabela.heading(coluna, 'command'))
            self.root.update()

        clicar('previsto')
        self.assertEqual(tabela.get_children(), (ids[1], ids[0], ids[2]))
        clicar('previsto')
        self.assertEqual(tabela.get_children(), (ids[2], ids[0], ids[1]))
        clicar('previsto')
        self.assertEqual(tabela.get_children(), normal)
        self.assertEqual(tabela.heading('previsto', 'text'), 'Valor Total RPV')
        clicar('nome')
        self.assertEqual(tabela.get_children(), tuple(ids))
        clicar('nome')
        self.assertEqual(tabela.get_children(), normal)
        clicar('nome')
        self.assertIsNone(self.programa.ordenacao)
        clicar('data')
        self.assertEqual(tabela.get_children(), normal)
        clicar('data')
        self.assertEqual(tabela.get_children(), tuple(ids))
        self.programa.busca.set('Bruno')
        self.root.update()
        self.assertEqual(tabela.get_children(), (ids[1],))

    def test_selecao_mouse_teclado_exclusao_e_restauracao_em_lote(self):
        for n in range(4):
            self.banco.salvar(dados_rpv(nome=f'Pessoa {n}'))
        self.programa.mostrar_historico()
        self.root.geometry('1100x900')
        self.root.update()
        tabela = self.programa.tabela
        linhas = list(tabela.get_children())
        def clicar(linha, estado=0):
            x, y, w, h = tabela.bbox(linha, 'nome')
            tabela.event_generate('<ButtonPress-1>', x=x + 8, y=y + h // 2, state=estado)
            tabela.event_generate('<ButtonRelease-1>', x=x + 8, y=y + h // 2, state=estado)
            self.root.update()
        clicar(linhas[0])
        clicar(linhas[2], 4)
        self.assertEqual(set(tabela.selection()), {linhas[0], linhas[2]})
        clicar(linhas[3], 1)
        self.assertEqual(set(tabela.selection()), {linhas[2], linhas[3]})
        clicar(linhas[0])
        x, y, w, h = tabela.bbox(linhas[2], 'nome')
        tabela.event_generate('<B1-Motion>', x=x + 8, y=y + h // 2, state=256)
        tabela.event_generate('<ButtonRelease-1>', x=x + 8, y=y + h // 2)
        self.root.update()
        self.assertEqual(set(tabela.selection()), set(linhas[:3]))
        # O arrasto também pode começar no espaço vazio abaixo das linhas.
        tabela.event_generate('<ButtonPress-1>', x=20, y=tabela.winfo_height() - 20)
        for linha in reversed(linhas[1:]):
            x, y, w, h = tabela.bbox(linha, 'nome')
            tabela.event_generate('<B1-Motion>', x=x + 8, y=y + h // 2, state=256)
        tabela.event_generate('<ButtonRelease-1>', x=x + 8, y=y + h // 2)
        self.root.update()
        self.assertEqual(set(tabela.selection()), set(linhas[1:]))
        tabela.focus_force()
        tabela.event_generate('<KeyPress>', keysym='Home')
        tabela.event_generate('<KeyPress>', keysym='Down', state=1)
        self.root.update()
        self.assertEqual(set(tabela.selection()), set(linhas[:2]))
        with patch.object(messagebox, 'askyesno', return_value=True):
            tabela.event_generate('<KeyPress>', keysym='Delete')
            self.root.update()
        self.assertEqual(len(self.banco.listar_lixeira()), 2)
        self.programa.mostrar_lixeira()
        self.root.update()
        tela = next(w for w in self.programa.historico.winfo_children()
                    if isinstance(w, tk.Toplevel) and w.title() == 'Lixeira')
        restaurar = botao(tela, 'Restaurar entradas')
        self.assertTrue(restaurar.winfo_ismapped())
        self.assertGreater(restaurar.winfo_width(), 150)
        self.assertLess(restaurar.winfo_rooty() + restaurar.winfo_height(), tela.winfo_rooty() + tela.winfo_height() + 1)
        estilo = ttk.Style(self.root)
        self.assertNotEqual(estilo.lookup('Restaurar.TButton', 'foreground'), estilo.lookup('Restaurar.TButton', 'background'))
        lixeira = next(w for w in filhos(tela) if isinstance(w, ttk.Treeview))
        lixeira.focus_force()
        self.root.update()
        lixeira.event_generate('<Control-a>')
        lixeira.event_generate('<Return>')
        self.root.update()
        self.assertEqual(len(self.banco.listar()), 4)
        self.assertEqual(str(self.programa.botao_lixeira.cget('compound')), 'image')

    def test_comissao_e_saldos_recebimento_filtro_lixeira_e_colunas(self):
        recebido = self.banco.salvar(dados_rpv(nome='Recebido', comissao=50000))
        aberto = self.banco.salvar(dados_rpv(nome='Aberto', previsto=1000000, custo=700000))
        self.banco.registrar_recebimento(recebido, '2026-10-22')
        self.programa.mostrar_historico()
        self.root.update()
        tabela = self.programa.tabela
        self.assertEqual(tabela['columns'][2:5], ('custo', 'comissao', 'previsto'))
        self.assertEqual(tabela.set(str(recebido), 'comissao'), 'R$ 500,00')
        self.assertEqual(tabela.set(str(aberto), 'comissao'), 'R$ 0,00')
        texto = texto_resumo(self.programa)
        self.assertIn('Registros: 2', texto)
        self.assertIn('Lucro previsto: R$ 11.000,00', texto)
        self.assertIn('Lucro realizado: R$ 8.000,00', texto)
        self.assertIn('Capital investido em aberto: R$ 7.000,00', texto)
        self.programa.ordenar_coluna('comissao')
        self.assertEqual(tabela.get_children(), (str(recebido), str(aberto)))
        self.programa.ordenar_coluna('comissao')
        self.assertEqual(tabela.get_children(), (str(aberto), str(recebido)))
        self.programa.busca.set('Aberto')
        self.root.update()
        self.assertIn('Lucro realizado: R$ 0,00', texto_resumo(self.programa))
        self.programa.busca.set('')
        self.banco.excluir(aberto)
        self.programa.atualizar()
        self.assertIn('Capital investido em aberto: R$ 0,00', texto_resumo(self.programa))
        self.banco.restaurar(aberto)
        self.banco.registrar_recebimento(recebido, None)
        self.programa.atualizar()
        self.root.update()
        self.assertIn('Capital investido em aberto: R$ 19.000,00', texto_resumo(self.programa))
        self.assertIn('Lucro realizado: R$ 0,00', texto_resumo(self.programa))
        # A coluna adicionada não desloca as ações de calendário/recebimento.
        tabela.xview_moveto(1)
        self.root.update()
        for coluna, titulo in (('previsao_atual', 'Previsão atual'), ('recebido', 'Recebimento')):
            x, y, w, h = tabela.bbox(str(aberto), coluna)
            tabela.event_generate('<ButtonPress-1>', x=x + w // 2, y=y + h // 2)
            tabela.event_generate('<ButtonRelease-1>', x=x + w // 2, y=y + h // 2)
            self.root.update()
            janela = next(w for w in self.programa.historico.winfo_children()
                          if isinstance(w, tk.Toplevel) and w.title() == titulo)
            botao(janela, 'Cancelar').invoke() if titulo == 'Recebimento' else janela.destroy()
            self.root.update()
        self.root.geometry('900x620')
        self.root.update()
        self.assertTrue(self.programa.botao_lixeira.winfo_ismapped())
        self.assertLess(self.programa.botao_lixeira.winfo_rootx() + self.programa.botao_lixeira.winfo_width(),
                        self.root.winfo_rootx() + self.root.winfo_width() + 1)

    def test_layout_responsivo_indicadores_e_botoes_e_salvamento_por_dias(self):
        identificador = self.banco.salvar(dados_rpv())
        self.programa.mostrar_historico()
        self.root.update()
        for largura, colunas in ((1600, 4), (900, 2)):
            self.root.geometry(f'{largura}x650')
            self.root.update()
            self.assertEqual(self.programa.colunas_resumo, colunas)
            cartoes = [c for c, _ in self.programa.cartoes_resumo]
            self.assertLessEqual(max(c.winfo_width() for c in cartoes) - min(c.winfo_width() for c in cartoes), 1)
            for inicio in range(0, 4, colunas):
                self.assertEqual(len({c.winfo_rooty() for c in cartoes[inicio:inicio + colunas]}), 1)
                valores = [c.winfo_children()[1] for c in cartoes[inicio:inicio + colunas]]
                self.assertEqual(len({v.winfo_rooty() for v in valores}), 1)
            self.assertGreaterEqual(self.programa.botao_lixeira.winfo_rootx(),
                                    self.programa.resumo.winfo_rootx() + self.programa.resumo.winfo_width())
        self.programa.formulario(identificador)
        self.root.update()
        form = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == 'Editar registro')
        botoes = [botao(form, t) for t in ('Dados de recebimento', 'Cancelar', 'Salvar registro')]
        self.assertEqual(len({b.winfo_rooty() for b in botoes}), 1)
        self.assertEqual(len({b.winfo_height() for b in botoes}), 1)
        self.assertLessEqual(max(b.winfo_width() for b in botoes) - min(b.winfo_width() for b in botoes), 1)
        modos = {w.cget('value'): w for w in filhos(form) if isinstance(w, ttk.Radiobutton)}
        modos['dias'].invoke()
        prazo = next(w for w in filhos(form) if w.winfo_name() == 'prazo_dias')
        prazo.delete(0, 'end')
        prazo.insert(0, '30')
        datas = [w for w in filhos(form) if isinstance(w, CampoData)]
        self.assertTrue(datas[1].entrada.instate(['disabled']))
        self.programa.menus['Exibir'].invoke('Tema claro')
        self.root.update()
        self.assertTrue(datas[1].entrada.instate(['disabled']))
        self.assertEqual(str(ttk.Style().lookup('ResumoRealizado.TLabel', 'foreground')), PALETAS['claro']['verde'])
        botao(form, 'Salvar registro').invoke()
        self.root.update()
        self.assertEqual(self.banco.obter(identificador)['previsao'], '2026-11-21')

    def test_lixeira_exclui_permanentemente_apos_confirmacao(self):
        arquivo = Path(self.pasta.name) / 'contrato.pdf'
        arquivo.write_bytes(b'%PDF exemplo')
        identificador = self.banco.salvar(dados_rpv(), anexos=[arquivo])
        caminho = self.banco.caminho_documento(self.banco.documentos(identificador)[0]['id'])
        self.banco.excluir(identificador)
        self.programa.mostrar_historico()
        self.programa.mostrar_lixeira()
        self.root.update()
        tela = next(w for w in self.programa.historico.winfo_children() if isinstance(w, tk.Toplevel))
        tabela = next(w for w in filhos(tela) if isinstance(w, ttk.Treeview))
        tabela.selection_set(str(identificador))
        with patch.object(messagebox, 'askyesno', return_value=False):
            botao(tela, 'Excluir permanentemente').invoke()
        self.assertIsNotNone(self.banco.obter(identificador))
        with patch.object(messagebox, 'askyesno', return_value=True):
            botao(tela, 'Excluir permanentemente').invoke()
        self.root.update()
        self.assertIsNone(self.banco.obter(identificador))
        self.assertFalse(caminho.exists())
        self.assertTrue(arquivo.exists())

    def test_fontes_indicadores_previsao_e_ultimo_backup_na_interface(self):
        identificador = self.banco.salvar(dados_rpv())
        self.banco.atualizar_previsao(identificador, '2027-01-20')
        self.banco.atualizar_previsao(identificador, '2026-11-20')
        self.programa.mostrar_historico()
        self.root.update()
        estilo = ttk.Style()
        self.assertEqual(tkfont.Font(font=estilo.lookup('Operacoes.Treeview', 'font')).actual('size'), 12)
        self.assertEqual(tkfont.Font(font=estilo.lookup('Operacoes.Treeview.Heading', 'font')).actual('size'), 18)
        ultimo = self.programa.cartoes_resumo[-1][1]
        self.assertEqual(ultimo.cget('text'), 'Lucro realizado')
        self.assertIn('ainda não realizado', self.programa.texto_ultimo_backup.get())
        destino = str(Path(self.pasta.name) / 'exportados')
        with patch.object(filedialog, 'askdirectory', return_value=destino), patch.object(messagebox, 'showinfo'):
            self.programa.exportar_backup()
        self.assertRegex(self.programa.texto_ultimo_backup.get(), r'Último backup: \d{2}/\d{2}/\d{4}')
        self.programa.editar_previsao(identificador)
        self.root.update()
        tela = next(w for w in self.programa.historico.winfo_children() if isinstance(w, tk.Toplevel))
        historico = next(w for w in filhos(tela) if isinstance(w, ttk.Treeview))
        self.assertEqual(len(historico.get_children()), 2)
        self.assertEqual(historico.item(historico.get_children()[0], 'values')[:2], ('20/01/2027', '20/11/2026'))

    def test_filtros_por_situacao_com_contagem_e_atrasadas_em_vermelho(self):
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


if __name__ == '__main__':
    unittest.main()
