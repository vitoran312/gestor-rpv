"""Backup na nuvem: o Worker (nuvem/worker.js, rodando no Node com um KV na memória) e o cliente do programa
(nuvem.py). O lembrete cifrado pelo Worker é decifrado aqui por conta própria, seguindo a RFC 8291."""
import base64
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import messagebox
from unittest.mock import patch

import nuvem
from apoio_interface import TesteDeInterface

RAIZ = Path(__file__).resolve().parent
NODE = shutil.which('node')


def b64(texto):
    return base64.urlsafe_b64decode(texto + '=' * (-len(texto) % 4))


@unittest.skipUnless(NODE, 'Requer Node.js')
class TestWorker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        saida = subprocess.run([NODE, str(RAIZ / 'nuvem' / 'teste_worker.mjs')], capture_output=True, text=True,
                               check=True, timeout=120)
        cls.r = json.loads(saida.stdout)

    def test_backup_em_partes_volta_igual(self):
        self.assertEqual(self.r['envio'], {'status': 200, 'partes': 2, 'tamanho': 21 * 1024 * 1024})
        self.assertTrue(self.r['igual'])

    def test_sem_a_chave_certa_nada_e_lido_nem_trocado(self):
        self.assertEqual((self.r['chave_errada'], self.r['sem_chave'], self.r['envio_chave_errada']), (404, 404, 403))
        self.assertEqual(self.r['endereco_ruim'], 404)

    def test_outro_aparelho_com_a_mesma_senha_so_substitui_se_pedir(self):
        self.assertEqual((self.r['conflito'], self.r['substituido'], self.r['mesmo_aparelho']), (409, 200, 200))
        self.assertEqual(self.r['partes_antigas'], 0)  # As partes da versão anterior saem do KV.

    def test_apagar_tira_tudo(self):
        self.assertEqual((self.r['apagar'], self.r['depois_de_apagar']), (200, 404))
        self.assertEqual(self.r['sobrou'], [])

    def test_lembrete_uma_vez_por_dia_e_assinatura_vencida_sai(self):
        self.assertEqual((self.r['lembrete'], self.r['lembrete_ruim']), (200, 400))
        self.assertEqual(self.r['primeira_rodada'], {'avisados': 1, 'removidos': 0})
        self.assertEqual(self.r['segunda_rodada'], {'avisados': 0, 'removidos': 0})
        self.assertEqual(self.r['sem_previsao'], {'avisados': 0, 'removidos': 0})
        self.assertEqual(self.r['assinatura_vencida'], {'avisados': 0, 'removidos': 1, 'restou': False})

    def test_lembrete_decifra_pela_rfc_8291(self):
        from cryptography.hazmat.primitives import hashes, hmac
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        n = self.r['notificacao']
        self.assertEqual(n['cabecalhos']['Content-Encoding'], 'aes128gcm')
        jwk = n['privada_aparelho']
        privada = ec.derive_private_key(int.from_bytes(b64(jwk['d']), 'big'), ec.SECP256R1())
        publica_aparelho = privada.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        corpo = b64(n['corpo'])
        sal, tamanho_id = corpo[:16], corpo[20]
        publica_servidor = corpo[21:21 + tamanho_id]
        cifrado = corpo[21 + tamanho_id:]

        def mac(chave, dados):
            h = hmac.HMAC(chave, hashes.SHA256())
            h.update(dados)
            return h.finalize()
        compartilhado = privada.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), publica_servidor))
        ikm = mac(mac(b64(n['segredo']), compartilhado), b'WebPush: info\0' + publica_aparelho + publica_servidor + b'\1')
        prk = mac(sal, ikm)
        cek = mac(prk, b'Content-Encoding: aes128gcm\0\1')[:16]
        nonce = mac(prk, b'Content-Encoding: nonce\0\1')[:12]
        claro = AESGCM(cek).decrypt(nonce, cifrado, None)
        self.assertEqual(claro[-1], 2)  # Delimitador do último registro.
        mensagem = json.loads(claro[:-1])
        self.assertEqual(mensagem['endereco'], '#agenda')
        self.assertIn('Amanhã há 2 previsões de recebimento', mensagem['texto'])

    def test_vapid_assinado_pela_chave_publica_anunciada(self):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
        n = self.r['notificacao']
        cabecalho = n['cabecalhos']['Authorization']
        token = cabecalho.split('t=')[1].split(',')[0]
        self.assertTrue(cabecalho.endswith('k=' + n['vapid_publica']))
        cabeca, corpo, assinatura = token.split('.')
        self.assertEqual(json.loads(b64(corpo))['aud'], 'https://push.exemplo')
        publica = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b64(n['vapid_publica']))
        bruta = b64(assinatura)
        der = encode_dss_signature(int.from_bytes(bruta[:32], 'big'), int.from_bytes(bruta[32:], 'big'))
        publica.verify(der, f'{cabeca}.{corpo}'.encode(), ec.ECDSA(hashes.SHA256()))  # Lança se não conferir.


class TestCredenciais(unittest.TestCase):
    def test_derivadas_da_senha_sem_depender_do_jeito_de_compor_acentos(self):
        import unicodedata
        identificador, chave = nuvem.credenciais('Café forte 9')
        self.assertRegex(identificador, r'^[0-9a-f]{32}$')
        self.assertRegex(chave, r'^[0-9a-f]{64}$')
        self.assertEqual(nuvem.credenciais(unicodedata.normalize('NFD', 'Café forte 9')), (identificador, chave))
        self.assertNotEqual(nuvem.credenciais('Cafe forte 9')[0], identificador)
        base = hashlib.scrypt('Café forte 9'.encode(), salt=b'gestor-rpv/nuvem/v1', n=2 ** 15, r=8, p=1,
                              maxmem=64 * 1024 ** 2, dklen=32)
        self.assertEqual(identificador, hashlib.sha256(base + b'id').hexdigest()[:32])


@unittest.skipUnless(NODE, 'Requer Node.js')
class TestClienteDoPrograma(unittest.TestCase):
    """nuvem.py contra o Worker de verdade, servido no próprio computador."""

    def setUp(self):
        self.processo = subprocess.Popen([NODE, str(RAIZ / 'nuvem' / 'local.mjs')], stdout=subprocess.PIPE, text=True)
        porta = self.processo.stdout.readline().strip()
        self.addCleanup(self.processo.stdout.close)
        self.addCleanup(self.processo.wait)
        self.addCleanup(self.processo.terminate)
        ambiente = patch.dict(os.environ, {'GESTOR_RPV_NUVEM': f'http://127.0.0.1:{porta}'})
        ambiente.start()
        self.addCleanup(ambiente.stop)
        self.acesso = nuvem.credenciais('cavalo azul 7')
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, True)

    def enviar(self, bytes_, sal='1' * 32):
        import urllib.request
        identificador, chave = self.acesso
        pedido = urllib.request.Request(f'{nuvem.endereco()}/v1/backup/{identificador}', data=bytes_, method='PUT', headers={
            'X-Gestor-Chave': chave, 'X-Gestor-Sal': sal, 'X-Gestor-Resumo': hashlib.sha256(bytes_).hexdigest(),
            'X-Gestor-Criado': '2026-10-30T10:00:00-03:00'})
        with urllib.request.urlopen(pedido) as resposta:
            return json.loads(resposta.read())

    def test_nada_na_nuvem(self):
        self.assertIsNone(nuvem.consultar(self.acesso))

    def test_baixa_e_confere(self):
        conteudo = os.urandom(300_000)
        enviado = self.enviar(conteudo)
        meta = nuvem.consultar(self.acesso)
        self.assertEqual((meta['versao'], meta['criado_em']), (enviado['versao'], '2026-10-30T10:00:00-03:00'))
        destino = nuvem.baixar(self.acesso, meta, self.temp / 'nuvem.rpvbackup')
        self.assertEqual(destino.read_bytes(), conteudo)

    def test_resumo_que_nao_confere_e_recusado(self):
        self.enviar(b'abc')
        meta = dict(nuvem.consultar(self.acesso), resumo='0' * 64)
        with self.assertRaises(nuvem.NuvemIndisponivel):
            nuvem.baixar(self.acesso, meta, self.temp / 'x.rpvbackup')
        self.assertFalse((self.temp / 'x.rpvbackup').exists())

    def test_sem_conexao(self):
        with patch.dict(os.environ, {'GESTOR_RPV_NUVEM': 'http://127.0.0.1:9'}), self.assertRaises(nuvem.NuvemIndisponivel):
            nuvem.consultar(self.acesso)


if __name__ == '__main__':
    unittest.main()


class TestSomenteLeitura(unittest.TestCase):
    def test_banco_recusa_alteracoes_mas_le_normalmente(self):
        from apoio_testes import banco_com_contas, dados_rpv
        from dados import SomenteLeitura
        pasta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, pasta, True)
        banco = banco_com_contas(pasta / 'b.sqlite3')
        identificador = banco.salvar(dados_rpv(nome='Antes'))
        banco.somente_leitura = True
        for acao in (lambda: banco.salvar(dados_rpv()), lambda: banco.excluir(identificador),
                     lambda: banco.atualizar_previsao(identificador, '2027-01-01'), lambda: banco.ativar_conta(1, False),
                     lambda: banco.registrar_recebimento(identificador, '2026-10-25')):
            with self.assertRaises(SomenteLeitura):
                acao()
        self.assertEqual([r['nome'] for r in banco.listar()], ['Antes'])
        banco.salvar_configuracao('qualquer', '1')  # Configurações deste computador continuam gravando.


class TestCelularPrincipalNoPrograma(TesteDeInterface):
    """O que o programa faz com o backup que o celular mandou: troca os dados, fica só para consulta e volta a
    editar quando o celular deixa de enviar."""

    def backup_do_celular(self, nome):
        from apoio_testes import SENHA_TESTE, banco_com_contas, dados_rpv
        from backup import criar_backup
        outro = banco_com_contas(Path(self.pasta.name) / 'celular.sqlite3')
        outro.salvar(dados_rpv(nome=nome))
        arquivo = criar_backup(outro, Path(self.pasta.name), registrar=False)
        self.assertEqual(SENHA_TESTE, self.banco.configuracao('senha_backup'))
        return arquivo

    def test_troca_os_dados_fica_so_consulta_e_volta_quando_o_celular_para(self):
        from apoio_testes import SENHA_TESTE, dados_rpv
        self.banco.salvar(dados_rpv(nome='Do Computador'))
        meta = {'versao': 'v1', 'criado_em': '2026-10-30T14:32:05-03:00'}
        self.programa.aplicar_nuvem(SENHA_TESTE, {'meta': meta, 'arquivo': self.backup_do_celular('Do Celular')})
        self.root.update()
        self.assertEqual([r['nome'] for r in self.banco.listar()], ['Do Celular'])
        self.assertTrue(self.banco.somente_leitura)
        self.assertEqual((self.banco.configuracao(nuvem.VERSAO), self.banco.configuracao(nuvem.ESPELHO)), ('v1', '1'))
        self.assertIn('30/10/2026 às 14:32', self.dialogos[0][1][1])  # A primeira vez pergunta.
        # Só consulta: Nova entrada avisa e nem abre o formulário.
        self.programa.formulario()
        self.root.update()
        self.assertEqual(self.dialogos[-1][0], 'showinfo')
        self.assertIn('só para consulta', self.dialogos[-1][1][1])
        self.assertFalse(any(isinstance(w, tk.Toplevel) and w.title() == 'Nova entrada' for w in self.root.winfo_children()))
        # Mesma versão: nada é baixado nem perguntado de novo.
        quantos = len(self.dialogos)
        self.programa.aplicar_nuvem(SENHA_TESTE, {'meta': meta})
        self.assertEqual(len(self.dialogos), quantos)
        # O celular apagou o backup da nuvem: o computador volta a editar.
        self.programa.aplicar_nuvem(SENHA_TESTE, {'meta': None})
        self.assertFalse(self.banco.somente_leitura)
        self.assertIsNone(self.banco.configuracao(nuvem.ESPELHO))

    def test_recusar_na_primeira_vez_mantem_os_dados(self):
        from apoio_testes import SENHA_TESTE, dados_rpv
        self.banco.salvar(dados_rpv(nome='Fica'))
        arquivo = self.backup_do_celular('Não Entra')
        with patch.object(messagebox, 'askyesno', return_value=False):
            self.programa.aplicar_nuvem(SENHA_TESTE, {'meta': {'versao': 'v1', 'criado_em': ''}, 'arquivo': arquivo})
        self.assertEqual([r['nome'] for r in self.banco.listar()], ['Fica'])
        self.assertFalse(self.banco.somente_leitura)
        self.assertFalse(arquivo.exists())  # O arquivo baixado não fica para trás.

    def test_sem_internet_segue_com_os_dados_do_celular(self):
        self.banco.salvar_configuracao(nuvem.ESPELHO, '1')
        self.banco.somente_leitura = True
        self.programa.aplicar_nuvem('x', {'erro': nuvem.NuvemIndisponivel('sem rede')})
        self.assertTrue(self.banco.somente_leitura)


@unittest.skipUnless(os.environ.get('GESTOR_RPV_TESTE_CELULAR') == '1', 'Requer Node.js com Playwright e '
                     'GESTOR_RPV_TESTE_CELULAR=1')
class TestNuvemPeloCelular(unittest.TestCase):
    """O app com o Worker de verdade (desviado para o computador): ligar, enviar a cada gravação, recuperar num
    celular novo, desligar e tornar principal; o programa abre o que o celular mandou."""
    SENHA = 'jardim de inverno 4'
    CONTA = {'identificacao': 'conta da nuvem', 'nome': 'ana paula lima', 'cpf': '529.982.247-25', 'endereco': 'rua b',
             'numero_endereco': '5', 'cidade': 'recife', 'estado': 'PE', 'banco': 'inter', 'agencia': '0001',
             'numero': '998877', 'pix': 'ana@example.com'}
    ENTRADA = {'nome': 'entrada pela nuvem', 'aquisicao': '2026-10-01', 'custo': '500000', 'previsto': '800000',
               'previsao': '2026-12-01'}

    @classmethod
    def setUpClass(cls):
        import functools
        import threading
        from http.server import ThreadingHTTPServer
        from apoio_testes import SENHA_TESTE, banco_com_contas, dados_rpv
        from backup import criar_backup
        from test_celular import Silencioso, rodar_node
        cls.temp = tempfile.TemporaryDirectory()
        pasta = Path(cls.temp.name)
        site = pasta / 'site'
        shutil.copytree(RAIZ / 'celular', site, ignore=shutil.ignore_patterns('testes'))
        banco = banco_com_contas(pasta / 'pc.sqlite3')
        banco.salvar(dados_rpv(nome='do computador'))
        backup_pc = criar_backup(banco, pasta, registrar=False)
        servidor = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Silencioso, directory=str(site)))
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        try:
            cls.r = json.loads(rodar_node('nuvem.cjs', f'http://127.0.0.1:{servidor.server_address[1]}', {
                'senha': cls.SENHA, 'conta': cls.CONTA, 'entrada': cls.ENTRADA, 'backup_pc': str(backup_pc),
                'senha_pc': SENHA_TESTE}))
        finally:
            servidor.shutdown()
            servidor.server_close()
        cls.senha_pc = SENHA_TESTE

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_sem_erros_na_pagina(self):
        self.assertEqual(self.r['erros'], [])

    def test_mesmo_identificador_que_o_programa(self):
        self.assertEqual(self.r['id'], nuvem.credenciais(self.SENHA)[0])
        self.assertEqual(self.r['principal_id'], nuvem.credenciais(self.senha_pc)[0])

    def test_ligar_confere_a_senha_e_envia_a_cada_gravacao(self):
        self.assertIn('Ligar backup na nuvem', self.r['mais_desligado'])
        self.assertNotIn('Trancar agora', self.r['mais_desligado'])
        self.assertIn('Senha incorreta', self.r['senha_errada'])
        self.assertIn('Ligado · último envio em', self.r['mais_ligado'])
        self.assertTrue(self.r['reenviado'])
        self.assertTrue(self.r['guardado_igual'])  # A nuvem tem exatamente o arquivo guardado no celular.

    def test_programa_abre_o_backup_enviado(self):
        from apoio_testes import banco_com_contas
        from backup import BackupPreparado
        pasta = Path(self.temp.name)
        arquivo = pasta / 'da-nuvem.rpvbackup'
        arquivo.write_bytes(base64.b64decode(self.r['backup']))
        banco = banco_com_contas(pasta / 'outro-pc.sqlite3')
        with BackupPreparado(arquivo, self.SENHA, pasta_trabalho=pasta / 'trabalho') as pacote:
            pacote.restaurar(banco, copia_de_seguranca=False)
        self.assertEqual([r['nome'] for r in banco.listar()], ['Entrada Pela Nuvem'])

    def test_celular_novo_recupera_e_desligar_apaga(self):
        self.assertTrue(self.r['abertura_recuperar'])
        self.assertEqual(self.r['passo_recuperar'], {'form': True, 'comecar': False})
        self.assertIn('Nenhum backup na nuvem com essa senha', self.r['recuperar_senha_errada'])
        self.assertIn('Entrada Pela Nuvem', self.r['recuperado'])
        self.assertIn('Backup automático na nuvem', self.r['recuperado_mais'])
        self.assertIn('Ligado', self.r['recuperado_mais'])
        self.assertTrue(self.r['desligado'])

    def test_celular_do_backup_do_computador_vira_principal(self):
        self.assertIn('Tornar este celular o principal', self.r['mais_pc'])
        self.assertIn('o programa no computador carrega sozinho', self.r['tela_principal'])
        self.assertIn('Senha incorreta', self.r['principal_senha_errada'])
        self.assertTrue(self.r['principal_guardado'])
        self.assertIn('Do Computador', self.r['principal_operacoes'])
        self.assertIn('Ligado', self.r['principal_mais'])
        self.assertNotIn('Tornar este celular o principal', self.r['principal_mais'])
