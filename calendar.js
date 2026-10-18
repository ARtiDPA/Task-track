let calendarMonth=todayKey.slice(0,7),calendarDay=todayKey,calendarProfileId=null,eventId=null,eventEditing=false;
function calendarItems(from=calendarMonth+'-01',end=RitmoSchedule.monthly(calendarMonth+'-01',31)){
  const data=orgData();return [
    ...data.events.map(e=>({...e,source:'event',kind:'event'})),
    ...data.plans.filter(p=>p.status!=='cancelled').map(p=>({id:p.id,day:p.day,title:p.name,source:'plan',kind:p.kind,amount:p.amountKopecks,status:p.status,time:''})),
    ...data.debts.filter(d=>d.remainingKopecks>0&&d.dueDay).flatMap(d=>RitmoSchedule.debtOccurrences(d,end,from).map(o=>({id:d.id,day:o.day,title:d.name,source:'debt',kind:d.direction==='owe'?'expense':'income',amount:o.amount,time:'',monthly:Boolean(d.monthlyDay)})))
  ];
}
function renderCalendar(){
  if(calendarProfileId!==currentUser?.id){calendarProfileId=currentUser?.id;calendarMonth=todayKey.slice(0,7);calendarDay=todayKey;}
  const [year,month]=calendarMonth.split('-').map(Number),first=new Date(year,month-1,1),start=shiftDate(first,-((first.getDay()+6)%7));
  const items=calendarItems(dateKey(start),dateKey(shiftDate(start,41)));$('#calendar-month-title').textContent=first.toLocaleDateString('ru-RU',{month:'long',year:'numeric'});
  $('#calendar-grid').innerHTML=Array.from({length:42},(_,i)=>{
    const date=shiftDate(start,i),key=dateKey(date),daily=items.filter(e=>e.day===key);
    return `<button class="calendar-day ${key.slice(0,7)!==calendarMonth?'outside':''} ${key===todayKey?'today':''} ${key===calendarDay?'selected':''}" data-calendar-day="${key}" aria-pressed="${key===calendarDay}" aria-label="${orgDate(key)}, событий: ${daily.length}"><span>${date.getDate()}</span><div class="calendar-day-lines">${daily.slice(0,2).map(e=>`<small class="${e.source==='event'?'personal':e.kind==='income'?'income':'expense'}">${escapeHTML(e.title)}</small>`).join('')}${daily.length>2?`<small class="calendar-extra">ещё ${daily.length-2}</small>`:''}</div><div class="calendar-dots">${daily.slice(0,4).map(e=>`<i class="${e.source==='event'?'personal':e.kind}"></i>`).join('')}</div></button>`;
  }).join('');
  $('#calendar-selected-title').textContent=orgDate(calendarDay);
  const selected=items.filter(e=>e.day===calendarDay).sort((a,b)=>(a.time||'99:99').localeCompare(b.time||'99:99'));
  $('#calendar-day-count').textContent=`${selected.length} ${plural(selected.length,['событие','события','событий'])}`;
  $('#calendar-agenda').innerHTML=selected.length?selected.map(e=>`<article class="calendar-agenda-item ${e.source==='event'?'personal':e.kind}"><div class="calendar-agenda-symbol">${e.source==='event'?'✦':e.source==='debt'?'◎':e.kind==='income'?'↙':'↗'}</div><div class="calendar-agenda-copy"><strong>${escapeHTML(e.title)}</strong><small>${e.time||'В течение дня'} · ${e.source==='event'?'Событие':e.source==='debt'?(e.monthly?'Ежемесячный платёж по долгу':'Платёж по долгу'):e.status==='posted'?'Уже проведено':'Плановая операция'}</small>${e.amount?`<b class="${e.kind==='income'?'org-positive':'org-negative'}">${e.kind==='income'?'+':'−'}${formatMoney(e.amount)}</b>`:''}${e.note?`<p>${escapeHTML(e.note)}</p>`:''}</div><div class="calendar-item-actions">${e.source==='event'?`<button data-edit-event="${e.id}" aria-label="Изменить событие">${icon('edit')}</button><button data-delete-event="${e.id}" aria-label="Удалить событие">${icon('x')}</button>`:`<button data-calendar-jump="${e.source}" data-id="${e.id}" aria-label="Открыть в финансах">↗</button>`}</div></article>`).join(''):'<div class="org-empty calendar-empty"><span>✳</span><h3>День пока свободен</h3><p>Добавь встречу, важное дело или напоминание. Планы и даты платежей появятся здесь автоматически.</p></div>';
  const monthItems=items.filter(e=>e.day.startsWith(calendarMonth));$('#calendar-month-count').textContent=monthItems.length;
}
orgDialog('org-event-dialog','Важное найдёт свой день',`${orgField('Событие','<input id="event-title" maxlength="80" placeholder="Встреча, день рождения, важное дело…" required>')}<div class="org-fields">${orgField('Дата','<input id="event-day" type="date" min="1900-01-01" max="2100-12-31" required>')}${orgField('Время (необязательно)','<input id="event-time" type="time">')}</div>${orgField('Подробности','<textarea id="event-note" maxlength="500" rows="3" placeholder="Где встречаемся, что взять с собой…"></textarea>')}`,async()=>{
  const day=$('#event-day').value,result=await persist(eventEditing?'/api/organizer/events/'+eventId:'/api/organizer/events',eventEditing?'PATCH':'POST',{id:eventId,title:$('#event-title').value.trim(),day,time:$('#event-time').value,note:$('#event-note').value.trim()});
  if(result){calendarDay=day;calendarMonth=day.slice(0,7);renderCalendar();}return result;
});
function openEvent(id=null){if(!openOrgDialog('org-event-dialog'))return;const e=orgData().events.find(e=>e.id===id);eventId=id||crypto.randomUUID();eventEditing=Boolean(e);$('#event-title').value=e?.title||'';$('#event-day').value=e?.day||calendarDay;$('#event-time').value=e?.time||'';$('#event-note').value=e?.note||'';}
$('#calendar-add').addEventListener('click',()=>openEvent());$('#calendar-add-selected').addEventListener('click',()=>openEvent());
$('#calendar-grid').addEventListener('click',event=>{const b=event.target.closest('[data-calendar-day]');if(b){calendarDay=b.dataset.calendarDay;calendarMonth=calendarDay.slice(0,7);renderCalendar();}});
document.querySelectorAll('[data-calendar-shift]').forEach(b=>b.addEventListener('click',()=>{const [y,m]=calendarMonth.split('-').map(Number),next=new Date(y,m-1+Number(b.dataset.calendarShift),1);if(next.getFullYear()<1900||next.getFullYear()>2100)return;calendarDay=dateKey(next);calendarMonth=calendarDay.slice(0,7);renderCalendar();}));
$('#calendar-today').addEventListener('click',()=>{calendarDay=todayKey;calendarMonth=todayKey.slice(0,7);renderCalendar();});
$('#calendar-agenda').addEventListener('click',event=>{const b=event.target.closest('button');if(!b)return;if(b.dataset.editEvent)openEvent(b.dataset.editEvent);if(b.dataset.deleteEvent)orgAction('/api/organizer/events/'+b.dataset.deleteEvent,'DELETE',{},'Удалить событие из календаря?');if(b.dataset.calendarJump)jumpToMoney(b.dataset.calendarJump==='debt'?'debts':'planning',b.dataset.id);});
