(function () {
  const loginLink = document.querySelector('[data-login-link]');
  if (!loginLink) {
    return;
  }
  if (getToken()) {
    loginLink.href = '/profile';
    loginLink.textContent = '账号设置';
    return;
  }
  loginLink.href = loginUrlForCurrentPage();
}());
