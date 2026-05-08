function getToken() {
  return window.localStorage.getItem('nte_token') || '';
}

function setToken(token) {
  window.localStorage.setItem('nte_token', token);
}

function clearToken() {
  window.localStorage.removeItem('nte_token');
}

async function apiRequest(url, options = {}) {
  const headers = Object.assign({}, options.headers || {});
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(url, Object.assign({}, options, { headers }));
  const payload = await response.json();
  if (!response.ok || payload.error) {
    throw new Error(payload.error || '请求失败');
  }
  return payload;
}

function ensureLogin() {
  if (!getToken()) {
    window.location.href = '/login';
    return false;
  }
  return true;
}
