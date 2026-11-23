import {request, state} from '../api.js';
import {empty, esc, option, pageTitle, pill} from '../ui.js';
import {action, number, text, wire} from './forms.js';

const status = {in_transit:'运输中', disputed:'签收短件', received:'签收可结算'};

export async function shipmentPage(root) {
  const {shipments, awaiting_dispatch} = await request('/vendor-shipments');
  const role = state.user.role;
  const form = role === 'quality' && awaiting_dispatch.length ? action('登记仓库出库', [
    `<label>退供流水<select name="disposition_id" required>${awaiting_dispatch.map(row => option(String(row.id),
      `${row.batch_code} · ${row.disposition_ref} · ${row.quantity} 件`)).join('')}</select></label>`,
    text('dispatch_ref','出库凭证'), text('carrier','承运商'), text('tracking','承运单号'),
  ], '提交退供运单', '/vendor-shipments') : '';
  const rows = shipments.map(row => {
    const base = `/vendor-shipments/${row.id}`;
    let next = '';
    if (role === 'supplier' && row.status === 'in_transit') next = action('供应商签收', [
      number('vendor_qty','实际收货件数',0,row.sent_qty), text('vendor_ref','收货凭证'), text('vendor_note','验收说明',5),
    ], '提交收货回执', `${base}/receipt`);
    if (role === 'quality' && row.status === 'disputed') next = action('核对短件', [
      number('settled_qty','裁定可结算件数',row.vendor_qty,row.sent_qty), text('resolution_ref','差异凭证'), text('resolution_note','裁定依据',5),
    ], '确定差异结算数', `${base}/resolution`);
    return `<article class="paper vendor-row" data-shipment="${row.id}"><h2>${esc(row.dispatch_ref)} ${pill(status[row.status])}</h2>
      <p>${esc(row.batch_code)} · ${esc(row.supplier)} · ${esc(row.carrier)} ${esc(row.tracking)}</p>
      <div class="vendor-metrics"><span>发出 <b>${row.sent_qty}</b></span><span>实收 <b>${row.vendor_qty ?? '—'}</b></span><span>可结算 <b>${row.settled_qty ?? '—'}</b></span></div>
      ${row.vendor_ref ? `<p>供应商回执 ${esc(row.vendor_ref)} · ${esc(row.vendor_note)}</p>` : ''}
      ${row.resolution_ref ? `<p>差异凭证 ${esc(row.resolution_ref)} · ${esc(row.resolution_note)}</p>` : ''}${next}</article>`;
  });
  root.innerHTML = pageTitle('退供履约','退供运单','根据已登记退供件数发货。签收短件须留承运证据并由品控裁定。') +
    (form ? `<section class="paper vendor-row">${form}</section>` : '') +
    (rows.join('') || empty('当前没有退供运单'));
  wire(root, shipmentPage);
}
