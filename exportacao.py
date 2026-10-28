"""Exportação das operações para planilha do Excel (.xlsx), sem dependências externas."""
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

from dados import situacao


COLUNAS = (
    ('Titular original', 'texto', 34),
    ('Data de aquisição', 'data', 16),
    ('Valor de aquisição', 'moeda', 18),
    ('Comissão', 'moeda', 14),
    ('Valor Total RPV', 'moeda', 18),
    ('Lucro previsto', 'moeda', 16),
    ('Conta de destino', 'texto', 20),
    ('Previsão inicial', 'data', 16),
    ('Previsão atual', 'data', 16),
    ('Situação', 'texto', 12),
    ('Data do recebimento', 'data', 18),
    ('Observações', 'texto', 40),
)
ESTILOS = {'cabecalho': 1, 'moeda': 2, 'data': 3, 'texto': 0}
# Tudo o que o XML 1.0 não aceita: controles, metades de pares substitutos e U+FFFE/U+FFFF.
INVALIDOS = re.compile('[^\x09\x0a\x0d\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]')
LIMITE_CELULA = 32767  # Caracteres por célula no Excel, contados em UTF-16.

CONTENT_TYPES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>'''

RAIZ_RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''

WORKBOOK = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Operações" sheetId="1" r:id="rId1"/></sheets>
<definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">'Operações'!$A$1:${ultima}${linhas}</definedName></definedNames>
</workbook>'''

WORKBOOK_RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="2"><numFmt numFmtId="164" formatCode="&quot;R$&quot; #,##0.00"/><numFmt numFmtId="165" formatCode="dd/mm/yyyy"/></numFmts>
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF551A2B"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="4">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''


def coluna_letra(indice):
    letras = ''
    indice += 1
    while indice:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def serial_excel(iso):
    return (date.fromisoformat(iso) - date(1899, 12, 30)).days


SITUACOES = {'recebida': 'Recebido', 'atrasada': 'Atrasada', 'pendente': 'Pendente'}


def linha_registro(registro):
    # A mesma situação da tela: atrasada quando a previsão atual passou sem recebimento.
    return (registro['nome'], registro['aquisicao'], registro['custo'], registro['comissao'] or 0,
            registro['previsto'], registro['previsto'] - registro['custo'], registro['conta'],
            registro['previsao'], registro['previsao_atual'], SITUACOES[situacao(registro)],
            registro['recebimento'], registro['observacoes'])


def limitar_celula(texto):
    if len(texto.encode('utf-16-le')) // 2 <= LIMITE_CELULA:
        return texto
    cortado = texto.encode('utf-16-le')[:(LIMITE_CELULA - 1) * 2].decode('utf-16-le', 'ignore')
    return cortado + '…'


def celula(referencia, valor, tipo, estilo=None):
    estilo = ESTILOS[tipo] if estilo is None else estilo
    atributo_estilo = f' s="{estilo}"' if estilo else ''
    if valor is None or valor == '':
        return f'<c r="{referencia}"{atributo_estilo}/>'
    if tipo == 'moeda':
        return f'<c r="{referencia}"{atributo_estilo}><v>{valor / 100:.2f}</v></c>'
    if tipo == 'data':
        return f'<c r="{referencia}"{atributo_estilo}><v>{serial_excel(valor)}</v></c>'
    texto = escape(limitar_celula(INVALIDOS.sub('', str(valor))))
    return f'<c r="{referencia}" t="inlineStr"{atributo_estilo}><is><t xml:space="preserve">{texto}</t></is></c>'


def planilha(registros):
    linhas = ['<row r="1">' + ''.join(celula(f'{coluna_letra(i)}1', titulo, 'texto', ESTILOS['cabecalho'])
                                      for i, (titulo, _tipo, _largura) in enumerate(COLUNAS)) + '</row>']
    for numero, registro in enumerate(registros, start=2):
        valores = linha_registro(registro)
        linhas.append(f'<row r="{numero}">' + ''.join(
            celula(f'{coluna_letra(i)}{numero}', valor, tipo)
            for i, (valor, (_titulo, tipo, _largura)) in enumerate(zip(valores, COLUNAS))) + '</row>')
    larguras = ''.join(f'<col min="{i}" max="{i}" width="{largura}" customWidth="1"/>'
                       for i, (_titulo, _tipo, largura) in enumerate(COLUNAS, start=1))
    ultima = coluna_letra(len(COLUNAS) - 1)
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
            '</sheetView></sheetViews>'
            f'<cols>{larguras}</cols><sheetData>{"".join(linhas)}</sheetData>'
            f'<autoFilter ref="A1:{ultima}{len(registros) + 1}"/></worksheet>')


def nome_sugerido():
    return 'GestorRPV-operacoes-' + datetime.now().strftime('%Y%m%d') + '.xlsx'


def exportar_excel(registros, destino):
    """Grava a planilha em um arquivo temporário e só então substitui o destino."""
    destino = Path(destino)
    if destino.suffix.casefold() in ('.csv', '.xls', '.ods', '.txt'):
        destino = destino.with_suffix('.xlsx')  # "relatorio.csv" vira "relatorio.xlsx", e não "relatorio.csv.xlsx".
    elif destino.suffix.casefold() != '.xlsx':
        destino = destino.with_name(destino.name + '.xlsx')
    destino.parent.mkdir(parents=True, exist_ok=True)
    registros = list(registros)
    descritor, temporario = tempfile.mkstemp(prefix='.exportar-rpv-', suffix='.tmp', dir=destino.parent)
    os.close(descritor)
    try:
        with ZipFile(temporario, 'w', ZIP_DEFLATED) as pacote:
            pacote.writestr('[Content_Types].xml', CONTENT_TYPES)
            pacote.writestr('_rels/.rels', RAIZ_RELS)
            pacote.writestr('xl/workbook.xml', WORKBOOK.replace('{ultima}', coluna_letra(len(COLUNAS) - 1))
                            .replace('{linhas}', str(len(registros) + 1)))
            pacote.writestr('xl/_rels/workbook.xml.rels', WORKBOOK_RELS)
            pacote.writestr('xl/styles.xml', STYLES)
            pacote.writestr('xl/worksheets/sheet1.xml', planilha(registros))
        os.replace(temporario, destino)
    except BaseException:
        Path(temporario).unlink(missing_ok=True)
        raise
    return destino

