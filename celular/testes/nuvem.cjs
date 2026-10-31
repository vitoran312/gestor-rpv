// Nuvem pelo app: o Worker de verdade (nuvem/worker.js) roda aqui, com o KV na memória, e os pedidos ao endereço
// da nuvem são desviados para ele. Cobre: ligar o backup automático, envio a cada gravação, recuperar num
// celular novo, desligar, e tornar principal um celular que abria o backup do computador. Imprime, em JSON, o
// que aconteceu e o último backup enviado (base64), para o Python abrir no programa.
'use strict';
const path = require('path');
const { pathToFileURL } = require('url');
const playwright = require('playwright');

const NAVEGADOR = process.env.GESTOR_RPV_NAVEGADOR || 'chromium';

(async () => {
  const [endereco, entradaJson] = process.argv.slice(2);
  const { senha, conta, entrada, backup_pc: backupPc, senha_pc: senhaPc } = JSON.parse(entradaJson);
  const { servir } = await import(pathToFileURL(path.join(__dirname, '..', '..', 'nuvem', 'local.mjs')).href);
  const { servidor, env, porta } = await servir();
  const kv = env.DADOS.valores;
  const metas = () => [...kv.keys()].filter((k) => k.startsWith('meta:'));
  const meta = (chave) => JSON.parse(kv.get(chave));
  const navegador = await playwright[NAVEGADOR].launch();
  const r = { erros: [] };

  async function aparelho() {
    const contexto = await navegador.newContext();
    // Os pedidos ao endereço da nuvem vão para o Worker local (a página continua vendo o endereço de sempre).
    await contexto.route(/workers\.dev/, async (rota) => {
      const pedido = rota.request();
      const url = new URL(pedido.url());
      const resposta = await fetch(`http://127.0.0.1:${porta}${url.pathname}${url.search}`, {
        method: pedido.method(), headers: pedido.headers(), body: pedido.postDataBuffer() || undefined,
      });
      await rota.fulfill({ status: resposta.status, headers: Object.fromEntries(resposta.headers),
        body: Buffer.from(await resposta.arrayBuffer()) });
    });
    const pagina = await contexto.newPage();
    pagina.on('pageerror', (erro) => r.erros.push(String(erro)));
    pagina.on('dialog', (d) => d.accept());
    const texto = () => pagina.evaluate(() => document.getElementById('tela').innerText);
    const ir = async (hash) => {
      await pagina.evaluate((h) => { location.hash = h; }, hash);
      await pagina.waitForFunction((h) => location.hash === h && document.getElementById('tela').childElementCount > 0, hash);
    };
    await pagina.goto(endereco + '/index.html');
    await pagina.waitForSelector('text=Começar com meus dados', { timeout: 30000 });
    await pagina.click('text=Começar com meus dados');
    await pagina.waitForSelector('#abertura:not([hidden])');
    return { contexto, pagina, texto, ir };
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

  try {
    // 1. Quem usa só o celular: cria os dados, cadastra conta e entrada e liga o backup na nuvem.
    const a = await aparelho();
    r.abertura_recuperar = await a.pagina.isVisible('#recuperar-nuvem');
    await a.pagina.click('#comecar');
    await a.pagina.fill('#senha-nova', senha);
    await a.pagina.fill('#senha-repetida', senha);
    await a.pagina.click('#criar');
    await a.pagina.waitForSelector('#aplicativo:not([hidden])', { timeout: 120000 });
    await a.ir('#nova-conta');
    for (const [campo, valor] of Object.entries(conta)) {
      await (campo === 'estado' ? a.pagina.selectOption('[name="estado"]', valor) : a.pagina.fill(`[name="${campo}"]`, valor));
    }
    await a.pagina.click('text=Salvar conta');
    await a.pagina.waitForFunction(() => location.hash === '#contas');
    await a.ir('#mais');
    r.mais_desligado = await a.texto();
    await a.pagina.fill('.cartao.nuvem [name="senha_nuvem"]', senha + 'x');
    await a.pagina.click('text=Ligar backup na nuvem');
    await a.pagina.waitForSelector('.cartao.nuvem .erro');
    r.senha_errada = await a.pagina.textContent('.cartao.nuvem .erro');
    await a.pagina.fill('.cartao.nuvem [name="senha_nuvem"]', senha);
    await a.pagina.click('text=Ligar backup na nuvem');
    await a.pagina.waitForSelector('text=último envio em', { timeout: 60000 });
    r.mais_ligado = await a.texto();
    await a.ir('#inicio');
    r.inicio_ligado = await a.texto();
    await esperar(() => metas().length === 1);
    const chaveMeta = metas()[0];
    r.id = chaveMeta.slice('meta:'.length);
    const primeiro = meta(chaveMeta);

    // 2. Cada gravação vai sozinha para a nuvem.
    await a.ir('#nova');
    await a.pagina.fill('[name="nome"]', entrada.nome);
    await a.pagina.fill('[name="aquisicao"]', entrada.aquisicao);
    await a.pagina.fill('[name="custo"]', entrada.custo);
    await a.pagina.fill('[name="previsto"]', entrada.previsto);
    await a.pagina.selectOption('[name="conta"]', { index: 1 });
    await a.pagina.fill('[name="previsao"]', entrada.previsao);
    await a.pagina.click('text=Salvar entrada');
    await a.pagina.waitForFunction(() => location.hash.startsWith('#operacao/'));
    await esperar(() => meta(chaveMeta).versao !== primeiro.versao);
    const ultimo = meta(chaveMeta);
    r.reenviado = ultimo.criado_em !== primeiro.criado_em;
    const partes = Array.from({ length: ultimo.partes }, (_, n) => Buffer.from(kv.get(`parte:${r.id}:${ultimo.versao}:${n}`)));
    r.backup = Buffer.concat(partes).toString('base64');
    r.guardado_igual = await a.pagina.evaluate(async (b64) => {
      const g = await Guarda.ler('backup');
      return btoa(Array.from(new Uint8Array(g.bytes), (b) => String.fromCharCode(b)).join('')) === b64;
    }, r.backup);
    await a.contexto.close();

    // 3. Celular novo: recupera da nuvem com a senha (errada antes, depois a certa).
    const b = await aparelho();
    await b.pagina.click('#recuperar-nuvem');
    await b.pagina.waitForSelector('#form-nuvem:not([hidden])');
    r.passo_recuperar = { form: await b.pagina.isVisible('#form-nuvem'), comecar: await b.pagina.isVisible('#comecar') };
    await b.pagina.fill('#senha-nuvem', 'outra senha 9');
    await b.pagina.click('#baixar-nuvem');
    await b.pagina.waitForSelector('#erro:not([hidden])', { timeout: 60000 });
    r.recuperar_senha_errada = await b.pagina.textContent('#erro');
    await b.pagina.fill('#senha-nuvem', senha);
    await b.pagina.click('#baixar-nuvem');
    await b.pagina.waitForSelector('#aplicativo:not([hidden])', { timeout: 120000 });
    await b.ir('#operacoes');
    r.recuperado = await b.texto();
    await b.ir('#mais');
    r.recuperado_mais = await b.texto();
    // 4. Desligar apaga a cópia da nuvem (o computador volta a editar).
    await b.pagina.click('.cartao.nuvem >> text=Desligar');
    await esperar(() => metas().length === 0);
    await b.pagina.waitForSelector('text=Ligar backup na nuvem');
    r.desligado = metas().length === 0;
    await b.contexto.close();

    // 5. Celular que abria o backup do computador vira o principal.
    const c = await aparelho();
    await c.pagina.setInputFiles('#arquivo', backupPc);
    await c.pagina.fill('#senha', senhaPc);
    await c.pagina.click('#abrir');
    await c.pagina.waitForSelector('#aplicativo:not([hidden])', { timeout: 120000 });
    await c.ir('#mais');
    r.mais_pc = await c.texto();
    await c.pagina.click('text=Tornar este celular o principal');
    await c.pagina.waitForFunction(() => location.hash === '#principal');
    r.tela_principal = await c.texto();
    await c.pagina.fill('[name="senha_nuvem"]', senhaPc + 'x');
    await c.pagina.click('button:has-text("Tornar este celular o principal")');
    await c.pagina.waitForSelector('#tela .erro');
    r.principal_senha_errada = await c.pagina.textContent('#tela .erro');
    await c.pagina.fill('[name="senha_nuvem"]', senhaPc);
    await c.pagina.click('button:has-text("Tornar este celular o principal")');
    await c.pagina.waitForFunction(() => location.hash === '#inicio', null, { timeout: 120000 });
    await esperar(() => metas().length === 1);
    r.principal_id = metas()[0].slice('meta:'.length);
    r.principal_guardado = await c.pagina.evaluate(async () => (await Guarda.ler('backup')).independente);
    await c.ir('#operacoes');
    r.principal_operacoes = await c.texto();
    await c.ir('#mais');
    r.principal_mais = await c.texto();
    await c.contexto.close();
  } finally {
    await navegador.close();
    servidor.close();
  }
  process.stdout.write(JSON.stringify(r));
})().catch((erro) => {
  console.error(erro);
  process.exit(1);
});
