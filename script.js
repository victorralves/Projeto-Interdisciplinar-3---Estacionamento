/* =============================================================
   SMARTPARK — script.js integrado com API Flask
   ============================================================= */
const API_URL     = 'http://localhost:5000';
const TOTAL_VAGAS = 20;

let listaVagas           = [];
let dadosOcupacaoPorHora = gerarDadosHorarios();
let modoOffline          = false;

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

function renderizarGrade() {
  const grade = document.getElementById('parking-grid');
  const lista = document.getElementById('status-list');
  grade.innerHTML = '';
  lista.innerHTML = '';

  listaVagas.forEach(vaga => {
    const el = document.createElement('div');
    const cls = vaga.situacao === 'indisponivel' ? 'unavailable' : vaga.situacao === 'livre' ? 'free' : 'occupied';
    el.className = 'spot ' + cls;
    const num = String(vaga.id).padStart(2, '0');
    if (vaga.situacao === 'ocupada')    el.innerHTML = `<div class="spot-car">🚗</div><div>${num}</div>`;
    else if (vaga.situacao === 'livre') el.innerHTML = `<div>${num}</div>`;
    else                                el.innerHTML = `<div style="font-size:8px;">N/D</div>`;
    el.addEventListener('mouseenter', e => exibirTooltip(e, vaga));
    el.addEventListener('mouseleave', ocultarTooltip);
    grade.appendChild(el);

    if (vaga.situacao !== 'indisponivel') {
      const item = document.createElement('div');
      item.className = 'status-item';
      const tempo = vaga.situacao === 'ocupada' ? formatarDuracao(Date.now() - vaga.horarioEntrada) : '';
      item.innerHTML = `
        <div class="spot-id">VAGA ${num}</div>
        <div style="display:flex;align-items:center;gap:8px;">
          ${vaga.situacao === 'ocupada' ? `<span style="font-size:10px;color:var(--muted);">${tempo}</span>` : ''}
          <span class="spot-badge ${vaga.situacao === 'livre' ? 'free' : 'occ'}">${vaga.situacao === 'livre' ? 'LIVRE' : 'OCUPADA'}</span>
        </div>`;
      lista.appendChild(item);
    }
  });
  atualizarEstatisticas();
}

function formatarDuracao(ms) {
  const min = Math.floor(ms / 60000);
  if (min < 60) return min + 'min';
  return Math.floor(min / 60) + 'h ' + (min % 60) + 'm';
}

function atualizarEstatisticas() {
  const livres      = listaVagas.filter(v => v.situacao === 'livre').length;
  const ocupadas    = listaVagas.filter(v => v.situacao === 'ocupada').length;
  const disponiveis = listaVagas.filter(v => v.situacao !== 'indisponivel').length;

  document.getElementById('s-free').textContent     = livres;
  document.getElementById('s-occ').textContent      = ocupadas;
  document.getElementById('s-free-pct').textContent = disponiveis > 0 ? Math.round(livres / disponiveis * 100) + '% do total' : '--';
  document.getElementById('s-occ-pct').textContent  = disponiveis > 0 ? Math.round(ocupadas / disponiveis * 100) + '% do total' : '--';

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
  document.getElementById('clock').textContent       = h + ':' + m + ':' + s;
  document.getElementById('last-update').textContent = agora.toLocaleDateString('pt-BR') + ' ' + h + ':' + m;
  document.getElementById('map-updated').textContent = 'Atualizado: ' + h + ':' + m + ':' + s;
}

function exibirTooltip(evento, vaga) {
  const el     = document.getElementById('tooltip');
  const rotulo = vaga.situacao === 'livre' ? 'Livre' : vaga.situacao === 'ocupada' ? 'Ocupada' : 'Indisponível';
  const tempo  = vaga.situacao === 'ocupada' ? '<br>Há: ' + formatarDuracao(Date.now() - vaga.horarioEntrada) : '';
  el.innerHTML      = `<strong>Vaga ${String(vaga.id).padStart(2, '0')}</strong><br>${rotulo}${tempo}`;
  el.style.display  = 'block';
  el.style.left     = (evento.clientX + 12) + 'px';
  el.style.top      = (evento.clientY - 30) + 'px';
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
        { label: 'Livres',   data: dadosOcupacaoPorHora.map(o => TOTAL_VAGAS - o), borderColor: '#1D9E75', backgroundColor: 'rgba(29,158,117,.12)', fill: true, tension: .4, pointRadius: 2, borderWidth: 2 },
        { label: 'Ocupadas', data: [...dadosOcupacaoPorHora],                       borderColor: '#E24B4A', backgroundColor: 'rgba(226,75,74,.10)',  fill: true, tension: .4, pointRadius: 2, borderWidth: 2, borderDash: [4,3] }
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

  const livres   = listaVagas.filter(v => v.situacao === 'livre').length;
  const ocupadas = listaVagas.filter(v => v.situacao === 'ocupada').length;
  graficoDonut = new Chart(document.getElementById('chart-donut'), {
    type: 'doughnut',
    data: { labels: ['Livres','Ocupadas'], datasets: [{ data: [livres, ocupadas], backgroundColor: ['#1D9E75','#E24B4A'], borderColor: ['#04342c','#2a1515'], borderWidth: 3, hoverOffset: 4 }] },
    options: { responsive: false, cutout: '70%', plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => c.label + ': ' + c.raw } } } }
  });
  atualizarLegendaDonut(livres, ocupadas);
}

function atualizarDonut(livres, ocupadas) {
  if (!graficoDonut) return;
  graficoDonut.data.datasets[0].data = [livres, ocupadas];
  graficoDonut.update();
  const pct = (livres + ocupadas) > 0 ? Math.round(livres / (livres + ocupadas) * 100) : 0;
  document.getElementById('donut-pct').textContent = pct + '%';
  atualizarLegendaDonut(livres, ocupadas);
}

function atualizarLegendaDonut(livres, ocupadas) {
  document.getElementById('donut-legend').innerHTML = `
    <span style="display:flex;align-items:center;gap:4px;color:var(--muted)"><span style="width:10px;height:10px;border-radius:2px;background:#1D9E75;display:inline-block;"></span>Livres (${livres})</span>
    <span style="display:flex;align-items:center;gap:4px;color:var(--muted)"><span style="width:10px;height:10px;border-radius:2px;background:#E24B4A;display:inline-block;"></span>Ocupadas (${ocupadas})</span>`;
}

let graficosRelatorioIniciados = false;
function inicializarGraficosRelatorio() {
  if (graficosRelatorioIniciados) return;
  graficosRelatorioIniciados = true;

  const horasR = ['00:00','04:00','06:00','08:00','10:00','12:00','14:00','16:00','18:00','20:00','22:00','24:00'];
  new Chart(document.getElementById('r-chart-line'), {
    type: 'line',
    data: { labels: horasR, datasets: [
      { label: 'Ocupação %', data: [10,8,15,45,60,75,70,65,80,90,55,20], borderColor: '#1D9E75', backgroundColor: 'rgba(29,158,117,.15)', fill: true, tension: .4, pointRadius: 2, borderWidth: 2 },
      { label: 'Ocupadas',   data: [5,4,10,30,40,50,45,40,60,70,35,10],  borderColor: '#E24B4A', backgroundColor: 'rgba(226,75,74,.10)',  fill: true, tension: .4, pointRadius: 2, borderWidth: 2 }
    ]},
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: '#8a8a85', font: { size: 10 } }, grid: { color: '#2a2f3a' } }, y: { min: 0, max: 100, ticks: { color: '#8a8a85', font: { size: 10 } }, grid: { color: '#2a2f3a' } } } }
  });

  const dias = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb','Dom'];
  const perm = [25,18,20,22,28,30,35,24];
  new Chart(document.getElementById('r-chart-bar'), {
    type: 'bar',
    data: { labels: dias, datasets: [
      { label: 'Curta', data: perm.map(v => Math.round(v*.6)), backgroundColor: '#1D9E75', borderRadius: 3, borderSkipped: false },
      { label: 'Longa', data: perm.map(v => Math.round(v*.4)), backgroundColor: '#E24B4A', borderRadius: 3, borderSkipped: false }
    ]},
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { stacked: true, ticks: { color: '#8a8a85', font: { size: 10 } }, grid: { color: '#2a2f3a' } }, y: { stacked: true, max: 40, ticks: { color: '#8a8a85', font: { size: 10 } }, grid: { color: '#2a2f3a' } } } }
  });

  new Chart(document.getElementById('r-chart-traffic'), {
    type: 'bar',
    data: { labels: ['00:00','Manh.','08:00','12:00','18:00','Noite','Semana'], datasets: [
      { label: 'Entradas', data: [40,80,110,130,120,100,90], backgroundColor: '#1D9E75', borderRadius: 3, borderSkipped: false },
      { label: 'Saídas',   data: [30,60,80,100,90,80,70],   backgroundColor: '#E24B4A', borderRadius: 3, borderSkipped: false }
    ]},
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { stacked: true, ticks: { color: '#8a8a85', font: { size: 9 } }, grid: { color: '#2a2f3a' } }, y: { stacked: true, max: 150, ticks: { color: '#8a8a85', font: { size: 9 } }, grid: { color: '#2a2f3a' } } } }
  });

  new Chart(document.getElementById('r-chart-tipo'), {
    type: 'doughnut',
    data: { labels: ['Curta','Longa'], datasets: [{ data: [12,8], backgroundColor: ['#1D9E75','#E24B4A'], borderColor: ['#04342c','#2a1515'], borderWidth: 3, hoverOffset: 4 }] },
    options: { responsive: false, cutout: '68%', plugins: { legend: { display: false } } }
  });

  const tbody = document.getElementById('logs-tbody');
  tbody.innerHTML = '';
  [
    { dataHora: '25/05 14:15', placa: 'ABC-1234', numeroVaga: '04', acao: 'Entrada', duracao: '-' },
    { dataHora: '25/05 13:45', placa: 'XYZ-7890', numeroVaga: '12', acao: 'Saída',   duracao: '1h 30m' },
    { dataHora: '25/05 13:45', placa: 'XYZ-7890', numeroVaga: '18', acao: 'Saída',   duracao: '1h 30m' },
    { dataHora: '25/05 14:15', placa: 'ABC-1234', numeroVaga: '04', acao: 'Entrada', duracao: '-' },
    { dataHora: '25/05 12:15', placa: 'ABC-1234', numeroVaga: '18', acao: 'Saída',   duracao: '1h 30m' },
  ].forEach(r => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td class="mono" style="color:var(--muted)">${r.dataHora}</td><td class="mono">${r.placa}</td><td class="mono">${r.numeroVaga}</td><td><span class="${r.acao==='Entrada'?'badge-entrada':'badge-saida'}">${r.acao}</span></td><td class="mono" style="color:var(--muted)">${r.duracao}</td>`;
    tbody.appendChild(tr);
  });

  const agora = new Date();
  document.getElementById('r-gen-ts').textContent = 'Gerado em: ' + agora.toLocaleDateString('pt-BR') + ' · ' + agora.toLocaleTimeString('pt-BR', { hour:'2-digit', minute:'2-digit' });
}

/* INICIALIZAÇÃO */
atualizarRelogio();
setInterval(atualizarRelogio, 1000);

window.addEventListener('load', async () => {
  await buscarVagasAPI();
  inicializarGraficosDashboard();
  setInterval(buscarVagasAPI, 2000);
});
