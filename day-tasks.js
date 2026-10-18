let taskDay=todayKey,taskMode='day',taskProfileId=null,taskEditId=null,taskDraftItems=[];
const taskData=()=>state.tasks||[];
const taskPriority={high:'Важное',normal:'Обычный',low:'Без спешки'};
$('#tasks-view').innerHTML=`<article class="task-hero"><div><span class="rel-kicker">ТВОЙ ДЕНЬ. ТВОЙ РИТМ.</span><h2>Освободи место в голове.</h2><p>Собери дела в одном месте. Задай дату — и задача уже в календаре.</p><div class="task-hero-buttons"><button class="button button-primary" id="task-new">＋ Новая задача</button><button id="task-open-calendar">Открыть день в календаре ↗</button></div></div><div class="task-progress-ring" id="task-progress-ring"><strong id="task-done-fraction">0 / 0</strong><span>сделано за день</span></div></article><div class="task-toolbar"><div class="task-mode-buttons"><button data-task-mode="day" class="selected">На день</button><button data-task-mode="inbox">Без даты <span id="task-inbox-count">0</span></button><button data-task-mode="overdue">Перенести <span id="task-overdue-count">0</span></button></div><input id="task-selected-day" type="date" min="1900-01-01" max="2100-12-31" aria-label="День планировщика"></div><div class="task-week" id="task-week"></div><div class="task-list-head"><div><h2 id="task-list-title"></h2><p id="task-list-caption"></p></div><button id="task-today">Сегодня</button></div><div class="task-search-row"><input id="task-search" type="search" placeholder="Найти задачу или заметку…" aria-label="Поиск задач"><label><input id="task-hide-done" type="checkbox">Скрыть выполненные</label></div><div id="task-list" class="task-list"></div><article class="task-inbox-tip"><span>✧</span><div><strong>Не всему нужна дата прямо сейчас.</strong><p>Сохраняй мысли в «Без даты», затем назначай день — задача появится в календаре без копирования.</p></div><button id="task-new-inbox">＋ В список без даты</button></article>`;
orgDialog('task-dialog','Место для важного',`${orgField('Задача','<input id="task-title" maxlength="120" required placeholder="Что хочется сделать?">')}${orgField('Подробности','<textarea id="task-note" rows="3" maxlength="3000" placeholder="Шаги, адрес, что взять с собой…"></textarea>')}<div class="org-fields">${orgField('День (пусто — в список без даты)','<input id="task-day" type="date" min="1900-01-01" max="2100-12-31">')}${orgField('Время','<input id="task-time" type="time">')}</div>${orgField('Приоритет','<select id="task-priority"><option value="normal">Обычный</option><option value="high">Важное</option><option value="low">Без спешки</option></select>')}<section class="task-checklist-editor"><h3>Подзадачи и чеклист</h3><div id="task-checklist-draft"></div><button type="button" id="task-checklist-add">＋ Добавить шаг</button></section><small>Планировщик и календарь показывают одну задачу: дата, время и отметки синхронизируются автоматически.</small>`,async()=>{
  const existing=taskData().find(t=>t.id===taskEditId),day=$('#task-day').value;
  const result=await persist('/api/tasks'+(existing?'/'+taskEditId:''),existing?'PATCH':'POST',{id:taskEditId,title:$('#task-title').value.trim(),note:$('#task-note').value.trim(),day,time:day?$('#task-time').value:'',priority:$('#task-priority').value,done:existing?.done||false,checklist:taskDraftItems.filter(i=>i.title.trim()).map(i=>({...i,title:i.title.trim()}))});
  if(result){taskDay=day||taskDay;taskMode=day?'day':'inbox';renderDayTasks();if(day&&view==='calendar'){calendarDay=day;calendarMonth=day.slice(0,7);renderCalendar();}}return result;
});
function openTask(id=null,day=taskDay){
  if(!openOrgDialog('task-dialog'))return;const t=taskData().find(t=>t.id===id);taskEditId=id||crypto.randomUUID();
  $('#task-title').value=t?.title||'';$('#task-note').value=t?.note||'';$('#task-day').value=t?t.day:day;$('#task-time').value=t?.time||'';$('#task-priority').value=t?.priority||'normal';syncTaskTime();taskDraftItems=(t?.checklist||[]).map(i=>({...i}));renderTaskDraft();
}
function syncTaskTime(){$('#task-time').disabled=!$('#task-day').value;if(!$('#task-day').value)$('#task-time').value='';}
$('#task-day').addEventListener('change',syncTaskTime);
function taskRow(t,compact=false){
  return `<article class="task-row ${t.done?'is-done':''} ${compact?'compact':''}" data-task-id="${t.id}"><button class="task-check" data-task-toggle="${t.id}" aria-pressed="${t.done}" aria-label="${t.done?'Вернуть':'Выполнить'} задачу ${escapeHTML(t.title)}">${t.done?icon('check'):''}</button><div class="task-row-copy"><strong>${escapeHTML(t.title)}</strong><div class="task-row-meta">${t.time?`<span>◷ ${t.time}</span>`:''}<span class="task-priority ${t.priority}">${taskPriority[t.priority]}</span>${!compact&&taskMode==='overdue'?`<span>${orgDate(t.day)}</span>`:''}</div>${t.note?`<p>${escapeHTML(t.note)}</p>`:''}${taskChecklist(t)}</div><div class="task-row-actions">${!compact&&!t.done?`<button data-task-focus="${t.id}" class="task-schedule">◎ Фокус</button>`:''}${!compact&&!t.done&&(taskMode==='inbox'||taskMode==='overdue')?`<button data-task-edit="${t.id}" class="task-schedule">Назначить день</button>`:''}<button data-task-edit="${t.id}" aria-label="Изменить задачу">${icon('edit')}</button><button data-task-delete="${t.id}" aria-label="Удалить задачу">${icon('x')}</button></div></article>`;
}
function renderDayTasks(){
  if(taskProfileId!==currentUser?.id){taskProfileId=currentUser?.id;taskDay=todayKey;taskMode='day';$('#task-search').value='';$('#task-hide-done').checked=false;}
  const data=taskData(),daily=data.filter(t=>t.day===taskDay),done=daily.filter(t=>t.done).length;
  $('#task-selected-day').value=taskDay;$('#task-selected-day').hidden=taskMode!=='day';$('#task-week').hidden=taskMode!=='day';$('#task-done-fraction').textContent=done+' / '+daily.length;
  $('#task-progress-ring').style.setProperty('--task-percent',(daily.length?done/daily.length*100:0)+'%');
  $('#task-inbox-count').textContent=data.filter(t=>!t.day&&!t.done).length;$('#task-overdue-count').textContent=data.filter(t=>t.day&&t.day<todayKey&&!t.done).length;
  document.querySelectorAll('[data-task-mode]').forEach(b=>{b.classList.toggle('selected',b.dataset.taskMode===taskMode);b.setAttribute('aria-pressed',b.dataset.taskMode===taskMode);});
  const start=new Date(taskDay+'T12:00:00');start.setDate(start.getDate()-((start.getDay()+6)%7));
  $('#task-week').innerHTML=Array.from({length:7},(_,i)=>{const d=shiftDate(start,i),key=dateKey(d),count=data.filter(t=>t.day===key&&!t.done).length;return `<button data-task-day="${key}" class="${key===taskDay?'selected':''}" aria-pressed="${key===taskDay}"><span>${dayNames[i]}</span><strong>${d.getDate()}</strong><small>${count?count+' '+plural(count,['дело','дела','дел']):'Свободно'}</small></button>`;}).join('');
  const query=$('#task-search').value.trim().toLocaleLowerCase('ru'),hideDone=$('#task-hide-done').checked;
  const entries=data.filter(t=>(taskMode==='day'?t.day===taskDay:taskMode==='inbox'?!t.day:t.day&&t.day<todayKey&&!t.done)&&(!hideDone||!t.done)&&(!query||(t.title+' '+t.note).toLocaleLowerCase('ru').includes(query))).sort((a,b)=>Number(a.done)-Number(b.done)||(a.time||'99:99').localeCompare(b.time||'99:99')||({high:0,normal:1,low:2}[a.priority]-{high:0,normal:1,low:2}[b.priority]));
  $('#task-list-title').textContent=taskMode==='day'?orgDate(taskDay):taskMode==='inbox'?'Идеи и дела без даты':'Дела, которым нужен новый день';
  $('#task-list-caption').textContent=taskMode==='day'?`${done} из ${daily.length} выполнено · все задачи этого дня видны в календаре`:taskMode==='inbox'?'Назначь дату, когда будешь готов.':'Прошедшие даты не сдвигаются сами: выбери удобный день.';
  $('#task-list').innerHTML=entries.length?entries.map(t=>taskRow(t)).join(''):`<div class="task-empty"><span>✦</span><h3>${query||hideDone?'Подходящих задач нет':taskMode==='day'?'День — чистый лист':taskMode==='inbox'?'Здесь можно выдохнуть':'Ничего не отложено'}</h3><p>${taskMode==='day'?'Добавь главное на этот день, остальное сложится.':'Добавь новую задачу или вернись к планам на сегодня.'}</p></div>`;
}
async function taskAction(path,method,data,question=''){
  if(!ready||saving||orgBusy||(question&&!confirm(question)))return;orgBusy=true;
  try{if(await persist(path,method,data))toast('План дня обновлён ✦');}finally{orgBusy=false;}
}
$('#task-new').addEventListener('click',()=>openTask(null,taskMode==='inbox'?'':taskDay));$('#task-new-inbox').addEventListener('click',()=>openTask(null,''));
$('#task-today').addEventListener('click',()=>{taskDay=todayKey;taskMode='day';renderDayTasks();});
$('#task-selected-day').addEventListener('change',e=>{if(e.target.value){taskDay=e.target.value;renderDayTasks();}});
$('#task-search').addEventListener('input',renderDayTasks);$('#task-hide-done').addEventListener('change',renderDayTasks);
$('#task-open-calendar').addEventListener('click',()=>{setView('calendar');calendarDay=taskDay;calendarMonth=taskDay.slice(0,7);renderCalendar();});
document.addEventListener('click',event=>{
  const b=event.target.closest('button');if(!b)return;
  if(b.dataset.taskMode){taskMode=b.dataset.taskMode;renderDayTasks();}
  if(b.dataset.taskDay){taskDay=b.dataset.taskDay;renderDayTasks();}
  if(b.dataset.taskFocus){const t=taskData().find(t=>t.id===b.dataset.taskFocus);if(t){setView('focus');if(!focusData().active)$('#focus-title').value=t.title;else toast('У тебя уже есть активная фокус-сессия.');}}
  if(b.dataset.taskEdit)openTask(b.dataset.taskEdit);
  if(b.dataset.taskToggle){const t=taskData().find(t=>t.id===b.dataset.taskToggle);if(t)taskAction('/api/tasks/'+t.id,'PATCH',{...t,done:!t.done});}
  if(b.dataset.taskDelete)taskAction('/api/tasks/'+b.dataset.taskDelete,'DELETE',{},'Удалить задачу из планировщика и календаря?');
});

function taskChecklist(t){
  const items=t.checklist||[];if(!items.length)return '';const done=items.filter(i=>i.done).length;
  return `<details class="task-checklist" ${items.length<=4?'open':''}><summary>${done} из ${items.length} шагов <span class="task-checklist-track"><i style="width:${done/items.length*100}%"></i></span></summary>${items.map(i=>`<button class="task-item ${i.done?'checked':''}" data-task-item="${i.id}" data-parent-task="${t.id}" role="checkbox" aria-checked="${i.done}"><span>${i.done?'✓':''}</span>${escapeHTML(i.title)}</button>`).join('')}</details>`;
}
function renderTaskDraft(){
  $('#task-checklist-draft').innerHTML=taskDraftItems.map((i,n)=>`<div class="task-draft-item"><input type="checkbox" data-draft-done="${n}" ${i.done?'checked':''} aria-label="Шаг выполнен"><input data-draft-title="${n}" value="${escapeHTML(i.title)}" maxlength="120" placeholder="Например, подготовить документы" aria-label="Название шага ${n+1}"><button type="button" data-draft-remove="${n}" aria-label="Удалить шаг">×</button></div>`).join('');$('#task-checklist-add').disabled=taskDraftItems.length>=100;
}
$('#task-checklist-add').addEventListener('click',()=>{if(taskDraftItems.length<100){taskDraftItems.push({id:crypto.randomUUID(),title:'',done:false});renderTaskDraft();$('#task-checklist-draft').querySelectorAll('[data-draft-title]')[taskDraftItems.length-1]?.focus();}});
$('#task-checklist-draft').addEventListener('input',e=>{if(e.target.dataset.draftTitle!==undefined)taskDraftItems[Number(e.target.dataset.draftTitle)].title=e.target.value;});
$('#task-checklist-draft').addEventListener('change',e=>{if(e.target.dataset.draftDone!==undefined)taskDraftItems[Number(e.target.dataset.draftDone)].done=e.target.checked;});
$('#task-checklist-draft').addEventListener('click',e=>{const b=e.target.closest('[data-draft-remove]');if(b){taskDraftItems.splice(Number(b.dataset.draftRemove),1);renderTaskDraft();}});
document.addEventListener('click',e=>{const b=e.target.closest('[data-task-item]');if(b){const t=taskData().find(t=>t.id===b.dataset.parentTask),i=t?.checklist.find(i=>i.id===b.dataset.taskItem);if(i)taskAction(`/api/tasks/${t.id}/items/${i.id}`,'PATCH',{done:!i.done});}});
