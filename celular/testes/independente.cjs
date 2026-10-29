// Quem usa só o celular: começa sem computador, cadastra conta e entrada, registra o recebimento, tranca e abre
// de novo. Imprime, em JSON, o que aconteceu e o arquivo guardado (base64), para o Python abrir no programa.
'use strict';
const playwright = require('playwright');

const NAVEGADOR = process.env.GESTOR_RPV_NAVEGADOR || 'chromium';

(async () => {
  const [endereco, entradaJson] = process.argv.slice(2);
  const { senha, conta, entrada, hoje, senhas_ruins: senhasRuins, nomes, senhas_regra: senhasRegra } = JSON.parse(entradaJson);
  const navegador = await playwright[NAVEGADOR].launch();
  const r = {};
  try {
    const pagina = await (await navegador.newContext()).newPage();
    const erros = [];
    pagina.on('pageerror', (erro) => erros.push(String(erro)));
    const texto = () => pagina.evaluate(() => document.getElementById('tela').innerText);
    const ir = async (hash) => {
      await pagina.evaluate((h) => { location.hash = h; }, hash);
      await pagina.waitForFunction((h) => location.hash === h && document.getElementById('tela').childElementCount > 0, hash);
    };
    await pagina.goto(endereco + '/index.html');
    // Regras de dados.js comparadas com o Python.
    r.regras = await pagina.evaluate(({ nomes, senhasRegra }) => ({
      titulos: nomes.map(GestorDados.nomeTitulo),
      senhas: senhasRegra.map((s) => { try { GestorDados.validarSenha(s); return 'ok'; } catch (e) { return e.message; } }),
    }), { nomes, senhasRegra });

    // 1. Primeira vez: "Começar sem computador", com senhas ruins antes da boa.
    await pagina.click('#comecar');
    r.erros_senha = [];
    for (const [nova, repetida] of senhasRuins) {
      await pagina.fill('#senha-nova', nova);
      await pagina.fill('#senha-repetida', repetida);
      await pagina.click('#criar');
      await pagina.waitForSelector('#erro:not([hidden])');
      r.erros_senha.push(await pagina.textContent('#erro'));
    }
    await pagina.fill('#senha-nova', senha);
    await pagina.fill('#senha-repetida', senha);
    await pagina.click('#criar');
    await pagina.waitForSelector('#aplicativo:not([hidden])', { timeout: 120000 });
    r.inicio_vazio = await texto();

    // 2. Conta e entrada gravadas direto no celular.
    await ir('#nova-conta');
    for (const [campo, valor] of Object.entries(conta)) {
      if (campo === 'estado') {
        await pagina.selectOption('[name="estado"]', valor);
      } else {
        await pagina.fill(`[name="${campo}"]`, valor);
      }
    }
    await pagina.click('text=Salvar conta');
    await pagina.waitForFunction(() => location.hash === '#contas');
    await pagina.waitForSelector('text=+ Nova conta');
    r.contas = await texto();
    await ir('#nova');
    await pagina.fill('[name="nome"]', entrada.nome);
    await pagina.fill('[name="aquisicao"]', entrada.aquisicao);
    await pagina.fill('[name="custo"]', entrada.custo);
    await pagina.fill('[name="previsto"]', entrada.previsto);
    await pagina.selectOption('[name="conta"]', { index: 1 });
    await pagina.fill('[name="previsao"]', entrada.previsao);
    await pagina.fill('[name="observacoes"]', entrada.observacoes);
    await pagina.click('text=Salvar entrada');
    await pagina.waitForFunction(() => location.hash.startsWith('#operacao/'));
    await pagina.waitForSelector('text=Registrar recebimento');
    r.detalhe = await texto();

    // 3. Recebimento: primeiro no futuro (recusado), depois numa data válida.
    await pagina.fill('[name="recebimento"]', '2099-01-01');
    await pagina.click('text=Registrar recebimento');
    await pagina.waitForFunction(() => document.querySelector('form.recebimento .erro').textContent.length > 0);
    r.erro_recebimento = await pagina.textContent('form.recebimento .erro');
    await pagina.fill('[name="recebimento"]', hoje);
    await pagina.click('text=Registrar recebimento');
    await pagina.waitForFunction(() => !document.querySelector('form.recebimento'));
    r.detalhe_recebido = await texto();
    await ir('#inicio');
    r.inicio_com_dados = await texto();

    // 4. Trancar e abrir de novo com a senha: os dados continuam.
    await ir('#mais');
    r.mais = await texto();
    await pagina.click('text=Trancar agora');
    await pagina.waitForFunction(() => document.getElementById('fonte-titulo').textContent.length > 0
      && !document.getElementById('abertura').hidden);
    r.abertura = await pagina.evaluate(() => ({
      fonte: document.getElementById('fonte-titulo').textContent,
      comecar: !document.getElementById('comecar').hidden,
      trocar: document.getElementById('trocar-backup').textContent,
    }));
    await pagina.fill('#senha', senha);
    await pagina.click('#abrir');
    await pagina.waitForSelector('#aplicativo:not([hidden])', { timeout: 120000 });
    await ir('#operacoes');
    r.operacoes_depois = await texto();
    await ir('#copia');
    r.copia = await texto();
    await ir('#convite');
    r.convite = await texto();
    r.guardado = await pagina.evaluate(async () => {
      const g = await Guarda.ler('backup');
      return { independente: g.independente, bytes: btoa(Array.from(new Uint8Array(g.bytes), (b) => String.fromCharCode(b)).join('')) };
    });
    r.erros = erros;
  } finally {
    await navegador.close();
  }
  process.stdout.write(JSON.stringify(r));
})().catch((erro) => {
  console.error(erro);
  process.exit(1);
});
