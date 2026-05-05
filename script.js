/* =============================================================
   SMARTPARK — script.js integrado com API Flask + Banco SQLite
   ============================================================= */
const API_URL = 'http://localhost:5000';
const TOTAL_VAGAS = 20;

let listaVagas = [];
let dadosOcupacaoPorHora = gerarDadosHorarios();
let modoOffline = false;

function gerarDadosHorarios() {
  return Array.from({ length: 24 }, (_, hora) => {
    const ocupadas = Math.round(3 + Math.sin((hora - 8) * 0.4) * 6 + Math.random() * 3);
    return Math.max(0, Math.min(TOTAL_VAGAS, ocupadas));
  });
}

async function buscarVagasAPI() {
  try {
    const resposta = await fetch(`${API_URL}/api/vagas`, { signal: AbortSignal.timeout(3000) });
    if (!resposta.ok) throw new Error('Resposta inválida');
    const dados = await resposta.json();
    listaVagas = dados.map(v => ({
      id: v.id,
      situacao: v.situacao,
      horarioEntrada: v.horarioEntrada
        ? new Date(v.horarioEntrada).getTime()
        : Date.now() - Math.floor(Math.random() * 1800000)
    }));
    if (modoOffline) { modoOffline = false; atualizarStatusConexao(true); }
    renderizarGrade();
    atualizarGraficoHoraAtual();
  } catch (erro) {
    console.warn('API indisponível:', erro.message);
    if (!modoOffline) { modoOffline = true; atualizarStatusConexao(false); }
    if (listaVagas.length === 0) {
      listaVagas = Array.from({ length: TOTAL_VAGAS }, (_, i) => ({
        id: i + 1,
        situacao: Math.random() > 0.45 ? 'livre' : 'ocupada',
        horarioEntrada: Date.now() - Math.floor(Math.random() * 3600000)
      }));
    }
    renderizarGrade();
  }
}

function atualizarStatusConexao(online) {
  const dot = document.querySelector('.sidebar-footer .status-dot');
  if (dot) dot.style.background = online ? 'var(--green)' : 'var(--amber)';
}

function atualizarGraficoHoraAtual() {
  const totalOcupadas = listaVagas.filter(v => v.situacao === 'ocupada').length;
  dadosOcupacaoPorHora[dadosOcupacaoPorHora.length - 1] = totalOcupadas;
  if (graficoHoras) {
    graficoHoras.data.datasets[0].data = dadosOcupacaoPorHora.map(ocp => TOTAL_VAGAS - ocp);
    graficoHoras.data.datasets[1].data = [...dadosOcupacaoPorHora];
    graficoHoras.update('none');
  }
}

document.querySelectorAll('.nav-item').forEach(itemMenu => {
  itemMenu.addEventListener('click', () => {
    const pagina = itemMenu.dataset.page;
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    itemMenu.classList.add('active');
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById('page-' + pagina).classList.add('active');
    document.getElementById('topbar-title').textContent = pagina.toUpperCase();
    if (pagina === 'relatorios') inicializarGraficosRelatorio();
  });
});

document.querySelectorAll('.rtab').forEach(aba => {
  aba.addEventListener('click', () => {
    document.querySelectorAll('.rtab').forEach(x => x.classList.remove('active'));
    aba.classList.add('active');
  });
});

document.getElementById('btn-gerar').addEventListener('click', () => {
  const btn = document.getElementById('btn-gerar');
  btn.textContent = '⏳ Gerando...';
  setTimeout(() => {
    const agora = new Date();
    document.getElementById('r-gen-ts').textContent = 'Gerado em: ' + agora.toLocaleDateString('pt-BR') + ' · ' + agora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    btn.textContent = '✓ Gerado';
    setTimeout(() => { btn.textContent = '⬇ Gerar Relatório'; }, 2000);
  }, 1200);
});

/* ── grade: cria os elementos uma única vez e só atualiza o que muda ── */
let gradeInicializada = false;
let estadoAnteriorVagas = {}; // Armazena situacao anterior para evitar render excessivo

function renderizarGrade() {
  const grade = document.getElementById('parking-grid');
  const lista = document.getElementById('status-list');
  if (!grade) return;

  if (!gradeInicializada) {
    grade.innerHTML = '';
    lista.innerHTML = '';

    listaVagas.forEach(vaga => {
      // ── spot ──
      const el = document.createElement('div');
      el.id = `spot-${vaga.id}`;
      el.className = 'spot ' + _clsVaga(vaga.situacao);
      el.innerHTML = _htmlSpot(vaga);
      el.addEventListener('mouseenter', e => exibirTooltip(e, vaga));
      el.addEventListener('mouseleave', ocultarTooltip);
      grade.appendChild(el);

      // ── status list item ──
      const item = document.createElement('div');
      item.id = `list-item-${vaga.id}`;
      item.className = 'status-item';
      item.innerHTML = _htmlListItem(vaga);
      lista.appendChild(item);

      estadoAnteriorVagas[vaga.id] = { situacao: vaga.situacao };
    });

    gradeInicializada = true;
  } else {
    // Atualizações seguintes: só altera o que realmente mudou
    listaVagas.forEach(vaga => {
      const el = document.getElementById(`spot-${vaga.id}`);
      const prev = estadoAnteriorVagas[vaga.id] || {};
      
      if (el && prev.situacao !== vaga.situacao) {
        el.className = 'spot ' + _clsVaga(vaga.situacao);
        el.innerHTML = _htmlSpot(vaga);
        prev.situacao = vaga.situacao;
      }

      // O item da lista atualiza o tempo, entao checamos se mudou o texto
      const item = document.getElementById(`list-item-${vaga.id}`);
      if (item) {
        const novoHtml = _htmlListItem(vaga);
        if (item.getAttribute('data-last-html') !== novoHtml) {
          item.innerHTML = novoHtml;
          item.setAttribute('data-last-html', novoHtml);
        }
      }
    });
  }

  atualizarEstatisticas();
}

function _clsVaga(situacao) {
  if (situacao === 'indisponivel') return 'unavailable';
  return situacao === 'livre' ? 'free' : 'occupied';
}

function _htmlSpot(vaga) {
  const num = String(vaga.id).padStart(2, '0');
  if (vaga.situacao === 'ocupada') return `<div class="spot-car">🚗</div><div>${num}</div>`;
  if (vaga.situacao === 'livre') return `<div>${num}</div>`;
  return `<div style="font-size:8px;">N/D</div>`;
}

function _htmlListItem(vaga) {
  const num = String(vaga.id).padStart(2, '0');
  const tempo = vaga.situacao === 'ocupada' ? formatarDuracao(Date.now() - vaga.horarioEntrada) : '';
  return `
    <div class="spot-id">VAGA ${num}</div>
    <div style="display:flex;align-items:center;gap:8px;">
      ${vaga.situacao === 'ocupada' ? `<span style="font-size:10px;color:var(--muted);">${tempo}</span>` : ''}
      <span class="spot-badge ${vaga.situacao === 'livre' ? 'free' : 'occ'}">${vaga.situacao === 'livre' ? 'LIVRE' : 'OCUPADA'}</span>
    </div>`;
}


function formatarDuracao(ms) {
  const min = Math.floor(ms / 60000);
  if (min < 1) return 'agora';
  if (min < 60) return min + 'min';
  return Math.floor(min / 60) + 'h ' + (min % 60) + 'm';
}

function atualizarEstatisticas() {
  const livres = listaVagas.filter(v => v.situacao === 'livre').length;
  const ocupadas = listaVagas.filter(v => v.situacao === 'ocupada').length;
  const disponiveis = listaVagas.filter(v => v.situacao !== 'indisponivel').length;

  document.getElementById('s-free').textContent = livres;
  document.getElementById('s-occ').textContent = ocupadas;
  document.getElementById('s-free-pct').textContent = disponiveis > 0 ? Math.round(livres / disponiveis * 100) + '% do total' : '--';
  document.getElementById('s-occ-pct').textContent = disponiveis > 0 ? Math.round(ocupadas / disponiveis * 100) + '% do total' : '--';

  const vagasOcup = listaVagas.filter(v => v.situacao === 'ocupada');
  if (vagasOcup.length) {
    const media = vagasOcup.reduce((a, v) => a + (Date.now() - v.horarioEntrada), 0) / vagasOcup.length;
    document.getElementById('s-avg').textContent = Math.round(media / 60000) + 'm';
  }
  atualizarDonut(livres, ocupadas);
}

function atualizarRelogio() {
  const agora = new Date();
  const h = String(agora.getHours()).padStart(2, '0');
  const m = String(agora.getMinutes()).padStart(2, '0');
  const s = String(agora.getSeconds()).padStart(2, '0');
  document.getElementById('clock').textContent = h + ':' + m + ':' + s;
  document.getElementById('last-update').textContent = agora.toLocaleDateString('pt-BR') + ' ' + h + ':' + m;
  document.getElementById('map-updated').textContent = 'Atualizado: ' + h + ':' + m + ':' + s;
}

function exibirTooltip(evento, vaga) {
  const el = document.getElementById('tooltip');
  const rotulo = vaga.situacao === 'livre' ? 'Livre' : vaga.situacao === 'ocupada' ? 'Ocupada' : 'Indisponível';
  const tempo = vaga.situacao === 'ocupada' ? '<br>Há: ' + formatarDuracao(Date.now() - vaga.horarioEntrada) : '';
  el.innerHTML = `<strong>Vaga ${String(vaga.id).padStart(2, '0')}</strong><br>${rotulo}${tempo}`;
  el.style.display = 'block';
  el.style.left = (evento.clientX + 12) + 'px';
  el.style.top = (evento.clientY - 30) + 'px';
}

function ocultarTooltip() { document.getElementById('tooltip').style.display = 'none'; }

let graficoHoras, graficoDonut;

function inicializarGraficosDashboard() {
  const rotulos = Array.from({ length: 24 }, (_, i) => i.toString().padStart(2, '0') + ':00');
  graficoHoras = new Chart(document.getElementById('chart-hour'), {
    type: 'line',
    data: {
      labels: rotulos,
      datasets: [
        { label: 'Livres', data: dadosOcupacaoPorHora.map(o => TOTAL_VAGAS - o), borderColor: '#1D9E75', backgroundColor: 'rgba(29,158,117,.12)', fill: true, tension: .4, pointRadius: 2, borderWidth: 2 },
        { label: 'Ocupadas', data: [...dadosOcupacaoPorHora], borderColor: '#E24B4A', backgroundColor: 'rgba(226,75,74,.10)', fill: true, tension: .4, pointRadius: 2, borderWidth: 2, borderDash: [4, 3] }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
      scales: {
        x: { ticks: { color: '#8a8a85', font: { size: 10 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { color: '#2a2f3a' } },
        y: { min: 0, max: TOTAL_VAGAS, ticks: { color: '#8a8a85', font: { size: 10 }, stepSize: 5 }, grid: { color: '#2a2f3a' } }
      }
    }
  });

  const livres = listaVagas.filter(v => v.situacao === 'livre').length;
  const ocupadas = listaVagas.filter(v => v.situacao === 'ocupada').length;
  graficoDonut = new Chart(document.getElementById('chart-donut'), {
    type: 'doughnut',
    data: { labels: ['Livres', 'Ocupadas'], datasets: [{ data: [livres, ocupadas], backgroundColor: ['#1D9E75', '#E24B4A'], borderColor: ['#04342c', '#2a1515'], borderWidth: 3, hoverOffset: 4 }] },
    options: { responsive: false, cutout: '70%', plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => c.label + ': ' + c.raw } } } }
  });
  atualizarLegendaDonut(livres, ocupadas);
}

function atualizarDonut(livres, ocupadas) {
  if (!graficoDonut) return;
  graficoDonut.data.datasets[0].data = [livres, ocupadas];
  graficoDonut.update('none'); // Update sem animacao para evitar refresh visual
  const pct = (livres + ocupadas) > 0 ? Math.round(livres / (livres + ocupadas) * 100) : 0;
  const elPct = document.getElementById('donut-pct');
  if (elPct) elPct.textContent = pct + '%';
  atualizarLegendaDonut(livres, ocupadas);
}

function atualizarLegendaDonut(livres, ocupadas) {
  document.getElementById('donut-legend').innerHTML = `
    <span style="display:flex;align-items:center;gap:4px;color:var(--muted)"><span style="width:10px;height:10px;border-radius:2px;background:#1D9E75;display:inline-block;"></span>Livres (${livres})</span>
    <span style="display:flex;align-items:center;gap:4px;color:var(--muted)"><span style="width:10px;height:10px;border-radius:2px;background:#E24B4A;display:inline-block;"></span>Ocupadas (${ocupadas})</span>`;
}

/* ─── Carrega sessões reais do banco via API ─── */
async function carregarSessoes() {
  const tbody = document.getElementById('logs-tbody');
  try {
    const resp = await fetch(`${API_URL}/api/sessoes`, { signal: AbortSignal.timeout(3000) });
    const dados = await resp.json();

    tbody.innerHTML = '';
    if (dados.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:16px;">Nenhum registro ainda.</td></tr>';
      return;
    }

    dados.forEach(s => {
      const entrada = new Date(s.entrada_em.replace(' ', 'T'));
      const dataHora = entrada.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
        + ' ' + entrada.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
      const vagaNum = String(s.vaga_id).padStart(2, '0');
      const acao = s.saida_em ? 'Saída' : 'Entrada';
      const duracao = s.duracao_min != null
        ? (s.duracao_min < 60 ? s.duracao_min + 'min' : Math.floor(s.duracao_min / 60) + 'h ' + (s.duracao_min % 60) + 'm')
        : '-';

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="mono" style="color:var(--muted)">${dataHora}</td>
        <td class="mono" style="color:var(--muted)">—</td>
        <td class="mono">${vagaNum}</td>
        <td><span class="${acao === 'Entrada' ? 'badge-entrada' : 'badge-saida'}">${acao}</span></td>
        <td class="mono" style="color:var(--muted)">${duracao}</td>`;
      tbody.appendChild(tr);
    });
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:16px;">API indisponível.</td></tr>';
  }
}

/* ─── Carrega snapshots reais do banco para o gráfico de linha ─── */
let graficoOcupacaoRelatorio = null;
async function carregarSnapshots() {
  try {
    const resp = await fetch(`${API_URL}/api/snapshots`, { signal: AbortSignal.timeout(3000) });
    const dados = await resp.json();

    if (dados.length === 0) return; // mantém gráfico com dados simulados

    const rotulos = dados.map(d => d.hora.slice(11, 16)); // "HH:00"
    const ocupadas = dados.map(d => d.ocupadas);
    const livres = dados.map(d => d.livres);

    if (graficoOcupacaoRelatorio) {
      graficoOcupacaoRelatorio.data.labels = rotulos;
      graficoOcupacaoRelatorio.data.datasets[0].data = livres;
      graficoOcupacaoRelatorio.data.datasets[1].data = ocupadas;
      graficoOcupacaoRelatorio.update();
    }
  } catch (e) {
    console.warn('Snapshots indisponíveis, usando dados simulados.');
  }
}

let graficosRelatorioIniciados = false;
function inicializarGraficosRelatorio() {
  if (graficosRelatorioIniciados) return;
  graficosRelatorioIniciados = true;

  // Gráfico de linha — começa com dados simulados, depois sobrescreve com reais
  const horasR = ['00:00', '04:00', '06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00', '24:00'];
  graficoOcupacaoRelatorio = new Chart(document.getElementById('r-chart-line'), {
    type: 'line',
    data: {
      labels: horasR, datasets: [
        { label: 'Livres', data: [18, 18, 17, 11, 8, 5, 6, 7, 4, 2, 9, 16], borderColor: '#1D9E75', backgroundColor: 'rgba(29,158,117,.15)', fill: true, tension: .4, pointRadius: 2, borderWidth: 2 },
        { label: 'Ocupadas', data: [2, 2, 3, 9, 12, 15, 14, 13, 16, 18, 11, 4], borderColor: '#E24B4A', backgroundColor: 'rgba(226,75,74,.10)', fill: true, tension: .4, pointRadius: 2, borderWidth: 2 }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: '#8a8a85', font: { size: 10 } }, grid: { color: '#2a2f3a' } }, y: { min: 0, max: TOTAL_VAGAS, ticks: { color: '#8a8a85', font: { size: 10 } }, grid: { color: '#2a2f3a' } } } }
  });
  carregarSnapshots(); // sobrescreve com dados reais se disponíveis

  const dias = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
  const perm = [25, 18, 20, 22, 28, 30, 35, 24];
  new Chart(document.getElementById('r-chart-bar'), {
    type: 'bar',
    data: {
      labels: dias, datasets: [
        { label: 'Curta', data: perm.map(v => Math.round(v * .6)), backgroundColor: '#1D9E75', borderRadius: 3, borderSkipped: false },
        { label: 'Longa', data: perm.map(v => Math.round(v * .4)), backgroundColor: '#E24B4A', borderRadius: 3, borderSkipped: false }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { stacked: true, ticks: { color: '#8a8a85', font: { size: 10 } }, grid: { color: '#2a2f3a' } }, y: { stacked: true, max: 40, ticks: { color: '#8a8a85', font: { size: 10 } }, grid: { color: '#2a2f3a' } } } }
  });

  new Chart(document.getElementById('r-chart-traffic'), {
    type: 'bar',
    data: {
      labels: ['00:00', 'Manh.', '08:00', '12:00', '18:00', 'Noite', 'Semana'], datasets: [
        { label: 'Entradas', data: [40, 80, 110, 130, 120, 100, 90], backgroundColor: '#1D9E75', borderRadius: 3, borderSkipped: false },
        { label: 'Saídas', data: [30, 60, 80, 100, 90, 80, 70], backgroundColor: '#E24B4A', borderRadius: 3, borderSkipped: false }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { stacked: true, ticks: { color: '#8a8a85', font: { size: 9 } }, grid: { color: '#2a2f3a' } }, y: { stacked: true, max: 150, ticks: { color: '#8a8a85', font: { size: 9 } }, grid: { color: '#2a2f3a' } } } }
  });

  new Chart(document.getElementById('r-chart-tipo'), {
    type: 'doughnut',
    data: { labels: ['Curta', 'Longa'], datasets: [{ data: [12, 8], backgroundColor: ['#1D9E75', '#E24B4A'], borderColor: ['#04342c', '#2a1515'], borderWidth: 3, hoverOffset: 4 }] },
    options: { responsive: false, cutout: '68%', plugins: { legend: { display: false } } }
  });

  // Carrega logs reais do banco
  carregarSessoes();

  const agora = new Date();
  document.getElementById('r-gen-ts').textContent = 'Gerado em: ' + agora.toLocaleDateString('pt-BR') + ' · ' + agora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

/* INICIALIZAÇÃO */
atualizarRelogio();
setInterval(atualizarRelogio, 1000);

// Loop serial para evitar overlapping de requests e refresh visual excessivo
async function loopUpdate() {
  await buscarVagasAPI();
  
  // Se estiver na pagina de relatorios, atualiza logs tambem
  const paginaRelatorios = document.getElementById('page-relatorios');
  if (paginaRelatorios && paginaRelatorios.classList.contains('active')) {
    await carregarSessoes();
    await carregarSnapshots();
  }
  
  setTimeout(loopUpdate, 2000); // 2 segundos apos o fim da request anterior
}

window.addEventListener('load', async () => {
  if (window.loopIniciado) return;
  window.loopIniciado = true;

  await buscarVagasAPI();
  inicializarGraficosDashboard();
  loopUpdate(); // Inicia o loop serial
});
