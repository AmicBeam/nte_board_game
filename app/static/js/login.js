const playerUidInput = document.getElementById('player-uid-input');
const codeInput = document.getElementById('code-input');
const loginBtn = document.getElementById('login-btn');
const loginFeedback = document.getElementById('login-feedback');

async function login() {
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
    try {
      const stateResponse = await fetch('/api/game/state', {
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
    window.location.href = catalog.saved_build ? '/home' : '/build';
  } catch (error) {
    loginFeedback.textContent = error.message;
  } finally {
    loginBtn.disabled = false;
  }
}

loginBtn.addEventListener('click', login);

if (window.NTE_IS_DEV_ENV === true) {
  playerUidInput.value = '10001';
  codeInput.value = '654321';
}
