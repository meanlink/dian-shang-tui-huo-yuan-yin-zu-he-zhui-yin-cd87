import {request, state} from '../api.js';
import {bindForm, empty, errorBox, esc, flash, localDate, pageTitle} from '../ui.js';

export async function batchesPage(root, location) {
  const rows = await request('/batches');
  const supplier = state.user.role === 'supplier';
  const quality = state.user.role === 'quality';
  const selected = rows.find(row => row.code === location.get('batch')) || rows[0];
  const add = quality && location.has('new');
  root.innerHTML = `${pageTitle('仓库溯源', '商品批次', '用到货批号核对 SKU、供应商和退货证据。', quality ? '<a class="button" href="#batches?new=1">＋ 登记批次</a>' : '')}
    <div class="split batch-split"><section class="paper"><div class="section-head"><h2>${supplier ? '我的供货批次' : '到货台账'}</h2><span class="mono">${rows.length} 批</span></div>
    ${rows.length ? `<div class="batch-list">${rows.map(row => `<a class="batch-entry ${!add && row.code === selected?.code ? 'chosen' : ''}" href="#batches?batch=${esc(row.code)}"><span class="barcode" aria-hidden="true"></span><span><span class="mono quiet">${esc(row.code)} · ${esc(row.sku)}</span><strong>${esc(row.product)}</strong><small>${esc(row.supplier)} · ${row.received_on} 到货</small></span><span class="mono qty">${row.delivered_qty.toLocaleString()} 件</span></a>`).join('')}</div>` : empty('当前没有符合权限范围的商品批次。')}</section>
    <aside class="paper clipboard">${add ? `<div class="section-head"><h2>登记到货批次</h2><a href="#batches">取消</a></div><form id="batch-form" class="form-stack">
      <div class="field-pair"><label>到货批号<input name="code" required></label><label>SKU<input name="sku" required></label></div><label>商品名称<input name="product" required></label><label>供应商<input name="supplier" required></label>
      <div class="field-pair"><label>到货日期<input name="received_on" type="date" value="${localDate()}" required></label><label>到货件数<input name="delivered_qty" type="number" min="1" required></label></div>${errorBox}<button>登记批次</button></form>` : selected ? `<div class="section-head"><h2>批次溯源卡</h2></div><div class="details"><span class="eyebrow">${esc(selected.supplier)}</span><h2>${esc(selected.product)}</h2><div class="mono batch-number">${esc(selected.code)}</div><dl><dt>SKU / 到货日</dt><dd class="mono">${esc(selected.sku)} / ${selected.received_on}</dd><dt>已绑定退货</dt><dd><b>${selected.returns}</b> 单</dd><dt>已签验货结论</dt><dd><b>${selected.inspected}</b> 单</dd></dl><p class="callout">汇总只使用同批次有效验货单。未查到批号的同 SKU 退货会展示于排除清单。</p>
      ${quality ? `<a class="button" href="#trace?batch=${esc(selected.code)}">对本批次发起追因 →</a>` : ''}</div>` : empty('登记商品批次后，可以查看来源与质检覆盖。')}</aside></div>`;
  bindForm(root.querySelector('#batch-form'), async data => {
    const row = await request('/batches', 'POST', {...Object.fromEntries(data), delivered_qty: Number(data.get('delivered_qty'))});
    state.batches = await request('/batches');
    flash('已登记到货批次');
    window.location.hash = `batches?batch=${row.code}`;
  });
}
