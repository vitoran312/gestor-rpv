// Regras de exibição do programa, iguais às de dados.py e grafico.py: situação, valores, datas, busca,
// indicadores e resumo mensal. test_celular.py compara cada uma com o resultado do Python.
'use strict';

const GestorDados = (() => {
  const TITULOS_CONTA = {
    identificacao: 'Identificação', nome: 'Nome completo', cpf: 'CPF', endereco: 'Endereço',
    numero_endereco: 'Número', cidade: 'Cidade', estado: 'Estado (UF)', banco: 'Nome do banco',
    agencia: 'Agência', numero: 'Conta bancária', pix: 'Chave Pix',
  };
  const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

  // ---- Valores e datas -------------------------------------------------------------------------------
  function moeda(valor) {
    const inteiro = Math.floor(Math.abs(valor) / 100);
    const fracao = Math.abs(valor) % 100;
    const milhares = String(inteiro).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return (valor < 0 ? '-' : '') + milhares + ',' + String(fracao).padStart(2, '0');
  }

  function reais(valor) {
    return 'R$ ' + moeda(valor);
  }

  function dataBr(iso) {
    if (!iso) {
      return '';
    }
    const [ano, mes, dia] = iso.slice(0, 10).split('-');
    return `${dia}/${mes}/${ano}`;
  }

  // Data e hora como foram gravadas no computador (sem converter fuso): "28/10/2026 às 18:42".
  function dataHora(iso) {
    if (!iso || iso.length < 16) {
      return dataBr(iso);
    }
    return `${dataBr(iso)} às ${iso.slice(11, 16)}`;
  }

  function hojeIso(hoje = new Date()) {
    const dois = (n) => String(n).padStart(2, '0');
    return `${hoje.getFullYear()}-${dois(hoje.getMonth() + 1)}-${dois(hoje.getDate())}`;
  }

  function cpf(texto) {
    const d = String(texto || '').replace(/\D/g, '');
    return d.length === 11 ? `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}` : String(texto || '');
  }

  // ---- Entrada digitada no celular (dados.centavos e Banco.problemas_da_entrada) ----------------------
  const LIMITE_NOME = 150;
  const LIMITE_OBSERVACOES = 5000;
  const VALOR_MAXIMO_CENTAVOS = 99999999999999n;  // R$ 999.999.999.999,99, como VALOR_MAXIMO.
  const MENSAGEM_VALOR = 'Informe um valor positivo ou zero, com até duas casas decimais.';

  // Texto digitado → centavos. Aceita "1.500,00", "1500,5", "R$ 1.500" e também "1,500.00" (colado do Excel).
  function centavos(texto) {
    let t = String(texto).replace('R$', '').replace(/[\s\u00a0\u202f]/g, '');
    if (t.includes(',') && t.includes('.')) {
      const [milhar, decimal] = t.lastIndexOf(',') > t.lastIndexOf('.') ? ['.', ','] : [',', '.'];
      const grupos = t.slice(0, t.lastIndexOf(decimal)).split(milhar);
      if (!(grupos[0].length >= 1 && grupos[0].length <= 3 && grupos.slice(1).every((g) => g.length === 3))) {
        throw new Error(MENSAGEM_VALOR);
      }
      t = t.split(milhar).join('').replace(decimal, '.');
    } else if (t.includes(',')) {
      t = t.split(',').join('.');
    } else if (t.includes('.')) {
      const partes = t.split('.');
      if (partes[0].length >= 1 && partes[0].length <= 3 && partes.slice(1).every((p) => /^[0-9]{3}$/.test(p))) {
        t = partes.join('');
      }
    }
    const partes = /^([0-9]+)(?:\.([0-9]+))?$/.exec(t);
    if (!partes) {
      throw new Error(MENSAGEM_VALOR);
    }
    const fracao = partes[2] || '';
    if (/[1-9]/.test(fracao.slice(2))) {
      throw new Error(MENSAGEM_VALOR);
    }
    const valor = BigInt(partes[1]) * 100n + BigInt((fracao.slice(0, 2) + '00').slice(0, 2));
    if (valor > VALOR_MAXIMO_CENTAVOS) {
      throw new Error(`O valor máximo é R$ ${moeda(Number(VALOR_MAXIMO_CENTAVOS))}.`);
    }
    return Number(valor);
  }

  function validarDataIso(texto, campo) {
    const valido = /^([0-9]{4})-([0-9]{2})-([0-9]{2})$/.exec(texto || '');
    const data = valido && new Date(Date.UTC(Number(valido[1]), Number(valido[2]) - 1, Number(valido[3])));
    if (!valido || data.getUTCMonth() !== Number(valido[2]) - 1 || data.getUTCDate() !== Number(valido[3])) {
      throw new Error(`${campo}: informe uma data válida.`);
    }
    if (Number(valido[1]) < 1900 || Number(valido[1]) > 2100) {
      throw new Error(`${campo}: informe uma data entre 1900 e 2100.`);
    }
    return texto;
  }

  const tamanho = (texto) => Array.from(texto).length;

  function nomeFormatado(texto) {
    return texto.split(/\s+/).filter(Boolean).join(' ');
  }

  // Mesmas regras de Banco.problemas_da_entrada; o computador confere de novo ao importar.
  function problemasDaEntrada(d, hoje = hojeIso()) {
    const problemas = [];
    const nome = nomeFormatado(d.nome || '');
    if (!nome) {
      problemas.push('Informe o nome completo do titular original.');
    } else if (tamanho(nome) > LIMITE_NOME) {
      problemas.push(`O nome do titular pode ter até ${LIMITE_NOME} caracteres.`);
    }
    if (tamanho(d.observacoes || '') > LIMITE_OBSERVACOES) {
      problemas.push(`As observações podem ter até ${LIMITE_OBSERVACOES} caracteres.`);
    }
    let datasValidas = true;
    for (const [chave, rotulo] of [['aquisicao', 'Data da aquisição'], ['previsao', 'Previsão de recebimento']]) {
      try {
        validarDataIso(d[chave], rotulo);
      } catch (erro) {
        problemas.push(erro.message);
        datasValidas = false;
      }
    }
    if (datasValidas) {
      if (d.aquisicao > hoje) {
        problemas.push('A data da aquisição não pode estar no futuro.');
      }
      if (d.previsao < d.aquisicao) {
        problemas.push('A previsão não pode ser anterior à aquisição.');
      }
    }
    if (d.comissao !== null && d.comissao < 0) {
      problemas.push('A comissão não pode ser negativa.');
    } else if (d.comissao !== null && d.comissao > d.previsto) {
      problemas.push('A comissão não pode superar o Valor Total RPV.');
    }
    if (d.custo <= 0) {
      problemas.push('O valor de aquisição deve ser maior que zero.');
    } else if (d.custo > d.previsto) {
      problemas.push('O valor de aquisição não pode superar o Valor Total RPV.');
    }
    return problemas;
  }

  // ---- Situação e indicadores (dados.situacao e Minhas operações) -------------------------------------
  function situacao(registro, hoje = hojeIso()) {
    if (registro.recebimento) {
      return 'recebida';
    }
    return registro.previsao_atual < hoje ? 'atrasada' : 'pendente';
  }

  function contarSituacoes(registros, hoje = hojeIso()) {
    const totais = { todas: registros.length, pendente: 0, atrasada: 0, recebida: 0 };
    for (const r of registros) {
      totais[situacao(r, hoje)] += 1;
    }
    return totais;
  }

  function indicadores(registros) {
    const soma = (lista, valor) => lista.reduce((total, r) => total + valor(r), 0);
    return {
      registros: registros.length,
      previsto: soma(registros, (r) => r.previsto - r.custo),
      realizado: soma(registros.filter((r) => r.recebimento), (r) => r.previsto - r.custo),
      aberto: soma(registros.filter((r) => !r.recebimento), (r) => r.custo),
    };
  }

  // ---- Busca (dados.normalizar, chave_texto, encontra e Banco.listar) ---------------------------------
  function normalizar(texto) {
    return Array.from(texto.normalize('NFKD').toLowerCase())
      .filter((c) => /[\p{L}\p{N}]/u.test(c)).join('');
  }

  function chaveTexto(texto) {
    return texto.replace(/['’`´]/g, '').split(/[^\p{L}\p{N}\p{M}]+|_+/u)
      .map(normalizar).filter(Boolean).join(' ');
  }

  function encontra(termo, texto) {
    if (!termo.includes(' ')) {
      return texto.includes(termo);
    }
    return (' ' + texto).includes(' ' + termo);
  }

  function filtrar(registros, busca) {
    const termo = chaveTexto(busca);
    if (!termo) {
      const minusculo = busca.toLowerCase();
      return registros.filter((r) => r.nome.toLowerCase().includes(minusculo) || dataBr(r.aquisicao).includes(busca));
    }
    return registros.filter((r) => encontra(termo, chaveTexto(r.nome)) || encontra(termo, chaveTexto(r.conta))
      || dataBr(r.aquisicao).includes(busca.trim()));
  }

  // ---- Gráfico (grafico.resumo_mensal) ----------------------------------------------------------------
  function resumoMensal(registros, meses = 12, hoje = new Date()) {
    const chaves = [];
    let ano = hoje.getFullYear();
    let mes = hoje.getMonth() + 1;
    for (let i = 0; i < meses; i += 1) {
      chaves.unshift(`${String(ano).padStart(4, '0')}-${String(mes).padStart(2, '0')}`);
      [ano, mes] = mes === 1 ? [ano - 1, 12] : [ano, mes - 1];
    }
    const totais = new Map(chaves.map((c) => [c, [0, 0]]));
    for (const r of registros) {
      if (totais.has(r.aquisicao.slice(0, 7))) {
        totais.get(r.aquisicao.slice(0, 7))[0] += 1;
      }
      if (r.recebimento && totais.has(r.recebimento.slice(0, 7))) {
        totais.get(r.recebimento.slice(0, 7))[1] += 1;
      }
    }
    return chaves.map((c) => [c, ...totais.get(c)]);
  }

  // Topo do eixo em quatro passos inteiros e redondos (1, 2 ou 5 × 10ⁿ), como grafico.escala.
  function escala(maximo) {
    for (let potencia = 1; ; potencia *= 10) {
      for (const fator of [1, 2, 5]) {
        if (fator * potencia * 4 >= maximo) {
          return fator * potencia * 4;
        }
      }
    }
  }

  // Valores de um mês ("2026-10"): quanto foi investido nas entradas e quanto entrou nos recebimentos.
  function valoresDoMes(registros, chave) {
    const entradas = registros.filter((r) => r.aquisicao.slice(0, 7) === chave);
    const recebidas = registros.filter((r) => r.recebimento && r.recebimento.slice(0, 7) === chave);
    return {
      investido: entradas.reduce((t, r) => t + r.custo, 0),
      recebido: recebidas.reduce((t, r) => t + r.previsto, 0),
      lucro: recebidas.reduce((t, r) => t + r.previsto - r.custo, 0),
    };
  }

  function quantidade(total, singular, plural) {
    return `${total} ${total === 1 ? singular : plural}`;
  }

  function rotuloMes(chave) {
    return `${MESES[Number(chave.slice(5, 7)) - 1]}/${chave.slice(2, 4)}`;
  }

  // ---- Leitura do banco do backup ----------------------------------------------------------------------
  const CONSULTA_RPVS = `SELECT r.*,
    COALESCE(r.previsao_atual_definida,
        (SELECT MAX(data) FROM prorrogacoes WHERE rpv_id=r.id), r.previsao) AS previsao_atual,
    (SELECT COUNT(*) FROM prorrogacoes WHERE rpv_id=r.id) AS total_prorrogacoes
    FROM rpvs r`;

  function linhas(db, sql) {
    const consulta = db.prepare(sql);
    const resultado = [];
    try {
      while (consulta.step()) {
        resultado.push(consulta.getAsObject());
      }
    } finally {
      consulta.free();
    }
    return resultado;
  }

  function agrupar(lista, chave) {
    const grupos = new Map();
    for (const item of lista) {
      if (!grupos.has(item[chave])) {
        grupos.set(item[chave], []);
      }
      grupos.get(item[chave]).push(item);
    }
    return grupos;
  }

  // Copia tudo o que as telas usam para objetos comuns; depois disso o banco pode ser fechado.
  function carregar(db) {
    const configuracoes = Object.fromEntries(linhas(db, 'SELECT chave, valor FROM configuracoes')
      .map((r) => [r.chave, r.valor]));
    let importadas = [];
    try {
      importadas = JSON.parse(configuracoes.entradas_celular_importadas || '[]');
    } catch (erro) {
      importadas = [];
    }
    return {
      importadasDoCelular: new Set(Array.isArray(importadas) ? importadas.filter((u) => typeof u === 'string') : []),
      operacoes: linhas(db, CONSULTA_RPVS + ' WHERE r.lixeira_em IS NULL ORDER BY aquisicao DESC, id DESC'),
      lixeira: linhas(db, CONSULTA_RPVS + ' WHERE r.lixeira_em IS NOT NULL ORDER BY lixeira_em DESC, id DESC'),
      contas: linhas(db, 'SELECT * FROM contas ORDER BY ativa DESC, identificacao COLLATE NOCASE, id'),
      documentos: agrupar(linhas(db, 'SELECT id, rpv_id, nome, caminho, tipo FROM documentos ORDER BY id'), 'rpv_id'),
      historico: agrupar(linhas(db, 'SELECT * FROM previsoes_historico ORDER BY id DESC'), 'rpv_id'),
      prorrogacoes: agrupar(linhas(db, 'SELECT * FROM prorrogacoes ORDER BY data DESC, id DESC'), 'rpv_id'),
      demonstracao: Boolean(configuracoes.dados_demonstracao),
    };
  }

  function contaDaOperacao(registro) {
    try {
      return JSON.parse(registro.conta_snapshot || '{}') || {};
    } catch (erro) {
      return {};
    }
  }

  return {
    TITULOS_CONTA, moeda, reais, dataBr, dataHora, hojeIso, cpf, situacao, contarSituacoes, indicadores,
    centavos, problemasDaEntrada, nomeFormatado, normalizar, chaveTexto, encontra, filtrar, resumoMensal, escala, valoresDoMes, quantidade, rotuloMes, carregar, contaDaOperacao,
  };
})();
