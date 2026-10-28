// Abre o app num navegador (Chromium; o Safari do iPhone é conferido no aparelho) e imprime, em JSON, o que
// ele encontrou em cada backup de teste, as contas feitas por dados.js e os erros das telas, para
// test_celular.py comparar com o que o Python gravou e calcula.
'use strict';
const { chromium } = require('playwright');

(async () => {
  const [endereco, entradaJson] = process.argv.slice(2);
  const { casos, regras, telas } = JSON.parse(entradaJson);
  const navegador = await chromium.launch();
  try {
    const pagina = await navegador.newPage();
    const erros = [];
    pagina.on('pageerror', (erro) => erros.push(String(erro)));
    pagina.on('console', (m) => m.type() === 'error' && erros.push(m.text()));
    await pagina.goto(endereco + '/index.html');
    const resultados = { leituras: {} };
    for (const caso of casos) {
      resultados.leituras[caso.nome] = await pagina.evaluate(async ({ arquivo, senha }) => {
        const bytes = new Uint8Array(await (await fetch(arquivo)).arrayBuffer());
        try {
          const { db, manifesto, cifrado } = await LeitorBackup.ler(bytes, senha);
          const um = (sql) => db.exec(sql)[0].values[0][0];
          const nomes = db.exec('SELECT nome FROM rpvs WHERE lixeira_em IS NULL ORDER BY id')[0];
          const resultado = {
            cifrado, versao_app: manifesto.versao_app,
            operacoes: um('SELECT COUNT(*) FROM rpvs WHERE lixeira_em IS NULL'),
            lixeira: um('SELECT COUNT(*) FROM rpvs WHERE lixeira_em IS NOT NULL'),
            contas: um('SELECT COUNT(*) FROM contas'),
            documentos: um('SELECT COUNT(*) FROM documentos'),
            nomes: nomes ? nomes.values.map((linha) => linha[0]) : [],
          };
          db.close();
          return resultado;
        } catch (erro) {
          return { erro: erro.constructor.name, mensagem: erro.message };
        }
      }, caso);
    }

    // Regras de dados.js sobre o backup principal, com a mesma data de "hoje" usada no Python.
    resultados.regras = await pagina.evaluate(async ({ arquivo, senha, hoje, termos, valores, textos }) => {
      const D = GestorDados;
      const bytes = new Uint8Array(await (await fetch(arquivo)).arrayBuffer());
      const { db, extrair } = await LeitorBackup.ler(bytes, senha);
      const dados = D.carregar(db);
      db.close();
      const hex = async (b) => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', b)),
        (x) => x.toString(16).padStart(2, '0')).join('');
      const anexos = {};
      for (const lista of dados.documentos.values()) {
        for (const d of lista) {
          anexos[d.nome] = await hex(await extrair(d.caminho));
        }
      }
      const recusas = [];
      for (const caminho of ['1/naoexiste.pdf', '../banco.sqlite3', '']) {
        try {
          await extrair(caminho);
          recusas.push('aceito');
        } catch (erro) {
          recusas.push(erro.constructor.name);
        }
      }
      const [ano, mes, dia] = hoje.split('-').map(Number);
      return {
        ordem: dados.operacoes.map((r) => r.id),
        lixeira: dados.lixeira.map((r) => r.id),
        previsao_atual: Object.fromEntries(dados.operacoes.map((r) => [r.id, r.previsao_atual])),
        situacoes: Object.fromEntries(dados.operacoes.map((r) => [r.id, D.situacao(r, hoje)])),
        totais: D.contarSituacoes(dados.operacoes, hoje),
        indicadores: D.indicadores(dados.operacoes),
        buscas: Object.fromEntries(termos.map((t) => [t, D.filtrar(dados.operacoes, t).map((r) => r.id)])),
        resumo: D.resumoMensal(dados.operacoes, 12, new Date(ano, mes - 1, dia)),
        moedas: valores.map(D.moeda),
        chaves: textos.map(D.chaveTexto),
        historico: Object.fromEntries([...dados.historico].map(([id, lista]) => [id, lista.length])),
        prorrogacoes: Object.fromEntries([...dados.prorrogacoes].map(([id, lista]) => [id, lista.length])),
        documentos: Object.fromEntries([...dados.documentos].map(([id, lista]) => [id, lista.map((d) => d.nome)])),
        anexos,
        recusas,
      };
    }, regras);

    // As telas: abre o backup pelo formulário e passa por todas, guardando o texto de cada uma.
    await pagina.setInputFiles('#arquivo', telas.arquivo);
    await pagina.fill('#senha', telas.senha);
    await pagina.click('#abrir');
    await pagina.waitForSelector('#aplicativo:not([hidden])', { timeout: 120000 });
    resultados.telas = {};
    for (const endereco of telas.enderecos) {
      await pagina.evaluate((h) => { location.hash = h; }, endereco);
      await pagina.waitForFunction(() => document.getElementById('tela').childElementCount > 0);
      resultados.telas[endereco] = await pagina.evaluate(() => document.getElementById('aplicativo').innerText);
    }
    // Cada anexo aberto na tela: PDF num quadro, imagem como imagem, os dois a partir do próprio aparelho (blob:).
    resultados.documentos = {};
    for (const endereco of telas.documentos) {
      await pagina.evaluate((h) => { location.hash = h; }, endereco);
      const visualizacao = await pagina.waitForSelector('.documento iframe, .documento img, .documento .erro', { timeout: 30000 });
      resultados.documentos[endereco] = await visualizacao.evaluate((e) => ({
        tag: e.tagName.toLowerCase(), blob: (e.getAttribute('src') || '').startsWith('blob:'),
        carregada: e.tagName === 'IMG' ? e.complete && e.naturalWidth > 0 : true, titulo: document.getElementById('titulo').textContent,
      }));
      if (resultados.documentos[endereco].tag === 'img') {
        await pagina.waitForFunction(() => document.querySelector('.documento img').naturalWidth > 0, null, { timeout: 10000 })
          .then(() => { resultados.documentos[endereco].carregada = true; }).catch(() => {});
      }
    }
    await pagina.evaluate(() => { location.hash = '#mais'; });
    resultados.blob_liberado = await pagina.evaluate(() => !document.querySelector('.documento'));
    await pagina.getByText('Fechar dados').click();
    resultados.fechado = await pagina.evaluate(() => ({
      abertura: !document.getElementById('abertura').hidden,
      tela_vazia: document.getElementById('tela').childElementCount === 0,
      senha_vazia: document.getElementById('senha').value === '',
    }));
    // App na Tela de Início: o service worker guarda o código, e o app abre de novo sem internet.
    resultados.service_worker = await pagina.evaluate(() => Promise.race([
      navigator.serviceWorker.ready.then(() => true),
      new Promise((ok) => setTimeout(() => ok(false), 15000)),
    ]));
    await pagina.context().setOffline(true);
    await pagina.reload();
    resultados.sem_internet = await pagina.evaluate(() => Boolean(document.getElementById('formulario'))
      && typeof GestorDados === 'object' && typeof LeitorBackup === 'object' && typeof initSqlJs === 'function');
    await pagina.context().setOffline(false);
    resultados.erros = erros;
    process.stdout.write(JSON.stringify(resultados));
  } finally {
    await navegador.close();
  }
})().catch((erro) => {
  console.error(erro);
  process.exit(1);
});
