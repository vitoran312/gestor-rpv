import unittest
from calculadora import MotorCalculadora


class TestCalculadora(unittest.TestCase):
    def calcular(self, teclas):
        motor = MotorCalculadora()
        for tecla in teclas:
            motor.clicar(tecla)
        return motor

    def test_operacoes_decimais_e_contas_encadeadas(self):
        for teclas, esperado in (
            (('1', '2', '+', '3', '='), '15'),
            (('9', '−', '1', '4', '='), '-5'),
            (('2', ',', '5', '×', '4', '='), '10'),
            (('1', '0', '÷', '4', '='), '2,5'),
            (('0', ',', '1', '+', '0', ',', '2', '='), '0,3'),
            (('2', '+', '3', '×', '4', '='), '20'),
        ):
            with self.subTest(teclas=teclas):
                self.assertEqual(self.calcular(teclas).texto, esperado)

    def test_porcentagem_repeticao_e_troca_de_operacao(self):
        self.assertEqual(self.calcular(('2', '0', '0', '+', '1', '0', '%', '=')).texto, '220')
        self.assertEqual(self.calcular(('2', '0', '0', '×', '1', '0', '%', '=')).texto, '20')
        self.assertEqual(self.calcular(('2', '+', '3', '=', '=')).texto, '8')
        self.assertEqual(self.calcular(('2', '+', '×', '3', '=')).texto, '6')

    def test_divisao_por_zero_e_recuperacao(self):
        motor = self.calcular(('8', '÷', '0', '='))
        self.assertTrue(motor.erro)
        self.assertEqual(motor.texto, 'Não divide por zero')
        motor.clicar('5')
        self.assertEqual(motor.texto, '5')
        self.assertFalse(motor.erro)

    def test_apagar_sinal_e_limpar(self):
        self.assertEqual(self.calcular(('1', '2', '3', '⌫')).texto, '12')
        self.assertEqual(self.calcular(('5', '±')).texto, '-5')
        self.assertEqual(self.calcular(('2', '+', '±', '3', '=')).texto, '-1')
        self.assertEqual(self.calcular(('9', '+', 'C', '2', '=')).texto, '2')


if __name__ == '__main__':
    unittest.main()
