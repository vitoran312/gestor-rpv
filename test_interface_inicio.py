"""Testes de interface: tela inicial, temas, páginas, gráfico, escala e aparência."""
import os
import tkinter as tk
from tkinter import ttk, font as tkfont
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import app
import estilos
from apoio_testes import dados_rpv
from tema import cores, PALETAS
from apoio_interface import TesteDeInterface, botao, filhos


@unittest.skipUnless(os.environ.get('GESTOR_RPV_TESTE_UI') == '1', 'Requer sessão gráfica e GESTOR_RPV_TESTE_UI=1')
class TestInicio(TesteDeInterface):
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

    def test_previsao_legivel_com_mouse_nos_dois_temas(self):
        form = self.formulario()
        opcoes = [w for w in filhos(form) if isinstance(w, ttk.Radiobutton)]
        self.assertEqual(len(opcoes), 2)
        self.assertEqual(self.programa.inicio.itemcget(self.programa.assinatura_inicio, 'text'), f'Vitoran Tech · v{app.VERSAO}')
        def luminancia(cor):
            canais = [n / 65535 for n in self.root.winfo_rgb(cor)]
            canais = [n / 12.92 if n <= 0.04045 else ((n + 0.055) / 1.055)**2.4 for n in canais]
            return sum(a * b for a, b in zip(canais, (0.2126, 0.7152, 0.0722)))
        estilo = ttk.Style(self.root)
        for modo in ('escuro', 'claro'):
            self.programa.modo_tema.set(modo)
            self.programa.configurar_tema()
            self.root.update()
            self.assertEqual(str(estilo.lookup('DataCalculada.TLabel', 'background', ('disabled',))), form.cget('bg'))
            for opcao in opcoes:
                opcao.event_generate('<Motion>', x=5, y=5, warp=True)
                self.root.update()
                opcao.event_generate('<Enter>', x=5, y=5)
                self.root.update()
                self.assertTrue(opcao.instate(['active']))
                for pressionado in (False, True):
                    if pressionado:
                        opcao.state(['pressed'])
                        self.root.update()
                        self.assertTrue(opcao.instate(['pressed']))
                    estado = opcao.state()
                    fundo = str(estilo.lookup('TRadiobutton', 'background', estado))
                    frente = str(estilo.lookup('TRadiobutton', 'foreground', estado))
                    a, b = sorted((luminancia(fundo), luminancia(frente)))
                    self.assertGreaterEqual((b + 0.05) / (a + 0.05), 4.5)
                    if modo == 'escuro':
                        self.assertNotEqual(self.root.winfo_rgb(fundo), (65535, 65535, 65535))
                opcao.state(['!pressed'])
                opcao.invoke()
                opcao.event_generate('<Leave>')
                self.root.update()

    def test_inicio_pro_acoes_visiveis_e_temas_sem_recriar_imagens(self):
        self.assertEqual(self.programa.modo_tema.get(), 'claro')
        self.assertEqual([w for w in filhos(self.root) if isinstance(w, ttk.Entry)], [])
        for largura, largo in ((1286, True), (944, False)):
            self.root.geometry(f'{largura}x668')
            self.root.update()
            self.root.update()
            self.assertEqual(self.programa.layout_largo_inicio, largo)
            for texto in ('Nova entrada', 'Minhas operações', 'Contas de recebimento', 'Sair'):
                b = botao(self.root, texto)
                self.assertTrue(b.winfo_ismapped())
                self.assertGreaterEqual(b.winfo_rooty(), self.root.winfo_rooty())
                self.assertLessEqual(b.winfo_rooty() + b.winfo_height(), self.root.winfo_rooty() + self.root.winfo_height())
                self.assertLessEqual(b.winfo_rootx() + b.winfo_width(), self.root.winfo_rootx() + self.root.winfo_width())
        self.programa.alternar_tema()
        self.root.update()
        self.assertEqual(self.programa.texto_alternar_tema.get(), 'Modo claro')
        imagens = self.root.tk.call('image', 'names')
        self.programa.alternar_tema()
        self.programa.alternar_tema()
        self.root.update()
        self.assertEqual(len(self.root._superficies_pro), 2)
        # Ícones de Canvas não criam novas imagens; as superfícies são reutilizadas.
        self.assertEqual(set(self.root.tk.call('image', 'names')), set(imagens))

    def test_temas_reutilizados_icones_e_fonte_das_contas(self):
        textos = [w.cget('text') for w in filhos(self.root) if isinstance(w, ttk.Label)]
        self.assertFalse(any(t in ('01', '02', '03') or t.startswith('VITORAN') for t in textos))
        claro = str(self.programa.botao_alternar_tema.cget('image'))
        self.assertTrue(claro)
        self.programa.botao_alternar_tema.invoke()
        self.root.update()
        escuro = str(self.programa.botao_alternar_tema.cget('image'))
        self.assertNotEqual(claro, escuro)
        with patch.object(estilos, 'aplicar_superficies', side_effect=AssertionError('Superfícies não devem ser recriadas')), \
             patch('visual.tkfont.families', side_effect=AssertionError('Fontes não devem ser enumeradas novamente')):
            for _ in range(3):
                self.programa.alternar_tema()
                self.root.update()
        self.assertEqual(str(self.programa.botao_alternar_tema.cget('image')), claro)
        self.programa.mostrar_contas()
        self.root.update()
        tabela = self.programa.janela_contas.tabela
        estilo = ttk.Style()
        fonte = tkfont.Font(font=estilo.lookup(tabela.cget('style'), 'font'))
        self.assertEqual(fonte.actual('size'), 12)
        self.assertGreaterEqual(int(estilo.lookup(tabela.cget('style'), 'rowheight')), 40)

    def test_sobre_marca_versao_tema_e_janela_unica(self):
        self.assertTrue(self.root._icones_vitoran)
        self.assertEqual(self.root._marca_vitoran.width(), 128)
        botao(self.root, 'Sobre').invoke()
        self.root.update()
        tela = self.programa.sobre
        textos = [w.cget('text') for w in filhos(tela) if isinstance(w, ttk.Label)]
        for texto in ('Gestor de RPV', 'Vitoran Tech', 'Desenvolvido por Vitor Alves Nascimento', f'Versão {app.VERSAO}', 'Sugestões ou dúvidas:', 'vitoran312@gmail.com'):
            self.assertIn(texto, textos)
        # O que mudou nas últimas versões, com a contagem de novidades e correções.
        import novidades
        (quadro,) = [w for w in filhos(tela) if isinstance(w, tk.Text)]
        conteudo = quadro.get('1.0', 'end')
        for versao, itens in novidades.ultimas():
            self.assertIn(f'Versão {versao}  ·  {novidades.contagem(itens)}', conteudo)
        self.assertEqual(quadro.cget('state'), 'disabled')
        fechar = botao(tela, 'Fechar')
        self.assertTrue(fechar.winfo_ismapped())
        self.assertLessEqual(fechar.winfo_rooty() + fechar.winfo_height(), tela.winfo_rooty() + tela.winfo_height())
        self.programa.alternar_tema()
        self.root.update()
        self.assertEqual(tela.cget('bg'), PALETAS['escuro']['fundo'])
        self.programa.mostrar_historico()
        self.programa.menus['Ajuda'].invoke('Sobre o Gestor de RPV')
        self.root.update()
        self.assertIs(self.programa.sobre, tela)
        fechar.invoke()
        self.programa.menus['Ajuda'].invoke('Sobre o Gestor de RPV')
        self.root.update()
        self.assertIsNot(self.programa.sobre, tela)
        # Sem gerenciador de janelas, o foco do teclado segue o ponteiro, que outro teste pode ter movido.
        self.programa.sobre.focus_force()
        self.root.update()
        self.programa.sobre.event_generate('<Escape>')
        self.root.update()
        self.assertFalse(self.programa.sobre.winfo_exists())

    def test_tema_escolhido_volta_ao_reabrir(self):
        self.programa.alternar_tema()
        # A gravação fica para depois do redesenho, para não atrasar a troca.
        self.assertEqual(self.banco.configuracao('tema'), 'claro')
        self.root.update()
        self.assertEqual(self.banco.configuracao('tema'), 'escuro')
        self.root.destroy()
        self.root = tk.Tk()
        self.root.report_callback_exception = lambda *args: self.erros.append(args)
        with patch.object(app, 'abrir_banco', return_value=self.banco):
            self.programa = app.Aplicativo(self.root)
        self.root.update()
        self.assertEqual(self.programa.modo_tema.get(), 'escuro')
        self.assertEqual(self.programa.texto_alternar_tema.get(), 'Modo claro')
        self.programa.alternar_tema()
        self.root.update()
        self.assertEqual(self.banco.configuracao('tema'), 'claro')

    def test_inicio_cabecalho_destaque_atalhos_e_avisos(self):
        tela = self.programa.inicio
        self.root.geometry('1420x900')
        self.root.update()
        self.root.update()
        # A marca fica na barra lateral; na tela, a data por extenso acima do título. Data, título, subtítulo e
        # assinatura são textos do Canvas, sem caixas de fundo.
        self.assertEqual(self.root.tk.splitlist(self.programa.barra_lateral.emblema.cget('image')), (str(self.root._icones_vitoran[2]),))
        from tela_inicio import data_por_extenso
        self.assertEqual(tela.itemcget(self.programa.data_inicio, 'text'), data_por_extenso())
        self.assertLess(tela.bbox(self.programa.data_inicio)[3], tela.bbox(self.programa.titulo_inicio)[3])
        self.assertEqual(tela.itemcget(self.programa.titulo_inicio, 'text'), 'Gestor de RPV')
        self.assertEqual(tela.itemcget(self.programa.subtitulo_inicio, 'text'),
                         'Registros, recebimentos e documentos. Tudo no seu lugar.')
        self.assertEqual(tela.itemcget(self.programa.assinatura_inicio, 'text'), f'Vitoran Tech · v{app.VERSAO}')
        self.assertEqual(tela.itemcget(self.programa.marca_assinatura, 'image'), str(self.root._marca_rodape))
        # Cartão em destaque à esquerda, com cerca de 56% da largura; atalhos empilhados à direita.
        entrada, historico, contas = self.programa.cartoes_inicio
        self.assertTrue(self.programa.layout_largo_inicio)
        largura_util = tela.winfo_width() - 2 * 40
        # O conteúdo fica recuado da borda da superfície pela sombra e pelo canto arredondado.
        from tela_inicio import recuo_superficie
        from visual import px
        esquerda, _topo, direita, _base = recuo_superficie(cores(), 'destaque', lambda v: px(tela, v))
        self.assertAlmostEqual(entrada.winfo_width() + esquerda + direita, largura_util * 0.56, delta=8)
        # Em telas maiores, a composição não estica: mantém o tamanho e fica centralizada.
        medidas = []
        for geometria in ('1900x1100', '2200x1200'):  # Já descontada a barra lateral.
            self.root.geometry(geometria)
            self.root.update()
            self.root.update()
            medidas.append((entrada.winfo_width(), entrada.winfo_height(),
                            entrada.winfo_x() - (tela.winfo_width() - 1420) // 2,
                            entrada.winfo_y() - (tela.winfo_height() - 900) // 2))
        self.assertEqual(medidas[0], medidas[1])
        self.assertLess(entrada.winfo_x() + entrada.winfo_width(), historico.winfo_x())
        self.assertEqual(historico.winfo_x(), contas.winfo_x())
        self.assertLess(historico.winfo_y() + historico.winfo_height(), contas.winfo_y())
        self.assertGreater(entrada.winfo_height(), historico.winfo_height())
        # Textos e botões dos cartões continuam os mesmos.
        textos = [[w.cget('text') for w in self.programa.partes_inicio[cartao][1:]] for cartao in self.programa.cartoes_inicio]
        self.assertEqual(textos, [
            ['Uma nova operação', 'Cadastre sua próxima aquisição\ne reúna os documentos da entrada.', 'Nova entrada'],
            ['Tudo sob controle', 'Consulte valores, acompanhe prazos\ne confirme seus recebimentos.', 'Minhas operações'],
            ['Contas de recebimento', 'Mantenha seus dados bancários\norganizados e sempre à mão.', 'Contas de recebimento']])
        # Avisos viram cartões abaixo dos atalhos, só quando há o que avisar.
        aviso_backup = self.programa.pecas_inicio['backup'][0]
        self.assertTrue(aviso_backup.winfo_ismapped())
        self.assertGreater(aviso_backup.winfo_y(), contas.winfo_y() + contas.winfo_height())
        self.assertFalse(self.programa.pecas_inicio['atrasadas'][0].winfo_ismapped())
        self.programa.texto_aviso_backup.set('')
        self.root.update()
        self.assertFalse(aviso_backup.winfo_ismapped())

    def test_grafico_mensal_pelo_menu_exibir(self):
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
        self.assertEqual(janela.dados[-1][1:], (1, 1))
        self.assertTrue(janela.grafico.find_all())
        grafico = janela.grafico
        inicio, fim = grafico.barras[-1][:2]
        grafico.event_generate('<Motion>', x=int((inicio + fim) / 2), y=50)
        self.root.update()
        self.assertIn('1 entrada · 1 recebida', janela.detalhe.get())
        grafico.event_generate('<Leave>')
        self.root.update()
        self.assertIn('Passe o mouse', janela.detalhe.get())
        self.programa.alternar_tema()
        self.assertEqual(grafico.cget('bg'), cores()['superficie'])
        self.programa.mostrar_grafico()
        self.root.update()
        self.assertFalse(janela.tela.winfo_exists())
        self.assertTrue(self.programa.grafico_mensal.tela.winfo_exists())

    def test_contas_em_cartao_centralizado_com_metade_da_area(self):
        self.root.geometry('1600x900')
        self.programa.mostrar_contas()
        self.root.update()
        janela = self.programa.janela_contas
        area, cartao = janela.area, janela.cartao
        self.assertEqual(cartao.winfo_manager(), 'place')
        self.assertEqual(str(cartao.cget('style')), 'Cartao.TFrame')
        from visual import px
        # Metade da área, sem ficar abaixo da largura mínima (a barra lateral ocupa parte da janela).
        self.assertAlmostEqual(cartao.winfo_width(), max(px(cartao, 660), area.winfo_width() // 2), delta=2)
        self.assertLess(cartao.winfo_height(), area.winfo_height())
        centro_cartao = cartao.winfo_rootx() + cartao.winfo_width() / 2
        centro_area = area.winfo_rootx() + area.winfo_width() / 2
        self.assertLessEqual(abs(centro_cartao - centro_area), 2)
        for texto in ('Cadastrar nova conta', 'Ver / Editar', 'Desativar / Reativar', 'Remover'):
            item = botao(cartao, texto)
            self.assertTrue(item.winfo_ismapped())
            self.assertLessEqual(item.winfo_rootx() + item.winfo_width(), cartao.winfo_rootx() + cartao.winfo_width())
        self.assertIs(janela.tabela.master, cartao)
        self.root.geometry('900x620')
        self.root.update()
        self.assertGreaterEqual(cartao.winfo_width(), min(660, area.winfo_width()))
        self.assertLessEqual(cartao.winfo_width(), area.winfo_width())

    def test_medidas_acompanham_a_escala_da_tela(self):
        from visual import fator_escala, px
        for dpi, fator in ((72.0, 1.0), (96.0, 1.0), (120.0, 1.25), (144.0, 1.5)):
            with self.subTest(dpi=dpi):
                if hasattr(self.root, '_fator_escala'):
                    del self.root._fator_escala
                with patch.object(tk.Misc, 'winfo_fpixels', return_value=dpi):
                    self.assertAlmostEqual(fator_escala(self.root), fator)
                    self.assertEqual(px(self.root, 40), round(40 * fator))
        del self.root._fator_escala
        tela = tk.Toplevel(self.root)
        with patch.object(tk.Misc, 'winfo_fpixels', return_value=144.0):
            from componentes import centralizar
            centralizar(tela, 400, 300)
        self.root.update()
        self.assertEqual((tela.winfo_width(), tela.winfo_height()), (600, 450))
        tela.destroy()

    def test_arte_entra_em_quatro_segundos_e_depois_fica_parada(self):
        import time
        import arte_inicio
        self.root.geometry('1600x900')
        self.root.update()
        self.root.update()
        arte = self.programa.arte_inicio
        cartao = arte.master
        _faixa, titulo, descricao, botao_entrada = self.programa.partes_inicio[cartao]
        self.assertAlmostEqual(arte_inicio.duracao_total(), 4.0, delta=0.4)
        # A arte é o elemento mais baixo do cartão e fica fora da área dos textos e do botão.
        self.assertEqual(self.root.tk.call('winfo', 'children', str(cartao))[0], str(arte))
        self.assertEqual(arte.winfo_manager(), 'place')
        self.assertGreaterEqual(arte.winfo_x(), descricao.winfo_x() + descricao.winfo_width())
        self.assertLessEqual(arte.winfo_y() + arte.winfo_height(), botao_entrada.winfo_y())
        # No começo da entrada, a primeira placa já aparece e a última ainda não.
        arte.inicio = time.monotonic() - 0.4
        arte.desenhar()
        estados = [arte.itemcget(vidro, 'state') for _brilho, vidro in arte.itens]
        self.assertEqual((estados[0], estados[-1]), ('normal', 'hidden'))
        # Depois da entrada, todas ficam no nível máximo e paradas.
        arte.inicio = time.monotonic() - arte_inicio.duracao_total() - 2.0
        arte.desenhar()
        finais = {arte.itemcget(item, 'image') for par in arte.itens for item in par}
        esperadas = {str(arte.imagens[i, camada, arte_inicio.NIVEIS - 1]) for i in range(len(arte.itens)) for camada in (0, 1)}
        self.assertEqual(finais, esperadas)
        antes = [arte.coords(vidro) for _brilho, vidro in arte.itens]
        arte.inicio -= 2.5
        arte.desenhar()
        depois = [arte.coords(vidro) for _brilho, vidro in arte.itens]
        self.assertEqual(antes, depois)
        # Terminada a entrada, o relógio encerra o laço.
        self.assertTrue(arte.terminou())
        relogio = self.programa.relogio_inicio
        relogio.parar()
        relogio.quadro()
        self.assertIsNone(relogio.agendamento)
        # Trocar de tema só troca as imagens: não reinicia a animação.
        inicio = arte.inicio
        self.programa.alternar_tema()
        self.root.update()
        self.assertEqual(arte.inicio, inicio)
        self.assertEqual(arte.cget('bg'), PALETAS['escuro']['heroi'])  # Sobre o cartão de destaque, em nanquim.
        self.assertIn(arte.itemcget(arte.itens[-1][1], 'image'),
                      {str(imagem) for imagem in arte_inicio.imagens_vidro(self.root, 'escuro').values()})
        luzes = self.programa.luzes_inicio
        self.assertEqual({self.programa.inicio.itemcget(i, 'image') for i in luzes.itens},
                         {str(imagem) for imagem in arte_inicio.imagens_luz(self.root, 'escuro')})

    def test_animacao_pausa_fora_da_tela_inicial(self):
        relogio = self.programa.relogio_inicio
        desenhos = []
        relogio.animados = (SimpleNamespace(desenhar=lambda: desenhos.append(1)),)
        relogio.parar()
        relogio.quadro()
        self.assertEqual(len(desenhos), 1)
        self.programa.mostrar_historico()
        self.root.update()
        relogio.parar()
        relogio.quadro()
        self.assertEqual(len(desenhos), 1)
        self.assertIsNotNone(relogio.agendamento)
        self.programa.voltar()
        self.root.update()
        relogio.parar()
        relogio.quadro()
        self.assertEqual(len(desenhos), 2)

    def test_luzes_de_fundo_ficam_atras_de_tudo_e_paradas(self):
        tela = self.programa.inicio
        luzes = self.programa.luzes_inicio
        self.assertEqual(tela.find_all()[:len(luzes.itens)], tuple(luzes.itens))
        antes = [tela.coords(i) for i in luzes.itens]
        luzes.desenhar()
        self.assertEqual([tela.coords(i) for i in luzes.itens], antes)

    def test_arte_de_vidro_comeca_sozinha_ao_abrir(self):
        arte = self.programa.arte_inicio
        self.root.after(400, lambda: None)
        fim = self.root.tk.call('clock', 'milliseconds') + 600
        while self.root.tk.call('clock', 'milliseconds') < fim:
            self.root.update()
        self.assertIsNotNone(arte.inicio)

    def test_outro_tema_preparado_em_segundo_plano_sem_trocar_o_visivel(self):
        estilo = ttk.Style(self.root)
        self.assertNotIn('VitoranProEscuro', estilo.theme_names())
        self.programa.preparar_outro_tema()
        self.root.update()
        self.assertIn('VitoranProEscuro', estilo.theme_names())
        self.assertEqual(estilo.theme_use(), 'VitoranProClaro')
        self.assertEqual(cores(), PALETAS['claro'])
        with patch.object(estilos, 'aplicar_superficies', side_effect=AssertionError('O tema já deveria estar pronto')):
            self.programa.alternar_tema()
            self.root.update()
        self.assertEqual(estilo.theme_use(), 'VitoranProEscuro')
        self.assertEqual(str(estilo.lookup('TButton', 'foreground')), PALETAS['escuro']['texto'])
        self.programa.preparar_outro_tema()
        self.assertEqual(self.erros, [])

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


if __name__ == '__main__':
    unittest.main()
