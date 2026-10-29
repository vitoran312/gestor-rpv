// Visualizador dos anexos: PDF desenhado pelo pdf.js (o quadro nativo do iPhone mostra a página em tamanho real,
// sem ajustar à tela) e imagens, os dois começando na largura da tela, com botões de zoom.
//
// Só as páginas perto da parte visível são desenhadas; as que se afastam são apagadas, para PDFs longos não
// esgotarem a memória do celular.
'use strict';

const Visualizador = (() => {
  const ZOOMS = [1, 1.5, 2, 3, 4];
  const MAX_PIXELS = 8 * 1024 * 1024;  // Por página desenhada; o Safari recusa telas (canvas) muito grandes.
  let biblioteca = null;

  function pdfjs() {
    biblioteca = biblioteca || import('./vendor/pdfjs/pdf.min.mjs').then((modulo) => {
      modulo.GlobalWorkerOptions.workerSrc = 'vendor/pdfjs/pdf.worker.min.mjs';
      return modulo;
    });
    return biblioteca;
  }

  function botao(texto, rotulo, aoTocar) {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = texto;
    b.setAttribute('aria-label', rotulo);
    b.addEventListener('click', aoTocar);
    return b;
  }

  // Barra com − / porcentagem / + / Ajustar. Chama aoMudar(fator) a cada troca.
  function barraDeZoom(aoMudar) {
    let indice = 0;
    let primeira = true;
    const barra = document.createElement('div');
    barra.className = 'zoom';
    const valor = document.createElement('span');
    const atualizar = () => {
      valor.textContent = indice === 0 ? 'Página inteira' : `${Math.round(ZOOMS[indice] * 100)}%`;
      menos.disabled = indice === 0;
      mais.disabled = indice === ZOOMS.length - 1;
      ajustar.disabled = indice === 0;
      aoMudar(ZOOMS[indice], primeira);
      primeira = false;
    };
    const menos = botao('−', 'Diminuir o zoom', () => { indice = Math.max(0, indice - 1); atualizar(); });
    const mais = botao('+', 'Aumentar o zoom', () => { indice = Math.min(ZOOMS.length - 1, indice + 1); atualizar(); });
    const ajustar = botao('Ajustar', 'Ajustar à largura da tela', () => { indice = 0; atualizar(); });
    barra.append(menos, valor, mais, ajustar);
    return { barra, iniciar: atualizar };
  }

  // Mantém o mesmo ponto do documento no meio da tela depois de trocar o zoom.
  function preservarPosicao(rolagem, mudar) {
    const antes = rolagem.getBoundingClientRect();
    const meio = window.innerHeight / 2;
    const fracaoY = (meio - antes.top) / Math.max(1, antes.height);
    const fracaoX = (rolagem.scrollLeft + rolagem.clientWidth / 2) / Math.max(1, rolagem.scrollWidth);
    mudar();
    const depois = rolagem.getBoundingClientRect();
    window.scrollBy(0, depois.top + fracaoY * depois.height - meio);
    rolagem.scrollLeft = fracaoX * rolagem.scrollWidth - rolagem.clientWidth / 2;
  }

  async function pdf(bytes, area) {
    const lib = await pdfjs();
    const documento = await lib.getDocument({
      data: bytes.slice(), isEvalSupported: false, disableAutoFetch: true,
      standardFontDataUrl: 'vendor/pdfjs/standard_fonts/',
    }).promise;
    const paginas = [];
    for (let numero = 1; numero <= documento.numPages; numero += 1) {
      paginas.push(await documento.getPage(numero));
    }
    const rolagem = document.createElement('div');
    rolagem.className = 'paginas';
    let zoom = 1;
    const quadros = paginas.map((pagina, i) => {
      const caixa = document.createElement('div');
      caixa.className = 'pagina';
      const tela = document.createElement('canvas');
      const legenda = document.createElement('div');
      legenda.className = 'legenda-pagina';
      legenda.textContent = `Página ${i + 1} de ${paginas.length}`;
      caixa.append(tela, legenda);
      rolagem.append(caixa);
      return { pagina, caixa, tela, desenhada: 0, tarefa: null, visivel: false };
    });

    const larguraBase = () => Math.max(200, area.clientWidth);

    function dimensionar() {
      for (const q of quadros) {
        const original = q.pagina.getViewport({ scale: 1 });
        const largura = larguraBase() * zoom;
        q.caixa.style.width = `${largura}px`;
        q.tela.style.width = `${largura}px`;
        q.tela.style.height = `${largura * original.height / original.width}px`;
      }
    }

    function apagar(q) {
      if (q.tarefa) {
        q.tarefa.cancel();
        q.tarefa = null;
      }
      q.tela.width = 0;
      q.tela.height = 0;
      q.desenhada = 0;
    }

    function desenhar(q) {
      if (q.desenhada === zoom) {
        return;
      }
      if (q.tarefa) {
        q.tarefa.cancel();
      }
      const original = q.pagina.getViewport({ scale: 1 });
      const largura = larguraBase() * zoom;
      let escala = largura / original.width * Math.min(window.devicePixelRatio || 1, 3);
      const pixels = original.width * original.height * escala * escala;
      if (pixels > MAX_PIXELS) {
        escala *= Math.sqrt(MAX_PIXELS / pixels);
      }
      const vista = q.pagina.getViewport({ scale: escala });
      q.tela.width = Math.floor(vista.width);
      q.tela.height = Math.floor(vista.height);
      const zoomDesenhado = zoom;
      q.tarefa = q.pagina.render({ canvasContext: q.tela.getContext('2d'), viewport: vista });
      q.tela.dataset.pronta = '';
      q.tarefa.promise.then(() => {
        q.desenhada = zoomDesenhado;
        q.tarefa = null;
        q.tela.dataset.pronta = String(zoomDesenhado);  // Página terminada neste zoom (usado pelos testes).
      }).catch(() => {});  // Cancelada por um novo zoom ou por sair da tela.
    }

    const observador = new IntersectionObserver((entradas) => {
      for (const entrada of entradas) {
        const q = quadros.find((x) => x.caixa === entrada.target);
        q.visivel = entrada.isIntersecting;
        if (q.visivel) {
          desenhar(q);
        } else {
          apagar(q);
        }
      }
    }, { rootMargin: '800px 0px' });

    const { barra, iniciar } = barraDeZoom((fator, primeira) => {
      const mudar = () => {
        zoom = fator;
        dimensionar();
      };
      // Ao abrir, o documento começa do topo; nas trocas de zoom, o mesmo trecho continua no meio da tela.
      if (primeira) {
        mudar();
      } else {
        preservarPosicao(rolagem, mudar);
      }
      quadros.filter((q) => q.visivel).forEach(desenhar);
    });
    area.replaceChildren(barra, rolagem);
    iniciar();
    quadros.forEach((q) => observador.observe(q.caixa));
    return () => {
      observador.disconnect();
      quadros.forEach(apagar);
      documento.destroy();
    };
  }

  function imagem(endereco, nome, area) {
    const rolagem = document.createElement('div');
    rolagem.className = 'paginas';
    const img = document.createElement('img');
    img.className = 'documento-imagem';
    img.src = endereco;
    img.alt = nome;
    rolagem.append(img);
    const { barra, iniciar } = barraDeZoom((fator, primeira) => {
      const mudar = () => {
        img.style.width = `${Math.max(200, area.clientWidth) * fator}px`;
      };
      if (primeira) {
        mudar();
      } else {
        preservarPosicao(rolagem, mudar);
      }
    });
    area.replaceChildren(barra, rolagem);
    iniciar();
    return () => {};
  }

  return { pdf, imagem };
})();
