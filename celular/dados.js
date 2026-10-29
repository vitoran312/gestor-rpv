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
  const MESES_EXTENSO = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro',
    'outubro', 'novembro', 'dezembro'];

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

  // ---- Conta de recebimento digitada no celular (Banco.salvar_conta, validar_cpf e chave_pix) -----------
  const ESTADOS = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 'PA', 'PB', 'PR',
    'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'];

  function validarCpf(texto) {
    if (!texto.trim()) {
      throw new Error('Informe o CPF.');
    }
    if (/[^0-9.\-\s]/.test(texto)) {
      throw new Error('CPF inválido.');
    }
    const cpf = texto.replace(/\D/g, '');
    if (cpf.length !== 11 || new Set(cpf).size === 1) {
      throw new Error('CPF inválido.');
    }
    for (const tamanho of [9, 10]) {
      let soma = 0;
      for (let i = 0; i < tamanho; i += 1) {
        soma += Number(cpf[i]) * (tamanho + 1 - i);
      }
      const resto = (soma * 10) % 11;
      if (Number(cpf[tamanho]) !== (resto === 10 ? 0 : resto)) {
        throw new Error('CPF inválido.');
      }
    }
    return cpf;
  }

  function chavePix(texto) {
    const t = texto.trim().toLowerCase();
    if (!/^[0-9+ ().\-/]+$/.test(t)) {
      return ['texto', t];
    }
    let digitos = t.replace(/\D/g, '');
    const tipo = /[./]/.test(t) ? 'documento' : /[()+ ]/.test(t) ? 'telefone' : 'numero';
    if (tipo !== 'documento' && (digitos.length === 12 || digitos.length === 13) && digitos.startsWith('55')) {
      digitos = digitos.slice(2);
    }
    return [tipo, digitos];
  }

  function mesmaChavePix(uma, outra) {
    const [[tipoA, valorA], [tipoB, valorB]] = [chavePix(uma), chavePix(outra)];
    if (!valorA || valorA !== valorB) {
      return false;
    }
    // CPF e celular podem ter os mesmos 11 dígitos sem serem a mesma chave.
    return tipoA === tipoB || tipoA === 'numero' || tipoB === 'numero';
  }

  const semZeros = (texto) => normalizar(texto).replace(/^0+/, '') || '0';

  // Mesmas regras de Banco.salvar_conta, inclusive as de duplicidade contra as contas já conhecidas.
  function problemasDaConta(c, existentes) {
    const d = Object.fromEntries(Object.keys(TITULOS_CONTA).map((k) => [k, (c[k] || '').trim()]));
    const faltando = Object.keys(TITULOS_CONTA).filter((k) => k !== 'agencia' && !d[k]).map((k) => TITULOS_CONTA[k]);
    const problemas = faltando.length ? [`Preencha: ${faltando.join(', ')}.`] : [];
    if (d.estado && !ESTADOS.includes(d.estado.toUpperCase())) {
      problemas.push('Selecione um estado brasileiro válido.');
    }
    if (d.cpf) {
      try {
        validarCpf(d.cpf);
      } catch (erro) {
        problemas.push(erro.message);
      }
    }
    if (problemas.length) {
      return problemas;
    }
    for (const outra of existentes) {
      if (normalizar(outra.identificacao) === normalizar(d.identificacao)) {
        problemas.push('Já existe uma conta com essa identificação, inclusive entre as desativadas.');
      } else if (normalizar(outra.banco) === normalizar(d.banco) && semZeros(outra.numero) === semZeros(d.numero)
        && (!outra.agencia || !d.agencia || semZeros(outra.agencia) === semZeros(d.agencia))) {
        problemas.push('Essa conta bancária já está cadastrada.');
      } else if (mesmaChavePix(outra.pix || '', d.pix)) {
        problemas.push('Essa chave Pix já está cadastrada em outra conta.');
      }
    }
    return [...new Set(problemas)];
  }

  // ---- Gravação direta no celular (quem usa só o app): mesmas transformações de dados.py e cifra.py ------
  // str.title() do Python: maiúscula depois de tudo o que não é letra ("d'ávila" → "D'Ávila").
  function titulo(texto) {
    let anteriorLetra = false;
    return Array.from(texto).map((c) => {
      const letra = c.toLowerCase() !== c.toUpperCase();
      const saida = letra ? (anteriorLetra ? c.toLowerCase() : c.toUpperCase()) : c;
      anteriorLetra = letra;
      return saida;
    }).join('');
  }

  // dados.nome_formatado: espaços normalizados e iniciais maiúsculas.
  function nomeTitulo(texto) {
    return titulo(nomeFormatado(texto));
  }

  const primeiraMaiuscula = (texto) => texto.slice(0, 1).toUpperCase() + texto.slice(1);

  // Linha da tabela contas como Banco.salvar_conta grava (inclusive as chaves que impedem duplicidade).
  function linhaDaConta(c) {
    const d = Object.fromEntries(Object.keys(TITULOS_CONTA).map((k) => [k, (c[k] || '').trim()]));
    d.estado = d.estado.toUpperCase();
    d.cpf = validarCpf(d.cpf);
    for (const campo of ['nome', 'endereco', 'cidade']) {
      d[campo] = nomeTitulo(d[campo]);
    }
    for (const campo of ['identificacao', 'endereco', 'banco']) {
      d[campo] = primeiraMaiuscula(d[campo]);
    }
    return { ...d, identificacao_chave: normalizar(d.identificacao), banco_chave: normalizar(d.banco),
      agencia_chave: d.agencia ? (normalizar(d.agencia).replace(/^0+/, '') || '0') : '',
      numero_chave: normalizar(d.numero).replace(/^0+/, '') || '0' };
  }

  // Banco.snapshot: os dados da conta guardados na operação, no mesmo texto que o json.dumps do Python.
  function snapshotConta(conta) {
    return '{' + Object.keys(TITULOS_CONTA).map((k) => `${JSON.stringify(k)}: ${JSON.stringify(conta[k] ?? '')}`)
      .join(', ') + '}';
  }

  // cifra.validar_senha.
  const BASES_OBVIAS = new Set(["", "senha", "minhasenha", "password", "passw", "qwerty", "qwertyuiop", "asdf", "asdfgh", "abc", "abcd", "abcdef", "abcabc", "abcabcab", "iloveyou", "teamo", "brasil", "admin", "teste", "mudar", "mudarsenha", "gestor", "gestorrpv", "rpv", "vitoran", "backup", "dragon", "monkey", "letmein", "welcome"]);
  const SENHA_MINIMA = 10;
  const SENHA_MAXIMA = 256;

  function validarSenha(senha) {
    if (senha !== senha.trim()) {
      throw new Error('A senha não pode começar nem terminar com espaço.');
    }
    const caracteres = Array.from(senha);
    if (caracteres.length < SENHA_MINIMA || caracteres.length > SENHA_MAXIMA) {
      throw new Error(`A senha precisa ter de ${SENHA_MINIMA} a ${SENHA_MAXIMA} caracteres.`);
    }
    const letras = Array.from(senha.toLowerCase().normalize('NFKD')).filter((c) => /\p{L}/u.test(c)).join('');
    const minusculo = Array.from(senha.toLowerCase());
    let passos = 0;
    for (let i = 1; i < minusculo.length; i += 1) {
      passos += Math.abs(minusculo[i].codePointAt(0) - minusculo[i - 1].codePointAt(0)) <= 1 ? 1 : 0;
    }
    if (new Set(caracteres).size < 4 || BASES_OBVIAS.has(letras) || passos >= caracteres.length - 3) {
      throw new Error('Essa senha é fácil demais de adivinhar. Use uma frase com palavras que só você liga, '
        + 'por exemplo "cavalo azul bebe café".');
    }
    return senha;
  }

  // ---- Situação e indicadores (dados.situacao e Minhas operações) -------------------------------------
  function situacao(registro, hoje = hojeIso()) {
    if (registro.recebimento) {
      return 'recebida';
    }
    return registro.previsao_atual < hoje ? 'atrasada' : 'pendente';
  }

  // ---- Edição no celular (as mesmas regras de Banco.salvar e Banco.atualizar_previsao) ------------------
  function problemasDaEdicao(registro, d, hoje = hojeIso()) {
    const problemas = problemasDaEntrada(d, hoje);
    if (!problemas.length) {
      if (registro.recebimento && d.aquisicao > registro.recebimento) {
        problemas.push('A aquisição não pode ser posterior à data do recebimento.');
      }
      if ((registro.previsao_atual_definida || registro.total_prorrogacoes) && d.aquisicao > registro.previsao_atual) {
        problemas.push('A aquisição não pode ser posterior à previsão atual.');
      }
    }
    return problemas;
  }

  function problemasDaPrevisao(registro, nova) {
    try {
      validarDataIso(nova, 'Nova previsão');
    } catch (erro) {
      return [erro.message];
    }
    if (nova < registro.aquisicao) {
      return ['A previsão atual não pode ser anterior à aquisição.'];
    }
    return nova === registro.previsao_atual ? ['A nova previsão é igual à atual.'] : [];
  }

  // ---- Colar e preencher -------------------------------------------------------------------------------
  // Lê um texto colado (WhatsApp, e-mail, cópia do processo) e encontra titular, CPF, número do processo, valores
  // e datas. Valores e datas são reconhecidos pelo que vem antes deles na mesma linha ("Valor da RPV: R$ ...").
  // Devolve só o que encontrou; a pessoa confere no formulário antes de salvar.
  const ROTULO_NOME = /(?:\bnome(?:\s+completo)?|\btitular(?:\s+original)?|\bbenefici[áa]ri[oa]|\brequerente|\bautora?|\bcredora?|\bcliente|\bexequente|\bcedente|\bparte)(?:\s*[:\-–]\s*|\s+)([A-Za-zÀ-ÖØ-öø-ÿ'’. -]+)/gi;
  const FIM_DO_NOME = /\s+(?:cpf|rg|portador|portadora|inscrit[oa]|processo|valor|nascid[oa]|residente|brasileir[oa])\b.*$/i;
  const DINHEIRO = /R\$\s*(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:,\d{2})?)|(\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2})(?![\d,])/g;
  const ROTULOS_VALOR = [
    ['comissao', /comiss/],
    ['custo', /aquisic|compra|proposta|oferta|pagar|pago|paguei|pagamos|cessao|negociad|investid/],
    ['previsto', /total|rpv|requisi|bruto|credito|face|precatori|valor/],
  ];
  const ROTULOS_DATA = [
    ['aquisicao', /aquisic|compra|cessao|negociad|fechad|assinad/],
    ['previsao', /previs|pagament|pagto|deposit|liberac|receb|vencim|prazo|pago em|sai em/],
  ];

  function semAcentos(texto) {
    return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  }

  function nomeDaMensagem(texto) {
    for (const [, achado] of texto.matchAll(ROTULO_NOME)) {
      const nome = nomeFormatado(achado.replace(FIM_DO_NOME, '').replace(/[.\-–\s]+$/, ''));
      if (nome.split(' ').length >= 2 && /^[A-Za-zÀ-ÖØ-öø-ÿ]/.test(nome)) {
        return nome;
      }
    }
    // Sem rótulo: uma linha só com o nome em maiúsculas, como nos documentos do processo.
    const linha = texto.split('\n').map((l) => nomeFormatado(l)).find((l) => /^[A-ZÀ-ÖØ-Þ'’. -]+$/.test(l)
      && l.split(' ').length >= 2 && l.length >= 8 && l.length <= LIMITE_NOME);
    return linha || null;
  }

  function extrairDaMensagem(texto) {
    const t = String(texto || '').replace(/\r/g, '');
    const achado = {};
    const nome = nomeDaMensagem(t);
    if (nome) {
      achado.nome = nome;
    }
    const processo = t.match(/(?<![\d.-])(\d{7})-?(\d{2})\.?(\d{4})\.?(\d)\.?(\d{2})\.?(\d{4})(?![\d.-])/);
    if (processo) {
      achado.processo = `${processo[1]}-${processo[2]}.${processo[3]}.${processo[4]}.${processo[5]}.${processo[6]}`;
    }
    for (const [candidato] of t.matchAll(/(?<![\d.-])\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?![\d.-])/g)) {
      try {
        achado.cpf = cpf(validarCpf(candidato));
        break;
      } catch (erro) {
        // Não é um CPF válido (ou é parte de outro número): segue procurando.
      }
    }
    for (const linha of t.split('\n')) {
      let inicio = 0;
      for (const m of linha.matchAll(DINHEIRO)) {
        const antes = semAcentos(linha.slice(inicio, m.index)).slice(-60);
        inicio = m.index + m[0].length;
        let valor;
        try {
          valor = centavos(m[1] || m[2]);
        } catch (erro) {
          continue;
        }
        const rotulo = ROTULOS_VALOR.find(([, padrao]) => padrao.test(antes));
        const campo = rotulo ? rotulo[0] : 'previsto';
        if (valor > 0 && achado[campo] === undefined) {
          achado[campo] = valor;
        }
      }
      inicio = 0;
      for (const m of linha.matchAll(/(?<!\d)(\d{1,2})\/(\d{1,2})\/(\d{4})(?!\d)/g)) {
        const antes = semAcentos(linha.slice(inicio, m.index)).slice(-60);
        inicio = m.index + m[0].length;
        const iso = `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`;
        const rotulo = ROTULOS_DATA.find(([, padrao]) => padrao.test(antes));
        try {
          validarDataIso(iso, 'Data');
        } catch (erro) {
          continue;
        }
        if (rotulo && achado[rotulo[0]] === undefined) {
          achado[rotulo[0]] = iso;
        }
      }
    }
    return achado;
  }

  // ---- Agenda das previsões ---------------------------------------------------------------------------
  function somarDias(iso, dias) {
    const [ano, mes, dia] = iso.split('-').map(Number);
    return hojeIso(new Date(ano, mes - 1, dia + dias));
  }

  // Operações ainda não recebidas, pela previsão atual: atrasadas, hoje, amanhã e nos próximos 7 dias (depois
  // de amanhã até daqui a uma semana), e todas agrupadas por dia (para o calendário).
  function agenda(registros, hoje = hojeIso()) {
    const abertas = registros.filter((r) => !r.recebimento)
      .sort((a, b) => a.previsao_atual.localeCompare(b.previsao_atual) || a.nome.localeCompare(b.nome, 'pt-BR'));
    const amanha = somarDias(hoje, 1);
    const semana = somarDias(hoje, 7);
    const porDia = new Map();
    for (const r of abertas) {
      if (!porDia.has(r.previsao_atual)) {
        porDia.set(r.previsao_atual, []);
      }
      porDia.get(r.previsao_atual).push(r);
    }
    return {
      atrasadas: abertas.filter((r) => r.previsao_atual < hoje),
      hoje: porDia.get(hoje) || [],
      amanha: porDia.get(amanha) || [],
      semana: abertas.filter((r) => r.previsao_atual > amanha && r.previsao_atual <= semana),
      porDia,
    };
  }

  // Semanas de um mês ("2026-10"), de domingo a sábado: cada dia como data ISO, ou null fora do mês.
  function semanasDoMes(chave) {
    const [ano, mes] = chave.split('-').map(Number);
    const dias = new Date(ano, mes, 0).getDate();
    const celulas = Array(new Date(ano, mes - 1, 1).getDay()).fill(null);
    for (let dia = 1; dia <= dias; dia += 1) {
      celulas.push(`${chave}-${String(dia).padStart(2, '0')}`);
    }
    while (celulas.length % 7) {
      celulas.push(null);
    }
    return Array.from({ length: celulas.length / 7 }, (_, i) => celulas.slice(i * 7, i * 7 + 7));
  }

  function mesVizinho(chave, passo) {
    const [ano, mes] = chave.split('-').map(Number);
    const data = new Date(ano, mes - 1 + passo, 1);
    return `${data.getFullYear()}-${String(data.getMonth() + 1).padStart(2, '0')}`;
  }

  function nomeDoMes(chave) {
    return `${MESES_EXTENSO[Number(chave.slice(5, 7)) - 1]} de ${chave.slice(0, 4)}`;
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
    centavos, problemasDaEntrada, validarDataIso, nomeFormatado, nomeTitulo, linhaDaConta, snapshotConta, validarSenha, primeiraMaiuscula, ESTADOS, validarCpf, mesmaChavePix, problemasDaConta, normalizar, chaveTexto, encontra, filtrar, resumoMensal, escala, valoresDoMes, quantidade, rotuloMes, carregar, contaDaOperacao,
    problemasDaEdicao, problemasDaPrevisao, extrairDaMensagem, somarDias, agenda, semanasDoMes, mesVizinho, nomeDoMes,
  };
})();
