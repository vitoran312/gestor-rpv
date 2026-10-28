import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from exportacao import COLUNAS, coluna_letra, exportar_excel, serial_excel
from test_contas import banco_com_contas, dados_rpv

NS = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def ler_planilha(arquivo):
    with ZipFile(arquivo) as pacote:
        raiz = ElementTree.fromstring(pacote.read('xl/worksheets/sheet1.xml'))
        ElementTree.fromstring(pacote.read('xl/workbook.xml'))
        ElementTree.fromstring(pacote.read('xl/styles.xml'))
    linhas = []
    for linha in raiz.iterfind('.//x:sheetData/x:row', NS):
        valores = []
        for celula in linha.iterfind('x:c', NS):
            texto = celula.find('x:is/x:t', NS)
            valor = celula.find('x:v', NS)
            valores.append(texto.text if texto is not None else valor.text if valor is not None else None)
        linhas.append(valores)
    return linhas


class TestExportacao(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name)
        self.banco = banco_com_contas(self.pasta / 'gestor.sqlite3')

    def test_planilha_tem_cabecalho_valores_datas_e_situacao(self):
        recebida = self.banco.salvar(dados_rpv(nome='Pessoa <&> "aspas"', comissao=15050, observacoes='Linha\x01 extra'))
        self.banco.salvar(dados_rpv(nome='Pendente', aquisicao='2026-10-23', previsao='2099-12-31'))
        self.banco.salvar(dados_rpv(nome='Atrasada', aquisicao='2020-01-01', previsao='2020-02-01',
                                    observacoes='a\ufffeb\uffffc'))
        self.banco.registrar_recebimento(recebida, '2026-10-22')
        lixo = self.banco.salvar(dados_rpv(nome='Na lixeira'))
        self.banco.excluir(lixo)
        destino = exportar_excel(self.banco.listar(), self.pasta / 'saida' / 'operacoes')
        self.assertEqual(destino.name, 'operacoes.xlsx')
        linhas = ler_planilha(destino)
        self.assertEqual(linhas[0], [titulo for titulo, _tipo, _largura in COLUNAS])
        self.assertEqual(len(linhas), 4)
        pendente, recebida, atrasada = linhas[1], linhas[2], linhas[3]
        self.assertEqual(atrasada[9], 'Atrasada')
        self.assertEqual(pendente[0], 'Pendente')
        self.assertEqual(pendente[9], 'Pendente')
        self.assertIsNone(pendente[10])
        self.assertEqual(recebida[0], 'Pessoa <&> "Aspas"')
        self.assertEqual(recebida[1], str(serial_excel('2026-10-22')))
        self.assertEqual(recebida[2:6], ['12000.00', '150.50', '20000.00', '8000.00'])
        self.assertEqual(recebida[9], 'Recebido')
        self.assertEqual(recebida[11], 'Linha extra')
        self.assertEqual(atrasada[11], 'Abc')

    def test_extensao_de_outra_planilha_e_trocada_por_xlsx(self):
        self.banco.salvar(dados_rpv())
        for nome, esperado in (('relatorio.csv', 'relatorio.xlsx'), ('relatorio.XLS', 'relatorio.xlsx'),
                               ('relatorio', 'relatorio.xlsx'), ('mes.10', 'mes.10.xlsx')):
            with self.subTest(nome):
                self.assertEqual(exportar_excel(self.banco.listar(), self.pasta / nome).name, esperado)

    def test_celula_respeita_o_limite_do_excel(self):
        from exportacao import LIMITE_CELULA, limitar_celula
        self.assertEqual(limitar_celula('curto'), 'curto')
        longo = limitar_celula('a' * 40000)
        self.assertEqual((len(longo), longo[-1]), (LIMITE_CELULA, '…'))
        emojis = limitar_celula('😀' * 20000)  # Cada emoji ocupa dois caracteres no Excel.
        self.assertLessEqual(len(emojis.encode('utf-16-le')) // 2, LIMITE_CELULA)
        self.assertTrue(emojis.endswith('😀…'))
        self.assertEqual(list(self.pasta.glob('saida/*.tmp')), [])

    def test_auxiliares_de_coluna_e_data(self):
        self.assertEqual([coluna_letra(i) for i in (0, 11, 25, 26, 27)], ['A', 'L', 'Z', 'AA', 'AB'])
        self.assertEqual(serial_excel('1900-03-01'), 61)
        self.assertEqual(serial_excel('2026-01-01'), 46023)


if __name__ == '__main__':
    unittest.main()
