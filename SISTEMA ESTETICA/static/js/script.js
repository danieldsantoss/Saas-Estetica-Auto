const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const money = v => Number(v || 0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
const todayISO = () => new Date().toISOString().slice(0,10);

async function api(url, opts={}){
  opts.headers = opts.headers || {};
  if(opts.body && !(opts.body instanceof FormData)) opts.headers['Content-Type']='application/json';
  const r = await fetch(url, opts);
  if(r.status === 401){ location.href='/login'; return; }
  const data = await r.json().catch(()=>({}));
  if(!r.ok || data.error) throw new Error(data.error || 'Erro na requisição');
  return data;
}
function toast(msg){ const t=$('#toast'); t.textContent=msg; t.style.display='block'; setTimeout(()=>t.style.display='none',3000); }
function showPage(id){ $$('.page').forEach(p=>p.classList.remove('active')); $('#'+id).classList.add('active'); $$('.nav').forEach(n=>n.classList.toggle('active', n.dataset.page===id)); $('#pageTitle').textContent = document.querySelector(`[data-page=${id}]`)?.textContent || id; if(loaders[id]) loaders[id](); }
$$('.nav[data-page]').forEach(b=>b.addEventListener('click',()=>showPage(b.dataset.page)));

const loaders = {dashboard:loadDashboard, clientes:loadClientes, orcamentos:loadOrcamentos, tarefas:loadTasks, agenda:loadAgenda, funcionarios:loadEmployees, financeiro:loadFinanceiro, estoque:loadEstoque, relatorios:loadRelatorios, config:loadConfig};

async function loadDashboard(){
  $('#today').textContent = new Date().toLocaleDateString('pt-BR',{weekday:'long',day:'2-digit',month:'long'});
  const d = await api('/api/dashboard');
  $('#dashTasks').innerHTML = d.tarefas_hoje.map(t=>`<div class="item"><strong>${t.title}</strong><p class="muted">${t.task_time||''} • ${t.funcionario||'Sem funcionário'} • ${t.status}</p><p>${t.description||''}</p></div>`).join('') || '<p class="muted">Nenhuma tarefa para hoje.</p>';
  $('#dashServices').innerHTML = d.servicos_hoje.map(s=>`<div class="item"><strong>${s.client_name}</strong><p class="muted">${s.service_time||''} • ${s.service_name||''} • ${s.funcionario||''}</p><p>${s.vehicle||''} — ${money(s.price)}</p></div>`).join('') || '<p class="muted">Nenhum serviço agendado hoje.</p>';
  $('#dashPendentes').innerHTML = d.orcamentos_pendentes.map(o=>`<div class="item"><strong>#${o.id} ${o.cliente||'Sem cliente'}</strong><p class="muted">${o.funcionario||'Sem funcionário'} • ${money(o.total)} • ${o.status}</p></div>`).join('') || '<p class="muted">Nenhum orçamento pendente.</p>';
  $('#dashRetornos').innerHTML = d.retornos.map(o=>`<div class="item"><strong>${o.cliente||'Cliente'}</strong><p class="muted">Retorno: ${o.retorno_cliente||''} • Orçamento #${o.id}</p></div>`).join('') || '<p class="muted">Nenhum retorno cadastrado.</p>';
  $('#dashboardCards').innerHTML = [['Faturamento do mês',money(d.faturado)],['Despesas',money(d.despesas)],['Lucro',money(d.lucro)],['Clientes',d.clientes],['Orçamentos',d.orcamentos],['Serviços finalizados',d.servicos_realizados]].map(c=>`<div class="card"><span>${c[0]}</span><strong>${c[1]}</strong></div>`).join('');
  $('#ultimosBody').innerHTML = d.ultimos.map(o=>`<tr><td>#${o.id}</td><td>${o.cliente||'-'}</td><td>${o.funcionario||'-'}</td><td>${o.status}</td><td>${money(o.total)}</td><td>${(o.criado_em||'').slice(0,10)}</td></tr>`).join('');
}

async function loadClientes(){
  const q = $('#buscaCliente')?.value || '';
  const list = await api('/api/clientes?q='+encodeURIComponent(q));
  if($('#clienteSelect')) $('#clienteSelect').innerHTML = '<option value="">Selecione um cliente</option>' + list.map(c=>`<option value="${c.id}">${c.nome} ${c.placa?'- '+c.placa:''}</option>`).join('');
  if($('#clientesList')) $('#clientesList').innerHTML = list.map(c=>`<div class="item"><div class="itemTop"><div><strong>${c.nome}</strong><p class="muted">${c.telefone||''} • ${c.placa||''} ${c.modelo||''}</p></div><button class="ghost" onclick="deleteCliente(${c.id})">Excluir</button></div><p>${c.observacoes||''}</p></div>`).join('') || '<p class="muted">Nenhum cliente.</p>';
}
$('#clienteForm')?.addEventListener('submit', async e=>{e.preventDefault(); await api('/api/clientes',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(e.target)))}); e.target.reset(); toast('Cliente salvo!'); loadClientes(); loadDashboard();});
async function deleteCliente(id){ if(confirm('Excluir cliente?')){ await api('/api/clientes/'+id,{method:'DELETE'}); loadClientes(); }}

let servicosCache=[];
async function loadServicos(){
  servicosCache = await api('/api/servicos');
  $('#servicosBox').innerHTML = servicosCache.map(s=>`<label class="service"><input type="checkbox" data-id="${s.id}" data-nome="${s.nome}" data-desc="${s.descricao||''}" data-preco="${s.preco}"><span><strong>${s.nome}</strong><small>${s.descricao||''}</small></span><input type="number" step="0.01" value="${s.preco}"></label>`).join('');
  $$('#servicosBox input').forEach(i=>i.addEventListener('input',calcTotal)); calcTotal();
}
function calcTotal(){ let total=0; $$('#servicosBox .service').forEach(row=>{ const cb=row.querySelector('input[type=checkbox]'); const val=Number(row.querySelector('input[type=number]').value||0); if(cb.checked) total+=val; }); const desconto=Number($('#orcamentoForm [name=desconto]')?.value||0); $('#orcTotal').textContent=money(Math.max(0,total-desconto)); }
$('#orcamentoForm [name=desconto]')?.addEventListener('input',calcTotal);
async function loadOrcamentos(){
  await Promise.all([loadClientes(), loadServicos(), loadEmployees(false)]);
  const list = await api('/api/orcamentos');
  $('#orcamentosList').innerHTML = list.map(o=>`<div class="item"><div class="itemTop"><div><strong>#${o.id} - ${o.cliente||'Sem cliente'}</strong><p class="muted">${o.data_servico||''} ${o.hora_servico||''} • ${o.funcionario||'Sem funcionário'} • ${o.forma_pagamento||''}</p></div><span class="pill ${o.status==='finalizado'?'ok':o.status==='cancelado'?'red':''}">${o.status}</span></div><h3>${money(o.total)}</h3><div class="miniBtns">${o.status!=='finalizado'?`<button onclick="finalizar(${o.id})">Finalizar + PDF</button>`:''}<button onclick="gerarPdf(${o.id})">Gerar PDF</button>${o.recibo_pdf?`<a class="ghost" href="/recibos/${o.recibo_pdf}" target="_blank">Abrir PDF</a>`:''}</div></div>`).join('') || '<p class="muted">Nenhum orçamento salvo.</p>';
}
$('#orcamentoForm')?.addEventListener('submit', async e=>{
  e.preventDefault(); const fd = new FormData(e.target); const itens=[];
  $$('#servicosBox .service').forEach(row=>{ const cb=row.querySelector('input[type=checkbox]'); if(cb.checked) itens.push({servico_id:cb.dataset.id,nome:cb.dataset.nome,descricao:cb.dataset.desc,valor:row.querySelector('input[type=number]').value}); });
  fd.append('itens', JSON.stringify(itens)); await api('/api/orcamentos',{method:'POST',body:fd}); e.target.reset(); toast('Orçamento salvo!'); loadOrcamentos(); loadDashboard(); loadFinanceiro();
});
async function finalizar(id){ const r=await api(`/api/orcamentos/${id}/finalizar`,{method:'POST'}); toast('Serviço finalizado e PDF gerado!'); loadOrcamentos(); loadDashboard(); if(r.pdf) window.open('/recibos/'+r.pdf,'_blank'); }
async function gerarPdf(id){ const r=await api(`/api/orcamentos/${id}/pdf`); if(r.pdf) window.open('/recibos/'+r.pdf,'_blank'); }

async function loadEmployees(render=true){
  const list = await api('/api/employees');
  ['#orcEmployee','#taskEmployee','#agendaEmployee','#relFuncionario'].forEach(sel=>{ const el=$(sel); if(el){ const first=el.querySelector('option')?.outerHTML || '<option value="">Funcionário</option>'; el.innerHTML = first + list.filter(e=>e.status==='ativo').map(e=>`<option value="${e.id}">${e.name}</option>`).join(''); }});
  if(render && $('#employeesList')) $('#employeesList').innerHTML = list.map(e=>`<div class="item"><div class="itemTop"><div><strong>${e.name}</strong><p class="muted">${e.role||''} • ${e.phone||''} • ${e.email||''}</p></div><span class="pill ${e.status==='ativo'?'ok':'red'}">${e.status}</span></div><div class="miniBtns"><button onclick="inativarEmployee(${e.id})">Desativar</button></div></div>`).join('') || '<p class="muted">Nenhum funcionário.</p>';
  return list;
}
$('#employeeForm')?.addEventListener('submit', async e=>{e.preventDefault(); await api('/api/employees',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(e.target)))}); e.target.reset(); toast('Funcionário salvo!'); loadEmployees();});
async function inativarEmployee(id){ await api('/api/employees/'+id,{method:'DELETE'}); loadEmployees(); }

async function loadTasks(){ await loadEmployees(false); const list=await api('/api/tasks'); $('#tasksList').innerHTML=list.map(t=>`<div class="item"><div class="itemTop"><div><strong>${t.title}</strong><p class="muted">${t.task_date||''} ${t.task_time||''} • ${t.funcionario||'Sem funcionário'}</p></div><span class="pill ${t.status==='concluída'?'ok':''}">${t.status}</span></div><p>${t.description||''}</p><div class="miniBtns"><button onclick="concluirTask(${t.id}, '${t.title.replaceAll("'", '')}', '${t.description||''}', '${t.task_date||''}', '${t.task_time||''}', '${t.employee_id||''}')">Concluir</button><button onclick="deleteTask(${t.id})">Excluir</button></div></div>`).join('') || '<p class="muted">Nenhuma tarefa.</p>'; }
$('#taskForm')?.addEventListener('submit', async e=>{e.preventDefault(); await api('/api/tasks',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(e.target)))}); e.target.reset(); toast('Tarefa salva!'); loadTasks(); loadDashboard();});
async function concluirTask(id,title,description,task_date,task_time,employee_id){ await api('/api/tasks/'+id,{method:'PUT',body:JSON.stringify({title,description,task_date,task_time,employee_id,status:'concluída'})}); loadTasks(); loadDashboard(); }
async function deleteTask(id){ await api('/api/tasks/'+id,{method:'DELETE'}); loadTasks(); loadDashboard(); }

async function loadAgenda(){ await loadEmployees(false); const list=await api('/api/services-agenda'); $('#agendaList').innerHTML=list.map(s=>`<div class="item"><div class="itemTop"><div><strong>${s.client_name}</strong><p class="muted">${s.service_date||''} ${s.service_time||''} • ${s.funcionario||'Sem funcionário'}</p></div><span class="pill ${s.status==='finalizado'?'ok':''}">${s.status}</span></div><p>${s.vehicle||''} — ${s.service_name||''} — ${money(s.price)}</p><button class="ghost" onclick="deleteAgenda(${s.id})">Excluir</button></div>`).join('') || '<p class="muted">Nenhum serviço agendado.</p>'; }
$('#agendaForm')?.addEventListener('submit', async e=>{e.preventDefault(); await api('/api/services-agenda',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(e.target)))}); e.target.reset(); toast('Serviço agendado!'); loadAgenda(); loadDashboard();});
async function deleteAgenda(id){ await api('/api/services-agenda/'+id,{method:'DELETE'}); loadAgenda(); loadDashboard(); }

$('#financeiroForm')?.addEventListener('submit', async e=>{e.preventDefault(); await api('/api/financeiro',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(e.target)))}); e.target.reset(); toast('Lançamento salvo!'); loadFinanceiro(); loadDashboard();});
async function loadFinanceiro(){ const list=await api('/api/financeiro'); $('#financeiroList').innerHTML=list.map(f=>`<div class="item"><div class="itemTop"><div><strong>${f.nome}</strong><p class="muted">${f.categoria||''} • ${f.data||''}</p></div><span class="pill ${f.tipo==='entrada'?'ok':'red'}">${f.tipo}</span></div><h3>${money(f.valor)}</h3><p>${f.observacoes||''}</p></div>`).join('') || '<p class="muted">Nenhum lançamento.</p>'; }

$('#estoqueForm')?.addEventListener('submit', async e=>{e.preventDefault(); await api('/api/estoque',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(e.target)))}); e.target.reset(); toast('Produto salvo!'); loadEstoque();});
async function loadEstoque(){ const list=await api('/api/estoque'); $('#estoqueList').innerHTML=list.map(p=>`<div class="item"><div class="itemTop"><div><strong>${p.nome}</strong><p class="muted">${p.categoria||''} • Fornecedor: ${p.fornecedor||''}</p></div><span class="pill ${Number(p.quantidade)<=Number(p.minimo)?'red':'ok'}">${p.quantidade} ${p.unidade||''}</span></div><p>Custo: ${money(p.custo)} • Mínimo: ${p.minimo}</p><div class="miniBtns"><button onclick="movEstoque(${p.id},'entrada')">Entrada</button><button onclick="movEstoque(${p.id},'saida')">Saída</button></div></div>`).join('') || '<p class="muted">Nenhum produto.</p>'; }
async function movEstoque(id,tipo){ const qtd=prompt(`Quantidade para ${tipo}:`); if(!qtd) return; await api(`/api/estoque/${id}/movimentar`,{method:'POST',body:JSON.stringify({tipo,quantidade:qtd,motivo:'Movimentação manual'})}); loadEstoque(); }

async function loadRelatorios(){ await loadEmployees(false); if(!$('#relMes').value) $('#relMes').value=new Date().toISOString().slice(0,7); const params=new URLSearchParams({mes:$('#relMes').value,cliente:$('#relCliente').value,servico:$('#relServico').value,funcionario:$('#relFuncionario').value,inicio:$('#relInicio').value,fim:$('#relFim').value,ano:$('#relAno').value}); const r=await api('/api/relatorios?'+params); $('#relCards').innerHTML=[['Faturamento filtrado',money(r.faturamento)],['Quantidade',r.quantidade],['Despesas do mês',money(r.despesas)],['Estoque baixo',r.estoque_baixo.length]].map(c=>`<div class="card"><span>${c[0]}</span><strong>${c[1]}</strong></div>`).join(''); $('#relDetalhes').innerHTML=r.detalhes.map(d=>`<div class="item"><strong>#${d.id} ${d.cliente||''}</strong><p class="muted">${d.servicos||''} • ${d.funcionario||'Sem funcionário'} • ${d.data||''}</p><h3>${money(d.total)}</h3></div>`).join('') || '<p class="muted">Sem resultados.</p>'; const max=Math.max(...r.servicos.map(s=>s.qtd),1); $('#servicosRel').innerHTML=r.servicos.map(s=>`<div class="bar"><strong>${s.nome}</strong><span class="muted"> ${s.qtd}x • ${money(s.total)}</span><div class="barFill" style="width:${(s.qtd/max)*100}%"></div></div>`).join('') || '<p class="muted">Sem dados.</p>'; $('#clientesRel').innerHTML=r.clientes_top.map(c=>`<div class="item"><strong>${c.nome}</strong><p class="muted">${c.qtd} serviços • ${money(c.total)}</p></div>`).join('') || '<p class="muted">Sem dados.</p>'; $('#baixoRel').innerHTML=r.estoque_baixo.map(p=>`<div class="item"><strong>${p.nome}</strong><p class="muted">Quantidade: ${p.quantidade} ${p.unidade||''} • mínimo: ${p.minimo}</p></div>`).join('') || '<p class="muted">Nenhum produto baixo.</p>'; }
async function exportReportPdf(){ const r=await api('/api/relatorios/pdf?'+new URLSearchParams({mes:$('#relMes').value,cliente:$('#relCliente').value,servico:$('#relServico').value,funcionario:$('#relFuncionario').value,inicio:$('#relInicio').value,fim:$('#relFim').value,ano:$('#relAno').value})); if(r.pdf) window.open('/relatorios_pdf/'+r.pdf,'_blank'); }

let currentConfig = {};
function initials(name){ return (name || 'AD').split(' ').filter(Boolean).slice(0,2).map(p=>p[0]).join('').toUpperCase(); }
function applyConfig(c={}){
  currentConfig = c;
  const systemName = c.nome_sistema || c.nome || 'AutoDetail Manager';
  const companyName = c.nome || 'Sua empresa';
  document.title = systemName;
  document.documentElement.style.setProperty('--primary', c.cor_principal || '#3b82f6');
  document.documentElement.style.setProperty('--primary-dark', c.cor_principal || '#2563eb');
  document.body.dataset.theme = localStorage.getItem('themeOverride') || c.tema || 'light';
  if($('#brandSystemName')) $('#brandSystemName').textContent = systemName;
  if($('#brandCompanyName')) $('#brandCompanyName').textContent = companyName;
  if($('#topCompanyName')) $('#topCompanyName').textContent = companyName;
  if($('#brandLogo')) $('#brandLogo').innerHTML = c.logo ? `<img src="/uploads/logos/${c.logo}" alt="Logo">` : initials(systemName);
  if($('#logoPreview')) $('#logoPreview').innerHTML = c.logo ? `<img src="/uploads/logos/${c.logo}" alt="Logo atual"><span>Logo atual salva</span>` : 'Nenhuma logo enviada';
}
function toggleTheme(){
  const next = document.body.dataset.theme === 'light' ? 'dark' : 'light';
  document.body.dataset.theme = next;
  localStorage.setItem('themeOverride', next);
}
async function loadConfig(){
  const c=await api('/api/config');
  applyConfig(c);
  Object.entries(c).forEach(([k,v])=>{ const el=$(`#configForm [name=${k}]`); if(el && el.type!=='file') el.value=v||''; });
  const me=await api('/api/me'); $('#accountForm [name=username]').value=me.username||'';
}
$('#configForm')?.addEventListener('submit', async e=>{
  e.preventDefault();
  const r = await fetch('/api/config',{method:'POST',body:new FormData(e.target)});
  if(!r.ok){ toast('Erro ao salvar configurações'); return; }
  toast('Configurações salvas!');
  await loadConfig();
});
$('#accountForm')?.addEventListener('submit', async e=>{e.preventDefault(); try{ await api('/api/account',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(e.target)))}); e.target.current_password.value=''; e.target.new_password.value=''; e.target.confirm_password.value=''; toast('Usuário/senha atualizados!'); }catch(err){ toast(err.message); }});

loadConfig().finally(loadDashboard);
