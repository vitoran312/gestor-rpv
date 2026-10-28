// Telas do app (só consulta). Os dados ficam só na memória desta página: fechar o app ou tocar em
// "Fechar dados" apaga tudo, e a próxima consulta abre o backup de novo.
//
// Todo texto vindo do backup entra na página por textContent (nunca como HTML).
'use strict';

(() => {
  const D = GestorDados;
  const $ = (id) => document.getElementById(id);
  const SITUACOES = { pendente: 'Pendente', atrasada: 'Atrasada', recebida: 'Recebida' };
  const FILTROS = [['todas', 'Todas'], ['pendente', 'Pendentes'], ['atrasada', 'Atrasadas'], ['recebida', 'Recebidas']];
  const ETAPAS = { senha: 'Conferindo a senha', decifrar: 'Abrindo o backup' };

  let dados = null;      // Conteúdo do backup aberto.
  let info = null;       // Arquivo, manifesto e tempos de abertura.
  const estado = { busca: '', filtro: 'todas' };

  // ---- Montagem de elementos ---------------------------------------------------------------------------
  function el(tag, atributos = {}, ...filhos) {
    const elemento = document.createElement(tag);
    for (const [nome, valor] of Object.entries(atributos)) {
      if (valor === undefined || valor === null || valor === false) {
        continue;
      }
      if (nome === 'texto') {
        elemento.textContent = valor;
      } else if (nome.startsWith('on')) {
        elemento.addEventListener(nome.slice(2), valor);
      } else {
        elemento.setAttribute(nome, valor === true ? '' : valor);
      }
    }
    elemento.append(...filhos.flat(Infinity).filter((f) => f !== null && f !== undefined && f !== false));
    return elemento;
  }

  function campos(pares) {
    return el('dl', { class: 'campos' }, pares.filter(([, valor]) => valor !== null && valor !== undefined && valor !== '')
      .map(([rotulo, valor, classe]) => [el('dt', { texto: rotulo }), el('dd', { texto: String(valor), class: classe })]));
  }

  function cartao(...filhos) {
    return el('div', { class: 'cartao' }, ...filhos);
  }

  function vazio(texto) {
    return el('p', { class: 'vazio', texto });
  }

  // ---- Abertura do backup ------------------------------------------------------------------------------
  function mostrarAndamento(texto, fracao) {
    $('andamento').hidden = false;
    $('andamento-texto').textContent = texto;
    $('andamento-barra').style.width = `${Math.round(fracao * 100)}%`;
  }

  $('formulario').addEventListener('submit', async (evento) => {
    evento.preventDefault();
    const arquivo = $('arquivo').files[0];
    $('erro').hidden = true;
    $('abrir').disabled = true;
    try {
      mostrarAndamento('Lendo o arquivo…', 0);
      const bytes = new Uint8Array(await arquivo.arrayBuffer());
      const leitura = await LeitorBackup.ler(bytes, $('senha').value, {
        // A senha leva alguns segundos de propósito (é o que impede tentativas em massa); a barra mostra o andamento.
        aoProgredir: (etapa, fracao) => mostrarAndamento(`${ETAPAS[etapa]}…`, etapa === 'senha' ? fracao * 0.9 : 0.9 + fracao * 0.1),
      });
      try {
        dados = D.carregar(leitura.db);
      } finally {
        leitura.db.close();
      }
      info = { arquivo: arquivo.name, tamanho: arquivo.size, manifesto: leitura.manifesto, cifrado: leitura.cifrado,
        tempos: leitura.tempos };
      $('senha').value = '';
      $('formulario').reset();
      $('andamento').hidden = true;
      $('abertura').hidden = true;
      $('aplicativo').hidden = false;
      if (location.hash === '#inicio') {
        desenhar();
      } else {
        location.hash = '#inicio';
      }
    } catch (erro) {
      $('andamento').hidden = true;
      $('erro').textContent = erro instanceof LeitorBackup.ErroBackup ? erro.message
        : 'Não foi possível abrir o backup neste aparelho: ' + (erro && erro.message ? erro.message : erro);
      $('erro').hidden = false;
    } finally {
      $('abrir').disabled = false;
    }
  });

  function fecharDados() {
    dados = null;
    info = null;
    estado.busca = '';
    estado.filtro = 'todas';
    $('tela').replaceChildren();
    $('aplicativo').hidden = true;
    $('abertura').hidden = false;
    history.replaceState(null, '', location.pathname);
  }

  // ---- Telas ---------------------------------------------------------------------------------------------
  function idadeDoBackup() {
    const criado = info.manifesto.criado_em;
    if (!criado) {
      return null;
    }
    const dias = Math.floor((Date.now() - new Date(criado).getTime()) / 86400000);
    return Number.isNaN(dias) ? null : dias;
  }

  function telaInicio() {
    const ind = D.indicadores(dados.operacoes);
    const totais = D.contarSituacoes(dados.operacoes);
    const dias = idadeDoBackup();
    const idade = dias === null ? '' : dias <= 0 ? ' (hoje)' : dias === 1 ? ' (ontem)' : ` (há ${dias} dias)`;
    const indicador = (rotulo, valor, classe) => el('div', { class: 'cartao indicador' },
      el('div', { class: 'rotulo', texto: rotulo }), el('div', { class: 'valor ' + (classe || ''), texto: valor }));
    const situacao = (chave, rotulo, classe) => el('a', { class: 'cartao', href: '#operacoes', onclick: () => {
      estado.filtro = chave;
      estado.busca = '';
    } }, el('div', { class: 'numero ' + (classe || ''), texto: String(totais[chave]) }),
    el('div', { class: 'discreto pequeno', texto: rotulo }));
    return [
      dados.demonstracao && el('p', { class: 'aviso', texto: 'Este backup tem dados de demonstração, com nomes e valores fictícios.' }),
      el('p', { class: 'discreto pequeno', texto: `Dados do backup de ${D.dataHora(info.manifesto.criado_em)}${idade}.` }),
      dias !== null && dias > 7 && el('p', { class: 'aviso', texto: 'Este backup tem mais de uma semana. Faça um backup novo no computador para ver os dados atuais.' }),
      el('div', { class: 'indicadores' },
        indicador('Registros', String(ind.registros)),
        indicador('Lucro previsto', D.reais(ind.previsto)),
        indicador('Capital investido em aberto', D.reais(ind.aberto)),
        indicador('Lucro realizado', D.reais(ind.realizado), 'verde')),
      el('h2', { texto: 'Situação das operações' }),
      el('div', { class: 'situacoes' },
        situacao('pendente', 'Pendentes'),
        situacao('atrasada', 'Atrasadas', totais.atrasada ? 'vermelho' : ''),
        situacao('recebida', 'Recebidas', 'verde')),
    ];
  }

  function itemOperacao(r, destino) {
    const s = D.situacao(r);
    const adiada = r.previsao_atual > r.previsao;
    return el('a', { class: `cartao item ${s}`, href: destino },
      el('div', { class: 'linha1' }, el('span', { class: 'nome', texto: r.nome }),
        el('span', { class: `selo ${s}`, texto: SITUACOES[s] })),
      el('div', { class: 'linha2' },
        el('span', { texto: D.reais(r.previsto) }),
        el('span', { class: 'discreto', texto: r.recebimento ? `Recebida em ${D.dataBr(r.recebimento)}`
          : `Previsão ${D.dataBr(r.previsao_atual)}${adiada ? ' (adiada)' : ''}` })),
      el('div', { class: 'linha2 discreto' },
        el('span', { texto: `Lucro ${D.reais(r.previsto - r.custo)}` }),
        el('span', { texto: `Aquisição ${D.dataBr(r.aquisicao)}` })));
  }

  function telaOperacoes() {
    const lista = el('div', { class: 'lista' });
    const filtros = el('div', { class: 'filtros' });
    const desenharLista = () => {
      const encontrados = D.filtrar(dados.operacoes, estado.busca);
      const totais = D.contarSituacoes(encontrados);
      filtros.replaceChildren(...FILTROS.map(([chave, rotulo]) => el('button', {
        type: 'button', class: chave === estado.filtro ? 'ativo' : '', texto: `${rotulo} ${totais[chave]}`,
        onclick: () => {
          estado.filtro = chave;
          desenharLista();
        } })));
      const visiveis = estado.filtro === 'todas' ? encontrados : encontrados.filter((r) => D.situacao(r) === estado.filtro);
      lista.replaceChildren(...(visiveis.length ? visiveis.map((r) => itemOperacao(r, `#operacao/${r.id}`))
        : [vazio(estado.busca ? 'Nenhuma operação encontrada.' : 'Nenhuma operação nesta situação.')]));
    };
    const busca = el('input', { class: 'busca', type: 'search', placeholder: 'Buscar nome, conta ou data',
      value: estado.busca, autocomplete: 'off', oninput: (e) => {
        estado.busca = e.target.value;
        desenharLista();
      } });
    desenharLista();
    return [busca, filtros, lista];
  }

  function telaOperacao(id) {
    const r = dados.operacoes.find((o) => o.id === id) || dados.lixeira.find((o) => o.id === id);
    if (!r) {
      return [vazio('Operação não encontrada neste backup.')];
    }
    const s = D.situacao(r);
    const conta = D.contaDaOperacao(r);
    const historico = dados.historico.get(id) || [];
    const prorrogacoes = dados.prorrogacoes.get(id) || [];
    const documentos = dados.documentos.get(id) || [];
    return [
      r.lixeira_em && el('p', { class: 'aviso', texto: `Na lixeira desde ${D.dataHora(r.lixeira_em)}.` }),
      cartao(campos([
        ['Situação', SITUACOES[s], s === 'atrasada' ? 'vermelho' : s === 'recebida' ? 'verde' : ''],
        ['Titular original', r.nome],
        ['Data de aquisição', D.dataBr(r.aquisicao)],
        ['Valor de aquisição', D.reais(r.custo)],
        ['Comissão', D.reais(r.comissao || 0)],
        ['Valor total RPV', D.reais(r.previsto)],
        ['Lucro previsto', D.reais(r.previsto - r.custo)],
        ['Previsão inicial', D.dataBr(r.previsao)],
        ['Previsão atual', D.dataBr(r.previsao_atual)],
        ['Recebido em', r.recebimento ? D.dataBr(r.recebimento) : 'Não recebido'],
      ])),
      el('h2', { texto: 'Conta de destino' }),
      cartao(campos([['Conta', r.conta], ...Object.entries(D.TITULOS_CONTA)
        .filter(([chave]) => chave !== 'identificacao')
        .map(([chave, rotulo]) => [rotulo, chave === 'cpf' ? D.cpf(conta[chave]) : conta[chave]])])),
      r.observacoes && [el('h2', { texto: 'Observações' }), cartao(el('div', { class: 'observacoes', texto: r.observacoes }))],
      el('h2', { texto: 'Histórico da previsão' }),
      historico.length || prorrogacoes.length
        ? cartao(campos([
          ...historico.map((h) => [D.dataHora(h.alterada_em), `${D.dataBr(h.anterior)} → ${D.dataBr(h.nova)}`]),
          ...prorrogacoes.map((p) => [`Prorrogação (${D.dataHora(p.criada_em)})`, D.dataBr(p.data)]),
        ]))
        : el('p', { class: 'discreto', texto: 'A previsão nunca foi alterada.' }),
      el('h2', { texto: 'Documentos' }),
      documentos.length
        ? cartao(campos(documentos.map((d) => [d.tipo === 'recebimento' ? 'Comprovante' : 'Documento', d.nome])),
          el('p', { class: 'discreto pequeno', texto: 'Abrir os documentos no celular será a próxima etapa.' }))
        : el('p', { class: 'discreto', texto: 'Nenhum documento anexado.' }),
    ];
  }

  function telaContas() {
    if (!dados.contas.length) {
      return [vazio('Nenhuma conta cadastrada.')];
    }
    return [el('div', { class: 'lista' }, dados.contas.map((c) => {
      const usos = dados.operacoes.filter((r) => r.conta_id === c.id).length;
      return cartao(
        el('div', { class: 'linha1' }, el('span', { class: 'nome', texto: c.identificacao }),
          el('span', { class: 'selo ' + (c.ativa ? 'recebida' : 'pendente'), texto: c.ativa ? 'Ativa' : 'Desativada' })),
        el('p', { class: 'discreto pequeno', texto: usos === 1 ? '1 operação usa esta conta.' : `${usos} operações usam esta conta.` }),
        campos(Object.entries(D.TITULOS_CONTA).filter(([chave]) => chave !== 'identificacao')
          .map(([chave, rotulo]) => [rotulo, chave === 'cpf' ? D.cpf(c[chave]) : c[chave]])));
    }))];
  }

  function telaLixeira() {
    if (!dados.lixeira.length) {
      return [vazio('A lixeira está vazia.')];
    }
    return [el('p', { class: 'discreto pequeno', texto: 'Operações excluídas no computador. Para restaurar, use o programa no computador.' }),
      el('div', { class: 'lista' }, dados.lixeira.map((r) => itemOperacao(r, `#operacao/${r.id}`)))];
  }

  function grafico(resumo) {
    const largura = 360;
    const altura = 200;
    const base = 170;
    const topo = 20;
    const maior = Math.max(1, ...resumo.flatMap(([, e, r]) => [e, r]));
    const grupo = largura / resumo.length;
    const barra = Math.min(12, grupo * 0.32);
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    const novo = (tag, atributos, texto) => {
      const elemento = document.createElementNS('http://www.w3.org/2000/svg', tag);
      Object.entries(atributos).forEach(([n, v]) => elemento.setAttribute(n, v));
      if (texto !== undefined) {
        elemento.textContent = texto;
      }
      return elemento;
    };
    svg.setAttribute('viewBox', `0 0 ${largura} ${altura}`);
    svg.setAttribute('class', 'grafico');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Entradas e recebimentos dos últimos 12 meses');
    svg.append(novo('line', { x1: 0, x2: largura, y1: base, y2: base, class: 'eixo' }));
    resumo.forEach(([chave, entradas, recebidas], i) => {
      const centro = grupo * (i + 0.5);
      [[entradas, 'entradas', -barra - 1], [recebidas, 'recebidas', 1]].forEach(([valor, classe, deslocamento]) => {
        if (!valor) {
          return;
        }
        const h = (base - topo) * valor / maior;
        svg.append(novo('rect', { x: centro + deslocamento, y: base - h, width: barra, height: h, rx: 2, class: classe }));
        svg.append(novo('text', { x: centro + deslocamento + barra / 2, y: base - h - 4, 'text-anchor': 'middle' }, String(valor)));
      });
      svg.append(novo('text', { x: centro, y: base + 16, 'text-anchor': 'middle' }, D.rotuloMes(chave).split('/')[0]));
    });
    return svg;
  }

  function telaGrafico() {
    const resumo = D.resumoMensal(dados.operacoes);
    const entradas = resumo.reduce((t, [, e]) => t + e, 0);
    const recebidas = resumo.reduce((t, [, , r]) => t + r, 0);
    return [
      el('p', { class: 'discreto', texto: `Últimos 12 meses: ${D.quantidade(entradas, 'entrada', 'entradas')} e ${D.quantidade(recebidas, 'recebida', 'recebidas')}.` }),
      el('div', { class: 'legenda' }, el('span', { class: 'entradas', texto: 'Entradas (aquisição)' }),
        el('span', { class: 'recebidas', texto: 'Recebidas' })),
      cartao(grafico(resumo)),
      el('h2', { texto: 'Mês a mês' }),
      cartao(campos(resumo.slice().reverse().map(([chave, e, r]) => [D.rotuloMes(chave),
        `${D.quantidade(e, 'entrada', 'entradas')} · ${D.quantidade(r, 'recebida', 'recebidas')}`]))),
    ];
  }

  function telaMais() {
    const opcao = (href, titulo, detalhe) => el('a', { class: 'cartao', href },
      el('div', { texto: titulo }), el('div', { class: 'discreto pequeno', texto: detalhe }));
    return [el('div', { class: 'menu' },
      opcao('#grafico', 'Gráfico mensal', 'Entradas e recebimentos dos últimos 12 meses'),
      opcao('#lixeira', `Lixeira (${dados.lixeira.length})`, 'Operações excluídas, só para consulta'),
      opcao('#backup', 'Sobre este backup', 'Arquivo, data e versão do programa'),
      el('button', { type: 'button', class: 'primario', texto: 'Fechar dados', onclick: fecharDados }),
      el('p', { class: 'discreto pequeno', texto: 'Fechar apaga os dados da memória do celular. Para ver de novo, abra o backup.' }))];
  }

  function telaBackup() {
    const t = info.tempos;
    return [cartao(campos([
      ['Arquivo', info.arquivo],
      ['Criado em', D.dataHora(info.manifesto.criado_em)],
      ['Versão do programa', info.manifesto.versao_app || 'não informada'],
      ['Protegido por senha', info.cifrado ? 'sim' : 'não'],
      ['Tempo para abrir', `${((Object.values(t).reduce((a, b) => a + b, 0)) / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} s`],
    ])), !info.cifrado && el('p', { class: 'aviso', texto: 'Este backup não tem senha: qualquer pessoa com o arquivo consegue ler os dados. Os backups das versões novas do programa sempre têm senha.' })];
  }

  // ---- Navegação pelo endereço (#tela/parâmetro): o botão voltar do iPhone funciona normalmente ---------
  const TELAS = {
    inicio: { titulo: 'Início', aba: 'inicio', montar: telaInicio },
    operacoes: { titulo: 'Operações', aba: 'operacoes', montar: telaOperacoes },
    operacao: { titulo: 'Operação', aba: 'operacoes', montar: telaOperacao, voltar: true },
    contas: { titulo: 'Contas de recebimento', aba: 'contas', montar: telaContas },
    mais: { titulo: 'Mais', aba: 'mais', montar: telaMais },
    lixeira: { titulo: 'Lixeira', aba: 'mais', montar: telaLixeira, voltar: true },
    grafico: { titulo: 'Gráfico mensal', aba: 'mais', montar: telaGrafico, voltar: true },
    backup: { titulo: 'Sobre este backup', aba: 'mais', montar: telaBackup, voltar: true },
  };

  function desenhar() {
    if (!dados) {
      return;
    }
    const [nome, parametro] = location.hash.slice(1).split('/');
    const tela = TELAS[nome] || TELAS.inicio;
    const id = Number(parametro);
    $('titulo').textContent = tela.titulo;
    $('voltar').hidden = !tela.voltar;
    document.querySelectorAll('.abas a').forEach((a) => a.classList.toggle('ativa', a.dataset.aba === tela.aba));
    $('tela').replaceChildren(...[tela.montar(id)].flat(2).filter(Boolean));
    if (tela === TELAS.operacao && dados.operacoes.concat(dados.lixeira).some((r) => r.id === id)) {
      const r = dados.operacoes.find((o) => o.id === id) || dados.lixeira.find((o) => o.id === id);
      $('titulo').textContent = r.nome;
    }
    window.scrollTo(0, 0);
  }

  $('voltar').addEventListener('click', () => history.back());
  window.addEventListener('hashchange', desenhar);
})();
