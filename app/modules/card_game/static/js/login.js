const playerUidInput = document.getElementById('player-uid-input');
const codeInput = document.getElementById('code-input');
const loginBtn = document.getElementById('login-btn');
const loginFeedback = document.getElementById('login-feedback');
const loginForm = document.getElementById('login-form');

function safeLoginRedirectTarget() {
  const params = new URLSearchParams(window.location.search);
  const target = params.get('next') || window.localStorage.getItem('nte_login_redirect') || '';
  if (!isSafeLoginTarget(target)) {
    return '';
  }
  const url = new URL(target, window.location.origin);
  return `${url.pathname}${url.search}${url.hash}`;
}

async function login(event) {
  event?.preventDefault();
  loginBtn.disabled = true;
  loginFeedback.textContent = '登录中...';
  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Log-Id': nextLogId() },
      body: JSON.stringify({
        player_uid: playerUidInput.value.trim(),
        code: codeInput.value.trim(),
      }),
    });
    const payload = await response.json();
    if (!response.ok || payload.error) {
      throw new Error(payload.error || '登录失败');
    }
    window.localStorage.setItem('nte_token', payload.token);
    loginFeedback.textContent = `登录成功，欢迎 ${payload.player.nickname}。`;
    const redirectTarget = safeLoginRedirectTarget();
    if (redirectTarget) {
      window.localStorage.removeItem('nte_login_redirect');
      window.location.href = redirectTarget;
      return;
    }
    try {
      const stateResponse = await fetch('/api/game/state?optional=1', {
        headers: { Authorization: `Bearer ${payload.token}`, 'X-Log-Id': nextLogId() },
      });
      const statePayload = await stateResponse.json();
      if (stateResponse.ok && statePayload.status === 'playing') {
        window.location.href = '/table';
        return;
      }
    } catch (stateError) {
      // 登录后的流向判断失败时继续按构筑状态兜底。
    }
    const catalogResponse = await fetch('/api/catalog', {
      headers: { Authorization: `Bearer ${payload.token}`, 'X-Log-Id': nextLogId() },
    });
    const catalog = await catalogResponse.json();
    if (!catalogResponse.ok || catalog.error) {
      throw new Error(catalog.error || '读取构筑失败');
    }
    window.location.href = catalog.saved_build ? '/card-game' : '/build';
  } catch (error) {
    loginFeedback.textContent = error.message;
  } finally {
    loginBtn.disabled = false;
  }
}

loginForm.addEventListener('submit', login);

if (window.NTE_IS_DEV_ENV === true) {
  playerUidInput.value = '10001';
  codeInput.value = '654321';
}
