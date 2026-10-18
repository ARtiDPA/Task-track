let financeSection='overview',organizerProfileId=null,orgBusy=false;
const orgData=()=>state.organizer||{savings:[],debts:[],plans:[],events:[],reservedKopecks:0};
const orgDate=day=>day?new Date(day+'T12:00:00').toLocaleDateString('ru-RU',{day:'numeric',month:'long',year:'numeric'}):'Без даты';
const orgAmount=value=>RitmoFinanceMath.parseAmount(String(value||'0'));
const orgMoneyInput=value=>(value/100).toFixed(2).replace('.',',');
function orgField(label,input){const id=input.match(/\bid="([^"]+)"/);return `<div class="org-field"><label${id?' for="'+id[1]+'"':''}>${label}</label>${input}</div>`;}
function orgInput(id,placeholder='',extra=''){return `<input id="${id}" inputmode="decimal" placeholder="${placeholder}" ${extra}>`;}
function orgDialog(id,title,html,submit,caption='Сохранить →'){
  const dialog=document.createElement('dialog');dialog.id=id;dialog.className='org-dialog';dialog.setAttribute('aria-labelledby',id+'-title');
  dialog.innerHTML=`<form><div class="modal-heading"><span class="modal-spark">✦</span><button type="button" class="icon-button" aria-label="Закрыть">×</button></div><h2 id="${id}-title">${title}</h2>${html}<p class="org-form-error" role="alert"></p><button type="submit" class="button button-primary org-submit">${caption}</button></form>`;
  document.body.append(dialog);dialog.querySelector('.icon-button').addEventListener('click',()=>dialog.close());
  dialog.querySelector('form').addEventListener('submit',async event=>{
    event.preventDefault();if(!ready||saving||orgBusy)return;
    const button=dialog.querySelector('[type=submit]'),error=dialog.querySelector('.org-form-error');
    orgBusy=true;button.disabled=true;error.textContent='';
    try{if(await submit()){dialog.close();toast('Сохранено в твоём профиле ✨');}else error.textContent='Не удалось сохранить. Проверь сообщение и повтори попытку.';}
    catch(e){error.textContent=e.message;}finally{orgBusy=false;button.disabled=false;}
  });return dialog;
}
function openOrgDialog(id){
  if(!ready||saving||orgBusy)return false;
  const dialog=$('#'+id);dialog.querySelector('form').reset();dialog.querySelector('.org-form-error').textContent='';dialog.showModal();return true;
}
async function orgAction(path,method='POST',data={},question=''){
  if(!ready||saving||orgBusy||(question&&!confirm(question)))return false;
  orgBusy=true;try{const result=await persist(path,method,data);if(result)toast('Готово. Все суммы пересчитаны.');return result;}finally{orgBusy=false;}
}
function setFinanceSection(section){
  financeSection=section;
  document.querySelectorAll('[data-finance-section]').forEach(b=>{b.classList.toggle('selected',b.dataset.financeSection===section);b.setAttribute('aria-pressed',b.dataset.financeSection===section);});
  for(const id of ['overview','planning','savings','debts'])$('#finance-'+id+'-content').hidden=id!==section;
  if(section==='planning'&&typeof renderPlanner==='function')renderPlanner();
}
$('#finance-sections').addEventListener('click',event=>{const button=event.target.closest('[data-finance-section]');if(button)setFinanceSection(button.dataset.financeSection);});
function jumpToMoney(section,id){setView('finance');setFinanceSection(section);if(id)setTimeout(()=>document.getElementById('org-'+id)?.scrollIntoView({behavior:'smooth',block:'center'}),30);}
function renderMoneyOrganizer(){
  if(organizerProfileId!==currentUser?.id){organizerProfileId=currentUser?.id;setFinanceSection('overview');document.querySelectorAll('.org-dialog form').forEach(form=>form.reset());}
  const data=orgData(),ledger=financeData(),free=(ledger.balanceKopecks||0)-data.reservedKopecks;
  $('#savings-total').textContent=formatMoney(data.reservedKopecks);$('#savings-free').textContent=formatMoney(free);
  $('#savings-done').textContent=data.savings.filter(p=>p.status==='bought').length;
  $('#finance-reserved-caption').textContent=data.reservedKopecks?`В копилках ${formatMoney(data.reservedKopecks)} · свободно ${formatMoney(free)}`:'';
  $('#savings-list').innerHTML=data.savings.length?data.savings.map(p=>{
    const bought=p.status==='bought',pct=p.targetKopecks?Math.min(100,Math.round(p.balanceKopecks/p.targetKopecks*100)):0;
    const place={bank:'Банк',cash:'Наличные',other:'Другое место'}[p.location];
    return `<article class="card org-pot ${bought?'completed':''}" id="org-${p.id}"><div class="org-card-top"><span class="org-card-symbol">${p.kind==='purchase'?'🎁':'🔐'}</span><span class="org-badge">${bought?'Куплено ✓':p.kind==='reserve'?'Сейф':'На покупку'}</span>${!bought?`<button data-edit-pot="${p.id}" class="icon-button" aria-label="Изменить копилку">${icon('edit')}</button>`:''}</div><h3>${escapeHTML(p.name)}</h3><p class="org-place">${escapeHTML(place)}${p.locationName?' · '+escapeHTML(p.locationName):''}</p><strong class="org-big-money">${formatMoney(bought?p.purchaseKopecks:p.balanceKopecks)}</strong><p class="org-goal-label">${bought?'Покупка учтена в расходах':p.targetKopecks?'из '+formatMoney(p.targetKopecks):'Резерв без конечной цели'}</p><div class="org-progress"><i style="width:${bought?100:pct}%"></i></div><p class="org-small">${bought?'Остаток копилки возвращён в свободные деньги.':p.targetKopecks?Math.round(p.balanceKopecks/p.targetKopecks*100)+'% цели · '+(p.balanceKopecks>=p.targetKopecks?'Цель достигнута!':'Осталось '+formatMoney(p.targetKopecks-p.balanceKopecks)):'Деньги остаются в сейфе, пока ты сам их не вернёшь.'}</p><div class="org-card-actions">${bought?`<button data-undo-buy="${p.id}">Отменить покупку</button>`:`<button class="org-primary" data-move-pot="${p.id}" data-direction="deposit">＋ Пополнить</button><button data-move-pot="${p.id}" data-direction="withdraw">Вернуть</button>${p.kind==='purchase'&&p.balanceKopecks>=p.targetKopecks?`<button class="org-buy" data-buy-pot="${p.id}">Купил ✓</button>`:''}${!p.balanceKopecks?`<button data-delete-pot="${p.id}" aria-label="Удалить копилку">×</button>`:''}`}</div></article>`;
  }).join(''):'<div class="card org-empty"><span>🔐</span><h3>У каждого рубля может быть своя цель</h3><p>Создай копилку для подарка или сейф для резерва. Укажи, где лежат деньги — в банке, наличными или в другом месте.</p></div>';
  const places=new Map();for(const p of data.savings.filter(p=>p.status==='active')){const label=({bank:'Банк',cash:'Наличные',other:'Другое'}[p.location])+(p.locationName?' · '+p.locationName:'');places.set(label,(places.get(label)||0)+p.balanceKopecks);}
  $('#savings-locations').innerHTML=places.size?[...places].map(([label,amount])=>`<div><span>${escapeHTML(label)}</span><strong>${formatMoney(amount)}</strong></div>`).join(''):'<p class="org-small">Здесь появятся места хранения твоих копилок.</p>';
  renderDebts();
}
let potId=null,potEditing=false,movePotId=null,moveId=null,buyPotId=null;
orgDialog('org-pot-dialog','Место для твоей цели',`<p>Деньги в копилке — часть общего остатка, а не дополнительный доход.</p>${orgField('Название','<input id="pot-name" maxlength="80" placeholder="Подарок, отпуск, подушка безопасности…" required>')}<div class="org-fields">${orgField('Тип','<select id="pot-kind"><option value="purchase">На покупку или подарок</option><option value="reserve">Сейф / резерв</option></select>')}${orgField('Где хранится','<select id="pot-location"><option value="bank">Банк</option><option value="cash">Наличные</option><option value="other">Другое место</option></select>')}</div>${orgField('Счёт или место','<input id="pot-place" maxlength="60" placeholder="Например, накопительный счёт или конверт">')}${orgField('Цель, ₽ (для сейфа можно 0)',orgInput('pot-target','50 000','required'))}<div id="pot-initial-field">${orgField('Уже отложено, ₽',orgInput('pot-initial','0'))}</div><small>Укажи в финансах полный остаток, включая копилки. Пополнение резервирует часть этих денег, не создавая расход.</small>`,async()=>persist(potEditing?'/api/organizer/savings/'+potId:'/api/organizer/savings',potEditing?'PATCH':'POST',dictPot()));
function dictPot(){return {id:potId,name:$('#pot-name').value.trim(),kind:$('#pot-kind').value,location:$('#pot-location').value,locationName:$('#pot-place').value.trim(),targetKopecks:orgAmount($('#pot-target').value),balanceKopecks:orgAmount($('#pot-initial').value)};}
function openPot(id=null){if(!openOrgDialog('org-pot-dialog'))return;const p=orgData().savings.find(p=>p.id===id);potId=id||crypto.randomUUID();potEditing=Boolean(p);$('#pot-initial-field').hidden=potEditing;
  $('#pot-name').value=p?.name||'';$('#pot-kind').value=p?.kind||'purchase';$('#pot-location').value=p?.location||'bank';$('#pot-place').value=p?.locationName||'';$('#pot-target').value=p?orgMoneyInput(p.targetKopecks):'';$('#pot-initial').value='0';}
orgDialog('org-move-dialog','Переложить в копилку',`<p id="pot-move-caption"></p>${orgField('Действие','<select id="pot-move-direction"><option value="deposit">Пополнить из свободных денег</option><option value="withdraw">Вернуть в свободные деньги</option></select>')}${orgField('Сумма, ₽',orgInput('pot-move-amount','1 000','required'))}<small>Это перемещение внутри твоего остатка. Доход или расход не создаётся.</small>`,async()=>persist(`/api/organizer/savings/${movePotId}/move`,'POST',{id:moveId,amountKopecks:orgAmount($('#pot-move-amount').value),direction:$('#pot-move-direction').value}));
orgDialog('org-buy-dialog','Пора исполнить желание',`<p id="pot-buy-caption"></p>${orgField('Фактическая стоимость, ₽',orgInput('pot-buy-amount','0','required'))}<small>Создадим один расход «Покупки». Копилка завершится, а неиспользованный остаток станет свободным. Покупку можно отменить.</small>`,async()=>persist(`/api/organizer/savings/${buyPotId}/buy`,'POST',{amountKopecks:orgAmount($('#pot-buy-amount').value)}),'Купил — учесть расход ✓');
$('#savings-add').addEventListener('click',()=>openPot());
$('#savings-list').addEventListener('click',event=>{
  const b=event.target.closest('button');if(!b)return;
  if(b.dataset.editPot){openPot(b.dataset.editPot);return;}
  if(b.dataset.movePot&&openOrgDialog('org-move-dialog')){movePotId=b.dataset.movePot;moveId=crypto.randomUUID();const p=orgData().savings.find(p=>p.id===movePotId);$('#pot-move-caption').textContent=p.name+' · в копилке '+formatMoney(p.balanceKopecks);$('#pot-move-direction').value=b.dataset.direction;}
  if(b.dataset.buyPot&&openOrgDialog('org-buy-dialog')){buyPotId=b.dataset.buyPot;const p=orgData().savings.find(p=>p.id===buyPotId);$('#pot-buy-caption').textContent=p.name+' · накоплено '+formatMoney(p.balanceKopecks);$('#pot-buy-amount').value=orgMoneyInput(p.targetKopecks);}
  if(b.dataset.undoBuy)orgAction(`/api/organizer/savings/${b.dataset.undoBuy}/undo-buy`,'POST',{},'Отменить покупку? Расход будет убран, деньги вернутся в копилку.');
  if(b.dataset.deletePot)orgAction(`/api/organizer/savings/${b.dataset.deletePot}`,'DELETE',{},'Удалить пустую копилку?');
});
let debtId=null,debtEditing=false,payDebtId=null,paymentId=null;
orgDialog('org-debt-dialog','Долг под контролем',`${orgField('Название','<input id="debt-name" maxlength="80" placeholder="Рассрочка, кредит, долг другу…" required>')}${orgField('Кто кому должен','<select id="debt-direction"><option value="owe">Я должен</option><option value="owed">Мне должны</option></select>')}${orgField('Кому / кто / где','<input id="debt-party" maxlength="80" placeholder="Банк или имя человека">')}<div class="org-fields">${orgField('Полная сумма долга, ₽',orgInput('debt-amount','30 000','required'))}${orgField('Ближайший платёж, ₽',orgInput('debt-next-amount','0'))}</div>${orgField('Дата ближайшего платежа','<input id="debt-date" type="date" min="1900-01-01" max="2100-12-31">')}${orgField('Повторение','<select id="debt-repeat"><option value="0">Разовый платёж</option><option value="1">Каждый месяц</option></select>')}<div id="debt-monthly-fields" class="org-fields" hidden>${orgField('Число месяца (1–31)','<input id="debt-monthly-day" type="number" min="1" max="31" value="10">')}${orgField('Регулярный платёж, ₽',orgInput('debt-monthly-amount','5 000'))}</div><small>В коротком месяце 29–31 число переносится на последний день. Все ежемесячные платежи появятся в календаре и бюджете.</small>${orgField('Комментарий','<textarea id="debt-note" maxlength="300" rows="2"></textarea>')}<small>Создание долга не меняет баланс. Платёж учтётся в финансах только по твоему выбору. Если ближайшая сумма не задана, в плане учитывается весь остаток.</small>`,async()=>persist(debtEditing?'/api/organizer/debts/'+debtId:'/api/organizer/debts',debtEditing?'PATCH':'POST',{id:debtId,name:$('#debt-name').value.trim(),party:$('#debt-party').value.trim(),direction:$('#debt-direction').value,amountKopecks:orgAmount($('#debt-amount').value),paymentKopecks:orgAmount($('#debt-next-amount').value),dueDay:$('#debt-date').value,monthlyDay:$('#debt-repeat').value==='1'?Number($('#debt-monthly-day').value):0,monthlyPaymentKopecks:$('#debt-repeat').value==='1'?orgAmount($('#debt-monthly-amount').value):0,note:$('#debt-note').value.trim()}));
function openDebt(id=null){if(!openOrgDialog('org-debt-dialog'))return;const d=orgData().debts.find(d=>d.id===id);debtId=id||crypto.randomUUID();debtEditing=Boolean(d);$('#debt-name').value=d?.name||'';$('#debt-party').value=d?.party||'';$('#debt-direction').value=d?.direction||'owe';$('#debt-amount').value=d?orgMoneyInput(d.amountKopecks):'';$('#debt-next-amount').value=d?orgMoneyInput(d.paymentKopecks):'';$('#debt-date').value=d?.dueDay||'';$('#debt-note').value=d?.note||'';$('#debt-repeat').value=d?.monthlyDay?'1':'0';$('#debt-monthly-day').value=d?.monthlyDay||10;$('#debt-monthly-amount').value=d?.monthlyPaymentKopecks?orgMoneyInput(d.monthlyPaymentKopecks):'';syncDebtRecurrence();}
function syncDebtRecurrence(){
  const repeating=$('#debt-repeat').value==='1';$('#debt-monthly-fields').hidden=!repeating;
  $('#debt-monthly-day').required=repeating;$('#debt-monthly-amount').required=repeating;$('#debt-date').required=repeating;
}
$('#debt-repeat').addEventListener('change',()=>{
  if($('#debt-repeat').value==='1'){
    if($('#debt-date').value)$('#debt-monthly-day').value=Number($('#debt-date').value.slice(8));
    if(!$('#debt-monthly-amount').value)$('#debt-monthly-amount').value=$('#debt-next-amount').value;
  }syncDebtRecurrence();
});
$('#debt-date').addEventListener('change',()=>{if($('#debt-repeat').value==='1'&&$('#debt-date').value)$('#debt-monthly-day').value=Number($('#debt-date').value.slice(8));});
$('#debt-monthly-day').addEventListener('change',()=>{const day=Number($('#debt-monthly-day').value);if(day>=1&&day<=31&&$('#debt-date').value)$('#debt-date').value=RitmoSchedule.monthly($('#debt-date').value,day);});
orgDialog('org-payment-dialog','Ещё один шаг к свободе',`<p id="debt-pay-caption"></p><div class="org-fields">${orgField('Сумма платежа, ₽',orgInput('debt-pay-amount','','required'))}${orgField('Дата платежа','<input id="debt-pay-date" type="date" required>')}</div>${orgField('Следующий платёж (если долг остаётся)','<input id="debt-pay-next" type="date" min="1900-01-01" max="2100-12-31">')}<label class="org-check"><input id="debt-pay-record" type="checkbox" checked>Учесть платёж в финансах</label><small>Если уже внёс этот платёж отдельной операцией, сними галочку, чтобы не списать деньги дважды. Полная сумма закроет долг.</small>`,async()=>persist(`/api/organizer/debts/${payDebtId}/payments`,'POST',{id:paymentId,amountKopecks:orgAmount($('#debt-pay-amount').value),day:$('#debt-pay-date').value,nextDueDay:$('#debt-pay-next').value,recordTransaction:$('#debt-pay-record').checked}),'Записать платёж ✓');
function renderDebts(){
  const debts=orgData().debts,open=debts.filter(d=>d.remainingKopecks>0);
  $('#debts-owe').textContent=formatMoney(open.filter(d=>d.direction==='owe').reduce((s,d)=>s+d.remainingKopecks,0));$('#debts-owed').textContent=formatMoney(open.filter(d=>d.direction==='owed').reduce((s,d)=>s+d.remainingKopecks,0));$('#debts-closed').textContent=debts.filter(d=>!d.remainingKopecks).length;
  const filter=$('#debt-filter').value;
  $('#debts-list').innerHTML=debts.filter(d=>filter==='all'||d.status===filter).map(d=>{
    const closed=!d.remainingKopecks,overdue=!closed&&d.dueDay&&d.dueDay<todayKey,pct=Math.round((d.amountKopecks-d.remainingKopecks)/d.amountKopecks*100);
    return `<article class="card org-debt ${closed?'completed':''}" id="org-${d.id}"><div class="org-card-top"><span class="org-card-symbol">${closed?'✓':d.direction==='owe'?'↗':'↙'}</span><span class="org-badge ${overdue?'warning':''}">${closed?'Закрыт':d.direction==='owe'?'Я должен':'Мне должны'}${overdue?' · платёж просрочен':''}</span>${!closed?`<button data-edit-debt="${d.id}" class="icon-button" aria-label="Изменить долг">${icon('edit')}</button>`:''}</div><h3>${escapeHTML(d.name)}</h3><p class="org-place">${escapeHTML(d.party||'Место или человек не указаны')}</p><strong class="org-big-money">${formatMoney(d.remainingKopecks)}</strong><p class="org-goal-label">осталось из ${formatMoney(d.amountKopecks)}</p><div class="org-progress"><i style="width:${pct}%"></i></div><p class="org-small">${closed?'Долг полностью закрыт.':`Ближайший платёж: ${formatMoney(d.paymentKopecks||d.remainingKopecks)} · ${orgDate(d.dueDay)}`}</p>${d.monthlyDay&&!closed?`<p class="org-small">↻ Каждый месяц, ${d.monthlyDay}-го · ${formatMoney(d.monthlyPaymentKopecks)}<br>В коротком месяце — в последний день</p>`:''}${d.note?`<p class="org-small">${escapeHTML(d.note)}</p>`:''}<div class="org-card-actions">${!closed?`<button class="org-primary" data-pay-debt="${d.id}">Внести платёж</button><button data-close-debt="${d.id}">Закрыл долг ✓</button>`:''}${!d.payments.length?`<button data-delete-debt="${d.id}" aria-label="Удалить долг">×</button>`:''}</div>${d.payments.length?`<details class="org-payment-history"><summary>История платежей · ${d.payments.length}</summary>${d.payments.map(p=>`<div><span>${orgDate(p.day)}<small>${p.recorded?'Учтено в финансах':'Без повторной операции'}</small></span><strong>${formatMoney(p.amountKopecks)}</strong><button data-undo-payment="${p.id}" data-debt="${d.id}" aria-label="Отменить платёж">×</button></div>`).join('')}</details>`:''}</article>`;
  }).join('')||'<div class="card org-empty"><span>◎</span><h3>Долги на виду — спокойнее в голове</h3><p>Добавь сумму, кому должен и дату платежа. Закрытые долги останутся в истории.</p></div>';
}
$('#debts-add').addEventListener('click',()=>openDebt());$('#debt-filter').addEventListener('change',renderDebts);
$('#debts-list').addEventListener('click',event=>{
  const b=event.target.closest('button');if(!b)return;
  if(b.dataset.editDebt)openDebt(b.dataset.editDebt);
  const id=b.dataset.payDebt||b.dataset.closeDebt;
  if(id&&openOrgDialog('org-payment-dialog')){const d=orgData().debts.find(d=>d.id===id);payDebtId=id;paymentId=crypto.randomUUID();$('#debt-pay-caption').textContent=d.name+' · осталось '+formatMoney(d.remainingKopecks);$('#debt-pay-amount').value=orgMoneyInput(b.dataset.closeDebt?d.remainingKopecks:d.paymentKopecks||d.remainingKopecks);$('#debt-pay-date').value=todayKey;$('#debt-pay-date').max=todayKey;$('#debt-pay-next').parentElement.hidden=Boolean(d.monthlyDay);}
  if(b.dataset.deleteDebt)orgAction('/api/organizer/debts/'+b.dataset.deleteDebt,'DELETE',{},'Удалить долг без платежей?');
  if(b.dataset.undoPayment)orgAction(`/api/organizer/debts/${b.dataset.debt}/payments/${b.dataset.undoPayment}`,'DELETE',{},'Отменить платёж? Связанная операция в финансах тоже будет убрана.');
});
