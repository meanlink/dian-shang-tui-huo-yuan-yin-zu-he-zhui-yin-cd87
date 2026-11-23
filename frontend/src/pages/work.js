import {request, state} from '../api.js';
import {bindForm, empty, errorBox, esc, flash, labelList, nameOf, pageTitle, pill, WORK} from '../ui.js';

const actions = {
  accept: '接单', submit: '提交验证', close: '验证通过并结案', return: '退回复工',
};

export async function improvementsPage(root, location) {
  const rows = await request('/improvements');
  const selected = rows.find(row => String(row.id) === location.get('work')) || rows[0];
  root.innerHTML = `${pageTitle('供应商协同', '改进工单', '供应商处理批次质量问题并提交凭证，品控验证后归档。')}
    <div class="split work-split"><section class="paper"><div class="section-head"><h2>整改清单</h2><span class="mono">${rows.length} 项</span></div>
    ${rows.length ? `<div class="table-wrap"><table><thead><tr><th>工单 / 批号</th><th>质检归因</th><th>状态</th><th>期限</th></tr></thead><tbody>${rows.map(row => `<tr class="${row.id === selected.id ? 'chosen' : ''}"><td><a class="mono" href="#improvements?work=${row.id}">CAPA-${String(row.id).padStart(4, '0')}</a><small>${esc(row.batch_code)}</small></td><td>${esc(nameOf(row.finding))}<small>${esc(row.supplier)}</small></td><td>${pill(WORK[row.status], row.status === 'closed' ? 'good' : 'warn')}</td><td class="mono">${row.due_on}</td></tr>`).join('')}</tbody></table></div>` : empty('暂无整改。品控确认根因后，工单会自动分配给该批次的供应商。')}</section>
    <aside class="paper clipboard">${selected ? workCard(selected) : '<div class="section-head"><h2>工单详情</h2></div>' + empty('打开一张工单查看整改要求和验证记录。')}</aside></div>`;
  bindForm(root.querySelector('#work-action'), async data => {
    const payload = Object.fromEntries(data);
    for (const key of ['note', 'proof_ref']) if (!payload[key]) delete payload[key];
    const changed = await request(`/improvements/${selected.id}/actions`, 'POST', payload);
    flash(`工单已更新为${WORK[changed.status]}`);
    await improvementsPage(root, location);
  });
}

function workCard(row) {
  const role = state.user.role;
  let options = [];
  if (role === 'supplier' && row.status === 'assigned') options = ['accept'];
  if (role === 'supplier' && row.status === 'working') options = ['submit'];
  if (role === 'quality' && row.status === 'verification') {
    options = row.hold_status === 'held' ? ['return'] : ['close', 'return'];
  }
  const holdLink = row.hold_id ? `<a href="#holds?hold=${row.hold_id}">查看库存处置 →</a>` :
    role === 'quality' && row.status !== 'closed' ? `<a href="#holds?work=${row.id}">登记批次库存隔离 →</a>` : '';
  const submit = options.includes('submit');
  const evidence = role === 'supplier' ? `${row.evidence_count} 张验货单` : `<div class="evidence">${row.evidence.map(ticket => `<a class="mono" href="#returns?ticket=${esc(ticket)}">${esc(ticket)}</a>`).join('')}</div>`;
  return `<div class="section-head"><h2 class="mono">CAPA-${String(row.id).padStart(4, '0')}</h2>${pill(WORK[row.status], row.status === 'closed' ? 'good' : 'warn')}</div><div class="details">
    <div class="progress">${Object.entries(WORK).map(([status, name], i, list) => `<span class="${i <= list.findIndex(([key]) => key === row.status) ? 'done' : ''}">${name}</span>`).join('')}</div><dl>
    <dt>批次 / 供货</dt><dd><a class="mono" href="#batches?batch=${esc(row.batch_code)}">${esc(row.batch_code)}</a> · ${esc(row.supplier)}</dd><dt>核实组合</dt><dd>${labelList(row.symptoms)} → ${esc(nameOf(row.finding))}</dd>
    <dt>整改要求</dt><dd>${esc(row.directive)}</dd><dt>复核依据</dt><dd>${esc(row.review_note)}${evidence}</dd>${row.proof_ref ? `<dt>行动与凭证</dt><dd>${esc(row.corrective_action)} · <span class="mono">${esc(row.proof_ref)}</span></dd>` : ''}${row.verification_note ? `<dt>品控验证</dt><dd>${esc(row.verification_note)}</dd>` : ''}</dl>${holdLink ? `<div class="callout">${holdLink}${row.hold_status === 'held' ? ' · 仍有封存库存，完成处置后可结案。' : ''}</div>` : ''}</div>
    ${options.length ? `<form id="work-action" class="form-stack">${options.length === 1 ? `<input name="action" type="hidden" value="${options[0]}">` : `<label>验证决定<select name="action">${options.map(action => `<option value="${action}">${actions[action]}</option>`).join('')}</select></label>`}
    ${options[0] !== 'accept' ? `<label>${submit ? '整改行动' : '品控验证说明'}<textarea name="note" minlength="6" required>${submit ? esc(row.corrective_action) : ''}</textarea></label>` : ''}
    ${submit ? `<label>验证凭证号<input name="proof_ref" value="${esc(row.proof_ref)}" required></label>` : ''}${errorBox}<button>${options.length === 1 ? actions[options[0]] : '保存验证决定'}</button></form>` : ''}`;
}
