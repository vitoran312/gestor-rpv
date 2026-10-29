// Telas do app (só consulta). O backup fica guardado no aparelho como saiu do computador (trancado pela
// senha); os dados abertos ficam só na memória desta página e somem ao trancar ou fechar o app.
//
// Todo texto vindo do backup entra na página por textContent (nunca como HTML).
'use strict';

(() => {
  // Igual a versao.py (test_celular confere): mostrada na abertura e em Mais, para saber se o aparelho já
  // carregou a última versão publicada.
  const VERSAO_APP = '0.49.0';
  const D = GestorDados;
  const $ = (id) => document.getElementById(id);
  const SITUACOES = { pendente: 'Pendente', atrasada: 'Atrasada', recebida: 'Recebida' };
  const FILTROS = [['todas', 'Todas'], ['pendente', 'Pendentes'], ['atrasada', 'Atrasadas'], ['recebida', 'Recebidas']];
  const ETAPAS = { senha: 'Conferindo a senha', decifrar: 'Abrindo o backup' };

  let dados = null;      // Conteúdo do backup aberto.
  let info = null;       // Arquivo, manifesto, tempos de abertura e extrair(), que tira um anexo do backup.
  let enderecoAberto = null;  // Anexo exibido agora (blob:), liberado ao sair da tela.
  const TIPOS = { pdf: 'application/pdf', png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp',
    gif: 'image/gif', bmp: 'image/bmp', tif: 'image/tiff', tiff: 'image/tiff' };
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
    // Linhas condicionais (cond && [rótulo, valor]) que não se aplicam chegam como false e são ignoradas.
    return el('dl', { class: 'campos' }, pares.filter(Boolean).filter(([, valor]) => valor !== null && valor !== undefined && valor !== '')
      .map(([rotulo, valor, classe]) => [el('dt', { texto: rotulo }), el('dd', { texto: String(valor), class: classe })]));
  }

  // Conta bancária: aparece só o nome do titular; CPF, endereço, banco e Pix só depois de um toque.
  function contaRecolhida(identificacao, conta) {
    const detalhes = Object.entries(D.TITULOS_CONTA).filter(([chave]) => !['identificacao', 'nome'].includes(chave))
      .map(([chave, rotulo]) => [rotulo, chave === 'cpf' ? D.cpf(conta[chave]) : conta[chave]]);
    return el('details', { class: 'cartao conta' },
      el('summary', {}, el('span', { class: 'nome', texto: conta.nome || identificacao || 'Conta removida' }),
        el('span', { class: 'discreto pequeno', texto: identificacao && conta.nome ? identificacao : '' }),
        el('span', { class: 'mostrar discreto pequeno', texto: 'Toque para ver os dados' })),
      campos(detalhes));
  }

  function cartao(...filhos) {
    return el('div', { class: 'cartao' }, ...filhos);
  }

  function vazio(texto) {
    return el('p', { class: 'vazio', texto });
  }

  // ---- Abertura do backup ------------------------------------------------------------------------------
  // `fonte` é o backup que será aberto: o guardado neste aparelho ou um escolhido agora (novo). Depois de aberto
  // com sucesso, um backup novo passa a ser o guardado.
  const BLOQUEIO_MS = 5 * 60 * 1000;  // Em segundo plano por mais tempo que isso, o app tranca de novo.
  let fonte = null;
  let senhaRecente = null;  // Só até a pessoa responder se quer ativar o Face ID; nunca é gravada.
  let escondidoEm = null;

  function mostrarAndamento(texto, fracao) {
    $('andamento').hidden = false;
    $('andamento-texto').textContent = texto;
    $('andamento-barra').style.width = `${Math.round(fracao * 100)}%`;
  }

  function mostrarErro(texto) {
    $('andamento').hidden = true;
    $('erro').textContent = texto;
    $('erro').hidden = !texto;
  }

  let guardadoAtual = null;  // O que está guardado no aparelho agora (para não trocar dados do celular sem aviso).
  let mostrarNovo = false;   // A pessoa tocou em "Começar sem computador".

  async function prepararAbertura() {
    const guardado = await Guarda.ler('backup').catch(() => null);
    guardadoAtual = guardado;
    if (!fonte || !fonte.novo) {
      fonte = guardado ? { ...guardado, novo: false } : null;
    }
    const faceId = fonte && await FaceId.ativo().catch(() => false);
    $('fonte').hidden = !fonte;
    if (fonte) {
      $('fonte-titulo').textContent = fonte.novo ? 'Arquivo escolhido agora'
        : fonte.independente ? 'Seus dados, guardados neste celular' : 'Backup guardado neste aparelho';
      $('fonte-detalhe').textContent = fonte.criado_em ? `De ${D.dataHora(fonte.criado_em)}` : fonte.nome;
    }
    $('rotulo-arquivo').textContent = guardado ? 'Backup mais novo (.rpvbackup)'
      : 'Já usa o programa no computador? Abra o backup (.rpvbackup)';
    faceIdAtivo = Boolean(faceId);
    $('abrir-faceid').hidden = !faceId;
    $('abrir').textContent = faceId ? 'Abrir com a senha' : 'Abrir';
    // Com um backup guardado, a tela é só de desbloqueio: escolher arquivo e (com Face ID) digitar a senha ficam
    // atrás de um toque. Sem backup guardado (primeira vez), aparece tudo.
    const desbloqueio = Boolean(guardado);
    $('grupo-arquivo').hidden = desbloqueio && !mostrarArquivo && !(fonte && fonte.novo);
    $('grupo-senha').hidden = Boolean(faceId) && !mostrarSenha;
    $('formulario').hidden = $('grupo-arquivo').hidden && $('grupo-senha').hidden;
    $('trocar-backup').hidden = !desbloqueio || !$('grupo-arquivo').hidden;
    $('usar-senha').hidden = !faceId || !$('grupo-senha').hidden;
    $('explicacao').hidden = desbloqueio;
    $('trocar-backup').textContent = guardado && guardado.independente ? 'Restaurar uma cópia de segurança'
      : 'Trocar por um backup mais novo';
    // Primeira vez: além de abrir um backup do computador, dá para começar só no celular.
    $('comecar').hidden = Boolean(guardado || (fonte && fonte.novo)) || mostrarNovo;
    $('form-novo').hidden = !mostrarNovo || Boolean(guardado);
    if (mostrarNovo && !guardado) {
      $('formulario').hidden = true;
      $('explicacao').hidden = true;
    }
    return faceId;
  }

  let mostrarArquivo = false;  // A pessoa tocou em "Trocar por um backup mais novo".
  let mostrarSenha = false;    // A pessoa tocou em "Usar a senha" (com Face ID ativo).
  $('trocar-backup').addEventListener('click', () => {
    mostrarArquivo = true;
    prepararAbertura();
  });
  $('comecar').addEventListener('click', () => {
    // No iPhone, o Safari e o app da Tela de Início guardam dados separados: começar no Safari deixaria os dados
    // fora do app.
    const noSafariDoIphone = /iPhone|iPad/.test(navigator.userAgent) && !instalado;
    if (noSafariDoIphone && !confirm('Você está no Safari. Os dados criados aqui não aparecem no app da Tela de Início. '
      + 'O certo é tocar em Compartilhar → Adicionar à Tela de Início e começar pelo ícone. Começar aqui mesmo assim?')) {
      return;
    }
    mostrarNovo = true;
    prepararAbertura().then(() => $('senha-nova').focus());
  });

  // Dados novos, só no celular: o banco vazio do programa (modelo.sqlite3), empacotado como um backup e trancado
  // com a senha criada agora. Daí em diante, abre como qualquer backup guardado (Face ID ou senha).
  $('form-novo').addEventListener('submit', async (evento) => {
    evento.preventDefault();
    const senha = $('senha-nova').value;
    try {
      D.validarSenha(senha);
      if (senha !== $('senha-repetida').value) {
        throw new Error('As duas senhas não são iguais.');
      }
    } catch (erro) {
      mostrarErro(erro.message);
      return;
    }
    mostrarErro('');
    $('criar').disabled = true;
    try {
      const chave = await LeitorBackup.novaChave(senha, (p) => mostrarAndamento('Criando a senha…', p * 0.9));
      const SQL = await LeitorBackup.sqlJs();
      const modelo = new SQL.Database(new Uint8Array(await (await fetch('modelo.sqlite3')).arrayBuffer()));
      const banco = modelo.export();
      modelo.close();
      const { bytes, manifesto } = await LeitorBackup.empacotar(banco, chave, VERSAO_APP);
      fonte = { bytes, nome: 'GestorRPV-celular.rpvbackup', tamanho: bytes.length, criado_em: manifesto.criado_em,
        novo: true };
      mostrarNovo = false;
      $('form-novo').reset();
      await abrirFonte({ senha, chave });
    } catch (erro) {
      mostrarErro('Não foi possível criar os dados neste aparelho: ' + (erro && erro.message ? erro.message : erro));
    } finally {
      $('criar').disabled = false;
    }
  });

  $('usar-senha').addEventListener('click', () => {
    mostrarSenha = true;
    prepararAbertura().then(() => $('senha').focus());
  });

  let faceIdAtivo = false;

  let bancoLocal = null;  // Banco aberto (sql.js) de quem usa só o celular: as gravações vão para ele.

  async function abrirFonte({ senha = '', faceId = false, automatico = false, chave: chaveDada = null }) {
    // Os dados de quem usa só o celular não são trocados por outro arquivo sem a pessoa confirmar.
    if (fonte && fonte.novo && guardadoAtual && guardadoAtual.independente && !confirm(
      'Abrir este arquivo substitui os dados guardados neste celular pelos dele. Continuar?')) {
      return;
    }
    mostrarErro('');
    $('abrir').disabled = true;
    $('abrir-faceid').disabled = true;
    try {
      if (!fonte) {
        throw new LeitorBackup.ErroBackup('Escolha o arquivo do backup.');
      }
      let liberado = null;
      if (faceId) {
        mostrarAndamento('Aguardando o Face ID…', 0);
        liberado = await FaceId.abrir();
        senha = liberado.segredo.senha;
      }
      const chave = chaveDada || (liberado && liberado.segredo.sal
        ? { sal: FaceId.deB64(liberado.segredo.sal), bruta: FaceId.deB64(liberado.segredo.bruta) } : null);
      mostrarAndamento('Abrindo o backup…', 0.05);
      const leitura = await LeitorBackup.ler(new Uint8Array(fonte.bytes), senha, {
        chave,
        // A senha leva alguns segundos de propósito (é o que impede tentativas em massa); a barra mostra o andamento.
        aoProgredir: (etapa, fracao) => mostrarAndamento(`${ETAPAS[etapa]}…`, etapa === 'senha' ? fracao * 0.9 : 0.9 + fracao * 0.1),
      });
      const independente = leitura.manifesto.origem === 'celular' && leitura.cifrado;
      try {
        dados = D.carregar(leitura.db);
      } finally {
        // Os dados de quem usa só o celular continuam abertos: é neles que o app grava.
        if (independente) {
          bancoLocal = leitura.db;
        } else {
          leitura.db.close();
        }
      }
      info = { arquivo: fonte.nome, tamanho: fonte.tamanho, manifesto: leitura.manifesto, cifrado: leitura.cifrado,
        tempos: leitura.tempos, extrair: leitura.extrair, chave: leitura.chave, independente };
      await carregarPendentes();
      if (fonte.novo) {
        // O arquivo é guardado como veio do computador: continua trancado pela senha.
        fonte = { bytes: fonte.bytes, nome: fonte.nome, tamanho: fonte.tamanho, criado_em: leitura.manifesto.criado_em,
          guardado_em: new Date().toISOString(), novo: false, independente };
        await Guarda.gravar('backup', { ...fonte, novo: undefined }).catch(() => {
          info.naoGuardado = true;  // Sem espaço ou sem permissão: funciona agora, mas precisará escolher de novo.
        });
        Guarda.persistir();
      }
      if (liberado && leitura.chave && liberado.segredo.sal !== FaceId.paraB64(leitura.chave.sal)) {
        // Backup novo, com outra chave: o mesmo Face ID passa a guardar a chave dele (a próxima abertura é rápida).
        await liberado.atualizar(segredoDe(senha, leitura.chave)).catch(() => {});
      }
      senhaRecente = !faceId && leitura.cifrado ? { senha, chave: leitura.chave } : null;
      if (senhaRecente) {
        senhaRecente.oferecer = !faceIdAtivo && await FaceId.possivel() && !localStorageLer('faceid_recusado');
      }
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
      const cancelado = erro && (erro.name === 'NotAllowedError' || erro.name === 'AbortError');
      if (automatico && cancelado) {
        mostrarErro('');  // O iPhone pode exigir um toque antes do Face ID: o botão continua ali.
        return;
      }
      mostrarErro(cancelado ? 'Face ID cancelado. Toque em "Abrir com Face ID" para tentar de novo, ou use a senha.'
        : erro instanceof LeitorBackup.SenhaIncorreta && faceId
          ? 'A senha guardada no Face ID não abre este backup (a senha dos backups foi trocada no computador?). Digite a senha nova.'
          : erro instanceof LeitorBackup.ErroBackup || erro instanceof FaceId.FaceIdIndisponivel ? erro.message
            : 'Não foi possível abrir o backup neste aparelho: ' + (erro && erro.message ? erro.message : erro));
    } finally {
      $('abrir').disabled = false;
      $('abrir-faceid').disabled = false;
    }
  }

  function segredoDe(senha, chave) {
    return { senha, sal: FaceId.paraB64(chave.sal), bruta: FaceId.paraB64(chave.bruta) };
  }

  $('arquivo').addEventListener('change', async () => {
    const arquivo = $('arquivo').files[0];
    if (!arquivo) {
      return;
    }
    fonte = { bytes: await arquivo.arrayBuffer(), nome: arquivo.name, tamanho: arquivo.size, novo: true };
    await prepararAbertura();
  });

  $('formulario').addEventListener('submit', (evento) => {
    evento.preventDefault();
    abrirFonte({ senha: $('senha').value });
  });

  $('abrir-faceid').addEventListener('click', () => abrirFonte({ faceId: true }));

  function localStorageLer(chave) {
    try {
      return localStorage.getItem(chave);
    } catch (erro) {
      return null;
    }
  }

  function localStorageGravar(chave, valor) {
    try {
      localStorage.setItem(chave, valor);
    } catch (erro) {
      // Só serve para não perguntar de novo; sem ele, a pergunta volta.
    }
  }

  async function ativarFaceId(aviso) {
    if (!senhaRecente) {
      return;
    }
    const pronto = () => {
      senhaRecente = null;
      faceIdAtivo = true;
      aviso.replaceChildren(el('div', { texto: 'Pronto: nas próximas vezes, o app abre com o Face ID.' }));
    };
    try {
      const completar = await FaceId.ativar(segredoDe(senhaRecente.senha, senhaRecente.chave));
      if (!completar) {
        pronto();
        return;
      }
      aviso.replaceChildren(el('div', { texto: 'Falta confirmar uma vez com o Face ID.' }),
        el('div', { class: 'botoes' }, el('button', { type: 'button', class: 'primario', texto: 'Confirmar com Face ID',
          onclick: () => completar().then(pronto).catch(() => aviso.replaceChildren(
            el('div', { texto: 'Face ID não foi ativado. Tente de novo pelo menu Mais.' }))) })));
    } catch (erro) {
      const cancelado = erro && (erro.name === 'NotAllowedError' || erro.name === 'AbortError');
      aviso.replaceChildren(el('div', { texto: cancelado ? 'Face ID não foi ativado.' : erro instanceof FaceId.FaceIdIndisponivel
        ? erro.message : 'Não foi possível ativar o Face ID neste aparelho.' }));
    }
  }

  let encerrarVisualizador = null;  // Libera as páginas desenhadas e o PDF aberto.

  function liberarDocumento() {
    if (encerrarVisualizador) {
      encerrarVisualizador();
      encerrarVisualizador = null;
    }
    if (enderecoAberto) {
      URL.revokeObjectURL(enderecoAberto);
      enderecoAberto = null;
    }
  }

  // Tranca: apaga os dados da memória e volta à abertura. O backup guardado continua no aparelho, trancado.
  async function fecharDados() {
    liberarDocumento();
    if (bancoLocal) {
      bancoLocal.close();
      bancoLocal = null;
    }
    dados = null;
    info = null;
    senhaRecente = null;
    abertasPendentes.clear();
    mostrarArquivo = false;
    mostrarSenha = false;
    estado.busca = '';
    estado.filtro = 'todas';
    $('tela').replaceChildren();
    $('aplicativo').hidden = true;
    $('abertura').hidden = false;
    history.replaceState(null, '', location.pathname);
    window.scrollTo(0, 0);
    return prepararAbertura();
  }

  async function esquecerBackup() {
    if (!confirm('Apagar o backup guardado neste aparelho e desativar o Face ID do app? O backup no computador e no Google Drive não muda.')) {
      return;
    }
    await Promise.all([Guarda.apagar('backup'), FaceId.desativar()]).catch(() => {});
    fonte = null;
    fecharDados();
  }

  // Ao voltar depois de muito tempo em segundo plano, o app tranca; com Face ID, já pede o rosto.
  document.addEventListener('visibilitychange', async () => {
    if (document.hidden) {
      escondidoEm = Date.now();
      return;
    }
    if (dados && escondidoEm && Date.now() - escondidoEm > BLOQUEIO_MS) {
      if (await fecharDados()) {
        abrirFonte({ faceId: true });
      }
    }
    escondidoEm = null;
  });

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
    const oferta = senhaRecente && senhaRecente.oferecer && el('div', { class: 'aviso' },
      el('div', { texto: 'Abrir com Face ID nas próximas vezes, sem digitar a senha?' }),
      el('div', { class: 'botoes' },
        el('button', { type: 'button', class: 'primario', texto: 'Ativar Face ID', onclick: (e) => ativarFaceId(e.target.closest('.aviso')) }),
        el('button', { type: 'button', class: 'secundario', texto: 'Agora não', onclick: (e) => {
          senhaRecente.oferecer = false;
          localStorageGravar('faceid_recusado', '1');
          e.target.closest('.aviso').remove();
        } })));
    return [
      oferta,
      info.naoGuardado && el('p', { class: 'aviso', texto: 'Não foi possível guardar o backup neste aparelho (falta de espaço?). Na próxima vez, escolha o arquivo de novo.' }),
      info.independente && localStorageLer('copia_pendente') === '1' && el('a', { class: 'aviso item', href: '#copia' },
        el('div', { class: 'nome', texto: 'Faça uma cópia de segurança' }),
        el('div', { class: 'discreto pequeno', texto: 'Há mudanças só neste celular. Toque para salvar uma cópia trancada no iCloud ou no Google Drive.' })),
      dados.demonstracao && el('p', { class: 'aviso', texto: 'Este backup tem dados de demonstração, com nomes e valores fictícios.' }),
      el('p', { class: 'discreto pequeno', texto: info.independente ? 'Seus dados, guardados neste celular.'
        : `Dados do backup de ${D.dataHora(info.manifesto.criado_em)}${idade}.` }),
      info.independente && !dados.operacoes.length && el('div', { class: 'aviso' },
        el('div', { class: 'nome', texto: 'Por onde começar' }),
        el('div', { texto: '1. Cadastre a conta onde você recebe, na aba Contas.' }),
        el('div', { texto: '2. Cadastre suas entradas na aba Operações (+ Nova entrada).' }),
        el('div', { texto: '3. Quando receber, abra a operação e toque em "Registrar recebimento".' })),
      !info.independente && dias !== null && dias > 7 && el('p', { class: 'aviso', texto: 'Este backup tem mais de uma semana. Faça um backup novo no computador para ver os dados atuais.' }),
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
    const quantas = listaPendentes.filter((p) => (p.tipo || 'entrada') === 'entrada').length;
    const pendentes = quantas > 0 && el('a', { class: 'aviso item', href: '#pendentes' },
      el('div', { class: 'nome', texto: quantas === 1 ? '1 entrada feita no celular aguarda o computador'
        : `${quantas} entradas feitas no celular aguardam o computador` }),
      el('div', { class: 'discreto pequeno', texto: 'Toque para ver ou enviar de novo' }));
    const nova = el('a', { class: 'botao-link primario', href: '#nova', texto: '+ Nova entrada' });
    return [nova, pendentes, busca, filtros, lista];
  }

  // ---- Entradas feitas no celular ----------------------------------------------------------------------
  // Cada entrada vira um arquivo .rpvcelular, cifrado com a chave do backup aberto (o computador abre com a
  // senha dos backups). O arquivo fica guardado aqui até um backup mais novo mostrar que o computador já o
  // importou (configuração entradas_celular_importadas); até lá, pode ser enviado de novo.
  let listaPendentes = [];          // [{id, arquivo, criada_em, bytes}] como guardadas no aparelho.
  const abertasPendentes = new Map();  // id → {tipo, ...dados}, para as que a chave do backup aberto consegue ler.

  async function carregarPendentes() {
    const guardadas = await Guarda.ler('pendentes').catch(() => null) || [];
    listaPendentes = guardadas.filter((p) => !dados.importadasDoCelular.has(p.id));
    if (listaPendentes.length !== guardadas.length) {
      await Guarda.gravar('pendentes', listaPendentes).catch(() => {});
    }
    abertasPendentes.clear();
    for (const p of listaPendentes) {
      try {
        const { conteudo } = await LeitorBackup.decifrar(new Uint8Array(p.bytes), { chave: info.chave });
        const pacote = JSON.parse(new TextDecoder().decode(conteudo));
        abertasPendentes.set(p.id, pacote.conta ? { ...pacote.conta, tipo: 'conta' } : { ...pacote.entrada, tipo: 'entrada' });
      } catch (erro) {
        // Feita com um backup de outra chave: continua guardada e pode ser enviada, só não é mostrada.
      }
    }
  }

  // Valor em reais digitado como no programa do computador: os números entram pelos centavos e a pontuação
  // aparece sozinha (1 → 0,01; 150000 → 1.500,00). Colar troca o valor inteiro ("1.500,00" vale mil e quinhentos).
  function campoMoeda(nome) {
    const campo = el('input', { name: nome, inputmode: 'numeric', autocomplete: 'off', placeholder: '0,00',
      enterkeyhint: 'next' });
    const formatar = () => {
      const digitos = campo.value.replace(/\D/g, '').replace(/^0+/, '').slice(0, 14);
      campo.value = digitos ? D.moeda(Number(digitos)) : '';
    };
    campo.addEventListener('input', (evento) => {
      if (evento.inputType !== 'insertFromPaste') {
        formatar();
      }
    });
    campo.addEventListener('paste', (evento) => {
      evento.preventDefault();
      const texto = (evento.clipboardData || window.clipboardData).getData('text');
      try {
        campo.value = D.moeda(D.centavos(texto.trim()));
      } catch (erro) {
        // Texto que não é um valor: o campo fica como estava.
      }
      campo.dispatchEvent(new Event('input'));
    });
    return campo;
  }

  // ---- Quem usa só o celular: gravações direto nos dados do aparelho ---------------------------------------
  // Cada gravação reempacota os dados como um backup (trancado pela mesma chave) e o guarda no aparelho.
  async function salvarLocal() {
    const banco = bancoLocal.export();
    const { bytes, manifesto } = await LeitorBackup.empacotar(banco, info.chave, VERSAO_APP);
    fonte = { ...fonte, bytes, tamanho: bytes.length, criado_em: manifesto.criado_em, independente: true };
    await Guarda.gravar('backup', { bytes, nome: fonte.nome, tamanho: bytes.length, criado_em: manifesto.criado_em,
      guardado_em: new Date().toISOString(), independente: true });
    Guarda.persistir();
    info.manifesto = manifesto;
    dados = D.carregar(bancoLocal);
    localStorageGravar('copia_pendente', '1');
  }

  function inserir(tabela, linha) {
    const campos = Object.keys(linha);
    bancoLocal.run(`INSERT INTO ${tabela} (${campos.join(',')}) VALUES (${campos.map(() => '?').join(',')})`,
      campos.map((k) => linha[k]));
    return bancoLocal.exec('SELECT last_insert_rowid()')[0].values[0][0];
  }

  // Como Banco.salvar: nome com iniciais maiúsculas, observação com a primeira maiúscula e a cópia dos dados da
  // conta guardada na operação.
  async function gravarEntradaLocal(entrada, conta) {
    const id = inserir('rpvs', {
      nome: D.nomeTitulo(entrada.nome), aquisicao: entrada.aquisicao, previsto: entrada.previsto, custo: entrada.custo,
      conta: conta.identificacao, previsao: entrada.previsao, comissao: entrada.comissao,
      observacoes: D.primeiraMaiuscula(entrada.observacoes), conta_id: conta.id, conta_snapshot: D.snapshotConta(conta),
    });
    await salvarLocal();
    return id;
  }

  async function gravarContaLocal(valores) {
    inserir('contas', D.linhaDaConta(valores));
    await salvarLocal();
  }

  // Como Banco.registrar_recebimento (sem anexos, por enquanto).
  async function registrarRecebimentoLocal(registro, data) {
    D.validarDataIso(data, 'Data do recebimento');
    if (data < registro.aquisicao) {
      throw new Error('O recebimento não pode ser anterior à aquisição.');
    }
    if (data > D.hojeIso()) {
      throw new Error('O recebimento não pode estar no futuro.');
    }
    bancoLocal.run('UPDATE rpvs SET recebimento=? WHERE id=? AND lixeira_em IS NULL', [data, registro.id]);
    await salvarLocal();
  }

  // Cópia de segurança: o mesmo arquivo trancado, salvo onde a pessoa quiser (Arquivos, iCloud, Google Drive).
  function telaCopia() {
    const hoje = D.hojeIso().replaceAll('-', '');
    const arquivo = new File([new Uint8Array(fonte.bytes)], `GestorRPV-celular-${hoje}.rpvbackup`, { type: 'application/octet-stream' });
    const podeCompartilhar = navigator.canShare && navigator.canShare({ files: [arquivo] });
    const resultado = el('p', { class: 'discreto pequeno' });
    const ultima = localStorageLer('ultima_copia');
    return [
      el('p', { texto: 'Seus dados estão só neste celular. Se ele for perdido, trocado ou o app for apagado, eles se vão junto — a cópia de segurança é o que permite recuperar.' }),
      el('ol', { class: 'passos' },
        el('li', { texto: 'Toque em "Salvar cópia de segurança".' }),
        el('li', { texto: 'Escolha "Salvar em Arquivos" e uma pasta do iCloud Drive ou do Google Drive.' }),
        el('li', { texto: 'Para recuperar num celular novo: instale o app, escolha o arquivo da cópia na primeira tela e digite a senha.' })),
      podeCompartilhar
        ? el('button', { type: 'button', class: 'primario', texto: 'Salvar cópia de segurança', onclick: () => {
          navigator.share({ files: [arquivo] }).then(() => {
            localStorageGravar('copia_pendente', '0');
            localStorageGravar('ultima_copia', new Date().toISOString());
            resultado.textContent = 'Cópia salva. Faça de novo sempre que cadastrar algo importante.';
          }).catch(() => {});
        } })
        : el('a', { class: 'botao-link primario', href: URL.createObjectURL(arquivo), download: arquivo.name,
          texto: 'Baixar cópia de segurança', onclick: () => localStorageGravar('copia_pendente', '0') }),
      resultado,
      el('p', { class: 'discreto pequeno', texto: ultima ? `Última cópia: ${D.dataHora(ultima)}.` : 'Nenhuma cópia feita ainda.' }),
      el('p', { class: 'discreto pequeno', texto: 'A cópia é trancada com a sua senha: sem ela, ninguém consegue abrir.' }),
    ];
  }

  // Cifra e guarda no aparelho uma entrada ou conta feita aqui, e abre a tela de envio ao computador.
  async function guardarPendente(tipo, dados) {
    const completa = { id: crypto.randomUUID(), ...dados, criada_em: new Date().toISOString() };
    const pacote = { formato: 'gestor-rpv-celular', versao_formato: 1, versao_app: VERSAO_APP, [tipo]: completa };
    const bytes = await LeitorBackup.cifrar(new TextEncoder().encode(JSON.stringify(pacote)), info.chave);
    const agora = new Date();
    const marca = `${D.hojeIso(agora).replaceAll('-', '')}-${String(agora.getHours()).padStart(2, '0')}${String(agora.getMinutes()).padStart(2, '0')}`;
    const registro = { id: completa.id, tipo, criada_em: completa.criada_em, bytes,
      arquivo: `GestorRPV-celular-${tipo}-${marca}-${completa.id.slice(0, 8)}.rpvcelular` };
    listaPendentes = [...listaPendentes, registro];
    await Guarda.gravar('pendentes', listaPendentes);
    abertasPendentes.set(completa.id, { ...completa, tipo });
    location.replace(`#enviar/${completa.id}`);
  }

  // Contas feitas no celular que o computador ainda não importou: já podem ser usadas em entradas novas.
  function contasPendentes() {
    return [...abertasPendentes.values()].filter((p) => p.tipo === 'conta');
  }

  function campoFormulario(rotulo, controle, ajuda) {
    return el('label', { class: 'campo' }, el('span', { texto: rotulo }), controle,
      ajuda && el('span', { class: 'discreto pequeno', texto: ajuda }));
  }

  function telaNovaEntrada() {
    if (!info.chave) {
      return [el('p', { class: 'aviso', texto: 'Para cadastrar entradas no celular, abra um backup com senha (feito pelo programa a partir da versão 0.30).' })];
    }
    const contas = [...dados.contas.filter((c) => c.ativa), ...(info.independente ? [] : contasPendentes()
      .map((c) => ({ id: `p:${c.id}`, conta_id: -1, identificacao: c.identificacao, pendente: true })))];
    if (!contas.length) {
      return [el('p', { class: 'aviso', texto: 'Cadastre uma conta de recebimento (aba Contas) antes de cadastrar entradas.' }),
        el('a', { class: 'botao-link primario', href: '#nova-conta', texto: '+ Nova conta' })];
    }
    const valor = campoMoeda;
    const c = {
      nome: el('input', { name: 'nome', autocomplete: 'off', autocapitalize: 'words', maxlength: '150' }),
      aquisicao: el('input', { name: 'aquisicao', type: 'date', value: D.hojeIso() }),
      custo: valor('custo'),
      previsto: valor('previsto'),
      conta: el('select', { name: 'conta' }, el('option', { value: '', texto: 'Escolha a conta' }),
        contas.map((conta) => el('option', { value: String(conta.id),
          texto: conta.identificacao + (conta.pendente ? ' (aguardando o computador)' : '') }))),
      previsao: el('input', { name: 'previsao', type: 'date' }),
      comissao: valor('comissao'),
      observacoes: el('textarea', { name: 'observacoes', rows: '3', maxlength: '5000' }),
    };
    if (contas.length === 1) {
      c.conta.value = String(contas[0].id);
    }
    const lucro = el('p', { class: 'discreto' });
    const erros = el('div', { class: 'erro', role: 'alert' });
    const atualizarLucro = () => {
      try {
        lucro.textContent = `Lucro previsto: ${D.reais(D.centavos(c.previsto.value) - D.centavos(c.custo.value))}`;
      } catch (erro) {
        lucro.textContent = 'Lucro previsto: preencha os dois valores.';
      }
    };
    c.custo.addEventListener('input', atualizarLucro);
    c.previsto.addEventListener('input', atualizarLucro);
    atualizarLucro();
    const salvar = el('button', { type: 'submit', class: 'primario', texto: 'Salvar entrada' });
    const formulario = el('form', { class: 'cartao formulario', autocomplete: 'off', onsubmit: async (evento) => {
      evento.preventDefault();
      const problemas = [];
      const converter = (rotulo, texto, opcional) => {
        if (opcional && !texto.trim()) {
          return null;
        }
        try {
          return D.centavos(texto);
        } catch (erro) {
          problemas.push(`${rotulo}: ${erro.message}`);
          return undefined;
        }
      };
      const entrada = {
        nome: D.nomeFormatado(c.nome.value), aquisicao: c.aquisicao.value, previsao: c.previsao.value,
        custo: converter('Valor de aquisição', c.custo.value), previsto: converter('Valor Total RPV', c.previsto.value),
        comissao: converter('Comissão', c.comissao.value, true), observacoes: c.observacoes.value.trim(),
      };
      // Todos os problemas de uma vez, como no computador: primeiro os valores mal escritos, depois as regras.
      if (!problemas.length) {
        problemas.push(...D.problemasDaEntrada(entrada));
      }
      const conta = contas.find((x) => String(x.id) === c.conta.value);
      if (!conta) {
        problemas.push('Escolha a conta de destino.');
      }
      if (problemas.length) {
        erros.replaceChildren(...problemas.map((p) => el('div', { texto: p })));
        erros.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return;
      }
      salvar.disabled = true;
      try {
        if (info.independente) {
          location.replace(`#operacao/${await gravarEntradaLocal(entrada, conta)}`);
          return;
        }
        // Conta ainda não importada: o computador a encontra pelo nome (conta_id -1), importando-a antes.
        await guardarPendente('entrada', { ...entrada, conta_id: conta.pendente ? -1 : conta.id, conta: conta.identificacao });
      } catch (erro) {
        erros.replaceChildren(el('div', { texto: 'Não foi possível guardar a entrada neste aparelho: ' + (erro && erro.message ? erro.message : erro) }));
        salvar.disabled = false;
      }
    } },
    campoFormulario('Titular original', c.nome),
    campoFormulario('Data de aquisição', c.aquisicao),
    campoFormulario('Valor de aquisição', c.custo),
    campoFormulario('Valor Total RPV', c.previsto),
    lucro,
    campoFormulario('Conta de destino', c.conta),
    campoFormulario('Previsão inicial de recebimento', c.previsao),
    campoFormulario('Comissão (opcional)', c.comissao),
    campoFormulario('Observações (opcional)', c.observacoes),
    erros,
    salvar);
    return [el('p', { class: 'discreto pequeno', texto: info.independente ? 'A entrada é gravada nos seus dados deste celular.'
      : 'A entrada fica guardada neste celular e vai para o computador por um arquivo que você salva na pasta do backup no Google Drive. Ao abrir, o Gestor no computador pergunta se quer importá-la.' }), formulario];
  }

  function resumoPendente(p) {
    const e = abertasPendentes.get(p.id);
    if (e && e.tipo === 'conta') {
      return [`Conta: ${e.identificacao}`, `${e.banco} · titular ${e.nome}`];
    }
    return e ? [e.nome, `${D.reais(e.previsto)} · previsão ${D.dataBr(e.previsao)} · ${e.conta}`]
      : ['Feita com um backup anterior', `Criada em ${D.dataHora(p.criada_em)}`];
  }

  // Conta de recebimento nova: mesmas regras do computador, inclusive não repetir apelido, conta ou Pix.
  function telaNovaConta() {
    if (!info.chave) {
      return [el('p', { class: 'aviso', texto: 'Para cadastrar contas no celular, abra um backup com senha (feito pelo programa a partir da versão 0.30).' })];
    }
    const campo = (nome, extra = {}) => el('input', { name: nome, autocomplete: 'off', ...extra });
    const c = {
      identificacao: campo('identificacao', { placeholder: 'Ex.: Nubank da Lilian' }),
      nome: campo('nome', { autocapitalize: 'words' }),
      cpf: campo('cpf', { inputmode: 'numeric', placeholder: '000.000.000-00' }),
      endereco: campo('endereco'),
      numero_endereco: campo('numero_endereco', { inputmode: 'numeric' }),
      cidade: campo('cidade'),
      estado: el('select', { name: 'estado' }, el('option', { value: '', texto: 'Escolha' }),
        D.ESTADOS.map((uf) => el('option', { value: uf, texto: uf }))),
      banco: campo('banco'),
      agencia: campo('agencia', { inputmode: 'numeric' }),
      numero: campo('numero', { inputmode: 'numeric' }),
      pix: campo('pix', { autocapitalize: 'off', spellcheck: 'false' }),
    };
    c.cpf.addEventListener('input', () => {
      const d = c.cpf.value.replace(/\D/g, '').slice(0, 11);
      c.cpf.value = [d.slice(0, 3), d.slice(3, 6), d.slice(6, 9)].filter(Boolean).join('.') + (d.length > 9 ? '-' + d.slice(9) : '');
    });
    const erros = el('div', { class: 'erro', role: 'alert' });
    const salvar = el('button', { type: 'submit', class: 'primario', texto: 'Salvar conta' });
    const formulario = el('form', { class: 'cartao formulario', autocomplete: 'off', onsubmit: async (evento) => {
      evento.preventDefault();
      const valores = Object.fromEntries(Object.entries(c).map(([k, controle]) => [k, controle.value.trim()]));
      const problemas = D.problemasDaConta(valores, [...dados.contas, ...(info.independente ? [] : contasPendentes())]);
      if (problemas.length) {
        erros.replaceChildren(...problemas.map((p) => el('div', { texto: p })));
        erros.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return;
      }
      salvar.disabled = true;
      try {
        if (info.independente) {
          await gravarContaLocal(valores);
          location.replace('#contas');
          return;
        }
        await guardarPendente('conta', valores);
      } catch (erro) {
        erros.replaceChildren(el('div', { texto: 'Não foi possível guardar a conta neste aparelho: ' + (erro && erro.message ? erro.message : erro) }));
        salvar.disabled = false;
      }
    } },
    ...Object.entries(D.TITULOS_CONTA).map(([chave, rotulo]) => campoFormulario(
      chave === 'agencia' ? 'Agência (opcional)' : rotulo, c[chave])),
    erros, salvar);
    return [el('p', { class: 'discreto pequeno', texto: info.independente ? 'A conta é gravada nos seus dados deste celular.'
      : 'A conta fica guardada neste celular e já pode ser escolhida numa entrada nova. Ela vai para o computador do mesmo jeito que as entradas.' }), formulario];
  }

  function telaPendentes() {
    if (!listaPendentes.length) {
      return [vazio('Nada aguardando o computador.')];
    }
    return [el('p', { class: 'discreto pequeno', texto: 'Somem daqui sozinhas quando um backup mais novo, feito depois da importação no computador, for aberto no celular.' }),
      el('div', { class: 'menu' }, listaPendentes.map((p) => {
        const [titulo, detalhe] = resumoPendente(p);
        return el('a', { class: 'cartao', href: `#enviar/${p.id}` }, el('div', { class: 'nome', texto: titulo }),
          el('div', { class: 'discreto pequeno', texto: detalhe }));
      }))];
  }

  function telaEnviar(id) {
    const p = listaPendentes.find((x) => x.id === id);
    if (!p) {
      return [vazio('Isto já foi importado pelo computador ou apagado.')];
    }
    const [titulo, detalhe] = resumoPendente(p);
    const arquivo = new File([new Uint8Array(p.bytes)], p.arquivo, { type: 'application/octet-stream' });
    const podeCompartilhar = navigator.canShare && navigator.canShare({ files: [arquivo] });
    const resultado = el('p', { class: 'discreto pequeno' });
    const enviar = podeCompartilhar
      ? el('button', { type: 'button', class: 'primario', texto: 'Enviar para o computador', onclick: () => {
        navigator.share({ files: [arquivo] }).then(() => {
          resultado.textContent = 'Arquivo enviado. Ao abrir o Gestor no computador, ele vai perguntar se quer importar.';
        }).catch(() => {});  // Cancelar o menu não é erro.
      } })
      : el('a', { class: 'botao-link primario', href: URL.createObjectURL(arquivo), download: p.arquivo, texto: 'Baixar o arquivo' });
    return [
      cartao(el('div', { class: 'nome', texto: titulo }), el('div', { class: 'discreto pequeno', texto: detalhe })),
      el('h2', { texto: 'Como levar ao computador' }),
      el('ol', { class: 'passos' },
        el('li', { texto: 'Toque em "Enviar para o computador".' }),
        el('li', { texto: 'No menu do iPhone, escolha "Salvar em Arquivos".' }),
        el('li', { texto: 'Abra Google Drive e a pasta onde ficam os backups do Gestor (a do backup automático) e toque em Salvar.' }),
        el('li', { texto: 'Abra o Gestor no computador: ele mostra as entradas do celular e pergunta se quer importar.' })),
      enviar, resultado,
      el('button', { type: 'button', class: 'secundario', texto: 'Apagar esta entrada do celular', onclick: async () => {
        if (!confirm('Apagar esta entrada do celular? Se o arquivo já foi salvo no Google Drive, o computador ainda pode importá-la.')) {
          return;
        }
        listaPendentes = listaPendentes.filter((x) => x.id !== id);
        await Guarda.gravar('pendentes', listaPendentes).catch(() => {});
        location.replace('#operacoes');
      } }),
    ];
  }

  // Quem usa só o celular registra o recebimento aqui (no computador, isso é feito no programa).
  function formularioRecebimento(r) {
    const data = el('input', { type: 'date', name: 'recebimento', value: D.hojeIso() });
    const erro = el('div', { class: 'erro', role: 'alert' });
    const botao = el('button', { type: 'submit', class: 'primario', texto: 'Registrar recebimento' });
    return el('form', { class: 'cartao formulario recebimento', onsubmit: async (evento) => {
      evento.preventDefault();
      botao.disabled = true;
      try {
        await registrarRecebimentoLocal(r, data.value);
        desenhar();
      } catch (e) {
        erro.textContent = e.message;
        botao.disabled = false;
      }
    } }, campoFormulario('Data do recebimento', data), erro, botao);
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
      info.independente && !r.recebimento && !r.lixeira_em && formularioRecebimento(r),
      el('h2', { texto: 'Conta de destino' }),
      contaRecolhida(r.conta, conta),
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
        ? el('div', { class: 'menu' }, documentos.map((d) => el('a', { class: 'cartao', href: `#documento/${d.id}` },
          el('div', { class: 'nome', texto: d.nome }),
          el('div', { class: 'discreto pequeno', texto: d.tipo === 'recebimento' ? 'Comprovante de recebimento' : 'Documento da entrada' }))))
        : el('p', { class: 'discreto', texto: 'Nenhum documento anexado.' }),
    ];
  }

  function documentoPorId(id) {
    for (const lista of dados.documentos.values()) {
      const encontrado = lista.find((d) => d.id === id);
      if (encontrado) {
        return encontrado;
      }
    }
    return null;
  }

  // Anexo: extraído do backup só agora, conferido pelo hash e mostrado na própria tela. "Compartilhar"
  // abre o menu do iPhone (ver em tela cheia, salvar em Arquivos, enviar).
  function telaDocumento(id) {
    const d = documentoPorId(id);
    if (!d) {
      return [vazio('Documento não encontrado neste backup.')];
    }
    const extensao = d.caminho.split('.').pop().toLowerCase();
    const tipo = TIPOS[extensao] || 'application/octet-stream';
    const area = el('div', { class: 'documento' }, el('p', { class: 'discreto', texto: 'Abrindo o documento…' }));
    const acoes = el('div');
    const visualizacao = el('div', { class: 'visualizacao' });
    info.extrair(d.caminho).then(async (bytes) => {
      if (location.hash !== `#documento/${id}`) {
        return;  // A pessoa já saiu da tela.
      }
      const arquivo = new File([bytes], d.nome, { type: tipo });
      liberarDocumento();
      enderecoAberto = URL.createObjectURL(arquivo);
      const podeCompartilhar = navigator.canShare && navigator.canShare({ files: [arquivo] });
      acoes.replaceChildren(podeCompartilhar
        ? el('button', { type: 'button', class: 'secundario', texto: 'Compartilhar ou salvar', onclick: () => {
          navigator.share({ files: [arquivo] }).catch(() => {});  // Cancelar o menu não é erro.
        } })
        : el('a', { class: 'cartao', href: enderecoAberto, download: d.nome, texto: 'Baixar o documento' }));
      area.replaceChildren(visualizacao, acoes);
      encerrarVisualizador = tipo === 'application/pdf'
        ? await Visualizador.pdf(bytes, visualizacao)
        : Visualizador.imagem(enderecoAberto, d.nome, visualizacao);
      window.scrollTo(0, 0);
    }).catch((erro) => {
      // Se o arquivo saiu do backup mas não pôde ser desenhado, "Compartilhar" ainda abre no visualizador do iPhone.
      area.replaceChildren(el('p', { class: 'erro', texto: erro instanceof LeitorBackup.ErroBackup ? erro.message
        : 'Não foi possível mostrar o documento aqui. Use "Compartilhar ou salvar" para abrir em outro app.' }),
      // Detalhe técnico (sem dados do documento), para um print explicar o que o aparelho recusou.
      !(erro instanceof LeitorBackup.ErroBackup) && el('p', { class: 'discreto pequeno',
        texto: `Detalhe: ${erro && erro.name ? erro.name : 'erro'}: ${erro && erro.message ? erro.message : erro}` }), acoes);
    });
    return [el('p', { class: 'discreto pequeno', texto: d.tipo === 'recebimento' ? 'Comprovante de recebimento' : 'Documento da entrada' }), area];
  }

  function telaContas() {
    const nova = el('a', { class: 'botao-link primario', href: '#nova-conta', texto: '+ Nova conta' });
    const pendentes = contasPendentes().map((c) => el('a', { class: 'aviso item', href: `#enviar/${c.id}` },
      el('div', { class: 'nome', texto: c.identificacao }),
      el('div', { class: 'discreto pequeno', texto: 'Feita no celular · aguarda o computador · toque para enviar' })));
    if (!dados.contas.length) {
      return [nova, pendentes, vazio('Nenhuma conta cadastrada.')];
    }
    return [nova, pendentes, el('div', { class: 'lista' }, dados.contas.map((c) => {
      const usos = dados.operacoes.filter((r) => r.conta_id === c.id).length;
      return el('div', {},
        el('div', { class: 'linha1 rotulo-conta' }, el('span', { class: 'discreto pequeno', texto: usos === 1
          ? '1 operação usa esta conta' : `${usos} operações usam esta conta` }),
        el('span', { class: 'selo ' + (c.ativa ? 'recebida' : 'pendente'), texto: c.ativa ? 'Ativa' : 'Desativada' })),
        contaRecolhida(c.identificacao, c));
    }))];
  }

  function telaLixeira() {
    if (!dados.lixeira.length) {
      return [vazio('A lixeira está vazia.')];
    }
    return [el('p', { class: 'discreto pequeno', texto: 'Operações excluídas no computador. Para restaurar, use o programa no computador.' }),
      el('div', { class: 'lista' }, dados.lixeira.map((r) => itemOperacao(r, `#operacao/${r.id}`)))];
  }

  // Gráfico de barras em SVG: entradas (neutro) e recebidas (verde) por mês, com grade e escala. Tocar num mês
  // o destaca e mostra os números dele embaixo.
  function grafico(resumo, aoEscolher, escolhido) {
    const SVG = 'http://www.w3.org/2000/svg';
    const largura = 360;
    const altura = 230;
    const esquerda = 26;
    const base = 196;
    const topo = 14;
    const topoEixo = D.escala(Math.max(1, ...resumo.flatMap(([, e, r]) => [e, r])));
    const grupo = (largura - esquerda) / resumo.length;
    const barra = Math.min(11, grupo * 0.3);
    const svg = document.createElementNS(SVG, 'svg');
    const novo = (tag, atributos, texto) => {
      const elemento = document.createElementNS(SVG, tag);
      Object.entries(atributos).forEach(([n, v]) => elemento.setAttribute(n, v));
      if (texto !== undefined) {
        elemento.textContent = texto;
      }
      return elemento;
    };
    const y = (valor) => base - (base - topo) * valor / topoEixo;
    svg.setAttribute('viewBox', `0 0 ${largura} ${altura}`);
    svg.setAttribute('class', 'grafico');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Entradas e recebimentos dos últimos 12 meses');
    for (let passo = 0; passo <= 4; passo += 1) {
      const valor = topoEixo * passo / 4;
      svg.append(novo('line', { x1: esquerda, x2: largura, y1: y(valor), y2: y(valor), class: passo ? 'grade' : 'eixo' }));
      svg.append(novo('text', { x: esquerda - 6, y: y(valor) + 3, 'text-anchor': 'end', class: 'escala' }, String(valor)));
    }
    resumo.forEach(([chave, entradas, recebidas], i) => {
      const inicio = esquerda + grupo * i;
      const centro = inicio + grupo / 2;
      const alvo = novo('g', { class: 'mes' + (chave === escolhido ? ' escolhido' : '') });
      alvo.append(novo('rect', { x: inicio + 1, y: topo - 6, width: grupo - 2, height: base - topo + 26, rx: 6, class: 'fundo-mes' }));
      [[entradas, 'entradas', -barra - 1], [recebidas, 'recebidas', 1]].forEach(([valor, classe, deslocamento]) => {
        if (valor) {
          alvo.append(novo('rect', { x: centro + deslocamento, y: y(valor), width: barra, height: base - y(valor), rx: 2, class: classe }));
        }
      });
      const [mes, ano] = D.rotuloMes(chave).split('/');
      alvo.append(novo('text', { x: centro, y: base + 14, 'text-anchor': 'middle' }, mes));
      if (i === 0 || mes === 'jan') {
        alvo.append(novo('text', { x: centro, y: base + 26, 'text-anchor': 'middle', class: 'ano' }, ano));
      }
      alvo.addEventListener('click', () => aoEscolher(chave));
      svg.append(alvo);
    });
    return svg;
  }

  function telaGrafico() {
    const resumo = D.resumoMensal(dados.operacoes);
    const entradas = resumo.reduce((t, [, e]) => t + e, 0);
    const recebidas = resumo.reduce((t, [, , r]) => t + r, 0);
    const area = el('div', { class: 'cartao' });
    const detalhe = el('div', { class: 'cartao' });
    const escolher = (chave) => {
      const [, e, r] = resumo.find(([c]) => c === chave);
      const valores = D.valoresDoMes(dados.operacoes, chave);
      area.replaceChildren(grafico(resumo, escolher, chave));
      detalhe.replaceChildren(el('div', { class: 'nome', texto: D.rotuloMes(chave) }), campos([
        ['Entradas', D.quantidade(e, 'operação', 'operações')],
        ['Investido', D.reais(valores.investido)],
        ['Recebidas', D.quantidade(r, 'operação', 'operações')],
        ['Recebido', D.reais(valores.recebido), 'verde'],
        ['Lucro realizado', D.reais(valores.lucro), 'verde'],
      ]));
    };
    escolher(resumo[resumo.length - 1][0]);
    const movimentados = resumo.filter(([, e, r]) => e || r).reverse();
    return [
      el('p', { class: 'discreto', texto: `Últimos 12 meses: ${D.quantidade(entradas, 'entrada', 'entradas')} e ${D.quantidade(recebidas, 'recebida', 'recebidas')}. Toque num mês para ver os números.` }),
      el('div', { class: 'legenda' }, el('span', { class: 'entradas', texto: 'Entradas (aquisição)' }),
        el('span', { class: 'recebidas', texto: 'Recebidas' })),
      area,
      el('h2', { texto: 'Mês escolhido' }),
      detalhe,
      el('h2', { texto: 'Meses com movimento' }),
      movimentados.length
        ? el('div', { class: 'menu' }, movimentados.map(([chave, e, r]) => el('a', { class: 'cartao', href: '#', onclick: (ev) => {
          ev.preventDefault();
          escolher(chave);
          window.scrollTo({ top: 0, behavior: 'smooth' });
        } }, el('div', { class: 'linha1' }, el('span', { class: 'nome', texto: D.rotuloMes(chave) }),
          el('span', { class: 'discreto pequeno', texto: `${D.quantidade(e, 'entrada', 'entradas')} · ${D.quantidade(r, 'recebida', 'recebidas')}` })))))
        : vazio('Nenhuma entrada ou recebimento nos últimos 12 meses.'),
    ];
  }

  function telaMais() {
    const opcao = (href, titulo, detalhe) => el('a', { class: 'cartao', href },
      el('div', { texto: titulo }), el('div', { class: 'discreto pequeno', texto: detalhe }));
    return [el('div', { class: 'menu' },
      opcao('#grafico', 'Gráfico mensal', 'Entradas e recebimentos dos últimos 12 meses'),
      opcao('#lixeira', `Lixeira (${dados.lixeira.length})`, 'Operações excluídas, só para consulta'),
      opcao('#backup', 'Sobre este backup', `Arquivo, data e versões · app ${VERSAO_APP}`),
      opcao('#novidades', 'Novidades', 'O que mudou nas últimas versões'),
      info.independente && opcao('#copia', 'Fazer cópia de segurança', 'Salvar seus dados (trancados) no iCloud ou no Google Drive'),
      opcao('#convite', 'Convidar alguém', 'Mandar o app para outra pessoa usar com os dados dela'),
      senhaRecente && !faceIdAtivo && el('div', { class: 'cartao' },
        el('div', { texto: 'Ativar o Face ID' }), el('div', { class: 'discreto pequeno', texto: 'Abrir o app com o rosto, sem digitar a senha' }),
        el('div', { class: 'botoes' }, el('button', { type: 'button', class: 'primario', texto: 'Ativar',
          onclick: (e) => ativarFaceId(e.target.closest('.cartao')) }))),
      faceIdAtivo && el('a', { class: 'cartao', href: '#', onclick: async (e) => {
        e.preventDefault();
        if (confirm('Desativar o Face ID do app? A próxima abertura pedirá a senha dos backups.')) {
          await FaceId.desativar().catch(() => {});
          faceIdAtivo = false;
          localStorageGravar('faceid_recusado', '1');
          desenhar();
        }
      } }, el('div', { texto: 'Desativar o Face ID' }), el('div', { class: 'discreto pequeno', texto: 'Voltar a abrir só com a senha' })),
      el('button', { type: 'button', class: 'primario', texto: 'Trancar agora', onclick: fecharDados }),
      el('p', { class: 'discreto pequeno', texto: 'Trancar apaga os dados da memória; o backup guardado continua trancado no aparelho. O app também tranca sozinho depois de 5 minutos em segundo plano.' }),
      el('button', { type: 'button', class: 'secundario', texto: 'Apagar o backup guardado neste aparelho', onclick: esquecerBackup }))];
  }

  // O que mudou nas últimas versões (novidades.json, gerado de novidades.py: o mesmo texto do "Sobre" do programa).
  function telaNovidades() {
    const area = el('div', { class: 'menu' }, el('p', { class: 'discreto', texto: 'Carregando…' }));
    fetch('novidades.json').then((r) => r.json()).then(({ versoes }) => {
      area.replaceChildren(...versoes.map((v) => cartao(
        el('div', { class: 'linha1' }, el('span', { class: 'nome', texto: `Versão ${v.versao}` }),
          el('span', { class: 'discreto pequeno', texto: v.resumo })),
        el('ul', { class: 'novidades' }, v.itens.map((item) => el('li', { class: item.tipo },
          el('span', { class: 'selo ' + (item.tipo === 'novidade' ? 'recebida' : 'atrasada'),
            texto: item.tipo === 'novidade' ? 'Novidade' : 'Correção' }), ' ', item.texto))))));
    }).catch(() => {
      area.replaceChildren(el('p', { class: 'discreto', texto: 'Não foi possível carregar as novidades agora.' }));
    });
    return [area];
  }

  // Convite: o link do app, um QR code para quem estiver perto e o passo a passo. Cada pessoa cria a própria
  // senha e os próprios dados; nada do seu celular vai junto.
  const ENDERECO_APP = 'https://vitoran312.github.io/gestor-rpv/';
  const MENSAGEM_CONVITE = 'Use o Gestor RPV no seu iPhone: abra o link no Safari, toque em Compartilhar → '
    + 'Adicionar à Tela de Início e abra pelo ícone. Depois toque em "Começar sem computador" e crie a sua senha.';

  function telaConvite() {
    const resultado = el('p', { class: 'discreto pequeno' });
    const compartilhar = navigator.share
      ? el('button', { type: 'button', class: 'primario', texto: 'Enviar convite', onclick: () => {
        navigator.share({ title: 'Gestor RPV', text: MENSAGEM_CONVITE, url: ENDERECO_APP }).catch(() => {});
      } })
      : el('button', { type: 'button', class: 'primario', texto: 'Copiar convite', onclick: () => {
        navigator.clipboard.writeText(`${MENSAGEM_CONVITE}\n${ENDERECO_APP}`)
          .then(() => { resultado.textContent = 'Convite copiado. Cole no WhatsApp ou no e-mail.'; })
          .catch(() => { resultado.textContent = ENDERECO_APP; });
      } });
    return [
      el('p', { texto: 'Mande o app para outra pessoa: ela cria a própria senha e começa com os dados vazios. Nada do seu celular vai junto.' }),
      compartilhar, resultado,
      el('h2', { texto: 'Ou mostre o QR code' }),
      el('div', { class: 'cartao qr' }, el('img', { src: 'icones/qr-app.svg', alt: 'QR code com o endereço do app' }),
        el('div', { class: 'discreto pequeno', texto: ENDERECO_APP })),
      el('h2', { texto: 'O que a pessoa faz' }),
      el('ol', { class: 'passos' },
        el('li', { texto: 'Abre o link (ou aponta a câmera para o QR code) no Safari do iPhone.' }),
        el('li', { texto: 'Toca em Compartilhar → Adicionar à Tela de Início.' }),
        el('li', { texto: 'Abre o app pelo ícone novo (não pelo Safari).' }),
        el('li', { texto: 'Toca em "Começar sem computador", cria a senha e ativa o Face ID.' })),
    ];
  }

  function telaBackup() {
    const t = info.tempos;
    return [cartao(campos([
      ['Arquivo', info.arquivo],
      ['Criado em', D.dataHora(info.manifesto.criado_em)],
      info.independente ? ['Dados', 'Criados e guardados neste celular']
        : ['Feito no computador pela versão', info.manifesto.versao_app || 'não informada'],
      info.independente && ['Última gravação', D.dataHora(info.manifesto.criado_em)],
      ['Versão deste app', VERSAO_APP],
      ['Protegido por senha', info.cifrado ? 'sim' : 'não'],
      ['Tempo para abrir', `${((Object.values(t).reduce((a, b) => a + b, 0)) / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} s`],
    ])), !info.cifrado && el('p', { class: 'aviso', texto: 'Este backup não tem senha: qualquer pessoa com o arquivo consegue ler os dados. Os backups das versões novas do programa sempre têm senha.' })];
  }

  // ---- Navegação pelo endereço (#tela/parâmetro): o botão voltar do iPhone funciona normalmente ---------
  const TELAS = {
    inicio: { titulo: 'Início', aba: 'inicio', montar: telaInicio },
    operacoes: { titulo: 'Operações', aba: 'operacoes', montar: telaOperacoes },
    operacao: { titulo: 'Operação', aba: 'operacoes', montar: telaOperacao, voltar: true },
    documento: { titulo: 'Documento', aba: 'operacoes', montar: telaDocumento, voltar: true },
    contas: { titulo: 'Contas de recebimento', aba: 'contas', montar: telaContas },
    mais: { titulo: 'Mais', aba: 'mais', montar: telaMais },
    lixeira: { titulo: 'Lixeira', aba: 'mais', montar: telaLixeira, voltar: true },
    grafico: { titulo: 'Gráfico mensal', aba: 'mais', montar: telaGrafico, voltar: true },
    backup: { titulo: 'Sobre este backup', aba: 'mais', montar: telaBackup, voltar: true },
    novidades: { titulo: 'Novidades', aba: 'mais', montar: telaNovidades, voltar: true },
    nova: { titulo: 'Nova entrada', aba: 'operacoes', montar: telaNovaEntrada, voltar: true },
    copia: { titulo: 'Cópia de segurança', aba: 'mais', montar: telaCopia, voltar: true },
    convite: { titulo: 'Convidar alguém', aba: 'mais', montar: telaConvite, voltar: true },
    'nova-conta': { titulo: 'Nova conta', aba: 'contas', montar: telaNovaConta, voltar: true },
    pendentes: { titulo: 'Aguardando o computador', aba: 'operacoes', montar: telaPendentes, voltar: true },
    enviar: { titulo: 'Enviar ao computador', aba: 'operacoes', montar: telaEnviar, voltar: true, textual: true },
  };

  function desenhar() {
    if (!dados) {
      return;
    }
    const [nome, parametro] = location.hash.slice(1).split('/');
    const tela = TELAS[nome] || TELAS.inicio;
    const id = tela.textual ? parametro : Number(parametro);
    liberarDocumento();
    $('titulo').textContent = tela.titulo;
    // A barra de zoom dos documentos fica logo abaixo do cabeçalho fixo.
    document.documentElement.style.setProperty('--altura-topo', `${document.querySelector('.topo').offsetHeight}px`);
    $('voltar').hidden = !tela.voltar;
    document.querySelectorAll('.abas a').forEach((a) => a.classList.toggle('ativa', a.dataset.aba === tela.aba));
    $('tela').replaceChildren(...[tela.montar(id)].flat(2).filter(Boolean));
    if (tela === TELAS.operacao && dados.operacoes.concat(dados.lixeira).some((r) => r.id === id)) {
      const r = dados.operacoes.find((o) => o.id === id) || dados.lixeira.find((o) => o.id === id);
      $('titulo').textContent = r.nome;
    }
    if (tela === TELAS.documento && documentoPorId(id)) {
      $('titulo').textContent = documentoPorId(id).nome;
    }
    window.scrollTo(0, 0);
  }

  $('voltar').addEventListener('click', () => history.back());
  window.addEventListener('hashchange', desenhar);

  $('versao-app').textContent = `Versão ${VERSAO_APP}`;


  // ---- Abertura do app: com Face ID ativo, já pede o rosto ------------------------------------------------
  // O logo aparece sozinho primeiro; só depois da animação o app pede o Face ID (a janela do iPhone cobre boa
  // parte da tela). O logo continua ao fundo enquanto o Face ID é pedido e esmaece quando o app já está pronto:
  // no Início, se o Face ID deu certo, ou na tela de desbloqueio.
  const ANIMACAO_LOGO_MS = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 300 : 1200;
  const esperar = (ms) => new Promise((ok) => setTimeout(ok, ms));

  function esconderSplash() {
    const splash = $('splash');
    if (!splash) {
      return;
    }
    splash.classList.add('sumindo');
    setTimeout(() => splash.remove(), 700);
  }

  Promise.all([prepararAbertura(), esperar(ANIMACAO_LOGO_MS)]).then(async ([faceId]) => {
    if (faceId) {
      await abrirFonte({ faceId: true, automatico: true });
    }
    esconderSplash();
  }, esconderSplash);

  // ---- App na Tela de Início -----------------------------------------------------------------------------
  const instalado = window.navigator.standalone === true || window.matchMedia('(display-mode: standalone)').matches;
  $('instalar').hidden = instalado;
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js').catch(() => {
      // Sem o service worker o app funciona igual, só não abre sem internet.
    });
  }
})();
