import tempfile
import unittest
from pathlib import Path
from dados import Banco, centavos, moeda, data_iso


class TestDados(unittest.TestCase):
    def test_valores_e_datas(self):
        self.assertEqual(centavos('20.000,00'), 2000000)
        self.assertEqual(centavos('12000,50'), 1200050)
        self.assertEqual(moeda(-800050), '-8.000,50')
        self.assertEqual(data_iso('22/10/2026'), '2026-10-22')
        for invalido in ('NaN', 'Infinity', '-1', '12,345', ''):
            with self.assertRaises(ValueError):
                centavos(invalido)
        with self.assertRaises(ValueError):
            data_iso('31/02/2026')

    def test_persistencia_edicao_comissao_e_registros_distintos(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / 'teste.sqlite3'
            banco = Banco(caminho)
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
            self.assertEqual(reaberto.obter(segundo)['nome'], 'Pessoa de teste')


if __name__ == '__main__':
    unittest.main()
