import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json

from backup import criar_backup, BackupPreparado, executar_backup_automatico, PASTA_AUTOMATICA
from dados import Banco, limitar_backups
from apoio_testes import banco_com_contas, dados_rpv, dados_conta, SENHA_TESTE


def adulterar_banco(arquivo, destino, sql):
    """Gera um backup com o banco alterado por `sql` e hashes recalculados, como faria um atacante."""
    with tempfile.TemporaryDirectory() as pasta:
        banco = Path(pasta) / 'banco.sqlite3'
        with ZipFile(arquivo) as origem:
            banco.write_bytes(origem.read('banco.sqlite3'))
            con = sqlite3.connect(banco)
            con.executescript(sql)
            con.close()
            manifesto = json.loads(origem.read('manifesto.json'))
            manifesto['arquivos']['banco.sqlite3'] = hashlib.sha256(banco.read_bytes()).hexdigest()
            with ZipFile(destino, 'w', ZIP_DEFLATED) as alvo:
                for nome in origem.namelist():
                    if nome == 'banco.sqlite3':
                        alvo.write(banco, nome)
                    elif nome == 'manifesto.json':
                        alvo.writestr(nome, json.dumps(manifesto))
                    else:
                        alvo.writestr(nome, origem.read(nome))
    return destino


TRIGGER_PIX = """CREATE TRIGGER t_pix AFTER INSERT ON contas BEGIN
    UPDATE contas SET pix='golpista@exemplo.com' WHERE id=NEW.id; END;"""


class TestBackupHistorico(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name)
        self.origem = banco_com_contas(self.pasta / 'origem' / 'gestor.sqlite3')
        self.destino = banco_com_contas(self.pasta / 'destino' / 'gestor.sqlite3')

    def backup_sem_senha(self):
        """Backup no formato antigo, sem criptografia: os testes de adulteração mexem direto no ZIP."""
        self.origem.remover_configuracao('senha_backup')
        return criar_backup(self.origem, self.pasta / 'backups', exigir_senha=False)

    def anexar(self, banco, rpv, nome, conteudo):
        """Anexa um arquivo pela rotina normal do aplicativo e devolve onde ele foi guardado."""
        origem = self.pasta / 'anexos' / nome
        origem.parent.mkdir(exist_ok=True)
        origem.write_bytes(conteudo)
        banco.salvar(dict(banco.obter(rpv)), rpv, anexos=[origem])
        documento = [d for d in banco.documentos(rpv) if d['nome'] == nome][0]
        return banco.caminho_documento(documento['id'])

    def test_backup_portatil_tudo_inclusive_documentos_lixeira_auditoria(self):
        conta = self.origem.salvar_conta(dados_conta())
        rpv = self.origem.salvar(dados_rpv(conta_id=conta))
        self.origem.atualizar_previsao(rpv, '2027-01-20')
        self.origem.registrar_recebimento(rpv, '2026-10-22')
        outra = self.origem.salvar(dados_rpv(nome='Lixeira'))
        self.origem.excluir(outra)
        contrato = self.anexar(self.origem, rpv, 'contrato.pdf', b'%PDF-teste-do-contrato')
        self.anexar(self.origem, rpv, 'protocolo.png', b'PNG-teste-do-protocolo')
        (contrato.parent / 'solto.exe').write_bytes(b'MZ')  # Arquivo sem cadastro: fica fora do backup.
        anterior = self.destino.salvar(dados_rpv(nome='Anterior'))
        antigo = self.anexar(self.destino, anterior, 'antigo.pdf', b'antigo')
        destino_docs = self.destino.caminho.parent / 'documentos'
        arquivo = criar_backup(self.origem, self.pasta / 'backups')
        with BackupPreparado(arquivo, SENHA_TESTE) as preparado:
            self.assertEqual(preparado.resumo, {'registros': 1, 'lixeira': 1, 'contas': 3, 'documentos': 2})
            seguranca = preparado.restaurar(self.destino)
        restaurado = Banco(self.destino.caminho)
        self.assertEqual(restaurado.obter(rpv)['previsao_atual'], '2027-01-20')
        self.assertEqual(restaurado.obter(rpv)['recebimento'], '2026-10-22')
        self.assertEqual(len(restaurado.listar_lixeira()), 1)
        self.assertEqual((destino_docs / contrato.relative_to(contrato.parents[1])).read_bytes(), b'%PDF-teste-do-contrato')
        self.assertFalse((destino_docs / contrato.parent.name / 'solto.exe').exists())
        self.assertFalse(antigo.exists())
        # A cópia de segurança devolve os dados anteriores, anexos incluídos.
        de_volta = banco_com_contas(self.pasta / 'de-volta' / 'gestor.sqlite3')
        with BackupPreparado(seguranca, SENHA_TESTE) as anterior:
            anterior.restaurar(de_volta)
        self.assertEqual([r['nome'] for r in de_volta.listar()], ['Anterior'])
        self.assertEqual((de_volta.pasta_documentos / antigo.relative_to(antigo.parents[1])).read_bytes(), b'antigo')

    def test_backup_vazio_documentos_e_falha_importacao_preserva_destino(self):
        self.origem.salvar(dados_rpv(nome='Origem'))
        self.destino.salvar(dados_rpv(nome='Anterior'))
        docs = self.destino.caminho.parent / 'documentos'
        docs.mkdir()
        (docs / 'antigo.pdf').write_bytes(b'preservar')
        arquivo = criar_backup(self.origem, self.pasta / 'backups')
        with BackupPreparado(arquivo, SENHA_TESTE) as preparado:
            with patch('backup.copiar_banco', side_effect=sqlite3.OperationalError('Falha simulada')):
                with self.assertRaises(sqlite3.OperationalError):
                    preparado.restaurar(self.destino)
        self.assertEqual(self.destino.listar()[0]['nome'], 'Anterior')
        self.assertEqual((docs / 'antigo.pdf').read_bytes(), b'preservar')
        self.assertEqual(len(list((self.destino.caminho.parent / 'backups_automaticos').glob('*.rpvbackup'))), 1)

    def test_backup_alterado_invalido_ou_caminho_inseguro_nao_importa(self):
        contrato = self.anexar(self.origem, self.origem.salvar(dados_rpv()), 'contrato.pdf', b'original')
        arquivo = self.backup_sem_senha()
        alterado = self.pasta / 'alterado.rpvbackup'
        no_zip = 'documentos/' + contrato.relative_to(contrato.parents[1]).as_posix()
        with ZipFile(arquivo) as origem, ZipFile(alterado, 'w', ZIP_DEFLATED) as alvo:
            for nome in origem.namelist():
                alvo.writestr(nome, b'alterado' if nome == no_zip else origem.read(nome))
        with self.assertRaises(ValueError), BackupPreparado(alterado, SENHA_TESTE):
            pass
        inseguro = self.pasta / 'inseguro.rpvbackup'
        with ZipFile(inseguro, 'w') as pacote:
            pacote.writestr('../fora.txt', 'invalido')
        with self.assertRaises(ValueError), BackupPreparado(inseguro, SENHA_TESTE):
            pass
        self.assertFalse((self.pasta / 'fora.txt').exists())
        invalido = self.pasta / 'invalido.rpvbackup'
        invalido.write_bytes(b'isto nao e um backup')
        with self.assertRaises(ValueError), BackupPreparado(invalido, SENHA_TESTE):
            pass

    def test_backup_com_trigger_ou_view_e_recusado(self):
        arquivo = self.backup_sem_senha()
        for nome, sql in (('trigger', TRIGGER_PIX), ('view', 'CREATE VIEW v AS SELECT * FROM contas;'),
                          ('indice', 'CREATE INDEX i ON contas(pix);'), ('tabela', 'CREATE TABLE extra (x);')):
            with self.subTest(nome):
                adulterado = adulterar_banco(arquivo, self.pasta / f'{nome}.rpvbackup', sql)
                with self.assertRaisesRegex(ValueError, 'segurança'), BackupPreparado(adulterado, SENHA_TESTE):
                    pass

    def test_backup_com_arquivo_que_nao_e_documento_cadastrado_e_recusado(self):
        contrato = self.anexar(self.origem, self.origem.salvar(dados_rpv()), 'contrato.pdf', b'%PDF')
        arquivo = self.backup_sem_senha()
        manifesto = json.loads(ZipFile(arquivo).read('manifesto.json'))
        for nome in ('documentos/LEIA-ME URGENTE.exe', 'documentos/desktop.ini',
                     'documentos/' + contrato.parent.name + '/Comprovante.pdf.url'):
            with self.subTest(nome):
                extra = self.pasta / 'extra.rpvbackup'
                manifesto_extra = dict(manifesto, arquivos=dict(manifesto['arquivos'], **{nome: hashlib.sha256(b'x').hexdigest()}))
                with ZipFile(arquivo) as origem, ZipFile(extra, 'w', ZIP_DEFLATED) as alvo:
                    for item in origem.namelist():
                        alvo.writestr(item, json.dumps(manifesto_extra) if item == 'manifesto.json' else origem.read(item))
                    alvo.writestr(nome, b'x')
                with self.assertRaisesRegex(ValueError, 'não são documentos cadastrados'), BackupPreparado(extra, SENHA_TESTE):
                    pass

    def test_importacao_recria_o_esquema_e_copia_so_os_dados(self):
        # Mesmo que um trigger passasse pela validação, a importação monta um banco novo e o descarta.
        arquivo = self.backup_sem_senha()
        adulterado = adulterar_banco(arquivo, self.pasta / 'trigger.rpvbackup', TRIGGER_PIX)
        with patch('backup.verificar_estruturas'), BackupPreparado(adulterado, SENHA_TESTE) as preparado:
            preparado.restaurar(self.destino)
        restaurado = Banco(self.destino.caminho)
        with restaurado.conectar() as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0], 0)
        conta = restaurado.obter_conta(restaurado.salvar_conta(dados_conta(identificacao='Nova', pix='meu@exemplo.com',
                                                                           numero='777-1', cpf='52998224725')))
        self.assertEqual(conta['pix'], 'meu@exemplo.com')

    def test_bomba_de_descompressao_e_recusada_antes_de_extrair(self):
        arquivo = self.backup_sem_senha()
        manifesto = json.loads(ZipFile(arquivo).read('manifesto.json'))
        bomba = self.pasta / 'bomba.rpvbackup'
        nome = 'documentos/1/' + 'a' * 32 + '.pdf'
        manifesto['arquivos'][nome] = '0' * 64
        with ZipFile(arquivo) as origem, ZipFile(bomba, 'w', ZIP_DEFLATED) as alvo:
            for item in origem.namelist():
                alvo.writestr(item, json.dumps(manifesto) if item == 'manifesto.json' else origem.read(item))
            alvo.writestr(nome, b'\0' * (20 * 1024 ** 2))
        with self.assertRaisesRegex(ValueError, 'suspeita'), BackupPreparado(bomba, pasta_trabalho=self.pasta / 'trabalho'):
            pass
        self.assertEqual(list((self.pasta / 'trabalho').iterdir()), [])

    def test_importacao_trabalha_na_pasta_de_dados_e_sobras_antigas_sao_limpas(self):
        from backup import limpar_temporarios
        arquivo = criar_backup(self.origem, self.pasta / 'backups')
        dados = self.destino.caminho.parent
        with BackupPreparado(arquivo, SENHA_TESTE, pasta_trabalho=dados) as preparado:
            self.assertEqual(preparado.pasta.parent, dados)
        antiga, recente = dados / '.importar-rpv-antiga', dados / '.importar-rpv-recente'
        for sobra in (antiga, recente):
            (sobra / 'documentos').mkdir(parents=True)
        os.utime(antiga, (0, 0))
        limpar_temporarios(dados)
        self.assertFalse(antiga.exists())
        self.assertTrue(recente.exists())

    def test_banco_local_com_trigger_e_limpo_ao_abrir(self):
        con = sqlite3.connect(self.destino.caminho)
        con.executescript(TRIGGER_PIX + 'CREATE VIEW "v""x" AS SELECT 1;')
        con.close()
        banco = Banco(self.destino.caminho)
        with banco.conectar() as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type IN ('trigger','view')").fetchone()[0], 0)

    def test_lixeira_restauracao_e_prorrogacao_somente_na_lista_ativa(self):
        identificador = self.origem.salvar(dados_rpv())
        self.origem.salvar(dados_rpv(observacoes='Alteração'), identificador)
        self.origem.atualizar_previsao(identificador, '2027-01-20')
        self.origem.registrar_recebimento(identificador, '2026-10-22')
        with self.assertRaises(ValueError):
            self.origem.salvar(dados_rpv(custo=0), identificador)
        self.assertEqual(self.origem.obter(identificador)['observacoes'], 'Alteração')
        self.origem.excluir(identificador)
        self.assertEqual(self.origem.listar(), [])
        self.assertEqual(len(self.origem.listar_lixeira()), 1)
        self.origem.restaurar(identificador)
        self.assertEqual(self.origem.obter(identificador)['recebimento'], '2026-10-22')

    def test_migracao_080_remove_unicidade_cpf_preserva_vinculos(self):
        conta = self.origem.salvar_conta(dados_conta())
        identificador = self.origem.salvar(dados_rpv(conta_id=conta))
        self.origem.registrar_recebimento(identificador, '2026-10-22')
        snapshot = self.origem.obter(identificador)['conta_snapshot']
        with self.origem.conectar() as con:
            con.execute('ALTER TABLE rpvs DROP COLUMN lixeira_em')
            esquema = con.execute("SELECT sql FROM sqlite_master WHERE name='contas'").fetchone()[0]
            esquema = esquema.replace('CREATE TABLE contas', 'CREATE TABLE contas_legado').replace('cpf TEXT,', 'cpf TEXT UNIQUE,')
            con.execute('PRAGMA foreign_keys=OFF')
            con.execute(esquema)
            campos = ','.join(r['name'] for r in con.execute('PRAGMA table_info(contas)'))
            con.execute(f'INSERT INTO contas_legado ({campos}) SELECT {campos} FROM contas')
            con.execute('DROP TABLE contas')
            con.execute('ALTER TABLE contas_legado RENAME TO contas')
            con.execute('PRAGMA user_version=3')
        migrado = Banco(self.origem.caminho)
        nova = migrado.salvar_conta(dados_conta(identificacao='Outro banco', numero='999', pix='outro@example.com'))
        self.assertNotEqual(conta, nova)
        self.assertEqual(migrado.obter(identificador)['conta_snapshot'], snapshot)
        self.assertEqual(migrado.obter(identificador)['recebimento'], '2026-10-22')
        with migrado.conectar() as con:
            self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertFalse(Banco.cpf_unico(con))
        with migrado.conectar() as con:
            self.assertIsNone(con.execute("SELECT 1 FROM sqlite_master WHERE name='historico_alteracoes'").fetchone())
        self.assertEqual(len(list(migrado.caminho.parent.glob('backup-antes-0.9.0-*.sqlite3'))), 1)

    def test_backup_dentro_da_pasta_documentos_nao_inclui_a_si_mesmo(self):
        self.anexar(self.origem, self.origem.salvar(dados_rpv()), 'contrato.pdf', b'%PDF-contrato')
        docs = self.origem.caminho.parent / 'documentos'
        primeiro = criar_backup(self.origem, docs)
        segundo = criar_backup(self.origem, docs)
        with BackupPreparado(segundo, SENHA_TESTE) as preparado:
            self.assertEqual(preparado.resumo['documentos'], 1)
        self.assertTrue(primeiro.exists())

    def test_backups_automaticos_mantem_somente_os_dez_mais_recentes(self):
        automaticos = self.destino.caminho.parent / 'backups_automaticos'
        automaticos.mkdir()
        for indice in range(12):
            antigo = automaticos / f'GestorRPV-202001{indice:02d}.rpvbackup'
            antigo.write_bytes(b'antigo')
            os.utime(antigo, (1_600_000_000 + indice, 1_600_000_000 + indice))
        outro = automaticos / 'manter.txt'
        outro.write_text('não é backup')
        self.origem.salvar(dados_rpv(nome='Origem'))
        arquivo = criar_backup(self.origem, self.pasta / 'exportado')
        with BackupPreparado(arquivo, SENHA_TESTE) as pacote:
            seguranca = pacote.restaurar(self.destino)
        restantes = list(automaticos.glob('*.rpvbackup'))
        self.assertEqual(len(restantes), 10)
        self.assertIn(seguranca, restantes)
        self.assertFalse((automaticos / 'GestorRPV-20200100.rpvbackup').exists())
        self.assertTrue(outro.exists())
        limitar_backups(automaticos, '*.rpvbackup', manter=3)
        self.assertEqual(len(list(automaticos.glob('*.rpvbackup'))), 3)
        self.assertTrue(seguranca.exists())

    def test_backups_antes_da_atualizacao_mantem_somente_os_dez_mais_recentes(self):
        pasta = self.destino.caminho.parent
        for indice in range(11):
            antigo = pasta / f'backup-antes-0.9.0-202001{indice:02d}.sqlite3'
            antigo.write_bytes(b'antigo')
            os.utime(antigo, (1_600_000_000 + indice, 1_600_000_000 + indice))
        with self.destino.conectar() as con:
            con.execute('PRAGMA user_version=6')
        Banco(self.destino.caminho)
        restantes = list(pasta.glob('backup-antes-*.sqlite3'))
        self.assertEqual(len(restantes), 10)
        self.assertEqual(len(list(pasta.glob('backup-antes-0.16.0-*.sqlite3'))), 1)
        self.assertFalse((pasta / 'backup-antes-0.9.0-20200100.sqlite3').exists())

    def test_backup_automatico_semanal_preserva_backups_manuais(self):
        self.assertIsNone(executar_backup_automatico(self.origem))
        pasta = self.pasta / 'nuvem'
        pasta.mkdir()
        manual = criar_backup(self.origem, pasta)
        self.origem.salvar_configuracao(PASTA_AUTOMATICA, str(pasta))
        self.assertIsNone(executar_backup_automatico(self.origem))
        self.origem.registrar_backup('2020-01-01T12:00:00')
        primeiro = executar_backup_automatico(self.origem)
        self.assertTrue(primeiro.name.startswith('GestorRPV-auto-'))
        self.assertIsNone(executar_backup_automatico(self.origem))
        for indice in range(11):
            antigo = pasta / f'GestorRPV-auto-202001{indice:02d}.rpvbackup'
            antigo.write_bytes(b'antigo')
            os.utime(antigo, (1_600_000_000 + indice, 1_600_000_000 + indice))
        ultimo = executar_backup_automatico(self.origem, forcar=True)
        self.assertEqual(len(list(pasta.glob('GestorRPV-auto-*.rpvbackup'))), 10)
        self.assertTrue(ultimo.exists())
        self.assertTrue(primeiro.exists())
        self.assertTrue(manual.exists())
        with BackupPreparado(ultimo, SENHA_TESTE) as preparado:
            self.assertEqual(preparado.resumo['contas'], 2)

    def test_backup_automatico_com_pasta_indisponivel_nao_cria_pasta(self):
        ausente = self.pasta / 'disco-externo' / 'backups'
        self.origem.salvar_configuracao(PASTA_AUTOMATICA, str(ausente))
        with self.assertRaises(OSError):
            executar_backup_automatico(self.origem)
        self.assertFalse(ausente.exists())
        self.assertIsNone(self.origem.ultimo_backup())

    def test_migracao_021_remove_historico_geral_e_guarda_copia(self):
        identificador = self.origem.salvar(dados_rpv())
        with self.origem.conectar() as con:
            con.execute('''CREATE TABLE historico_alteracoes (
                id INTEGER PRIMARY KEY, rpv_id INTEGER NOT NULL REFERENCES rpvs(id) ON DELETE CASCADE,
                quando TEXT NOT NULL, acao TEXT NOT NULL, alteracoes TEXT NOT NULL)''')
            con.execute("INSERT INTO historico_alteracoes (rpv_id,quando,acao,alteracoes) VALUES (?,'2026-01-01','Legado','{}')",
                        (identificador,))
            con.execute('PRAGMA user_version=7')
        migrado = Banco(self.origem.caminho)
        with migrado.conectar() as con:
            self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0], 8)
            self.assertIsNone(con.execute("SELECT 1 FROM sqlite_master WHERE name='historico_alteracoes'").fetchone())
        copias = list(migrado.caminho.parent.glob('backup-antes-0.21.0-*.sqlite3'))
        self.assertEqual(len(copias), 1)
        copia = sqlite3.connect(copias[0])
        try:
            self.assertEqual(copia.execute('SELECT COUNT(*) FROM historico_alteracoes').fetchone()[0], 1)
        finally:
            copia.close()
        self.assertEqual(migrado.obter(identificador)['nome'], 'Pessoa De Teste')


if __name__ == '__main__':
    unittest.main()
