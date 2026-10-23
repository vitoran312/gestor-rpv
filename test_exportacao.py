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
        self.banco.salvar(dados_rpv(nome='Pendente', aquisicao='2026-10-23'))
        self.banco.registrar_recebimento(recebida, '2026-10-22')
        lixo = self.banco.salvar(dados_rpv(nome='Na lixeira'))
        self.banco.excluir(lixo)
        destino = exportar_excel(self.banco.listar(), self.pasta / 'saida' / 'operacoes')
        self.assertEqual(destino.name, 'operacoes.xlsx')
        linhas = ler_planilha(destino)
        self.assertEqual(linhas[0], [titulo for titulo, _tipo, _largura in COLUNAS])
        self.assertEqual(len(linhas), 3)
        pendente, recebida = linhas[1], linhas[2]
        self.assertEqual(pendente[0], 'Pendente')
        self.assertEqual(pendente[9], 'Pendente')
        self.assertIsNone(pendente[10])
        self.assertEqual(recebida[0], 'Pessoa <&> "Aspas"')
        self.assertEqual(recebida[1], str(serial_excel('2026-10-22')))
        self.assertEqual(recebida[2:6], ['12000.00', '150.50', '20000.00', '8000.00'])
        self.assertEqual(recebida[9], 'Recebido')
        self.assertEqual(recebida[11], 'Linha extra')
        self.assertEqual(list(self.pasta.glob('saida/*.tmp')), [])

    def test_auxiliares_de_coluna_e_data(self):
        self.assertEqual([coluna_letra(i) for i in (0, 11, 25, 26, 27)], ['A', 'L', 'Z', 'AA', 'AB'])
        self.assertEqual(serial_excel('1900-03-01'), 61)
        self.assertEqual(serial_excel('2026-01-01'), 46023)


if __name__ == '__main__':
    unittest.main()
