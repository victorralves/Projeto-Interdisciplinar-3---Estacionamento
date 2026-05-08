/* =============================================================
   SMARTPARK — script.js integrado com API Flask + Banco SQLite
   ============================================================= */
const API_URL = 'http://localhost:5000';
let TOTAL_VAGAS = 20;

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
    // Atualiza TOTAL_VAGAS dinamicamente com base na API
    if (listaVagas.length > 0) TOTAL_VAGAS = listaVagas.length;
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

/* ── Navegação entre páginas ── */
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

/* ══════════════════════════════════════════════════════════════
   RELATÓRIOS — Estado e controles interativos
   ══════════════════════════════════════════════════════════════ */
let _relatorioDias = 1;
const _PERIODO_NOMES = { 1: 'Último dia', 7: 'Últimos 7 dias', 30: 'Últimos 30 dias', 365: 'Último ano' };

function _atualizarLabels() {
  const nome = _PERIODO_NOMES[_relatorioDias] || _relatorioDias + ' dias';
  const lbl = document.getElementById('date-range-lbl');
  if (lbl) lbl.textContent = 'Período: ' + nome;
  const titulo = document.getElementById('r-chart-title');
  if (titulo) titulo.textContent = 'Ocupação — ' + nome;
}

/* ── Tabs de período ── */
document.querySelectorAll('.rtab').forEach(aba => {
  aba.addEventListener('click', () => {
    document.querySelectorAll('.rtab').forEach(x => x.classList.remove('active'));
    aba.classList.add('active');
    const dias = parseInt(aba.dataset.dias) || 1;
    _relatorioDias = dias;
    const sel = document.getElementById('r-chart-periodo');
    if (sel) sel.value = String(dias);
    _atualizarLabels();
    carregarDadosRelatorio();
  });
});

/* ── Dropdown do gráfico sincroniza com tabs ── */
document.addEventListener('DOMContentLoaded', () => {
  const sel = document.getElementById('r-chart-periodo');
  if (sel) sel.addEventListener('change', () => {
    const dias = parseInt(sel.value) || 30;
    _relatorioDias = dias;
    document.querySelectorAll('.rtab').forEach(t => {
      t.classList.toggle('active', parseInt(t.dataset.dias) === dias);
    });
    _atualizarLabels();
    carregarDadosRelatorio();
  });

  /* ── Busca filtra a tabela de logs em tempo real ── */
  const search = document.getElementById('r-search-input');
  if (search) search.addEventListener('input', () => {
    const q = search.value.toLowerCase();
    document.querySelectorAll('#logs-tbody tr').forEach(tr => {
      tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });
});

/* ── Botão Exportar CSV ── */
document.getElementById('btn-gerar').addEventListener('click', () => {
  const btn = document.getElementById('btn-gerar');
  btn.textContent = '⏳ Gerando...';
  const url = `${API_URL}/api/exportar/csv?dias=${_relatorioDias}`;
  fetch(url, { signal: AbortSignal.timeout(8000) })
    .then(r => r.blob())
    .then(blob => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'relatorio_smartpark.csv';
      a.click();
      URL.revokeObjectURL(a.href);
      btn.textContent = '✓ Baixado';
      setTimeout(() => { btn.textContent = '⬇ Exportar CSV'; }, 2000);
    })
    .catch(() => {
      btn.textContent = '❌ Erro';
      setTimeout(() => { btn.textContent = '⬇ Exportar CSV'; }, 2000);
    });
});

/* ══════════════════════════════════════════════════════════════
   DASHBOARD — Grade de vagas e estatísticas
   ══════════════════════════════════════════════════════════════ */
let gradeInicializada = false;
let estadoAnteriorVagas = {};

function renderizarGrade() {
  const grade = document.getElementById('parking-grid');
  const lista = document.getElementById('status-list');
  if (!grade) return;

  if (!gradeInicializada) {
    grade.innerHTML = '';
    lista.innerHTML = '';
    listaVagas.forEach(vaga => {
      const el = document.createElement('div');
      el.id = `spot-${vaga.id}`;
      el.className = 'spot ' + _clsVaga(vaga.situacao);
      el.innerHTML = _htmlSpot(vaga);
      el.addEventListener('mouseenter', e => exibirTooltip(e, vaga));
      el.addEventListener('mouseleave', ocultarTooltip);
      grade.appendChild(el);

      const item = document.createElement('div');
      item.id = `list-item-${vaga.id}`;
      item.className = 'status-item';
      item.innerHTML = _htmlListItem(vaga);
      lista.appendChild(item);
      estadoAnteriorVagas[vaga.id] = { situacao: vaga.situacao };
    });
    gradeInicializada = true;
  } else {
    listaVagas.forEach(vaga => {
      const el = document.getElementById(`spot-${vaga.id}`);
      const prev = estadoAnteriorVagas[vaga.id] || {};
      if (el && prev.situacao !== vaga.situacao) {
        el.className = 'spot ' + _clsVaga(vaga.situacao);
        el.innerHTML = _htmlSpot(vaga);
        prev.situacao = vaga.situacao;
      }
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

function _clsVaga(s) { return s === 'indisponivel' ? 'unavailable' : s === 'livre' ? 'free' : 'occupied'; }

function _htmlSpot(v) {
  const n = String(v.id).padStart(2, '0');
  if (v.situacao === 'ocupada') return `<div class="spot-car">🚗</div><div>${n}</div>`;
  if (v.situacao === 'livre') return `<div>${n}</div>`;
  return `<div style="font-size:8px;">N/D</div>`;
}

function _htmlListItem(v) {
  const n = String(v.id).padStart(2, '0');
  const t = v.situacao === 'ocupada' ? formatarDuracao(Date.now() - v.horarioEntrada) : '';
  return `<div class="spot-id">VAGA ${n}</div>
    <div style="display:flex;align-items:center;gap:8px;">
      ${v.situacao === 'ocupada' ? `<span style="font-size:10px;color:var(--muted);">${t}</span>` : ''}
      <span class="spot-badge ${v.situacao === 'livre' ? 'free' : 'occ'}">${v.situacao === 'livre' ? 'LIVRE' : 'OCUPADA'}</span>
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
  document.getElementById('s-total').textContent = listaVagas.length;
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
  const mapUpdated = document.getElementById('map-updated');
  if (mapUpdated) mapUpdated.textContent = 'Atualizado: ' + h + ':' + m + ':' + s;
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

/* ══════════════════════════════════════════════════════════════
   GRÁFICOS — Dashboard
   ══════════════════════════════════════════════════════════════ */
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
  graficoDonut.update('none');
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

/* ══════════════════════════════════════════════════════════════
   RELATÓRIOS — Sessões e gráfico de ocupação
   ══════════════════════════════════════════════════════════════ */
async function carregarSessoes() {
  const tbody = document.getElementById('logs-tbody');
  try {
    const resp = await fetch(`${API_URL}/api/sessoes`, { signal: AbortSignal.timeout(3000) });
    const dados = await resp.json();
    tbody.innerHTML = '';
    const countEl = document.getElementById('logs-count');
    if (countEl) countEl.textContent = dados.length + ' registros';

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
    // Re-apply search filter if active
    const search = document.getElementById('r-search-input');
    if (search && search.value) {
      const q = search.value.toLowerCase();
      document.querySelectorAll('#logs-tbody tr').forEach(tr => {
        tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
      });
    }
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:16px;">API indisponível.</td></tr>';
  }
}

let graficoOcupacaoRelatorio = null;

function _formatarDurMin(min) {
  if (min == null) return '--';
  if (min < 60) return Math.round(min) + 'min';
  return Math.floor(min / 60) + 'h ' + Math.round(min % 60) + 'm';
}

function _aplicarResumo(d) {
  const elOcp  = document.getElementById('r-stat-ocupacao');
  const elDur  = document.getElementById('r-stat-duracao');
  const elDia  = document.getElementById('r-stat-dia');
  const elSess = document.getElementById('r-stat-sessoes');
  if (elOcp)  elOcp.textContent  = d.avg_ocupacao_pct != null ? d.avg_ocupacao_pct + '%' : '--';
  if (elDur)  elDur.textContent  = _formatarDurMin(d.avg_duracao_min);
  if (elDia)  elDia.textContent  = d.dia_maior_movimento || '--';
  if (elSess) elSess.textContent = d.total_sessoes ?? '--';
}

async function carregarDadosRelatorio() {
  try {
    const diasParam = `dias=${_relatorioDias}`;
    const [respResumo, respSnaps] = await Promise.all([
      fetch(`${API_URL}/api/relatorio/resumo?${diasParam}`, { signal: AbortSignal.timeout(4000) }),
      fetch(`${API_URL}/api/snapshots?${diasParam}`,        { signal: AbortSignal.timeout(4000) }),
    ]);
    const [resumo, snaps] = await Promise.all([respResumo.json(), respSnaps.json()]);

    _aplicarResumo(resumo);

    if (graficoOcupacaoRelatorio) {
      if (snaps.length > 0) {
        const labels = snaps.map(d => {
          if (_relatorioDias <= 1) return d.hora.slice(11, 16);
          if (_relatorioDias <= 7) return d.hora.slice(5, 16);
          return d.hora.slice(5, 10);
        });
        graficoOcupacaoRelatorio.data.labels           = labels;
        graficoOcupacaoRelatorio.data.datasets[0].data = snaps.map(d => d.livres);
        graficoOcupacaoRelatorio.data.datasets[1].data = snaps.map(d => d.ocupadas);
      } else {
        graficoOcupacaoRelatorio.data.labels = [];
        graficoOcupacaoRelatorio.data.datasets[0].data = [];
        graficoOcupacaoRelatorio.data.datasets[1].data = [];
      }
      graficoOcupacaoRelatorio.update('none');
    }

    await carregarSessoes();

    const agora = new Date();
    document.getElementById('r-gen-ts').textContent =
      'Gerado em: ' + agora.toLocaleDateString('pt-BR') + ' · '
      + agora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    console.warn('Erro ao carregar dados de relatório:', e.message);
  }
}

let graficosRelatorioIniciados = false;
function inicializarGraficosRelatorio() {
  if (graficosRelatorioIniciados) return;
  graficosRelatorioIniciados = true;

  graficoOcupacaoRelatorio = new Chart(document.getElementById('r-chart-line'), {
    type: 'line',
    data: {
      labels: [], datasets: [
        { label: 'Livres',   data: [], borderColor: '#1D9E75', backgroundColor: 'rgba(29,158,117,.15)', fill: true, tension: .4, pointRadius: 2, borderWidth: 2 },
        { label: 'Ocupadas', data: [], borderColor: '#E24B4A', backgroundColor: 'rgba(226,75,74,.10)',  fill: true, tension: .4, pointRadius: 2, borderWidth: 2 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
      scales: {
        x: { ticks: { color: '#8a8a85', font: { size: 10 }, maxRotation: 45, autoSkip: true, maxTicksLimit: 16 }, grid: { color: '#2a2f3a' } },
        y: { min: 0, max: TOTAL_VAGAS, ticks: { color: '#8a8a85', font: { size: 10 } }, grid: { color: '#2a2f3a' } }
      }
    }
  });

  _relatorioDias = 1;
  const sel = document.getElementById('r-chart-periodo');
  if (sel) sel.value = '1';
  _atualizarLabels();
  carregarDadosRelatorio();
}

/* ══════════════════════════════════════════════════════════════
   INICIALIZAÇÃO
   ══════════════════════════════════════════════════════════════ */
atualizarRelogio();
setInterval(atualizarRelogio, 1000);

async function loopUpdate() {
  const pgDash = document.getElementById('page-dashboard');
  const pgRel  = document.getElementById('page-relatorios');
  if (pgDash && pgDash.classList.contains('active')) await buscarVagasAPI();
  if (pgRel  && pgRel.classList.contains('active'))  await carregarDadosRelatorio();
  setTimeout(loopUpdate, 2000);
}

window.addEventListener('load', async () => {
  if (window.loopIniciado) return;
  window.loopIniciado = true;
  await buscarVagasAPI();
  inicializarGraficosDashboard();
  loopUpdate();
});
