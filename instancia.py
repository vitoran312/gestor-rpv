"""Uma só execução do programa por vez nos mesmos dados.

Duas janelas abertas ao mesmo tempo poderiam se atrapalhar: a segunda, ao abrir, trataria como interrompida a
importação que a primeira ainda está fazendo. A trava é um arquivo bloqueado na pasta dos dados; o sistema a
solta sozinho quando o programa fecha, inclusive à força, então nunca fica presa.
"""
import sys
from pathlib import Path

NOME = 'gestor.trava'
_travas = {}  # Mantém o arquivo aberto (e a trava valendo) enquanto o programa roda.


def travar(pasta):
    """True se esta execução ficou com a trava; False se outra já está aberta."""
    caminho = Path(pasta) / NOME
    if caminho in _travas:
        return True
    caminho.parent.mkdir(parents=True, exist_ok=True)
    arquivo = open(caminho, 'a+b')
    try:
        if sys.platform == 'win32':
            import msvcrt
            arquivo.seek(0)
            msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        arquivo.close()
        return False
    _travas[caminho] = arquivo
    return True


def soltar(pasta):
    """Solta a trava desta execução (o sistema também a solta sozinho quando o programa fecha)."""
    arquivo = _travas.pop(Path(pasta) / NOME, None)
    if arquivo is not None:
        arquivo.close()
