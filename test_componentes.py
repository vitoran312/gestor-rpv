import unittest

from componentes import formatar_digitacao_moeda


class TestMoeda(unittest.TestCase):
    def test_digitacao_em_centavos_e_colagem(self):
        for entrada, esperado in (
            ('', '0,00'), ('1', '0,01'), ('10560,50', '10.560,50'),
            ('R$ 10.560,50', '10.560,50'), ('1.234', '1.234,00'),
            ('10560.50', '10.560,50'), ('0000100', '1,00'),
            ('999999999999,99', '999.999.999.999,99'),
            ('5200000', '52.000,00'), ('1523659', '15.236,59'),
            ('99999999999999', '999.999.999.999,99'),
        ):
            with self.subTest(entrada=entrada):
                self.assertEqual(formatar_digitacao_moeda(entrada), esperado)

    def test_rejeita_texto_negativos_e_valores_acima_do_limite(self):
        for entrada in ('abc', '-100', '100000000000000'):
            with self.subTest(entrada=entrada), self.assertRaises(ValueError):
                formatar_digitacao_moeda(entrada)


if __name__ == '__main__':
    unittest.main()
