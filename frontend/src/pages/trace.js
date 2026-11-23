import {request, state} from '../api.js';
import {batchOptions, bindForm, DECISION, empty, errorBox, esc, FLAGS, flash, labelList, localDate, nameOf, pageTitle, percent, pill, RUN} from '../ui.js';

export async function tracePage(root, location) {
  const runs = await request('/traces');
  const run = runs.find(item => String(item.id) === location.get('run')) || runs[0];
  const result = run ? await request(`/traces/${run.id}`) : null;
  const selected = result?.rules.find(item => String(item.id) === location.get('rule')) || result?.rules[0];
  const quality = state.user.role === 'quality';
  const batch = location.get('batch') || result?.batch_code || 'HX-261107-A';
  const initial = state.batches.find(item => item.code === batch);
  const start = result?.batch_code === batch ? result.from_date : initial?.received_on ?? localDate();
  const end = result?.batch_code === batch ? result.through_date : localDate();
  root.innerHTML = `${pageTitle('证据分析', '组合追因', '在同一批次内查找反复同现的客诉标签与质检结论。')}
    ${quality ? `<form class="paper run-form" id="run-form"><label>商品批次<select name="batch_code" required>${batchOptions(batch)}</select></label><label>起始退货日<input name="from_date" type="date" value="${esc(start)}" required></label><label>截止退货日<input name="through_date" type="date" value="${esc(end)}" required></label><button>运行 FP-Growth</button>${errorBox}</form>` : ''}
    ${runs.length ? `<div class="run-history" aria-label="追因历史"><b>最近运行</b>${runs.slice(0, 8).map(item => `<a class="mono ${item.id === result.id ? 'active' : ''}" href="#trace?run=${item.id}">#${item.id} ${esc(item.batch_code)} · ${RUN[item.status]}</a>`).join('')}</div>` : ''}
    ${result?.coverage?.total !== undefined ? coverage(result) : ''}
    <div class="split trace-split"><section class="paper"><div class="section-head"><h2>待复核的证据组合</h2>${result ? `<span class="mono">${esc(result.batch_code)} / RUN ${result.id}</span>` : ''}${result?.status === 'failed' && quality ? '<button type="button" id="retry-run">按原受理票据重试</button>' : ''}</div>
    ${result?.rules.length ? `<p class="section-copy">按提升度排序。每行至少 3 张同现票据，提升度高于 1 才可提交根因确认。</p><div class="table-wrap"><table><thead><tr><th>客诉组合 → 验货结论</th><th>同现率</th><th>置信度</th><th>提升度</th></tr></thead><tbody>${result.rules.map(rule => `<tr class="${rule.id === selected.id ? 'chosen' : ''}"><td><a href="#trace?run=${result.id}&rule=${rule.id}">${esc(rule.symptoms.map(nameOf).join(' ＋ '))}</a><small>↳ ${esc(nameOf(rule.finding))} · ${DECISION[rule.decision]}</small></td><td class="mono">${percent(rule.support)}</td><td class="mono">${percent(rule.confidence)}</td><td><b class="mono lift">${rule.lift.toFixed(2)}×</b></td></tr>`).join('')}</tbody></table></div>` : empty(['queued', 'running'].includes(result?.status) ? '后台正在读取样本。计算完毕后可复核。' : result?.message || '选取有验货记录的批次及日期窗口，发起第一次追因。')}</section>
    <aside class="paper clipboard">${selected ? reviewCard(selected, quality) : `<div class="section-head"><h2>根因复核</h2></div>${empty('组合生成后，打开一行查看底单和质检结论。')}</aside>`}</div>`;
  bindForm(root.querySelector('#run-form'), async data => {
    const run = await request('/traces', 'POST', Object.fromEntries(data));
    flash('追因已提交后台计算');
    window.location.hash = `trace?run=${run.id}`;
  });
  const select = root.querySelector('#run-form select');
  select?.addEventListener('change', () => {
    const startDate = state.batches.find(item => item.code === select.value)?.received_on;
    if (startDate) root.querySelector('#run-form [name=from_date]').value = startDate;
  });
  bindForm(root.querySelector('#review-form'), async data => {
    const decision = data.get('decision');
    const payload = {decision, note: data.get('note')};
    if (decision === 'confirm') Object.assign(payload, {directive: data.get('directive'), due_on: data.get('due_on') || null});
    const review = await request(`/rules/${selected.id}/review`, 'POST', payload);
    flash(review.work ? `已生成供应商改进工单 #${review.work.id}` : '已排除该组合');
    await tracePage(root, location);
  });
  root.querySelector('#retry-run')?.addEventListener('click', async event => {
    event.target.disabled = true;
    try {
      await request(`/traces/${result.id}/retry`, 'POST');
      flash('已按原受理票据重新排队');
      await tracePage(root, location);
    } catch (error) {
      flash(error.message, true);
      event.target.disabled = false;
    }
  });
  let timer;
  if (['queued', 'running'].includes(result?.status)) {
    const activeHash = window.location.hash;
    timer = setTimeout(() => {
      if (activeHash === window.location.hash && root.isConnected) tracePage(root, location).catch(error => flash(error.message, true));
    }, 950);
  }
  return () => clearTimeout(timer);
}

function coverage(run) {
  const data = run.coverage;
  return `<section class="coverage"><div><span>有效验货单</span><b class="mono">${data.eligible}<small> / ${data.total}</small></b></div><div><span>缺商品批次</span><b class="mono">${data.missing_batch}</b></div><div><span>标签互斥</span><b class="mono">${data.tag_conflict}</b></div><div><span>待签质检</span><b class="mono">${data.uninspected}</b></div><details><summary>排除票据 (${data.excluded.length})</summary>${data.excluded.length ? `<ul>${data.excluded.map(row => `<li><a class="mono" href="#returns?ticket=${esc(row.ticket)}">${esc(row.ticket)}</a> · ${esc(row.flags.map(flag => FLAGS[flag]).join('、'))}</li>`).join('')}</ul>` : '<p>当前窗口未排除票据。</p>'}</details>${run.accepted ? `<details class="accepted"><summary>受理票据 (${run.accepted.length})</summary><ul>${run.accepted.map(row => `<li><a class="mono" href="#returns?ticket=${esc(row.ticket)}">${esc(row.ticket)}</a> · 提交时版本 v${row.revision}</li>`).join('')}</ul>` : ''}</section>`;
}

function reviewCard(rule, quality) {
  const reviewable = quality && rule.decision === 'pending';
  return `<div class="section-head"><h2>根因复核</h2>${pill(DECISION[rule.decision], rule.decision === 'confirmed' ? 'good' : '')}</div><div class="details">
    <div class="tags">${labelList(rule.symptoms)}</div><h3 class="finding">→ ${esc(nameOf(rule.finding))}</h3>
    <p class="callout">有该组合的 ${rule.symptom_count} 单中，${rule.matched_count} 单验出此结论。该结论在整个批次窗口的基线为 ${rule.finding_count} / ${rule.eligible_count} 单。</p>
    <details open><summary>查看原始验货票据 (${rule.evidence.length})</summary><div class="evidence">${rule.evidence.map(ticket => `<a class="mono" href="#returns?ticket=${esc(ticket)}">${esc(ticket)}</a>`).join('')}</div></details>
    ${rule.review_note ? `<p>${esc(rule.review_note)}</p>` : ''}${rule.work_id ? `<a class="button" href="#improvements?work=${rule.work_id}">打开改进工单 #${rule.work_id}</a>` : ''}</div>
    ${reviewable ? `<form class="form-stack" id="review-form"><label>处理结论<select name="decision"><option value="confirm" ${rule.lift <= 1 ? 'disabled' : ''}>确认并下发整改</option><option value="dismiss" ${rule.lift <= 1 ? 'selected' : ''}>排除该组合</option></select></label><label>复核依据<textarea name="note" placeholder="说明仓库复检发现与客诉为何一致" minlength="6" required></textarea></label>
      <label>整改要求<input name="directive" placeholder="例如复测压装工位，回传压装记录"></label><label>整改期限<input name="due_on" type="date" min="${localDate()}"></label>${errorBox}<button>提交复核</button></form>` : ''}`;
}
