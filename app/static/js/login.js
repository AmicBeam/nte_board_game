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
      headers: { 'Content-Type': 'application/json' },
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
    window.location.href = '/build';
  } catch (error) {
    loginFeedback.textContent = error.message;
  } finally {
    loginBtn.disabled = false;
  }
}

loginBtn.addEventListener('click', login);
playerUidInput.value = '10001';
codeInput.value = '654321';
