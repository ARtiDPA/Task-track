let plannerEnd=dateKey(new Date(today.getFullYear(),today.getMonth()+1,0)),planId=null,planEditing=false,postPlanId=null;
function renderPlannerCategories(selected=''){
  const kind=$('#plan-kind').value;
  $('#plan-category').innerHTML=financeData().categories.filter(c=>c.kind===kind).map(c=>`<option value="${escapeHTML(c.id)}">${c.emoji} ${escapeHTML(c.name)}</option>`).join('');
  if(selected)$('#plan-category').value=selected;
}
orgDialog('org-plan-dialog','План на твои деньги',`<p>Это ожидание, а не фактическая операция. Баланс изменится только после кнопки «Провести».</p>${orgField('Название','<input id="plan-name" maxlength="80" placeholder="Аренда, зарплата, подарок…" required>')}<div class="org-fields">${orgField('Тип','<select id="plan-kind"><option value="expense">Плановый расход</option><option value="income">Ожидаемый доход</option></select>')}${orgField('Сумма, ₽',orgInput('plan-amount','','required'))}</div>${orgField('Ожидаемая дата','<input id="plan-day" type="date" min="1900-01-01" max="2100-12-31" required>')}${orgField('Категория','<select id="plan-category" required></select>')}`,async()=>persist(planEditing?'/api/organizer/plans/'+planId:'/api/organizer/plans',planEditing?'PATCH':'POST',{id:planId,name:$('#plan-name').value.trim(),kind:$('#plan-kind').value,categoryId:$('#plan-category').value,amountKopecks:orgAmount($('#plan-amount').value),day:$('#plan-day').value}));
$('#plan-kind').addEventListener('change',()=>renderPlannerCategories());
function openPlan(id=null,day='',kind='expense'){
  if(!openOrgDialog('org-plan-dialog'))return;const p=orgData().plans.find(p=>p.id===id);planId=id||crypto.randomUUID();planEditing=Boolean(p);
  $('#plan-name').value=p?.name||'';$('#plan-kind').value=p?.kind||kind;$('#plan-amount').value=p?orgMoneyInput(p.amountKopecks):'';$('#plan-day').value=p?.day||day||dateKey(shiftDate(today,1));renderPlannerCategories(p?.categoryId);
}
document.querySelectorAll('[data-new-plan]').forEach(button=>button.addEventListener('click',()=>openPlan(null,button.closest('#calendar-view')?calendarDay:'',button.dataset.newPlan)));
orgDialog('org-post-plan-dialog','План стал реальностью',`<p id="plan-post-caption"></p>${orgField('Когда деньги пришли или ушли?','<input id="plan-actual-day" type="date" min="1900-01-01" required>')}<small>Создадим одну фактическую операцию. План перестанет участвовать в прогнозе, поэтому повторного учёта не будет.</small>`,async()=>persist(`/api/organizer/plans/${postPlanId}/post`,'POST',{actualDay:$('#plan-actual-day').value}),'Провести в финансах ✓');
function renderPlanner(){
  $('#planner-end').value=plannerEnd;$('#planner-end').min=todayKey;$('#planner-end').max=dateKey(shiftDate(today,365));
  let result;try{result=RitmoPlanner.calculate(financeData(),orgData(),todayKey,plannerEnd,{includeIncome:$('#planner-income-toggle').checked,includeDebts:$('#planner-debts-toggle').checked});}catch(error){$('#planner-warning').textContent=error.message;return;}
  $('#planner-daily').textContent=formatMoney(result.daily);$('#planner-weekly').textContent=formatMoney(result.week);$('#planner-period').textContent=formatMoney(result.period);$('#planner-ending').textContent=formatMoney(result.ending);
  $('#planner-range-caption').textContent=`С ${orgDate(todayKey)} по ${orgDate(plannerEnd)} · ${result.days} ${plural(result.days,['день','дня','дней'])}, включая сегодня`;
  $('#planner-warning').textContent=result.firstShortfall?`Есть нехватка денег уже ${orgDate(result.firstShortfall)}. Положительный остаток позже не устраняет этот разрыв.`:result.overdue?'Планы с прошедшей датой ещё не исполнены: в расчёте они перенесены на сегодня.':'Расчёт сходится по внесённым планам. Ожидаемые доходы пока не являются фактическими деньгами.';
  $('#planner-warning').classList.toggle('danger',Boolean(result.firstShortfall));
  $('#planner-breakdown').innerHTML=[['Текущий фактический остаток',result.balance],['Отложено в копилках',-result.reserved],['Свободно на старте',result.free],['Ожидаемые поступления',result.income],['Будущие расходы и платежи',-result.expenses],['Остаток к выбранной дате',result.ending]].map(([label,amount])=>`<div><span>${label}</span><strong class="${amount<0?'org-negative':''}">${formatMoney(amount)}</strong></div>`).join('');
  $('#planner-obligations').innerHTML=result.items.length?result.items.map(item=>`<button class="org-schedule-item" data-planner-jump="${item.source}" data-id="${item.id}"><span class="org-schedule-icon">${item.source==='debt'?'◎':item.kind==='income'?'↙':'↗'}</span><div><strong>${escapeHTML(item.name)}</strong><small>${orgDate(item.originalDay)} · ${item.source==='debt'?'Ближайший платёж по долгу':'План'}${item.originalDay<todayKey?' · дата прошла':''}</small></div><b class="${item.kind==='income'?'org-positive':'org-negative'}">${item.kind==='income'?'+':'−'}${formatMoney(item.amount)}</b></button>`).join(''):'<p class="org-small">До выбранной даты пока нет планов или платежей.</p>';
  $('#planner-undated').textContent=result.undatedDebts?`${result.undatedDebts} ${plural(result.undatedDebts,['долг без даты','долга без даты','долгов без даты'])} не включено в расчёт. Укажи дату платежа в разделе «Долги».`:'';
  renderPlannerChart(result);renderPlans();
}
function renderPlannerChart(result){
  const width=Math.max(270,Math.min(650,$('#planner-chart').clientWidth||500)),height=195,left=45,right=15,top=15,bottom=27;
  const vals=[result.free,...result.series.map(p=>p.balance)],min=Math.min(0,...vals),max=Math.max(10000,...vals),span=max-min||1;
  const points=result.series.map((p,i)=>({...p,x:left+i*(width-left-right)/Math.max(1,result.days-1),y:top+(max-p.balance)/span*(height-top-bottom)}));
  const path=points.map((p,i)=>`${i?'L':'M'}${p.x},${p.y}`).join(' ');
  $('#planner-chart').innerHTML=`<svg class="planner-line" viewBox="0 0 ${width} ${height}" role="img" aria-label="Прогноз свободного остатка без повседневных трат">${[0,.5,1].map(v=>`<line x1="${left}" x2="${width-right}" y1="${top+v*(height-top-bottom)}" y2="${top+v*(height-top-bottom)}" stroke="#eee8f5" stroke-dasharray="3 5"/><text x="0" y="${top+v*(height-top-bottom)+4}">${moneyShort.format((max-v*span)/100)}</text>`).join('')}<path d="${path}" fill="none" stroke="${result.firstShortfall?'#c78d9d':'#a48bcd'}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>${points.filter((p,i)=>i===0||i===points.length-1||i%Math.max(1,Math.floor(points.length/4))===0).map(p=>`<circle cx="${p.x}" cy="${p.y}" r="3" fill="white" stroke="#b09aca"/><text x="${p.x}" y="${height-5}" text-anchor="middle">${p.day.slice(8)}.${p.day.slice(5,7)}</text>`).join('')}</svg>`;
}
function renderPlans(){
  const filter=$('#plan-filter').value;
  const plans=orgData().plans.filter(p=>filter==='all'||p.status===filter);
  $('#plans-list').innerHTML=plans.length?plans.map(p=>{
    const cat=financeData().categories.find(c=>c.id===p.categoryId),overdue=p.status==='pending'&&p.day<todayKey;
    return `<article class="card org-plan" id="org-${p.id}"><div class="org-plan-main"><span class="org-card-symbol">${cat?.emoji||'◷'}</span><div><h3>${escapeHTML(p.name)}</h3><p>${orgDate(p.day)} · ${escapeHTML(cat?.name||'')} ${overdue?'· дата прошла':''}</p></div><strong class="${p.kind==='income'?'org-positive':'org-negative'}">${p.kind==='income'?'+':'−'}${formatMoney(p.amountKopecks)}</strong></div><div class="org-plan-bottom"><span class="org-badge ${overdue?'warning':''}">${p.status==='posted'?'Проведено '+orgDate(p.actualDay):p.status==='cancelled'?'Отменён':overdue?'Ожидает проведения':'В планах'}</span><div class="org-card-actions">${p.status==='pending'?`<button class="org-primary" data-post-plan="${p.id}">Провести ✓</button><button data-edit-plan="${p.id}">Изменить</button><button data-cancel-plan="${p.id}">Отменить</button>`:`<button data-undo-plan="${p.id}">${p.status==='posted'?'Отменить проведение':'Восстановить'}</button><button data-delete-plan="${p.id}" ${p.status==='posted'?'disabled':''}>×</button>`}</div></div></article>`;
  }).join(''):'<div class="card org-empty"><span>◷</span><h3>У будущих денег тоже есть дата</h3><p>Запланируй зарплату, аренду или покупку. Они появятся в календаре и расчёте бюджета.</p></div>';
}
$('#plans-add').addEventListener('click',()=>openPlan());$('#plan-filter').addEventListener('change',renderPlans);
$('#planner-end').addEventListener('change',event=>{plannerEnd=event.target.value;renderPlanner();});
['#planner-income-toggle','#planner-debts-toggle'].forEach(s=>$(s).addEventListener('change',renderPlanner));
document.querySelectorAll('[data-plan-range]').forEach(button=>button.addEventListener('click',()=>{plannerEnd=button.dataset.planRange==='month'?dateKey(new Date(today.getFullYear(),today.getMonth()+1,0)):dateKey(shiftDate(today,Number(button.dataset.planRange)-1));renderPlanner();}));
$('#plans-list').addEventListener('click',event=>{
  const b=event.target.closest('button');if(!b)return;
  if(b.dataset.editPlan)openPlan(b.dataset.editPlan);
  if(b.dataset.postPlan&&openOrgDialog('org-post-plan-dialog')){postPlanId=b.dataset.postPlan;const p=orgData().plans.find(p=>p.id===postPlanId);$('#plan-post-caption').textContent=p.name+' · '+formatMoney(p.amountKopecks);$('#plan-actual-day').value=todayKey;$('#plan-actual-day').max=todayKey;}
  if(b.dataset.cancelPlan)orgAction(`/api/organizer/plans/${b.dataset.cancelPlan}/cancel`,'POST',{},'Убрать этот план из прогноза? Его можно будет восстановить.');
  if(b.dataset.undoPlan)orgAction(`/api/organizer/plans/${b.dataset.undoPlan}/undo`,'POST',{},'Вернуть план в ожидание? Связанная фактическая операция, если она есть, будет убрана.');
  if(b.dataset.deletePlan)orgAction(`/api/organizer/plans/${b.dataset.deletePlan}`,'DELETE',{},'Удалить план?');
});
$('#planner-obligations').addEventListener('click',event=>{const b=event.target.closest('[data-planner-jump]');if(b)jumpToMoney(b.dataset.plannerJump==='debt'?'debts':'planning',b.dataset.id);});
new ResizeObserver(()=>{if(view==='finance'&&financeSection==='planning'&&ready){try{renderPlannerChart(RitmoPlanner.calculate(financeData(),orgData(),todayKey,plannerEnd,{includeIncome:$('#planner-income-toggle').checked,includeDebts:$('#planner-debts-toggle').checked}));}catch{}}}).observe($('#planner-chart'));
