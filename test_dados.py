import tempfile
import unittest
from pathlib import Path
from dados import Banco, centavos, data_br, moeda, data_iso, previsao_por_prazo
from test_contas import banco_com_contas


class TestDados(unittest.TestCase):
    def test_previsao_em_dias_corridos(self):
        for aquisicao,prazo,prevista in (
            ('28/02/2028','1','29/02/2028'),
            ('28/02/2027','1','01/03/2027'),
            ('28/12/2026','10','07/01/2027'),
            ('22/10/2026','0','22/10/2026'),
        ):
            self.assertEqual(previsao_por_prazo(aquisicao,prazo),prevista)
        for prazo in ('','-1','1,5','1.5','abc','999999999999999999999'):
            with self.assertRaises(ValueError):
                previsao_por_prazo('22/10/2026',prazo)
        with self.assertRaises(ValueError):
            previsao_por_prazo('31/02/2026','2')

    def test_valores_e_datas(self):
        self.assertEqual(centavos('20.000,00'), 2000000)
        self.assertEqual(centavos('12000,50'), 1200050)
        self.assertEqual(moeda(-800050), '-8.000,50')
        self.assertEqual(data_iso('22/10/2026'), '2026-10-22')
        self.assertEqual(centavos('R$ 1.000,00'), 100000)
        self.assertEqual(centavos('1500.5'), 150050)
        for invalido in ('NaN', 'Infinity', '-1', '12,345', '', '1e3', '1E2', '2e-2', '1_000', '١٢٣', '１２３',
                         '+5', '.5', '5.', '1,2,3', 'abc'):
            with self.assertRaises(ValueError):
                centavos(invalido)
        with self.assertRaises(ValueError):
            data_iso('31/02/2026')
        for fora in ('01/01/0001', '01/01/0026', '31/12/1899', '01/01/2101', '01/01/9999'):
            with self.subTest(fora), self.assertRaisesRegex(ValueError, '1900 e 2100'):
                data_iso(fora)
        self.assertEqual(data_iso('01/01/1900'), '1900-01-01')
        self.assertEqual(data_br('0026-01-01'), '01/01/0026')
        with self.assertRaisesRegex(ValueError, 'depois de 2100'):
            previsao_por_prazo('01/01/2026', '99999')

    def test_persistencia_edicao_comissao_e_registros_distintos(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / 'teste.sqlite3'
            banco = banco_com_contas(caminho)
            dados = dict(nome='Pessoa de teste', aquisicao='2026-10-22',
                         previsto=2000000, custo=1200000, conta='Vitor',
                         previsao='2026-12-20', comissao=50000, observacoes='Teste')
            primeiro = banco.salvar(dados)
            segundo = banco.salvar(dados)
            self.assertNotEqual(primeiro, segundo)
            reaberto = Banco(caminho)
            self.assertEqual(len(reaberto.listar()), 2)
            registro = reaberto.obter(primeiro)
            self.assertEqual(registro['previsto'] - registro['custo'], 800000)
            self.assertEqual(registro['comissao'], 50000)
            dados.update(nome="Nome com ' apóstrofo", conta='Lilian', comissao=None)
            reaberto.salvar(dados, primeiro)
            self.assertEqual(reaberto.obter(primeiro)['conta'], 'Lilian')
            self.assertIsNone(reaberto.obter(primeiro)['comissao'])
            self.assertEqual(len(reaberto.listar('APÓSTROFO')), 1)
            self.assertEqual(len(reaberto.listar('22/10/2026')), 2)
            self.assertEqual(reaberto.obter(segundo)['nome'], 'Pessoa De Teste')

    def test_regras_da_entrada_valem_na_gravacao_sem_depender_da_tela(self):
        from datetime import date, timedelta
        from test_contas import dados_rpv
        with tempfile.TemporaryDirectory() as pasta:
            banco = banco_com_contas(Path(pasta) / 'teste.sqlite3')
            amanha = (date.today() + timedelta(days=1)).isoformat()
            for valores, mensagem in (
                (dict(aquisicao=amanha, previsao='2099-01-01'), 'aquisição não pode estar no futuro'),
                (dict(aquisicao='2026-05-10', previsao='2026-05-01'), 'previsão não pode ser anterior'),
                (dict(comissao=2000001), 'comissão não pode superar'),
                (dict(aquisicao='0001-01-01'), 'entre 1900 e 2100'),
                (dict(previsao='31/12/2026'), 'Previsão de recebimento: informe uma data válida'),
                (dict(nome='A' * 151), 'até 150 caracteres'),
                (dict(observacoes='x' * 5001), 'até 5000 caracteres'),
            ):
                with self.subTest(mensagem), self.assertRaisesRegex(ValueError, mensagem):
                    banco.salvar(dados_rpv(**valores))
            self.assertEqual(banco.listar(), [])
            self.assertTrue(banco.salvar(dados_rpv(comissao=2000000, previsao='2026-10-22')))

    def test_exclusao_persistente_preserva_outro_registro_igual(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / 'teste.sqlite3'
            banco = banco_com_contas(caminho)
            dados = dict(nome='Mesmo nome', aquisicao='2026-10-22',
                         previsto=2000000, custo=1200000, conta='Vitor',
                         previsao='2026-12-20', comissao=None, observacoes='')
            primeiro = banco.salvar(dados)
            segundo = banco.salvar(dados)
            banco.excluir(primeiro)
            reaberto = Banco(caminho)
            self.assertIsNotNone(reaberto.obter(primeiro)['lixeira_em'])
            self.assertEqual([r['id'] for r in reaberto.listar()], [segundo])
            self.assertEqual(reaberto.obter(segundo)['custo'], 1200000)


if __name__ == '__main__':
    unittest.main()
