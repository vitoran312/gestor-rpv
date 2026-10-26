"""Gera as folhas de imagens das placas de vidro da tela inicial (recursos/vidro-claro.png e vidro-escuro.png).

Só é usado no desenvolvimento, com Pillow; o programa apenas lê os PNGs prontos. Cada folha tem, por placa,
uma linha de vidro (preenchimento e borda fina) e uma linha de brilho (borda desfocada), em NIVEIS colunas
de opacidade crescente. O fade-in troca de coluna; o deslocamento move as imagens no Canvas.
Uso: python scripts/gerar_arte_vidro.py
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

RAIZ = Path(__file__).resolve().parent.parent
LARGURA, ALTURA = 136, 164  # Célula de cada placa, com margem para o brilho desfocado.
NIVEIS = 6
AMOSTRAGEM = 4             # Desenho em 4x e redução, para bordas suaves.
MARGEM = 14

# Do fundo para a frente: inclinação, opacidade do vidro (topo, base), opacidade da borda e do brilho.
PLACAS = (
    dict(queda=0.16, vidro=(0.10, 0.03), borda=0.30, brilho=0.10),
    dict(queda=0.15, vidro=(0.13, 0.04), borda=0.42, brilho=0.14),
    dict(queda=0.14, vidro=(0.16, 0.05), borda=0.60, brilho=0.20),
    dict(queda=0.13, vidro=(0.22, 0.07), borda=0.95, brilho=0.34),
)
CORES = {'escuro': (255, 165, 134), 'claro': (140, 29, 52)}  # Pêssego e carmim da paleta Vitoran Pro.
INTENSIDADE = {'escuro': 1.0, 'claro': 0.75}                   # No claro, o vidro escuro pesaria demais.


def contorno(queda):
    """Quadrilátero inclinado, como uma placa vista em perspectiva, dentro da margem da célula."""
    s = AMOSTRAGEM
    x0, x1 = MARGEM * s, (LARGURA - MARGEM) * s
    y0, y1 = MARGEM * s, (ALTURA - MARGEM) * s
    altura = y1 - y0
    return [(x0, y0 + queda * altura), (x1, y0), (x1, y1), (x0, y1 - queda * altura * 0.4)]


def mascara_arredondada(pontos, raio):
    """Polígono com cantos arredondados: desfocar e cortar no meio arredonda os cantos convexos."""
    s = AMOSTRAGEM
    base = Image.new('L', (LARGURA * s, ALTURA * s), 0)
    ImageDraw.Draw(base).polygon(pontos, fill=255)
    return base.filter(ImageFilter.GaussianBlur(raio / 2)).point(lambda v: 255 if v >= 128 else 0)


def placa(cor, config, intensidade):
    s = AMOSTRAGEM
    pontos = contorno(config['queda'])
    forma = mascara_arredondada(pontos, 10 * s)
    # Vidro: gradiente vertical, mais aceso no alto, como luz refletida.
    topo, base = (v * intensidade for v in config['vidro'])
    gradiente = Image.linear_gradient('L').resize(forma.size)
    gradiente = gradiente.point(lambda v: round(255 * (topo + (base - topo) * v / 255)))
    alfa_vidro = ImageChops.multiply(forma, gradiente)
    # Borda: anel de 1,5 px na beirada da forma.
    interno = forma.filter(ImageFilter.MinFilter(2 * s + 1))
    anel = ImageChops.subtract(forma, interno)
    alfa_borda = anel.point(lambda v: round(v * config['borda'] * intensidade))
    alfa = ImageChops.lighter(alfa_vidro, alfa_borda)
    vidro = Image.new('RGBA', forma.size, cor + (0,))
    vidro.putalpha(alfa)
    vidro = vidro.resize((LARGURA, ALTURA), Image.LANCZOS)
    # Brilho: o mesmo anel, desfocado, aparece depois do vidro.
    halo = anel.resize((LARGURA, ALTURA), Image.LANCZOS).filter(ImageFilter.GaussianBlur(5))
    halo = halo.point(lambda v: min(255, round(v * 3.2 * config['brilho'] * intensidade)))
    brilho = Image.new('RGBA', (LARGURA, ALTURA), cor + (0,))
    brilho.putalpha(halo)
    return vidro, brilho


def com_opacidade(imagem, fracao):
    copia = imagem.copy()
    copia.putalpha(imagem.getchannel('A').point(lambda v: round(v * fracao)))
    return copia


def gerar():
    for tema, cor in CORES.items():
        folha = Image.new('RGBA', (LARGURA * NIVEIS, ALTURA * 2 * len(PLACAS)), (0, 0, 0, 0))
        for indice, config in enumerate(PLACAS):
            for camada, imagem in enumerate(placa(cor, config, INTENSIDADE[tema])):
                for nivel in range(NIVEIS):
                    folha.paste(com_opacidade(imagem, (nivel + 1) / NIVEIS),
                                (nivel * LARGURA, (indice * 2 + camada) * ALTURA))
        destino = RAIZ / 'recursos' / f'vidro-{tema}.png'
        folha.save(destino, optimize=True)
        print(destino, destino.stat().st_size, 'bytes')


if __name__ == '__main__':
    gerar()
