"""O app do celular (pasta celular/) abre os mesmos backups que o programa grava e mostra as mesmas contas.

Roda um navegador de verdade (Playwright + Chromium); fica de fora quando não há Node.js com Playwright,
como no Windows do CI. Exemplo: GESTOR_RPV_TESTE_CELULAR=1 python -m unittest test_celular -v
"""
import base64
import calendar
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
from dados import Banco, chave_texto, moeda, situacao
from grafico import resumo_mensal
from apoio_testes import SENHA_TESTE, banco_com_contas, dados_rpv, prorrogacao_antiga

RAIZ = Path(__file__).resolve().parent
NAVEGADOR = os.environ.get('GESTOR_RPV_NAVEGADOR', 'chromium')
# Imagem PNG de 1x1 pixel, para o comprovante de teste.
PNG_1X1 = bytes.fromhex('89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c6338'
                        '2167040002ca0119bfd3bf060000000049454e44ae426082')
HOJE = date(2026, 10, 28)
TERMOS = ['', 'ana', 'jose', 'maria jose', 'ria jo', 'lva', 'silva c', 'lva c', 'davila', 'lilian', '10/2026', '---', 'ÁVILA',
          'x y z', '  bruno  ']
VALORES = [0, 5, 99, 100, 123456, 100000000, -800050, 99999999999999]
TEXTOS = ["Ana Júlia D'Ávila", 'Maria-José  Souza', 'João_da Silva', '  ', 'ÇÃO ção', 'O’Neill', 'x1 y2']
CPFS = ['529.982.247-25', '52998224725', '529.982.247-24', '111.111.111-11', '', '  ', '529.982.247-2a',
        '1234567890']
CONTA_VALIDA = {'identificacao': 'Conta Nova', 'nome': 'Fulana De Tal', 'cpf': '529.982.247-25', 'endereco': 'Rua A',
                'numero_endereco': '10', 'cidade': 'Campinas', 'estado': 'SP', 'banco': 'Banco Novo', 'agencia': '',
                'numero': '777-1', 'pix': 'fulana@example.com'}
CASOS_CONTA = [CONTA_VALIDA, dict(CONTA_VALIDA, nome='', banco=''), dict(CONTA_VALIDA, estado='XX'),
               dict(CONTA_VALIDA, cpf='111.111.111-11'), dict(CONTA_VALIDA, identificacao='vitor')]
MENSAGENS = [
    'Nome: MARIA DA SILVA SOUZA\nCPF: 529.982.247-25\nProcesso nº 0001234-56.2024.4.03.6301\nValor da RPV: R$ 15.432,10\n'
    'Previsão de pagamento: 15/12/2026',
    'Bom dia! Segue cliente José Carlos de Almeida, cpf 52998224725, valor 8.500,00. Vou pagar 5.000,00 pela cessão. '
    'Processo 50012345620234047000',
    'oi tudo bem?',
    'Titular: Ana Paula Ribeiro CPF 111.111.111-11\nComissão: R$ 300,00\nData da compra: 20/10/2026\nTotal R$ 12000',
    "JOAO PEDRO D'AVILA\nRPV 20.000,00 aquisição 14.000,00",
]
TELAS = ['#inicio', '#operacoes', '#contas', '#mais', '#grafico', '#lixeira', '#backup', '#novidades', '#agenda']


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
                               capture_output=True, text=True, encoding='utf-8', timeout=300)
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
                  'mensagens': MENSAGENS,
                  'valores': VALORES, 'textos': TEXTOS, 'textos_cpf': CPFS, 'casos_conta': CASOS_CONTA}
        documentos = {d['nome']: d['id'] for r in (cls.ana, cls.maria) for t in ('entrada', 'recebimento')
                      for d in banco.documentos(r, t)}
        cls.endereco_pdf, cls.endereco_png = (f'#documento/{documentos[n]}' for n in ('contrato.pdf', 'comprovante.png'))
        telas = {'arquivo': endereco(cifrado), 'senha': SENHA_TESTE, 'enderecos': TELAS + [f'#operacao/{cls.antiga}'],
                 'documentos': [cls.endereco_pdf, cls.endereco_png]}
        # Entrada feita no celular: os dados do formulário.
        banco.salvar_configuracao('senha_backup', SENHA_TESTE)  # Tirada acima para o backup antigo, sem senha.
        cls.conta_vitor = next(c['id'] for c in banco.contas() if c['identificacao'] == 'Vitor')
        # Valores digitados como no celular: só números, que entram pelos centavos (800000 = R$ 8.000,00).
        telas['nova'] = {'nome': '  entrada   do celular ', 'aquisicao': '2026-10-20', 'custo': '500000',
                         'previsto': '800000', 'conta_id': cls.conta_vitor, 'previsao': '2026-12-15', 'comissao': '10000',
                         'observacoes': 'veio do celular'}
        telas['conta'] = dict(CONTA_VALIDA, identificacao='Conta Do Celular', cpf='52998224725', pix='celular@example.com')
        telas['extras'] = {'operacao': cls.bruno, 'mensagem': MENSAGENS[1]}
        telas['mudancas'] = {'editar': cls.bruno, 'previsao': cls.carlos, 'nova_previsao': '2027-01-30',
                             'excluir': cls.antiga, 'anexar': cls.ana, 'png': base64.b64encode(PNG_1X1).decode()}
        outro = banco_com_contas(cls.pasta / 'outro' / 'gestor.sqlite3')
        outro.salvar(dados_rpv(nome='Só No Segundo Backup'))
        segundo = criar_backup(outro, cls.pasta / 'segundo')
        segundo = shutil.copy(segundo, cls.site / 'backups' / 'segundo.rpvbackup')
        cls.entrada_faceid = {'primeiro': endereco(cifrado), 'segundo': 'backups/segundo.rpvbackup', 'senha': SENHA_TESTE}
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
        self.assertIn('trancados com a senha', telas['#backup'])
        import novidades
        versao, itens = novidades.NOVIDADES[0]
        self.assertIn(f'Versão {versao}', telas['#novidades'])
        self.assertIn(itens[0][1], telas['#novidades'])

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
        if NAVEGADOR == 'chromium':
            self.assertTrue(self.resultados['sem_internet'])

    # ---- Entrada feita no celular ----------------------------------------------------------------------------
    def test_valor_ganha_pontuacao_enquanto_e_digitado(self):
        self.assertEqual(self.resultados['mascara'], ['0,01', '0,12', '1,23', '12,34', '123,45', '1.234,56', '12.345,67',
                                                      '1.234,56'])

    def test_nova_entrada_confere_as_regras_e_mostra_o_lucro(self):
        self.assertIn('O valor de aquisição não pode superar o Valor Total RPV.', self.resultados['nova_erro'])
        self.assertEqual(self.resultados['nova_lucro'], 'Lucro previsto: R$ 3.000,00')
        self.assertIn('Entrada Do Celular'.lower(), self.resultados['nova_tela'].lower())
        self.assertIn('Registrar recebimento', self.resultados['nova_tela'])  # Já é dos dados do celular.

    def test_primeira_vez_pede_nome_e_senha(self):
        abertura = self.resultados['abertura_nova']
        self.assertTrue(abertura['nome'])
        for texto in ('Nome', 'Repita a senha', 'Recebi um código de convite', 'Já tenho dados: recuperar da nuvem'):
            self.assertIn(texto, abertura['texto'])
        self.assertNotIn('computador', abertura['texto'])

    def test_tudo_que_o_celular_grava_abre_no_programa(self):
        # O arquivo guardado no celular depois de entrada, conta, edição, previsão, exclusão e anexo: o programa abre.
        from backup import BackupPreparado
        arquivo = self.pasta / 'guardado-no-celular.rpvbackup'
        arquivo.write_bytes(base64.b64decode(self.resultados['guardado_final']))
        destino = banco_com_contas(self.pasta / 'outro-pc' / 'gestor.sqlite3')
        with BackupPreparado(arquivo, SENHA_TESTE, pasta_trabalho=self.pasta / 'trabalho-final') as pacote:
            pacote.restaurar(destino, copia_de_seguranca=False)
        nova = next(r for r in destino.listar() if r['nome'] == 'Entrada Do Celular')
        self.assertEqual((nova['aquisicao'], nova['custo'], nova['previsto'], nova['comissao'], nova['previsao'],
                          nova['observacoes']), ('2026-10-20', 500000, 800000, 10000, '2026-12-15', 'Veio do celular'))
        conta = next(c for c in destino.contas() if c['identificacao'] == 'Conta Do Celular')
        self.assertEqual((conta['cpf'], conta['pix'], conta['estado']), ('52998224725', 'celular@example.com', 'SP'))
        bruno = destino.obter(self.bruno)
        self.assertEqual((bruno['previsto'], bruno['custo'], bruno['observacoes']), (3000000, 1200000, 'Editada no celular'))
        self.assertEqual(destino.obter(self.carlos)['previsao_atual'], '2027-01-30')
        self.assertTrue(destino.obter(self.antiga)['lixeira_em'])
        (foto,) = [d for d in destino.documentos(self.ana) if d['nome'].endswith('.jpg')]
        self.assertTrue(foto['nome'].startswith('Foto '))
        self.assertEqual(destino.caminho_documento(foto['id']).read_bytes()[:2], b'\xff\xd8')  # Virou JPEG.

    # ---- Mudanças nas operações ---------------------------------------------------------------------------
    def test_editar_e_alterar_previsao_conferem_as_regras(self):
        r = self.resultados
        lilian = next(c['id'] for c in self.banco.contas() if c['identificacao'] == 'Lilian')
        self.assertEqual(r['editar_valores'], {'nome': 'Bruno Lima', 'custo': moeda(1200000), 'previsto': moeda(2000000),
                                               'previsao': '2026-12-01', 'conta': str(lilian)})
        self.assertIn('não pode ser anterior à aquisição', r['previsao_erro'])
        self.assertIn('Editada no celular', r['editar_tela'])
        self.assertIn('R$ 30.000,00', r['editar_tela'])
        self.assertIn('Foto ', r['anexo_tela'])

    # ---- Agenda -------------------------------------------------------------------------------------------
    def test_agenda_igual_ao_que_o_programa_calcula(self):
        abertas = sorted((r for r in self.banco.listar() if not r['recebimento']),
                         key=lambda r: (r['previsao_atual'], r['nome']))
        hoje, amanha = HOJE.isoformat(), date.fromordinal(HOJE.toordinal() + 1).isoformat()
        semana = date.fromordinal(HOJE.toordinal() + 7).isoformat()
        dias = {}
        for r in abertas:
            dias.setdefault(r['previsao_atual'], []).append(r['id'])
        self.assertEqual(self.resultados['regras']['agenda'], {
            'atrasadas': [r['id'] for r in abertas if r['previsao_atual'] < hoje],
            'hoje': dias.get(hoje, []), 'amanha': dias.get(amanha, []),
            'semana': [r['id'] for r in abertas if amanha < r['previsao_atual'] <= semana], 'dias': dias})
        self.assertIn(self.ana, self.resultados['regras']['agenda']['atrasadas'])

    def test_calendario_de_domingo_a_sabado(self):
        for mes, semanas in self.resultados['regras']['semanas'].items():
            ano, numero = map(int, mes.split('-'))
            esperado = [[d.isoformat() if d.month == numero else None for d in semana]
                        for semana in calendar.Calendar(firstweekday=6).monthdatescalendar(ano, numero)]
            self.assertEqual(semanas, esperado, mes)

    def test_regras_da_nova_previsao(self):
        esperado = [(['A previsão atual não pode ser anterior à aquisição.'] if '2026-01-01' < r['aquisicao'] else [])
                    + ['A nova previsão é igual à atual.'] for r in self.banco.listar()]
        self.assertEqual(self.resultados['regras']['previsoes'], esperado)

    def test_agenda_no_inicio_e_no_calendario(self):
        agenda = self.resultados['agenda']
        self.assertIn('Agenda das previsões', self.resultados['inicio_agenda'])
        self.assertIn('Próx. 7 dias', self.resultados['inicio_agenda'])
        self.assertEqual(agenda['titulo'], 'Agenda')
        self.assertTrue(agenda['hoje'])
        hoje = date.today()
        self.assertEqual(agenda['dias'], calendar.monthrange(hoje.year, hoje.month)[1])
        if hoje.isoformat() > '2026-10-01':
            self.assertIn("Ana Júlia D'Ávila", agenda['texto'])  # Atrasada desde 01/10/2026.
        meses = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro',
                 'novembro', 'dezembro']
        proximo = date(hoje.year + hoje.month // 12, hoje.month % 12 + 1, 1)
        self.assertEqual(self.resultados['agenda_proximo_mes'], f'{meses[proximo.month - 1]} de {proximo.year}')

    # ---- Modo discreto, colar e preencher e resumo em imagem ----------------------------------------------
    def test_modo_discreto_esconde_os_valores(self):
        r = self.resultados
        self.assertRegex(r['discreto_antes'], r'R\$ \d')
        for texto in (r['discreto_inicio'], r['discreto_operacao']):
            self.assertIn('R$ •••••', texto)
            self.assertNotRegex(texto, r'R\$ \d')
        self.assertIn('Bruno Lima', r['discreto_operacao'])  # Só os valores somem.
        self.assertEqual(r['discreto_guardado'], ['1', 'true'])
        self.assertRegex(r['discreto_depois'], r'R\$ \d')

    def test_ultimo_botao_da_operacao_fica_acima_das_abas(self):
        fim = self.resultados['fim_da_operacao']
        self.assertLessEqual(fim['botao'], fim['abas'] - 16)

    def test_ler_mensagens_coladas(self):
        self.assertEqual(self.resultados['regras']['mensagens'], [
            {'nome': 'MARIA DA SILVA SOUZA', 'processo': '0001234-56.2024.4.03.6301', 'cpf': '529.982.247-25',
             'previsto': 1543210, 'previsao': '2026-12-15'},
            {'nome': 'José Carlos de Almeida', 'processo': '5001234-56.2023.4.04.7000', 'cpf': '529.982.247-25',
             'previsto': 850000, 'custo': 500000},
            {},
            {'nome': 'Ana Paula Ribeiro', 'comissao': 30000, 'aquisicao': '2026-10-20', 'previsto': 1200000},
            {'nome': "JOAO PEDRO D'AVILA", 'previsto': 2000000, 'custo': 1400000},
        ])

    def test_colar_e_preencher_o_formulario(self):
        colar = self.resultados['colar']
        self.assertEqual({k: colar[k] for k in ('nome', 'custo', 'previsto', 'comissao')},
                         {'nome': 'José Carlos De Almeida', 'custo': '5.000,00', 'previsto': '8.500,00', 'comissao': ''})
        self.assertEqual(colar['observacoes'], 'Processo nº 5001234-56.2023.4.04.7000\nCPF do titular: 529.982.247-25')
        self.assertEqual(colar['lucro'], 'Lucro previsto: R$ 3.500,00')
        self.assertIn('Preenchido: titular, valor de aquisição, Valor Total RPV, processo e CPF', colar['aviso'])
        self.assertIn('Nada reconhecido', self.resultados['colar_nada'])

    def test_resumo_em_imagem_sem_dados_sensiveis(self):
        resumo = self.resultados['resumo']
        # Uma linha de nome, previsão e aquisição: a altura acompanha o conteúdo.
        self.assertEqual((resumo['largura'], resumo['altura']), (1080, 1210))
        self.assertEqual(resumo['titulo'], 'Resumo em imagem')
        self.assertIn('Não leva CPF', resumo['texto'])
        self.assertIn('Mostrar o Valor Total RPV', resumo['texto'])
        self.assertTrue(self.resultados['resumo_trocou'])

    # ---- Conta feita no celular -------------------------------------------------------------------------------
    def test_regras_de_cpf_e_de_conta_iguais_as_do_programa(self):
        from dados import validar_cpf
        esperado = []
        for texto in CPFS:
            try:
                esperado.append(validar_cpf(texto))
            except ValueError as erro:
                esperado.append(f'ERRO: {erro}')
        self.assertEqual(self.resultados['regras']['cpfs'], esperado)
        for caso, problemas in zip(CASOS_CONTA, self.resultados['regras']['contas_regras']):
            with self.subTest(caso=caso):
                copia = self.pasta / f'conta-{len(problemas)}-{caso["identificacao"]}.sqlite3'
                shutil.copy(self.banco.caminho, copia)
                try:
                    Banco(copia).salvar_conta(caso)
                    self.assertEqual(problemas, [])
                except ValueError as erro:
                    self.assertEqual('\n'.join(problemas), str(erro))

    def test_conta_feita_no_celular(self):
        # Como no computador: primeiro os campos mal preenchidos; a duplicidade é conferida depois deles.
        self.assertEqual(self.resultados['conta_erro'], 'CPF inválido.')
        self.assertEqual(self.resultados['cpf_mascara'], '529.982.247-25')
        self.assertIn('Conta Do Celular', self.resultados['opcoes_conta'])

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
        self.assertEqual(f['trancado'], {'app': False, 'faceid_visivel': True, 'fonte': 'Seus dados, guardados neste celular',
                                         'erro': ''})
        self.assertTrue(f['faceid_abriu'])
        # Ao abrir o app de novo, o Face ID é pedido sozinho e os dados aparecem, sem escolher arquivo.
        self.assertTrue(f['reabriu_sozinho']['app'])
        self.assertIn('Tempo para abrir\n0 s', f['tempo_com_faceid'])  # Com a chave guardada, sem o scrypt.
        # O logo aparece sozinho primeiro: o Face ID (janela do iPhone) só é pedido depois da animação.
        self.assertGreaterEqual(f['splash']['pedido_em'], 2650)  # O logo fica um instante a mais (2,7 s).
        self.assertTrue(f['splash']['logo_ao_abrir'])

    def test_outros_dados_pelo_face_id_pedem_a_senha_uma_vez(self):
        self.assertIn('Só No Segundo Backup', self.faceid['segundo_nomes'])
        self.assertIn('chave antiga', self.faceid['faceid_chave_antiga']['erro'])
        self.assertIn('Só No Segundo Backup', self.faceid['segundo_guardado'])

    def test_senha_errada_e_apagar_o_backup_guardado(self):
        self.assertFalse(self.faceid['senha_errada']['app'])
        self.assertIn('Senha incorreta', self.faceid['senha_errada']['erro'])
        self.assertEqual(self.faceid['apagado'], {'app': False, 'faceid_visivel': False, 'fonte': '', 'erro': ''})

    def test_fechar_dados_limpa_a_tela(self):
        self.assertEqual(self.resultados['fechado'], {'abertura': True, 'tela_vazia': True, 'senha_vazia': True})


@unittest.skipUnless(os.environ.get('GESTOR_RPV_TESTE_CELULAR') == '1', 'Requer Node.js com Playwright e '
                     'GESTOR_RPV_TESTE_CELULAR=1')
class TestQuemUsaSoOCelular(unittest.TestCase):
    """Começa sem computador: os dados nascem no celular, no mesmo formato de backup do programa."""
    SENHA = 'cavalo azul bebe cafe'
    CONTA = {'identificacao': 'nubank pessoal', 'nome': 'maria  de souza', 'cpf': '529.982.247-25',
             'endereco': 'rua das flores', 'numero_endereco': '12', 'cidade': 'são paulo', 'estado': 'SP',
             'banco': 'nubank', 'agencia': '0001', 'numero': '12345-6', 'pix': 'maria@example.com'}
    ENTRADA = {'nome': "joão d'ávila   santos", 'aquisicao': '2026-10-01', 'custo': '500000', 'previsto': '800000',
               'previsao': '2026-12-01', 'observacoes': 'primeira entrada'}
    SEGUNDA = {'nome': 'segunda entrada', 'custo': '100000', 'previsto': '200000', 'previsao': '2026-12-10',
               'novo_previsto': '300000', 'nova_previsao': '2027-03-01', 'mes_previsao': 'março de 2027'}
    PDF = pdf_de_teste(['Oficio do tribunal'])
    NOMES = ["joão d'ávila", 'MARIA-JOSÉ', '3rd ávila', 'ana  beatriz', "o'neill mcdonald"]
    SENHAS = ['123456789', 'abcdefghij', ' com espaço ', 'senha@12345', 'cavalo azul bebe cafe', 'Mar1aJ0se!x', 'k7#pQ2', '123456', 'aaaaab']

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.pasta = Path(cls.temp.name)
        site = cls.pasta / 'site'
        shutil.copytree(RAIZ / 'celular', site, ignore=shutil.ignore_patterns('testes'))
        cls.hoje = date.today().isoformat()
        servidor = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Silencioso, directory=str(site)))
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        try:
            cls.r = json.loads(rodar_node('independente.cjs', f'http://127.0.0.1:{servidor.server_address[1]}', {
                'senha': cls.SENHA, 'conta': cls.CONTA, 'entrada': cls.ENTRADA, 'hoje': cls.hoje,
                'segunda': dict(cls.SEGUNDA, pdf=base64.b64encode(cls.PDF).decode(), png=base64.b64encode(PNG_1X1).decode()),
                'senhas_ruins': [['123', '123'], ['abcdefghij', 'abcdefghij'], [cls.SENHA, cls.SENHA + 'x']],
                'nomes': cls.NOMES, 'senhas_regra': cls.SENHAS}))
        finally:
            servidor.shutdown()
            servidor.server_close()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_primeira_abertura_mostra_a_demonstracao(self):
        d = self.r['demonstracao']
        for hash, texto in d.items():
            self.assertIn('meramente sugestivos', texto, hash)
            self.assertIn('Começar a usar com meus dados', texto, hash)
        import demonstracao
        self.assertIn(f'Registros\n{len(demonstracao.OPERACOES)}', d['#inicio'])
        self.assertIn('Estes dados são de exemplo', d['#inicio'])  # O convite para começar, em destaque.
        self.assertIn('Helena Batista Correia', d['#operacoes'])
        self.assertIn('Conta principal', d['#contas'])
        self.assertNotIn('Abrir meu backup', d['#mais'])
        self.assertNotIn('computador', d['#mais'])
        self.assertNotIn('Apagar os dados deste celular', d['#mais'])
        self.assertIn('Na demonstração não dá para cadastrar', d['#nova'])
        self.assertIn('Atrasadas', d['#agenda'])
        self.assertNotIn('Mudar esta operação', d['operacao'])  # Só consulta.
        self.assertEqual(self.r['depois_da_demonstracao'], {'app': False, 'novo': True, 'demonstracao': True})

    def test_senha_nova_com_as_regras_do_programa(self):
        erros = self.r['erros_senha']
        self.assertEqual(self.r['erro_sem_nome'], 'Digite o seu nome.')
        self.assertIn('de 6 a 256 caracteres', erros[0])
        self.assertIn('fácil demais', erros[1])
        self.assertIn('não são iguais', erros[2])
        import cifra
        esperado = []
        for senha in self.SENHAS:
            try:
                cifra.validar_senha(senha)
                esperado.append('ok')
            except ValueError as erro:
                esperado.append(str(erro))
        self.assertEqual(self.r['regras']['senhas'], esperado)

    def test_nomes_como_o_programa_grava(self):
        from dados import nome_formatado
        self.assertEqual(self.r['regras']['titulos'], [nome_formatado(n) for n in self.NOMES])

    def test_app_abre_vazio_e_grava_no_celular(self):
        self.assertEqual(self.r['erros'], [])
        self.assertIn('Registros\n0', self.r['inicio_vazio'])
        self.assertIn('Olá, Maria!', self.r['inicio_vazio'])
        self.assertEqual(self.r['nome_guardado'], 'Maria')
        self.assertIn('Nubank pessoal', self.r['contas'])
        self.assertIn("João D'Ávila Santos", self.r['detalhe'])
        self.assertIn('futuro', self.r['erro_recebimento'])
        self.assertIn('Recebida', self.r['detalhe_recebido'])
        # Sem internet (a nuvem é bloqueada neste teste): nenhum aviso chamativo, só o texto pequeno.
        self.assertNotIn('Ligue o backup', self.r['inicio_com_dados'])
        self.assertIn('sincroniza ao voltar a internet', self.r['inicio_com_dados'])
        self.assertNotIn('Fazer cópia de segurança', self.r['mais'])  # A cópia é a da nuvem.
        self.assertIn('Backup na nuvem', self.r['mais'])
        self.assertNotIn('computador', self.r['mais'])
        self.assertEqual(self.r['abertura'], {'fonte': 'Seus dados, guardados neste celular', 'novo': False, 'outras': False})
        self.assertIn("João D'Ávila Santos", self.r['operacoes_depois'])  # Continua depois de trancar e abrir.
        self.assertIn('Começar a usar com meus dados', self.r['convite'])
        self.assertTrue(self.r['guardado']['independente'])

    def test_editar_previsao_documentos_e_lixeira_no_celular(self):
        r = self.r
        self.assertIn('Ofício.pdf', r['segunda_criada'])
        self.assertIn('image.jpg', r['segunda_criada'].replace('Foto ', 'image.jpg #'))  # Foto da câmera ganha nome.
        self.assertIn('R$ 3.000,00', r['segunda_editada'])
        self.assertIn('Editada no celular', r['segunda_editada'])
        self.assertIn('10/12/2026 → 01/03/2027', r['segunda_editada'])
        self.assertIn('Recibo.jpg', r['segunda_editada'])
        self.assertTrue(r['foto_aberta'])
        self.assertNotIn('Segunda Entrada', r['operacoes_sem_segunda'])
        self.assertIn('Segunda Entrada', r['lixeira'])
        self.assertIn('restaurar', r['lixeira'])
        self.assertNotIn('Na lixeira desde', r['restaurada'])
        self.assertEqual((r['documentos_restaurada'], r['documentos_depois']), (3, 3))
        # Excluir permanentemente (depois de guardar o pacote que o programa confere abaixo).
        self.assertIn('não podem ser restaurados', r['aviso_de_vez'])
        self.assertIn('A lixeira está vazia.', r['lixeira_de_vez'])
        self.assertNotIn('Segunda Entrada', r['operacoes_de_vez'])
        self.assertGreater(r['encolheu_de_vez'], len(self.PDF))  # Os anexos saíram do pacote.

    def test_editar_desativar_e_remover_conta_no_celular(self):
        r = self.r
        self.assertEqual(r['conta_preenchida'], 'Nubank pessoal')
        self.assertIn('Conta Renomeada', r['contas_desativada'])
        self.assertIn('DESATIVADA', r['contas_desativada'].upper())
        self.assertIn('1 operação usa esta conta', r['aviso_remover_conta'])
        # A operação perde o vínculo, mas guarda os dados bancários que copiou.
        self.assertIn('Maria De Souza', r['operacao_sem_conta'])
        self.assertIn('Segunda Entrada', r['agenda'])  # Previsão em 01/03/2027, ainda não recebida.
        self.assertIn('segunda 01/03', r['agenda'])
        self.assertIn('Agenda das previsões', r['inicio_com_dados'])
        self.assertIn('Nenhuma previsão para os próximos 7 dias.', r['inicio_com_dados'])

    def test_dados_do_celular_abrem_no_programa_como_o_programa_gravaria(self):
        from backup import BackupPreparado
        import cifra
        arquivo = self.pasta / 'GestorRPV-celular.rpvbackup'
        arquivo.write_bytes(base64.b64decode(self.r['guardado']['bytes']))
        # Dados criados no celular: trancados pela chave sorteada (a senha abre o envelope dela, no app).
        pacote = self.pasta / 'GestorRPV-celular.zip'
        cifra.decifrar_arquivo(arquivo, pacote, None, chave=base64.b64decode(self.r['guardado']['chave']))
        do_celular = Banco(self.pasta / 'restaurado' / 'gestor.sqlite3')
        with BackupPreparado(pacote, None) as preparado:
            self.assertEqual((preparado.resumo['registros'], preparado.resumo['documentos']), (2, 3))
            preparado.restaurar(do_celular, copia_de_seguranca=False)
        referencia = Banco(self.pasta / 'referencia' / 'gestor.sqlite3')
        conta_id = referencia.salvar_conta(self.CONTA)
        rpv = referencia.salvar(dict(self.ENTRADA, custo=500000, previsto=800000, comissao=None, conta_id=conta_id,
                                     conta=''))
        referencia.registrar_recebimento(rpv, self.hoje)
        def linha(banco, tabela):
            with banco.conectar() as con:
                return {k: v for k, v in dict(con.execute(f'SELECT * FROM {tabela}').fetchone()).items() if k != 'id'}

        self.assertEqual(linha(do_celular, 'contas'), linha(referencia, 'contas'))
        self.assertEqual(linha(do_celular, 'rpvs'), linha(referencia, 'rpvs'))
        # A segunda entrada: editada, com nova previsão no histórico e os três documentos legíveis no programa.
        (segunda,) = [x for x in do_celular.listar() if x['nome'] == 'Segunda Entrada']
        self.assertEqual((segunda['custo'], segunda['previsto'], segunda['previsao'], segunda['previsao_atual'],
                          segunda['observacoes'], segunda['lixeira_em']),
                         (100000, 300000, '2026-12-10', '2027-03-01', 'Editada no celular', None))
        self.assertEqual([(h['anterior'], h['nova']) for h in do_celular.historico_previsoes(segunda['id'])],
                         [('2026-12-10', '2027-03-01')])
        documentos = {d['nome']: do_celular.caminho_documento(d['id']).read_bytes() for d in do_celular.documentos(segunda['id'])}
        self.assertEqual(documentos.pop('Ofício.pdf'), self.PDF)
        self.assertEqual(len(documentos), 2)
        self.assertIn('Recibo.jpg', documentos)
        self.assertTrue(all(b[:2] == b'\xff\xd8' for b in documentos.values()))


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

    @unittest.skipUnless(shutil.which('node'), 'Requer Node.js')
    def test_codigo_do_app_sem_erro_de_sintaxe(self):
        # Um parêntese a mais derruba o app inteiro no celular: confere cada arquivo antes de publicar.
        for arquivo in sorted((RAIZ / 'celular').glob('*.js')):
            with self.subTest(arquivo.name):
                resultado = subprocess.run(['node', '--check', str(arquivo)], capture_output=True, text=True)
                self.assertEqual(resultado.returncode, 0, resultado.stderr)

    def test_modelo_do_celular_tem_o_esquema_atual_do_banco(self):
        # Mudou o esquema em dados.py? Rode "python gerar_modelo_celular.py" para o app criar dados iguais.
        import sqlite3
        import gerar_modelo_celular

        def esquema(caminho):
            con = sqlite3.connect(caminho)
            try:
                return (sorted(con.execute("SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")),
                        con.execute('PRAGMA user_version').fetchone()[0],
                        con.execute('SELECT COUNT(*) FROM configuracoes').fetchone()[0])
            finally:
                con.close()

        with tempfile.TemporaryDirectory() as pasta:
            novo = Path(pasta) / 'modelo.sqlite3'
            gerar_modelo_celular.gerar(novo)
            self.assertEqual(esquema(RAIZ / 'celular' / 'modelo.sqlite3'), esquema(novo))

    def test_demonstracao_do_celular_igual_a_do_programa(self):
        # Mudou o esquema ou os dados fictícios? Rode "python gerar_modelo_celular.py".
        import sqlite3
        import gerar_modelo_celular

        def conteudo(caminho):
            con = sqlite3.connect(caminho)
            try:
                return {t: con.execute(f'SELECT * FROM {t} ORDER BY 1').fetchall()
                        for t in ('rpvs', 'contas', 'prorrogacoes', 'previsoes_historico', 'documentos')} | {
                    'esquema': sorted(con.execute("SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")),
                    'configuracoes': sorted(con.execute('SELECT chave FROM configuracoes'))}
            finally:
                con.close()

        with tempfile.TemporaryDirectory() as pasta:
            novo = Path(pasta) / 'demonstracao.sqlite3'
            gerar_modelo_celular.gerar(novo, com_demonstracao=True)
            atual = conteudo(RAIZ / 'celular' / 'demonstracao.sqlite3')
            gerado = conteudo(novo)
        # A data em que a operação teve a previsão alterada é o momento da geração: fica de fora.
        for dados in (atual, gerado):
            dados['previsoes_historico'] = [linha[:4] for linha in dados['previsoes_historico']]
        self.assertEqual(atual, gerado)
        self.assertEqual(atual['configuracoes'], [('dados_demonstracao',), ('demonstracao_referencia',)])

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
