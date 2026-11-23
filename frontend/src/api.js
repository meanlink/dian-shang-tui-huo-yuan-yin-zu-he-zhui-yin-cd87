const sessionKey = 'qingyu-return-session';
export const state = {
  token: sessionStorage.getItem(sessionKey),
  user: null,
  tags: {},
  batches: [],
};

export function setToken(token) {
  state.token = token;
  if (token) sessionStorage.setItem(sessionKey, token);
  else sessionStorage.removeItem(sessionKey);
}

export async function request(path, method = 'GET', data) {
  const headers = {'Accept': 'application/json'};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (data !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(`/api${path}`, {method, headers, body: data === undefined ? undefined : JSON.stringify(data)});
  const result = await response.json();
  if (response.status === 401 && path !== '/sessions') {
    setToken(null);
    window.dispatchEvent(new Event('session-expired'));
  }
  if (!response.ok) throw new Error(result.detail || `请求失败（${response.status}）`);
  return result;
}

export async function referenceData() {
  const [tags, batches] = await Promise.all([request('/tags'), request('/batches')]);
  state.tags = Object.fromEntries(tags.map(tag => [tag.code, tag]));
  state.batches = batches;
}
