// static/js/main.js
// Helpers: attach JWT automatically if present
(function() {
  const token = localStorage.getItem('token');
  if (!token) return;
  const origFetch = window.fetch;
  window.fetch = (input, init = {}) => {
    init.headers = init.headers || {};
    if (!init.headers['Authorization']) init.headers['Authorization'] = `Bearer ${token}`;
    return origFetch(input, init);
  };
})();