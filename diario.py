"""Diário de ocorrências em arquivo (gestor.log, na pasta dos dados).

Falhas que a interface contorna sem incomodar a pessoa — tema que não foi gravado, backup antigo que não
pôde ser apagado, erro inesperado num botão — ficam anotadas aqui para quem for investigar depois.
No executável não há console, então sem este arquivo esses erros sumiriam.
"""
import logging
from logging.handlers import RotatingFileHandler

log = logging.getLogger('gestor')
log.addHandler(logging.NullHandler())  # Sem ativar (nos testes, por exemplo), nada é escrito.


def ativar(pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = RotatingFileHandler(pasta / 'gestor.log', maxBytes=512 * 1024, backupCount=2, encoding='utf-8')
    arquivo.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    log.addHandler(arquivo)
    log.setLevel(logging.INFO)


def erro_na_interface(tipo, valor, rastro):
    """Para Tk.report_callback_exception: anota erros não tratados dos botões e eventos."""
    log.error('Erro não tratado na interface', exc_info=(tipo, valor, rastro))
