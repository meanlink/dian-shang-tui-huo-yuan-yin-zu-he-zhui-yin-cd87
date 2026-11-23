import {creditPage} from './supplier-returns/credit-page.js';
import {shipmentPage} from './supplier-returns/shipment-page.js';
import {referenceData, request, setToken, state} from './api.js';
import {bindForm, empty, errorBox, esc, ROLE} from './ui.js';
import {returnsPage} from './pages/returns.js';
import {batchesPage} from './pages/batches.js';
import {tracePage} from './pages/trace.js';
import {improvementsPage} from './pages/work.js';
import {holdsPage, reinspectionPage} from './pages/stock.js';

const app = document.querySelector('#app');
const pages = {
  returns: ['退货单', returnsPage], batches: ['商品批次', batchesPage],
  trace: ['组合追因', tracePage], improvements: ['改进工单', improvementsPage],
  holds: ['批次库存隔离', holdsPage], reinspection: ['整改复验抽检', reinspectionPage],
  shipments: ['退供运单', shipmentPage], credits: ['供方货款冲抵', creditPage],
};
const brand = '<a class="brand" href="#"><span class="mark" aria-hidden="true">青</span><span><b>青屿品控</b><small>退货追因</small></span></a>';
let pageCleanup;

function loginView() {
  pageCleanup?.();
  app.innerHTML = `<div class="login"><div class="login-editorial">${brand}<div class="login-copy"><span class="eyebrow">青屿自营 · 售后质量</span><h1>让每一项整改<br>都有退货证据。</h1><p>从客诉标签回查商品批号，通过仓库实物验货确认根因，跟进供应商整改直至结案。</p></div><div class="login-flow"><span>客诉登记</span><span>批次溯源</span><span>根因复核</span><span>验证结案</span></div></div>
    <div class="login-form-wrap"><form id="login" class="form-stack"><div class="eyebrow">员工与供应商入口</div><h2>登录工作台</h2><label>账号<input name="login" autocomplete="username" placeholder="输入工作账号" required></label><label>密码<input name="password" type="password" autocomplete="current-password" required></label>${errorBox}<button>登录 →</button>
    <details><summary>演示账号</summary><p>售后 <code>lin</code> · 品控 <code>zhou</code> · 海汐杯业 <code>haixi</code> · 新茂金工 <code>xinmao</code><br>共用密码 <code>returns2026</code></p></details></form></div></div>`;
  bindForm(app.querySelector('#login'), async data => {
    const result = await request('/sessions', 'POST', Object.fromEntries(data));
    setToken(result.token);
    state.user = result.staff;
    await referenceData();
    await render();
  });
}

async function render() {
  pageCleanup?.();
  if (!state.token || !state.user) return loginView();
  const role = state.user.role;
  const available = role === 'supplier' ? ['improvements', 'batches', 'holds', 'reinspection', 'shipments', 'credits']
    : Object.keys(pages).filter(page => role !== 'service' || page !== 'credits');
  const [path, search] = window.location.hash.slice(1).split('?');
  const active = available.includes(path) ? path : available[0];
  app.innerHTML = `<header class="masthead"><div class="masthead-inner">${brand}<nav aria-label="业务导航">${available.map(route => `<a href="#${route}" ${route === active ? 'aria-current="page"' : ''}>${pages[route][0]}</a>`).join('')}</nav><div class="identity"><span>${esc(state.user.display_name)}</span><small>${ROLE[role]}</small><button type="button" class="exit" id="signout">退出</button></div></div></header><main id="page" class="workspace" aria-busy="true">${empty('正在读取业务记录…')}</main>`;
  app.querySelector('#signout').onclick = signOut;
  const root = app.querySelector('#page');
  try {
    const cleanup = await pages[active][1](root, new URLSearchParams(search));
    if (root.isConnected) pageCleanup = cleanup;
    else cleanup?.();
  } catch (error) {
    root.innerHTML = `<div class="paper retry"><p role="alert">${esc(error.message)}</p><button>重新加载</button></div>`;
    root.querySelector('button').onclick = render;
  } finally {
    root.setAttribute('aria-busy', 'false');
  }
}

function signOut() {
  setToken(null);
  state.user = null;
  history.replaceState(null, '', window.location.pathname);
  loginView();
}

window.addEventListener('hashchange', render);
window.addEventListener('session-expired', signOut);
if (state.token) {
  try {
    state.user = await request('/session');
    await referenceData();
  } catch {
    signOut();
  }
}
await render();
