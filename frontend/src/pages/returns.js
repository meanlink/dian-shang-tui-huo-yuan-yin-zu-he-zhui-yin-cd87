import {request, state} from '../api.js';
import {batchOptions, bindForm, empty, errorBox, esc, FLAGS, flash, labelList, localDate, nameOf, option, pageTitle, pill} from '../ui.js';

function symptoms(selected = []) {
  return `<fieldset><legend>客诉标签</legend><div class="check-grid">${Object.values(state.tags).filter(tag => tag.kind === 'symptom').map(tag => `<label title="互斥组 ${esc(tag.mutex)}"><input type="checkbox" name="symptoms" value="${esc(tag.code)}" ${selected.includes(tag.code) ? 'checked' : ''}>${esc(tag.name)}</label>`).join('')}</div><small>同组最多保留一项。原始标签冲突可先登记，待查证后补正。</small></fieldset>`;
}

export async function returnsPage(root, location) {
  const rows = await request('/returns');
  const selected = rows.find(row => row.ticket === location.get('ticket'));
  const role = state.user.role;
  const mode = location.has('new') && role === 'service' ? 'new' : '';
  const filter = location.get('filter');
  const shown = filter === 'excluded' ? rows.filter(row => row.flags.length) : rows;
  root.innerHTML = `${pageTitle('售后归档', '退货单', '登记客诉及到货批号，补正后由品控签录验货结论。', role === 'service' ? '<a class="button" href="#returns?new=1">＋ 登记退货</a>' : '')}
    <div class="split returns-split"><section class="paper">
      <div class="section-head"><h2>售后清单</h2><span class="mono">${shown.length} / ${rows.length} 单</span></div>
      <div class="filter-bar"><a class="${!filter ? 'active' : ''}" href="#returns">全部退货</a><a class="${filter === 'excluded' ? 'active' : ''}" href="#returns?filter=excluded">待补证据 ${rows.filter(row => row.flags.length).length}</a></div>
      <div class="table-wrap">${shown.length ? `<table><thead><tr><th>退货票号 / SKU</th><th>客诉现象</th><th>证据状态</th></tr></thead><tbody>${shown.map(row => `<tr class="${row.ticket === selected?.ticket ? 'chosen' : ''}"><td><a class="mono" href="#returns?ticket=${esc(row.ticket)}${filter ? '&filter=excluded' : ''}">${esc(row.ticket)}</a><small>${esc(row.sku)} · ${esc(row.opened_on)}</small></td><td><div class="tags">${labelList(row.symptoms)}</div></td><td><div class="tags">${row.flags.length ? row.flags.map(flag => pill(FLAGS[flag], flag === 'uninspected' ? '' : 'warn')).join(' ') : pill('已签录', 'good')}</div></td></tr>`).join('')}</tbody></table>` : empty('筛选结果为空。可切回全部退货查看原始登记。')}</div>
    </section><aside class="paper clipboard">${mode ? newForm() : selected ? detail(selected, role) : `<div class="section-head"><h2>证据检查</h2></div>${empty('选择票号，查看标签、批号与质检记录。')}`}</aside></div>`;
  bindForm(root.querySelector('#source'), async data => {
    const info = {batch_code: data.get('batch_code') || null, symptoms: data.getAll('symptoms')};
    if (mode) Object.assign(info, Object.fromEntries(['ticket', 'order_ref', 'sku', 'opened_on', 'detail'].map(key => [key, data.get(key)])));
    else info.revision = selected.revision;
    const updated = await request(mode ? '/returns' : `/returns/${selected.ticket}/source`, mode ? 'POST' : 'PATCH', info);
    flash(updated.flags.length ? '已保存到待补清单' : '已保存来源');
    if (mode) window.location.hash = `returns?ticket=${updated.ticket}`;
    else await returnsPage(root, location);
  });
  bindForm(root.querySelector('#inspection'), async data => {
    await request(`/returns/${selected.ticket}/inspection`, 'PUT', {...Object.fromEntries(data), revision: selected.revision});
    flash('已签录质检结论');
    await returnsPage(root, location);
  });
}

const sourceFields = row => `<label>商品批次<select name="batch_code" ${row ? 'aria-label="补录商品批次"' : ''}>${option('', '未查到批号', row?.batch_code || '')}${batchOptions(row?.batch_code)}</select></label>${symptoms(row?.symptoms)}`;

function newForm() {
  return `<div class="section-head"><h2>登记退货</h2><a href="#returns">取消</a></div><form id="source" class="form-stack">
    <label>退货号<input name="ticket" placeholder="RT-261130" required></label><label>订单号<input name="order_ref" placeholder="SO-78450" required></label>
    <div class="field-pair"><label>SKU<input name="sku" placeholder="MUG-480" required></label><label>登记日<input type="date" name="opened_on" value="${localDate()}" required></label></div>
    ${sourceFields()}<label>原始描述<textarea name="detail" placeholder="记录买家提供的现象" minlength="6" required></textarea></label>
    ${errorBox}<button>保存退货单</button></form>`;
}

function detail(row, role) {
  const blocked = row.flags.some(flag => flag !== 'uninspected');
  const isQuality = role === 'quality';
  return `<div class="section-head"><h2 class="mono">${esc(row.ticket)}</h2><span class="mono quiet">REV ${row.revision}</span></div>
    <div class="details"><dl><dt>订单 / SKU</dt><dd class="mono">${esc(row.order_ref)} / ${esc(row.sku)}</dd><dt>来源批号</dt><dd>${row.batch_code ? `<a class="mono" href="#batches?batch=${esc(row.batch_code)}">${esc(row.batch_code)}</a>` : '待补录'}</dd><dt>客诉标签</dt><dd>${labelList(row.symptoms)}</dd><dt>客诉记录</dt><dd>${esc(row.detail)}</dd><dt>仓库验货</dt><dd>${row.finding ? `${esc(nameOf(row.finding))} · <span class="mono">${esc(row.inspection_ref)}</span>` : '尚未签录'}</dd></dl>
    ${blocked ? '<div class="callout warn">此单已隔离。缺批号或标签互斥时，无法质检签录，也不会进入根因汇总。</div>' : ''}</div>
    ${isQuality ? (blocked ? '' : `<form id="inspection" class="form-stack">
      <label>质检结论<select name="finding" required>${option('', '选择仓库验货结论', row.finding || '')}${Object.values(state.tags).filter(tag => tag.kind === 'finding').map(tag => option(tag.code, tag.name, row.finding)).join('')}</select></label>
      <label>验货凭证号<input name="inspection_ref" value="${esc(row.inspection_ref)}" placeholder="QC-HX-030" required></label>${errorBox}<button>签录质检</button></form>`)
      : `<form id="source" class="form-stack"><h3>补正客诉与批号</h3>${sourceFields(row)}${row.finding ? '<small>修改客诉或批号后，已有验货结论须重新签录。</small>' : ''}${errorBox}<button>保存补正</button></form>`}`;
}
