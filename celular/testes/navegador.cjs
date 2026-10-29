// Abre o app num navegador (Chromium ou WebKit; o Safari de verdade é conferido no aparelho) e imprime, em JSON, o que
// ele encontrou em cada backup de teste, as contas feitas por dados.js e os erros das telas, para
// test_celular.py comparar com o que o Python gravou e calcula.
'use strict';
const playwright = require('playwright');

// Chromium por padrão; no CI também WebKit, o motor do Safari do iPhone.
const NAVEGADOR = process.env.GESTOR_RPV_NAVEGADOR || 'chromium';

(async () => {
  const [endereco, entradaJson] = process.argv.slice(2);
  const { casos, regras, telas } = JSON.parse(entradaJson);
  const navegador = await playwright[NAVEGADOR].launch();
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
      await pagina.waitForFunction(() => document.getElementById('tela').childElementCount > 0
        && !document.getElementById('tela').innerText.includes('Carregando…'));
      resultados.telas[endereco] = await pagina.evaluate(() => document.getElementById('aplicativo').innerText);
    }
    // Cada anexo aberto na tela: PDF desenhado pelo pdf.js na largura da tela, com zoom; imagem como imagem.
    resultados.documentos = {};
    for (const endereco of telas.documentos) {
      await pagina.evaluate((h) => { location.hash = h; }, endereco);
      const visualizacao = await pagina.waitForSelector('.documento canvas, .documento img, .documento .erro', { timeout: 30000 });
      const tag = await visualizacao.evaluate((e) => e.tagName.toLowerCase());
      if (tag === 'canvas') {
        // Espera a primeira página terminar de ser desenhada (o WebKit leva mais tempo que o Chromium).
        await pagina.waitForFunction(() => document.querySelector('.pagina canvas').dataset.pronta === '1',
          null, { timeout: 30000 });
        const medida = () => pagina.evaluate(() => {
          const tela = document.querySelector('.pagina canvas');
          const contexto = tela.getContext('2d');
          const dados = contexto.getImageData(0, 0, tela.width, Math.floor(tela.height / 4)).data;
          let escuros = 0;
          for (let i = 0; i < dados.length; i += 4) {
            escuros += dados[i] < 128 && dados[i + 3] > 0 ? 1 : 0;
          }
          return {
            paginas: document.querySelectorAll('.pagina').length, pixels_desenhados: tela.width * tela.height,
            texto_desenhado: escuros > 50, largura: tela.getBoundingClientRect().width,
            largura_tela: document.querySelector('.visualizacao').clientWidth,
            titulo: document.getElementById('titulo').textContent,
          };
        });
        const antes = await medida();
        await pagina.click('[aria-label="Aumentar o zoom"]');
        await pagina.waitForFunction(() => document.querySelector('.pagina canvas').dataset.pronta === '1.5',
          null, { timeout: 30000 });
        antes.largura_com_zoom = (await medida()).largura;
        antes.rotulo_zoom = await pagina.evaluate(() => document.querySelector('.zoom span').textContent);
        resultados.documentos[endereco] = antes;
      } else {
        resultados.documentos[endereco] = await visualizacao.evaluate((e) => ({
          tag: e.tagName.toLowerCase(), blob: (e.getAttribute('src') || '').startsWith('blob:'), carregada: false,
          erro: e.tagName === 'P' ? e.textContent : '',
        }));
        if (tag === 'img') {
          await pagina.waitForFunction(() => document.querySelector('.documento img').naturalWidth > 0, null, { timeout: 10000 })
            .then(() => { resultados.documentos[endereco].carregada = true; }).catch(() => {});
        }
      }
    }
    // Nova entrada no celular: primeiro com um erro (a regra aparece), depois certa; o arquivo cifrado que o
    // app guardou volta em base64 para o Python importar como o programa importa.
    if (telas.nova) {
      const n = telas.nova;
      await pagina.evaluate(() => { location.hash = '#nova'; });
      await pagina.waitForSelector('form [name="nome"]');
      await pagina.fill('[name="nome"]', n.nome);
      await pagina.fill('[name="aquisicao"]', n.aquisicao);
      // Máscara de valor: os números entram pelos centavos e a pontuação aparece sozinha.
      await pagina.click('[name="custo"]');
      resultados.mascara = [];
      for (const tecla of '1234567') {
        await pagina.keyboard.type(tecla);
        resultados.mascara.push(await pagina.inputValue('[name="custo"]'));
      }
      await pagina.keyboard.press('Backspace');
      resultados.mascara.push(await pagina.inputValue('[name="custo"]'));
      await pagina.fill('[name="custo"]', '');
      await pagina.keyboard.type('900000');
      await pagina.fill('[name="previsto"]', n.previsto);
      await pagina.selectOption('[name="conta"]', String(n.conta_id));
      await pagina.fill('[name="previsao"]', n.previsao);
      await pagina.fill('[name="comissao"]', n.comissao);
      await pagina.fill('[name="observacoes"]', n.observacoes);
      await pagina.click('text=Salvar entrada');
      await pagina.waitForFunction(() => document.querySelector('form .erro').textContent.length > 0);
      resultados.nova_erro = await pagina.evaluate(() => document.querySelector('form .erro').textContent);
      await pagina.fill('[name="custo"]', n.custo);
      resultados.nova_lucro = await pagina.evaluate(() => document.querySelector('form p.discreto').textContent);
      await pagina.click('text=Salvar entrada');
      await pagina.waitForFunction(() => location.hash.startsWith('#enviar/'));
      resultados.nova_tela = await pagina.evaluate(() => document.getElementById('tela').innerText);
      resultados.nova_arquivos = await pagina.evaluate(async () => (await Guarda.ler('pendentes')).map((p) => ({
        id: p.id, arquivo: p.arquivo, bytes: btoa(String.fromCharCode(...new Uint8Array(p.bytes))) })));
      await pagina.evaluate(() => { location.hash = '#operacoes'; });
      await pagina.waitForSelector('text=aguarda o computador');
      // Entrada já importada no computador (o backup novo traz a lista): some do celular ao abrir esse backup.
      await pagina.evaluate(async (id) => {
        const lista = await Guarda.ler('pendentes');
        await Guarda.gravar('pendentes', [...lista, { id, arquivo: 'antiga.rpvcelular', criada_em: '2026-10-01T10:00:00Z', bytes: new Uint8Array([1, 2, 3]) }]);
      }, n.ja_importada);
      await pagina.evaluate(() => { location.hash = '#mais'; });
      await pagina.getByText('Trancar agora').click();
      await pagina.waitForSelector('#abertura:not([hidden])');
      await pagina.setInputFiles('#arquivo', n.backup_com_importada);
      await pagina.fill('#senha', telas.senha);
      await pagina.click('#abrir');
      await pagina.waitForSelector('#aplicativo:not([hidden])', { timeout: 120000 });
      resultados.pendentes_depois = await pagina.evaluate(async () => (await Guarda.ler('pendentes')).map((p) => p.id));
    }

    await pagina.evaluate(() => { location.hash = '#mais'; });
    resultados.blob_liberado = await pagina.evaluate(() => !document.querySelector('.documento'));
    await pagina.getByText('Trancar agora').click();
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
    // O modo sem internet do Playwright não funciona junto com service worker no WebKit: lá, fica só o registro.
    resultados.sem_internet = null;
    if (NAVEGADOR === 'chromium') {
      await pagina.context().setOffline(true);
      await pagina.reload();
      resultados.sem_internet = await pagina.evaluate(() => Boolean(document.getElementById('formulario'))
        && typeof GestorDados === 'object' && typeof LeitorBackup === 'object' && typeof initSqlJs === 'function');
      await pagina.context().setOffline(false);
    }
    resultados.erros = erros;
    process.stdout.write(JSON.stringify(resultados));
  } finally {
    await navegador.close();
  }
})().catch((erro) => {
  console.error(erro);
  process.exit(1);
});
