"""Cada recusa do backup e da gravação, com a mensagem certa: são os caminhos que protegem os dados."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from backup import BackupPreparado, criar_backup
from dados import VERSAO_BANCO, Banco
from apoio_testes import SENHA_TESTE, banco_com_contas, dados_conta, dados_rpv


class TestRecusasDoBackup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name)
        Banco(self.pasta / 'modelo.sqlite3')
        self.banco_bytes = (self.pasta / 'modelo.sqlite3').read_bytes()

    def pacote(self, nome, arquivos=None, manifesto=None, sem_manifesto=False, versao_banco=None):
        """Monta um backup à mão, como faria alguém tentando enganar a importação."""
        banco = self.banco_bytes
        if versao_banco is not None:
            caminho = self.pasta / f'v{versao_banco}.sqlite3'
            caminho.write_bytes(banco)
            con = sqlite3.connect(caminho)
            con.execute(f'PRAGMA user_version={versao_banco}')
            con.close()
            banco = caminho.read_bytes()
        arquivos = {'banco.sqlite3': banco, **(arquivos or {})}
        dados_manifesto = {'formato': 'gestor-rpv-backup', 'versao_formato': 1,
                           'arquivos': {n: hashlib.sha256(c).hexdigest() for n, c in arquivos.items()}}
        dados_manifesto.update(manifesto or {})
        destino = self.pasta / nome
        with ZipFile(destino, 'w', ZIP_DEFLATED) as zipado:
            for nome_arquivo, conteudo in arquivos.items():
                zipado.writestr(nome_arquivo, conteudo)
            if not sem_manifesto:
                zipado.writestr('manifesto.json', json.dumps(dados_manifesto))
        return destino

    def assertRecusa(self, arquivo, trecho):
        with self.assertRaises(ValueError) as contexto, BackupPreparado(arquivo, SENHA_TESTE):
            pass
        self.assertIn(trecho, str(contexto.exception))

    def test_cada_problema_tem_sua_recusa(self):
        documento = 'documentos/1/' + 'a' * 32 + '.pdf'
        casos = (
            ('versão futura do banco', self.pacote('futura.rpvbackup', versao_banco=VERSAO_BANCO + 1), 'outra versão'),
            ('formato desconhecido', self.pacote('f2.rpvbackup', manifesto={'versao_formato': 2}), 'Formato de backup'),
            ('sem manifesto', self.pacote('sm.rpvbackup', sem_manifesto=True), 'Manifesto'),
            ('manifesto que não é objeto', self.pacote('mo.rpvbackup', manifesto={'arquivos': [1, 2]}), 'incompleta'),
            ('lista incompleta', self.pacote('li.rpvbackup', arquivos={documento: b'%PDF'},
                                             manifesto={'arquivos': {'banco.sqlite3': '0'}}), 'incompleta'),
            ('arquivo desconhecido', self.pacote('ad.rpvbackup', arquivos={'outro.txt': b'x'}), 'desconhecidos'),
            ('caminho com ..', self.pacote('pp.rpvbackup', arquivos={'documentos/../x.pdf': b'x'}), 'caminho inválido'),
            ('arquivo alterado', self.pacote('aa.rpvbackup', manifesto={'arquivos': {'banco.sqlite3': '0' * 64}}),
             'danificado ou foi alterado'),
            ('banco que não é SQLite', None, 'validar o banco'),
            ('documento sem cadastro', self.pacote('ds.rpvbackup', arquivos={documento: b'%PDF'}), 'não são documentos'),
        )
        for nome, arquivo, trecho in casos:
            if arquivo is None:
                self.banco_bytes, original = b'nao sou sqlite' * 100, self.banco_bytes
                arquivo = self.pacote('ns.rpvbackup')
                self.banco_bytes = original
            with self.subTest(nome):
                self.assertRecusa(arquivo, trecho)

    def test_nomes_repetidos_e_arquivos_demais(self):
        repetido = self.pasta / 'rep.rpvbackup'
        with ZipFile(repetido, 'w') as zipado:
            zipado.writestr('banco.sqlite3', self.banco_bytes)
            zipado.writestr('BANCO.sqlite3', self.banco_bytes)
        self.assertRecusa(repetido, 'repetidos')

    def test_documento_cadastrado_ausente_no_pacote(self):
        origem = banco_com_contas(self.pasta / 'origem' / 'gestor.sqlite3')
        anexo = self.pasta / 'contrato.pdf'
        anexo.write_bytes(b'%PDF')
        origem.salvar(dados_rpv(), anexos=[anexo])
        origem.remover_configuracao('senha_backup')
        completo = criar_backup(origem, self.pasta / 'backups', exigir_senha=False)
        with ZipFile(completo) as zipado:
            manifesto = json.loads(zipado.read('manifesto.json'))
            banco = zipado.read('banco.sqlite3')
        manifesto['arquivos'] = {'banco.sqlite3': manifesto['arquivos']['banco.sqlite3']}
        sem_documento = self.pasta / 'sem-documento.rpvbackup'
        with ZipFile(sem_documento, 'w') as zipado:
            zipado.writestr('banco.sqlite3', banco)
            zipado.writestr('manifesto.json', json.dumps(manifesto))
        self.assertRecusa(sem_documento, 'ausente no backup')


class TestRecusasDaGravacao(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.banco = banco_com_contas(Path(self.temp.name) / 'gestor.sqlite3')

    def test_contas_invalidas(self):
        for valores, trecho in ((dict(cpf=''), 'Preencha'), (dict(cpf='529.982.247-2a'), 'CPF inválido'),
                                (dict(cpf='111.111.111-11'), 'CPF inválido'), (dict(cpf='529.982.247-24'), 'CPF inválido'),
                                (dict(estado='XX'), 'estado brasileiro')):
            with self.subTest(trecho, **valores), self.assertRaisesRegex(ValueError, trecho):
                self.banco.salvar_conta(dados_conta(**valores))

    def test_operacoes_invalidas(self):
        identificador = self.banco.salvar(dados_rpv())
        self.banco.registrar_recebimento(identificador, '2026-10-25')
        for chamada, trecho in (
            (lambda: self.banco.salvar(dados_rpv(conta_id=999999)), 'conta cadastrada'),
            (lambda: self.banco.salvar(dados_rpv(aquisicao='2026-10-26', previsao='2026-12-01'), identificador),
             'posterior à data do recebimento'),
            (lambda: self.banco.registrar_recebimento(999999, '2026-10-22'), 'não encontrado'),
            (lambda: self.banco.atualizar_previsao(999999, '2026-12-22'), 'não encontrado'),
            (lambda: self.banco.atualizar_previsao(identificador, '2026-10-01'), 'anterior à aquisição'),
            (lambda: self.banco.registrar_recebimento(identificador, None, anexos=['x.pdf']), 'data do recebimento'),
        ):
            with self.subTest(trecho), self.assertRaisesRegex(ValueError, trecho):
                chamada()
        self.banco.excluir(identificador)
        with self.assertRaisesRegex(ValueError, 'lixeira'):
            self.banco.salvar(dados_rpv(), identificador)


if __name__ == '__main__':
    unittest.main()
