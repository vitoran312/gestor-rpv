// Telas do app (só consulta). O backup fica guardado no aparelho como saiu do computador (trancado pela
// senha); os dados abertos ficam só na memória desta página e somem ao trancar ou fechar o app.
//
// Todo texto vindo do backup entra na página por textContent (nunca como HTML).
'use strict';

(() => {
  // Igual a versao.py (test_celular confere): mostrada na abertura e em Mais, para saber se o aparelho já
  // carregou a última versão publicada.
  const VERSAO_APP = '0.61.0';
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
  const estado = { busca: '', filtro: 'todas', mes: null, dia: null };
  // Modo discreto: os valores em reais aparecem como "R$ •••••" (para usar o app em público ou mostrar a tela a
  // alguém). Fica ligado entre aberturas; os campos dos formulários continuam mostrando o que se digita.
  let discreto = false;
  const reais = (valor) => (discreto ? 'R$ •••••' : D.reais(valor));  // mes e dia: os escolhidos na agenda.

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

  // Ícones de traço (24 × 24), desenhados aqui: nada de arquivos nem fontes de ícones.
  const ICONES = {
    tendencia: ['M4 17l5-5 4 4 7-7', 'M15 9h5v5'],
    documento: ['M7 3.5h7l4 4v13H7z', 'M14 3.5V8h4', 'M10 12.5h5M10 16h5'],
    moedas: ['M5 7c0-1.4 3.1-2.5 7-2.5s7 1.1 7 2.5-3.1 2.5-7 2.5S5 8.4 5 7z',
      'M5 7v5c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V7', 'M5 12v5c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-5'],
    dinheiro: ['M12 3.5v17', 'M16 7.5c-.7-1.3-2.2-2-4-2-2.3 0-4 1.1-4 3s1.8 2.6 4 3 4 1.2 4 3.1-1.8 3-4.1 3c-2 0-3.5-.8-4.2-2.2'],
    calendario: ['M4.5 6.5h15v13h-15z', 'M4.5 10.5h15', 'M8.5 4v4M15.5 4v4'],
    barras: ['M4 20.5h16', 'M6.5 17v-5M11 17V7M15.5 17v-7M20 17V9.5'],
    lixeira: ['M4.5 7h15', 'M9.5 7V4.5h5V7', 'M6.5 7l1 13h9l1-13', 'M10.5 11v5.5M13.5 11v5.5'],
    info: ['M12 3.5a8.5 8.5 0 1 1 0 17 8.5 8.5 0 0 1 0-17z', 'M12 11v5.5', 'M12 7.8v.01'],
    megafone: ['M4 10v4h3l7 4V6l-7 4z', 'M17.5 9.5a3.5 3.5 0 0 1 0 5'],
    convidar: ['M9 4.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7z', 'M3 19.5c.8-3.2 3.3-5 6-5s5.2 1.8 6 5', 'M18.5 8v6M15.5 11h6'],
    escudo: ['M12 3.5l7 2.5v5.5c0 4.3-3 7.6-7 9-4-1.4-7-4.7-7-9V6z', 'M9 12l2 2 4-4'],
    enviar: ['M12 15V4.5M8 8.5l4-4 4 4', 'M5 14.5v5h14v-5'],
    rosto: ['M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16',
      'M9 9.5v1M15 9.5v1M12 9.5V13h-1M9.5 15.5c1.4 1 3.6 1 5 0'],
    cadeado: ['M6 10.5h12v10H6z', 'M8.5 10.5v-3a3.5 3.5 0 0 1 7 0v3'],
    celular: ['M8 3.5h8v17H8z', 'M11 17.5h2'],
    seta: ['M9 5.5l6.5 6.5L9 18.5'],
  };

  function icone(nome, classe = 'icone') {
    const NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('class', classe);
    svg.setAttribute('aria-hidden', 'true');
    for (const d of ICONES[nome]) {
      const traco = document.createElementNS(NS, 'path');
      traco.setAttribute('d', d);
      svg.append(traco);
    }
    return svg;
  }

  // Aviso passageiro acima das abas, depois de gravar algo no celular: um de cada vez (o novo substitui o atual).
  let temporizadorAviso = null;
  function avisar(texto) {
    let toast = $('toast');
    if (!toast) {
      toast = el('div', { id: 'toast', class: 'toast', role: 'status', 'aria-live': 'polite' });
      document.body.append(toast);
    }
    toast.textContent = texto;
    void toast.offsetWidth;  // Garante a transição também quando o aviso anterior ainda some.
    toast.classList.add('visivel');
    clearTimeout(temporizadorAviso);
    temporizadorAviso = setTimeout(() => toast.classList.remove('visivel'), 2600);
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
  let mostrarNuvem = false;  // A pessoa tocou em "Recuperar meus dados da nuvem".

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
    $('ver-demonstracao').hidden = Boolean(guardado);
    $('trocar-backup').textContent = guardado && guardado.independente ? 'Restaurar uma cópia de segurança'
      : 'Trocar por um backup mais novo';
    // Primeira vez: além de abrir um backup do computador, dá para começar só no celular.
    $('comecar').hidden = Boolean(guardado || (fonte && fonte.novo)) || mostrarNovo;
    // Num passo da abertura (criar a senha, digitar a senha, escolher outro arquivo), dá para voltar ao início dela.
    $('voltar-abertura').hidden = !emPassoDaAbertura();
    $('form-novo').hidden = !mostrarNovo || Boolean(guardado);
    if (mostrarNovo && !guardado) {
      $('formulario').hidden = true;
      $('explicacao').hidden = true;
    }
    // Celular novo: recuperar o backup que o app mandava para a nuvem.
    $('recuperar-nuvem').hidden = Boolean(guardado || (fonte && fonte.novo)) || mostrarNovo || mostrarNuvem;
    $('form-nuvem').hidden = !mostrarNuvem || Boolean(guardado);
    if (mostrarNuvem && !guardado) {
      ['formulario', 'explicacao', 'comecar', 'ver-demonstracao'].forEach((id) => { $(id).hidden = true; });
    }
    return faceId;
  }

  let mostrarArquivo = false;  // A pessoa tocou em "Trocar por um backup mais novo".
  let mostrarSenha = false;    // A pessoa tocou em "Usar a senha" (com Face ID ativo).

  function emPassoDaAbertura() {
    return Boolean(mostrarNovo || mostrarNuvem || mostrarArquivo || mostrarSenha || (fonte && fonte.novo && guardadoAtual));
  }

  // Cada passo da abertura entra no histórico: o gesto ou a tecla de voltar do aparelho também volta dele.
  function entrarNoPasso() {
    if (!emPassoDaAbertura()) {
      history.pushState({ passo: true }, '', location.pathname + location.search + '#passo');
    }
  }

  function sairDoPasso() {
    mostrarNovo = false;
    mostrarNuvem = false;
    mostrarArquivo = false;
    mostrarSenha = false;
    if (fonte && fonte.novo) {
      fonte = null;
    }
    mostrarErro('');
    $('form-novo').reset();
    $('arquivo').value = '';
    return prepararAbertura();
  }

  $('voltar-abertura').addEventListener('click', () => {
    if (history.state && history.state.passo) {
      history.back();  // O popstate abaixo desfaz o passo.
    } else {
      sairDoPasso();
    }
  });
  window.addEventListener('popstate', () => {
    if (!$('abertura').hidden && emPassoDaAbertura()) {
      sairDoPasso();
    }
  });

  $('trocar-backup').addEventListener('click', () => {
    entrarNoPasso();
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
    entrarNoPasso();
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

  $('recuperar-nuvem').addEventListener('click', () => {
    entrarNoPasso();
    mostrarNuvem = true;
    prepararAbertura().then(() => $('senha-nuvem').focus());
  });

  $('form-nuvem').addEventListener('submit', async (evento) => {
    evento.preventDefault();
    const senha = $('senha-nuvem').value;
    if (!senha) {
      mostrarErro('Digite a senha.');
      return;
    }
    mostrarErro('');
    $('baixar-nuvem').disabled = true;
    try {
      const cred = await Nuvem.credenciais(senha, (p) => mostrarAndamento('Conferindo a senha…', p * 0.5));
      mostrarAndamento('Procurando na nuvem…', 0.5);
      const meta = await Nuvem.consultar(cred);
      if (!meta) {
        throw new Error('Nenhum backup na nuvem com essa senha. Confira a senha (maiúsculas, acentos e espaços contam).');
      }
      const bytes = await Nuvem.baixar(cred, meta, (p) => mostrarAndamento('Baixando os dados…', 0.5 + p * 0.4));
      await guardarNuvem({ ...cred, backup: true, lembretes: false });
      gravarEstadoNuvem({ criado_em: meta.criado_em });
      fonte = { bytes, nome: 'GestorRPV-celular.rpvbackup', tamanho: bytes.length, criado_em: meta.criado_em, novo: true };
      mostrarNuvem = false;
      $('form-nuvem').reset();
      await abrirFonte({ senha });
    } catch (erro) {
      $('andamento').hidden = true;
      mostrarErro(erro && erro.message ? erro.message : String(erro));
    } finally {
      $('baixar-nuvem').disabled = false;
    }
  });

  $('usar-senha').addEventListener('click', () => {
    entrarNoPasso();
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
        tempos: leitura.tempos, extrair: leitura.extrair, todos: leitura.todos, chave: leitura.chave, independente };
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
      } else if (location.hash === '#passo') {
        location.replace('#inicio');  // O passo da abertura não fica no histórico do app aberto.
      } else {
        location.hash = '#inicio';
      }
      aposAbrirDados();
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

  // ---- Demonstração: dados fictícios na primeira abertura --------------------------------------------------
  // Quem ainda não tem dados neste aparelho vê o app funcionando com os dados fictícios do programa
  // (demonstracao.sqlite3, gerado por gerar_modelo_celular.py), sem senha e só para consulta. As datas são
  // deslocadas para hoje, como o programa faz: sempre há operações pendentes, atrasadas e recebidas.
  let demonstracaoDispensada = false;  // A pessoa saiu da demonstração: não volta sozinha até o app ser aberto de novo.

  async function abrirDemonstracao() {
    const SQL = await LeitorBackup.sqlJs();
    const db = new SQL.Database(new Uint8Array(await (await fetch('demonstracao.sqlite3')).arrayBuffer()));
    try {
      const referencia = db.exec("SELECT valor FROM configuracoes WHERE chave='demonstracao_referencia'")[0].values[0][0];
      const [ano, mes, dia] = referencia.split('-').map(Number);
      const [ha, hm, hd] = D.hojeIso().split('-').map(Number);
      const dias = Math.round((Date.UTC(ha, hm - 1, hd) - Date.UTC(ano, mes - 1, dia)) / 86400000);
      const mudar = `${dias >= 0 ? '+' : ''}${dias} days`;
      db.run(`UPDATE rpvs SET aquisicao=date(aquisicao, $d), previsao=date(previsao, $d),
        previsao_atual_definida=date(previsao_atual_definida, $d), recebimento=date(recebimento, $d)`, { $d: mudar });
      db.run('UPDATE previsoes_historico SET anterior=date(anterior, $d), nova=date(nova, $d)', { $d: mudar });
      db.run('UPDATE prorrogacoes SET data=date(data, $d)', { $d: mudar });
      dados = D.carregar(db);
    } finally {
      db.close();
    }
    const nenhum = () => Promise.reject(new LeitorBackup.ErroBackup('A demonstração não tem documentos.'));
    info = { arquivo: 'Demonstração', tamanho: 0, manifesto: { criado_em: LeitorBackup.dataHoraLocal() }, cifrado: false,
      tempos: {}, extrair: nenhum, todos: async () => ({}), chave: null, independente: false, demonstracao: true };
    listaPendentes = [];
    abertasPendentes.clear();
    $('abertura').hidden = true;
    $('aplicativo').hidden = false;
    if (location.hash === '#inicio') {
      desenhar();
    } else {
      location.hash = '#inicio';
    }
  }

  // Para os testes automáticos: tranca como o app faz sozinho depois de 5 minutos em segundo plano.
  window.trancarGestor = () => fecharDados();

  function sairDaDemonstracao() {
    demonstracaoDispensada = true;
    return fecharDados();
  }

  $('ver-demonstracao').addEventListener('click', () => {
    abrirDemonstracao().catch((erro) => mostrarErro('Não foi possível abrir a demonstração: ' + (erro && erro.message ? erro.message : erro)));
  });

  // Em Mais: escolher um backup mais novo (ou uma cópia de segurança) sem precisar recusar o Face ID. O app volta à
  // abertura com o arquivo escolhido e, com Face ID ativo, já pede o rosto para abri-lo.
  async function trocarPorArquivo(arquivo) {
    const escolhido = { bytes: await arquivo.arrayBuffer(), nome: arquivo.name, tamanho: arquivo.size, novo: true };
    demonstracaoDispensada = true;
    await fecharDados();
    fonte = escolhido;
    mostrarArquivo = true;
    if (await prepararAbertura()) {
      await abrirFonte({ faceId: true, automatico: true });
    } else {
      $('senha').focus();
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
    clearTimeout(temporizadorNuvem);
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
    estado.mes = null;
    estado.dia = null;
    $('tela').replaceChildren();
    caminho.length = 0;
    telaAnimada = null;
    telaAnterior = null;
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
    // A demonstração não tem o que trancar: continua aberta.
    if (dados && info && !info.demonstracao && escondidoEm && Date.now() - escondidoEm > BLOQUEIO_MS) {
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
    const indicador = (rotulo, valor, classe, simbolo) => el('div', { class: 'indicador ' + (classe || '') },
      el('span', { class: 'icone-indicador' }, icone(simbolo)),
      el('div', { class: 'textos' }, el('div', { class: 'rotulo', texto: rotulo }), el('div', { class: 'valor', texto: valor })));
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
      dados.demonstracao && !info.demonstracao && el('p', { class: 'aviso', texto: 'Este backup tem dados de demonstração, com nomes e valores fictícios.' }),
      info.independente && !dados.operacoes.length && el('div', { class: 'aviso' },
        el('div', { class: 'nome', texto: 'Por onde começar' }),
        el('div', { texto: '1. Cadastre a conta onde você recebe, na aba Contas.' }),
        el('div', { texto: '2. Cadastre suas entradas na aba Operações (+ Nova entrada).' }),
        el('div', { texto: '3. Quando receber, abra a operação e toque em "Registrar recebimento".' })),
      !info.independente && !info.demonstracao && dias !== null && dias > 7 && el('p', { class: 'aviso', texto: 'Este backup tem mais de uma semana. Faça um backup novo no computador para ver os dados atuais.' }),
      // O título da página, de onde vêm os dados e os quatro indicadores: o lucro previsto em terracota.
      el('section', { class: 'panorama' },
        el('div', { class: 'saudacao', texto: 'Olá!' }),
        el('h2', { class: 'panorama-titulo', texto: 'Seu panorama' }),
        !info.demonstracao && el('p', { class: 'panorama-fonte', texto: info.independente ? 'Seus dados, guardados neste celular.'
          : `Dados do backup de ${D.dataHora(info.manifesto.criado_em)}${idade}.` })),
      el('div', { class: 'indicadores' },
        indicador('Lucro previsto', reais(ind.previsto), 'principal', 'tendencia'),
        indicador('Registros', String(ind.registros), '', 'documento'),
        indicador('Capital investido em aberto', reais(ind.aberto), '', 'moedas'),
        indicador('Lucro realizado', reais(ind.realizado), 'verde', 'dinheiro')),
      dados.operacoes.length > 0 && cartaoAgenda(),
      el('h2', { texto: 'Situação das operações' }),
      el('div', { class: 'situacoes' },
        situacao('pendente', 'Pendentes'),
        situacao('atrasada', 'Atrasadas', totais.atrasada ? 'vermelho' : ''),
        situacao('recebida', 'Recebidas', 'verde')),
    ];
  }

  // ---- Agenda das previsões ------------------------------------------------------------------------------
  const DIAS_SEMANA = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado'];

  function nomeDoDia(iso, hoje) {
    const [ano, mes, dia] = iso.split('-').map(Number);
    const semana = DIAS_SEMANA[new Date(ano, mes - 1, dia).getDay()];
    const prefixo = iso === hoje ? 'Hoje, ' : iso === D.somarDias(hoje, 1) ? 'Amanhã, ' : iso === D.somarDias(hoje, -1) ? 'Ontem, ' : '';
    return `${prefixo}${semana} ${D.dataBr(iso).slice(0, 5)}`;
  }

  // No Início: quantas previsões estão atrasadas, são hoje, amanhã e nos próximos dias, com os nomes de hoje e amanhã.
  function cartaoAgenda() {
    const hoje = D.hojeIso();
    const ag = D.agenda(dados.operacoes, hoje);
    const bloco = (rotulo, lista, classe, tom) => el('div', { class: 'bloco-agenda ' + tom },
      el('div', { class: 'numero ' + (lista.length && classe ? classe : ''), texto: String(lista.length) }),
      el('div', { class: 'discreto pequeno', texto: rotulo }));
    const nomes = (rotulo, lista) => lista.length > 0 && el('div', { class: 'pequeno nomes-agenda' },
      el('strong', { texto: `${rotulo}: ` }), lista.slice(0, 3).map((r) => r.nome).join(', ')
        + (lista.length > 3 ? ` e mais ${lista.length - 3}` : ''));
    return el('a', { class: 'cartao agenda-resumo', href: '#agenda' },
      el('div', { class: 'linha1' }, el('span', { class: 'nome', texto: 'Agenda das previsões' }),
        el('span', { class: 'mostrar pequeno', texto: 'Ver calendário ›' })),
      el('div', { class: 'blocos-agenda' }, bloco('Atrasadas', ag.atrasadas, 'vermelho', 'atrasadas'),
        bloco('Hoje', ag.hoje, 'marca', 'hoje'), bloco('Amanhã', ag.amanha, 'marca', 'amanha'),
        bloco('Próx. 7 dias', ag.semana, '', 'semana')),
      nomes('Hoje', ag.hoje), nomes('Amanhã', ag.amanha),
      !ag.atrasadas.length && !ag.hoje.length && !ag.amanha.length && !ag.semana.length
        && el('div', { class: 'discreto pequeno', texto: 'Nenhuma previsão para os próximos 7 dias.' }));
  }

  // Calendário do mês com as previsões das operações ainda não recebidas; tocar num dia mostra as operações dele.
  function telaAgenda() {
    const hoje = D.hojeIso();
    const ag = D.agenda(dados.operacoes, hoje);
    estado.mes = estado.mes || hoje.slice(0, 7);
    estado.dia = estado.dia || hoje;
    const area = el('div');
    const desenharAgenda = () => {
      const mudarMes = (passo) => {
        estado.mes = D.mesVizinho(estado.mes, passo);
        estado.dia = estado.mes === hoje.slice(0, 7) ? hoje : `${estado.mes}-01`;
        desenharAgenda();
      };
      const dia = (iso) => {
        if (!iso) {
          return el('div', { class: 'dia fora' });
        }
        const lista = ag.porDia.get(iso) || [];
        const classes = ['dia', iso === hoje && 'hoje', iso === estado.dia && 'escolhido',
          lista.length && (iso < hoje ? 'com-atraso' : 'com-previsao')].filter(Boolean).join(' ');
        return el('button', { type: 'button', class: classes, 'data-dia': iso,
          'aria-label': `${nomeDoDia(iso, hoje)}: ${D.quantidade(lista.length, 'previsão', 'previsões')}`,
          onclick: () => {
            estado.dia = iso;
            desenharAgenda();
          } }, el('span', { texto: String(Number(iso.slice(8))) }),
        el('span', { class: 'marca-dia', texto: lista.length > 1 ? String(lista.length) : lista.length ? '•' : '' }));
      };
      const doDia = ag.porDia.get(estado.dia) || [];
      area.replaceChildren(
        el('div', { class: 'cartao calendario' },
          el('div', { class: 'mes-agenda' },
            el('button', { type: 'button', class: 'secundario', 'aria-label': 'Mês anterior', texto: '‹', onclick: () => mudarMes(-1) }),
            el('span', { class: 'nome', texto: D.nomeDoMes(estado.mes) }),
            el('button', { type: 'button', class: 'secundario', 'aria-label': 'Próximo mês', texto: '›', onclick: () => mudarMes(1) })),
          el('div', { class: 'grade-agenda' },
            DIAS_SEMANA.map((d) => el('div', { class: 'dia-semana', texto: d.slice(0, 3) })),
            D.semanasDoMes(estado.mes).flat().map(dia))),
        el('h2', { texto: nomeDoDia(estado.dia, hoje) }),
        doDia.length ? el('div', { class: 'lista' }, doDia.map((r) => itemOperacao(r, `#operacao/${r.id}`)))
          : vazio(estado.dia < hoje ? 'Nenhuma operação atrasada com previsão neste dia.' : 'Nenhuma previsão neste dia.'));
    };
    desenharAgenda();
    return [
      el('p', { class: 'discreto pequeno', texto: 'Previsões atuais das operações ainda não recebidas. Dias em vermelho têm operações atrasadas.' }),
      area,
      ag.atrasadas.length > 0 && [el('h2', { texto: `Atrasadas (${ag.atrasadas.length})` }),
        el('div', { class: 'lista' }, ag.atrasadas.map((r) => itemOperacao(r, `#operacao/${r.id}`)))],
    ];
  }

  function itemOperacao(r, destino) {
    const s = D.situacao(r);
    const adiada = r.previsao_atual > r.previsao;
    // As iniciais do avatar vêm de um atributo (desenhadas pelo CSS): não entram no texto lido da tela.
    return el('a', { class: `cartao item operacao ${s}`, href: destino },
      el('span', { class: 'avatar', 'data-iniciais': iniciais(r.nome), 'aria-hidden': 'true' }),
      el('div', { class: 'corpo' },
        el('div', { class: 'linha1' }, el('span', { class: 'nome', texto: r.nome }),
          el('span', { class: `selo ${s}`, texto: SITUACOES[s] })),
        el('div', { class: 'linha2' },
          el('span', { class: 'valor-principal', texto: reais(r.previsto) }),
          el('span', { class: 'discreto', texto: r.recebimento ? `Recebida em ${D.dataBr(r.recebimento)}`
            : `Previsão ${D.dataBr(r.previsao_atual)}${adiada ? ' (adiada)' : ''}` })),
        el('div', { class: 'linha2 discreto' },
          el('span', { texto: `Lucro ${reais(r.previsto - r.custo)}` }),
          el('span', { texto: `Aquisição ${D.dataBr(r.aquisicao)}` }))),
      icone('seta', 'seta'));
  }

  // "Gabriel Henrique Timoteo" → "GT": a primeira e a última palavra (de, da, dos... não contam).
  function iniciais(nome) {
    const palavras = nome.split(/\s+/).filter((p) => p && !/^(d[aeo]s?|e)$/i.test(p));
    const letras = palavras.length > 1 ? [palavras[0], palavras[palavras.length - 1]] : palavras;
    return letras.map((p) => Array.from(p)[0].toUpperCase()).join('');
  }

  function telaOperacoes() {
    const lista = el('div', { class: 'lista' });
    const filtros = el('div', { class: 'filtros' });
    const desenharLista = ({ animar = false } = {}) => {
      const encontrados = D.filtrar(dados.operacoes, estado.busca);
      const totais = D.contarSituacoes(encontrados);
      filtros.replaceChildren(...FILTROS.map(([chave, rotulo]) => el('button', {
        type: 'button', class: chave === estado.filtro ? 'ativo' : '', texto: `${rotulo} ${totais[chave]}`,
        onclick: () => {
          estado.filtro = chave;
          desenharLista({ animar: true });
        } })));
      const visiveis = estado.filtro === 'todas' ? encontrados : encontrados.filter((r) => D.situacao(r) === estado.filtro);
      lista.replaceChildren(...(visiveis.length ? visiveis.map((r) => itemOperacao(r, `#operacao/${r.id}`))
        : [vazio(estado.busca ? 'Nenhuma operação encontrada.' : 'Nenhuma operação nesta situação.')]));
      // Trocar de filtro: só a lista faz o crossfade (digitar na busca não anima, para não piscar a cada letra).
      if (animar) {
        lista.classList.remove('trocando');
        void lista.offsetWidth;
        lista.classList.add('trocando');
      }
    };
    const busca = el('input', { class: 'busca', type: 'search', placeholder: 'Buscar nome, conta ou data',
      value: estado.busca, autocomplete: 'off', oninput: (e) => {
        estado.busca = e.target.value;
        desenharLista();
      } });
    desenharLista();
    // Contas aparecem na aba Contas; aqui, entradas e mudanças em operações.
    const itens = listaPendentes.filter((p) => (p.tipo || 'entrada') !== 'conta');
    const quantas = itens.length;
    const soEntradas = itens.every((p) => (p.tipo || 'entrada') === 'entrada');
    const pendentes = quantas > 0 && el('a', { class: 'aviso item com-icone', href: '#pendentes' },
      icone('celular'),
      el('div', { class: 'nome', texto: soEntradas
        ? (quantas === 1 ? '1 entrada feita no celular aguarda o computador' : `${quantas} entradas feitas no celular aguardam o computador`)
        : (quantas === 1 ? '1 mudança feita no celular aguarda o computador' : `${quantas} itens feitos no celular aguardam o computador`) }),
      el('div', { class: 'discreto pequeno', texto: 'Toque para ver ou enviar de novo' }), icone('seta', 'seta'));
    const nova = el('a', { class: 'botao-link primario', href: '#nova', texto: '+ Nova entrada' });
    return [nova, pendentes, busca, filtros, lista];
  }

  // ---- Entradas feitas no celular ----------------------------------------------------------------------
  // Cada entrada vira um arquivo .rpvcelular, cifrado com a chave do backup aberto (o computador abre com a
  // senha dos backups). O arquivo fica guardado aqui até um backup mais novo mostrar que o computador já o
  // importou (configuração entradas_celular_importadas); até lá, pode ser enviado de novo.
  let listaPendentes = [];          // [{id, arquivo, criada_em, bytes}] como guardadas no aparelho.
  // Entradas e contas novas, e mudanças em operações que já existem no computador (entradas_celular.py).
  const TIPOS_PENDENTES = ['entrada', 'conta', 'alteracao', 'previsao', 'exclusao', 'anexo'];
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
        const tipo = TIPOS_PENDENTES.find((t) => pacote[t]);
        abertasPendentes.set(p.id, { ...pacote[tipo], tipo });
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
  // `novos` traz os anexos acrescentados agora ({caminho: bytes}); os que já existiam vão junto, menos os `removidos`.
  async function salvarLocal(novos = {}, removidos = []) {
    const banco = bancoLocal.export();
    const anexos = { ...await info.todos(), ...novos };
    removidos.forEach((caminho) => delete anexos[caminho]);
    const { bytes, manifesto, extrair, todos } = await LeitorBackup.empacotar(banco, info.chave, VERSAO_APP, anexos);
    fonte = { ...fonte, bytes, tamanho: bytes.length, criado_em: manifesto.criado_em, independente: true };
    await Guarda.gravar('backup', { bytes, nome: fonte.nome, tamanho: bytes.length, criado_em: manifesto.criado_em,
      guardado_em: new Date().toISOString(), independente: true });
    Guarda.persistir();
    Object.assign(info, { manifesto, extrair, todos });
    dados = D.carregar(bancoLocal);
    localStorageGravar('copia_pendente', '1');
    agendarEnvioNuvem();
    sincronizarLembretes();
  }

  // ---- Nuvem: backup automático e lembretes (celular/nuvem.js) ------------------------------------------
  // `nuvem` ({id, chave, backup, lembretes}) fica guardado no aparelho: as credenciais saem da senha uma vez só.
  let nuvem = null;
  let temporizadorNuvem = null;
  let enviandoNuvem = null;

  const estadoNuvem = () => {
    try {
      return JSON.parse(localStorageLer('nuvem_estado') || '{}');
    } catch (erro) {
      return {};
    }
  };
  const gravarEstadoNuvem = (estado) => localStorageGravar('nuvem_estado', JSON.stringify(estado));

  async function carregarNuvem() {
    nuvem = await Guarda.ler('nuvem').catch(() => null) || null;
  }

  async function guardarNuvem(valor) {
    nuvem = valor;
    await Guarda.gravar('nuvem', valor);
  }

  function redesenharMais() {
    if (dados && location.hash === '#mais') {
      const rolagem = window.scrollY;
      desenhar();
      window.scrollTo(0, rolagem);
    }
  }

  // Um envio por vez, logo depois da última gravação (várias seguidas viram um envio só).
  function agendarEnvioNuvem(atraso = 1200) {
    if (!nuvem || !nuvem.backup || !info || !info.independente) {
      return;
    }
    clearTimeout(temporizadorNuvem);
    temporizadorNuvem = setTimeout(() => enviarNuvem().catch(() => {}), atraso);
  }

  async function enviarNuvem({ substituir = false } = {}) {
    if (!info || !info.independente || !nuvem) {
      return;
    }
    if (enviandoNuvem) {
      await enviandoNuvem.catch(() => {});
    }
    const criadoEm = info.manifesto.criado_em;
    enviandoNuvem = (async () => {
      try {
        await Nuvem.enviar(nuvem, new Uint8Array(fonte.bytes), { sal: info.chave.sal, criadoEm, substituir });
        gravarEstadoNuvem({ enviado_em: LeitorBackup.dataHoraLocal(), criado_em: criadoEm });
      } catch (erro) {
        gravarEstadoNuvem({ ...estadoNuvem(), erro: erro.message, conflito: Boolean(erro.conflito), outro_em: erro.criadoEm || null });
        throw erro;
      } finally {
        enviandoNuvem = null;
        redesenharMais();
      }
    })();
    return enviandoNuvem;
  }

  // Depois de abrir os dados: o que ficou sem enviar (sem internet na hora) vai agora; os lembretes são conferidos.
  async function aposAbrirDados() {
    await carregarNuvem();
    if (nuvem && nuvem.backup && info.independente && estadoNuvem().criado_em !== info.manifesto.criado_em) {
      agendarEnvioNuvem(0);
    }
    sincronizarLembretes();
  }

  const lembretesPossiveis = () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  const datasDasPrevisoes = () => dados.operacoes.filter((r) => !r.recebimento).map((r) => r.previsao_atual).sort();

  function deB64url(texto) {
    const base = texto.replace(/-/g, '+').replace(/_/g, '/');
    return Uint8Array.from(atob(base + '='.repeat((4 - (base.length % 4)) % 4)), (c) => c.charCodeAt(0));
  }

  // As datas mudaram (entrada nova, previsão alterada, recebimento)? Manda a lista nova para a nuvem.
  async function sincronizarLembretes({ forcar = false } = {}) {
    if (!nuvem || !nuvem.lembretes || !dados || !lembretesPossiveis() || Notification.permission !== 'granted') {
      return;
    }
    try {
      const registro = await navigator.serviceWorker.ready;
      const assinatura = await registro.pushManager.getSubscription();
      if (!assinatura) {
        return;
      }
      const previsoes = datasDasPrevisoes();
      const marca = `${nuvem.id}|${assinatura.endpoint}|${previsoes.join(',')}`;
      if (!forcar && localStorageLer('lembretes_enviados') === marca) {
        return;
      }
      await Nuvem.guardarLembretes(nuvem, assinatura.toJSON(), previsoes);
      localStorageGravar('lembretes_enviados', marca);
    } catch (erro) {
      // Sem internet agora: a lista vai na próxima gravação ou abertura.
    }
  }

  // O pedido de permissão precisa ser a primeira coisa do toque: por isso as credenciais já estão prontas aqui.
  async function ligarLembretes() {
    const permissao = await Notification.requestPermission();
    if (permissao !== 'granted') {
      throw new Error('As notificações não foram permitidas. Ative em Ajustes → Notificações → Gestor RPV.');
    }
    const registro = await navigator.serviceWorker.ready;
    const assinatura = await registro.pushManager.getSubscription()
      || await registro.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: deB64url(await Nuvem.chaveVapid()) });
    await Nuvem.guardarLembretes(nuvem, assinatura.toJSON(), datasDasPrevisoes());
    await guardarNuvem({ ...nuvem, lembretes: true });
    localStorageGravar('lembretes_enviados', '');
  }

  async function desligarLembretes() {
    const registro = await navigator.serviceWorker.ready.catch(() => null);
    const assinatura = registro && await registro.pushManager.getSubscription().catch(() => null);
    if (assinatura) {
      await assinatura.unsubscribe().catch(() => {});
    }
    await Nuvem.apagarLembretes(nuvem).catch(() => {});
    await guardarNuvem({ ...nuvem, lembretes: false });
  }

  function inserir(tabela, linha) {
    const campos = Object.keys(linha);
    bancoLocal.run(`INSERT INTO ${tabela} (${campos.join(',')}) VALUES (${campos.map(() => '?').join(',')})`,
      campos.map((k) => linha[k]));
    return bancoLocal.exec('SELECT last_insert_rowid()')[0].values[0][0];
  }

  // Como Banco.salvar: nome com iniciais maiúsculas, observação com a primeira maiúscula e a cópia dos dados da
  // conta guardada na operação.
  async function gravarEntradaLocal(entrada, conta, documentos = []) {
    const id = inserir('rpvs', {
      nome: D.nomeTitulo(entrada.nome), aquisicao: entrada.aquisicao, previsto: entrada.previsto, custo: entrada.custo,
      conta: conta.identificacao, previsao: entrada.previsao, comissao: entrada.comissao,
      observacoes: D.primeiraMaiuscula(entrada.observacoes), conta_id: conta.id, conta_snapshot: D.snapshotConta(conta),
    });
    await salvarLocal(registrarDocumentos(id, documentos));
    avisar('Entrada salva.');
    return id;
  }

  // Como Banco.salvar com um identificador: a conta (e a cópia dos dados dela) só muda se outra foi escolhida.
  async function editarLocal(r, entrada, conta) {
    const mesma = conta.manter || conta.id === r.conta_id;
    bancoLocal.run(`UPDATE rpvs SET nome=?, aquisicao=?, previsto=?, custo=?, previsao=?, comissao=?, observacoes=?,
      conta=?, conta_id=?, conta_snapshot=? WHERE id=? AND lixeira_em IS NULL`, [
      D.nomeTitulo(entrada.nome), entrada.aquisicao, entrada.previsto, entrada.custo, entrada.previsao, entrada.comissao,
      D.primeiraMaiuscula(entrada.observacoes), mesma ? r.conta : conta.identificacao, mesma ? r.conta_id : conta.id,
      mesma ? r.conta_snapshot : D.snapshotConta(conta), r.id]);
    await salvarLocal();
    avisar('Alterações salvas.');
  }

  // Como Banco.atualizar_previsao: a previsão anterior fica no histórico.
  async function previsaoLocal(r, nova) {
    bancoLocal.run('INSERT INTO previsoes_historico (rpv_id,anterior,nova,alterada_em) VALUES (?,?,?,?)',
      [r.id, r.previsao_atual, nova, LeitorBackup.dataHoraLocal()]);
    bancoLocal.run('UPDATE rpvs SET previsao_atual_definida=? WHERE id=?', [nova, r.id]);
    await salvarLocal();
    avisar('Previsão atualizada.');
  }

  // Excluir manda para a lixeira (como no computador); restaurar tira de lá.
  async function lixeiraLocal(r, excluir) {
    bancoLocal.run('UPDATE rpvs SET lixeira_em=? WHERE id=?', [excluir ? LeitorBackup.dataHoraLocal() : null, r.id]);
    await salvarLocal();
    avisar(excluir ? 'Operação enviada à lixeira.' : 'Operação restaurada.');
  }

  // Como Banco.excluir_permanentemente: só sai de vez quem está na lixeira, com o histórico, as prorrogações e os
  // anexos (que deixam de ir no pacote).
  async function excluirDeVez(r) {
    const conferida = bancoLocal.exec('SELECT 1 FROM rpvs WHERE id=? AND lixeira_em IS NOT NULL', [r.id]);
    if (!conferida.length) {
      throw new Error('Somente entradas na lixeira podem ser excluídas permanentemente.');
    }
    const documentos = bancoLocal.exec('SELECT caminho FROM documentos WHERE rpv_id=?', [r.id]);
    const caminhos = documentos.length ? documentos[0].values.map((linha) => linha[0]) : [];
    for (const tabela of ['documentos', 'previsoes_historico', 'prorrogacoes']) {
      bancoLocal.run(`DELETE FROM ${tabela} WHERE rpv_id=?`, [r.id]);
    }
    bancoLocal.run('DELETE FROM rpvs WHERE id=?', [r.id]);
    await salvarLocal({}, caminhos);
    avisar('Operação excluída de vez.');
  }

  // Anexos como Banco.copiar_anexos grava ("12/<32 letras>.jpg"); devolve os arquivos para salvarLocal.
  function registrarDocumentos(rpvId, documentos) {
    const novos = {};
    for (const d of documentos) {
      const caminho = `${rpvId}/${crypto.randomUUID().replaceAll('-', '')}.${d.extensao}`;
      bancoLocal.run("INSERT INTO documentos (rpv_id,nome,caminho,tipo) VALUES (?,?,?,'entrada')", [rpvId, d.nome, caminho]);
      novos[caminho] = d.bytes;
    }
    return novos;
  }

  // ---- Documentos escolhidos no celular (câmera, fotos ou Arquivos) ----------------------------------------
  // Fotos são reduzidas (lado maior até 2000 px, em JPEG): continuam legíveis e o arquivo fica leve para guardar
  // e mandar ao computador. PDFs vão como estão.
  const LADO_MAXIMO = 2000;
  const LIMITE_PDF = 25 * 1024 * 1024;

  async function prepararDocumento(arquivo) {
    const extensao = (arquivo.name.includes('.') ? arquivo.name.split('.').pop() : '').toLowerCase();
    if (arquivo.type === 'application/pdf' || extensao === 'pdf') {
      if (arquivo.size > LIMITE_PDF) {
        throw new Error(`${arquivo.name}: o PDF passa de 25 MB.`);
      }
      return { nome: nomeDoDocumento(arquivo.name, 'pdf'), extensao: 'pdf', bytes: new Uint8Array(await arquivo.arrayBuffer()) };
    }
    if (!arquivo.type.startsWith('image/') && !TIPOS[extensao]) {
      throw new Error(`${arquivo.name}: escolha um PDF ou uma foto.`);
    }
    const imagem = await abrirImagem(arquivo);
    const largura = imagem.naturalWidth || imagem.width;
    const altura = imagem.naturalHeight || imagem.height;
    const escala = Math.min(1, LADO_MAXIMO / Math.max(largura, altura));
    const tela = el('canvas', { width: Math.max(1, Math.round(largura * escala)), height: Math.max(1, Math.round(altura * escala)) });
    const contexto = tela.getContext('2d');
    contexto.fillStyle = '#ffffff';  // Imagem com transparência: fundo branco, como no papel.
    contexto.fillRect(0, 0, tela.width, tela.height);
    contexto.drawImage(imagem, 0, 0, tela.width, tela.height);
    if (imagem.close) {
      imagem.close();
    }
    const blob = await new Promise((ok, falha) => tela.toBlob((b) => (b ? ok(b) : falha(new Error(`${arquivo.name}: não foi possível preparar a foto.`))), 'image/jpeg', 0.85));
    return { nome: nomeDoDocumento(arquivo.name, 'jpg'), extensao: 'jpg', bytes: new Uint8Array(await blob.arrayBuffer()) };
  }

  // createImageBitmap primeiro (respeita a rotação da foto); se o aparelho não decodificar assim, pela <img>.
  async function abrirImagem(arquivo) {
    try {
      return await createImageBitmap(arquivo);
    } catch (erro) {
      const endereco = URL.createObjectURL(arquivo);
      try {
        const imagem = new Image();
        imagem.src = endereco;
        await imagem.decode();
        return imagem;
      } catch (erroImagem) {
        throw new Error(`${arquivo.name}: não foi possível ler esta imagem.`);
      } finally {
        URL.revokeObjectURL(endereco);
      }
    }
  }

  // A câmera do iPhone entrega "image.jpg": esse vira "Foto 29-10-2026 14h32.jpg".
  function nomeDoDocumento(original, extensao) {
    const base = original.replace(/\.[^.]*$/, '').replace(/[<>:"/\\|?*\u0000-\u001f]/g, '').trim().slice(0, 100);
    if (base && !/^image$/i.test(base)) {
      return `${base}.${extensao}`;
    }
    const agora = new Date();
    const dois = (n) => String(n).padStart(2, '0');
    return `Foto ${D.dataBr(D.hojeIso(agora)).replaceAll('/', '-')} ${dois(agora.getHours())}h${dois(agora.getMinutes())}.${extensao}`;
  }

  async function prepararDocumentos(arquivos) {
    const documentos = [];
    for (const arquivo of arquivos) {
      documentos.push(await prepararDocumento(arquivo));
    }
    return documentos;
  }

  function paraBase64(bytes) {
    let texto = '';
    for (let i = 0; i < bytes.length; i += 0x8000) {
      texto += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    }
    return btoa(texto);
  }

  const documentoParaEnvio = (d) => ({ arquivo: d.nome, conteudo: paraBase64(d.bytes) });

  async function gravarContaLocal(valores) {
    inserir('contas', D.linhaDaConta(valores));
    await salvarLocal();
    avisar('Conta salva.');
  }

  // Como Banco.salvar_conta com identificador: as operações antigas continuam com a cópia dos dados que guardaram.
  async function atualizarContaLocal(id, valores) {
    const linha = D.linhaDaConta(valores);
    const campos = Object.keys(linha);
    bancoLocal.run(`UPDATE contas SET ${campos.map((k) => k + '=?').join(',')} WHERE id=?`, [...campos.map((k) => linha[k]), id]);
    await salvarLocal();
    avisar('Conta atualizada.');
  }

  // Banco.ativar_conta.
  async function ativarContaLocal(id, ativa) {
    bancoLocal.run('UPDATE contas SET ativa=? WHERE id=?', [ativa ? 1 : 0, id]);
    await salvarLocal();
    avisar(ativa ? 'Conta reativada.' : 'Conta desativada.');
  }

  // Banco.remover_contas: as operações perdem o vínculo, mas guardam os dados bancários que copiaram.
  async function removerContaLocal(id) {
    bancoLocal.run('UPDATE rpvs SET conta_id=NULL WHERE conta_id=?', [id]);
    bancoLocal.run('DELETE FROM contas WHERE id=?', [id]);
    await salvarLocal();
    avisar('Conta removida.');
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
    avisar('Recebimento registrado.');
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

  // Cifra e guarda no aparelho uma entrada, conta ou mudança feita aqui, e abre a tela de envio ao computador.
  async function guardarPendente(tipo, dados, { ir = true } = {}) {
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
    if (ir) {
      location.replace(`#enviar/${completa.id}`);
    }
    return completa.id;
  }

  // Mudanças feitas no celular numa operação do computador, ainda não importadas.
  function pendentesDa(operacaoId) {
    return listaPendentes.filter((p) => {
      const aberta = abertasPendentes.get(p.id);
      return aberta && aberta.operacao_id === operacaoId;
    });
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
    return telaEntrada(null);
  }

  function telaEditar(id) {
    const r = dados.operacoes.find((o) => o.id === id);
    return r ? telaEntrada(r) : [vazio('Operação não encontrada.')];
  }

  // Campos de uma operação que o celular pode mudar, como estão gravados (o computador confere com os dele).
  const CAMPOS_EDITAVEIS = ['nome', 'aquisicao', 'custo', 'previsto', 'conta_id', 'conta', 'previsao', 'comissao', 'observacoes'];

  // Formulário de entrada: nova (r = null) ou edição de uma operação que já existe.
  function telaEntrada(r) {
    if (!info.chave) {
      return [el('p', { class: 'aviso', texto: info.demonstracao ? 'Na demonstração não dá para cadastrar. Toque em "Começar com meus dados", no aviso do alto da tela.'
        : 'Para cadastrar ou mudar entradas no celular, abra um backup com senha (feito pelo programa a partir da versão 0.30).' })];
    }
    const contas = [...dados.contas.filter((c) => c.ativa || (r && c.id === r.conta_id)), ...(info.independente ? [] : contasPendentes()
      .map((c) => ({ id: `p:${c.id}`, conta_id: -1, identificacao: c.identificacao, pendente: true })))];
    if (r && !dados.contas.some((c) => c.id === r.conta_id)) {
      // Conta removida no computador: a operação guarda o nome e os dados dela, que continuam se não for trocada.
      contas.unshift({ id: 'manter', identificacao: `${r.conta} (removida)`, manter: true });
    }
    if (!contas.length) {
      return [el('p', { class: 'aviso', texto: 'Cadastre uma conta de recebimento (aba Contas) antes de cadastrar entradas.' }),
        el('a', { class: 'botao-link primario', href: '#nova-conta', texto: '+ Nova conta' })];
    }
    const valor = (nome, centavos) => {
      const campo = campoMoeda(nome);
      campo.value = centavos === null || centavos === undefined ? '' : D.moeda(centavos);
      return campo;
    };
    const c = {
      nome: el('input', { name: 'nome', autocomplete: 'off', autocapitalize: 'words', maxlength: '150', value: r ? r.nome : '' }),
      aquisicao: el('input', { name: 'aquisicao', type: 'date', value: r ? r.aquisicao : D.hojeIso() }),
      custo: valor('custo', r && r.custo),
      previsto: valor('previsto', r && r.previsto),
      conta: el('select', { name: 'conta' }, el('option', { value: '', texto: 'Escolha a conta' }),
        contas.map((conta) => el('option', { value: String(conta.id),
          texto: conta.identificacao + (conta.pendente ? ' (aguardando o computador)' : conta.ativa === 0 ? ' (desativada)' : '') }))),
      previsao: el('input', { name: 'previsao', type: 'date', value: r ? r.previsao : '' }),
      comissao: valor('comissao', r && r.comissao),
      observacoes: el('textarea', { name: 'observacoes', rows: '3', maxlength: '5000' }),
      documentos: !r && el('input', { name: 'documentos', type: 'file', accept: 'image/*,application/pdf', multiple: true }),
    };
    c.observacoes.value = r ? r.observacoes : '';
    const colar = !r && preencherPorTexto(c);
    if (r) {
      c.conta.value = r.conta_id === null || !dados.contas.some((x) => x.id === r.conta_id) ? 'manter' : String(r.conta_id);
    } else if (contas.length === 1) {
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
    const salvar = el('button', { type: 'submit', class: 'primario', texto: r ? 'Salvar alterações' : 'Salvar entrada' });
    const mostrarErros = (problemas) => {
      erros.replaceChildren(...problemas.map((p) => el('div', { texto: p })));
      erros.scrollIntoView({ behavior: 'smooth', block: 'center' });
    };
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
        problemas.push(...(r ? D.problemasDaEdicao(r, entrada) : D.problemasDaEntrada(entrada)));
      }
      const conta = contas.find((x) => String(x.id) === c.conta.value);
      if (!conta) {
        problemas.push('Escolha a conta de destino.');
      }
      if (problemas.length) {
        mostrarErros(problemas);
        return;
      }
      salvar.disabled = true;
      try {
        const documentos = c.documentos ? await prepararDocumentos([...c.documentos.files]) : [];
        if (r) {
          await salvarEdicao(r, entrada, conta);
        } else if (info.independente) {
          location.replace(`#operacao/${await gravarEntradaLocal(entrada, conta, documentos)}`);
        } else {
          // Conta ainda não importada: o computador a encontra pelo nome (conta_id -1), importando-a antes.
          await guardarPendente('entrada', { ...entrada, conta_id: conta.pendente ? -1 : conta.id, conta: conta.identificacao,
            ...(documentos.length ? { anexos: documentos.map(documentoParaEnvio) } : {}) });
        }
      } catch (erro) {
        mostrarErros([erro instanceof AvisoEdicao ? erro.message
          : 'Não foi possível guardar neste aparelho: ' + (erro && erro.message ? erro.message : erro)]);
        salvar.disabled = false;
      }
    } },
    campoFormulario('Titular original', c.nome),
    campoFormulario('Data de aquisição', c.aquisicao),
    campoFormulario('Valor de aquisição', c.custo),
    campoFormulario('Valor Total RPV', c.previsto),
    lucro,
    campoFormulario('Conta de destino', c.conta),
    campoFormulario('Previsão inicial de recebimento', c.previsao,
      r && r.previsao_atual !== r.previsao ? `A previsão atual (${D.dataBr(r.previsao_atual)}) muda em "Alterar previsão", na operação.` : null),
    campoFormulario('Comissão (opcional)', c.comissao),
    campoFormulario('Observações (opcional)', c.observacoes),
    c.documentos && campoFormulario('Documentos (opcional)', c.documentos, 'Fotos ou PDFs: tire uma foto do documento ou escolha em Arquivos.'),
    erros,
    salvar);
    const explicacao = info.independente ? (r ? 'As alterações são gravadas nos seus dados deste celular.' : 'A entrada é gravada nos seus dados deste celular.')
      : r ? 'A alteração vai para o computador como as entradas feitas aqui. Lá, só os campos que você mudou são gravados; se a operação tiver mudado no computador depois deste backup, ele avisa e não grava.'
        : 'A entrada fica guardada neste celular e vai para o computador por um arquivo que você salva na pasta do backup no Google Drive. Ao abrir, o Gestor no computador pergunta se quer importá-la.';
    return [el('p', { class: 'discreto pequeno', texto: explicacao }), colar, formulario];
  }

  class AvisoEdicao extends Error {}

  // Colar e preencher: um texto com os dados do cliente (WhatsApp, e-mail, processo) preenche o formulário.
  // CPF e número do processo não têm campo próprio: vão para as observações.
  function preencherPorTexto(c) {
    const texto = el('textarea', { name: 'texto_colado', rows: '4', placeholder: 'Cole aqui a mensagem com os dados do cliente' });
    const resultado = el('p', { class: 'discreto pequeno', role: 'status' });
    const preencher = () => {
      const achado = D.extrairDaMensagem(texto.value);
      const preenchidos = [];
      const valor = (campo, centavos, rotulo) => {
        if (centavos !== undefined) {
          campo.value = D.moeda(centavos);
          campo.dispatchEvent(new Event('input'));
          preenchidos.push(rotulo);
        }
      };
      if (achado.nome) {
        c.nome.value = D.nomeTitulo(achado.nome);
        preenchidos.push('titular');
      }
      valor(c.custo, achado.custo, 'valor de aquisição');
      valor(c.previsto, achado.previsto, 'Valor Total RPV');
      valor(c.comissao, achado.comissao, 'comissão');
      if (achado.aquisicao) {
        c.aquisicao.value = achado.aquisicao;
        preenchidos.push('data de aquisição');
      }
      if (achado.previsao) {
        c.previsao.value = achado.previsao;
        preenchidos.push('previsão');
      }
      const notas = [achado.processo && `Processo nº ${achado.processo}`, achado.cpf && `CPF do titular: ${achado.cpf}`]
        .filter((n) => n && !c.observacoes.value.includes(n));
      if (notas.length) {
        c.observacoes.value = [c.observacoes.value.trim(), ...notas].filter(Boolean).join('\n');
        preenchidos.push(achado.processo && achado.cpf ? 'processo e CPF (nas observações)'
          : achado.processo ? 'processo (nas observações)' : 'CPF (nas observações)');
      }
      resultado.className = preenchidos.length ? 'discreto pequeno' : 'erro';
      resultado.textContent = preenchidos.length ? `Preenchido: ${preenchidos.join(', ')}. Confira antes de salvar.`
        : 'Nada reconhecido no texto. Os dados precisam estar escritos, como "Valor da RPV: R$ 10.000,00".';
    };
    const caixa = el('details', { class: 'cartao acao colar' },
      el('summary', {}, el('span', { class: 'nome', texto: 'Colar e preencher' }),
        el('span', { class: 'discreto pequeno', texto: 'Dados de uma mensagem' })),
      el('div', { class: 'formulario' },
        el('p', { class: 'discreto pequeno', texto: 'Copie a mensagem do WhatsApp ou do e-mail com os dados do cliente e cole abaixo. O app encontra o nome, os valores, as datas, o CPF e o número do processo.' }),
        navigator.clipboard && navigator.clipboard.readText && el('button', { type: 'button', class: 'primario', texto: 'Colar e preencher',
          onclick: async () => {
            try {
              texto.value = await navigator.clipboard.readText();
              preencher();
            } catch (erro) {
              resultado.className = 'discreto pequeno';
              resultado.textContent = 'Toque na caixa abaixo e escolha Colar; depois toque em "Preencher".';
              texto.focus();
            }
          } }),
        texto,
        el('button', { type: 'button', class: 'secundario', texto: 'Preencher', onclick: preencher }),
        resultado));
    return caixa;
  }

  async function salvarEdicao(r, entrada, conta) {
    if (info.independente) {
      await editarLocal(r, entrada, conta);
      location.replace(`#operacao/${r.id}`);
      return;
    }
    const antes = Object.fromEntries(CAMPOS_EDITAVEIS.map((k) => [k, r[k]]));
    const mesma = conta.manter || conta.id === r.conta_id;
    const depois = { ...entrada, nome: D.nomeTitulo(entrada.nome), observacoes: D.primeiraMaiuscula(entrada.observacoes),
      conta_id: mesma ? r.conta_id : conta.pendente ? -1 : conta.id, conta: mesma ? r.conta : conta.identificacao };
    if (CAMPOS_EDITAVEIS.every((k) => antes[k] === depois[k])) {
      throw new AvisoEdicao('Nada foi alterado.');
    }
    await guardarPendente('alteracao', { operacao_id: r.id, nome: r.nome, antes, depois });
  }

  const TITULOS_EDITAVEIS = { nome: 'titular', aquisicao: 'data de aquisição', custo: 'valor de aquisição',
    previsto: 'Valor Total RPV', conta_id: 'conta de destino', conta: 'conta de destino', previsao: 'previsão inicial',
    comissao: 'comissão', observacoes: 'observações' };

  function resumoPendente(p) {
    const e = abertasPendentes.get(p.id);
    if (!e) {
      return ['Feita com um backup anterior', `Criada em ${D.dataHora(p.criada_em)}`];
    }
    switch (e.tipo) {
      case 'conta':
        return [`Conta: ${e.identificacao}`, `${e.banco} · titular ${e.nome}`];
      case 'alteracao':
        return [`Alteração: ${e.nome}`, 'Mudou: ' + [...new Set(CAMPOS_EDITAVEIS.filter((k) => e.antes[k] !== e.depois[k])
          .map((k) => TITULOS_EDITAVEIS[k]))].join(', ')];
      case 'previsao':
        return [`Nova previsão: ${e.nome}`, `${D.dataBr(e.anterior)} → ${D.dataBr(e.nova)}`];
      case 'exclusao':
        return [`Exclusão: ${e.nome}`, 'Vai para a lixeira do computador'];
      case 'anexo':
        return [`Documento: ${e.nome}`, e.arquivo];
      default: {
        const anexos = (e.anexos || []).length;
        return [e.nome, `${reais(e.previsto)} · previsão ${D.dataBr(e.previsao)} · ${e.conta}`
          + (anexos ? ` · ${D.quantidade(anexos, 'documento', 'documentos')}` : '')];
      }
    }
  }

  // Arquivo de um item guardado, pronto para o menu Compartilhar do iPhone.
  function arquivoPendente(p) {
    return new File([new Uint8Array(p.bytes)], p.arquivo, { type: 'application/octet-stream' });
  }

  // Conta de recebimento nova (ou editada, só no celular): mesmas regras do computador, inclusive não repetir
  // apelido, conta ou Pix.
  function telaNovaConta(id) {
    const existente = Number.isInteger(id) ? dados.contas.find((x) => x.id === id) : null;
    if (Number.isInteger(id) && (!existente || !info.independente)) {
      return [vazio('Conta não encontrada.')];
    }
    if (!info.chave) {
      return [el('p', { class: 'aviso', texto: info.demonstracao ? 'Na demonstração não dá para cadastrar. Toque em "Começar com meus dados", no aviso do alto da tela.'
        : 'Para cadastrar contas no celular, abra um backup com senha (feito pelo programa a partir da versão 0.30).' })];
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
    if (existente) {
      Object.entries(c).forEach(([k, controle]) => {
        controle.value = k === 'cpf' ? D.cpf(existente.cpf) : (existente[k] || '');
      });
    }
    c.cpf.addEventListener('input', () => {
      const d = c.cpf.value.replace(/\D/g, '').slice(0, 11);
      c.cpf.value = [d.slice(0, 3), d.slice(3, 6), d.slice(6, 9)].filter(Boolean).join('.') + (d.length > 9 ? '-' + d.slice(9) : '');
    });
    const erros = el('div', { class: 'erro', role: 'alert' });
    const salvar = el('button', { type: 'submit', class: 'primario', texto: 'Salvar conta' });
    const formulario = el('form', { class: 'cartao formulario', autocomplete: 'off', onsubmit: async (evento) => {
      evento.preventDefault();
      const valores = Object.fromEntries(Object.entries(c).map(([k, controle]) => [k, controle.value.trim()]));
      const outras = dados.contas.filter((x) => !existente || x.id !== existente.id);
      const problemas = D.problemasDaConta(valores, [...outras, ...(info.independente ? [] : contasPendentes())]);
      if (problemas.length) {
        erros.replaceChildren(...problemas.map((p) => el('div', { texto: p })));
        erros.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return;
      }
      salvar.disabled = true;
      try {
        if (existente) {
          await atualizarContaLocal(existente.id, valores);
          location.replace('#contas');
          return;
        }
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
    if (existente) {
      return [el('p', { class: 'discreto pequeno', texto: 'Alterações não modificam os dados de recebimento guardados nas operações antigas.' }),
        formulario];
    }
    return [el('p', { class: 'discreto pequeno', texto: info.independente ? 'A conta é gravada nos seus dados deste celular.'
      : 'A conta fica guardada neste celular e já pode ser escolhida numa entrada nova. Ela vai para o computador do mesmo jeito que as entradas.' }), formulario];
  }

  function telaPendentes() {
    if (!listaPendentes.length) {
      return [vazio('Nada aguardando o computador.')];
    }
    // Vários de uma vez: o menu do iPhone salva todos na mesma pasta.
    const arquivos = listaPendentes.map(arquivoPendente);
    const resultado = el('p', { class: 'discreto pequeno' });
    const todos = listaPendentes.length > 1 && navigator.canShare && navigator.canShare({ files: arquivos })
      && el('button', { type: 'button', class: 'primario', texto: `Enviar todos (${listaPendentes.length}) para o computador`,
        onclick: () => {
          navigator.share({ files: arquivos }).then(() => {
            resultado.textContent = 'Arquivos enviados. Ao abrir o Gestor no computador, ele vai perguntar se quer importar.';
          }).catch(() => {});
        } });
    return [el('p', { class: 'discreto pequeno', texto: 'Somem daqui sozinhas quando um backup mais novo, feito depois da importação no computador, for aberto no celular.' }),
      todos, resultado,
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
    const arquivo = arquivoPendente(p);
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
        el('li', { texto: 'Abra o Gestor no computador: ele mostra o que veio do celular e pergunta se quer importar.' })),
      enviar, resultado,
      listaPendentes.length > 1 && el('a', { class: 'botao-link', href: '#pendentes',
        texto: `Ver tudo o que aguarda o computador (${listaPendentes.length})` }),
      el('button', { type: 'button', class: 'secundario', texto: 'Apagar do celular', onclick: async () => {
        if (!confirm('Apagar do celular? Se o arquivo já foi salvo no Google Drive, o computador ainda pode importá-lo.')) {
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
    const aguardando = !info.independente && pendentesDa(r.id).map((p) => {
      const [titulo, detalhe] = resumoPendente(p);
      return el('a', { class: 'aviso item', href: `#enviar/${p.id}` }, el('div', { class: 'nome', texto: titulo }),
        el('div', { class: 'discreto pequeno', texto: `${detalhe} · aguarda o computador` }));
    });
    return [
      r.lixeira_em && el('p', { class: 'aviso', texto: `Na lixeira desde ${D.dataHora(r.lixeira_em)}.` }),
      aguardando,
      cartao(campos([
        ['Situação', SITUACOES[s], s === 'atrasada' ? 'vermelho' : s === 'recebida' ? 'verde' : ''],
        ['Titular original', r.nome],
        ['Data de aquisição', D.dataBr(r.aquisicao)],
        ['Valor de aquisição', reais(r.custo)],
        ['Comissão', reais(r.comissao || 0)],
        ['Valor total RPV', reais(r.previsto)],
        ['Lucro previsto', reais(r.previsto - r.custo)],
        ['Previsão inicial', D.dataBr(r.previsao)],
        ['Previsão atual', D.dataBr(r.previsao_atual)],
        ['Recebido em', r.recebimento ? D.dataBr(r.recebimento) : 'Não recebido'],
      ])),
      !r.lixeira_em && el('a', { class: 'botao-link secundario', href: `#resumo/${r.id}`, texto: 'Compartilhar resumo em imagem' }),
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
      anexarDocumento(r),
      acoesDaOperacao(r),
    ];
  }

  // Foto (câmera ou álbum) ou PDF anexado à operação: gravado aqui (só celular) ou mandado ao computador.
  function anexarDocumento(r) {
    if (!info.chave || r.lixeira_em) {
      return null;
    }
    const situacao = el('p', { class: 'discreto pequeno', role: 'status' });
    const entrada = el('input', { type: 'file', accept: 'image/*,application/pdf', multiple: true, class: 'oculto-visual',
      name: 'anexar', onchange: async () => {
        const arquivos = [...entrada.files];
        if (!arquivos.length) {
          return;
        }
        situacao.className = 'discreto pequeno';
        situacao.textContent = 'Preparando…';
        try {
          const documentos = await prepararDocumentos(arquivos);
          if (info.independente) {
            await salvarLocal(registrarDocumentos(r.id, documentos));
            desenhar();
            return;
          }
          const ids = [];
          for (const d of documentos) {
            ids.push(await guardarPendente('anexo', { operacao_id: r.id, nome: r.nome, ...documentoParaEnvio(d) }, { ir: false }));
          }
          location.replace(ids.length === 1 ? `#enviar/${ids[0]}` : '#pendentes');
        } catch (erro) {
          situacao.className = 'erro';
          situacao.textContent = erro && erro.message ? erro.message : String(erro);
        } finally {
          entrada.value = '';
        }
      } });
    return [el('label', { class: 'botao-link secundario anexar' }, '+ Anexar foto ou PDF', entrada), situacao];
  }

  // Alterar a previsão, editar e excluir: gravado aqui (só celular) ou mandado ao computador, que confere.
  function acoesDaOperacao(r) {
    if (!info.chave) {
      return null;
    }
    if (r.lixeira_em) {
      return info.independente && [
        el('button', { type: 'button', class: 'secundario', texto: 'Restaurar da lixeira',
          onclick: async (evento) => {
            evento.target.disabled = true;
            await lixeiraLocal(r, false);
            desenhar();
          } }),
        el('button', { type: 'button', class: 'secundario perigo', texto: 'Excluir permanentemente',
          onclick: async (evento) => {
            if (!confirm(`Excluir permanentemente a operação de ${r.nome}? Ela e os documentos anexados saem de vez `
              + 'e não podem ser restaurados.')) {
              return;
            }
            evento.target.disabled = true;
            try {
              await excluirDeVez(r);
              location.replace('#lixeira');
            } catch (erro) {
              evento.target.disabled = false;
              alert(erro && erro.message ? erro.message : String(erro));
            }
          } }),
      ];
    }
    const excluir = el('button', { type: 'button', class: 'secundario perigo', texto: 'Excluir operação', onclick: async () => {
      if (!confirm(info.independente ? 'Excluir esta operação? Ela vai para a lixeira (em Mais), de onde pode ser restaurada.'
        : 'Excluir esta operação? O pedido vai para o computador, que a coloca na lixeira.')) {
        return;
      }
      excluir.disabled = true;
      if (info.independente) {
        await lixeiraLocal(r, true);
        location.replace('#operacoes');
      } else {
        await guardarPendente('exclusao', { operacao_id: r.id, nome: r.nome });
      }
    } });
    return [
      el('h2', { texto: 'Mudar esta operação' }),
      !r.recebimento && formularioPrevisao(r),
      el('a', { class: 'botao-link secundario', href: `#editar/${r.id}`, texto: 'Editar dados da entrada' }),
      excluir,
    ];
  }

  function formularioPrevisao(r) {
    const data = el('input', { type: 'date', name: 'nova_previsao', value: r.previsao_atual });
    const erro = el('div', { class: 'erro', role: 'alert' });
    const botao = el('button', { type: 'submit', class: 'primario', texto: 'Salvar nova previsão' });
    return el('details', { class: 'cartao acao' },
      el('summary', {}, el('span', { class: 'nome', texto: 'Alterar previsão' }),
        el('span', { class: 'discreto pequeno', texto: `Atual: ${D.dataBr(r.previsao_atual)}` })),
      el('form', { class: 'formulario', onsubmit: async (evento) => {
        evento.preventDefault();
        const problemas = D.problemasDaPrevisao(r, data.value);
        if (problemas.length) {
          erro.textContent = problemas.join(' ');
          return;
        }
        botao.disabled = true;
        try {
          if (info.independente) {
            await previsaoLocal(r, data.value);
            desenhar();
          } else {
            await guardarPendente('previsao', { operacao_id: r.id, nome: r.nome, anterior: r.previsao_atual, nova: data.value });
          }
        } catch (e) {
          erro.textContent = 'Não foi possível guardar neste aparelho: ' + (e && e.message ? e.message : e);
          botao.disabled = false;
        }
      } }, campoFormulario('Nova previsão de recebimento', data, 'A previsão anterior fica no histórico.'), erro, botao));
  }

  // ---- Resumo da operação em imagem (para mandar no WhatsApp) -----------------------------------------------
  // Só o que não é sensível: titular, situação e datas. Sem CPF, conta, banco ou Pix; o Valor Total RPV só se a
  // pessoa marcar (e nunca no modo discreto).
  // Identidade Terracota: creme, terracota e azul-marinho; situação com as mesmas cores do app.
  const CORES_SITUACAO = { pendente: ['#8a5d24', '#f7ead6'], atrasada: ['#a83c47', '#f8e3e3'], recebida: ['#2f7560', '#e4f0ea'] };
  const SERIFA = '"New York", ui-serif, Georgia, "Times New Roman", serif';
  const FONTE = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
  let logoCarregado = null;

  function carregarLogo() {
    logoCarregado = logoCarregado || new Promise((ok) => {
      const imagem = new Image();
      imagem.onload = () => ok(imagem);
      imagem.onerror = () => ok(null);  // Sem o logo, a imagem sai só com o nome.
      imagem.src = 'icones/logo.png';
    });
    return logoCarregado;
  }

  function quebrarLinhas(contexto, texto, largura, maximo) {
    const linhas = [];
    let atual = '';
    for (const palavra of texto.split(' ')) {
      const tentativa = atual ? `${atual} ${palavra}` : palavra;
      if (contexto.measureText(tentativa).width <= largura || !atual) {
        atual = tentativa;
      } else {
        linhas.push(atual);
        atual = palavra;
      }
    }
    linhas.push(atual);
    if (linhas.length > maximo) {
      linhas.length = maximo;
      linhas[maximo - 1] += '…';
    }
    return linhas;
  }

  function retanguloArredondado(contexto, x, y, largura, altura, raio) {
    contexto.beginPath();
    contexto.moveTo(x + raio, y);
    contexto.arcTo(x + largura, y, x + largura, y + altura, raio);
    contexto.arcTo(x + largura, y + altura, x, y + altura, raio);
    contexto.arcTo(x, y + altura, x, y, raio);
    contexto.arcTo(x, y, x + largura, y, raio);
    contexto.closePath();
  }

  async function desenharResumo(r, { comValor }) {
    const largura = 1080;
    const x = 80;
    const larguraCartao = largura - 2 * x;
    const linhas = [
      r.recebimento ? ['Recebida em', D.dataBr(r.recebimento)] : ['Previsão de recebimento', D.dataBr(r.previsao_atual)],
      !r.recebimento && r.previsao_atual !== r.previsao && ['Previsão inicial', D.dataBr(r.previsao)],
      ['Data de aquisição', D.dataBr(r.aquisicao)],
      comValor && !discreto && ['Valor Total RPV', D.reais(r.previsto)],
    ].filter(Boolean);
    // A altura acompanha o conteúdo (nome em até duas linhas, de duas a quatro informações).
    const tela = el('canvas', { width: largura, height: 10 });
    const g = tela.getContext('2d');
    g.font = `700 64px ${SERIFA}`;
    const nome = quebrarLinhas(g, r.nome, larguraCartao - 120, 2);
    const fimDoCartao = 470 + nome.length * 80 + 104 + linhas.length * 168 + 70;
    const altura = fimDoCartao + 150;
    tela.height = altura;  // Mudar o tamanho limpa o desenho e as configurações do contexto.
    g.fillStyle = '#f7f3ee';
    g.fillRect(0, 0, largura, altura);
    // Faixa em terracota com uma luz suave atrás do logo.
    const faixa = g.createLinearGradient(0, 0, largura, 330);
    faixa.addColorStop(0, '#c96548');
    faixa.addColorStop(1, '#b4553a');
    g.fillStyle = faixa;
    g.fillRect(0, 0, largura, 330);
    const brilho = g.createRadialGradient(largura / 2, 130, 10, largura / 2, 130, 360);
    brilho.addColorStop(0, 'rgba(255, 255, 255, 0.2)');
    brilho.addColorStop(1, 'rgba(255, 255, 255, 0)');
    g.fillStyle = brilho;
    g.fillRect(0, 0, largura, 330);
    const logo = await carregarLogo();
    if (logo) {
      g.fillStyle = '#ffffff';
      retanguloArredondado(g, largura / 2 - 80, 50, 160, 160, 36);
      g.fill();
      g.drawImage(logo, largura / 2 - 64, 66, 128, 128);
    }
    g.textAlign = 'center';
    g.fillStyle = '#ffffff';
    g.font = `700 50px ${SERIFA}`;
    g.fillText('Gestor RPV', largura / 2, 284);

    g.fillStyle = '#fffdf9';
    retanguloArredondado(g, x, 380, larguraCartao, fimDoCartao - 380, 40);
    g.fill();
    g.textAlign = 'left';
    const margem = x + 60;
    let y = 470;
    g.fillStyle = '#656b79';
    g.font = `600 34px ${FONTE}`;
    g.fillText('Resumo da operação', margem, y);
    g.fillStyle = '#20334d';
    g.font = `700 64px ${SERIFA}`;
    for (const linha of nome) {
      y += 80;
      g.fillText(linha, margem, y);
    }
    const s = D.situacao(r);
    const [cor, fundo] = CORES_SITUACAO[s];
    g.font = `700 32px ${FONTE}`;
    const selo = SITUACOES[s].toUpperCase();
    const larguraSelo = g.measureText(selo).width + 56;
    y += 44;
    g.fillStyle = fundo;
    retanguloArredondado(g, margem, y, larguraSelo, 60, 30);
    g.fill();
    g.fillStyle = cor;
    g.fillText(selo, margem + 28, y + 42);
    y += 60;
    for (const [rotulo, valor] of linhas) {
      y += 40;
      g.strokeStyle = '#ede7e0';
      g.lineWidth = 2;
      g.beginPath();
      g.moveTo(margem, y);
      g.lineTo(x + larguraCartao - 60, y);
      g.stroke();
      y += 62;
      g.fillStyle = '#656b79';
      g.font = `500 34px ${FONTE}`;
      g.fillText(rotulo, margem, y);
      y += 66;
      g.fillStyle = '#20334d';
      g.font = `700 52px ${FONTE}`;
      g.fillText(valor, margem, y);
    }
    g.textAlign = 'center';
    g.fillStyle = '#656b79';
    g.font = `500 30px ${FONTE}`;
    g.fillText(`Atualizado em ${D.dataBr(D.hojeIso())}`, largura / 2, altura - 70);
    return new Promise((ok, falha) => tela.toBlob((b) => (b ? ok(b) : falha(new Error('Não foi possível gerar a imagem.'))), 'image/png'));
  }

  function telaResumo(id) {
    const r = dados.operacoes.find((o) => o.id === id);
    if (!r) {
      return [vazio('Operação não encontrada.')];
    }
    const imagem = el('img', { class: 'resumo-imagem', alt: `Resumo da operação de ${r.nome}` });
    const acoes = el('div');
    const comValor = el('input', { type: 'checkbox', name: 'com_valor' });
    const atualizar = async () => {
      const blob = await desenharResumo(r, { comValor: comValor.checked });
      if (location.hash !== `#resumo/${id}`) {
        return;  // A pessoa já saiu da tela.
      }
      const nome = `Resumo ${D.nomeTitulo(r.nome)}.png`.replace(/[<>:"/\\|?*]/g, '');
      const arquivo = new File([blob], nome, { type: 'image/png' });
      liberarDocumento();
      enderecoAberto = URL.createObjectURL(arquivo);
      imagem.src = enderecoAberto;
      const podeCompartilhar = navigator.canShare && navigator.canShare({ files: [arquivo] });
      acoes.replaceChildren(podeCompartilhar
        ? el('button', { type: 'button', class: 'primario', texto: 'Compartilhar imagem', onclick: () => {
          navigator.share({ files: [arquivo] }).catch(() => {});  // Cancelar o menu não é erro.
        } })
        : el('a', { class: 'botao-link primario', href: enderecoAberto, download: nome, texto: 'Baixar imagem' }));
    };
    comValor.addEventListener('change', atualizar);
    atualizar();
    return [
      el('p', { class: 'discreto pequeno', texto: 'Imagem para mandar no WhatsApp: titular, situação e datas. Não leva CPF, conta, banco nem Pix.' }),
      imagem,
      !discreto && el('label', { class: 'opcao' }, comValor, el('span', { texto: 'Mostrar o Valor Total RPV' })),
      acoes,
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
        contaRecolhida(c.identificacao, c),
        info.independente && acoesDaConta(c, usos + dados.lixeira.filter((r) => r.conta_id === c.id).length));
    }))];
  }

  // Ver / Editar, Desativar / Reativar e Remover, como na tela de contas do computador (só com os dados no celular).
  function acoesDaConta(c, usos) {
    const executar = async (botao, acao) => {
      botao.disabled = true;
      try {
        await acao();
        desenhar();
      } catch (erro) {
        botao.disabled = false;
        alert('Não foi possível alterar a conta: ' + (erro && erro.message ? erro.message : erro));
      }
    };
    const status = el('button', { type: 'button', class: 'secundario', texto: c.ativa ? 'Desativar' : 'Reativar', onclick: () => {
      if (confirm(`${c.ativa ? 'Desativar' : 'Reativar'} a conta ${c.identificacao}?`
        + (c.ativa ? ' Ela continua no histórico e pode ser reativada.' : ''))) {
        executar(status, () => ativarContaLocal(c.id, !c.ativa));
      }
    } });
    const remover = el('button', { type: 'button', class: 'secundario perigo', texto: 'Remover', onclick: () => {
      const aviso = usos ? `${usos === 1 ? '1 operação usa' : usos + ' operações usam'} esta conta. Elas guardam os dados `
        + 'bancários, mas a conta não poderá ser escolhida de novo nem reativada. Se for só parar de usar, prefira Desativar.'
        : 'As operações e os dados bancários já guardados nelas continuam existindo.';
      if (confirm(`Remover permanentemente a conta ${c.identificacao}?\n\n${aviso}`)) {
        executar(remover, () => removerContaLocal(c.id));
      }
    } });
    return el('div', { class: 'acoes-conta' },
      el('a', { class: 'botao-link secundario', href: `#editar-conta/${c.id}`, texto: 'Editar' }), status, remover);
  }

  function telaLixeira() {
    if (!dados.lixeira.length) {
      return [vazio('A lixeira está vazia.')];
    }
    return [el('p', { class: 'discreto pequeno', texto: info.independente ? 'Operações excluídas. Toque numa delas para ver, restaurar ou excluir de vez.'
      : 'Operações excluídas no computador. Para restaurar, use o programa no computador.' }),
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
        ['Investido', reais(valores.investido)],
        ['Recebidas', D.quantidade(r, 'operação', 'operações')],
        ['Recebido', reais(valores.recebido), 'verde'],
        ['Lucro realizado', reais(valores.lucro), 'verde'],
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

  // Ícone num ladrilho colorido, o título com o detalhe e a seta: o desenho de cada opção de Mais.
  function conteudoOpcao(simbolo, tom, titulo, detalhe) {
    return [el('span', { class: 'icone-menu ' + (tom || '') }, icone(simbolo)),
      el('div', { class: 'textos' }, el('div', { texto: titulo }), el('div', { class: 'discreto pequeno', texto: detalhe })),
      icone('seta', 'seta')];
  }

  // Senha num cartão (para ligar a nuvem, os lembretes ou tornar o celular principal); `acao(senha, andamento)` mostra
  // o andamento no próprio cartão e, se falhar, a mensagem fica ali.
  function formularioSenha(rotulo, acao) {
    const campo = el('input', { type: 'password', name: 'senha_nuvem', autocomplete: 'current-password', autocapitalize: 'off',
      spellcheck: 'false' });
    const situacao = el('p', { class: 'discreto pequeno', role: 'status' });
    const botao = el('button', { type: 'submit', class: 'primario', texto: rotulo });
    return el('form', { class: 'formulario', autocomplete: 'off', onsubmit: async (evento) => {
      evento.preventDefault();
      if (!campo.value) {
        situacao.className = 'erro';
        situacao.textContent = 'Digite a senha.';
        return;
      }
      botao.disabled = true;
      situacao.className = 'discreto pequeno';
      situacao.textContent = 'Conferindo a senha…';
      try {
        await acao(campo.value, (texto) => { situacao.textContent = texto; });
      } catch (erro) {
        situacao.className = 'erro';
        situacao.textContent = erro && erro.message ? erro.message : String(erro);
        botao.disabled = false;
      }
    } }, campoFormulario('Senha dos seus dados', campo), situacao, botao);
  }

  // A senha abre os dados abertos agora? Então as credenciais da nuvem saem dela.
  async function credenciaisConferidas(senha, andamento) {
    if (!await LeitorBackup.senhaConfere(senha, info.chave)) {
      throw new Error('Senha incorreta: use a mesma senha que abre estes dados.');
    }
    andamento('Preparando a conexão com a nuvem…');
    return Nuvem.credenciais(senha);
  }

  function textosCartao(titulo, detalhe) {
    return el('div', { class: 'textos' }, el('div', { class: 'nome', texto: titulo }),
      el('div', { class: 'discreto pequeno', texto: detalhe }));
  }

  // Backup automático na nuvem: com os dados no celular, liga, mostra o último envio e desliga; com o backup do
  // computador, leva à tela de tornar este celular o principal.
  function cartaoNuvem() {
    if (!info.independente) {
      return el('a', { class: 'cartao opcao-menu', href: '#principal' }, conteudoOpcao('celular', 'verde',
        'Tornar este celular o principal', 'Entradas valem na hora; o backup vai sozinho para a nuvem e o computador só consulta'));
    }
    if (!nuvem || !nuvem.backup) {
      return el('div', { class: 'cartao nuvem' },
        textosCartao('Backup automático na nuvem', 'Desligado. Ligado, a cada gravação o app guarda na nuvem uma cópia '
          + 'trancada com a sua senha (para o computador ver os dados e para recuperar num celular novo).'),
        formularioSenha('Ligar backup na nuvem', async (senha, andamento) => {
          const cred = await credenciaisConferidas(senha, andamento);
          await guardarNuvem({ ...cred, backup: true, lembretes: Boolean(nuvem && nuvem.lembretes) });
          andamento('Enviando o primeiro backup…');
          await enviarNuvem();
          avisar('Backup na nuvem ligado.');
        }));
    }
    const estado = estadoNuvem();
    const situacao = enviandoNuvem ? 'Ligado · enviando…'
      : estado.conflito ? `Há na nuvem um backup de outro aparelho com esta senha${estado.outro_em ? ` (de ${D.dataHora(estado.outro_em)})` : ''}. `
        + 'Substitua só se aquele aparelho não for mais usado.'
        : estado.erro ? `O último envio não foi (${estado.erro}). O app tenta de novo na próxima gravação ou abertura.`
          : estado.enviado_em ? `Ligado · último envio em ${D.dataHora(estado.enviado_em)}`
            : 'Ligado · em dia com a nuvem';
    const enviar = (substituir) => async (evento) => {
      evento.target.disabled = true;
      await enviarNuvem({ substituir }).then(() => avisar('Backup enviado para a nuvem.')).catch(() => {});
    };
    return el('div', { class: 'cartao nuvem' },
      textosCartao('Backup automático na nuvem', situacao),
      el('div', { class: 'botoes' },
        estado.conflito ? el('button', { type: 'button', class: 'secundario perigo', texto: 'Substituir pelo deste celular', onclick: enviar(true) })
          : el('button', { type: 'button', class: 'secundario', texto: 'Enviar agora', onclick: enviar(false) }),
        el('button', { type: 'button', class: 'secundario', texto: 'Desligar', onclick: async (evento) => {
          if (!confirm('Desligar o backup na nuvem? A cópia guardada lá é apagada, e o programa no computador volta a '
            + 'aceitar alterações na próxima vez que abrir.')) {
            return;
          }
          evento.target.disabled = true;
          try {
            await Nuvem.apagar(nuvem);
            await guardarNuvem({ ...nuvem, backup: false });
            gravarEstadoNuvem({});
            avisar('Backup na nuvem desligado.');
          } catch (erro) {
            alert('Não foi possível desligar agora: ' + erro.message);
          }
          redesenharMais();
        } })));
  }

  // Lembrete às 8h do dia anterior a cada previsão (Web Push, pela nuvem do Gestor).
  function cartaoLembretes() {
    const titulo = 'Lembrete um dia antes da previsão';
    if (!lembretesPossiveis()) {
      return el('div', { class: 'cartao nuvem' }, textosCartao(titulo, 'Para receber lembretes, abra o app pelo ícone da '
        + 'Tela de Início (iPhone com iOS 16.4 ou mais novo).'));
    }
    if (nuvem && nuvem.lembretes && Notification.permission === 'granted') {
      return el('div', { class: 'cartao nuvem' },
        textosCartao(titulo, 'Ligado · às 8h do dia anterior, um aviso com quantas previsões caem no dia seguinte.'),
        el('div', { class: 'botoes' }, el('button', { type: 'button', class: 'secundario', texto: 'Desligar lembretes',
          onclick: async (evento) => {
            evento.target.disabled = true;
            await desligarLembretes();
            avisar('Lembretes desligados.');
            redesenharMais();
          } })));
    }
    const detalhe = 'Desligado. O aviso só diz quantas previsões caem no dia seguinte; nomes e valores não saem do celular.';
    if (!nuvem) {
      return el('div', { class: 'cartao nuvem' }, textosCartao(titulo, detalhe),
        formularioSenha('Continuar', async (senha, andamento) => {
          await guardarNuvem({ ...await credenciaisConferidas(senha, andamento), backup: false, lembretes: false });
          redesenharMais();
        }));
    }
    const situacao = el('p', { class: 'discreto pequeno', role: 'status' });
    return el('div', { class: 'cartao nuvem' }, textosCartao(titulo, detalhe), situacao,
      el('div', { class: 'botoes' }, el('button', { type: 'button', class: 'primario', texto: 'Ligar lembretes',
        onclick: async (evento) => {
          evento.target.disabled = true;
          try {
            await ligarLembretes();
            avisar('Lembretes ligados.');
            redesenharMais();
          } catch (erro) {
            situacao.className = 'erro';
            situacao.textContent = erro && erro.message ? erro.message : String(erro);
            evento.target.disabled = false;
          }
        } })));
  }

  // Celular principal: o backup do computador vira dados deste celular (com a mesma senha), e daí em diante cada
  // gravação vai para a nuvem; o programa no computador carrega esses dados ao abrir e fica só para consulta.
  function telaPrincipal() {
    if (info.independente) {
      return [vazio('Este celular já é o principal.')];
    }
    if (info.demonstracao || !info.chave) {
      return [el('p', { class: 'aviso', texto: 'Abra o seu backup (com senha) para tornar este celular o principal.' })];
    }
    const passos = el('ol', { class: 'passos' },
      el('li', { texto: 'Entradas, contas e alterações passam a valer na hora, aqui no celular.' }),
      el('li', { texto: 'A cada gravação, o app guarda na nuvem uma cópia trancada com a sua senha.' }),
      el('li', { texto: 'Ao abrir, o programa no computador carrega sozinho os dados mais novos e fica só para consulta.' }));
    if (listaPendentes.length) {
      return [passos, el('div', { class: 'aviso' },
        el('div', { class: 'nome', texto: `Antes, leve ao computador o que ainda aguarda (${listaPendentes.length})` }),
        el('div', { class: 'pequeno', texto: 'Importe no programa, feche-o (ele grava um backup novo) e abra esse backup aqui, '
          + 'em Mais → Abrir um backup mais novo. Depois volte a esta tela.' })),
      el('a', { class: 'botao-link secundario', href: '#pendentes', texto: 'Ver o que aguarda o computador' })];
    }
    return [passos, el('p', { class: 'discreto pequeno', texto: `Os dados de agora (backup de ${D.dataHora(info.manifesto.criado_em)}) `
      + 'viram os dados deste celular. Use a mesma senha dos backups do computador.' }),
    cartao(formularioSenha('Tornar este celular o principal', async (senha, andamento) => {
      if (!await LeitorBackup.senhaConfere(senha, info.chave)) {
        throw new Error('Senha incorreta: use a senha dos backups do computador.');
      }
      andamento('Preparando os dados deste celular…');
      const leitura = await LeitorBackup.ler(new Uint8Array(fonte.bytes), senha, { chave: info.chave });
      let pacote;
      try {
        pacote = await LeitorBackup.empacotar(leitura.db.export(), leitura.chave, VERSAO_APP, await leitura.todos());
      } finally {
        leitura.db.close();
      }
      andamento('Preparando a conexão com a nuvem…');
      const cred = await Nuvem.credenciais(senha);
      await guardarNuvem({ ...cred, backup: true, lembretes: Boolean(nuvem && nuvem.lembretes) });
      gravarEstadoNuvem({});
      fonte = { bytes: pacote.bytes, nome: 'GestorRPV-celular.rpvbackup', tamanho: pacote.bytes.length,
        criado_em: pacote.manifesto.criado_em, novo: true };
      andamento('Abrindo…');
      await abrirFonte({ senha, chave: leitura.chave });
      avisar('Este celular agora é o principal.');
    }))];
  }

  function telaMais() {
    const opcao = (href, titulo, detalhe, simbolo, tom) => el('a', { class: 'cartao opcao-menu', href },
      conteudoOpcao(simbolo, tom, titulo, detalhe));
    const grupo = (titulo, ...itens) => [el('h3', { class: 'grupo-menu', texto: titulo }), el('div', { class: 'menu' }, itens)];
    return [
      grupo('Ferramentas',
        opcao('#agenda', 'Agenda das previsões', 'Calendário com as datas previstas de recebimento', 'calendario'),
        opcao('#grafico', 'Gráfico mensal', 'Entradas e recebimentos dos últimos 12 meses', 'barras', 'ambar'),
        opcao('#lixeira', `Lixeira (${dados.lixeira.length})`, info.independente ? 'Operações excluídas: restaurar ou excluir de vez'
          : 'Operações excluídas, só para consulta', 'lixeira')),
      grupo('Aplicativo e compartilhamento',
        opcao('#novidades', 'Novidades', 'O que mudou nas últimas versões', 'megafone'),
        opcao('#convite', 'Convidar alguém', 'Mandar o app para outra pessoa usar com os dados dela', 'convidar', 'azul'),
        opcao('#backup', 'Sobre este backup', `Arquivo, data e versões · app ${VERSAO_APP}`, 'info', 'azul')),
      grupo('Aparência', escolherTema()),
      !info.demonstracao && info.chave && grupo('Nuvem e lembretes', cartaoNuvem(), cartaoLembretes()),
      grupo('Dados e segurança',
        info.independente && opcao('#copia', 'Fazer cópia de segurança', 'Salvar seus dados (trancados) no iCloud ou no Google Drive', 'escudo', 'verde'),
        escolherBackup(),
        senhaRecente && !faceIdAtivo && el('div', { class: 'cartao' },
          el('div', { texto: 'Ativar o Face ID' }), el('div', { class: 'discreto pequeno', texto: 'Abrir o app com o rosto, sem digitar a senha' }),
          el('div', { class: 'botoes' }, el('button', { type: 'button', class: 'primario', texto: 'Ativar',
            onclick: (e) => ativarFaceId(e.target.closest('.cartao')) }))),
        faceIdAtivo && el('a', { class: 'cartao opcao-menu', href: '#', onclick: async (e) => {
        e.preventDefault();
        if (confirm('Desativar o Face ID do app? A próxima abertura pedirá a senha dos backups.')) {
          await FaceId.desativar().catch(() => {});
          faceIdAtivo = false;
          localStorageGravar('faceid_recusado', '1');
          desenhar();
        }
        } }, conteudoOpcao('cadeado', 'ambar', 'Desativar o Face ID', 'Voltar a abrir só com a senha'))),
      el('div', { class: 'menu-acoes' },
        info.demonstracao && el('button', { type: 'button', class: 'primario', texto: 'Sair da demonstração', onclick: sairDaDemonstracao }),
        !info.demonstracao && el('p', { class: 'discreto pequeno', texto: 'O app tranca sozinho depois de 5 minutos em segundo plano.' }),
        !info.demonstracao && el('button', { type: 'button', class: 'secundario', texto: 'Apagar o backup guardado neste aparelho', onclick: esquecerBackup })),
    ];
  }

  function escolherBackup() {
    const [titulo, detalhe] = info.demonstracao ? ['Abrir meu backup', 'Escolher o arquivo .rpvbackup feito pelo programa no computador']
      : info.independente ? ['Restaurar uma cópia de segurança', 'Escolher um arquivo .rpvbackup (substitui os dados deste celular)']
        : ['Abrir um backup mais novo', 'Escolher o arquivo .rpvbackup no Google Drive ou em Arquivos'];
    const entrada = el('input', { type: 'file', class: 'oculto-visual', name: 'escolher_backup', 'aria-label': titulo,
      onchange: () => {
        if (entrada.files[0]) {
          trocarPorArquivo(entrada.files[0]);
        }
      } });
    return el('label', { class: 'cartao opcao-menu escolher-backup' }, conteudoOpcao('enviar', 'verde', titulo, detalhe), entrada);
  }

  // O que mudou nas últimas versões (novidades.json, gerado de novidades.py: o mesmo texto do "Sobre" do programa).
  function telaNovidades() {
    const area = el('div', { class: 'menu' }, el('div', { class: 'esqueleto' },
      el('span', { class: 'so-leitor', texto: 'Carregando…' }), [1, 2, 3].map(() => el('div', { class: 'bloco' }))));
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
    editar: { titulo: 'Editar entrada', aba: 'operacoes', montar: telaEditar, voltar: true },
    agenda: { titulo: 'Agenda', aba: 'inicio', montar: telaAgenda, voltar: true },
    resumo: { titulo: 'Resumo em imagem', aba: 'operacoes', montar: telaResumo, voltar: true },
    copia: { titulo: 'Cópia de segurança', aba: 'mais', montar: telaCopia, voltar: true },
    convite: { titulo: 'Convidar alguém', aba: 'mais', montar: telaConvite, voltar: true },
    'nova-conta': { titulo: 'Nova conta', aba: 'contas', montar: telaNovaConta, voltar: true },
    principal: { titulo: 'Celular principal', aba: 'mais', montar: telaPrincipal, voltar: true },
    'editar-conta': { titulo: 'Editar conta', aba: 'contas', montar: telaNovaConta, voltar: true },
    pendentes: { titulo: 'Aguardando o computador', aba: 'operacoes', montar: telaPendentes, voltar: true },
    enviar: { titulo: 'Enviar ao computador', aba: 'operacoes', montar: telaEnviar, voltar: true, textual: true },
  };

  function avisoDemonstracao() {
    return el('div', { class: 'aviso demonstracao' },
      el('div', { class: 'nome', texto: 'Demonstração' }),
      el('div', { class: 'pequeno', texto: 'Estes dados são fictícios e meramente sugestivos: servem só para mostrar como o app fica. Nada aqui é real.' }),
      el('div', { class: 'botoes' }, el('button', { type: 'button', class: 'primario', texto: 'Começar com meus dados',
        onclick: sairDaDemonstracao })));
  }

  let telaAnimada = null;  // Endereço da última tela que entrou com animação.
  let telaAnterior = null; // A tela mostrada antes desta (para saber se a navegação foi para dentro ou para fora).
  const caminho = [];      // Endereços visitados, para reconhecer o Voltar.
  const ABAS = ['inicio', 'operacoes', 'contas', 'mais'];

  // Detalhes (telas com Voltar) entram da direita; ao voltar, a tela chega da esquerda; entre as abas, o conteúdo
  // só sobe e aparece (abas não deslizam de lado, como no iOS).
  function tipoDeEntrada(tela) {
    const voltou = caminho.length > 1 && caminho[caminho.length - 2] === location.hash;
    if (voltou) {
      caminho.pop();
    } else {
      caminho.push(location.hash);
      caminho.splice(0, Math.max(0, caminho.length - 30));
    }
    if (voltou || (telaAnterior && telaAnterior.voltar && !tela.voltar)) {
      return 'voltando';
    }
    return tela.voltar ? 'empurrando' : 'entrando';
  }

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
    $('voltar').hidden = tela === TELAS.inicio;
    document.querySelectorAll('.abas a').forEach((a) => a.classList.toggle('ativa', a.dataset.aba === tela.aba));
    document.querySelector('.abas').style.setProperty('--aba', String(Math.max(0, ABAS.indexOf(tela.aba))));
    document.body.dataset.tela = TELAS[nome] ? nome : 'inicio';
    $('tela').replaceChildren(...[info.demonstracao && avisoDemonstracao(), tela.montar(id)].flat(2).filter(Boolean));
    // Entrada sutil só ao trocar de tela; redesenhar a mesma (modo discreto, depois de salvar) não anima.
    if (location.hash !== telaAnimada) {
      telaAnimada = location.hash;
      $('tela').classList.remove('entrando', 'empurrando', 'voltando');
      void $('tela').offsetWidth;  // Reinicia a animação.
      $('tela').classList.add(tipoDeEntrada(tela));
      telaAnterior = tela;
    }
    if (tela === TELAS.operacao && dados.operacoes.concat(dados.lixeira).some((r) => r.id === id)) {
      const r = dados.operacoes.find((o) => o.id === id) || dados.lixeira.find((o) => o.id === id);
      $('titulo').textContent = r.nome;
    }
    if (tela === TELAS.documento && documentoPorId(id)) {
      $('titulo').textContent = documentoPorId(id).nome;
    }
    window.scrollTo(0, 0);
  }

  // Voltar (o botão do topo, o gesto ou a tecla de voltar do aparelho): para a tela anterior, se houver; senão,
  // de um detalhe para a aba dele e de uma aba para o Início.
  function telaAtual() {
    return TELAS[location.hash.slice(1).split('/')[0]] || TELAS.inicio;
  }

  function voltar() {
    const tela = telaAtual();
    if (caminho.length > 1) {
      history.back();
    } else {
      location.hash = tela === TELAS[tela.aba] ? '#inicio' : `#${tela.aba}`;
    }
  }

  $('voltar').addEventListener('click', voltar);

  // Tocar de novo na aba que já está acesa também volta: de um detalhe para a tela principal da aba; na tela
  // principal, para a tela anterior.
  document.querySelectorAll('.abas a').forEach((a) => a.addEventListener('click', (evento) => {
    const tela = telaAtual();
    const raiz = `#${a.dataset.aba}`;
    if (!dados || a.dataset.aba !== tela.aba) {
      return;
    }
    evento.preventDefault();
    if (tela === TELAS[a.dataset.aba]) {
      if (caminho.length > 1 || a.dataset.aba !== 'inicio') {
        voltar();
      }
    } else if (caminho.length > 1 && caminho[caminho.length - 2] === raiz) {
      history.back();
    } else {
      location.hash = raiz;
    }
  }));

  function mostrarDiscreto() {
    $('discreto').setAttribute('aria-pressed', String(discreto));
    $('discreto').setAttribute('aria-label', discreto ? 'Mostrar valores' : 'Esconder valores');
    $('discreto').classList.toggle('ligado', discreto);
  }

  // Tema: automático (segue o iPhone), claro (diurno) ou escuro. Fica guardado neste aparelho.
  const TEMAS = [['auto', 'Automático'], ['claro', 'Claro'], ['escuro', 'Escuro']];
  const COR_DO_TOPO = { claro: '#f7f3ee', escuro: '#121519' };

  function aplicarTema(tema) {
    const raiz = document.documentElement;
    if (tema === 'claro' || tema === 'escuro') {
      raiz.dataset.tema = tema;
    } else {
      delete raiz.dataset.tema;
    }
    // A cor da barra de status acompanha o tema escolhido (no automático, cada meta vale para um modo do iPhone).
    document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
      const modo = meta.media.includes('dark') ? 'escuro' : 'claro';
      meta.content = COR_DO_TOPO[raiz.dataset.tema || modo];
    });
  }

  function escolherTema() {
    const atual = localStorageLer('tema') || 'auto';
    return el('div', { class: 'cartao tema' },
      el('div', { class: 'textos' }, el('div', { texto: 'Tema' }),
        el('div', { class: 'discreto pequeno', texto: 'Claro para o dia, escuro para a noite, ou o mesmo do iPhone' })),
      el('div', { class: 'segmentos', role: 'radiogroup', 'aria-label': 'Tema' }, TEMAS.map(([chave, rotulo]) => el('button', {
        type: 'button', role: 'radio', 'aria-checked': String(chave === atual), class: chave === atual ? 'ativo' : '',
        texto: rotulo, onclick: () => {
          localStorageGravar('tema', chave);
          aplicarTema(chave);
          const rolagem = window.scrollY;
          desenhar();
          window.scrollTo(0, rolagem);
        } }))));
  }

  aplicarTema(localStorageLer('tema'));

  discreto = localStorageLer('discreto') === '1';
  mostrarDiscreto();
  $('discreto').addEventListener('click', () => {
    discreto = !discreto;
    localStorageGravar('discreto', discreto ? '1' : '0');
    mostrarDiscreto();
    const rolagem = window.scrollY;
    desenhar();
    window.scrollTo(0, rolagem);
  });
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
    } else if (!guardadoAtual && !demonstracaoDispensada) {
      await abrirDemonstracao().catch(() => {});  // Sem a demonstração, fica a tela de abertura de sempre.
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
