import {state} from './api.js';

export const ROLE = {service: '售后客服', quality: '品控主管', supplier: '供应商'};
export const WORK = {assigned: '待接单', working: '整改中', verification: '待验证', closed: '已结案'};
export const FLAGS = {missing_batch: '缺商品批次', tag_conflict: '客诉标签互斥', uninspected: '待质检'};
export const RUN = {ready: '待复核', queued: '计算中', blocked: '样本不足', failed: '计算失败'};
export const DECISION = {pending: '待判断', confirmed: '已确认', dismissed: '已排除'};

export function esc(text) {
  return String(text ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'})[char]);
}

export function localDate() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

export const percent = ratio => `${(100 * ratio).toFixed(1)}%`;
export const nameOf = code => state.tags[code]?.name || code;
export const option = (value, label, selected) => `<option value="${esc(value)}" ${value === selected ? 'selected' : ''}>${esc(label)}</option>`;
export const pill = (label, tone = '') => `<span class="pill ${tone}">${esc(label)}</span>`;
export const empty = text => `<div class="empty">${esc(text)}</div>`;
export const pageTitle = (section, title, copy, action = '') => `<header class="page-title"><div><div class="eyebrow">${esc(section)}</div><h1>${esc(title)}</h1><p>${esc(copy)}</p></div>${action}</header>`;
export const batchOptions = selected => state.batches.map(b => option(b.code, `${b.code} · ${b.product}`, selected)).join('');
export const labelList = tags => tags.map(code => pill(nameOf(code))).join(' ');

export function flash(message, error = false) {
  const node = document.querySelector('#toast');
  node.textContent = message;
  node.className = error ? 'visible bad' : 'visible';
  clearTimeout(flash.timer);
  flash.timer = setTimeout(() => { node.className = ''; }, 4500);
}

export function bindForm(form, submit) {
  form?.addEventListener('submit', async event => {
    event.preventDefault();
    const button = event.submitter;
    if (button) button.disabled = true;
    const output = form.querySelector('[role="alert"]');
    if (output) output.textContent = '';
    try {
      await submit(new FormData(form));
    } catch (error) {
      if (output) output.textContent = error.message;
      else flash(error.message, true);
    } finally {
      if (button) button.disabled = false;
    }
  });
}

export const errorBox = '<p class="form-error" role="alert"></p>';
