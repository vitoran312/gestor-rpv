"""Mensagens de erro do sistema em português, sem códigos técnicos nem caminhos temporários."""
import errno
import sqlite3

TEXTOS_OSERROR = {
    errno.ENOSPC: 'Não há espaço livre suficiente no disco.',
    errno.EACCES: 'Sem permissão para usar este local. Se o arquivo estiver aberto em outro programa, feche-o e tente de novo.',
    errno.EPERM: 'Sem permissão para usar este local. Se o arquivo estiver aberto em outro programa, feche-o e tente de novo.',
    errno.ENOENT: 'O arquivo ou a pasta não foi encontrado.',
    errno.EISDIR: 'O caminho escolhido é uma pasta, e não um arquivo.',
    errno.ENOTDIR: 'O caminho escolhido não é uma pasta.',
    errno.EEXIST: 'Já existe um arquivo com esse nome.',
    errno.ENAMETOOLONG: 'O nome do arquivo ou da pasta é longo demais.',
    errno.EINVAL: 'O nome do arquivo contém caracteres que o Windows não aceita.',
    errno.EROFS: 'Este local não permite gravar arquivos.',
}


def descrever_erro(erro):
    """Texto para mostrar ao usuário. ValueError já sai do aplicativo em português."""
    if isinstance(erro, ValueError):
        return str(erro)
    if isinstance(erro, sqlite3.Error):
        return 'Não foi possível acessar os dados do programa.'
    if isinstance(erro, OSError):
        texto = TEXTOS_OSERROR.get(erro.errno)
        if texto is None and getattr(erro, 'winerror', None) == 32:  # Arquivo em uso por outro programa.
            texto = TEXTOS_OSERROR[errno.EACCES]
        return texto or 'O sistema não permitiu acessar o arquivo ou a pasta.'
    return 'Ocorreu um erro inesperado.'
