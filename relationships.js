const relKinds={note:{label:'О ней',single:'Заметка',emoji:'✎',add:'Добавить заметку',hint:'Любимые цветы, вкус кофе, размеры, мечты и всё, что хочется запомнить.'},gift:{label:'Подарки',single:'Подарок',emoji:'🎁',add:'Идея подарка',hint:'Сохраняй желания, цены и ссылки. Выбирай подарок под повод и бюджет.'},date:{label:'Свидания',single:'Свидание',emoji:'🥂',add:'Идея свидания',hint:'Ваш список «однажды». От домашнего вечера до маленького путешествия.'},milestone:{label:'Важные даты',single:'Важная дата',emoji:'♡',add:'Важная дата'},care:{label:'Забота',single:'Знак внимания',emoji:'☀',add:'Знак внимания',hint:'Забрать с работы, оставить записку, приготовить любимый завтрак. Маленькое тоже важно.'},memory:{label:'Воспоминания',single:'Воспоминание',emoji:'📷',add:'Сохранить момент',hint:'Место для ваших историй: куда сходили, над чем смеялись, что хочется повторить.'}};
const relQuestions=['Что на этой неделе помогло тебе почувствовать мою поддержку?','Какой наш день ты хотела бы повторить?','Что мы давно хотим попробовать вместе?','Как я могу сделать твою следующую неделю легче?','Что сейчас приносит тебе больше всего радости?','Какая маленькая традиция могла бы стать нашей?','О чём тебе хочется поговорить, но пока не было времени?','Как ты любишь отдыхать после сложного дня?'];
let relTab='note',relProfileId=null,relEditId=null,relEditKind='note',relQuestionIndex=0,relSelectedDay=todayKey,relMonth=todayKey.slice(0,7);
const relData=()=>state.relationships||{partnerName:'',togetherDay:'',entries:[]};
const relEntry=id=>relData().entries.find(e=>e.id===id);
const relDiff=(a,b)=>Math.round((Date.parse(a+'T12:00:00Z')-Date.parse(b+'T12:00:00Z'))/86400000);
const relEsc=escapeHTML;
async function relAction(path,method,data,question=''){
  if(!ready||saving||orgBusy||(question&&!confirm(question)))return false;
  orgBusy=true;
  try{const result=await persist(path,method,data);if(result)toast('Сохранено в твоей истории ♡');return result;}
  finally{orgBusy=false;}
}
function relOccurrences(entry,from,end){
  if(!entry.day)return [];
  if(!entry.yearly)return entry.day>=from&&entry.day<=end?[{...entry,occurrenceDay:entry.day}]:[];
  const result=[],anchor=Number(entry.day.slice(8));
  for(let year=Math.max(Number(entry.day.slice(0,4)),Number(from.slice(0,4)));year<=Number(end.slice(0,4));year++){
    const day=RitmoSchedule.monthly(year+entry.day.slice(4),anchor);
    if(day>=from&&day<=end&&day>=entry.day)result.push({...entry,occurrenceDay:day});
  }return result;
}
function relCalendarItems(from,end){
  const data=relData(),entries=data.entries.filter(e=>e.kind!=='note');
  if(data.togetherDay)entries.push({id:'together-anniversary',kind:'milestone',title:'Наша годовщина',body:'День, с которого началась ваша история.',day:data.togetherDay,yearly:true,done:false,priceKopecks:null,time:'',automatic:true});
  return entries.flatMap(e=>relOccurrences(e,from,end)).sort((a,b)=>a.occurrenceDay.localeCompare(b.occurrenceDay)||(a.time||'99:99').localeCompare(b.time||'99:99'));
}

$('#relationships-view').innerHTML=`
  <article class="rel-hero"><div class="rel-hero-copy"><span class="rel-kicker">ВАША МАЛЕНЬКАЯ ВСЕЛЕННАЯ</span><h2 id="rel-hero-title">Быть рядом.<br>Замечать больше.</h2><p>Не забывать её любимое. Находить время для вас.<br>Собирать моменты, к которым хочется вернуться.</p><button id="rel-profile-open">Настроить вашу историю ${icon('arrow-up-right')}</button></div><div class="rel-hero-art" aria-hidden="true"><div class="rel-orbit one"></div><div class="rel-orbit two"></div><span class="rel-art-star">✦</span><span class="rel-art-heart">♡</span><span class="rel-art-small">✧</span></div><div class="rel-together"><span>ВАША ИСТОРИЯ</span><strong id="rel-together-count">♡</strong><small id="rel-together-label">У каждой любви своё начало</small></div></article>
  <div class="rel-stats"><article><span>Ближайший повод</span><strong id="rel-next-title">Пока чистый лист</strong><small id="rel-next-day">Добавь важную дату</small></article><article><span>Идей для неё</span><strong id="rel-gifts-count">0</strong><small>Подарки, которые ждут своего момента</small></article><article><span>Время вдвоём</span><strong id="rel-dates-count">0</strong><small>Свиданий в вашей истории</small></article></div>
  <div class="rel-tabs" role="group" aria-label="Разделы личной жизни">${['note','gift','date','planner','care','memory'].map(k=>`<button data-rel-tab="${k}" aria-pressed="${k==='note'}" class="${k==='note'?'selected':''}">${k==='planner'?'◷ Планировщик':relKinds[k].label}</button>`).join('')}</div>
  <div id="rel-library"><div class="rel-section-head"><div><h2 id="rel-section-title"></h2><p id="rel-section-hint"></p></div><button class="button button-primary rel-main-add" id="rel-add">＋ Добавить</button></div><div class="rel-library-tools"><input id="rel-search" type="search" placeholder="Найти по названию, деталям, месту…" aria-label="Поиск записей личной жизни"><select id="rel-status-filter" aria-label="Статус идей"><option value="all">Все записи</option><option value="ideas">Без даты</option><option value="planned">Запланировано</option><option value="done">Выполнено</option></select><label id="rel-budget-filter-label">До <input id="rel-budget-filter" inputmode="decimal" placeholder="любая сумма" aria-label="Бюджет для поиска идей"> ₽</label></div><p id="rel-library-summary"></p><div id="rel-cards" class="rel-cards"></div></div>
  <div id="rel-planner" hidden><div class="rel-section-head"><div><h2>Время для вас двоих</h2><p>Ваш отдельный календарь. Свидания, подарки и поводы — в одном ритме.</p></div><button class="button button-primary" data-rel-new="milestone">＋ Важная дата</button></div><div class="rel-planner-layout"><article class="card rel-month-card"><div class="rel-month-toolbar"><h3 id="rel-month-title"></h3><div><button data-rel-month-shift="-1" aria-label="Предыдущий месяц личного календаря">←</button><button id="rel-calendar-today">Сегодня</button><button data-rel-month-shift="1" aria-label="Следующий месяц личного календаря">→</button></div></div><div class="calendar-weekdays"><span>ПН</span><span>ВТ</span><span>СР</span><span>ЧТ</span><span>ПТ</span><span>СБ</span><span>ВС</span></div><div class="calendar-grid rel-calendar-grid" id="rel-calendar-grid"></div><div class="rel-calendar-legend"><span>♡ Важная дата</span><span>🥂 Свидание</span><span>🎁 Подарок</span><span>☀ Забота</span></div><p id="rel-month-budget" class="rel-month-budget"></p></article><article class="card rel-day-card"><div class="rel-day-heading"><span class="rel-kicker">ПЛАН НА ДЕНЬ</span><h3 id="rel-day-title"></h3><p id="rel-day-budget"></p></div><div class="rel-day-add"><button data-rel-new="date">＋ Свидание</button><button data-rel-new="gift">＋ Подарок</button><button data-rel-new="care">＋ Забота</button><button data-rel-new="milestone">＋ Повод</button></div><div id="rel-day-agenda"></div></article></div><article class="card rel-upcoming-card"><div class="rel-section-head"><div><h3>Не упустить важное</h3><p>Ближайшие 30 дней и ежегодные поводы</p></div></div><div id="rel-upcoming"></div></article><div class="rel-section-head"><div><h3>Все важные даты</h3><p>Годовщины и дни рождения можно повторять каждый год.</p></div></div><div id="rel-milestones" class="rel-cards"></div></div>
  <div class="rel-extra-grid"><article class="rel-conversation"><span class="rel-kicker">РАЗГОВОР НА ДВОИХ</span><h3>Чуть ближе, чем вчера</h3><p id="rel-question"></p><div><button id="rel-next-question">Другой вопрос ↻</button><button id="rel-save-question">Записать ответ ✎</button></div><small>Выбери спокойный момент и просто послушай ответ.</small></article><article class="rel-surprise"><span class="rel-kicker">ВЕЧЕР БЕЗ «НЕ ЗНАЮ»</span><h3>Пусть решит случай</h3><p id="rel-surprise-text">Выберем случайную идею из твоего списка свиданий с учётом указанного бюджета.</p><label>Бюджет до, ₽ <input id="rel-surprise-budget" inputmode="decimal" placeholder="Без ограничения"></label><div><button id="rel-surprise-pick">✦ Выбрать свидание</button><button id="rel-surprise-plan" hidden>Запланировать →</button></div></article></div>`;

orgDialog('rel-profile-dialog','Ваша история',`${orgField('Как её зовут','<input id="rel-partner-name" maxlength="60" placeholder="Имя или ваше ласковое обращение">')}${orgField('С какого дня вы вместе','<input id="rel-together-day" type="date" min="1900-01-01" max="2100-12-31">')}<small>Покажем дни вместе и вашу годовщину в личном календаре. Все записи доступны только в твоём профиле.</small>`,async()=>persist('/api/relationships/profile','PUT',{partnerName:$('#rel-partner-name').value.trim(),togetherDay:$('#rel-together-day').value}));
$('#rel-profile-open').addEventListener('click',()=>{if(openOrgDialog('rel-profile-dialog')){$('#rel-partner-name').value=relData().partnerName;$('#rel-together-day').value=relData().togetherDay;}});

orgDialog('rel-entry-dialog','Сохранить важное',`
  ${orgField('Название','<input id="rel-entry-title" maxlength="100" required placeholder="То, что хочется запомнить">')}
  ${orgField('Раздел / теги','<input id="rel-entry-category" maxlength="60" list="rel-category-options" placeholder="Например: цветы, вкусное, мечты…"><datalist id="rel-category-options"></datalist>')}
  ${orgField('Подробности','<textarea id="rel-entry-body" rows="5" maxlength="6000" placeholder="Детали, предпочтения, почему это ей понравится…"></textarea>')}
  <div id="rel-entry-money-field">${orgField('Цена / бюджет, ₽ (можно оставить пустым)',orgInput('rel-entry-price','Неизвестно'))}</div>
  <div id="rel-entry-place-field">${orgField('Место / магазин','<input id="rel-entry-place" maxlength="180" placeholder="Куда пойдём или где купить">')}${orgField('Ссылка','<input id="rel-entry-url" type="url" maxlength="1000" placeholder="https://…">')}</div>
  <div id="rel-entry-date-fields" class="org-fields">${orgField('Дата','<input id="rel-entry-day" type="date" min="1900-01-01" max="2100-12-31">')}${orgField('Время (необязательно)','<input id="rel-entry-time" type="time">')}</div>
  <label class="org-check" id="rel-entry-yearly-label"><input id="rel-entry-yearly" type="checkbox">Повторять каждый год</label>
  <label class="org-check"><input id="rel-entry-pin" type="checkbox">♡ Закрепить в начале списка</label>
  <p id="rel-entry-caption" class="rel-form-caption"></p>`,async()=>{
    const day=$('#rel-entry-day').value,existing=relEntry(relEditId);
    const result=await persist('/api/relationships/entries'+(existing?'/'+relEditId:''),existing?'PATCH':'POST',{id:relEditId,kind:relEditKind,title:$('#rel-entry-title').value.trim(),body:$('#rel-entry-body').value.trim(),category:$('#rel-entry-category').value.trim(),priceKopecks:['gift','date'].includes(relEditKind)&&$('#rel-entry-price').value.trim()?orgAmount($('#rel-entry-price').value):null,location:$('#rel-entry-place').value.trim(),url:$('#rel-entry-url').value.trim(),day:relEditKind==='note'?'':day,time:relEditKind==='note'?'':$('#rel-entry-time').value,yearly:relEditKind==='milestone'&&$('#rel-entry-yearly').checked,pinned:$('#rel-entry-pin').checked,done:existing?.done||false});
    if(result&&day&&relTab==='planner'){
      const saved=relEntry(relEditId),upcoming=saved?.yearly?relOccurrences(saved,todayKey,dateKey(shiftDate(today,366)))[0]:null;
      relSelectedDay=upcoming?.occurrenceDay||day;relMonth=relSelectedDay.slice(0,7);renderRelPlanner();
    }return result;
  });
function openRelEntry(kind='note',id=null,day='',preset={}){
  if(!openOrgDialog('rel-entry-dialog'))return;
  const entry=relEntry(id);relEditId=id||crypto.randomUUID();relEditKind=entry?.kind||kind;
  const k=relEditKind,source=entry||preset;
  $('#rel-entry-dialog-title').textContent=(entry?'Изменить: ':'')+relKinds[k].single;
  $('#rel-entry-title').value=source.title||'';$('#rel-entry-body').value=source.body||'';$('#rel-entry-category').value=source.category||'';
  $('#rel-entry-price').value=source.priceKopecks!=null?orgMoneyInput(source.priceKopecks):'';$('#rel-entry-place').value=source.location||'';$('#rel-entry-url').value=source.url||'';
  $('#rel-entry-day').value=source.day||day||(k==='memory'?todayKey:'');$('#rel-entry-time').value=source.time||'';$('#rel-entry-pin').checked=Boolean(source.pinned);$('#rel-entry-yearly').checked=entry?Boolean(entry.yearly):k==='milestone';
  $('#rel-entry-money-field').hidden=!['gift','date'].includes(k);$('#rel-entry-place-field').hidden=!['gift','date','memory'].includes(k);
  $('#rel-entry-date-fields').hidden=k==='note';$('#rel-entry-day').required=['milestone','memory'].includes(k);$('#rel-entry-yearly-label').hidden=k!=='milestone';
  $('#rel-entry-caption').textContent=['gift','date'].includes(k)?'Без даты это идея. С датой — план в вашем отдельном календаре. Цена служит ориентиром: фактический баланс не меняется.':k==='milestone'?'Укажи исходную дату. Ежегодный повод появится в каждом следующем году. 29 февраля в обычный год отмечается 28 февраля.':'Сохраняй своими словами. Это пространство доступно только тебе.';
  const categories={note:['Любит','Не любит','Цветы','Еда и напитки','Размеры','Мечты','Важное'],gift:['На день рождения','Без повода','Ручная работа','Впечатления'],date:['Дома','Прогулка','Вкусное','Культура','Приключение'],care:['Поддержка','Сюрприз','Помощь','Наша традиция'],memory:['Первый раз','Путешествие','Наш день'],milestone:['День рождения','Годовщина','Важный день']}[k];
  $('#rel-category-options').innerHTML=categories.map(c=>`<option value="${c}"></option>`).join('');
}
function setRelTab(tab){relTab=tab;$('#rel-search').value='';$('#rel-status-filter').value='all';$('#rel-budget-filter').value='';renderRelationships();}
function renderRelationships(){
  if(relProfileId!==currentUser?.id){relProfileId=currentUser?.id;relTab='note';relMonth=todayKey.slice(0,7);relSelectedDay=todayKey;relSurpriseId=null;relQuestionIndex=0;$('#rel-search').value='';$('#rel-budget-filter').value='';$('#rel-status-filter').value='all';$('#rel-surprise-budget').value='';$('#rel-surprise-text').textContent='Выберем случайную идею из твоего списка свиданий с учётом указанного бюджета.';$('#rel-surprise-plan').hidden=true;}
  const data=relData(),start=data.togetherDay,days=start?relDiff(todayKey,start):0;
  $('#rel-hero-title').textContent=data.partnerName?data.partnerName+'. Ваша маленькая вселенная.':'Быть рядом. Замечать больше.';
  $('#rel-together-count').textContent=start?Math.abs(days)+(days>=0?1:0):'♡';$('#rel-together-label').textContent=start?(days>=0?plural(days+1,['день вместе','дня вместе','дней вместе']):'дней до начала вашей истории'):'У каждой любви своё начало';
  const upcoming=relCalendarItems(todayKey,dateKey(shiftDate(today,366))).filter(e=>!e.done),next=upcoming[0];
  $('#rel-next-title').textContent=next?.title||'Пока чистый лист';$('#rel-next-day').textContent=next?`${orgDate(next.occurrenceDay)} · ${relDiff(next.occurrenceDay,todayKey)===0?'сегодня':'через '+relDiff(next.occurrenceDay,todayKey)+' дн.'}`:'Добавь важную дату или запланируй свидание';
  $('#rel-gifts-count').textContent=data.entries.filter(e=>e.kind==='gift'&&!e.done).length;$('#rel-dates-count').textContent=data.entries.filter(e=>e.kind==='date'&&e.done).length;
  document.querySelectorAll('[data-rel-tab]').forEach(b=>{b.classList.toggle('selected',b.dataset.relTab===relTab);b.setAttribute('aria-pressed',b.dataset.relTab===relTab);});
  $('#rel-library').hidden=relTab==='planner';$('#rel-planner').hidden=relTab!=='planner';
  $('#rel-question').textContent=relQuestions[relQuestionIndex];
  if(relTab==='planner')renderRelPlanner();else{
    $('#rel-section-title').textContent=relKinds[relTab].label;$('#rel-section-hint').textContent=relKinds[relTab].hint;$('#rel-add').textContent='＋ '+relKinds[relTab].add;
    $('#rel-status-filter').hidden=['note','memory'].includes(relTab);$('#rel-budget-filter-label').hidden=!['gift','date'].includes(relTab);renderRelCards();
  }
}
function relCard(entry){
  const k=entry.kind,action={gift:'Подарил',date:'Сходили',care:'Сделано'},status=entry.done?({gift:'Подарено',date:'Были здесь',care:'Сделано',memory:'Ваша история'}[k]||'Сохранено'):entry.day?'Запланировано':'Идея';
  return `<article class="card rel-entry rel-kind-${k} ${entry.done?'rel-done':''}" id="rel-entry-${entry.id}"><div class="rel-entry-top"><span class="rel-entry-symbol">${relKinds[k].emoji}</span><span class="rel-entry-tag">${relEsc(entry.category||relKinds[k].single)}</span><button data-rel-pin="${entry.id}" class="rel-pin ${entry.pinned?'pinned':''}" aria-label="${entry.pinned?'Открепить':'Закрепить'} запись" aria-pressed="${entry.pinned}">♡</button></div><h3>${relEsc(entry.title)}</h3>${entry.body?`<p class="rel-entry-body">${relEsc(entry.body)}</p>`:''}${entry.location?`<p class="rel-entry-place">⌖ ${relEsc(entry.location)}</p>`:''}${['gift','date'].includes(k)?`<strong class="rel-entry-price">${entry.priceKopecks===null?'Цена пока неизвестна':formatMoney(entry.priceKopecks)}</strong>`:''}<div class="rel-entry-meta">${entry.day?`<span>◷ ${orgDate(entry.day)}${entry.time?' · '+entry.time:''}${entry.yearly?' · каждый год':''}</span>`:''}${['gift','date','care'].includes(k)?`<span class="rel-status ${entry.done?'done':''}">${status}</span>`:''}</div><div class="rel-entry-actions">${action[k]?`<button class="rel-primary" data-rel-done="${entry.id}">${entry.done?'↶ Вернуть в планы':'✓ '+action[k]}</button>`:''}${!entry.done&&['gift','date','care'].includes(k)?`<button data-rel-schedule="${entry.id}">◷ Запланировать</button>`:''}${entry.url?`<a href="${relEsc(entry.url)}" target="_blank" rel="noopener noreferrer">Ссылка ↗</a>`:''}<button data-rel-edit="${entry.id}" aria-label="Изменить запись">${icon('edit')}</button><button data-rel-delete="${entry.id}" aria-label="Удалить запись">${icon('x')}</button></div></article>`;
}
function renderRelCards(){
  const query=$('#rel-search').value.trim().toLocaleLowerCase('ru'),status=$('#rel-status-filter').value,budgetValue=$('#rel-budget-filter').value.trim();let budget=null;
  try{if(budgetValue)budget=orgAmount(budgetValue);}catch{$('#rel-library-summary').textContent='Проверь сумму бюджета.';return;}
  const all=relData().entries.filter(e=>e.kind===relTab),entries=all.filter(e=>(!query||[e.title,e.body,e.category,e.location].join(' ').toLocaleLowerCase('ru').includes(query))&&(['note','memory'].includes(relTab)||status==='all'||status==='done'&&e.done||status==='planned'&&!e.done&&e.day||status==='ideas'&&!e.done&&!e.day)&&(!['gift','date'].includes(relTab)||budget===null||e.priceKopecks!==null&&e.priceKopecks<=budget));
  $('#rel-library-summary').textContent=`${entries.length} ${plural(entries.length,['запись','записи','записей'])}${budget!==null?' · только с известной ценой до '+formatMoney(budget):''}`;
  $('#rel-cards').innerHTML=entries.length?entries.map(relCard).join(''):`<div class="rel-empty"><span>${relKinds[relTab].emoji}</span><h3>${all.length?'Пока ничего не нашлось':'Здесь будет ваша история'}</h3><p>${all.length?'Попробуй другой запрос или бюджет.':relKinds[relTab].hint}</p>${!all.length?`<button class="button" data-rel-new="${relTab}">＋ ${relKinds[relTab].add}</button>`:''}</div>`;
}
function relBudgetCaption(items){
  const spending=items.filter(e=>['gift','date'].includes(e.kind)&&!e.done),sum=spending.reduce((s,e)=>s+(e.priceKopecks||0),0),unknown=spending.filter(e=>e.priceKopecks===null).length;
  return `Бюджет планов: ${formatMoney(sum)}${unknown?' · ещё '+unknown+' без цены':''}`;
}
function renderRelPlanner(){
  const [y,m]=relMonth.split('-').map(Number),first=new Date(y,m-1,1),start=shiftDate(first,-((first.getDay()+6)%7)),end=shiftDate(start,41);
  const items=relCalendarItems(dateKey(start),dateKey(end));
  $('#rel-month-title').textContent=first.toLocaleDateString('ru-RU',{month:'long',year:'numeric'});
  $('#rel-calendar-grid').innerHTML=Array.from({length:42},(_,i)=>{
    const date=shiftDate(start,i),day=dateKey(date),daily=items.filter(e=>e.occurrenceDay===day);
    return `<button class="calendar-day ${day.slice(0,7)!==relMonth?'outside':''} ${day===todayKey?'today':''} ${day===relSelectedDay?'selected':''}" data-rel-day="${day}" aria-pressed="${day===relSelectedDay}" aria-label="${orgDate(day)}, планов: ${daily.length}"><span>${date.getDate()}</span><div class="calendar-day-lines">${daily.slice(0,2).map(e=>`<small class="rel-calendar-label ${e.done?'rel-calendar-done':''}">${relKinds[e.kind].emoji} ${relEsc(e.title)}</small>`).join('')}${daily.length>2?`<small class="calendar-extra">ещё ${daily.length-2}</small>`:''}</div><div class="calendar-dots">${daily.slice(0,4).map(()=>'<i class="rel-calendar-dot"></i>').join('')}</div></button>`;
  }).join('');
  const selected=items.filter(e=>e.occurrenceDay===relSelectedDay);
  $('#rel-day-title').textContent=orgDate(relSelectedDay);$('#rel-day-budget').textContent=relBudgetCaption(selected);$('#rel-month-budget').textContent=relBudgetCaption(items.filter(e=>e.occurrenceDay.startsWith(relMonth)))+' за месяц. Суммы не списываются из финансов.';
  $('#rel-day-agenda').innerHTML=selected.length?selected.map(relAgendaItem).join(''):'<div class="rel-day-empty"><span>♡</span><h3>Оставьте время друг для друга</h3><p>Добавь план на этот день или выбери идею из своих списков.</p><button data-rel-open-ideas>Выбрать свидание →</button></div>';
  const upcoming=relCalendarItems(todayKey,dateKey(shiftDate(today,30))).filter(e=>!e.done);
  $('#rel-upcoming').innerHTML=upcoming.length?upcoming.map(relAgendaItem).join(''):'<p class="rel-muted">Ближайшие 30 дней свободны. Самое время придумать что-то вместе.</p>';
  const milestones=relData().entries.filter(e=>e.kind==='milestone');$('#rel-milestones').innerHTML=milestones.length?milestones.map(relCard).join(''):'<p class="rel-muted">Добавь день рождения, годовщину или другой важный повод.</p>';
}
function relAgendaItem(e){
  return `<div class="rel-agenda-item"><span class="rel-agenda-symbol">${relKinds[e.kind].emoji}</span><div><strong>${relEsc(e.title)}</strong><small>${orgDate(e.occurrenceDay)}${e.time?' · '+e.time:''}${e.done?' · выполнено':e.yearly?' · каждый год':''}</small>${e.location?`<small>⌖ ${relEsc(e.location)}</small>`:''}${e.priceKopecks!=null?`<b>${formatMoney(e.priceKopecks)}</b>`:''}</div>${e.automatic?'<button data-rel-profile-edit aria-label="Настроить годовщину">↗</button>':`<button data-rel-edit="${e.id}" aria-label="Изменить план">${icon('edit')}</button>${['gift','date','care'].includes(e.kind)?`<button data-rel-done="${e.id}" aria-label="${e.done?'Вернуть в планы':'Отметить выполненным'}">${e.done?'↶':'✓'}</button>`:''}`}</div>`;
}

let relSurpriseId=null;
$('#rel-add').addEventListener('click',()=>openRelEntry(relTab));
$('#rel-search').addEventListener('input',renderRelCards);$('#rel-status-filter').addEventListener('change',renderRelCards);$('#rel-budget-filter').addEventListener('input',renderRelCards);
$('#rel-next-question').addEventListener('click',()=>{relQuestionIndex=(relQuestionIndex+1)%relQuestions.length;$('#rel-question').textContent=relQuestions[relQuestionIndex];});
$('#rel-save-question').addEventListener('click',()=>openRelEntry('note',null,'',{title:relQuestions[relQuestionIndex],category:'Разговор на двоих',body:'Её ответ:\n\nЧто я хочу запомнить:\n'}));
$('#rel-surprise-pick').addEventListener('click',()=>{
  let budget=null;try{if($('#rel-surprise-budget').value.trim())budget=orgAmount($('#rel-surprise-budget').value);}catch(e){toast(e.message);return;}
  let ideas=relData().entries.filter(e=>e.kind==='date'&&!e.done&&!e.day&&(budget===null||e.priceKopecks!==null&&e.priceKopecks<=budget));
  if(ideas.length>1)ideas=ideas.filter(e=>e.id!==relSurpriseId);
  if(!ideas.length){relSurpriseId=null;$('#rel-surprise-text').textContent='Подходящих идей без даты пока нет. Добавь свидание в список или измени бюджет.';$('#rel-surprise-plan').hidden=true;return;}
  const choice=ideas[Math.floor(Math.random()*ideas.length)];relSurpriseId=choice.id;$('#rel-surprise-text').textContent=choice.title+(choice.location?' · '+choice.location:'')+(choice.priceKopecks!==null?' · '+formatMoney(choice.priceKopecks):'');$('#rel-surprise-plan').hidden=false;
});
$('#rel-surprise-plan').addEventListener('click',()=>{const entry=relEntry(relSurpriseId);if(entry)openRelEntry(entry.kind,entry.id,relSelectedDay);});
$('#rel-calendar-today').addEventListener('click',()=>{relSelectedDay=todayKey;relMonth=todayKey.slice(0,7);renderRelPlanner();});
$('#relationships-view').addEventListener('click',async event=>{
  const b=event.target.closest('button');if(!b)return;
  if(b.dataset.relTab)setRelTab(b.dataset.relTab);
  if(b.dataset.relNew)openRelEntry(b.dataset.relNew,null,relTab==='planner'?relSelectedDay:'');
  if(b.hasAttribute('data-rel-open-ideas'))setRelTab('date');
  if(b.hasAttribute('data-rel-profile-edit'))$('#rel-profile-open').click();
  if(b.dataset.relDay){relSelectedDay=b.dataset.relDay;relMonth=relSelectedDay.slice(0,7);renderRelPlanner();}
  if(b.dataset.relMonthShift){const [y,m]=relMonth.split('-').map(Number),d=new Date(y,m-1+Number(b.dataset.relMonthShift),1);if(d.getFullYear()>=1900&&d.getFullYear()<=2100){relSelectedDay=dateKey(d);relMonth=relSelectedDay.slice(0,7);renderRelPlanner();}}
  if(b.dataset.relEdit){const e=relEntry(b.dataset.relEdit);if(e)openRelEntry(e.kind,e.id);}
  if(b.dataset.relSchedule){const e=relEntry(b.dataset.relSchedule);if(e)openRelEntry(e.kind,e.id,relSelectedDay);}
  if(b.dataset.relPin){const e=relEntry(b.dataset.relPin);if(e)await relAction('/api/relationships/entries/'+e.id,'PATCH',{...e,pinned:!e.pinned});}
  if(b.dataset.relDone){const e=relEntry(b.dataset.relDone);if(e)await relAction('/api/relationships/entries/'+e.id,'PATCH',{...e,done:!e.done,day:e.day||todayKey});}
  if(b.dataset.relDelete)await relAction('/api/relationships/entries/'+b.dataset.relDelete,'DELETE',{},'Удалить эту запись из личной жизни?');
});
