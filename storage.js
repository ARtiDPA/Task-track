/* All writes are individual API operations, never a replacement of the whole DB. */
globalThis.RitmoStorage = Object.freeze({
  async request(path = '/api/state', method = 'GET', body) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(path, {
        method,
        cache: 'no-store',
        headers: body === undefined ? {} : {'Content-Type': 'application/json'},
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Не удалось сохранить изменения.');
      if (!Array.isArray(data.habits)) throw new Error('Хранилище вернуло неверный ответ.');
      return data;
    } catch (error) {
      if (error.name === 'AbortError' || error instanceof TypeError || error instanceof SyntaxError) {
        throw new Error('Нет соединения с базой. Повтори попытку — изменения ещё не сохранены.');
      }
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  },
  cache(state) {
    try { localStorage.setItem('ritmo-v1', JSON.stringify(state)); } catch { /* SQLite is authoritative. */ }
  }
});
