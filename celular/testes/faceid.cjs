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

    // 1. Primeira vez: escolhe o arquivo e digita a senha; o app oferece o Face ID.
    // Sem nada guardado, a demonstração abre sozinha; "Começar com meus dados" leva à abertura de sempre.
    const sairDaDemonstracao = async () => {
      await pagina.waitForSelector('text=Começar com meus dados', { timeout: 30000 });
      await pagina.click('text=Começar com meus dados');
      await pagina.waitForSelector('#abertura:not([hidden])');
    };
    await pagina.goto(endereco + '/index.html');
    await sairDaDemonstracao();
    r.inicial = await estado();
    await pagina.setInputFiles('#arquivo', primeiro);
    await pagina.fill('#senha', senha);
    await pagina.click('#abrir');
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
    await pagina.click('text=Trancar agora');
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

    // 4. Backup novo, aberto pelo mesmo Face ID: passa a ser o guardado e a chave nova fica no Face ID.
    await pagina.evaluate(() => { location.hash = '#mais'; });
    await pagina.click('text=Trancar agora');
    await pagina.waitForSelector('#abertura:not([hidden])');
    await pagina.setInputFiles('#arquivo', segundo);
    await pagina.waitForFunction(() => document.getElementById('fonte-titulo').textContent.includes('escolhido'));
    await pagina.click('#abrir-faceid');
    await aberto();
    r.segundo_nomes = await pagina.evaluate(() => { location.hash = '#operacoes'; return new Promise((ok) => setTimeout(() => ok(document.getElementById('tela').innerText), 200)); });
    await pagina.reload();
    await aberto();
    r.segundo_guardado = await pagina.evaluate(() => { location.hash = '#operacoes'; return new Promise((ok) => setTimeout(() => ok(document.getElementById('tela').innerText), 200)); });

    // 4b. Em Mais, "Abrir um backup mais novo": escolhe o arquivo e o Face ID abre direto, sem passar pela abertura.
    await pagina.evaluate(() => { location.hash = '#mais'; });
    await pagina.waitForSelector('[name="escolher_backup"]', { state: 'attached' });
    r.mais_escolher = await pagina.evaluate(() => document.querySelector('label.escolher-backup').innerText);
    await pagina.setInputFiles('[name="escolher_backup"]', primeiro);
    await pagina.waitForFunction(() => !document.getElementById('aplicativo').hidden && location.hash === '#inicio'
      && !document.getElementById('tela').innerText.includes('Abrir um backup mais novo'), null, { timeout: 60000 });
    r.pelo_mais = await pagina.evaluate(() => { location.hash = '#operacoes'; return new Promise((ok) => setTimeout(() => ok(document.getElementById('tela').innerText), 200)); });

    // 5. Senha errada no backup guardado (sem Face ID) mostra o erro e não abre.
    await pagina.evaluate(() => { location.hash = '#mais'; });
    await pagina.click('text=Trancar agora');
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
    pagina.once('dialog', (d) => d.accept());
    await pagina.click('text=Apagar o backup guardado');
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
