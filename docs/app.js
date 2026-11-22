(function () {
  'use strict';

  var perguntas = [];
  var temaAtivo = 'Todos';
  var selecionada = null;

  var elBusca = document.getElementById('busca');
  var elTemas = document.getElementById('temas');
  var elLista = document.getElementById('lista');
  var elContagem = document.getElementById('contagem');
  var elDetalhe = document.getElementById('detalhe');
  var elTotal = document.getElementById('total');

  // Remove acentos e caixa para a busca ("matrícula" encontra "matricula")
  function normalizar(texto) {
    return (texto || '').toString().toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  }

  function criar(tag, classe, texto) {
    var el = document.createElement(tag);
    if (classe) el.className = classe;
    if (texto !== undefined) el.textContent = texto;
    return el;
  }

  function filtrar() {
    var termos = normalizar(elBusca.value).split(/\s+/).filter(Boolean);
    return perguntas.filter(function (q) {
      if (temaAtivo !== 'Todos' && q.tema !== temaAtivo) return false;
      var alvo = normalizar([q.pergunta, q.resposta, q.tema, (q.fontes || []).join(' ')].join(' '));
      return termos.every(function (t) { return alvo.indexOf(t) !== -1; });
    });
  }

  function desenharTemas() {
    var temas = ['Todos'];
    perguntas.forEach(function (q) { if (temas.indexOf(q.tema) === -1) temas.push(q.tema); });
    elTemas.innerHTML = '';
    temas.forEach(function (tema) {
      var b = criar('button', 'tema', tema);
      b.type = 'button';
      b.setAttribute('aria-pressed', tema === temaAtivo ? 'true' : 'false');
      b.addEventListener('click', function () { temaAtivo = tema; desenharTemas(); desenharLista(); });
      elTemas.appendChild(b);
    });
  }

  function desenharLista() {
    var resultado = filtrar();
    elLista.innerHTML = '';
    elContagem.textContent = resultado.length === 1 ? '1 dúvida encontrada' : resultado.length + ' dúvidas encontradas';
    if (!resultado.length) {
      elLista.appendChild(criar('li', 'aviso', 'Nenhuma dúvida encontrada. Tente outra palavra ou outro tema.'));
      return;
    }
    resultado.forEach(function (q) {
      var li = criar('li');
      var b = criar('button', 'item', q.pergunta);
      b.type = 'button';
      if (selecionada && selecionada.id === q.id) b.setAttribute('aria-current', 'true');
      b.addEventListener('click', function () { selecionar(q); });
      li.appendChild(b);
      elLista.appendChild(li);
    });
  }

  function selecionar(q) {
    selecionada = q;
    desenharLista();
    elDetalhe.innerHTML = '';

    var etiquetas = criar('div', 'etiquetas');
    etiquetas.appendChild(criar('span', 'etiqueta', q.tema));
    etiquetas.appendChild(criar('span', 'etiqueta', q.tipo));
    elDetalhe.appendChild(etiquetas);

    elDetalhe.appendChild(criar('h3', '', q.pergunta));
    elDetalhe.appendChild(criar('div', 'rotulo', 'Resposta conferida no documento oficial'));
    elDetalhe.appendChild(criar('p', 'resposta', q.resposta));

    var fonte = criar('div', 'fonte');
    fonte.appendChild(criar('strong', '', 'Fonte:'));
    var texto = (q.fontes || []).join('; ');
    if (q.local) texto += ' – ' + q.local;
    fonte.appendChild(criar('span', '', texto));
    elDetalhe.appendChild(fonte);

    if (q.assistente) {
      var det = criar('details', 'assistente');
      det.appendChild(criar('summary', '', 'Ver a resposta gerada pelo assistente (RAG)'));
      // Remove a marcação de negrito do Markdown e mostra como texto simples
      det.appendChild(criar('div', 'assistente-texto', q.assistente.replace(/\*\*/g, '')));
      elDetalhe.appendChild(det);
    }

    elDetalhe.appendChild(criar('p', 'aviso', 'Informação válida para os documentos de 2026. Confira sempre o documento oficial antes de agir.'));
  }

  elBusca.addEventListener('input', desenharLista);

  fetch('perguntas.json')
    .then(function (r) { return r.json(); })
    .then(function (dados) {
      perguntas = dados;
      elTotal.textContent = dados.length;
      desenharTemas();
      desenharLista();
      if (dados.length) selecionar(dados[0]);
    })
    .catch(function () {
      elContagem.textContent = 'Não foi possível carregar as dúvidas. Recarregue a página.';
    });
})();
