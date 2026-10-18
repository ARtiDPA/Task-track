/* Access JWT lives only in memory. Refresh token is an HttpOnly cookie. */
globalThis.RitmoStorage = (() => {
  let token=null, refreshPromise=null, generation=0;
  async function raw(path, method='GET', body, access=null) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(path, {
        method,
        cache: 'no-store',
        credentials: 'same-origin',
        headers: {...(body === undefined ? {} : {'Content-Type': 'application/json'}), ...(access?{Authorization:'Bearer '+access}:{})},
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal
      });
      const data = await response.json();
      if (!response.ok) {
        const error=new Error(data.error || 'Не удалось сохранить изменения.');
        error.status=response.status;throw error;
      }
      return data;
    } catch (error) {
      if (error.name === 'AbortError' || error instanceof TypeError || error instanceof SyntaxError) {
        throw new Error('Нет соединения с базой. Повтори попытку — изменения ещё не сохранены.');
      }
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }
  function clear() {token=null;generation++;}
  async function refresh() {
    if(refreshPromise)return refreshPromise;
    const version=generation;
    refreshPromise=(async()=>{
      try {
        const data=await raw('/api/auth/refresh','POST',{});
        if(version!==generation)throw Object.assign(new Error('Сессия изменилась.'),{status:401});
        token=data.accessToken;return data;
      } catch(error) {
        if(error.status===401&&version===generation){clear();window.dispatchEvent(new Event('ritmo:unauthorized'));}
        throw error;
      } finally {refreshPromise=null;}
    })();
    return refreshPromise;
  }
  return Object.freeze({
    async request(path='/api/state',method='GET',body) {
      if(path.startsWith('/api/auth/'))return raw(path,method,body,token);
      if(!token)await refresh();
      try {return await raw(path,method,body,token);}
      catch(error) {
        if(error.status!==401)throw error;
        await refresh();
        return raw(path,method,body,token);
      }
    },
    async authenticate(mode,details) {
      const data=await raw('/api/auth/'+mode,'POST',details);
      generation++;token=data.accessToken;return data;
    },
    async logout() {await raw('/api/auth/logout','POST',{},token);clear();},
    clear,
    // Profile data is deliberately not cached in shared browser localStorage.
    cache() {}
  });
})();
