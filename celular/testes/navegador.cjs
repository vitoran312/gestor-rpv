// Abre os backups de teste no navegador (Chromium; o Safari do iPhone é conferido no aparelho) e imprime o que
// o leitor encontrou em cada um, em JSON, para test_celular.py comparar com o que o Python gravou.
'use strict';
const { chromium } = require('playwright');

(async () => {
  const [endereco, casosJson] = process.argv.slice(2);
  const casos = JSON.parse(casosJson);
  const navegador = await chromium.launch();
  try {
    const pagina = await navegador.newPage();
    await pagina.goto(endereco + '/index.html');
    const resultados = {};
    for (const caso of casos) {
      resultados[caso.nome] = await pagina.evaluate(async ({ arquivo, senha }) => {
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
    process.stdout.write(JSON.stringify(resultados));
  } finally {
    await navegador.close();
  }
})().catch((erro) => {
  console.error(erro);
  process.exit(1);
});
