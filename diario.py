"""Diário de ocorrências em arquivo (gestor.log, na pasta dos dados).

Falhas que a interface contorna sem incomodar a pessoa — tema que não foi gravado, backup antigo que não
pôde ser apagado, erro inesperado num botão — ficam anotadas aqui para quem for investigar depois.
No executável não há console, então sem este arquivo esses erros sumiriam.
"""
import logging
import traceback
from logging.handlers import RotatingFileHandler

log = logging.getLogger('gestor')
log.addHandler(logging.NullHandler())  # Sem ativar (nos testes, por exemplo), nada é escrito.


class FormatoSemDados(logging.Formatter):
    """Erros entram só com o tipo, o código e as linhas do programa: a mensagem de uma exceção pode trazer o que
    a pessoa digitou ou caminhos com o nome dela (pasta do usuário, pasta do OneDrive)."""

    def formatException(self, informacao):
        tipo, valor, rastro = informacao
        codigo = getattr(valor, 'errno', None)
        cabecalho = tipo.__name__ + (f' (código {codigo})' if codigo is not None else '')
        return cabecalho + '\n' + ''.join(traceback.format_tb(rastro)).rstrip()


def ativar(pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = RotatingFileHandler(pasta / 'gestor.log', maxBytes=512 * 1024, backupCount=2, encoding='utf-8')
    arquivo.setFormatter(FormatoSemDados('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    log.addHandler(arquivo)
    log.setLevel(logging.INFO)


def erro_na_interface(tipo, valor, rastro):
    """Para Tk.report_callback_exception: anota erros não tratados dos botões e eventos.

    Só o tipo do erro e as linhas do programa: a mensagem pode conter o que a pessoa digitou (nomes, CPFs).
    """
    log.error('Erro não tratado na interface.', exc_info=(tipo, valor, rastro))
