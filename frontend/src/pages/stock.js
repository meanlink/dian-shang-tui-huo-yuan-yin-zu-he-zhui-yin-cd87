import {request, state} from '../api.js';
import {bindForm, empty, errorBox, esc, flash, nameOf, option, pageTitle, percent, pill, WORK} from '../ui.js';

const HOLD = {held: '封存中', cleared: '已清账'};
const DISPOSITION = {release: '放行入库', scrap: '报废', vendor_return: '退回供应商'};
const OUTCOME = {pass: '抽检通过', fail: '抽检不通过'};
const count = quantity => Number(quantity).toLocaleString('zh-CN');
const capa = id => `CAPA-${String(id).padStart(4, '0')}`;
const holdBadge = row => pill(HOLD[row.status], row.status === 'cleared' ? 'good' : 'warn');
const roundBadge = row => pill(OUTCOME[row.outcome], row.outcome === 'pass' ? 'good' : 'warn');
const integer = (form, field) => Number(form.get(field));
const units = (name, label, min = 1) => `<label>${label}<input name="${name}" type="number" required min="${min}" step="1" max="1000000"></label>`;
const reference = (name, label) => `<label>${label}<input name="${name}" maxlength="40" pattern="[A-Za-z0-9][A-Za-z0-9\\-]{2,39}" required></label>`;
const notes = (label, placeholder) => `<label>${label}<textarea name="note" minlength="6" maxlength="1000" placeholder="${placeholder}" required></textarea></label>`;

async function load(location, withOptions = false) {
  const quality = state.user.role === 'quality';
  const [rows, options] = await Promise.all([
    request('/stock-holds'), withOptions && quality ? request('/stock-holds/options') : [],
  ]);
  const id = rows.find(row => String(row.id) === location.get('hold'))?.id ?? rows[0]?.id;
  const selected = id ? await request(`/stock-holds/${id}`) : null;
  return { rows, options, selected, quality };
}

function selectList(rows, selected, page, reinspection = false) {
  const title = reinspection ? '待复验库存' : '隔离台账';
  const description = reinspection ? '抽检结论绑定供应商提交版本，历史抽检可随批次回查。' : '以仓库封存单为起点，逐笔核销放行、报废和退供。';
  return `<section class="paper"><div class="section-head"><h2>${title}</h2><span>${rows.length} 批</span></div>
    <p class="section-copy">${description}</p>
    ${rows.length ? `<div class="table-wrap"><table><thead><tr><th>批号 / 商品</th><th>供应商</th><th>隔离余量</th><th>状态</th></tr></thead><tbody>
      ${rows.map(row => `<tr class="${row.id === selected?.id ? 'chosen' : ''}"><td>
        <a class="mono" href="#${page}?hold=${row.id}">${esc(row.batch_code)}</a><small>${esc(row.sku)} · ${esc(row.product)}</small></td>
        <td>${esc(row.supplier)}</td><td class="mono">${count(row.remaining_qty)} / ${count(row.held_qty)}</td><td>${holdBadge(row)}</td></tr>`).join('')}
    </tbody></table></div>` : empty('还没有库存隔离单。品控可从已确认根因的在办工单登记实物库存。')}
  </section>`;
}

function createForm(options, initial) {
  if (!options.length) return `<section class="paper"><div class="section-head"><h2>登记隔离</h2></div>
    ${empty('当前没有可登记的未结案批次。可到改进工单查看已确认根因。')}</section>`;
  return `<section class="paper"><div class="section-head"><h2>登记隔离</h2></div>
    <form id="hold-form" class="form-stack"><label>改进工单<select name="improvement_id" required><option value="">请选择已确认根因的工单</option>
    ${options.map(row => option(String(row.id), `${capa(row.id)} · ${row.batch_code} · ${nameOf(row.finding)}`, initial)).join('')}
    </select></label><div class="field-pair">${reference('hold_ref', '仓库封存凭证')}${units('held_qty', '实际封存件数')}</div>
    ${notes('封存依据', '仓位、封条和实盘依据')}${errorBox}<button type="submit">登记封存</button></form>
  </section>`;
}

const stats = row => `<div class="stock-stats">
  <div><small>封存总量</small><strong>${count(row.held_qty)}</strong></div>
  <div><small>隔离余量</small><strong>${count(row.remaining_qty)}</strong></div>
  <div><small>已放行</small><strong>${count(row.released_qty)}</strong></div>
  <div><small>已报废 / 退供</small><strong>${count(row.scrapped_qty)} / ${count(row.returned_qty)}</strong></div>
</div>`;

function movements(row) {
  if (!row.dispositions.length) return '<p class="quiet">暂无库存处置流水。</p>';
  return `<div class="stock-history"><h3>库存处置流水</h3><ul>
    ${row.dispositions.map(move => `<li><strong>${DISPOSITION[move.kind]} · ${count(move.quantity)} 件</strong>
      <span class="mono">${esc(move.disposition_ref)}</span><p>${esc(move.note)}</p></li>`).join('')}
  </ul></div>`;
}

function dispositionForm(row) {
  const release = row.current_round?.outcome === 'pass';
  return `<form class="form-stack" id="disposition-form"><h3>登记实物处置</h3>
    <div class="callout ${release ? '' : 'warn'}">${release ? `按抽检凭证 ${esc(row.current_round.inspection_ref)} 放行，或登记剩余库存的其他处置。` : '当前整改版本通过抽检后才能放行。现有隔离库存可报废或退回供应商。'}</div>
    <label>处置方式<select name="kind"><option value="release" ${release ? '' : 'disabled'}>放行入库</option>
      <option value="scrap">报废</option><option value="vendor_return">退回供应商</option></select></label>
    <div class="field-pair">${reference('disposition_ref', '仓库处置凭证')}${units('quantity', '处置件数')}</div>
    ${notes('处置说明', '核对实物数量、仓位和凭证')}${errorBox}<button type="submit">登记处置</button>
  </form>`;
}

function holdDetails(row, quality) {
  return `<section class="paper clipboard"><div class="section-head"><h2 class="mono">${esc(row.hold_ref)}</h2>${holdBadge(row)}</div>
    <div class="details"><p>${esc(row.product)} · <span class="mono">${esc(row.batch_code)}</span></p>
    <p class="quiet">${esc(row.note)}</p>${stats(row)}
    <div class="stock-links"><a href="#reinspection?hold=${row.id}">查看抽检记录 →</a>
    <a class="mono" href="#improvements?work=${row.improvement_id}">${capa(row.improvement_id)}</a></div>
    ${movements(row)}</div>${quality && row.status === 'held' ? dispositionForm(row) : ''}</section>`;
}

export async function holdsPage(root, location) {
  const { rows, options, selected, quality } = await load(location, true);
  if (!root.isConnected) return;
  root.innerHTML = `${pageTitle('库内处置', '批次库存隔离', '登记确认问题批次的实际封存数量，随仓库处置凭证核减隔离余额。')}
    <div class="split stock-split"><div class="stock-stack">${selectList(rows, selected, 'holds')}
    ${quality ? createForm(options, location.get('work')) : ''}</div>
    ${selected ? holdDetails(selected, quality) : `<aside class="paper clipboard">${empty('选择隔离单以核对库存余额和处置流水。')}</aside>`}</div>`;
  const form = root.querySelector('#hold-form');
  bindForm(form, async data => {
    const created = await request('/stock-holds', 'POST', { improvement_id: integer(data, 'improvement_id'),
      hold_ref: data.get('hold_ref'), held_qty: integer(data, 'held_qty'), note: data.get('note') });
    flash('已登记库存隔离');
    window.location.hash = `holds?hold=${created.id}`;
  });
  bindForm(root.querySelector('#disposition-form'), async data => {
    const changed = await request(`/stock-holds/${selected.id}/dispositions`, 'POST', {
      ...Object.fromEntries(data), quantity: integer(data, 'quantity'),
    });
    flash(changed.status === 'cleared' ? '库存余额已清账，可返回工单结案' : '处置已登记');
    await holdsPage(root, new URLSearchParams({ hold: selected.id }));
  });
}

function rounds(row) {
  if (!row.rounds.length) return '<p class="quiet">暂无抽检记录。</p>';
  return `<div class="stock-history"><h3>抽检履历</h3><ul>
    ${row.rounds.map(round => `<li><div class="stock-history-head"><strong class="mono">${esc(round.inspection_ref)}</strong>${roundBadge(round)}</div>
      <span class="quiet">整改凭证 ${esc(round.supplier_proof_ref)} · 缺陷 ${round.defect_qty} / ${round.sample_qty} 件（${percent(round.defect_qty / round.sample_qty)}）</span>
      <p>${esc(round.note)}</p></li>`).join('')}
  </ul></div>`;
}

function sampleDetails(row, quality) {
  if (!row) return `<aside class="paper clipboard">${empty('登记库存隔离后，可以按供应商提交的整改版本进行抽检。')}</aside>`;
  let guidance = '供应商提交整改后才能登记抽检。';
  if (row.current_round?.outcome === 'fail') guidance = '本版整改未通过，放行已锁定。请退回改进工单，等待供应商重提后复验。';
  if (row.current_round?.outcome === 'pass') guidance = '当前整改版本已通过，可返回库存隔离登记放行。';
  if (row.status === 'cleared') guidance = '库存已清账，保留抽检履历。';
  const canSample = quality && row.status === 'held' && row.submission && !row.current_round;
  const minimum = Math.min(12, row.remaining_qty);
  return `<section class="paper clipboard"><div class="section-head"><h2>${esc(nameOf(row.finding))}</h2>${holdBadge(row)}</div>
    <div class="details"><p class="mono">${esc(row.batch_code)} · ${esc(row.hold_ref)}</p>
    <p class="quiet">库存余量 ${count(row.remaining_qty)} 件 · 工单${WORK[row.work_status]}${row.submission ? ` · 当前整改凭证 ${esc(row.submission.proof_ref)}` : ''}</p>
    <p class="callout ${row.current_round?.outcome === 'fail' ? 'warn' : ''}">${canSample ? `从隔离库存中抽检至少 ${minimum} 件，零缺陷时通过。` : guidance}</p>
    <div class="stock-links"><a href="#improvements?work=${row.improvement_id}">打开改进工单 →</a><a href="#holds?hold=${row.id}">查看库存处置 →</a></div>
    ${rounds(row)}</div>
    ${canSample ? `<form class="form-stack" id="reinspection-form"><h3>签录抽检</h3>
    ${reference('inspection_ref', '仓库抽检凭证')}<div class="field-pair">${units('sample_qty', '抽检件数')}${units('defect_qty', '不合格件数', 0)}</div>
    ${notes('检验记录', '填写抽样位置、测项及异常')}${errorBox}<button type="submit">签录抽检</button></form>` : ''}
  </section>`;
}

export async function reinspectionPage(root, location) {
  const { rows, selected, quality } = await load(location);
  if (!root.isConnected) return;
  root.innerHTML = `${pageTitle('仓库验证', '整改复验抽检', '按封存批次抽样核对供应商整改，抽检结果约束该版本可否放行。')}
    <div class="split stock-split">${selectList(rows, selected, 'reinspection', true)}${sampleDetails(selected, quality)}</div>`;
  bindForm(root.querySelector('#reinspection-form'), async data => {
    const updated = await request(`/stock-holds/${selected.id}/reinspections`, 'POST', {
      ...Object.fromEntries(data), sample_qty: integer(data, 'sample_qty'), defect_qty: integer(data, 'defect_qty'),
      submission_id: selected.submission.id,
    });
    flash(OUTCOME[updated.current_round.outcome]);
    await reinspectionPage(root, new URLSearchParams({ hold: selected.id }));
  });
}
