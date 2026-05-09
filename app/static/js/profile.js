if (ensureLogin()) {
  bootstrapProfile();
}

async function bootstrapProfile() {
  const me = await apiRequest('/api/me');
  const nicknameInput = document.getElementById('nickname-input');
  const passwordInput = document.getElementById('password-input');
  const saveNicknameBtn = document.getElementById('save-nickname-btn');
  const savePasswordBtn = document.getElementById('save-password-btn');
  const accountFeedback = document.getElementById('account-feedback');
  const accountDisplayName = document.getElementById('account-display-name');
  const accountDisplayId = document.getElementById('account-display-id');

  const account = {
    playerUid: me.player_uid,
    nickname: me.nickname,
  };

  function renderAccount() {
    accountDisplayName.textContent = account.nickname;
    accountDisplayId.textContent = `账号：${account.playerUid}`;
    nicknameInput.value = account.nickname === account.playerUid ? '' : account.nickname;
  }

  async function saveNickname() {
    saveNicknameBtn.disabled = true;
    accountFeedback.textContent = '正在修改用户名...';
    try {
      const result = await apiRequest('/api/account/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nickname: nicknameInput.value }),
      });
      account.nickname = result.nickname;
      renderAccount();
      accountFeedback.textContent = `用户名已更新为 ${result.nickname}。`;
    } catch (error) {
      accountFeedback.textContent = error.message;
    } finally {
      saveNicknameBtn.disabled = false;
    }
  }

  async function savePassword() {
    savePasswordBtn.disabled = true;
    accountFeedback.textContent = '正在修改密码...';
    try {
      await apiRequest('/api/account/password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: passwordInput.value }),
      });
      passwordInput.value = '';
      accountFeedback.textContent = '密码修改成功，新密码立即生效。';
    } catch (error) {
      accountFeedback.textContent = error.message;
    } finally {
      savePasswordBtn.disabled = false;
    }
  }

  saveNicknameBtn.addEventListener('click', saveNickname);
  savePasswordBtn.addEventListener('click', savePassword);
  renderAccount();
}
