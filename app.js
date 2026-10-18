const icons = {
  heart:'<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>',
  wallet:'<rect x="3" y="5" width="18" height="15" rx="3"/><path d="M3 8V5l14-3v3m4 6h-6v6h6"/><circle cx="17" cy="14" r=".5"/>',
  dashboard:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  layers:'<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/>',
  chart:'<path d="M4 3v17h17M8 14l4-5 4 3 5-7"/>',
  award:'<circle cx="12" cy="8" r="5"/><path d="m8 12-2 9 6-3 6 3-2-9"/>',
  chevrons:'<path d="m8 8 4-4 4 4m-8 8 4 4 4-4"/>',
  sprout:'<path d="M12 21v-9M12 14C4 15 3 9 3 6c6-1 10 2 9 8ZM12 11c0-6 4-8 9-8 0 6-3 9-9 8Z"/>',
  sparkles:'<path d="m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4L12 3ZM20 2v4m-2-2h4"/>',
  bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  calendar:'<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M16 3v4M8 3v4M3 11h18"/>',
  'check-circle':'<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  flame:'<path d="M12 3c1 5 6 5 6 11a6 6 0 0 1-12 0c0-3 2-5 3-6 0 4 2 4 2 4s3-3 1-9Z"/>',
  trend:'<path d="m3 17 6-6 4 4 8-10M15 5h6v6"/>',
  'arrow-up-right':'<path d="M6 18 18 6M6 6h12v12"/>',
  'arrow-right':'<path d="M4 12h16m-6-6 6 6-6 6"/>',
  target:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  check:'<path d="m5 12 4 4L19 6"/>',
  x:'<path d="m6 6 12 12M6 18 18 6"/>',
  edit:'<path d="m15 4 5 5M4 20l5-1L21 7l-5-5L4 14v6Z"/>'
};
const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.sparkles}</svg>`;
document.querySelectorAll('[data-icon]').forEach(el => el.innerHTML = icon(el.dataset.icon));
const $ = selector => document.querySelector(selector);
let today = new Date(); today.setHours(0,0,0,0);
const dateKey = date => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
let todayKey = dateKey(today);
const shiftDate = (date, delta) => {const d = new Date(date); d.setDate(d.getDate()+delta); return d;};
const escapeHTML = value => String(value).replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
const colors = ['#9772db','#6aaa91','#ddac6e','#7c9ed0','#cf8ba5','#6bafb8'];
const emojis = RitmoEmojiCatalog.map(item=>item.emoji);
let emojiCategory='Все';
let ready = false, saving = false, stateRevision = 0;
let currentUser=null;
let state;
if (!state || !Array.isArray(state.habits)) {
  state = {habits:[
    {id:'reading',name:'Читать 20 минут',category:'Развитие',emoji:'📖',color:colors[0],logs:[]},
    {id:'water',name:'Пить достаточно воды',category:'Здоровье',emoji:'💧',color:colors[3],logs:[]},
    {id:'meditation',name:'10 минут для себя',category:'Осознанность',emoji:'🧘',color:colors[4],logs:[]},
    {id:'movement',name:'Двигаться каждый день',category:'Спорт',emoji:'🏃',color:colors[1],logs:[]},
    {id:'sleep',name:'Ложиться до 23:00',category:'Здоровье',emoji:'🌙',color:colors[2],logs:[]},
    {id:'journal',name:'Записать мысли',category:'Осознанность',emoji:'✍️',color:colors[5],logs:[]}
  ]};
}
state.habits = state.habits.filter(h => h && typeof h.id==='string' && typeof h.name==='string').map(h => {
  const logs=Array.isArray(h.logs)?h.logs:[],createdAt=RitmoMetrics.creationDate({...h,logs},todayKey);
  return {...h,createdAt,category:typeof h.category==='string'?h.category:'Другое',emoji:emojis.includes(h.emoji)?h.emoji:'🌿',color:colors.includes(h.color)?h.color:colors[0],logs:[...new Set(logs.filter(d=>typeof d==='string' && /^\d{4}-\d{2}-\d{2}$/.test(d) && d<=todayKey && d>=createdAt))]};
});
const starterHabits=state.habits.map(h=>({...h,logs:[]}));
let period='week', view='dashboard', selectedEmoji=emojis[0], selectedColor=colors[0], editingId=null, toastTimer;
function setSaveStatus(message, failed=false) {
  const label=$('.live-label');label.innerHTML='<i></i>'+escapeHTML(message);
  label.classList.toggle('save-error',failed);
}
function setSaving(value) {
  saving=value;
  $('#habit-list').inert=value;$('#habit-form').inert=value;
  $('#add-habit').disabled=value;$('#add-inline').disabled=value;
  if(value)setSaveStatus('Сохраняем…');
}
async function persist(path,method,body) {
  if(!ready||saving)return false;
  stateRevision++;
  setSaving(true);
  try {
    state=await RitmoStorage.request(path,method,body);
    RitmoStorage.cache(state);render();setSaveStatus('Сохранено в базе');
    return true;
  } catch(error) {
    setSaveStatus('Не сохранено',true);toast(error.message);
    return false;
  } finally {setSaving(false);}
}
async function connectStorage() {
  $('.app-shell').inert=true;
  $('#connection-panel').hidden=false;$('#retry-connection').hidden=true;
  $('#connection-title').textContent='Собираем твой ритм';
  $('#connection-description').textContent='Загружаем привычки и сохранённый прогресс.';
  $('#connection-symbol').classList.remove('connection-error');
  try {
    let remote=await RitmoStorage.request();
    if(!remote.initialized)remote=await RitmoStorage.request('/api/import','POST',{habits:starterHabits.map(h=>({...h,createdAt:todayKey,logs:[]}))});
    state=remote;currentUser=remote.user;RitmoStorage.cache(state);ready=true;render();
    setSaveStatus('Сохранено в базе');$('#connection-panel').hidden=true;$('.app-shell').inert=false;
  } catch(error) {
    if(error.status===401){await showAuth();return;}
    setSaveStatus('Нет соединения',true);
    $('#connection-title').textContent='Не удалось открыть хранилище';
    $('#connection-description').textContent='Проверь, запущено ли приложение, и повтори подключение. Сохранённые данные останутся в базе.';
    $('#connection-symbol').classList.add('connection-error');
    $('#retry-connection').hidden=false;
    $('#retry-connection').focus();
  }
}
$('#retry-connection').addEventListener('click',connectStorage);
async function refreshStorage() {
  if(!ready||saving)return;
  const revision=stateRevision;
  try {
    const remote=await RitmoStorage.request();
    if(saving||revision!==stateRevision)return;
    if(JSON.stringify(remote)!==JSON.stringify(state)){state=remote;RitmoStorage.cache(state);render();}
    setSaveStatus('Сохранено в базе');
  } catch {if(!saving)setSaveStatus('Нет соединения',true);}
}
let weekStart = shiftDate(today,-((today.getDay()+6)%7));
let week = Array.from({length:7},(_,i)=>shiftDate(weekStart,i));
const dayNames=['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];
function renderDates(){ $('#current-date').textContent = today.toLocaleDateString('ru-RU',{day:'numeric',month:'long',year:'numeric'});$('#activity-year').textContent=today.getFullYear();$('#week-days-label').innerHTML = week.map((d,i)=>`<span style="${dateKey(d)===todayKey?'color:var(--purple);font-weight:800':''}">${dayNames[i]}</span>`).join('');}
function streak(habit){let n=0,d=today;if(!habit.logs.includes(todayKey))d=shiftDate(d,-1);while(habit.logs.includes(dateKey(d))){n++;d=shiftDate(d,-1);}return n;}
function bestStreak(habit){let best=0,current=0,prev=null;habit.logs.slice().sort().forEach(key=>{const d=new Date(key+'T00:00:00');current=prev && dateKey(shiftDate(prev,1))===key?current+1:1;best=Math.max(best,current);prev=d;});return best;}
function totalForDay(date, habits=state.habits){const key=dateKey(date);return RitmoMetrics.activeOn(habits,key).filter(h=>h.logs.includes(key)).length;}
function percentage(date){return RitmoMetrics.rate(state.habits,[dateKey(date)]);}
function plural(n,forms){return forms[n%10===1&&n%100!==11?0:n%10>=2&&n%10<=4&&(n%100<12||n%100>14)?1:2];}
function toast(message){$('#toast-text').textContent=message;$('#toast').classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('visible'),3500);}
function render(){renderDates();renderHabits();renderStats();renderChart();renderActivityOptions();renderHeatmap();renderAchievements();if(typeof renderWater==='function')renderWater();if(typeof renderFinance==='function')renderFinance();if(typeof renderFocus==='function')renderFocus();if(typeof renderWishlist==='function')renderWishlist();if(typeof renderDayTasks==='function')renderDayTasks();if(typeof renderCalendar==='function')renderCalendar();if(typeof renderAccount==='function')renderAccount();if(typeof renderRelationships==='function')renderRelationships();}
function renderHabits(){
  $('#habit-count').textContent=state.habits.length;$('#habits-badge').textContent=state.habits.length;
  $('#habit-list').innerHTML=state.habits.length?state.habits.map((h,index)=>`<div class="habit-row" style="--habit-color:${h.color};animation-delay:${index*.035}s"><div class="habit-info"><span class="habit-emoji">${h.emoji}</span><div class="habit-detail"><div class="habit-name" title="${escapeHTML(h.name)}">${escapeHTML(h.name)}</div><span class="habit-category">${escapeHTML(h.category)}</span></div></div><div class="habit-week">${week.map((d,i)=>{const key=dateKey(d),done=h.logs.includes(key),future=d>today,notStarted=key<h.createdAt;return `<button class="day-check ${done?'done':''} ${key===todayKey?'today':''}" data-day="${dayNames[i]}" data-habit="${escapeHTML(h.id)}" data-date="${key}" ${future||notStarted?'disabled':''} aria-pressed="${done}" aria-label="${escapeHTML(h.name)}, ${d.toLocaleDateString('ru-RU')}${done?', выполнено':''}" title="${d.toLocaleDateString('ru-RU')}${future?' — ещё впереди':notStarted?' — до создания привычки':''}">${done?icon('check'):'<span>·</span>'}</button>`;}).join('')}</div><div class="habit-streak" title="Текущая серия">${icon('flame')}${streak(h)}</div><button class="habit-edit" data-edit="${escapeHTML(h.id)}" aria-label="Изменить привычку ${escapeHTML(h.name)}">${icon('edit')}</button></div>`).join(''):'<div class="empty-habits">Пока здесь чистый лист 🌱<br>Добавь первую привычку и начни свою историю.</div>';
}
function renderStats(){
  const count=state.habits.length,done=totalForDay(today),all=state.habits.reduce((sum,h)=>sum+h.logs.length,0);
  $('#today-done').textContent=done;$('#today-total').textContent=`/ ${count}`;$('#today-progress').style.width=`${count?done/count*100:0}%`;$('#today-percent').textContent=`${count?Math.round(done/count*100):0}% от цели`;
  $('#best-streak').textContent=Math.max(0,...state.habits.map(bestStreak));$('#total-done').textContent=all;
  const dates=periodDates().filter(d=>d<=today),pct=RitmoMetrics.rate(state.habits,dates.map(dateKey));
  $('#period-percent').textContent=pct;$('#period-trend').textContent=pct>=75?'Отличный ритм':pct>0?'Есть прогресс':'Новый старт';$('#chart-average').innerHTML=`${pct}<small>%</small>`;
  $('#chart-note').innerHTML=done===count&&count?'Сегодня все привычки выполнены.<br><strong>Ты заслуживаешь гордиться собой!</strong>':done>0?'Ты уже уделил время себе сегодня.<br><strong>Продолжай в своём ритме.</strong>':'Каждая отметка приближает тебя к цели.<br><strong>Начни с одной привычки сегодня.</strong>';
  $('#next-title').textContent=done===count&&count?'Сегодня ты молодец!':'Твоя следующая победа';$('#next-description').textContent=done===count&&count?'Все привычки выполнены. До завтра ♡':done?`Осталось ${count-done} ${plural(count-done,['маленький шаг','маленьких шага','маленьких шагов'])} сегодня`:'Выполни первую привычку сегодня';
}
function periodDates(){return period==='week'?week:Array.from({length:new Date(today.getFullYear(),today.getMonth()+1,0).getDate()},(_,i)=>new Date(today.getFullYear(),today.getMonth(),i+1));}
function renderChart(){
  const dates=periodDates(),w=360,h=165,left=28,right=12,top=12,bottom=25,plotH=h-top-bottom;
  const points=dates.map((d,i)=>({x:left+i*(w-left-right)/(dates.length-1),y:top+plotH*(1-percentage(d)/100),d})).filter(p=>p.d<=today && RitmoMetrics.activeOn(state.habits,dateKey(p.d)).length);
  const path=points.map((p,i)=>`${i?'L':'M'}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ');
  const area=points.length?`${path} L${points.at(-1).x},${top+plotH} L${left},${top+plotH} Z`:'';
  $('#progress-chart').innerHTML=`<svg class="chart-svg" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Процент выполнения привычек по дням"><defs><linearGradient id="area-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#b39adf" stop-opacity=".25"/><stop offset="100%" stop-color="#b39adf" stop-opacity=".02"/></linearGradient></defs>${[0,25,50,75,100].map(n=>{const y=top+plotH*(1-n/100);return `<line x1="${left}" y1="${y}" x2="${w-right}" y2="${y}" stroke="#f0ecf5" stroke-dasharray="3 4"/><text x="0" y="${y+3}">${n}%</text>`;}).join('')}<path d="${area}" fill="url(#area-fill)"/><path class="chart-line" d="${path}" fill="none" stroke="#a386d6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>${points.map(p=>`<circle cx="${p.x}" cy="${p.y}" r="3" fill="white" stroke="#a386d6" stroke-width="1.7"><title>${p.d.toLocaleDateString('ru-RU')}: ${percentage(p.d)}%</title></circle>`).join('')}${dates.map((d,i)=>period==='week'||i%5===0||i===dates.length-1?`<text x="${left+i*(w-left-right)/(dates.length-1)}" y="${h-3}" text-anchor="middle">${period==='week'?dayNames[i]:d.getDate()}</text>`:'').join('')}</svg>`;
}
function renderActivityOptions(){const selected=$('#activity-habit').value;$('#activity-habit').innerHTML='<option value="all">Все привычки</option>'+state.habits.map(h=>`<option value="${escapeHTML(h.id)}">${escapeHTML(h.name)}</option>`).join('');if(state.habits.some(h=>h.id===selected))$('#activity-habit').value=selected;}
function renderHeatmap(){
  const selected=$('#activity-habit').value,habits=selected==='all'?state.habits:state.habits.filter(h=>h.id===selected),start=shiftDate(today,-364),first=shiftDate(start,-((start.getDay()+6)%7)),columns=Math.ceil((Math.round((today-first)/86400000)+1)/7),months=[];let lastMonth=-1,total=0;
  const cells=Array.from({length:columns*7},(_,i)=>{const d=shiftDate(first,i),count=totalForDay(d,habits),blank=d<start||d>today;if(!blank)total+=count;if(i%7===0&&d.getMonth()!==lastMonth){months.push({name:d.toLocaleDateString('ru-RU',{month:'short'}).replace('.',''),pos:Math.floor(i/7)/columns*100});lastMonth=d.getMonth();}const level=count?Math.max(1,Math.ceil(count/Math.max(1,RitmoMetrics.activeOn(habits,dateKey(d)).length)*4)):0;return `<div class="heat-cell ${blank?'blank':''}" data-level="${level}" title="${d.toLocaleDateString('ru-RU',{day:'numeric',month:'long',year:'numeric'})}: ${count} ${plural(count,['выполнение','выполнения','выполнений'])}" ${blank?'aria-hidden="true"':''}></div>`;}).join('');
  $('#year-total').textContent=`${total} ${plural(total,['выполнение','выполнения','выполнений'])}`;
  $('#heatmap').innerHTML=`<div class="heatmap-layout"><div class="heatmap-labels"><span></span><span>Пн</span><span></span><span>Ср</span><span></span><span>Пт</span><span></span><span>Вс</span></div><div class="heatmap-main"><div class="heatmap-months">${months.map(m=>`<span style="left:${m.pos}%">${m.name}</span>`).join('')}</div><div class="heatmap-cells">${cells}</div></div></div>`;
  const scroll=$('.heatmap-scroll');scroll.scrollLeft=scroll.scrollWidth;
}
let achievementFilter='all';
function renderAchievements(){
  const items=RitmoAchievements.evaluate(state.habits,state.water),unlocked=items.filter(item=>item.unlocked).length;
  const filtered=items.filter(item=>achievementFilter==='all'||(achievementFilter==='unlocked'?item.unlocked:!item.unlocked));
  const heading=`<div class="achievement-overview"><div><h2>Коллекция твоих побед</h2><p>Получено <strong>${unlocked} из ${items.length}</strong> достижений. Прогресс считается по твоей истории.</p></div><div class="achievement-filters">${[['all','Все'],['unlocked','Получены'],['pending','Впереди']].map(([id,label])=>`<button data-achievement-filter="${id}" class="${achievementFilter===id?'selected':''}" aria-pressed="${achievementFilter===id}">${label}</button>`).join('')}</div></div>`;
  $('#achievements-view').innerHTML=heading+(filtered.length?filtered.map((item,index)=>`<article class="card achievement ${item.unlocked?'':'locked'}" data-achievement="${item.id}" style="animation-delay:${Math.min(index,8)*.025}s"><span class="achievement-category">${item.category}</span><span class="achievement-symbol">${item.emoji}</span><h2>${item.name}</h2><p>${item.description}</p><progress class="achievement-progress" value="${Math.min(item.value,item.target)}" max="${item.target}" aria-label="${item.name}: ${Math.min(item.value,item.target)} из ${item.target}"></progress><div class="achievement-numbers"><span>${Math.min(item.value,item.target)} / ${item.target} ${item.unit}</span><span>${item.percent}%</span></div><span class="achievement-status">${item.unlocked?'✓ Достижение получено':'Ещё впереди'}</span></article>`).join(''):'<div class="card achievement-empty">Здесь скоро появятся твои победы 🌱<br>Начни с одной привычки сегодня.</div>');
}
$('#achievements-view').addEventListener('click',event=>{
  const button=event.target.closest('[data-achievement-filter]');if(!button)return;
  achievementFilter=button.dataset.achievementFilter;renderAchievements();
  $(`[data-achievement-filter="${achievementFilter}"]`)?.focus();
});
function celebrate(){if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;const container=$('#confetti-container');for(let i=0;i<45;i++){const piece=document.createElement('i');piece.className='confetti';piece.style.cssText=`left:${Math.random()*100}%;background:${colors[i%colors.length]};--drift:${Math.random()*180-90}px;animation-delay:${Math.random()*.5}s;`;container.append(piece);setTimeout(()=>piece.remove(),3500);}}
$('#habit-list').addEventListener('click',async event=>{
  if(!ready||saving)return;
  const edit=event.target.closest('[data-edit]');
  if(edit){openModal(edit.dataset.edit);return;}
  const button=event.target.closest('[data-habit]');
  if(!button||button.disabled)return;
  const habit=state.habits.find(h=>h.id===button.dataset.habit);if(!habit)return;
  const key=button.dataset.date,wasDone=habit.logs.includes(key);
  const saved=await persist(`/api/habits/${encodeURIComponent(habit.id)}/days/${key}`,'PUT',{completed:!wasDone});
  if(!saved)return;
  const fresh=[...document.querySelectorAll('[data-habit]')].find(b=>b.dataset.habit===habit.id&&b.dataset.date===key);
  fresh?.focus({preventScroll:true});
  if(!wasDone){
    fresh?.classList.add('popped');
    if(totalForDay(today)===state.habits.length&&key===todayKey){celebrate();toast('Идеальный день! Все привычки выполнены ✨');}
    else toast('Маленький шаг — большая победа ✨');
  }
});
function setView(next){
  view=next;
  document.querySelectorAll('[data-view]').forEach(button=>{button.classList.toggle('active',button.dataset.view===next);button.setAttribute('aria-current',button.dataset.view===next?'page':'false');});
  const names={dashboard:'Обзор',habits:'Мои привычки',analytics:'Статистика',achievements:'Достижения',water:'Трекер воды',finance:'Финансы',calendar:'Календарь',relationships:'Личная жизнь',tasks:'План дня',wishlist:'Мой вишлист',focus:'Фокус'};
  $('#breadcrumb-current').textContent=names[next];
  const titles={dashboard:'Хороший день, чтобы стать лучше',habits:'Маленькие ритуалы, большие перемены',analytics:'Каждый шаг имеет значение',achievements:'Тебе есть чем гордиться',water:'Забота о себе начинается с глотка',finance:'Твои деньги. Ясная картина.',calendar:'У важных вещей есть свой день.',relationships:'Любовь живёт в деталях.',tasks:'Меньше хаоса. Больше ясности.',wishlist:'Твои желания имеют значение.',focus:'Верни внимание себе.'};
  $('#page-title').innerHTML=titles[next]+'<span class="heading-spark">✳</span>';
  $('#page-subtitle').textContent={dashboard:'Не нужно быть идеальным. Просто будь немного лучше, чем вчера.',habits:'Отмечай выполненное, редактируй привычки и находи свой ритм.',analytics:'Твой прогресс в цифрах. Замечай то, что уже получилось.',achievements:'Каждая победа начинается с простого решения продолжать.',water:'Найди свой водный ритм. Маленькая забота, каждый день.',finance:'Знай, сколько осталось. Понимай, куда уходит. Решай спокойно.',calendar:'События, планы и платежи — в одном спокойном пространстве.',relationships:'Помнить важное. Придумывать новое. Быть ближе.',tasks:'Выбери главное, назначь время и двигайся в своём ритме.',wishlist:'Всё, о чём мечтаешь, в одном личном пространстве.',focus:'Меньше ленты. Больше времени на то, что важно тебе.'}[next];
  $('#dashboard-view').hidden=['achievements','water','finance','calendar','relationships','tasks','wishlist','focus'].includes(next);
  $('#achievements-view').hidden=next!=='achievements';$('#water-view').hidden=next!=='water';$('#finance-view').hidden=next!=='finance';$('#calendar-view').hidden=next!=='calendar';$('#relationships-view').hidden=next!=='relationships';$('#tasks-view').hidden=next!=='tasks';$('#wishlist-view').hidden=next!=='wishlist';$('#focus-view').hidden=next!=='focus';
  document.body.classList.toggle('analytics-mode',next==='analytics');document.body.classList.toggle('habits-mode',next==='habits');
  $('.date-row').hidden=['achievements','water','finance','calendar','relationships','tasks','wishlist','focus'].includes(next);$('#add-habit').hidden=['water','finance','calendar','relationships','tasks','wishlist','focus'].includes(next);
  if(next==='focus'&&typeof renderFocus==='function')renderFocus();if(next==='wishlist'&&typeof renderWishlist==='function')renderWishlist();if(next==='tasks'&&typeof renderDayTasks==='function')renderDayTasks();if(next==='relationships'&&typeof renderRelationships==='function')renderRelationships();if(next==='finance'&&typeof renderFinance==='function')renderFinance();if(next==='calendar'&&typeof renderCalendar==='function')renderCalendar();
}

document.querySelectorAll('[data-view]').forEach(b=>{b.setAttribute('aria-label',b.textContent.replace(/NEW|6/g,'').trim());b.addEventListener('click',()=>setView(b.dataset.view));});
$('.brand').addEventListener('click',e=>{e.preventDefault();setView('dashboard');});
$('#all-habits').addEventListener('click',()=>setView('habits'));
document.querySelectorAll('[data-period]').forEach(b=>b.addEventListener('click',()=>{period=b.dataset.period;document.querySelectorAll('[data-period]').forEach(el=>{el.classList.toggle('selected',el===b);el.setAttribute('aria-pressed',el===b);});renderStats();renderChart();}));
$('#activity-habit').addEventListener('change',renderHeatmap);
function renderPickers(){
  const query=$('#emoji-search').value.trim().toLocaleLowerCase('ru');
  const filtered=RitmoEmojiCatalog.filter(item=>(emojiCategory==='Все'||item.category===emojiCategory)&&`${item.name} ${item.category} ${item.emoji}`.toLocaleLowerCase('ru').includes(query));
  $('#emoji-picker').innerHTML=filtered.length?filtered.map(item=>`<button type="button" class="emoji-option ${item.emoji===selectedEmoji?'selected':''}" data-emoji="${item.emoji}" aria-label="${item.name}" title="${item.name}" aria-pressed="${item.emoji===selectedEmoji}">${item.emoji}</button>`).join(''):'<p class="emoji-empty" role="status">Ничего не найдено. Попробуй другое слово.</p>';
  $('#emoji-categories').innerHTML=['Все',...RitmoEmojiGroups.map(group=>group.name)].map(name=>`<button type="button" data-emoji-category="${name}" class="emoji-category ${name===emojiCategory?'selected':''}" aria-pressed="${name===emojiCategory}">${name}</button>`).join('');
  $('#color-picker').innerHTML=colors.map((c,i)=>`<button type="button" class="color-option ${c===selectedColor?'selected':''}" style="--color:${c}" data-color="${c}" aria-label="${['Фиолетовый','Зелёный','Золотистый','Голубой','Розовый','Бирюзовый'][i]}" aria-pressed="${c===selectedColor}"></button>`).join('');
}
function openModal(id=null){
  if(!ready||saving)return;
  editingId=id;const habit=state.habits.find(h=>h.id===id);
  $('#habit-form').reset();$('#habit-name').setCustomValidity('');
  emojiCategory='Все';$('#emoji-search').value='';
  selectedEmoji=habit?.emoji||emojis[0];selectedColor=habit?.color||colors[state.habits.length%colors.length];
  $('#habit-name').value=habit?.name||'';$('#habit-category').value=habit?.category||'Здоровье';
  $('#modal-title').textContent=habit?'Твоя привычка, твои правила':'Большое начинается с малого';
  $('#save-habit').innerHTML=icon(habit?'check':'plus')+(habit?'Сохранить':'Добавить привычку');
  $('.delete-habit')?.remove();
  if(habit){
    const btn=document.createElement('button');btn.type='button';btn.className='delete-habit';btn.textContent='Удалить';
    btn.addEventListener('click',async ()=>{
      if(saving||!confirm(`Удалить привычку «${habit.name}» и её историю?`))return;
      const saved=await persist(`/api/habits/${encodeURIComponent(id)}`,'DELETE',{});
      if(saved){$('#habit-dialog').close();toast('Привычка удалена');}
    });
    $('.modal-actions').prepend(btn);
  }
  renderPickers();$('#habit-dialog').showModal();setTimeout(()=>$('#habit-name').focus(),50);
}
['#add-habit','#add-inline'].forEach(id=>$(id).addEventListener('click',()=>openModal()));
$('#add-habit').setAttribute('aria-label','Добавить новую привычку');
$('#habit-dialog').setAttribute('aria-labelledby','modal-title');
['#close-modal','#cancel-modal'].forEach(id=>$(id).addEventListener('click',()=>$('#habit-dialog').close()));
$('#habit-dialog').addEventListener('click',e=>{if(e.target===$('#habit-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
$('#emoji-picker').addEventListener('click',e=>{const b=e.target.closest('[data-emoji]');if(b){selectedEmoji=b.dataset.emoji;renderPickers();[...document.querySelectorAll('[data-emoji]')].find(el=>el.dataset.emoji===selectedEmoji)?.focus();}});
$('#emoji-search').addEventListener('input',renderPickers);
$('#emoji-categories').addEventListener('click',e=>{
  const button=e.target.closest('[data-emoji-category]');if(!button)return;
  emojiCategory=button.dataset.emojiCategory;renderPickers();
  [...document.querySelectorAll('[data-emoji-category]')].find(b=>b.dataset.emojiCategory===emojiCategory)?.focus();
});
$('#color-picker').addEventListener('click',e=>{const b=e.target.closest('[data-color]');if(b){selectedColor=b.dataset.color;renderPickers();[...document.querySelectorAll('[data-color]')].find(el=>el.dataset.color===selectedColor)?.focus();}});
$('#habit-form').addEventListener('submit',async e=>{
  e.preventDefault();if(!ready||saving)return;
  const name=$('#habit-name').value.trim();
  if(!name){$('#habit-name').setCustomValidity('Введи название привычки');$('#habit-name').reportValidity();return;}
  const details={name,category:$('#habit-category').value,emoji:selectedEmoji,color:selectedColor};
  const id=editingId;
  const payload=id?details:{id:globalThis.crypto?.randomUUID?.()||`habit-${Date.now()}-${Math.random().toString(36).slice(2)}`,...details};
  const saved=await persist(id?`/api/habits/${encodeURIComponent(id)}`:'/api/habits',id?'PATCH':'POST',payload);
  if(saved){$('#habit-dialog').close();toast(id?'Привычка обновлена':'Новая привычка — новое начало 🌱');}
});
$('#habit-name').addEventListener('input',()=>$('#habit-name').setCustomValidity(''));
$('#notification-button').addEventListener('click',()=>toast('Твой ритм важнее чужой скорости. Начни с одного шага 🌿'));
window.addEventListener('focus',refreshStorage);
document.addEventListener('visibilitychange',()=>{if(!document.hidden){const now=new Date();now.setHours(0,0,0,0);if(dateKey(now)!==todayKey){today=now;todayKey=dateKey(today);weekStart=shiftDate(today,-((today.getDay()+6)%7));week=Array.from({length:7},(_,i)=>shiftDate(weekStart,i));render();}refreshStorage();}});
render();
