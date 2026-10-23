import unittest
from datetime import date

from dados import situacao
from grafico import escala, resumo_mensal, rotulo_mes, valor_curto


def registro(aquisicao, custo, previsto, recebimento=None, previsao_atual='2026-12-01'):
    return dict(aquisicao=aquisicao, custo=custo, previsto=previsto, recebimento=recebimento,
                previsao_atual=previsao_atual)


class TestGrafico(unittest.TestCase):
    def test_resumo_mensal_agrupa_aquisicao_e_recebimento_nos_ultimos_doze_meses(self):
        registros = [registro('2026-03-10', 300000, 500000, '2026-06-08'),
                     registro('2026-03-25', 100000, 150000),
                     registro('2025-10-31', 999900, 999900, '2026-10-01'),
                     registro('2026-10-02', 200000, 260000, '2026-10-20')]
        meses = resumo_mensal(registros, hoje=date(2026, 10, 23))
        self.assertEqual(len(meses), 12)
        self.assertEqual(meses[0][0], '2025-11')
        self.assertEqual(meses[-1][0], '2026-10')
        totais = {chave: (investido, recebido) for chave, investido, recebido in meses}
        self.assertEqual(totais['2026-03'], (400000, 0))
        self.assertEqual(totais['2026-06'], (0, 500000))
        self.assertEqual(totais['2026-10'], (200000, 999900 + 260000))
        self.assertNotIn('2025-10', totais)

    def test_resumo_mensal_atravessa_a_virada_do_ano(self):
        meses = resumo_mensal([], meses=3, hoje=date(2027, 1, 5))
        self.assertEqual([m[0] for m in meses], ['2026-11', '2026-12', '2027-01'])

    def test_escala_e_rotulos(self):
        self.assertEqual(escala(0), 100000)
        self.assertEqual(escala(4860000), 6000000)
        self.assertEqual(escala(4000000), 4000000)
        self.assertEqual(escala(120000000), 200000000)
        self.assertEqual(valor_curto(1500000), 'R$ 15 mil')
        self.assertEqual(valor_curto(1250000), 'R$ 12,5 mil')
        self.assertEqual(valor_curto(150000000), 'R$ 1,5 mi')
        self.assertEqual(valor_curto(25000), 'R$ 250')
        self.assertEqual(rotulo_mes('2026-03'), 'mar/26')

    def test_situacao_recebida_atrasada_ou_pendente(self):
        hoje = date(2026, 10, 23)
        self.assertEqual(situacao(registro('2026-01-01', 1, 2, '2026-05-01', '2026-01-01'), hoje), 'recebida')
        self.assertEqual(situacao(registro('2026-01-01', 1, 2, None, '2026-10-22'), hoje), 'atrasada')
        self.assertEqual(situacao(registro('2026-01-01', 1, 2, None, '2026-10-23'), hoje), 'pendente')


if __name__ == '__main__':
    unittest.main()
