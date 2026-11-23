import {request, state} from '../api.js';
import {empty, esc, option, pageTitle, pill} from '../ui.js';
import {action, number, text, wire} from './forms.js';

const money = new Intl.NumberFormat('zh-CN',{style:'currency',currency:'CNY'});
const currency = cents => money.format(cents / 100);
const status = {pending:'待供方确认',accepted:'已确认冲抵',rejected:'退回重议'};

export async function creditPage(root) {
  const {credits, eligible_shipments} = await request('/vendor-credits');
  const role = state.user.role;
  const form = role === 'quality' && eligible_shipments.length ? action('提出货款冲抵', [
    `<label>已签收运单<select name="shipment_id" required>${eligible_shipments.map(row => option(String(row.id),
      `${row.dispatch_ref} · ${row.supplier} · ${row.settled_qty} 件`)).join('')}</select></label>`,
    text('proposal_ref','冲抵编号'), number('unit_price_cents','单件结算价（分）',1),
    number('freight_cents','扣减运费（分）',0,100000000), text('note','结算依据',5),
  ], '提交冲抵单', '/vendor-credits/$shipment') : '';
  const rows = credits.map(row => `<article class="paper vendor-row" data-credit="${row.id}"><h2>${esc(row.proposal_ref)} ${pill(status[row.status])}</h2>
    <p>${esc(row.dispatch_ref)} · ${esc(row.batch_code)} · ${esc(row.supplier)}</p>
    <div class="vendor-metrics"><span>结算 ${row.units} × ${currency(row.unit_price_cents)}</span><span>扣减运费 ${currency(row.freight_cents)}</span><span>净冲抵 <b>${currency(row.net_cents)}</b></span></div>
    <p>${esc(row.note)}</p>${row.review_note ? `<p>${esc(row.review_note)} ${esc(row.acknowledged_ref ?? '')}</p>` : ''}
    ${role === 'supplier' && row.status === 'pending' ? action('供应商核对货款', [
      '<label>决定<select name="decision"><option value="accepted">确认冲抵</option><option value="rejected">退回重议</option></select></label>',
      '<label>确认凭证（确认时填写）<input name="acknowledged_ref"></label>', text('review_note','确认或退回依据',5),
    ], '提交供方裁定', `/vendor-credits/${row.shipment_id}/${row.id}/decision`) : ''}</article>`);
  root.innerHTML = pageTitle('退供结算','供方货款冲抵','按最终结算件数、约定单价和扣减运费生成应冲抵额。退回后的新方案另行确认。') +
    (form ? `<section class="paper vendor-row">${form}</section>` : '') + (rows.join('') || empty('当前没有货款冲抵记录'));
  wire(root, creditPage);
}
