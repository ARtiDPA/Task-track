let authMode='register',authBusy=false;
function setAuthMode(mode){
  authMode=mode;
  document.querySelectorAll('[data-auth-mode]').forEach(button=>{
    button.classList.toggle('selected',button.dataset.authMode===mode);
    button.setAttribute('aria-pressed',button.dataset.authMode===mode);
  });
  $('#auth-name-field').hidden=mode!=='register';
  $('#auth-name').required=mode==='register';
  $('#auth-password').autocomplete=mode==='register'?'new-password':'current-password';
  $('#auth-password').minLength=mode==='register'?10:1;
  $('#auth-submit').textContent=mode==='register'?'Создать мой профиль →':'Войти в свой ритм →';
  $('#auth-form-title').textContent=mode==='register'?'Твоя новая глава':'С возвращением';
  $('#auth-error').textContent='';
  $('#legacy-field').hidden=mode!=='register'||!$('#legacy-field').dataset.available;
}
async function showAuth(){
  ready=false;stateRevision++;currentUser=null;state={habits:[]};render();
  document.querySelectorAll('.workspace-avatar,.profile-avatar,.top-avatar').forEach(el=>el.textContent='Я');
  $('#profile-button strong').textContent='Личный профиль';$('#profile-button small').textContent='Твой путь к лучшей версии';
  $('#account-name').textContent='Мой профиль';$('#account-email').textContent='';
  document.querySelectorAll('dialog[open]').forEach(dialog=>dialog.close());
  $('#connection-panel').hidden=true;$('#auth-screen').hidden=false;
  $('.app-shell').inert=true;document.body.classList.add('auth-open');
  setView('dashboard');
  try {
    const data=await RitmoStorage.request('/api/auth/bootstrap');
    $('#legacy-field').dataset.available=data.legacyAvailable?'yes':'';
    $('#legacy-field').hidden=authMode!=='register'||!data.legacyAvailable;
  }catch {/* Login still offers a retry and explains service errors. */}
}
function renderAccount(){
  if(!currentUser)return;
  const initial=Array.from(currentUser.name)[0]?.toLocaleUpperCase('ru')||'Я';
  document.querySelectorAll('.workspace-avatar,.profile-avatar,.top-avatar').forEach(el=>el.textContent=initial);
  $('#profile-button strong').textContent=currentUser.name;
  $('#profile-button small').textContent='Личный профиль';
  $('#account-name').textContent=currentUser.name;$('#account-email').textContent=currentUser.email;
}
document.querySelectorAll('[data-auth-mode]').forEach(button=>button.addEventListener('click',()=>setAuthMode(button.dataset.authMode)));
$('#auth-form').addEventListener('submit',async event=>{
  event.preventDefault();if(authBusy)return;
  authBusy=true;$('#auth-submit').disabled=true;$('#auth-error').textContent='';
  const details={email:$('#auth-email').value.trim(),password:$('#auth-password').value};
  if(authMode==='register'){details.name=$('#auth-name').value.trim();details.importLegacy=$('#auth-import-legacy').checked;}
  try {
    await RitmoStorage.authenticate(authMode,details);
    $('#auth-password').value='';$('#auth-screen').hidden=true;document.body.classList.remove('auth-open');
    await connectStorage();
  }catch(error){$('#auth-error').textContent=error.message;}
  finally {authBusy=false;$('#auth-submit').disabled=false;}
});
$('#profile-button').addEventListener('click',()=>$('#account-dialog').showModal());
$('.top-avatar').setAttribute('role','button');$('.top-avatar').tabIndex=0;$('.top-avatar').setAttribute('aria-label','Мой профиль');
$('.top-avatar').addEventListener('click',()=>$('#account-dialog').showModal());
$('.top-avatar').addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();$('#account-dialog').showModal();}});
$('#close-account').addEventListener('click',()=>$('#account-dialog').close());
$('#logout-button').addEventListener('click',async()=>{
  if(saving)return;$('#logout-button').disabled=true;
  try{await RitmoStorage.logout();$('#account-dialog').close();$('#auth-error').textContent='';await showAuth();setAuthMode('login');}
  catch(error){toast(error.message);}
  finally{$('#logout-button').disabled=false;}
});
window.addEventListener('ritmo:unauthorized',showAuth);
setAuthMode('register');

connectStorage();
