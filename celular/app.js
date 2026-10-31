// Telas do app (só consulta). O backup fica guardado no aparelho como saiu do computador (trancado pela
// senha); os dados abertos ficam só na memória desta página e somem ao trancar ou fechar o app.
//
// Todo texto vindo do backup entra na página por textContent (nunca como HTML).
'use strict';

(() => {
  // Igual a versao.py (test_celular confere): mostrada na abertura e em Mais, para saber se o aparelho já
  // carregou a última versão publicada.
  const VERSAO_APP = '0.64.1';
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
    enviar: ['M12 15V4.5M8 8.5l4-4 4 4', 'M5 14.5v5h14v-5'],
    rosto: ['M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16',
      'M9 9.5v1M15 9.5v1M12 9.5V13h-1M9.5 15.5c1.4 1 3.6 1 5 0'],
    cadeado: ['M6 10.5h12v10H6z', 'M8.5 10.5v-3a3.5 3.5 0 0 1 7 0v3'],
    celular: ['M8 3.5h8v17H8z', 'M11 17.5h2'],
    seta: ['M9 5.5l6.5 6.5L9 18.5'],
    ajustes: ['M4 7h10M18 7h2M4 17h4M12 17h8', 'M16 4.5v5M10 14.5v5'],
    mais: ['M12 5.5v13M5.5 12h13'],
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
    // Um toque copia a chave Pix (para colar no app do banco).
    const copiarPix = conta.pix && navigator.clipboard && el('button', { type: 'button', class: 'secundario copiar-pix',
      texto: 'Copiar chave Pix', onclick: () => navigator.clipboard.writeText(conta.pix)
        .then(() => avisar('Chave Pix copiada.')).catch(() => avisar('Não foi possível copiar agora.')) });
    return el('details', { class: 'cartao conta' },
      el('summary', {}, el('span', { class: 'nome', texto: conta.nome || identificacao || 'Conta removida' }),
        el('span', { class: 'discreto pequeno', texto: identificacao && conta.nome ? identificacao : '' }),
        el('span', { class: 'mostrar discreto pequeno', texto: 'Toque para ver os dados' })),
      campos(detalhes), copiarPix);
  }

  function cartao(...filhos) {
    return el('div', { class: 'cartao' }, ...filhos);
  }

  function vazio(texto) {
    return el('p', { class: 'vazio', texto });
  }

  // ---- Abertura ----------------------------------------------------------------------------------------
  // `fonte` é o arquivo trancado que será aberto: o guardado neste celular ou um que acabou de chegar (dados
  // novos, recuperados da nuvem ou vindos de um convite). Depois de aberto, ele passa a ser o guardado.
  //
  // Os dados são trancados por uma chave sorteada no celular (a chave da casa). A senha de cada pessoa abre o
  // "envelope" com essa chave, guardado aqui e na nuvem (celular/nuvem.js). Nos dados criados antes disso, a
  // senha era a própria chave do arquivo: na primeira abertura com ela, eles ganham o envelope.
  const BLOQUEIO_MS = 5 * 60 * 1000;  // Em segundo plano por mais tempo que isso, o app tranca de novo.
  let fonte = null;
  let senhaRecente = null;  // {chave} até a pessoa responder se quer ativar o Face ID; a senha nunca é gravada.
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

  let guardadoAtual = null;  // O que está guardado neste celular agora.
  let passo = 'novo';        // Sem dados neste celular: 'novo' (nome e senha), 'convite' ou 'nuvem'.
  let mostrarSenha = false;  // Com Face ID ativo, a pessoa tocou em "Usar a senha".

  async function prepararAbertura() {
    const guardado = await Guarda.ler('backup').catch(() => null);
    guardadoAtual = guardado;
    if (!fonte || !fonte.novo) {
      fonte = guardado ? { ...guardado, novo: false } : null;
    }
    const desbloqueio = Boolean(guardado);
    const faceId = desbloqueio && await FaceId.ativo().catch(() => false);
    faceIdAtivo = Boolean(faceId);
    $('fonte').hidden = !desbloqueio;
    if (desbloqueio) {
      $('fonte-titulo').textContent = 'Seus dados, guardados neste celular';
      $('fonte-detalhe').textContent = guardado.criado_em ? `Última gravação: ${D.dataHora(guardado.criado_em)}` : '';
    }
    $('abrir-faceid').hidden = !faceId;
    $('formulario').hidden = !desbloqueio || (faceId && !mostrarSenha);
    $('abrir').textContent = faceId ? 'Abrir com a senha' : 'Abrir';
    $('usar-senha').hidden = !faceId || mostrarSenha;
    // Primeira vez neste celular: nome e senha; ou um convite; ou os dados que já estão na nuvem.
    $('form-novo').hidden = desbloqueio || passo !== 'novo';
    $('form-convite').hidden = desbloqueio || passo !== 'convite';
    $('form-nuvem').hidden = desbloqueio || passo !== 'nuvem';
    $('outras-entradas').hidden = desbloqueio;
    $('recebi-convite').hidden = passo === 'convite';
    $('recuperar-nuvem').hidden = passo === 'nuvem';
    $('ver-demonstracao').hidden = desbloqueio || passo !== 'novo';
    $('voltar-abertura').hidden = !emPassoDaAbertura();
    return faceId;
  }

  function emPassoDaAbertura() {
    return Boolean((guardadoAtual && mostrarSenha) || (!guardadoAtual && passo !== 'novo'));
  }

  // Cada passo da abertura entra no histórico: o gesto ou a tecla de voltar do aparelho também volta dele.
  function irParaPasso(novo, foco) {
    if (!emPassoDaAbertura()) {
      history.pushState({ passo: true }, '', location.pathname + location.search + '#passo');
    }
    if (novo === 'senha') {
      mostrarSenha = true;
    } else {
      passo = novo;
    }
    mostrarErro('');
    prepararAbertura().then(() => $(foco).focus());
  }

  function sairDoPasso() {
    passo = 'novo';
    mostrarSenha = false;
    mostrarErro('');
    ['form-convite', 'form-nuvem'].forEach((id) => $(id).reset());
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
  $('recebi-convite').addEventListener('click', () => irParaPasso('convite', 'codigo-convite'));
  $('recuperar-nuvem').addEventListener('click', () => irParaPasso('nuvem', 'senha-nuvem'));
  $('usar-senha').addEventListener('click', () => irParaPasso('senha', 'senha'));

  // No iPhone, o Safari e o app da Tela de Início guardam dados separados: começar no Safari deixaria os dados
  // fora do app.
  function confirmarForaDoSafari() {
    const noSafariDoIphone = /iPhone|iPad/.test(navigator.userAgent) && !instalado;
    return !noSafariDoIphone || confirm('Você está no Safari. Os dados criados aqui não aparecem no app da Tela de Início. '
      + 'O certo é tocar em Compartilhar → Adicionar à Tela de Início e começar pelo ícone. Continuar aqui mesmo assim?');
  }

  function conferirNomeESenha(nome, senha, repetida) {
    if (!nome.trim()) {
      throw new Error('Digite o seu nome.');
    }
    D.validarSenha(senha);
    if (senha !== repetida) {
      throw new Error('As duas senhas não são iguais.');
    }
  }

  // Guarda neste celular o envelope da pessoa e o acesso à nuvem (que fica sempre ligada).
  async function guardarAcesso({ pessoa, conteudo, envelope, nome, membroPendente = null }) {
    await Guarda.gravar('envelope', envelope);
    await guardarNuvem({ id: conteudo.cofre.id, chave: conteudo.cofre.chave, backup: true, lembretes: false,
      membro: { id: pessoa.id, chave: pessoa.chave }, membroPendente });
    if (nome) {
      localStorageGravar('nome', nome.trim());
    }
  }

  async function executarNaAbertura(botao, tarefa) {
    mostrarErro('');
    $(botao).disabled = true;
    try {
      await tarefa();
    } catch (erro) {
      $('andamento').hidden = true;
      mostrarErro(erro && erro.message ? erro.message : String(erro));
    } finally {
      $(botao).disabled = false;
    }
  }

  // Dados novos: o banco vazio (modelo.sqlite3) trancado com a chave da casa, sorteada agora; a senha tranca o
  // envelope, e o cofre na nuvem nasce no primeiro envio.
  $('form-novo').addEventListener('submit', (evento) => {
    evento.preventDefault();
    executarNaAbertura('criar', async () => {
      const nome = $('nome-novo').value;
      const senha = $('senha-nova').value;
      conferirNomeESenha(nome, senha, $('senha-repetida').value);
      if (!confirmarForaDoSafari()) {
        return;
      }
      const pessoa = await Nuvem.credenciais(senha, (p) => mostrarAndamento('Preparando a senha…', p * 0.8));
      const chave = { sal: crypto.getRandomValues(new Uint8Array(16)), bruta: crypto.getRandomValues(new Uint8Array(32)) };
      const conteudo = { ...chave, cofre: Nuvem.cofreNovo() };
      const SQL = await LeitorBackup.sqlJs();
      const modelo = new SQL.Database(new Uint8Array(await (await fetch('modelo.sqlite3')).arrayBuffer()));
      const banco = modelo.export();
      modelo.close();
      const { bytes, manifesto } = await LeitorBackup.empacotar(banco, chave, VERSAO_APP);
      const envelope = await Nuvem.fecharEnvelope(pessoa.envelope, conteudo);
      await guardarAcesso({ pessoa, conteudo, envelope, nome, membroPendente: envelope });
      gravarEstadoNuvem({});
      fonte = { bytes, nome: 'GestorRPV-celular.rpvbackup', tamanho: bytes.length, criado_em: manifesto.criado_em, novo: true };
      $('form-novo').reset();
      await abrirFonte({ chave });
    });
  });

  // Convite: o código abre o envelope que a outra pessoa deixou na nuvem; esta pessoa fecha o seu, com a senha dela.
  $('form-convite').addEventListener('submit', (evento) => {
    evento.preventDefault();
    executarNaAbertura('entrar-convite', async () => {
      const convite = await Nuvem.chavesDoConvite($('codigo-convite').value);
      if (!convite.valido) {
        throw new Error('O código tem 10 letras e números, como K7P2Q-9XMRT.');
      }
      const nome = $('nome-convite').value;
      const senha = $('senha-convite').value;
      conferirNomeESenha(nome, senha, $('senha-convite-repetida').value);
      if (!confirmarForaDoSafari()) {
        return;
      }
      mostrarAndamento('Conferindo o código…', 0.05);
      const envelopeConvite = await Nuvem.lerConvite(convite);
      if (!envelopeConvite) {
        throw new Error('Código inválido ou vencido. Peça um código novo a quem convidou.');
      }
      const conteudo = await Nuvem.abrirEnvelope(convite.chave, envelopeConvite);
      const pessoa = await Nuvem.credenciais(senha, (p) => mostrarAndamento('Preparando a senha…', 0.1 + p * 0.5));
      mostrarAndamento('Baixando os dados…', 0.65);
      const meta = await Nuvem.consultar(conteudo.cofre);
      if (!meta) {
        throw new Error('Os dados de quem convidou ainda não estão na nuvem. Peça para abrir o app e gerar outro código.');
      }
      const bytes = await Nuvem.baixar(conteudo.cofre, meta, (p) => mostrarAndamento('Baixando os dados…', 0.65 + p * 0.25));
      const envelope = await Nuvem.fecharEnvelope(pessoa.envelope, conteudo);
      await Nuvem.guardarMembro(pessoa, conteudo.cofre, { envelope, nome: nome.trim(), convite: convite.id });
      await guardarAcesso({ pessoa, conteudo, envelope, nome });
      gravarEstadoNuvem({ versao: meta.versao, criado_em: meta.criado_em, sincronizado_em: LeitorBackup.dataHoraLocal() });
      fonte = { bytes, nome: 'GestorRPV-celular.rpvbackup', tamanho: bytes.length, criado_em: meta.criado_em, novo: true };
      passo = 'novo';
      $('form-convite').reset();
      await abrirFonte({ chave: { sal: conteudo.sal, bruta: conteudo.bruta } });
    });
  });

  // Celular novo: a senha acha o envelope da pessoa na nuvem e, com ele, os dados. Nos dados antigos (antes do
  // envelope), a própria senha acha o backup.
  $('form-nuvem').addEventListener('submit', (evento) => {
    evento.preventDefault();
    executarNaAbertura('baixar-nuvem', async () => {
      const senha = $('senha-nuvem').value;
      if (!senha) {
        throw new Error('Digite a senha.');
      }
      if (!confirmarForaDoSafari()) {
        return;
      }
      const pessoa = await Nuvem.credenciais(senha, (p) => mostrarAndamento('Conferindo a senha…', p * 0.5));
      mostrarAndamento('Procurando na nuvem…', 0.5);
      const registro = await Nuvem.lerMembro(pessoa);
      const conteudo = registro && await Nuvem.abrirEnvelope(pessoa.envelope, registro.envelope);
      const cofre = conteudo ? conteudo.cofre : pessoa;
      const meta = await Nuvem.consultar(cofre);
      if (!meta) {
        throw new Error('Nenhum dado na nuvem com essa senha. Confira a senha (maiúsculas, acentos e espaços contam).');
      }
      const bytes = await Nuvem.baixar(cofre, meta, (p) => mostrarAndamento('Baixando os dados…', 0.5 + p * 0.4));
      if (conteudo) {
        await guardarAcesso({ pessoa, conteudo, envelope: registro.envelope, nome: registro.nome });
      }
      gravarEstadoNuvem({ versao: meta.versao, criado_em: meta.criado_em, sincronizado_em: LeitorBackup.dataHoraLocal() });
      fonte = { bytes, nome: 'GestorRPV-celular.rpvbackup', tamanho: bytes.length, criado_em: meta.criado_em, novo: true };
      passo = 'novo';
      $('form-nuvem').reset();
      await (conteudo ? abrirFonte({ chave: { sal: conteudo.sal, bruta: conteudo.bruta } }) : abrirFonte({ senha, pessoa }));
    });
  });

  let faceIdAtivo = false;

  let bancoLocal = null;  // Banco aberto (sql.js): as gravações vão para ele.

  // Destinos que podem chegar antes de os dados abrirem (o toque num lembrete): ficam para depois da senha.
  const DESTINOS_GUARDADOS = ['#agenda', '#atrasadas'];

  async function abrirFonte({ senha = '', faceId = false, automatico = false, chave: chaveDada = null, pessoa = null }) {
    mostrarErro('');
    $('abrir').disabled = true;
    $('abrir-faceid').disabled = true;
    try {
      if (!fonte) {
        throw new LeitorBackup.ErroBackup('Não há dados guardados neste celular.');
      }
      let chave = chaveDada;
      let senhaLegada = null;  // Dados antigos: a senha que abre o arquivo direto (para criar o envelope).
      let liberado = null;
      if (faceId) {
        mostrarAndamento('Aguardando o Face ID…', 0);
        liberado = await FaceId.abrir();
        if (liberado.segredo.sal) {
          chave = { sal: FaceId.deB64(liberado.segredo.sal), bruta: FaceId.deB64(liberado.segredo.bruta) };
        }
        senha = liberado.segredo.senha || '';
      }
      const envelope = await Guarda.ler('envelope').catch(() => null);
      if (!envelope && senha) {
        senhaLegada = senha;
      }
      if (!chave && senha && envelope) {
        const credenciais = pessoa || await Nuvem.credenciais(senha, (p) => mostrarAndamento('Conferindo a senha…', p * 0.9));
        try {
          const conteudo = await Nuvem.abrirEnvelope(credenciais.envelope, envelope);
          chave = { sal: conteudo.sal, bruta: conteudo.bruta };
        } catch (erro) {
          throw new LeitorBackup.SenhaIncorreta('Senha incorreta.');
        }
      }
      mostrarAndamento('Abrindo…', 0.05);
      const leitura = await LeitorBackup.ler(new Uint8Array(fonte.bytes), senhaLegada || '', {
        chave,
        // A senha leva alguns segundos de propósito (é o que impede tentativas em massa); a barra mostra o andamento.
        aoProgredir: (etapa, fracao) => mostrarAndamento(`${ETAPAS[etapa]}…`, etapa === 'senha' ? fracao * 0.9 : 0.9 + fracao * 0.1),
      });
      if (!leitura.cifrado) {
        leitura.db.close();
        throw new LeitorBackup.ErroBackup('Este arquivo não tem senha e não pode ser usado.');
      }
      dados = D.carregar(leitura.db);
      bancoLocal = leitura.db;
      info = { arquivo: fonte.nome, tamanho: fonte.tamanho, manifesto: leitura.manifesto, cifrado: true,
        tempos: leitura.tempos, extrair: leitura.extrair, todos: leitura.todos, chave: leitura.chave, independente: true };
      if (fonte.novo) {
        fonte = { bytes: fonte.bytes, nome: fonte.nome, tamanho: fonte.tamanho, criado_em: leitura.manifesto.criado_em,
          guardado_em: new Date().toISOString(), novo: false, independente: true };
        await Guarda.gravar('backup', { ...fonte, novo: undefined }).catch(() => {
          info.naoGuardado = true;  // Sem espaço ou sem permissão: funciona agora, mas precisará baixar de novo.
        });
        Guarda.persistir();
      }
      if (liberado && (liberado.segredo.senha || liberado.segredo.sal !== FaceId.paraB64(leitura.chave.sal))) {
        // O Face ID passa a guardar só a chave (nunca a senha), e a chave destes dados.
        await liberado.atualizar(segredoDe(leitura.chave)).catch(() => {});
      }
      senhaRecente = !faceId ? { chave: leitura.chave } : null;
      if (senhaRecente) {
        senhaRecente.oferecer = !faceIdAtivo && await FaceId.possivel() && !localStorageLer('faceid_recusado');
      }
      $('formulario').reset();
      $('andamento').hidden = true;
      $('abertura').hidden = true;
      $('aplicativo').hidden = false;
      const destino = DESTINOS_GUARDADOS.includes(location.hash) ? location.hash : '#inicio';
      if (location.hash === destino) {
        desenhar();
      } else if (location.hash === '#passo') {
        location.replace(destino);  // O passo da abertura não fica no histórico do app aberto.
      } else {
        location.hash = destino;
      }
      aposAbrirDados({ senhaLegada: envelope ? null : senhaLegada });
    } catch (erro) {
      const cancelado = erro && (erro.name === 'NotAllowedError' || erro.name === 'AbortError');
      if (automatico && cancelado) {
        mostrarErro('');  // O iPhone pode exigir um toque antes do Face ID: o botão continua ali.
        return;
      }
      mostrarErro(cancelado ? 'Face ID cancelado. Toque em "Abrir com Face ID" para tentar de novo, ou use a senha.'
        : erro instanceof LeitorBackup.SenhaIncorreta && faceId
          ? 'O Face ID guardava uma chave antiga (os dados ganharam uma chave nova). Digite a senha.'
          : erro instanceof LeitorBackup.SenhaIncorreta ? 'Senha incorreta.'
            : erro instanceof LeitorBackup.ErroBackup || erro instanceof FaceId.FaceIdIndisponivel ? erro.message
              : 'Não foi possível abrir os dados neste aparelho: ' + (erro && erro.message ? erro.message : erro));
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
    $('abertura').hidden = true;
    $('aplicativo').hidden = false;
    if (location.hash === '#inicio') {
      desenhar();
    } else {
      location.hash = '#inicio';
    }
  }

  // Para os testes automáticos: tranca como o app faz sozinho depois de 5 minutos em segundo plano, e abre um
  // arquivo .rpvbackup com a senha dele (como o app fazia com o arquivo do computador), virando os dados deste celular.
  window.trancarGestor = () => fecharDados();
  window.abrirArquivoGestor = async (bytes, senha, nome = 'teste.rpvbackup') => {
    await Promise.all([Guarda.apagar('envelope'), Guarda.apagar('nuvem')]).catch(() => {});
    fonte = { bytes: new Uint8Array(bytes).buffer, nome, tamanho: bytes.length, novo: true };
    await abrirFonte({ senha });
  };

  function sairDaDemonstracao() {
    demonstracaoDispensada = true;
    return fecharDados();
  }

  $('ver-demonstracao').addEventListener('click', () => {
    abrirDemonstracao().catch((erro) => mostrarErro('Não foi possível abrir a demonstração: ' + (erro && erro.message ? erro.message : erro)));
  });

  // O que o Face ID guarda: só a chave dos dados (a senha nunca).
  function segredoDe(chave) {
    return { sal: FaceId.paraB64(chave.sal), bruta: FaceId.paraB64(chave.bruta) };
  }

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
      const completar = await FaceId.ativar(segredoDe(senhaRecente.chave));
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
    filaNuvem = [];
    passo = 'novo';
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
    if (!confirm('Apagar os dados deste celular e desativar o Face ID do app? Eles continuam na nuvem: para trazer de '
      + 'volta, use "Já tenho dados: recuperar da nuvem", com a sua senha.')) {
      return;
    }
    if (estadoNuvem().criado_em !== info.manifesto.criado_em && !confirm('A última mudança ainda não chegou à nuvem e '
      + 'será perdida. Apagar mesmo assim?')) {
      return;
    }
    await Promise.all(['backup', 'envelope', 'nuvem'].map((k) => Guarda.apagar(k)).concat(FaceId.desativar())).catch(() => {});
    localStorageGravar('nuvem_estado', '{}');
    nuvem = null;
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
    } else if (dados && info && !info.demonstracao) {
      sincronizarAgora().catch(() => {});  // O outro celular da casa pode ter mudado algo enquanto este estava parado.
    }
    escondidoEm = null;
  });

  // ---- Telas ---------------------------------------------------------------------------------------------
  function telaInicio() {
    const ind = D.indicadores(dados.operacoes);
    const totais = D.contarSituacoes(dados.operacoes);
    const indicador = (rotulo, valor, classe, simbolo) => el('div', { class: 'indicador ' + (classe || '') },
      el('span', { class: 'icone-indicador' }, icone(simbolo)),
      el('div', { class: 'textos' }, el('div', { class: 'rotulo', texto: rotulo }), el('div', { class: 'valor', texto: valor })));
    // Atalhos grandes, no lugar da antiga "Situação das operações" (a agenda já mostra o que está atrasado).
    const atalho = (href, rotulo, detalhe, simbolo, classe, aoTocar) => el('a', { class: 'atalho ' + (classe || ''), href,
      onclick: aoTocar }, el('span', { class: 'icone-atalho' }, icone(simbolo)),
    el('span', { class: 'textos' }, el('span', { class: 'nome', texto: rotulo }), el('span', { class: 'pequeno', texto: detalhe })));
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
      // A nuvem é a cópia de segurança: só aparece aviso se ela ainda não foi ligada (dados antigos abertos pelo
      // Face ID) ou no raro caso de este celular e outro terem mudado os dados ao mesmo tempo.
      !info.demonstracao && nuvemCarregada && !(nuvem && nuvem.backup) && el('a', { class: 'aviso item', href: '#ajustes' },
        el('div', { class: 'nome', texto: 'Ligue o backup na nuvem' }),
        el('div', { class: 'discreto pequeno', texto: 'Em Mais → Ajustes, confirme a sua senha uma vez: os dados passam a ir para a nuvem a cada gravação.' })),
      !info.demonstracao && estadoNuvem().conflito_dados && el('a', { class: 'aviso item', href: '#ajustes' },
        el('div', { class: 'nome', texto: 'Dados mudados em dois aparelhos ao mesmo tempo' }),
        el('div', { class: 'discreto pequeno', texto: 'Toque para escolher quais ficam.' })),
      dados.demonstracao && !info.demonstracao && el('p', { class: 'aviso', texto: 'Este backup tem dados de demonstração, com nomes e valores fictícios.' }),
      !info.demonstracao && !dados.operacoes.length && el('div', { class: 'aviso' },
        el('div', { class: 'nome', texto: 'Por onde começar' }),
        el('div', { texto: '1. Cadastre a conta onde você recebe, na aba Contas.' }),
        el('div', { texto: '2. Cadastre suas entradas na aba Operações (+ Nova entrada).' }),
        el('div', { texto: '3. Quando receber, abra a operação e toque em "Registrar recebimento".' })),
      // O título da página, de onde vêm os dados e os quatro indicadores: o lucro previsto em terracota.
      el('section', { class: 'panorama' },
        el('div', { class: 'saudacao', texto: !info.demonstracao && nomeDono() ? `Olá, ${nomeDono()}!` : 'Olá!' }),
        el('h2', { class: 'panorama-titulo', texto: 'Seu panorama' }),
        !info.demonstracao && el('p', { class: 'panorama-fonte', texto: textoSincronia() })),
      el('div', { class: 'indicadores' },
        indicador('Lucro previsto', reais(ind.previsto), 'principal', 'tendencia'),
        indicador('Registros', String(ind.registros), '', 'documento'),
        indicador('Capital investido em aberto', reais(ind.aberto), '', 'moedas'),
        indicador('Lucro realizado', reais(ind.realizado), 'verde', 'dinheiro')),
      dados.operacoes.length > 0 && cartaoAgenda(),
      el('div', { class: 'atalhos' },
        atalho('#nova', 'Nova entrada', 'Cadastrar uma operação', 'mais', 'principal'),
        atalho('#operacoes', 'Pendentes', D.quantidade(totais.pendente, 'operação', 'operações'), 'documento', '', () => {
          estado.filtro = 'pendente';
          estado.busca = '';
        }),
        atalho('#grafico', 'Gráfico', 'Últimos 12 meses', 'barras', 'ambar')),
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
    const nova = el('a', { class: 'botao-link primario', href: '#nova', texto: '+ Nova entrada' });
    return [nova, busca, filtros, lista];
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
    geracao += 1;
  }

  // ---- Gravar e sincronizar ------------------------------------------------------------------------------
  // Cada gravação é uma `operacao` que muda o banco aberto e devolve {valor, novos, removidos}. Antes de gravar, o
  // app puxa o que outro celular da casa mandou; depois, manda os dados para a nuvem. Se outro aparelho gravou
  // nesse meio-tempo (a nuvem recusa por estar desatualizado), o app baixa a versão nova, refaz as operações que
  // ainda não subiram e manda de novo: nada se perde. Tudo isso acontece por trás; na tela, só um texto pequeno.
  let geracao = 0;            // Muda a cada gravação local.
  let filaNuvem = [];         // [{operacao, geracao}] gravadas aqui e ainda não confirmadas pela nuvem.
  let trabalho = Promise.resolve();

  // Um de cada vez: gravar, puxar e refazer nunca se cruzam.
  function emOrdem(tarefa) {
    const resultado = trabalho.then(tarefa, tarefa);
    trabalho = resultado.catch(() => {});
    return resultado;
  }

  function gravar(operacao, mensagem) {
    return emOrdem(async () => {
      await puxarDaNuvem();
      const r = operacao() || {};
      await salvarLocal(r.novos, r.removidos);
      filaNuvem.push({ operacao, geracao });
      if (mensagem) {
        avisar(typeof mensagem === 'function' ? mensagem(r.valor) : mensagem);
      }
      agendarEnvioNuvem();
      sincronizarLembretes();
      atualizarSelo();
      return r.valor;
    });
  }

  // ---- Nuvem (celular/nuvem.js) ----
  // `nuvem` fica guardado no aparelho: o cofre ({id, chave}), a pessoa (`membro`), se os lembretes estão ligados e
  // o token do calendário. O backup na nuvem fica sempre ligado.
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
  const cofreAtual = () => nuvem && { id: nuvem.id, chave: nuvem.chave };
  const podeSincronizar = () => Boolean(nuvem && nuvem.backup && info && !info.demonstracao && bancoLocal);
  const nomeDono = () => (localStorageLer('nome') || '').trim();

  let nuvemCarregada = false;
  async function carregarNuvem() {
    nuvem = await Guarda.ler('nuvem').catch(() => null) || null;
    nuvemCarregada = true;
  }

  async function guardarNuvem(valor) {
    nuvem = valor;
    await Guarda.gravar('nuvem', valor);
  }

  const telasDeFormulario = new Set(['nova', 'editar', 'nova-conta', 'editar-conta', 'compartilhar']);

  // Redesenha a tela à frente com os dados novos, sem perder a rolagem; nunca no meio de um formulário, nem com
  // algo aberto ou sendo digitado (os dados novos aparecem na próxima tela).
  function redesenharSemPular() {
    const tela = $('tela');
    const ocupada = tela.querySelector('details[open]') || (document.activeElement && tela.contains(document.activeElement)
      && /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName));
    if (!dados || ocupada || telasDeFormulario.has(location.hash.slice(1).split('/')[0])) {
      return;
    }
    const rolagem = window.scrollY;
    desenhar();
    window.scrollTo(0, rolagem);
  }

  // Depois de um envio, só o texto pequeno muda (o Início e o cartão da nuvem em Ajustes); a tela não é redesenhada.
  function atualizarTextoSincronia() {
    if (!info || info.demonstracao) {
      return;
    }
    document.querySelectorAll('.panorama-fonte').forEach((p) => { p.textContent = textoSincronia(); });
    if (location.hash === '#ajustes' && !$('tela').querySelector('form input:focus')) {
      redesenharSemPular();
    }
  }

  // "Sincronizado às 14:32": o único sinal da sincronização na tela.
  function textoSincronia() {
    const estado = estadoNuvem();
    if (enviandoNuvem) {
      return 'Sincronizando…';
    }
    if (!nuvem || !nuvem.backup) {
      return 'Guardado neste celular';
    }
    if (estado.erro || estado.criado_em !== info.manifesto.criado_em) {
      return 'Guardado neste celular · sincroniza ao voltar a internet';
    }
    const quando = estado.sincronizado_em;
    if (!quando) {
      return 'Sincronizado';
    }
    return quando.slice(0, 10) === D.hojeIso() ? `Sincronizado às ${quando.slice(11, 16)}` : `Sincronizado em ${D.dataHora(quando)}`;
  }

  function agendarEnvioNuvem(atraso = 800) {
    if (!podeSincronizar()) {
      return;
    }
    clearTimeout(temporizadorNuvem);
    temporizadorNuvem = setTimeout(() => enviarNuvem().catch(() => {}), atraso);
  }

  async function enviarNuvem({ substituir = false, tentativas = 3 } = {}) {
    if (!podeSincronizar()) {
      return;
    }
    if (enviandoNuvem) {
      await enviandoNuvem.catch(() => {});
    }
    const criadoEm = info.manifesto.criado_em;
    const enviada = geracao;
    const estado = estadoNuvem();
    if (estado.criado_em === criadoEm && !substituir && !estado.erro) {
      return;  // Já está na nuvem.
    }
    enviandoNuvem = (async () => {
      try {
        const meta = await Nuvem.enviar(cofreAtual(), new Uint8Array(fonte.bytes), { sal: info.chave.sal, criadoEm,
          base: estado.versao || null, substituir });
        gravarEstadoNuvem({ versao: meta.versao, criado_em: criadoEm, sincronizado_em: LeitorBackup.dataHoraLocal() });
        filaNuvem = filaNuvem.filter((item) => item.geracao > enviada);
        if (nuvem.membroPendente) {
          // Dados novos: depois do primeiro envio, a pessoa passa a ser reconhecida pela senha num celular novo.
          await Nuvem.guardarMembro(nuvem.membro, cofreAtual(), { envelope: nuvem.membroPendente, nome: nomeDono() })
            .then(() => guardarNuvem({ ...nuvem, membroPendente: null })).catch(() => {});
        }
      } catch (erro) {
        if (erro.desatualizado && tentativas > 0) {
          enviandoNuvem = null;
          if (await emOrdem(() => juntarComANuvem()) === 'refeito') {
            return enviarNuvem({ tentativas: tentativas - 1 });
          }
        }
        gravarEstadoNuvem({ ...estadoNuvem(), erro: erro.message, conflito: Boolean(erro.conflito),
          desatualizado: Boolean(erro.desatualizado), outro_em: erro.criadoEm || null });
        throw erro;
      } finally {
        enviandoNuvem = null;
        atualizarTextoSincronia();
      }
    })();
    atualizarTextoSincronia();
    return enviandoNuvem;
  }

  // Abre os dados que vieram da nuvem no lugar dos daqui (mesma chave: a da casa).
  async function trocarPelosDaNuvem(meta) {
    const bytes = await Nuvem.baixar(cofreAtual(), meta);
    const leitura = await LeitorBackup.ler(bytes, '', { chave: info.chave });
    if (bancoLocal) {
      bancoLocal.close();
    }
    bancoLocal = leitura.db;
    dados = D.carregar(bancoLocal);
    Object.assign(info, { manifesto: leitura.manifesto, extrair: leitura.extrair, todos: leitura.todos });
    fonte = { ...fonte, bytes, tamanho: bytes.length, criado_em: leitura.manifesto.criado_em, independente: true };
    await Guarda.gravar('backup', { bytes, nome: fonte.nome, tamanho: bytes.length, criado_em: leitura.manifesto.criado_em,
      guardado_em: new Date().toISOString(), independente: true });
    gravarEstadoNuvem({ versao: meta.versao, criado_em: leitura.manifesto.criado_em, sincronizado_em: LeitorBackup.dataHoraLocal() });
  }

  // Outro celular gravou: traz a versão dele e refaz por cima as gravações daqui que ainda não tinham subido.
  // Mudanças daqui de antes de o app ser fechado não têm como ser refeitas: aí a pessoa escolhe (é raro).
  async function juntarComANuvem() {
    const meta = await Nuvem.consultar(cofreAtual());
    if (!meta) {
      return 'nada';
    }
    const pendentes = filaNuvem;
    if (!pendentes.length) {
      gravarEstadoNuvem({ ...estadoNuvem(), conflito_dados: true });
      return 'conflito';
    }
    await trocarPelosDaNuvem(meta);
    let novos = {};
    let removidos = [];
    filaNuvem = [];
    for (const item of pendentes) {
      try {
        const r = item.operacao() || {};
        novos = { ...novos, ...(r.novos || {}) };
        removidos = [...removidos, ...(r.removidos || [])];
        filaNuvem.push({ operacao: item.operacao, geracao: geracao + 1 });
      } catch (erro) {
        // A operação não cabe mais (o outro aparelho excluiu a mesma entrada, por exemplo): fica de fora.
      }
    }
    await salvarLocal(novos, removidos);
    gravarEstadoNuvem({ ...estadoNuvem(), criado_em: null });
    return 'refeito';
  }

  // A escolha do raro conflito: ficar com o que está neste celular ou com o que está na nuvem.
  async function resolverConflito(manterDaqui) {
    if (manterDaqui) {
      gravarEstadoNuvem({ ...estadoNuvem(), conflito_dados: false });
      await enviarNuvem({ substituir: true });
    } else {
      await emOrdem(async () => {
        const meta = await Nuvem.consultar(cofreAtual());
        if (meta) {
          await trocarPelosDaNuvem(meta);
        }
        filaNuvem = [];
      });
    }
    redesenharSemPular();
  }

  // Antes de gravar e ao voltar ao app: há algo mais novo na nuvem (de outro celular)? Sem internet, segue.
  async function puxarDaNuvem() {
    if (!podeSincronizar() || filaNuvem.length || enviandoNuvem) {
      return;
    }
    const estado = estadoNuvem();
    if (estado.criado_em !== info.manifesto.criado_em) {
      return;  // Há mudanças daqui ainda não enviadas: o envio junta as duas.
    }
    let meta;
    try {
      meta = await Promise.race([Nuvem.consultar(cofreAtual()), new Promise((_, falha) => setTimeout(() => falha(new Error('demora')), 5000))]);
    } catch (erro) {
      return;
    }
    if (!meta) {
      return;
    }
    if (meta.versao === estado.versao) {
      gravarEstadoNuvem({ ...estado, sincronizado_em: LeitorBackup.dataHoraLocal() });
      return;
    }
    try {
      await trocarPelosDaNuvem(meta);
    } catch (erro) {
      if (erro instanceof LeitorBackup.SenhaIncorreta) {
        // A chave da casa foi trocada em outro aparelho (acesso removido): este celular segue com o que tem.
        gravarEstadoNuvem({ ...estado, erro: 'Os dados compartilhados não abrem mais com este celular.' });
      }
    }
  }

  // Ao voltar ao app (e ao abrir): puxa por trás e redesenha só se algo mudou.
  async function sincronizarAgora() {
    const antes = info && info.manifesto.criado_em;
    await emOrdem(() => puxarDaNuvem());
    if (info && info.manifesto.criado_em !== antes) {
      redesenharSemPular();
      sincronizarLembretes();
      atualizarSelo();
    }
  }

  // Depois de abrir os dados: o que ficou sem enviar vai agora; se não, puxa o que outro celular mudou.
  async function aposAbrirDados({ senhaLegada = null } = {}) {
    await carregarNuvem();
    if (senhaLegada) {
      await adotarEnvelope(senhaLegada, info.chave).catch(() => {});
    }
    if (location.hash === '#inicio') {
      redesenharSemPular();
    }
    atualizarSelo();
    if (podeSincronizar()) {
      if (estadoNuvem().criado_em !== info.manifesto.criado_em) {
        agendarEnvioNuvem(0);
      } else {
        sincronizarAgora();
      }
    }
    sincronizarLembretes();
  }

  // Dados de antes do envelope (a senha abria o arquivo direto): passam a ter envelope, e a nuvem fica ligada.
  async function adotarEnvelope(senha, chave) {
    const pessoa = await Nuvem.credenciais(senha);
    const cofre = nuvem && nuvem.id ? { id: nuvem.id, chave: nuvem.chave } : { id: pessoa.id, chave: pessoa.chave };
    const envelope = await Nuvem.fecharEnvelope(pessoa.envelope, { ...chave, cofre });
    await Guarda.gravar('envelope', envelope);
    await guardarNuvem({ ...(nuvem || {}), ...cofre, backup: true, membro: { id: pessoa.id, chave: pessoa.chave },
      membroPendente: envelope });
  }

  // ---- Número no ícone: previsões atrasadas e as de hoje ----
  function atualizarSelo() {
    if (!navigator.setAppBadge || !dados || (info && info.demonstracao)) {
      return;
    }
    const hoje = D.hojeIso();
    const total = dados.operacoes.filter((r) => !r.recebimento && r.previsao_atual <= hoje).length;
    (total ? navigator.setAppBadge(total) : navigator.clearAppBadge()).catch(() => {});
  }

  // ---- Lembretes e calendário ----
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
      await Nuvem.guardarLembretes(cofreAtual(), assinatura.toJSON(), previsoes, nuvem.calendario);
      localStorageGravar('lembretes_enviados', marca);
    } catch (erro) {
      // Sem internet agora: a lista vai na próxima gravação ou abertura.
    }
  }

  // Um toque: notificações (o pedido de permissão precisa ser a primeira coisa do toque) e, em seguida, o
  // calendário das previsões no app Calendário do iPhone.
  async function ligarLembretes() {
    const permissao = await Notification.requestPermission();
    if (permissao !== 'granted') {
      throw new Error('As notificações não foram permitidas. Ative em Ajustes → Notificações → Gestor RPV.');
    }
    const registro = await navigator.serviceWorker.ready;
    const assinatura = await registro.pushManager.getSubscription()
      || await registro.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: deB64url(await Nuvem.chaveVapid()) });
    const calendario = nuvem.calendario || Nuvem.tokenCalendario();
    await Nuvem.guardarLembretes(cofreAtual(), assinatura.toJSON(), datasDasPrevisoes(), calendario);
    await guardarNuvem({ ...nuvem, lembretes: true, calendario });
    localStorageGravar('lembretes_enviados', '');
    assinarCalendario();
  }

  // O iPhone pergunta "Assinar este calendário?"; daí em diante, ele mesmo busca as datas novas de tempos em tempos.
  function assinarCalendario() {
    const link = el('a', { href: Nuvem.enderecoCalendario(nuvem.calendario) });
    document.body.append(link);
    link.click();
    link.remove();
  }

  async function desligarLembretes() {
    const registro = await navigator.serviceWorker.ready.catch(() => null);
    const assinatura = registro && await registro.pushManager.getSubscription().catch(() => null);
    if (assinatura) {
      await Nuvem.apagarLembretes(cofreAtual(), assinatura.endpoint).catch(() => {});
      await assinatura.unsubscribe().catch(() => {});
    }
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
  function gravarEntradaLocal(entrada, conta, documentos = []) {
    return gravar(() => {
      const id = inserir('rpvs', {
        nome: D.nomeTitulo(entrada.nome), aquisicao: entrada.aquisicao, previsto: entrada.previsto, custo: entrada.custo,
        conta: conta.identificacao, previsao: entrada.previsao, comissao: entrada.comissao,
        observacoes: D.primeiraMaiuscula(entrada.observacoes), conta_id: conta.id, conta_snapshot: D.snapshotConta(conta),
      });
      return { valor: id, novos: registrarDocumentos(id, documentos) };
    }, 'Entrada salva.');
  }

  // Como Banco.salvar com um identificador: a conta (e a cópia dos dados dela) só muda se outra foi escolhida.
  function editarLocal(r, entrada, conta) {
    const mesma = conta.manter || conta.id === r.conta_id;
    return gravar(() => {
      bancoLocal.run(`UPDATE rpvs SET nome=?, aquisicao=?, previsto=?, custo=?, previsao=?, comissao=?, observacoes=?,
        conta=?, conta_id=?, conta_snapshot=? WHERE id=? AND lixeira_em IS NULL`, [
        D.nomeTitulo(entrada.nome), entrada.aquisicao, entrada.previsto, entrada.custo, entrada.previsao, entrada.comissao,
        D.primeiraMaiuscula(entrada.observacoes), mesma ? r.conta : conta.identificacao, mesma ? r.conta_id : conta.id,
        mesma ? r.conta_snapshot : D.snapshotConta(conta), r.id]);
    }, 'Alterações salvas.');
  }

  // Como Banco.atualizar_previsao: a previsão anterior fica no histórico.
  function previsaoLocal(r, nova) {
    const quando = LeitorBackup.dataHoraLocal();
    return gravar(() => {
      bancoLocal.run('INSERT INTO previsoes_historico (rpv_id,anterior,nova,alterada_em) VALUES (?,?,?,?)',
        [r.id, r.previsao_atual, nova, quando]);
      bancoLocal.run('UPDATE rpvs SET previsao_atual_definida=? WHERE id=?', [nova, r.id]);
    }, 'Previsão atualizada.');
  }

  // Excluir manda para a lixeira (como no computador); restaurar tira de lá.
  function lixeiraLocal(r, excluir) {
    const quando = excluir ? LeitorBackup.dataHoraLocal() : null;
    return gravar(() => {
      bancoLocal.run('UPDATE rpvs SET lixeira_em=? WHERE id=?', [quando, r.id]);
    }, excluir ? 'Operação enviada à lixeira.' : 'Operação restaurada.');
  }

  // Como Banco.excluir_permanentemente: só sai de vez quem está na lixeira, com o histórico, as prorrogações e os
  // anexos (que deixam de ir no pacote).
  function excluirDeVez(r) {
    return gravar(() => {
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
      return { removidos: caminhos };
    }, 'Operação excluída de vez.');
  }

  function anexarLocal(r, documentos) {
    return gravar(() => ({ novos: registrarDocumentos(r.id, documentos) }),
      documentos.length === 1 ? 'Documento anexado.' : 'Documentos anexados.');
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

  function gravarContaLocal(valores) {
    const linha = D.linhaDaConta(valores);
    return gravar(() => {
      inserir('contas', linha);
    }, 'Conta salva.');
  }

  // Como Banco.salvar_conta com identificador: as operações antigas continuam com a cópia dos dados que guardaram.
  function atualizarContaLocal(id, valores) {
    const linha = D.linhaDaConta(valores);
    const campos = Object.keys(linha);
    return gravar(() => {
      bancoLocal.run(`UPDATE contas SET ${campos.map((k) => k + '=?').join(',')} WHERE id=?`, [...campos.map((k) => linha[k]), id]);
    }, 'Conta atualizada.');
  }

  // Banco.ativar_conta.
  function ativarContaLocal(id, ativa) {
    return gravar(() => {
      bancoLocal.run('UPDATE contas SET ativa=? WHERE id=?', [ativa ? 1 : 0, id]);
    }, ativa ? 'Conta reativada.' : 'Conta desativada.');
  }

  // Banco.remover_contas: as operações perdem o vínculo, mas guardam os dados bancários que copiaram.
  function removerContaLocal(id) {
    return gravar(() => {
      bancoLocal.run('UPDATE rpvs SET conta_id=NULL WHERE conta_id=?', [id]);
      bancoLocal.run('DELETE FROM contas WHERE id=?', [id]);
    }, 'Conta removida.');
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
    return gravar(() => {
      bancoLocal.run('UPDATE rpvs SET recebimento=? WHERE id=? AND lixeira_em IS NULL', [data, registro.id]);
    }, 'Recebimento registrado.');
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

  // Formulário de entrada: nova (r = null) ou edição de uma operação que já existe.
  function telaEntrada(r) {
    if (info.demonstracao) {
      return [avisoSoNaDemonstracao()];
    }
    const contas = dados.contas.filter((c) => c.ativa || (r && c.id === r.conta_id));
    if (r && !dados.contas.some((c) => c.id === r.conta_id)) {
      // Conta removida: a operação guarda o nome e os dados dela, que continuam se não for trocada.
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
          texto: conta.identificacao + (conta.ativa === 0 ? ' (desativada)' : '') }))),
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
      // Todos os problemas de uma vez: primeiro os valores mal escritos, depois as regras.
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
          await editarLocal(r, entrada, conta);
          location.replace(`#operacao/${r.id}`);
        } else {
          location.replace(`#operacao/${await gravarEntradaLocal(entrada, conta, documentos)}`);
        }
      } catch (erro) {
        mostrarErros(['Não foi possível guardar neste aparelho: ' + (erro && erro.message ? erro.message : erro)]);
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
    return [colar, formulario];
  }

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

  // Conta de recebimento nova (ou editada, só no celular): mesmas regras do computador, inclusive não repetir
  // apelido, conta ou Pix.
  function telaNovaConta(id) {
    const existente = Number.isInteger(id) ? dados.contas.find((x) => x.id === id) : null;
    if (Number.isInteger(id) && !existente) {
      return [vazio('Conta não encontrada.')];
    }
    if (info.demonstracao) {
      return [avisoSoNaDemonstracao()];
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
      const problemas = D.problemasDaConta(valores, outras);
      if (problemas.length) {
        erros.replaceChildren(...problemas.map((p) => el('div', { texto: p })));
        erros.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return;
      }
      salvar.disabled = true;
      try {
        await (existente ? atualizarContaLocal(existente.id, valores) : gravarContaLocal(valores));
        location.replace('#contas');
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
    return [formulario];
  }

  // Registrar o recebimento (com a data de hoje já preenchida).
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
        ['Valor de aquisição', reais(r.custo)],
        ['Comissão', reais(r.comissao || 0)],
        ['Valor total RPV', reais(r.previsto)],
        ['Lucro previsto', reais(r.previsto - r.custo)],
        ['Previsão inicial', D.dataBr(r.previsao)],
        ['Previsão atual', D.dataBr(r.previsao_atual)],
        ['Recebido em', r.recebimento ? D.dataBr(r.recebimento) : 'Não recebido'],
      ])),
      !r.lixeira_em && el('a', { class: 'botao-link secundario', href: `#resumo/${r.id}`, texto: 'Compartilhar resumo em imagem' }),
      !info.demonstracao && !r.recebimento && !r.lixeira_em && formularioRecebimento(r),
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

  // Foto (câmera ou álbum) ou PDF anexado à operação.
  function anexarDocumento(r) {
    if (info.demonstracao || r.lixeira_em) {
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
          await anexarLocal(r, documentos);
          desenhar();
        } catch (erro) {
          situacao.className = 'erro';
          situacao.textContent = erro && erro.message ? erro.message : String(erro);
        } finally {
          entrada.value = '';
        }
      } });
    return [el('label', { class: 'botao-link secundario anexar' }, '+ Anexar foto ou PDF', entrada), situacao];
  }

  // Alterar a previsão, editar e excluir.
  function acoesDaOperacao(r) {
    if (info.demonstracao) {
      return null;
    }
    if (r.lixeira_em) {
      return [
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
      if (!confirm('Excluir esta operação? Ela vai para a lixeira (em Mais), de onde pode ser restaurada.')) {
        return;
      }
      excluir.disabled = true;
      await lixeiraLocal(r, true);
      location.replace('#operacoes');
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
          await previsaoLocal(r, data.value);
          desenhar();
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
    if (!dados.contas.length) {
      return [nova, vazio('Nenhuma conta cadastrada.')];
    }
    return [nova, el('div', { class: 'lista' }, dados.contas.map((c) => {
      const usos = dados.operacoes.filter((r) => r.conta_id === c.id).length;
      return el('div', {},
        el('div', { class: 'linha1 rotulo-conta' }, el('span', { class: 'discreto pequeno', texto: usos === 1
          ? '1 operação usa esta conta' : `${usos} operações usam esta conta` }),
        el('span', { class: 'selo ' + (c.ativa ? 'recebida' : 'pendente'), texto: c.ativa ? 'Ativa' : 'Desativada' })),
        contaRecolhida(c.identificacao, c),
        !info.demonstracao && acoesDaConta(c, usos + dados.lixeira.filter((r) => r.conta_id === c.id).length));
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
    return [el('p', { class: 'discreto pequeno', texto: 'Operações excluídas. Toque numa delas para ver, restaurar ou excluir de vez.' }),
      el('div', { class: 'lista' }, dados.lixeira.map((r) => itemOperacao(r, `#operacao/${r.id}`)))];
  }

  // Gráfico mensal em 3D: por mês, uma barra de entradas (terracota) e uma de recebidas (verde), em perspectiva
  // oblíqua — frente com degradê, lateral mais escura e topo mais claro — sobre um piso, com a grade na parede do
  // fundo. Tocar num mês o destaca e mostra os números dele embaixo. As barras sobem uma vez, ao abrir a tela.
  function grafico(resumo, aoEscolher, escolhido, animar = false) {
    const SVG = 'http://www.w3.org/2000/svg';
    const largura = 360;
    const altura = 252;
    const esquerda = 28;
    const base = 206;
    const topo = 26;
    const fundoX = 7;    // Profundidade: para a direita…
    const fundoY = -6;   // …e para cima.
    const topoEixo = D.escala(Math.max(1, ...resumo.flatMap(([, e, r]) => [e, r])));
    const grupo = (largura - esquerda - fundoX - 4) / resumo.length;
    const barra = Math.min(12, grupo * 0.34);
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
    svg.setAttribute('class', 'grafico grafico-3d' + (animar ? ' subindo' : ''));
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Entradas e recebimentos dos últimos 12 meses');
    // Degradês das frentes (as cores vêm do CSS, para os dois temas).
    const defs = novo('defs', {});
    ['entradas', 'recebidas'].forEach((serie) => {
      const degrade = novo('linearGradient', { id: `frente-${serie}`, x1: '0', y1: '0', x2: '0', y2: '1' });
      degrade.append(novo('stop', { offset: '0', class: `parada-${serie}-alto` }), novo('stop', { offset: '1', class: `parada-${serie}-baixo` }));
      defs.append(degrade);
    });
    svg.append(defs);
    // Parede do fundo com a grade, e o piso.
    for (let passo = 0; passo <= 4; passo += 1) {
      const valor = topoEixo * passo / 4;
      if (passo) {
        svg.append(novo('line', { x1: esquerda + fundoX, x2: largura - 2, y1: y(valor) + fundoY, y2: y(valor) + fundoY, class: 'grade' }));
      }
      svg.append(novo('text', { x: esquerda - 6, y: y(valor) + 3, 'text-anchor': 'end', class: 'escala' }, String(valor)));
    }
    svg.append(novo('polygon', { class: 'piso', points: `${esquerda},${base} ${largura - fundoX - 2},${base} ${largura - 2},${base + fundoY} ${esquerda + fundoX},${base + fundoY}` }));
    svg.append(novo('rect', { class: 'piso-borda', x: esquerda, y: base, width: largura - fundoX - 2 - esquerda, height: 5, rx: 1 }));
    const caixa = (x, valor, serie, atraso) => {
      const alto = y(valor);
      const g = novo('g', { class: `barra3d ${serie}` });
      g.style.animationDelay = `${atraso}ms`;  // Pelo CSSOM: a política de segurança da página não aceita atributo style.
      g.append(novo('rect', { x, y: alto, width: barra, height: base - alto, class: 'frente', fill: `url(#frente-${serie})` }));
      g.append(novo('polygon', { class: 'lado', points: `${x + barra},${alto} ${x + barra + fundoX},${alto + fundoY} ${x + barra + fundoX},${base + fundoY} ${x + barra},${base}` }));
      g.append(novo('polygon', { class: 'topo', points: `${x},${alto} ${x + fundoX},${alto + fundoY} ${x + barra + fundoX},${alto + fundoY} ${x + barra},${alto}` }));
      g.append(novo('text', { x: x + barra / 2 + fundoX / 2, y: alto + fundoY - 3, 'text-anchor': 'middle', class: 'valor-barra' }, String(valor)));
      return g;
    };
    resumo.forEach(([chave, entradas, recebidas], i) => {
      const inicio = esquerda + grupo * i;
      const centro = inicio + grupo / 2;
      const alvo = novo('g', { class: 'mes' + (chave === escolhido ? ' escolhido' : '') });
      alvo.append(novo('rect', { x: inicio + 1, y: topo - 14, width: grupo - 2, height: base - topo + 40, rx: 7, class: 'fundo-mes' }));
      if (entradas) {
        alvo.append(caixa(centro - barra - 2, entradas, 'entradas', i * 35));
      }
      if (recebidas) {
        alvo.append(caixa(centro + 1, recebidas, 'recebidas', i * 35 + 60));
      }
      const [mes, ano] = D.rotuloMes(chave).split('/');
      alvo.append(novo('text', { x: centro, y: base + 18, 'text-anchor': 'middle' }, mes));
      if (i === 0 || mes === 'jan') {
        alvo.append(novo('text', { x: centro, y: base + 30, 'text-anchor': 'middle', class: 'ano' }, ano));
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
    const area = el('div', { class: 'cartao area-grafico' });
    const detalhe = el('div', { class: 'cartao' });
    let primeira = true;
    const escolher = (chave) => {
      const [, e, r] = resumo.find(([c]) => c === chave);
      const valores = D.valoresDoMes(dados.operacoes, chave);
      area.replaceChildren(grafico(resumo, escolher, chave, primeira));
      primeira = false;
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

  // Senha num cartão (para confirmar quem é antes de compartilhar ou de tirar um acesso); `acao(senha, andamento)`
  // mostra o andamento no próprio cartão e, se falhar, a mensagem fica ali.
  function formularioSenha(rotulo, acao, { botao: classe = 'primario' } = {}) {
    const campo = el('input', { type: 'password', name: 'senha_confirmar', autocomplete: 'current-password', autocapitalize: 'off',
      spellcheck: 'false' });
    const situacao = el('p', { class: 'discreto pequeno', role: 'status' });
    const botao = el('button', { type: 'submit', class: classe, texto: rotulo });
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
    } }, campoFormulario('Sua senha', campo), situacao, botao);
  }

  // A senha é a desta pessoa? Confere pelo envelope guardado (ou, nos dados antigos, pela chave do arquivo).
  async function confirmarSenha(senha) {
    const pessoa = await Nuvem.credenciais(senha);
    const envelope = await Guarda.ler('envelope').catch(() => null);
    if (envelope) {
      await Nuvem.abrirEnvelope(pessoa.envelope, envelope).catch(() => {
        throw new Error('Senha incorreta.');
      });
    } else if (!await LeitorBackup.senhaConfere(senha, info.chave)) {
      throw new Error('Senha incorreta.');
    }
    return pessoa;
  }

  function textosCartao(titulo, detalhe) {
    return el('div', { class: 'textos' }, el('div', { class: 'nome', texto: titulo }),
      el('div', { class: 'discreto pequeno', texto: detalhe }));
  }

  // Backup na nuvem: sempre ligado; aqui só a situação, em texto pequeno, e o que fazer no raro conflito.
  function cartaoNuvem() {
    if (!nuvem || !nuvem.backup) {
      // Dados antigos abertos pelo Face ID: a senha liga a nuvem (uma vez só).
      return el('div', { class: 'cartao nuvem' },
        textosCartao('Backup na nuvem', 'Confirme a sua senha uma vez para os dados irem para a nuvem a cada gravação.'),
        formularioSenha('Ligar', async (senha, andamento) => {
          await confirmarSenha(senha);
          andamento('Preparando a nuvem…');
          await adotarEnvelope(senha, info.chave);
          agendarEnvioNuvem(0);
          avisar('Backup na nuvem ligado.');
          redesenharSemPular();
        }));
    }
    const estado = estadoNuvem();
    if (estado.conflito_dados) {
      return el('div', { class: 'cartao nuvem' },
        textosCartao('Backup na nuvem', 'Este celular e outro aparelho mudaram os dados ao mesmo tempo, com este celular sem '
          + 'internet. Escolha quais ficam.'),
        el('div', { class: 'botoes' },
          el('button', { type: 'button', class: 'secundario', texto: 'Manter os deste celular', onclick: () => resolverConflito(true) }),
          el('button', { type: 'button', class: 'secundario', texto: 'Usar os da nuvem', onclick: () => resolverConflito(false) })));
    }
    const situacao = estado.conflito ? `Há na nuvem dados de outro aparelho com esta senha${estado.outro_em ? ` (de ${D.dataHora(estado.outro_em)})` : ''}.`
      : textoSincronia();
    return el('div', { class: 'cartao nuvem' },
      textosCartao('Backup na nuvem', `${situacao} A cada gravação, uma cópia trancada com a senha vai para a nuvem.`),
      el('div', { class: 'botoes' }, estado.conflito
        ? el('button', { type: 'button', class: 'secundario perigo', texto: 'Substituir pelos deste celular',
          onclick: () => enviarNuvem({ substituir: true }).catch(() => {}) })
        : el('button', { type: 'button', class: 'secundario', texto: 'Sincronizar agora', onclick: async (evento) => {
          evento.target.disabled = true;
          await (estado.criado_em !== info.manifesto.criado_em ? enviarNuvem() : sincronizarAgora()).catch(() => {});
          redesenharSemPular();
        } })));
  }

  // Lembretes: às 8h, um aviso no dia anterior a cada previsão e outro quando uma passa da data; no mesmo toque,
  // o calendário das previsões no app Calendário do iPhone.
  function cartaoLembretes() {
    const titulo = 'Lembretes e calendário';
    if (!lembretesPossiveis()) {
      return el('div', { class: 'cartao nuvem' }, textosCartao(titulo, 'Para receber lembretes, abra o app pelo ícone da '
        + 'Tela de Início (iPhone com iOS 16.4 ou mais novo).'));
    }
    if (nuvem && nuvem.lembretes && Notification.permission === 'granted') {
      return el('div', { class: 'cartao nuvem' },
        textosCartao(titulo, 'Ligado · às 8h, aviso no dia anterior a cada previsão e quando uma passa da data. As datas '
          + 'também aparecem no Calendário do iPhone.'),
        el('div', { class: 'botoes' },
          el('button', { type: 'button', class: 'secundario', texto: 'Assinar o calendário', onclick: assinarCalendario }),
          el('button', { type: 'button', class: 'secundario', texto: 'Desligar', onclick: async (evento) => {
            evento.target.disabled = true;
            await desligarLembretes();
            avisar('Lembretes desligados.');
            redesenharSemPular();
          } })));
    }
    const situacao = el('p', { class: 'discreto pequeno', role: 'status' });
    return el('div', { class: 'cartao nuvem' },
      textosCartao(titulo, 'Desligado. Os avisos dizem só quantas previsões caem no dia; nomes e valores não saem do celular.'),
      situacao,
      el('div', { class: 'botoes' }, el('button', { type: 'button', class: 'primario', texto: 'Ligar lembretes e calendário',
        disabled: !nuvem || !nuvem.backup, onclick: async (evento) => {
          evento.target.disabled = true;
          try {
            await ligarLembretes();
            avisar('Lembretes ligados.');
            redesenharSemPular();
          } catch (erro) {
            situacao.className = 'erro';
            situacao.textContent = erro && erro.message ? erro.message : String(erro);
            evento.target.disabled = false;
          }
        } })));
  }

  // ---- Compartilhar os dados com outra pessoa ----
  // A chave dos dados é trocada (uma chave nova, sorteada) quando os dados antigos ainda usavam a senha como
  // chave, ou para tirar o acesso de alguém: os dados vão para um cofre novo, e o antigo é apagado da nuvem.
  async function trocarChaveDaCasa(senha, { remover = [] } = {}, andamento = () => {}) {
    const pessoa = await confirmarSenha(senha);
    const anterior = cofreAtual();
    // Uma troca anterior pode ter parado no meio (internet caiu, app fechado): o cadastro da pessoa na nuvem já
    // aponta para um cofre que este celular não chegou a guardar. O envelope dela, aberto com a senha, prova esse
    // cofre, e a troca continua dele; o cofre que sobrou é apagado no fim.
    andamento('Conferindo a nuvem…');
    const registrado = await Nuvem.lerMembro(pessoa);
    const sobra = registrado && anterior && registrado.cofre !== anterior.id
      ? (await Nuvem.abrirEnvelope(pessoa.envelope, registrado.envelope)).cofre : null;
    const novaChave = { sal: crypto.getRandomValues(new Uint8Array(16)), bruta: crypto.getRandomValues(new Uint8Array(32)) };
    const novoCofre = Nuvem.cofreNovo();
    await emOrdem(async () => {
      andamento('Trancando os dados com uma chave nova…');
      const pacote = await LeitorBackup.empacotar(bancoLocal.export(), novaChave, VERSAO_APP, await info.todos());
      andamento('Enviando para a nuvem…');
      const meta = await Nuvem.enviar(novoCofre, pacote.bytes, { sal: novaChave.sal, criadoEm: pacote.manifesto.criado_em });
      const envelope = await Nuvem.fecharEnvelope(pessoa.envelope, { ...novaChave, cofre: novoCofre });
      await Nuvem.guardarMembro(pessoa, novoCofre, { envelope, nome: nomeDono(), anterior: sobra || anterior });
      for (const id of remover) {
        await Nuvem.apagarMembro(id, anterior).catch(() => {});
      }
      await Nuvem.apagar(anterior).catch(() => {});
      if (sobra && !(await Nuvem.listarMembros(sobra).catch(() => [{}])).length) {
        await Nuvem.apagar(sobra).catch(() => {});  // Só se ninguém mais usa aquele cofre.
      }
      await Guarda.gravar('envelope', envelope);
      await guardarNuvem({ ...nuvem, id: novoCofre.id, chave: novoCofre.chave, backup: true,
        membro: { id: pessoa.id, chave: pessoa.chave }, membroPendente: null });
      info.chave = novaChave;
      Object.assign(info, { manifesto: pacote.manifesto, extrair: pacote.extrair, todos: pacote.todos });
      fonte = { ...fonte, bytes: pacote.bytes, tamanho: pacote.bytes.length, criado_em: pacote.manifesto.criado_em };
      await Guarda.gravar('backup', { bytes: pacote.bytes, nome: fonte.nome, tamanho: pacote.bytes.length,
        criado_em: pacote.manifesto.criado_em, guardado_em: new Date().toISOString(), independente: true });
      gravarEstadoNuvem({ versao: meta.versao, criado_em: pacote.manifesto.criado_em, sincronizado_em: LeitorBackup.dataHoraLocal() });
      filaNuvem = [];
    });
    // O Face ID guardava a chave antiga: é oferecido de novo, já com a nova.
    if (faceIdAtivo) {
      await FaceId.desativar().catch(() => {});
      faceIdAtivo = false;
    }
    senhaRecente = { chave: info.chave, oferecer: await FaceId.possivel().catch(() => false) };
    localStorageGravar('lembretes_enviados', '');
    sincronizarLembretes({ forcar: true });
  }

  async function gerarConvite() {
    const codigo = Nuvem.codigoNovo();
    const convite = await Nuvem.chavesDoConvite(codigo);
    const envelope = await Nuvem.fecharEnvelope(convite.chave, { ...info.chave, cofre: cofreAtual() });
    await Nuvem.guardarConvite(cofreAtual(), convite, envelope);
    return codigo;
  }

  function telaCompartilhar() {
    if (info.demonstracao) {
      return [avisoSoNaDemonstracao()];
    }
    const antigos = !nuvem || !nuvem.membro || nuvem.id === nuvem.membro.id;
    const pessoas = el('div', { class: 'menu' }, el('p', { class: 'discreto pequeno', texto: 'Carregando…' }));
    const area = el('div', { class: 'formulario' });
    const mostrarPessoas = async () => {
      try {
        const lista = await Nuvem.listarMembros(cofreAtual());
        const outras = lista.filter((m) => m.id !== nuvem.membro.id);
        pessoas.replaceChildren(...lista.map((m) => {
          const eu = m.id === nuvem.membro.id;
          const remover = !eu && el('details', { class: 'remover-acesso' },
            el('summary', { texto: 'Remover acesso' }),
            el('p', { class: 'discreto pequeno', texto: outras.length > 1
              ? 'Os dados ganham uma chave nova; as outras pessoas também vão precisar de um convite novo.'
              : 'Os dados ganham uma chave nova, que o celular dela não abre mais.' }),
            formularioSenha(`Remover ${m.nome || 'esta pessoa'}`, async (senha, andamento) => {
              await trocarChaveDaCasa(senha, { remover: [m.id] }, andamento);
              avisar('Acesso removido.');
              redesenharSemPular();
              desenhar();
            }, { botao: 'secundario perigo' }));
          return el('div', { class: 'cartao pessoa' }, el('div', { class: 'nome', texto: m.nome || 'Sem nome' }),
            el('div', { class: 'discreto pequeno', texto: eu ? 'Este celular' : `Desde ${D.dataBr(m.desde.slice(0, 10))}` }), remover);
        }));
        if (!lista.length) {
          pessoas.replaceChildren(el('p', { class: 'discreto pequeno', texto: 'Só você, por enquanto.' }));
        }
      } catch (erro) {
        pessoas.replaceChildren(el('p', { class: 'discreto pequeno', texto: 'Sem conexão para ver quem tem acesso agora.' }));
      }
    };
    const mostrarCodigo = (codigo) => {
      const texto = `Use o Gestor RPV comigo: abra ${ENDERECO_APP} no Safari, toque em Compartilhar → Adicionar à Tela de `
        + `Início e abra pelo ícone. Depois toque em "Começar a usar com meus dados" → "Recebi um código de convite" e `
        + `digite: ${codigo} (vale por 15 minutos).`;
      area.replaceChildren(
        el('div', { class: 'codigo-convite', texto: codigo }),
        el('p', { class: 'discreto pequeno', texto: 'Vale por 15 minutos e para uma pessoa. Ela escolhe o nome e a senha dela.' }),
        navigator.share
          ? el('button', { type: 'button', class: 'primario', texto: 'Enviar convite',
            onclick: () => navigator.share({ title: 'Gestor RPV', text: texto }).catch(() => {}) })
          : el('button', { type: 'button', class: 'primario', texto: 'Copiar convite',
            onclick: () => navigator.clipboard.writeText(texto).then(() => avisar('Convite copiado.')).catch(() => {}) }),
        el('button', { type: 'button', class: 'secundario', texto: 'Gerar outro código', onclick: gerar }));
    };
    const situacao = el('p', { class: 'discreto pequeno', role: 'status' });
    async function gerar(evento) {
      if (evento) {
        evento.target.disabled = true;
      }
      situacao.className = 'discreto pequeno';
      situacao.textContent = 'Gerando o código…';
      try {
        if (estadoNuvem().criado_em !== info.manifesto.criado_em) {
          await enviarNuvem();
        }
        mostrarCodigo(await gerarConvite());
        situacao.textContent = '';
      } catch (erro) {
        situacao.className = 'erro';
        situacao.textContent = 'Não foi possível gerar o código agora: ' + (erro && erro.message ? erro.message : erro);
        if (evento) {
          evento.target.disabled = false;
        }
      }
    }
    if (antigos) {
      area.append(el('p', { class: 'discreto pequeno', texto: 'Antes do primeiro convite, confirme a sua senha (a mesma com que '
        + 'você abre o app): os dados ganham uma chave só deles, e a sua senha continua só sua. A senha dela, ela cria no '
        + 'celular dela, ao entrar com o código.' }),
      formularioSenha('Continuar', async (senha, andamento) => {
        await trocarChaveDaCasa(senha, {}, andamento);
        desenhar();
      }));
    } else {
      area.append(el('button', { type: 'button', class: 'primario', texto: 'Gerar código de convite', onclick: gerar }));
      mostrarPessoas();
    }
    return [
      el('p', { class: 'discreto pequeno', texto: 'Quem você convidar vê e altera os mesmos dados, com o nome e a senha dela. '
        + 'O que um muda aparece no celular do outro.' }),
      !antigos && [el('h2', { texto: 'Pessoas com acesso' }), pessoas],
      el('h2', { texto: 'Convite' }), cartao(area, situacao),
    ];
  }

  function telaMais() {
    const opcao = (href, titulo, detalhe, simbolo, tom) => el('a', { class: 'cartao opcao-menu', href },
      conteudoOpcao(simbolo, tom, titulo, detalhe));
    const grupo = (titulo, ...itens) => [el('h3', { class: 'grupo-menu', texto: titulo }), el('div', { class: 'menu' }, itens)];
    return [
      grupo('Ferramentas',
        opcao('#agenda', 'Agenda das previsões', 'Calendário com as datas previstas de recebimento', 'calendario'),
        opcao('#grafico', 'Gráfico mensal', 'Entradas e recebimentos dos últimos 12 meses', 'barras', 'ambar'),
        opcao('#lixeira', `Lixeira (${dados.lixeira.length})`, 'Operações excluídas: restaurar ou excluir de vez', 'lixeira')),
      grupo('Aplicativo e compartilhamento',
        !info.demonstracao && opcao('#compartilhar', 'Compartilhar com outra pessoa', 'Ela entra com o nome e a senha dela e vê os mesmos dados', 'convidar', 'verde'),
        opcao('#novidades', 'Novidades', 'O que mudou nas últimas versões', 'megafone'),
        opcao('#convite', 'Indicar o app', 'Mandar o app para outra pessoa usar com os dados dela', 'convidar', 'azul')),
      grupo('Ajustes e segurança',
        opcao('#ajustes', 'Ajustes', info.demonstracao ? 'Tema e nome' : 'Tema, nome, backup na nuvem, lembretes e calendário',
          'ajustes', 'ambar'),
        senhaRecente && !faceIdAtivo && el('div', { class: 'cartao' },
          el('div', { texto: 'Ativar o Face ID' }), el('div', { class: 'discreto pequeno', texto: 'Abrir o app com o rosto, sem digitar a senha' }),
          el('div', { class: 'botoes' }, el('button', { type: 'button', class: 'primario', texto: 'Ativar',
            onclick: (e) => ativarFaceId(e.target.closest('.cartao')) }))),
        faceIdAtivo && el('a', { class: 'cartao opcao-menu', href: '#', onclick: async (e) => {
          e.preventDefault();
          if (confirm('Desativar o Face ID do app? A próxima abertura pedirá a senha.')) {
            await FaceId.desativar().catch(() => {});
            faceIdAtivo = false;
            localStorageGravar('faceid_recusado', '1');
            desenhar();
          }
        } }, conteudoOpcao('cadeado', 'ambar', 'Desativar o Face ID', 'Voltar a abrir só com a senha')),
        !info.demonstracao && el('p', { class: 'discreto pequeno', texto: 'O app tranca sozinho depois de 5 minutos em segundo plano.' })),
      el('div', { class: 'menu-acoes' },
        info.demonstracao && el('button', { type: 'button', class: 'primario', texto: 'Começar a usar com meus dados', onclick: sairDaDemonstracao }),
        !info.demonstracao && el('button', { type: 'button', class: 'secundario', texto: 'Apagar os dados deste celular', onclick: esquecerBackup })),
      el('a', { class: 'sobre-dados', href: '#backup', texto: `Sobre os dados · versão ${VERSAO_APP}` }),
    ];
  }

  // Ajustes: tema, nome e, com dados de verdade, o backup na nuvem e os lembretes com o calendário.
  function telaAjustes() {
    const grupo = (titulo, ...itens) => [el('h3', { class: 'grupo-menu', texto: titulo }), el('div', { class: 'menu' }, itens)];
    return [
      grupo('Aparência', escolherTema(), escolherNome()),
      !info.demonstracao && grupo('Nuvem e lembretes', cartaoNuvem(), cartaoLembretes()),
    ];
  }

  // Nome do dono deste celular, mostrado no "Olá" do Início (fica só aqui).
  function escolherNome() {
    const campo = el('input', { name: 'nome_dono', value: nomeDono(), autocomplete: 'given-name', autocapitalize: 'words', maxlength: '40' });
    return el('form', { class: 'cartao tema', onsubmit: (evento) => {
      evento.preventDefault();
      localStorageGravar('nome', campo.value.trim());
      avisar(campo.value.trim() ? `Pronto, ${campo.value.trim()}!` : 'Nome apagado.');
    } }, el('div', { class: 'textos' }, el('div', { texto: 'Nome' }),
      el('div', { class: 'discreto pequeno', texto: 'Aparece no "Olá" do Início' })),
    el('div', { class: 'linha-nome' }, campo, el('button', { type: 'submit', class: 'secundario', texto: 'Salvar' })));
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
    + 'Adicionar à Tela de Início e abra pelo ícone. Depois toque em "Começar a usar com meus dados" e crie a sua senha.';

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
      el('p', { texto: 'Mande o app para outra pessoa: ela cria a própria senha e começa com os dados vazios. Nada do seu celular vai junto. Para ela ver os seus dados, use "Compartilhar com outra pessoa", em Mais.' }),
      compartilhar, resultado,
      el('h2', { texto: 'Ou mostre o QR code' }),
      el('div', { class: 'cartao qr' }, el('img', { src: 'icones/qr-app.svg', alt: 'QR code com o endereço do app' }),
        el('div', { class: 'discreto pequeno', texto: ENDERECO_APP })),
      el('h2', { texto: 'O que a pessoa faz' }),
      el('ol', { class: 'passos' },
        el('li', { texto: 'Abre o link (ou aponta a câmera para o QR code) no Safari do iPhone.' }),
        el('li', { texto: 'Toca em Compartilhar → Adicionar à Tela de Início.' }),
        el('li', { texto: 'Abre o app pelo ícone novo (não pelo Safari).' }),
        el('li', { texto: 'Toca em "Começar a usar com meus dados", digita o nome e cria a senha.' })),
    ];
  }

  function telaBackup() {
    const t = info.tempos;
    return [cartao(campos([
      ['Dados', 'Guardados neste celular e na nuvem, trancados com a senha'],
      ['Última gravação', D.dataHora(info.manifesto.criado_em)],
      ['Versão deste app', VERSAO_APP],
      ['Tempo para abrir', `${((Object.values(t).reduce((a, b) => a + b, 0)) / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} s`],
    ]))];
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
    backup: { titulo: 'Sobre os dados', aba: 'mais', montar: telaBackup, voltar: true },
    ajustes: { titulo: 'Ajustes', aba: 'mais', montar: telaAjustes, voltar: true },
    novidades: { titulo: 'Novidades', aba: 'mais', montar: telaNovidades, voltar: true },
    nova: { titulo: 'Nova entrada', aba: 'operacoes', montar: telaNovaEntrada, voltar: true },
    editar: { titulo: 'Editar entrada', aba: 'operacoes', montar: telaEditar, voltar: true },
    agenda: { titulo: 'Agenda', aba: 'inicio', montar: telaAgenda, voltar: true },
    resumo: { titulo: 'Resumo em imagem', aba: 'operacoes', montar: telaResumo, voltar: true },
    convite: { titulo: 'Indicar o app', aba: 'mais', montar: telaConvite, voltar: true },
    compartilhar: { titulo: 'Compartilhar', aba: 'mais', montar: telaCompartilhar, voltar: true },
    'nova-conta': { titulo: 'Nova conta', aba: 'contas', montar: telaNovaConta, voltar: true },
    'editar-conta': { titulo: 'Editar conta', aba: 'contas', montar: telaNovaConta, voltar: true },
  };

  function avisoSoNaDemonstracao() {
    return el('p', { class: 'aviso', texto: 'Na demonstração não dá para cadastrar. Toque em "Começar a usar com meus dados", no alto da tela.' });
  }

  // No Início, um cartão em destaque; nas outras telas, a mesma chamada, menor.
  function avisoDemonstracao(destaque) {
    return el('div', { class: 'aviso demonstracao' + (destaque ? ' destaque' : '') },
      el('div', { class: 'nome', texto: destaque ? 'Estes dados são de exemplo' : 'Demonstração' }),
      el('div', { class: 'pequeno', texto: 'Estes dados são fictícios e meramente sugestivos: servem só para mostrar como o app fica. Nada aqui é real.' }),
      el('div', { class: 'botoes' }, el('button', { type: 'button', class: 'primario', texto: 'Começar a usar com meus dados',
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
    // Vindo do aviso de atraso: uma operação atrasada abre direto no recebimento; várias, a lista filtrada.
    if (location.hash === '#atrasadas') {
      const atrasadas = dados.operacoes.filter((r) => D.situacao(r) === 'atrasada');
      if (atrasadas.length === 1) {
        receberAoAbrir = atrasadas[0].id;
        location.replace(`#operacao/${atrasadas[0].id}`);
      } else {
        estado.filtro = atrasadas.length ? 'atrasada' : 'todas';
        location.replace(atrasadas.length ? '#operacoes' : '#inicio');
      }
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
    $('tela').replaceChildren(...[info.demonstracao && avisoDemonstracao(tela === TELAS.inicio), tela.montar(id)].flat(2).filter(Boolean));
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
    if (tela === TELAS.operacao && receberAoAbrir === id) {
      receberAoAbrir = null;
      const recebimento = document.querySelector('form.recebimento');
      if (recebimento) {
        recebimento.scrollIntoView({ block: 'center' });
        recebimento.classList.add('chamando');
      }
    }
  }

  let receberAoAbrir = null;  // Operação aberta pelo aviso de atraso: o recebimento já aparece à frente.

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
          mostrarBotaoTema();
          const rolagem = window.scrollY;
          desenhar();
          window.scrollTo(0, rolagem);
        } }))));
  }

  aplicarTema(localStorageLer('tema'));

  // O sol e a lua no topo do Início: um toque troca entre o claro e o escuro (deixa de seguir o iPhone).
  const temaDoIphone = window.matchMedia('(prefers-color-scheme: dark)');
  const temaEscuro = () => (document.documentElement.dataset.tema || (temaDoIphone.matches ? 'escuro' : 'claro')) === 'escuro';

  function mostrarBotaoTema() {
    const escuro = temaEscuro();
    $('tema').classList.toggle('escuro', escuro);
    $('tema').setAttribute('aria-label', escuro ? 'Mudar para o tema claro' : 'Mudar para o tema escuro');
  }

  mostrarBotaoTema();
  temaDoIphone.addEventListener('change', mostrarBotaoTema);
  $('tema').addEventListener('click', () => {
    const tema = temaEscuro() ? 'claro' : 'escuro';
    localStorageGravar('tema', tema);
    aplicarTema(tema);
    mostrarBotaoTema();
    const rolagem = window.scrollY;
    desenhar();
    window.scrollTo(0, rolagem);
  });

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
  const ANIMACAO_LOGO_MS = 2700;  // A entrada do logo e mais um instante parado, para ele ser visto.
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
