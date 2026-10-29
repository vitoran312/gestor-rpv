"""A lista de novidades acompanha cada versão e é a mesma no programa e no app."""
import json
import unittest

import novidades
from versao import VERSAO


def numero(versao):
    return tuple(int(parte) for parte in versao.split('.'))


class TestNovidades(unittest.TestCase):
    def test_versao_atual_tem_novidades_escritas(self):
        # Ao mudar versao.py, a versão nova precisa entrar no topo de novidades.py.
        self.assertEqual(novidades.NOVIDADES[0][0], VERSAO)

    def test_versoes_em_ordem_e_itens_validos(self):
        versoes = [numero(v) for v, _ in novidades.NOVIDADES]
        self.assertEqual(versoes, sorted(versoes, reverse=True))
        self.assertEqual(len(versoes), len(set(versoes)))
        for versao, itens in novidades.NOVIDADES:
            with self.subTest(versao):
                self.assertTrue(itens)
                for tipo, texto in itens:
                    self.assertIn(tipo, ('novidade', 'correcao'))
                    self.assertTrue(texto.endswith('.') and len(texto) <= 160, texto)

    def test_contagem(self):
        self.assertEqual(novidades.contagem([('novidade', 'a.')]), '1 novidade')
        self.assertEqual(novidades.contagem([('novidade', 'a.'), ('novidade', 'b.'), ('correcao', 'c.')]),
                         '2 novidades · 1 correção')
        self.assertEqual(novidades.contagem([('correcao', 'a.'), ('correcao', 'b.')]), '2 correções')

    def test_app_mostra_o_mesmo_texto(self):
        # celular/novidades.json é gerado por "python novidades.py"; esquecer de gerar quebra este teste.
        self.assertEqual(json.loads(novidades.ARQUIVO_APP.read_text(encoding='utf-8')), novidades.para_o_app())
        self.assertEqual(len(novidades.para_o_app()['versoes']), novidades.MOSTRAR)


if __name__ == '__main__':
    unittest.main()
