// A nuvem pelo app, com o Worker de verdade (nuvem/worker.js) rodando aqui e o KV na memória; os pedidos ao endereço
// da nuvem são desviados para ele. Dois "celulares" (contextos do navegador) dividem os dados: criar com nome e
// senha, convidar, entrar pelo código, sincronizar, gravar ao mesmo tempo sem perder nada, recuperar num celular
// novo, tirar o acesso e os dados antigos (de antes do envelope). Imprime, em JSON, o que aconteceu.
'use strict';
const path = require('path');
const { pathToFileURL } = require('url');
const playwright = require('playwright');

const NAVEGADOR = process.env.GESTOR_RPV_NAVEGADOR || 'chromium';

(async () => {
  const [endereco, entradaJson] = process.argv.slice(2);
  const { senha, senha_ana: senhaAna, conta, backup_pc: backupPc, senha_pc: senhaPc } = JSON.parse(entradaJson);
  const { servir } = await import(pathToFileURL(path.join(__dirname, '..', '..', 'nuvem', 'local.mjs')).href);
  const { servidor, env, porta } = await servir();
  const kv = env.DADOS.valores;
  const chaves = (prefixo) => [...kv.keys()].filter((k) => k.startsWith(prefixo));
  const json = (chave) => JSON.parse(kv.get(chave));
  const navegador = await playwright[NAVEGADOR].launch();
  const r = { erros: [] };

  async function aparelho(nome) {
    const contexto = await navegador.newContext();
    const estado = { falharConsulta: false, semCadastro: false, perderResposta: false };
    // Os pedidos ao endereço da nuvem vão para o Worker local (a página continua vendo o endereço de sempre).
    await contexto.route(/workers\.dev/, async (rota) => {
      const pedido = rota.request();
      const url = new URL(pedido.url());
      if (estado.falharConsulta && pedido.method() === 'GET' && /^\/v1\/backup\/[0-9a-f]{32}$/.test(url.pathname)) {
        estado.falharConsulta = false;  // Sem internet por um instante: a conferência antes de gravar falha.
        await rota.abort();
        return;
      }
      if (estado.semCadastro && pedido.method() === 'PUT' && url.pathname.startsWith('/v1/membro/')) {
        await rota.abort();  // Como pelo Face ID antigo: os dados não mudaram, e o cadastro da pessoa não chegou à nuvem.
        return;
      }
      const resposta = await fetch(`http://127.0.0.1:${porta}${url.pathname}${url.search}`, {
        method: pedido.method(), headers: pedido.headers(), body: pedido.postDataBuffer() || undefined,
      });
      if (estado.perderResposta && pedido.method() === 'PUT' && url.pathname.startsWith('/v1/membro/')) {
        estado.perderResposta = false;  // A nuvem gravou, mas a resposta não chegou (internet caiu, app fechado).
        await rota.abort();
        return;
      }
      await rota.fulfill({ status: resposta.status, headers: Object.fromEntries(resposta.headers),
        body: Buffer.from(await resposta.arrayBuffer()) });
    });
    const pagina = await contexto.newPage();
    pagina.on('pageerror', (erro) => r.erros.push(`${nome}: ${erro}`));
    pagina.on('dialog', (d) => d.accept());
    const texto = () => pagina.evaluate(() => document.getElementById('tela').innerText);
    const ir = async (hash) => {
      await pagina.evaluate((h) => { location.hash = h; }, hash);
      await pagina.waitForFunction((h) => location.hash === h && document.getElementById('tela').childElementCount > 0, hash);
    };
    // Voltar ao app (como ao desbloquear o celular): ele confere a nuvem por trás.
    const voltarAoApp = () => pagina.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    const novaEntrada = async (nome) => {
      await ir('#nova');
      await pagina.fill('[name="nome"]', nome);
      await pagina.fill('[name="aquisicao"]', '2026-10-01');
      await pagina.fill('[name="custo"]', '500000');
      await pagina.fill('[name="previsto"]', '800000');
      await pagina.selectOption('[name="conta"]', { index: 1 });
      await pagina.fill('[name="previsao"]', '2026-12-01');
      await pagina.click('text=Salvar entrada');
      await pagina.waitForFunction(() => location.hash.startsWith('#operacao/'));
    };
    const operacoes = async () => {
      await ir('#operacoes');
      return texto();
    };
    await pagina.goto(endereco + '/index.html');
    await pagina.waitForSelector('.aviso.demonstracao button', { timeout: 30000 });
    await pagina.click('.aviso.demonstracao button');
    await pagina.waitForSelector('#abertura:not([hidden])');
    return { contexto, pagina, texto, ir, voltarAoApp, novaEntrada, operacoes, estado };
  }

  const esperar = async (condicao, ms = 30000) => {
    const fim = Date.now() + ms;
    while (!condicao()) {
      if (Date.now() > fim) {
        throw new Error('Tempo esgotado esperando a nuvem.');
      }
      await new Promise((ok) => setTimeout(ok, 100));
    }
  };
  const versao = (cofre) => (kv.has(`meta:${cofre}`) ? json(`meta:${cofre}`).versao : null);

  try {
    // 1. Vitor: primeira vez, com nome e senha. Os dados nascem num cofre sorteado; ele é reconhecido pela senha.
    const a = await aparelho('vitor');
    await a.pagina.fill('#nome-novo', 'Vitor');
    await a.pagina.fill('#senha-nova', senha);
    await a.pagina.fill('#senha-repetida', senha);
    await a.pagina.click('#criar');
    await a.pagina.waitForSelector('#aplicativo:not([hidden])', { timeout: 120000 });
    await esperar(() => chaves('membro:').length === 1 && chaves('meta:').length === 1);
    r.membro_vitor = chaves('membro:')[0].slice('membro:'.length);
    r.cofre = chaves('meta:')[0].slice('meta:'.length);
    await a.pagina.waitForSelector('text=Sincronizado às');
    r.inicio_vitor = await a.texto();
    await a.ir('#nova-conta');
    for (const [campo, valor] of Object.entries(conta)) {
      await (campo === 'estado' ? a.pagina.selectOption('[name="estado"]', valor) : a.pagina.fill(`[name="${campo}"]`, valor));
    }
    await a.pagina.click('text=Salvar conta');
    await a.pagina.waitForFunction(() => location.hash === '#contas');
    const antesDaEntrada = versao(r.cofre);
    await a.novaEntrada('entrada do vitor');
    await esperar(() => versao(r.cofre) !== antesDaEntrada);
    await a.ir('#mais');
    r.mais_vitor = await a.texto();
    await a.ir('#ajustes');
    r.ajustes_vitor = await a.texto();

    // 2. O convite: um código de 10 letras e números, para uma pessoa só.
    await a.ir('#compartilhar');
    r.compartilhar_antes = await a.texto();
    await a.pagina.click('text=Gerar código de convite');
    await a.pagina.waitForSelector('.codigo-convite', { timeout: 30000 });
    const codigo = await a.pagina.textContent('.codigo-convite');
    r.codigo = codigo;

    // 3. Ana entra pelo código (errado antes), com o nome e a senha dela, e vê os dados do Vitor.
    const b = await aparelho('ana');
    await b.pagina.click('#recebi-convite');
    await b.pagina.waitForSelector('#form-convite:not([hidden])');
    await b.pagina.fill('#codigo-convite', 'AAAAA-BBBBB');
    await b.pagina.fill('#nome-convite', 'Ana');
    await b.pagina.fill('#senha-convite', senhaAna);
    await b.pagina.fill('#senha-convite-repetida', senhaAna);
    await b.pagina.click('#entrar-convite');
    await b.pagina.waitForSelector('#erro:not([hidden])', { timeout: 60000 });
    r.convite_errado = await b.pagina.textContent('#erro');
    await b.pagina.fill('#codigo-convite', codigo.toLowerCase().replace('-', ' '));
    await b.pagina.click('#entrar-convite');
    await b.pagina.waitForSelector('#aplicativo:not([hidden])', { timeout: 120000 });
    r.inicio_ana = await b.texto();
    r.operacoes_ana = await b.operacoes();
    r.membros = json(`membros:${r.cofre}`).map((m) => m.nome);

    // 4. O mesmo código não serve de novo.
    const c = await aparelho('outro');
    await c.pagina.click('#recebi-convite');
    await c.pagina.fill('#codigo-convite', codigo);
    await c.pagina.fill('#nome-convite', 'Intruso');
    await c.pagina.fill('#senha-convite', 'outra senha 77');
    await c.pagina.fill('#senha-convite-repetida', 'outra senha 77');
    await c.pagina.click('#entrar-convite');
    await c.pagina.waitForSelector('#erro:not([hidden])', { timeout: 60000 });
    r.convite_usado = await c.pagina.textContent('#erro');
    await c.contexto.close();

    // 5. Ana grava; o Vitor, ao voltar ao app, já vê (por trás, sem aviso).
    const antes = versao(r.cofre);
    await b.novaEntrada('entrada da ana');
    await esperar(() => versao(r.cofre) !== antes);
    await a.ir('#operacoes');
    await a.voltarAoApp();
    await a.pagina.waitForFunction(() => document.getElementById('tela').innerText.includes('Entrada Da Ana'), null,
      { timeout: 30000 });
    r.operacoes_vitor = await a.texto();

    // 6. Os dois gravam quase ao mesmo tempo: a Ana primeiro; o Vitor sem conseguir conferir a nuvem antes. A nuvem
    //    recusa o envio dele (desatualizado), o app traz o da Ana, refaz a entrada dele por cima e manda: as duas ficam.
    const antesDela = versao(r.cofre);
    await b.novaEntrada('ana ao mesmo tempo');
    await esperar(() => versao(r.cofre) !== antesDela);
    const antesDele = versao(r.cofre);
    a.estado.falharConsulta = true;
    await a.novaEntrada('vitor ao mesmo tempo');
    await esperar(() => versao(r.cofre) !== antesDele);
    await a.pagina.waitForTimeout(1500);
    r.vitor_depois_de_juntar = await a.operacoes();
    await b.voltarAoApp();
    await b.pagina.waitForTimeout(2000);
    r.ana_depois_de_juntar = await b.operacoes();

    // 7. Celular novo da Ana: só com a senha dela, os dados da casa voltam.
    const d = await aparelho('ana-nova');
    await d.pagina.click('#recuperar-nuvem');
    await d.pagina.waitForSelector('#form-nuvem:not([hidden])');
    await d.pagina.fill('#senha-nuvem', senhaAna);
    await d.pagina.click('#baixar-nuvem');
    await d.pagina.waitForSelector('#aplicativo:not([hidden])', { timeout: 120000 });
    r.recuperado_ana = await d.operacoes();
    await d.ir('#inicio');
    r.ola_recuperado = await d.pagina.evaluate(() => document.querySelector('.saudacao') && document.querySelector('.saudacao').textContent);
    await d.contexto.close();

    // 8. O Vitor tira o acesso da Ana: os dados ganham chave e cofre novos; o antigo some da nuvem.
    await a.ir('#compartilhar');
    await a.pagina.waitForSelector('.cartao.pessoa >> nth=1');
    r.pessoas = await a.texto();
    await a.pagina.click('details.remover-acesso summary');
    await a.pagina.fill('details.remover-acesso [name="senha_confirmar"]', senha);
    await a.pagina.click('details.remover-acesso button');
    await esperar(() => !kv.has(`meta:${r.cofre}`) && chaves('meta:').length === 1, 60000);
    r.cofre_novo = chaves('meta:')[0].slice('meta:'.length);
    r.vitor_no_novo = json(`membro:${r.membro_vitor}`).cofre === r.cofre_novo;
    r.membros_depois = json(`membros:${r.cofre_novo}`).map((m) => m.nome);
    r.membros_cadastrados = chaves('membro:').length;
    await a.pagina.waitForTimeout(1000);
    r.vitor_depois_de_remover = await a.operacoes();
    // A Ana tenta recuperar num celular novo: não acha mais nada.
    const e = await aparelho('ana-removida');
    await e.pagina.click('#recuperar-nuvem');
    await e.pagina.fill('#senha-nuvem', senhaAna);
    await e.pagina.click('#baixar-nuvem');
    await e.pagina.waitForSelector('#erro:not([hidden])', { timeout: 60000 });
    r.ana_removida = await e.pagina.textContent('#erro');
    await e.contexto.close();
    // O Vitor continua gravando no cofre novo.
    const noNovo = versao(r.cofre_novo);
    await a.novaEntrada('depois de remover');
    await esperar(() => versao(r.cofre_novo) !== noNovo);
    await b.contexto.close();

    // 9. Dados antigos (de antes do envelope, a senha era a chave): ganham envelope e vão para a nuvem sozinhos.
    const f = await aparelho('antigos');
    f.estado.semCadastro = true;
    await f.pagina.evaluate(async ({ url, senhaPc }) => {
      await abrirArquivoGestor(new Uint8Array(await (await fetch(url)).arrayBuffer()), senhaPc);
    }, { url: backupPc, senhaPc });
    await f.pagina.waitForSelector('#aplicativo:not([hidden])', { timeout: 120000 });
    const cofresAntes = chaves('meta:').length;
    await esperar(() => chaves('meta:').length === cofresAntes + 1, 60000);
    r.cofre_antigo = chaves('meta:').find((k) => k !== `meta:${r.cofre_novo}`).slice('meta:'.length);
    await f.pagina.waitForTimeout(1500);
    r.antigos_sem_cadastro = !kv.has(`membro:${r.cofre_antigo}`);
    f.estado.semCadastro = false;
    // Antes do primeiro convite, a senha é confirmada e os dados ganham uma chave só deles (cofre novo).
    await f.ir('#compartilhar');
    r.compartilhar_antigos = await f.texto();
    // A primeira troca para no meio: o cadastro já foi para um cofre novo, que este celular não guardou.
    f.estado.perderResposta = true;
    await f.pagina.fill('[name="senha_confirmar"]', senhaPc);
    await f.pagina.click('button:has-text("Continuar")');
    await f.pagina.waitForSelector('#tela form p.erro', { timeout: 60000 });
    r.troca_interrompida = await f.pagina.textContent('#tela form p.erro');
    const cofresInterrompidos = chaves('meta:').length;
    // Na segunda, o app continua de onde parou (sem "senha já usada") e apaga o cofre que sobrou.
    await f.pagina.click('button:has-text("Continuar")');
    await f.pagina.waitForSelector('text=Gerar código de convite', { timeout: 60000 });
    r.cofres_depois_da_retomada = chaves('meta:').length - cofresInterrompidos;
    await esperar(() => !kv.has(`meta:${r.cofre_antigo}`), 30000);
    r.antigos_migrados = { cadastro_continua: kv.has(`membro:${r.cofre_antigo}`),
      cofre_novo: json(`membro:${r.cofre_antigo}`).cofre !== r.cofre_antigo };
    r.operacoes_antigos = await f.operacoes();
    await f.contexto.close();
    await a.contexto.close();
  } finally {
    await navegador.close();
    servidor.close();
  }
  process.stdout.write(JSON.stringify(r));
})().catch((erro) => {
  console.error(erro);
  process.exit(1);
});
