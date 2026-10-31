// Fluxo completo do backup guardado e do Face ID, com o autenticador virtual do Chromium (faz o papel do Face
// ID, com a mesma extensão PRF). Imprime, em JSON, o que aconteceu em cada passo.
'use strict';
const { chromium } = require('playwright');

(async () => {
  const [endereco, entradaJson] = process.argv.slice(2);
  const { primeiro, segundo, senha } = JSON.parse(entradaJson);
  const navegador = await chromium.launch();
  const r = {};
  try {
    const contexto = await navegador.newContext();
    const pagina = await contexto.newPage();
    await pagina.route(/workers\.dev/, (rota) => rota.abort());  // Sem a nuvem de verdade (ver test_nuvem).
    const erros = [];
    pagina.on('pageerror', (erro) => erros.push(String(erro)));
    const cdp = await contexto.newCDPSession(pagina);
    await cdp.send('WebAuthn.enable');
    await cdp.send('WebAuthn.addVirtualAuthenticator', { options: {
      protocol: 'ctap2', transport: 'internal', hasResidentKey: true, hasUserVerification: true,
      isUserVerified: true, hasPrf: true, automaticPresenceSimulation: true,
    } });
    const aberto = () => pagina.waitForSelector('#aplicativo:not([hidden])', { timeout: 120000 });
    const estado = () => pagina.evaluate(() => ({
      app: !document.getElementById('aplicativo').hidden,
      faceid_visivel: !document.getElementById('abrir-faceid').hidden,
      fonte: document.getElementById('fonte').hidden ? '' : document.getElementById('fonte-titulo').textContent,
      erro: document.getElementById('erro').hidden ? '' : document.getElementById('erro').textContent,
    }));

    // 1. Primeira vez: os dados chegam (aqui, um backup aberto com a senha) e o app oferece o Face ID.
    // Sem nada guardado, a demonstração abre sozinha; "Começar a usar com meus dados" leva à abertura.
    const sairDaDemonstracao = async () => {
      await pagina.waitForSelector('.aviso.demonstracao button', { timeout: 30000 });
      await pagina.click('.aviso.demonstracao button');
      await pagina.waitForSelector('#abertura:not([hidden])');
    };
    const abrirArquivo = (url) => pagina.evaluate(async ({ url, senha }) => {
      await abrirArquivoGestor(new Uint8Array(await (await fetch(url)).arrayBuffer()), senha);
    }, { url, senha });
    await pagina.goto(endereco + '/index.html');
    await sairDaDemonstracao();
    r.inicial = await estado();
    await abrirArquivo(primeiro);
    await aberto();
    await pagina.waitForSelector('text=Ativar Face ID');
    await pagina.click('text=Ativar Face ID');
    await pagina.waitForFunction(() => /Pronto|Confirmar/.test(document.getElementById('tela').innerText));
    if (await pagina.locator('text=Confirmar com Face ID').count()) {
      await pagina.click('text=Confirmar com Face ID');
      await pagina.waitForSelector('text=Pronto');
    }
    r.ativado = await pagina.locator('text=Pronto').count() > 0;

    // 2. Trancar e abrir de novo: backup guardado, sem escolher arquivo; o Face ID abre sem senha e sem scrypt.
    await pagina.evaluate(() => { location.hash = '#mais'; });
    await pagina.evaluate(() => trancarGestor());
    await pagina.waitForSelector('#abrir-faceid:not([hidden])');
    r.trancado = await estado();
    await pagina.click('#abrir-faceid');
    await aberto();
    r.faceid_abriu = await pagina.evaluate(() => document.getElementById('tela').innerText.includes('Lucro previsto'));

    // 3. Fechar o app (recarregar a página): já abre pedindo o Face ID, com o backup guardado. O pedido só sai
    //    depois da animação do logo, e o logo ainda cobre a tela quando os dados aparecem.
    await pagina.addInitScript(() => {
      const original = navigator.credentials.get.bind(navigator.credentials);
      navigator.credentials.get = (...args) => {
        window.__faceIdPedidoEm = window.__faceIdPedidoEm || performance.now();
        return original(...args);
      };
    });
    await pagina.reload();
    await aberto();
    r.reabriu_sozinho = await estado();
    r.splash = await pagina.evaluate(() => ({
      pedido_em: Math.round(window.__faceIdPedidoEm || 0),
      logo_ao_abrir: Boolean(document.getElementById('splash')),
    }));
    await pagina.waitForFunction(() => !document.getElementById('splash'), null, { timeout: 5000 });
    await pagina.evaluate(() => { location.hash = '#backup'; });
    r.tempo_com_faceid = await pagina.evaluate(() => document.getElementById('tela').innerText);

    // 4. Outros dados (com outra chave) neste celular: o Face ID, que guardava a chave antiga, pede a senha uma vez.
    await abrirArquivo(segundo);
    await aberto();
    r.segundo_nomes = await pagina.evaluate(() => { location.hash = '#operacoes'; return new Promise((ok) => setTimeout(() => ok(document.getElementById('tela').innerText), 200)); });
    await pagina.evaluate(() => trancarGestor());
    await pagina.waitForSelector('#abrir-faceid:not([hidden])');
    await pagina.click('#abrir-faceid');
    await pagina.waitForSelector('#erro:not([hidden])');
    r.faceid_chave_antiga = await estado();
    await pagina.click('#usar-senha');
    await pagina.fill('#senha', senha);
    await pagina.click('#abrir');
    await aberto();
    r.segundo_guardado = await pagina.evaluate(() => { location.hash = '#operacoes'; return new Promise((ok) => setTimeout(() => ok(document.getElementById('tela').innerText), 200)); });

    // 5. Senha errada no backup guardado (sem Face ID) mostra o erro e não abre.
    await pagina.evaluate(() => { location.hash = '#mais'; });
    await pagina.evaluate(() => trancarGestor());
    await pagina.waitForSelector('#abertura:not([hidden])');
    await pagina.click('#usar-senha');  // Com Face ID ativo, a senha fica atrás de um toque.
    await pagina.fill('#senha', senha + 'x');
    await pagina.click('#abrir');
    await pagina.waitForSelector('#erro:not([hidden])');
    r.senha_errada = await estado();

    // 6. Apagar o backup guardado: volta ao começo, sem Face ID.
    await pagina.fill('#senha', senha);
    await pagina.click('#abrir');
    await aberto();
    await pagina.evaluate(() => { location.hash = '#mais'; });
    pagina.on('dialog', (d) => d.accept().catch(() => {}));
    await pagina.click('text=Apagar os dados deste celular');
    await pagina.waitForSelector('#abertura:not([hidden])');
    await pagina.reload();
    await sairDaDemonstracao();
    r.apagado = await estado();
    r.erros = erros;
  } finally {
    await navegador.close();
  }
  process.stdout.write(JSON.stringify(r));
})().catch((erro) => {
  console.error(erro);
  process.exit(1);
});
