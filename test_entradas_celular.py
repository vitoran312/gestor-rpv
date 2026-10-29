"""Entradas cadastradas no app do celular chegando ao programa (entradas_celular.py)."""
import base64
import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

import cifra
import entradas_celular
from backup import PASTA_AUTOMATICA
from apoio_testes import SENHA_TESTE, banco_com_contas, dados_conta, dados_rpv

PNG_1X1 = bytes.fromhex('89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c6338'
                        '2167040002ca0119bfd3bf060000000049454e44ae426082')
EDITAVEIS = ('nome', 'aquisicao', 'custo', 'previsto', 'conta_id', 'conta', 'previsao', 'comissao', 'observacoes')


def entrada(**valores):
    dados = dict(id=str(uuid.uuid4()), nome='Fulano De Tal', aquisicao='2026-10-01', custo=500000, previsto=800000,
                 conta_id=None, conta='Vitor', previsao='2026-12-01', comissao=None, observacoes='',
                 criada_em='2026-10-28T10:00:00-03:00')
    dados.update(valores)
    return dados


class TestEntradasDoCelular(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name)
        self.banco = banco_com_contas(self.pasta / 'dados' / 'gestor.sqlite3')
        self.drive = self.pasta / 'drive'
        self.drive.mkdir()
        self.banco.salvar_configuracao(PASTA_AUTOMATICA, str(self.drive))
        self.vitor = next(c['id'] for c in self.banco.contas() if c['identificacao'] == 'Vitor')

    def arquivo(self, dados, senha=SENHA_TESTE, nome=None, pacote=None):
        """Grava um arquivo como o app grava: JSON cifrado no formato dos backups."""
        aberto = self.pasta / 'aberto.json'
        aberto.write_text(json.dumps(pacote or {'formato': 'gestor-rpv-celular', 'versao_formato': 1, 'entrada': dados}),
                          encoding='utf-8')
        destino = self.drive / (nome or f'GestorRPV-celular-{dados["id"][:8]}.rpvcelular')
        cifra.cifrar_arquivo(aberto, destino, senha)
        return destino

    def test_entrada_importada_uma_vez_so(self):
        dados = entrada(conta_id=self.vitor, comissao=10000, observacoes='feita no celular')
        arquivo = self.arquivo(dados)
        copia = self.pasta / 'copia.rpvcelular'
        shutil.copy(arquivo, copia)
        encontradas, problemas = entradas_celular.procurar(self.banco)
        self.assertEqual(problemas, [])
        self.assertEqual([e['id'] for _, e in encontradas], [dados['id']])
        self.assertEqual(entradas_celular.importar(self.banco, encontradas), (1, []))
        registro = self.banco.listar()[0]
        self.assertEqual((registro['nome'], registro['custo'], registro['previsto'], registro['comissao'],
                          registro['conta_id'], registro['observacoes']),
                         ('Fulano De Tal', 500000, 800000, 10000, self.vitor, 'Feita no celular'))
        self.assertIn(dados['id'], entradas_celular.importadas(self.banco))
        # O arquivo sai da pasta principal e fica guardado em importados-do-celular.
        self.assertFalse(arquivo.exists())
        self.assertTrue((self.drive / entradas_celular.PASTA_IMPORTADOS / arquivo.name).exists())
        # Se a sincronização trouxer o arquivo de volta, ele não entra de novo.
        shutil.copy(copia, arquivo)
        self.assertEqual(entradas_celular.procurar(self.banco), ([], []))
        self.assertFalse(arquivo.exists())
        self.assertEqual(len(self.banco.listar()), 1)

    def test_conta_pelo_nome_quando_o_numero_nao_existe(self):
        encontradas, _ = entradas_celular.conferir(self.banco, [self.arquivo(entrada(conta_id=999, conta='Lilian'))])
        self.assertEqual(entradas_celular.importar(self.banco, encontradas), (1, []))
        self.assertEqual(self.banco.listar()[0]['conta'], 'Lilian')

    def test_regras_do_formulario_valem_para_o_celular(self):
        casos = {
            'custo maior que o total': entrada(conta_id=self.vitor, custo=900000),
            'aquisição no futuro': entrada(conta_id=self.vitor, aquisicao='2099-01-01', previsao='2099-02-01'),
            'conta que não existe': entrada(conta_id=999, conta='Ninguém'),
        }
        ativa = self.banco.salvar_conta(dados_conta(identificacao='Desativada'))
        self.banco.ativar_conta(ativa, False)
        casos['conta desativada'] = entrada(conta_id=ativa, conta='Desativada')
        arquivos = [self.arquivo(dados) for dados in casos.values()]
        encontradas, _ = entradas_celular.conferir(self.banco, arquivos)
        gravadas, recusadas = entradas_celular.importar(self.banco, encontradas)
        self.assertEqual(gravadas, 0)
        mensagens = '\n'.join(m for _, m in recusadas)
        for trecho in ('não pode superar', 'futuro', 'conta cadastrada', 'desativada'):
            self.assertIn(trecho, mensagens)
        # Recusadas continuam na pasta e não contam como importadas: dá para corrigir e tentar de novo.
        self.assertTrue(all(a.exists() for a in arquivos))
        self.assertEqual(entradas_celular.importadas(self.banco), set())

    def test_arquivos_que_nao_abrem(self):
        dados = entrada(conta_id=self.vitor)
        outra_senha = self.arquivo(dados, senha='outra senha qualquer 1', nome='outra.rpvcelular')
        formato = self.arquivo(dados, nome='formato.rpvcelular', pacote={'formato': 'outro', 'versao_formato': 1})
        incompleto = self.arquivo(dados, nome='incompleto.rpvcelular', pacote={
            'formato': 'gestor-rpv-celular', 'versao_formato': 1, 'entrada': {k: v for k, v in dados.items() if k != 'nome'}})
        tipo = self.arquivo(dados, nome='tipo.rpvcelular', pacote={
            'formato': 'gestor-rpv-celular', 'versao_formato': 1, 'entrada': dict(dados, custo='5000')})
        solto = self.drive / 'solto.rpvcelular'
        solto.write_bytes(b'nao sou cifrado')
        encontradas, problemas = entradas_celular.procurar(self.banco)
        self.assertEqual(encontradas, [])
        mensagens = {a.name: m for a, m in problemas}
        self.assertIn('outra senha', mensagens[outra_senha.name])
        self.assertIn('não reconhecido', mensagens[formato.name])
        self.assertIn('incompleto', mensagens[incompleto.name])
        self.assertIn('incompleto', mensagens[tipo.name])
        self.assertIn('não é uma entrada', mensagens[solto.name])

    def conta_do_celular(self, **valores):
        dados = dict(dados_conta(identificacao='nubank da lilian', nome='Lilian Teste', cpf='529.982.247-25',
                                 numero='999-1', pix='lilian@example.com'), id=str(uuid.uuid4()),
                     criada_em='2026-10-28T10:00:00-03:00')
        dados.update(valores)
        return dados

    def pacote_conta(self, conta):
        return self.arquivo(conta, nome=f'conta-{conta["id"][:8]}.rpvcelular',
                            pacote={'formato': 'gestor-rpv-celular', 'versao_formato': 1, 'conta': conta})

    def test_conta_e_entrada_com_a_conta_nova_no_mesmo_lote(self):
        conta = self.conta_do_celular()
        # A entrada só conhece a conta pelo nome (ela ainda não existia no computador quando foi feita).
        entrada_nova = entrada(conta_id=-1, conta='nubank da lilian', nome='Com Conta Nova')
        arquivos = [self.arquivo(entrada_nova), self.pacote_conta(conta)]  # Entrada antes, de propósito.
        encontradas, problemas = entradas_celular.conferir(self.banco, arquivos)
        self.assertEqual(problemas, [])
        self.assertEqual(entradas_celular.contar(encontradas), '1 entrada e 1 conta de recebimento')
        self.assertEqual(entradas_celular.importar(self.banco, encontradas), (2, []))
        nova = next(c for c in self.banco.contas() if c['identificacao'] == 'Nubank da lilian')
        self.assertEqual((nova['nome'], nova['cpf'], nova['pix']), ('Lilian Teste', '52998224725', 'lilian@example.com'))
        self.assertEqual(self.banco.listar()[0]['conta_id'], nova['id'])
        self.assertEqual(entradas_celular.importadas(self.banco), {conta['id'], entrada_nova['id']})

    def test_regras_da_conta_valem_para_o_celular(self):
        self.banco.salvar_conta(dados_conta(identificacao='Já existe', pix='repetido@example.com'))
        casos = [self.conta_do_celular(cpf='111.111.111-11'),
                 self.conta_do_celular(identificacao='já EXISTE', numero='1'),
                 self.conta_do_celular(identificacao='Outra', numero='2', pix='repetido@example.com')]
        encontradas, _ = entradas_celular.conferir(self.banco, [self.pacote_conta(c) for c in casos])
        gravadas, recusadas = entradas_celular.importar(self.banco, encontradas)
        self.assertEqual(gravadas, 0)
        mensagens = '\n'.join(m for _, m in recusadas)
        for trecho in ('CPF inválido', 'com essa identificação', 'chave Pix'):
            self.assertIn(trecho, mensagens)

    def test_pacote_com_dois_tipos_ou_campo_a_mais_e_recusado(self):
        conta = self.conta_do_celular()
        dois = self.arquivo(conta, nome='dois.rpvcelular', pacote={'formato': 'gestor-rpv-celular', 'versao_formato': 1,
                                                                  'conta': conta, 'entrada': entrada()})
        a_mais = self.arquivo(conta, nome='mais.rpvcelular', pacote={'formato': 'gestor-rpv-celular', 'versao_formato': 1,
                                                                    'conta': dict(conta, ativa=True)})
        _, problemas = entradas_celular.conferir(self.banco, [dois, a_mais])
        self.assertEqual([m for _, m in problemas], ['O arquivo do celular está incompleto.'] * 2)

    # ---- Mudanças em operações que já existem -----------------------------------------------------------
    def mudanca(self, tipo, operacao, **valores):
        """Arquivo de mudança como o app grava, com o nome do titular e os valores que o celular via."""
        dados = dict(id=str(uuid.uuid4()), operacao_id=operacao, nome=self.banco.obter(operacao)['nome'],
                     criada_em='2026-10-29T10:00:00-03:00', **valores)
        return self.arquivo(dados, nome=f'{tipo}-{dados["id"][:8]}.rpvcelular',
                            pacote={'formato': 'gestor-rpv-celular', 'versao_formato': 1, tipo: dados})

    def campos(self, operacao):
        return {k: self.banco.obter(operacao)[k] for k in EDITAVEIS}

    def importar_tudo(self):
        encontradas, problemas = entradas_celular.procurar(self.banco)
        self.assertEqual(problemas, [])
        return entradas_celular.importar(self.banco, encontradas)

    def test_alteracao_grava_so_o_que_o_celular_mudou(self):
        rpv = self.banco.salvar(dados_rpv(aquisicao='2026-10-01'))
        antes = self.campos(rpv)
        depois = dict(antes, previsto=2500000, previsao='2027-01-15', observacoes='corrigido no celular')
        self.mudanca('alteracao', rpv, antes=antes, depois=depois)
        # Enquanto isso, no computador, outro campo mudou: os dois ficam.
        self.banco.salvar(dict(dados_rpv(aquisicao='2026-10-01'), comissao=30000), rpv)
        encontradas, _ = entradas_celular.procurar(self.banco)
        self.assertEqual(entradas_celular.resumo(encontradas[0][1]),
                         'Alteração em Pessoa De Teste — Valor Total RPV, previsão inicial, observações')
        self.assertEqual(entradas_celular.importar(self.banco, encontradas), (1, []))
        registro = self.banco.obter(rpv)
        self.assertEqual((registro['previsto'], registro['previsao'], registro['observacoes'], registro['comissao']),
                         (2500000, '2027-01-15', 'Corrigido no celular', 30000))

    def test_alteracao_que_conflita_com_o_computador_nao_e_aplicada(self):
        rpv = self.banco.salvar(dados_rpv(aquisicao='2026-10-01'))
        antes = self.campos(rpv)
        arquivo = self.mudanca('alteracao', rpv, antes=antes, depois=dict(antes, previsto=2500000))
        self.banco.salvar(dict(dados_rpv(aquisicao='2026-10-01'), previsto=3000000), rpv)
        gravadas, recusadas = self.importar_tudo()
        self.assertEqual(gravadas, 0)
        self.assertIn('Alterada no computador', recusadas[0][1])
        self.assertIn('Valor Total RPV', recusadas[0][1])
        self.assertEqual(self.banco.obter(rpv)['previsto'], 3000000)
        # Não tem como dar certo depois: sai da pasta e não é perguntada de novo.
        self.assertFalse(arquivo.exists())
        self.assertEqual(entradas_celular.procurar(self.banco), ([], []))

    def test_alteracao_troca_de_conta_e_regras_do_formulario(self):
        rpv = self.banco.salvar(dados_rpv(aquisicao='2026-10-01'))
        antes = self.campos(rpv)
        lilian = next(c['id'] for c in self.banco.contas() if c['identificacao'] == 'Lilian')
        self.mudanca('alteracao', rpv, antes=antes, depois=dict(antes, conta_id=lilian, conta='Lilian'))
        outra = self.banco.salvar(dados_rpv(aquisicao='2026-10-01'))
        antes_outra = self.campos(outra)
        self.mudanca('alteracao', outra, antes=antes_outra, depois=dict(antes_outra, custo=9999999))
        gravadas, recusadas = self.importar_tudo()
        self.assertEqual(gravadas, 1)
        self.assertEqual(self.banco.obter(rpv)['conta_id'], lilian)
        self.assertIn('não pode superar', recusadas[0][1])

    def test_nova_previsao_entra_no_historico(self):
        rpv = self.banco.salvar(dados_rpv(aquisicao='2026-10-01', previsao='2026-12-20'))
        self.mudanca('previsao', rpv, anterior='2026-12-20', nova='2027-02-10')
        outra = self.banco.salvar(dados_rpv(aquisicao='2026-10-01', previsao='2026-12-20'))
        self.mudanca('previsao', outra, anterior='2026-12-20', nova='2027-03-01')
        self.banco.atualizar_previsao(outra, '2027-01-05')  # Mudou no computador depois do backup.
        gravadas, recusadas = self.importar_tudo()
        self.assertEqual(gravadas, 1)
        self.assertEqual(self.banco.obter(rpv)['previsao_atual'], '2027-02-10')
        self.assertEqual(self.banco.historico_previsoes(rpv)[0]['anterior'], '2026-12-20')
        self.assertIn('05/01/2027', recusadas[0][1])
        self.assertEqual(self.banco.obter(outra)['previsao_atual'], '2027-01-05')

    def test_exclusao_vai_para_a_lixeira(self):
        rpv = self.banco.salvar(dados_rpv(aquisicao='2026-10-01'))
        self.mudanca('exclusao', rpv)
        encontradas, _ = entradas_celular.procurar(self.banco)
        self.assertEqual(entradas_celular.resumo(encontradas[0][1]), 'Excluir Pessoa De Teste (vai para a lixeira)')
        self.assertEqual(entradas_celular.importar(self.banco, encontradas), (1, []))
        self.assertTrue(self.banco.obter(rpv)['lixeira_em'])

    def test_documento_anexado_no_celular(self):
        rpv = self.banco.salvar(dados_rpv(aquisicao='2026-10-01'))
        conteudo = base64.b64encode(PNG_1X1).decode()
        self.mudanca('anexo', rpv, arquivo='Foto do ofício.png', conteudo=conteudo)
        self.mudanca('anexo', rpv, arquivo='..\\..\\pasta/escondido.jpg', conteudo=conteudo)
        self.mudanca('anexo', rpv, arquivo='programa.exe', conteudo=conteudo)
        encontradas, problemas = entradas_celular.procurar(self.banco)
        self.assertIn('não é PDF nem imagem', problemas[0][1])
        self.assertEqual(entradas_celular.contar(encontradas), '2 documentos')
        self.assertEqual(entradas_celular.importar(self.banco, encontradas), (2, []))
        documentos = self.banco.documentos(rpv)
        self.assertEqual(sorted(d['nome'] for d in documentos), ['Foto do ofício.png', 'escondido.jpg'])
        self.assertTrue(all(self.banco.caminho_documento(d['id']).read_bytes() == PNG_1X1 for d in documentos))

    def test_entrada_nova_com_documentos(self):
        dados = entrada(conta_id=self.vitor, anexos=[
            {'arquivo': 'Contrato.pdf', 'conteudo': base64.b64encode(b'%PDF-1.4 teste').decode()},
            {'arquivo': 'Contrato.pdf', 'conteudo': base64.b64encode(b'%PDF-1.4 outro').decode()}])
        self.arquivo(dados)
        encontradas, _ = entradas_celular.procurar(self.banco)
        self.assertTrue(entradas_celular.resumo(encontradas[0][1]).endswith('— 2 documentos'))
        self.assertEqual(entradas_celular.importar(self.banco, encontradas), (1, []))
        rpv = self.banco.listar()[0]['id']
        self.assertEqual([self.banco.caminho_documento(d['id']).read_bytes() for d in self.banco.documentos(rpv)],
                         [b'%PDF-1.4 teste', b'%PDF-1.4 outro'])

    def test_mudanca_em_operacao_que_saiu_da_lista(self):
        rpv = self.banco.salvar(dados_rpv(aquisicao='2026-10-01'))
        self.mudanca('previsao', rpv, anterior='2026-12-20', nova='2027-02-10')
        self.mudanca('exclusao', rpv)
        self.banco.excluir(rpv)
        gravadas, recusadas = self.importar_tudo()
        # A exclusão já estava feita (conta como aplicada); a previsão é recusada com aviso.
        self.assertEqual(gravadas, 1)
        self.assertIn('não está mais na lista ativa', recusadas[0][1])

    def test_mudanca_com_campos_errados_e_recusada(self):
        rpv = self.banco.salvar(dados_rpv(aquisicao='2026-10-01'))
        antes = self.campos(rpv)
        self.mudanca('alteracao', rpv, antes=antes, depois={k: v for k, v in antes.items() if k != 'nome'})
        self.mudanca('anexo', rpv, arquivo='a.png', conteudo='isto não é base64!')
        _, problemas = entradas_celular.procurar(self.banco)
        self.assertEqual(sorted(m for _, m in problemas), ['O arquivo do celular está incompleto.',
                                                           'Um documento do arquivo do celular está ilegível.'])

    def test_sem_pasta_do_backup_automatico_nao_procura(self):
        self.banco.remover_configuracao(PASTA_AUTOMATICA)
        self.arquivo(entrada(conta_id=self.vitor))
        self.assertEqual(entradas_celular.procurar(self.banco), ([], []))


if __name__ == '__main__':
    unittest.main()
