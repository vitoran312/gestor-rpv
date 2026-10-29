"""O app do celular (pasta celular/) abre os mesmos backups que o programa grava e mostra as mesmas contas.

Roda um navegador de verdade (Playwright + Chromium); fica de fora quando não há Node.js com Playwright,
como no Windows do CI. Exemplo: GESTOR_RPV_TESTE_CELULAR=1 python -m unittest test_celular -v
"""
import functools
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from backup import criar_backup
from dados import chave_texto, moeda, situacao
from grafico import resumo_mensal
from apoio_testes import SENHA_TESTE, banco_com_contas, dados_rpv, prorrogacao_antiga

RAIZ = Path(__file__).resolve().parent
NAVEGADOR = os.environ.get('GESTOR_RPV_NAVEGADOR', 'chromium')
# Imagem PNG de 1x1 pixel, para o comprovante de teste.
PNG_1X1 = bytes.fromhex('89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c63f8cf'
                        'c000000301010018dd8db40000000049454e44ae426082')
HOJE = date(2026, 10, 28)
TERMOS = ['', 'ana', 'jose', 'maria jose', 'ria jo', 'lva', 'silva c', 'lva c', 'davila', 'lilian', '10/2026', '---', 'ÁVILA',
          'x y z', '  bruno  ']
VALORES = [0, 5, 99, 100, 123456, 100000000, -800050, 99999999999999]
TEXTOS = ["Ana Júlia D'Ávila", 'Maria-José  Souza', 'João_da Silva', '  ', 'ÇÃO ção', 'O’Neill', 'x1 y2']
TELAS = ['#inicio', '#operacoes', '#contas', '#mais', '#grafico', '#lixeira', '#backup']


def pdf_de_teste(textos, enchimento=0):
    """PDF válido com uma página por texto (fonte Helvetica, não embutida) e um bloco de bytes aleatórios sem uso."""
    objetos = [b'<< /Type /Catalog /Pages 2 0 R >>', None, b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    paginas = []
    for texto in textos:
        conteudo = f'BT /F1 24 Tf 72 720 Td ({texto.encode("latin-1").decode("latin-1")}) Tj ET'.encode('latin-1')
        objetos.append(b'<< /Length %d >>\nstream\n' % len(conteudo) + conteudo + b'\nendstream')
        objetos.append(b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> '
                       b'/Contents %d 0 R >>' % len(objetos))
        paginas.append(len(objetos))
    objetos[1] = b'<< /Type /Pages /Kids [%s] /Count %d >>' % (b' '.join(b'%d 0 R' % n for n in paginas), len(paginas))
    if enchimento:
        objetos.append(b'<< /Length %d >>\nstream\n' % enchimento + os.urandom(enchimento) + b'\nendstream')
    saida, posicoes = bytearray(b'%PDF-1.4\n'), []
    for numero, corpo in enumerate(objetos, 1):
        posicoes.append(len(saida))
        saida += b'%d 0 obj\n' % numero + corpo + b'\nendobj\n'
    inicio = len(saida)
    saida += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objetos) + 1)
    saida += b''.join(b'%010d 00000 n \n' % p for p in posicoes)
    saida += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objetos) + 1, inicio)
    return bytes(saida)


def rodar_node(script, endereco, entrada):
    """Roda um roteiro do navegador; se ele falhar, o erro do Node aparece na falha do teste."""
    resultado = subprocess.run(['node', str(RAIZ / 'celular' / 'testes' / script), endereco, json.dumps(entrada)],
                               capture_output=True, text=True, timeout=300)
    if resultado.returncode:
        raise AssertionError(f'{script} falhou no {NAVEGADOR}:\n{resultado.stderr[-4000:]}')
    return resultado.stdout


class Silencioso(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


@unittest.skipUnless(os.environ.get('GESTOR_RPV_TESTE_CELULAR') == '1', 'Requer Node.js com Playwright e '
                     'GESTOR_RPV_TESTE_CELULAR=1')
class TestAppDoCelular(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.pasta = Path(cls.temp.name)
        cls.site = cls.pasta / 'site'
        shutil.copytree(RAIZ / 'celular', cls.site, ignore=shutil.ignore_patterns('testes'))
        entrada = cls.montar_backups()
        servidor = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Silencioso, directory=str(cls.site)))
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        try:
            saida = rodar_node('navegador.cjs', f'http://127.0.0.1:{servidor.server_address[1]}', entrada)
            # Chave de acesso exige um nome de site (localhost), não um endereço IP.
            faceid = None if NAVEGADOR != 'chromium' else rodar_node(
                'faceid.cjs', f'http://localhost:{servidor.server_address[1]}', cls.entrada_faceid)
        finally:
            servidor.shutdown()
            servidor.server_close()
        cls.resultados = json.loads(saida)
        cls.faceid = json.loads(faceid) if faceid else None

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def montar_backups(cls):
        banco = cls.banco = banco_com_contas(cls.pasta / 'dados' / 'gestor.sqlite3')
        # Um anexo de 2,5 MB faz o backup passar de um bloco da cifra (1 MiB): confere a costura dos blocos.
        anexo = cls.pasta / 'contrato.pdf'
        anexo.write_bytes(pdf_de_teste(['Contrato de cessão', 'Página dois do contrato'], enchimento=2_500_000))
        cls.ana = banco.salvar(dados_rpv(nome='Ana Júlia D\'Ávila', aquisicao='2026-09-10', previsao='2026-10-01'),
                               anexos=[anexo])
        cls.bruno = banco.salvar(dados_rpv(nome='Bruno Lima', conta='Lilian', aquisicao='2026-10-01',
                                           previsao='2026-12-01', comissao=50000))
        cls.maria = banco.salvar(dados_rpv(nome='Maria-José Souza', aquisicao='2026-08-05', previsao='2026-09-01',
                                           custo=700000, previsto=1000000))
        comprovante = cls.pasta / 'comprovante.png'
        comprovante.write_bytes(PNG_1X1)
        banco.registrar_recebimento(cls.maria, '2026-09-15', anexos=[comprovante])
        cls.hashes = {a.name: hashlib.sha256(a.read_bytes()).hexdigest() for a in (anexo, comprovante)}
        cls.carlos = banco.salvar(dados_rpv(nome='Carlos Silva', aquisicao='2026-10-20', previsao='2026-11-10'))
        banco.atualizar_previsao(cls.carlos, '2026-12-20')
        cls.antiga = banco.salvar(dados_rpv(nome='Operação Antiga', aquisicao='2025-11-02', previsao='2026-01-10',
                                            observacoes='Linha 1\nLinha 2 <b>sem HTML</b>'))
        prorrogacao_antiga(banco, cls.antiga, '2026-11-30')
        banco.excluir(banco.salvar(dados_rpv(nome='Na Lixeira')))
        cifrado = criar_backup(banco, cls.site / 'backups')
        banco.remover_configuracao('senha_backup')
        aberto = criar_backup(banco, cls.site / 'backups', prefixo='SemSenha-', exigir_senha=False)
        adulterado = cls.site / 'backups' / 'adulterado.rpvbackup'
        bytes_ = bytearray(cifrado.read_bytes())
        bytes_[len(bytes_) // 2] ^= 1
        adulterado.write_bytes(bytes_)
        cortado = cls.site / 'backups' / 'cortado.rpvbackup'
        cortado.write_bytes(cifrado.read_bytes()[:-(1024 * 1024 + 16)])  # Sem o último bloco inteiro.
        endereco = lambda arquivo: 'backups/' + arquivo.name
        casos = [
            {'nome': 'cifrado', 'arquivo': endereco(cifrado), 'senha': SENHA_TESTE},
            {'nome': 'sem_senha', 'arquivo': endereco(aberto), 'senha': ''},
            {'nome': 'senha_errada', 'arquivo': endereco(cifrado), 'senha': SENHA_TESTE + 'x'},
            {'nome': 'senha_vazia', 'arquivo': endereco(cifrado), 'senha': ''},
            {'nome': 'adulterado', 'arquivo': endereco(adulterado), 'senha': SENHA_TESTE},
            {'nome': 'cortado', 'arquivo': endereco(cortado), 'senha': SENHA_TESTE},
        ]
        regras = {'arquivo': endereco(cifrado), 'senha': SENHA_TESTE, 'hoje': HOJE.isoformat(), 'termos': TERMOS,
                  'valores': VALORES, 'textos': TEXTOS}
        documentos = {d['nome']: d['id'] for r in (cls.ana, cls.maria) for t in ('entrada', 'recebimento')
                      for d in banco.documentos(r, t)}
        cls.endereco_pdf, cls.endereco_png = (f'#documento/{documentos[n]}' for n in ('contrato.pdf', 'comprovante.png'))
        telas = {'arquivo': str(cifrado), 'senha': SENHA_TESTE, 'enderecos': TELAS + [f'#operacao/{cls.antiga}'],
                 'documentos': [cls.endereco_pdf, cls.endereco_png]}
        outro = banco_com_contas(cls.pasta / 'outro' / 'gestor.sqlite3')
        outro.salvar(dados_rpv(nome='Só No Segundo Backup'))
        segundo = criar_backup(outro, cls.pasta / 'segundo')
        cls.entrada_faceid = {'primeiro': str(cifrado), 'segundo': str(segundo), 'senha': SENHA_TESTE}
        return {'casos': casos, 'regras': regras, 'telas': telas}

    # ---- Leitura do backup ------------------------------------------------------------------------------
    def test_backup_com_senha_abre_igual_ao_programa(self):
        resultado = dict(self.resultados['leituras']['cifrado'])
        self.assertTrue(resultado.pop('cifrado'))
        resultado.pop('versao_app')
        self.assertEqual(resultado, {'operacoes': 5, 'lixeira': 1, 'contas': len(self.banco.contas()), 'documentos': 2,
                                     'nomes': [r['nome'] for r in sorted(self.banco.listar(), key=lambda r: r['id'])]})

    def test_backup_antigo_sem_senha_tambem_abre(self):
        resultado = self.resultados['leituras']['sem_senha']
        self.assertFalse(resultado['cifrado'])
        self.assertEqual(resultado['operacoes'], 5)

    def test_senha_errada_ou_ausente_e_recusada(self):
        for caso in ('senha_errada', 'senha_vazia'):
            with self.subTest(caso):
                self.assertEqual(self.resultados['leituras'][caso]['erro'], 'SenhaIncorreta')

    def test_arquivo_alterado_ou_cortado_e_recusado(self):
        for caso in ('adulterado', 'cortado'):
            with self.subTest(caso):
                self.assertEqual(self.resultados['leituras'][caso]['erro'], 'SenhaIncorreta')
                self.assertIn('alterado ou está incompleto', self.resultados['leituras'][caso]['mensagem'])

    # ---- As mesmas contas do programa ---------------------------------------------------------------------
    def test_ordem_previsao_atual_e_situacao(self):
        regras = self.resultados['regras']
        registros = self.banco.listar()
        self.assertEqual(regras['ordem'], [r['id'] for r in registros])
        self.assertEqual(regras['lixeira'], [r['id'] for r in self.banco.listar_lixeira()])
        self.assertEqual(regras['previsao_atual'], {str(r['id']): r['previsao_atual'] for r in registros})
        self.assertEqual(regras['situacoes'], {str(r['id']): situacao(r, HOJE) for r in registros})
        situacoes = [situacao(r, HOJE) for r in registros]
        self.assertEqual(regras['totais'], {'todas': len(registros), **{s: situacoes.count(s) for s in
                                                                         ('pendente', 'atrasada', 'recebida')}})
        self.assertEqual(set(situacoes), {'pendente', 'atrasada', 'recebida'})  # Os dados cobrem os três casos.

    def test_indicadores_iguais_aos_de_minhas_operacoes(self):
        registros = self.banco.listar()
        self.assertEqual(self.resultados['regras']['indicadores'], {
            'registros': len(registros),
            'previsto': sum(r['previsto'] - r['custo'] for r in registros),
            'realizado': sum(r['previsto'] - r['custo'] for r in registros if r['recebimento']),
            'aberto': sum(r['custo'] for r in registros if not r['recebimento']),
        })

    def test_busca_encontra_o_mesmo_que_no_computador(self):
        for termo in TERMOS:
            with self.subTest(termo=termo):
                self.assertEqual(self.resultados['regras']['buscas'][termo], [r['id'] for r in self.banco.listar(termo)])

    def test_grafico_mensal(self):
        esperado = [list(linha) for linha in resumo_mensal(self.banco.listar(), hoje=HOJE)]
        self.assertEqual(self.resultados['regras']['resumo'], esperado)

    def test_valores_e_textos(self):
        self.assertEqual(self.resultados['regras']['moedas'], [moeda(v) for v in VALORES])
        self.assertEqual(self.resultados['regras']['chaves'], [chave_texto(t) for t in TEXTOS])

    def test_historico_prorrogacoes_e_documentos(self):
        regras = self.resultados['regras']
        self.assertEqual(regras['historico'], {str(self.carlos): 1})
        self.assertEqual(regras['prorrogacoes'], {str(self.antiga): 1})
        self.assertEqual(regras['documentos'], {str(self.ana): ['contrato.pdf'], str(self.maria): ['comprovante.png']})

    # ---- Anexos ---------------------------------------------------------------------------------------------
    def test_anexos_saem_do_backup_identicos_aos_originais(self):
        self.assertEqual(self.resultados['regras']['anexos'], self.hashes)

    def test_caminho_que_nao_e_anexo_do_backup_e_recusado(self):
        self.assertEqual(self.resultados['regras']['recusas'], ['ErroBackup'] * 3)

    def test_pdf_e_imagem_abrem_na_tela(self):
        documentos = self.resultados['documentos']
        pdf = documentos[self.endereco_pdf]
        self.assertEqual(pdf['titulo'], 'contrato.pdf')
        self.assertEqual(pdf['paginas'], 2)
        self.assertGreater(pdf['pixels_desenhados'], 0)   # A primeira página foi desenhada.
        self.assertTrue(pdf['texto_desenhado'])             # E não em branco: o texto (fonte padrão) aparece.
        self.assertAlmostEqual(pdf['largura'], pdf['largura_tela'], delta=2)  # Começa na largura da tela.
        self.assertAlmostEqual(pdf['largura_com_zoom'], pdf['largura_tela'] * 1.5, delta=3)
        self.assertEqual(pdf['rotulo_zoom'], '150%')
        self.assertEqual(documentos[self.endereco_png]['tag'], 'img')
        self.assertTrue(documentos[self.endereco_png]['blob'])
        self.assertTrue(documentos[self.endereco_png]['carregada'])
        self.assertTrue(self.resultados['blob_liberado'])

    # ---- Telas ----------------------------------------------------------------------------------------------
    def test_todas_as_telas_abrem_sem_erro(self):
        self.assertEqual(self.resultados['erros'], [])
        telas = self.resultados['telas']
        self.assertIn('Lucro previsto', telas['#inicio'])
        self.assertIn('Bruno Lima', telas['#operacoes'])
        self.assertIn('Na Lixeira', telas['#lixeira'])
        self.assertNotIn('Na Lixeira', telas['#operacoes'])
        self.assertIn('Gráfico mensal', telas['#mais'])
        self.assertIn('Protegido por senha', telas['#backup'])

    def test_detalhe_mostra_texto_do_backup_como_texto(self):
        detalhe = self.resultados['telas'][f'#operacao/{self.antiga}']
        self.assertIn('Linha 2 <b>sem HTML</b>', detalhe)  # Nada do backup vira HTML na página.
        self.assertIn('30/11/2026', detalhe)              # Prorrogação antiga define a previsão atual.
        # Dados bancários recolhidos: só o titular aparece até a pessoa tocar.
        self.assertIn('Toque para ver os dados', detalhe)
        self.assertNotIn('Chave Pix', detalhe)
        self.assertNotIn('Chave Pix', self.resultados['telas']['#contas'])

    def test_service_worker_guarda_o_app_para_abrir_sem_internet(self):
        self.assertTrue(self.resultados['service_worker'])
        self.assertTrue(self.resultados['sem_internet'])

    # ---- Backup guardado e Face ID (autenticador virtual com PRF) --------------------------------------------
    def setUp(self):
        if self._testMethodName.startswith('test_face_id') or 'pelo_face_id' in self._testMethodName \
                or self._testMethodName == 'test_senha_errada_e_apagar_o_backup_guardado':
            if self.faceid is None:
                self.skipTest('O autenticador virtual (Face ID simulado) só existe no Chromium.')

    def test_face_id_abre_sem_senha_e_sem_escolher_arquivo(self):
        f = self.faceid
        self.assertEqual(f['erros'], [])
        self.assertEqual(f['inicial'], {'app': False, 'faceid_visivel': False, 'fonte': '', 'erro': ''})
        self.assertTrue(f['ativado'])
        self.assertEqual(f['trancado'], {'app': False, 'faceid_visivel': True, 'fonte': 'Backup guardado neste aparelho',
                                         'erro': ''})
        self.assertTrue(f['faceid_abriu'])
        # Ao abrir o app de novo, o Face ID é pedido sozinho e os dados aparecem, sem escolher arquivo.
        self.assertTrue(f['reabriu_sozinho']['app'])
        self.assertIn('Tempo para abrir\n0 s', f['tempo_com_faceid'])  # Com a chave guardada, sem o scrypt.

    def test_backup_novo_aberto_pelo_face_id_passa_a_ser_o_guardado(self):
        self.assertIn('Só No Segundo Backup', self.faceid['segundo_nomes'])
        self.assertIn('Só No Segundo Backup', self.faceid['segundo_guardado'])

    def test_senha_errada_e_apagar_o_backup_guardado(self):
        self.assertFalse(self.faceid['senha_errada']['app'])
        self.assertIn('Senha incorreta', self.faceid['senha_errada']['erro'])
        self.assertEqual(self.faceid['apagado'], {'app': False, 'faceid_visivel': False, 'fonte': '', 'erro': ''})

    def test_fechar_dados_limpa_a_tela(self):
        self.assertEqual(self.resultados['fechado'], {'abertura': True, 'tela_vazia': True, 'senha_vazia': True})


class TestArquivosDoApp(unittest.TestCase):
    """Conferências que não precisam de navegador: rodam também no CI."""

    def test_service_worker_lista_arquivos_que_existem(self):
        import re
        texto = (RAIZ / 'celular' / 'sw.js').read_text(encoding='utf-8')
        lista = re.search(r'const ARQUIVOS = \[(.*?)\];', texto, re.S).group(1)
        arquivos = re.findall(r"'([^']+)'", lista)
        for arquivo in arquivos:
            with self.subTest(arquivo):
                self.assertTrue(arquivo == './' or (RAIZ / 'celular' / arquivo).is_file())
        # Todo arquivo do app (fora os testes) precisa estar na lista, senão não abre sem internet.
        publicados = {str(c.relative_to(RAIZ / 'celular')).replace(os.sep, '/') for c in (RAIZ / 'celular').rglob('*')
                      if c.is_file() and 'testes' not in c.parts and c.name != 'sw.js' and not c.name.startswith('LICEN')}
        self.assertEqual(publicados - set(arquivos), set())

    def test_versao_mostrada_no_app_e_a_do_programa(self):
        import re
        from versao import VERSAO
        texto = (RAIZ / 'celular' / 'app.js').read_text(encoding='utf-8')
        self.assertEqual(re.search(r"const VERSAO_APP = '([^']+)'", texto).group(1), VERSAO)

    def test_manifesto_e_icones(self):
        import struct
        manifesto = json.loads((RAIZ / 'celular' / 'manifest.webmanifest').read_text(encoding='utf-8'))
        self.assertEqual(manifesto['display'], 'standalone')
        for icone in manifesto['icons'] + [{'src': 'icones/apple-touch-icon.png', 'sizes': '180x180'}]:
            with self.subTest(icone['src']):
                # Cabeçalho do PNG: assinatura, bloco IHDR com largura, altura, bits e tipo de cor.
                cabecalho = (RAIZ / 'celular' / icone['src']).read_bytes()[:26]
                self.assertEqual(cabecalho[:8], b'\x89PNG\r\n\x1a\n')
                largura, altura = struct.unpack('>II', cabecalho[16:24])
                self.assertEqual(f'{largura}x{altura}', icone['sizes'])
                self.assertEqual(cabecalho[25], 2)  # RGB, sem transparência: o iPhone pintaria o fundo de preto.


if __name__ == '__main__':
    unittest.main()
