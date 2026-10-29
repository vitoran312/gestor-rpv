"""Acabamento da interface: movimento, validação apontando o campo, avisos passageiros, estados vazios e realce."""
import os
import tkinter as tk
import unittest
from tkinter import ttk
from unittest.mock import Mock, patch

import contas
import movimento
import tela_registro
from apoio_interface import TesteDeInterface, botao, filhos
from apoio_testes import dados_rpv
from tema import cores


class TestMovimento(unittest.TestCase):
    def test_curva_ease_out_da_skill(self):
        # cubic-bezier(0.23, 1, 0.32, 1): começa rápido e assenta devagar, sem passar do fim.
        valores = [movimento.EASE_OUT(x / 10) for x in range(11)]
        self.assertEqual((valores[0], valores[-1]), (0.0, 1.0))
        self.assertEqual(valores, sorted(valores))
        self.assertGreater(movimento.EASE_OUT(0.25), 0.7)
        linear = movimento.bezier(0, 0, 1, 1)
        for x in (0.1, 0.5, 0.9):
            self.assertAlmostEqual(linear(x), x, places=3)

    def test_movimento_reduzido_vai_direto_ao_fim(self):
        chamadas = []
        widget = Mock()
        with patch.dict(os.environ, {'GESTOR_RPV_SEM_ANIMACAO': '1'}):
            self.assertTrue(movimento.movimento_reduzido())
            movimento.animar(widget, 200, chamadas.append, lambda: chamadas.append('fim'))
        self.assertEqual(chamadas, [1.0, 'fim'])
        widget.after.assert_not_called()


class TestCamposComProblema(unittest.TestCase):
    def test_cada_regra_aponta_o_campo(self):
        casos = {
            'Informe o nome completo do titular original.': ['nome'],
            'A data da aquisição não pode estar no futuro.': ['aquisicao'],
            'A previsão não pode ser anterior à aquisição.': ['previsao'],
            'O valor de aquisição não pode superar o Valor Total RPV.': ['custo'],
            'A comissão não pode superar o Valor Total RPV.': ['comissao'],
            'Valor Total RPV: valor inválido.': ['previsto'],
            'Prazo em dias: informe um número.': ['previsao'],
        }
        for problema, esperado in casos.items():
            with self.subTest(problema):
                self.assertEqual(tela_registro.campos_com_problema([problema], set()), esperado)
        # Na ordem do formulário, para o foco ir ao primeiro.
        self.assertEqual(tela_registro.campos_com_problema(list(casos), set()),
                         ['nome', 'aquisicao', 'previsto', 'custo', 'previsao', 'comissao'])

    def test_mensagens_da_conta_apontam_os_campos(self):
        self.assertEqual(contas.campos_da_mensagem('Preencha: Nome completo, CPF, Chave Pix.'), ['nome', 'cpf', 'pix'])
        self.assertEqual(contas.campos_da_mensagem('Essa chave Pix já está cadastrada em outra conta.'), ['pix'])
        self.assertEqual(contas.campos_da_mensagem('Selecione um estado brasileiro válido.'), ['estado'])


@unittest.skipUnless(os.environ.get('GESTOR_RPV_TESTE_UI') == '1', 'Requer sessão gráfica e GESTOR_RPV_TESTE_UI=1')
class TestAcabamentoNaInterface(TesteDeInterface):
    def aviso_atual(self):
        notificacao = getattr(self.root, '_notificacao', None)
        return notificacao.rotulo.cget('text') if notificacao is not None else None

    def test_salvar_com_problemas_contorna_os_campos_e_some_ao_corrigir(self):
        tela = self.formulario()
        botao(tela, 'Salvar registro').invoke()
        self.root.update()
        self.assertEqual(self.dialogos[-1][0], 'showerror')
        entradas = [w for w in filhos(tela) if isinstance(w, ttk.Entry)]
        com_erro = [w for w in entradas if 'Erro.' in str(w.cget('style'))]
        nome = entradas[0]
        self.assertIn(nome, com_erro)
        self.assertEqual(str(ttk.Style().lookup(nome.cget('style'), 'bordercolor', ['!disabled'])), cores()['vermelho'])
        # Mexer no campo tira o contorno; os outros continuam marcados.
        nome.insert(0, 'Fulano de Tal')
        self.root.update()
        self.assertNotIn('Erro.', str(nome.cget('style')))
        self.assertTrue(any('Erro.' in str(w.cget('style')) for w in entradas))

    def test_salvar_entrada_mostra_aviso_passageiro(self):
        tela = self.formulario()
        campos = [w for w in filhos(tela) if isinstance(w, ttk.Entry)]
        campos[0].insert(0, 'Fulano de Tal')
        tela_previsao = next(w for w in filhos(tela) if isinstance(w, ttk.Entry) and w.get() == '')
        tela_previsao.insert(0, '20/12/2026')
        for entrada, valor in zip([w for w in filhos(tela) if isinstance(w, ttk.Entry) and w.get() == '0,00'],
                                  ('2.000.000,00', '1.200.000,00')):
            entrada.delete(0, 'end')
            entrada.insert(0, valor)
        botao(tela, 'Salvar registro').invoke()
        self.root.update()
        self.assertEqual(len(self.banco.listar()), 1, self.dialogos)
        self.assertEqual(self.aviso_atual(), 'Entrada salva.')
        # Um segundo aviso substitui o primeiro, sem empilhar.
        from componentes import notificar
        notificar(self.root, 'Outro aviso.')
        self.root.update()
        self.assertEqual(sum(isinstance(w, tk.Frame) and w.winfo_manager() == 'place' and w.cget('bg') == cores()['notificacao']
                             for w in self.root.winfo_children()), 1)

    def test_estado_vazio_explica_a_tabela_sem_linhas(self):
        self.programa.mostrar_historico()
        self.root.update()
        vazio = self.programa.vazio_operacoes
        self.assertTrue(vazio.visivel)
        self.assertEqual(vazio.titulo.cget('text'), 'Nenhuma operação cadastrada')
        self.banco.salvar(dados_rpv(nome='Alguém'))
        self.programa.atualizar()
        self.root.update()
        self.assertFalse(vazio.visivel)
        self.programa.busca.set('zzz')
        self.root.update()
        self.assertTrue(vazio.visivel)
        self.assertEqual(vazio.titulo.cget('text'), 'Nada encontrado para “zzz”')
        self.programa.busca.set('')
        self.programa.filtro.set('atrasada')
        self.programa.atualizar()
        self.assertEqual(vazio.titulo.cget('text'), 'Nenhuma operação atrasada')

    def test_busca_com_dica_e_botao_de_limpar(self):
        self.programa.mostrar_historico()
        self.root.update()
        campo = self.programa.barra_busca.winfo_children()[0]
        self.assertTrue(campo.dica.winfo_ismapped())
        self.assertFalse(campo.limpar.winfo_ismapped())
        self.programa.busca.set('ana')
        self.root.update()
        self.assertFalse(campo.dica.winfo_ismapped())
        self.assertTrue(campo.limpar.winfo_ismapped())
        campo.limpar.event_generate('<Button-1>')
        self.root.update()
        self.assertEqual(self.programa.busca.get(), '')
        self.assertTrue(campo.dica.winfo_ismapped())

    def test_realce_da_linha_sob_o_mouse_respeita_a_cor_da_linha(self):
        from selecao import realcar
        normal = self.banco.salvar(dados_rpv(nome='Normal', previsao='2099-01-01'))
        atrasada = self.banco.salvar(dados_rpv(nome='Atrasada', aquisicao='2020-01-01', previsao='2020-02-01'))
        self.programa.mostrar_historico()
        self.root.update()
        tabela = self.programa.tabela
        realcar(tabela, str(atrasada))
        self.assertIn('realce_atrasada', tabela.item(str(atrasada), 'tags'))
        realcar(tabela, str(normal))
        self.assertNotIn('realce_atrasada', tabela.item(str(atrasada), 'tags'))
        self.assertIn('realce', tabela.item(str(normal), 'tags'))
        # O realce vence o fundo da linha (prioridade da tag criada primeiro).
        nomes = list(tabela.tk.splitlist(tabela.tk.call(tabela, 'tag', 'names')))
        self.assertLess(nomes.index('realce_atrasada'), nomes.index('atrasada'))
        realcar(tabela, '')
        self.assertNotIn('realce', tabela.item(str(normal), 'tags'))

    def test_excluir_avisa_e_lixeira_vazia_explica(self):
        identificador = self.banco.salvar(dados_rpv(nome='Some'))
        self.programa.mostrar_historico()
        self.root.update()
        self.programa.tabela.selection_set(str(identificador))
        self.programa.excluir()
        self.root.update()
        self.assertEqual(self.aviso_atual(), '1 entrada enviada à lixeira.')
        self.banco.restaurar(identificador)
        self.programa.mostrar_lixeira()
        self.root.update()
        tela = self.programa.janela_lixeira
        tabela = next(w for w in filhos(tela) if isinstance(w, ttk.Treeview))
        self.assertTrue(any(isinstance(w, ttk.Label) and w.cget('text') == 'A lixeira está vazia' and w.winfo_ismapped()
                            for w in filhos(tabela)))

    def test_botoes_mostram_o_foco_do_teclado(self):
        # O botão com foco (Tab) tem superfície própria, com o contorno da marca, nos dois temas.
        for modo in ('claro', 'escuro'):
            if self.programa.modo_tema.get() != modo:
                self.programa.alternar_tema()
                self.root.update()
            _prefixo, imagens = self.root._superficies_pro[cores()['fundo']]
            self.assertIn('foco', imagens)
            self.assertIn('primario_foco', imagens)


if __name__ == '__main__':
    unittest.main()
