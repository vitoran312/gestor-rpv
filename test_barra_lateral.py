"""Barra lateral: navegação entre as páginas, item ativo com filete, ações e modo recolhido."""
import os
import time
import unittest

from apoio_interface import TesteDeInterface
from apoio_testes import dados_rpv
from visual import px


@unittest.skipUnless(os.environ.get('GESTOR_RPV_TESTE_UI') == '1', 'Requer sessão gráfica e GESTOR_RPV_TESTE_UI=1')
class TestBarraLateral(TesteDeInterface):
    def test_itens_abrem_as_paginas_e_acendem(self):
        barra = self.programa.barra_lateral
        self.root.geometry('1600x900')
        self.root.update()
        self.assertEqual(barra.ativo, 'inicio')
        for chave, titulo in (('historico', 'Minhas operações'), ('contas', 'Contas de recebimento'),
                              ('grafico', 'Gráfico mensal')):
            barra.itens[chave].invoke()
            self.root.update()
            self.assertEqual(self.programa.pagina_atual().titulo_pagina, titulo)
            self.assertEqual(barra.ativo, chave)
            self.assertTrue(barra.itens[chave].instate(['selected']))
            self.assertEqual(sum(b.instate(['selected']) for b in barra.itens.values()), 1)
        # O filete chega ao item ativo (a animação termina em 200 ms).
        fim = time.monotonic() + 0.5
        while time.monotonic() < fim:
            self.root.update()
            time.sleep(0.01)
        botao = barra.itens['grafico']
        self.assertEqual(barra.indicador.winfo_manager(), 'place')
        self.assertAlmostEqual(int(barra.indicador.place_info()['y']), botao.winfo_y() + px(barra, 9), delta=1)
        barra.itens['inicio'].invoke()
        self.root.update()
        self.assertEqual(self.programa.paginas, [])
        self.assertEqual(barra.ativo, 'inicio')

    def test_nova_entrada_e_voltar_mantem_o_item_certo(self):
        barra = self.programa.barra_lateral
        self.banco.salvar(dados_rpv())
        barra.itens['historico'].invoke()
        self.root.update()
        barra.nova.invoke()
        self.root.update()
        self.assertIsNotNone(self.programa.janela_formulario)
        self.assertTrue(self.programa.janela_formulario.winfo_exists())
        self.programa.janela_formulario.destroy()
        self.programa.voltar()
        self.root.update()
        self.assertEqual(barra.ativo, 'inicio')

    def test_tema_sobre_e_sair_ficam_no_rodape_da_barra(self):
        barra = self.programa.barra_lateral
        for botao in (self.programa.botao_alternar_tema, self.programa.botao_sobre, self.programa.botao_sair):
            self.assertIs(botao.master.master, barra)
        modo = self.programa.modo_tema.get()
        self.programa.botao_alternar_tema.invoke()
        self.root.update()
        self.assertNotEqual(self.programa.modo_tema.get(), modo)

    def test_janela_estreita_recolhe_para_icones(self):
        barra = self.programa.barra_lateral
        self.root.geometry('1000x700')
        self.root.update()
        self.root.update()
        self.assertTrue(barra.recolhida)
        self.assertEqual(str(barra.itens['historico'].cget('compound')), 'image')
        self.assertEqual(barra.nova.cget('text'), '')
        self.assertFalse(barra.textos_marca.winfo_ismapped())
        self.root.geometry('1600x900')
        self.root.update()
        self.root.update()
        self.assertFalse(barra.recolhida)
        self.assertEqual(str(barra.itens['historico'].cget('compound')), 'left')
        self.assertEqual(barra.nova.cget('text'), 'Nova entrada')
        self.assertTrue(barra.textos_marca.winfo_ismapped())


if __name__ == '__main__':
    unittest.main()
