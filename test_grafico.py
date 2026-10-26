import unittest
from datetime import date

from dados import situacao
from grafico import escala, quantidade, resumo_mensal, rotulo_mes


def registro(aquisicao, custo, previsto, recebimento=None, previsao_atual='2026-12-01'):
    return dict(aquisicao=aquisicao, custo=custo, previsto=previsto, recebimento=recebimento,
                previsao_atual=previsao_atual)


class TestGrafico(unittest.TestCase):
    def test_resumo_mensal_conta_aquisicao_e_recebimento_nos_ultimos_doze_meses(self):
        registros = [registro('2026-03-10', 300000, 500000, '2026-06-08'),
                     registro('2026-03-25', 100000, 150000),
                     registro('2025-10-31', 999900, 999900, '2026-10-01'),
                     registro('2026-10-02', 200000, 260000, '2026-10-20')]
        meses = resumo_mensal(registros, hoje=date(2026, 10, 23))
        self.assertEqual(len(meses), 12)
        self.assertEqual(meses[0][0], '2025-11')
        self.assertEqual(meses[-1][0], '2026-10')
        totais = {chave: (entradas, recebidas) for chave, entradas, recebidas in meses}
        self.assertEqual(totais['2026-03'], (2, 0))
        self.assertEqual(totais['2026-06'], (0, 1))
        self.assertEqual(totais['2026-10'], (1, 2))
        self.assertNotIn('2025-10', totais)

    def test_resumo_mensal_atravessa_a_virada_do_ano(self):
        meses = resumo_mensal([], meses=3, hoje=date(2027, 1, 5))
        self.assertEqual([m[0] for m in meses], ['2026-11', '2026-12', '2027-01'])

    def test_escala_e_rotulos(self):
        self.assertEqual(escala(0), 4)
        self.assertEqual(escala(3), 4)
        self.assertEqual(escala(5), 8)
        self.assertEqual(escala(9), 20)
        self.assertEqual(escala(37), 40)
        self.assertEqual(escala(41), 80)
        self.assertEqual(quantidade(1, 'entrada', 'entradas'), '1 entrada')
        self.assertEqual(quantidade(3, 'entrada', 'entradas'), '3 entradas')
        self.assertEqual(rotulo_mes('2026-03'), 'mar/26')

    def test_situacao_recebida_atrasada_ou_pendente(self):
        hoje = date(2026, 10, 23)
        self.assertEqual(situacao(registro('2026-01-01', 1, 2, '2026-05-01', '2026-01-01'), hoje), 'recebida')
        self.assertEqual(situacao(registro('2026-01-01', 1, 2, None, '2026-10-22'), hoje), 'atrasada')
        self.assertEqual(situacao(registro('2026-01-01', 1, 2, None, '2026-10-23'), hoje), 'pendente')


if __name__ == '__main__':
    unittest.main()
