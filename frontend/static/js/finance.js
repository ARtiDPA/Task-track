let financeMonth=todayKey.slice(0,7),financeKind='expense',financeFilter='all',financeSearch='',financeEntryId=null,financeEditing=false,financeWorking=false,financeProfileId=null,financeCategoryId=null,financeBudgetId=null;
const moneyFormat=new Intl.NumberFormat('ru-RU',{style:'currency',currency:'RUB',maximumFractionDigits:2});
const moneyShort=new Intl.NumberFormat('ru-RU',{notation:'compact',maximumFractionDigits:1});
const formatMoney=value=>moneyFormat.format(value/100);
const emptyFinance=()=>({openingBalanceKopecks:0,monthlyBudgetKopecks:0,categories:[],transactions:[],balanceKopecks:0});
function financeData(){return state.finance||emptyFinance();}
function financeSummary(){return RitmoFinanceMath.summarize(financeData(),financeMonth,todayKey);}
function financeMonthLabel(){return new Date(financeMonth+'-02T12:00:00').toLocaleDateString('ru-RU',{month:'long',year:'numeric'});}
function renderFinance(){
  if(financeProfileId!==currentUser?.id){
    financeMonth=todayKey.slice(0,7);financeFilter='all';financeSearch='';financeProfileId=currentUser?.id;
    $('#finance-search').value='';
    ['#finance-entry-form','#finance-settings-form','#finance-category-form','#finance-category-budget-form'].forEach(selector=>$(selector).reset());
  }
  const data=financeData(),summary=financeSummary();
  $('#finance-month').value=financeMonth;$('#finance-month').max=todayKey.slice(0,7);
  $('#finance-month-title').textContent=financeMonthLabel();
  $('#finance-balance').textContent=formatMoney(summary.balance);
  $('#finance-balance-card').classList.toggle('negative',summary.balance<0);
  $('#finance-income').textContent=formatMoney(summary.income);$('#finance-expenses').textContent=formatMoney(summary.expenses);
  $('#finance-net').textContent=formatMoney(summary.income-summary.expenses);
  ['#finance-balance','#finance-income','#finance-expenses','#finance-net'].forEach(selector=>$(selector).title=$(selector).textContent);
  $('#finance-net-caption').textContent=summary.expenses>summary.income?'Расходы выше доходов':'Доходы минус расходы';
  $('#finance-daily').textContent=summary.current?formatMoney(summary.dailyAvailable):'—';
  $('#finance-daily-caption').textContent=summary.current?`На день до конца месяца · ${summary.daysLeft} ${plural(summary.daysLeft,['день','дня','дней'])}`:'Для завершённого месяца не рассчитывается';
  $('#finance-month-income-label').textContent=financeMonthLabel();$('#finance-month-expense-label').textContent=financeMonthLabel();
  $('#finance-budget-value').textContent=summary.budget?`${formatMoney(summary.expenses)} / ${formatMoney(summary.budget)}`:'Лимит пока не задан';
  $('#finance-budget-fill').style.width=summary.budget?Math.min(100,summary.expenses/summary.budget*100)+'%':'0%';
  $('#finance-budget-fill').classList.toggle('over',Boolean(summary.budget&&summary.expenses>summary.budget));
  $('#finance-budget-left').textContent=summary.budget?(summary.remaining>=0?`Можно потратить ещё ${formatMoney(summary.remaining)}`:`Лимит превышен на ${formatMoney(-summary.remaining)}`):'Укажи месячный лимит, чтобы замечать перерасход.';
  $('#finance-setup-hint').hidden=Boolean(data.transactions.length||data.openingBalanceKopecks);
  const oldFilter=financeFilter;
  $('#finance-category-filter').innerHTML='<option value="all">Все категории</option>'+data.categories.map(c=>`<option value="${escapeHTML(c.id)}">${c.emoji} ${escapeHTML(c.name)}</option>`).join('');
  $('#finance-category-filter').value=data.categories.some(c=>c.id===oldFilter)?oldFilter:'all';
  renderFinanceChart(summary);renderFinanceDonut(summary);renderFinanceInsights(summary);renderFinanceLedger(summary);renderFinanceBudgets(summary);
  if($('#finance-entry-dialog').open)renderFinanceEntryCategories();
  if(typeof renderMoneyOrganizer==='function')renderMoneyOrganizer();
  if(typeof renderPlanner==='function')renderPlanner();
}
function renderFinanceChart(summary){
  const width=Math.max(260,Math.min(700,$('#finance-chart').clientWidth||600)),height=220,left=43,right=13,top=18,bottom=30,values=summary.series.map(item=>item.balance);
  const min=Math.min(0,...values),max=Math.max(10000,...values),span=max-min||1,plot=height-top-bottom;
  const coords=summary.series.map((item,i)=>({...item,x:left+i*(width-left-right)/Math.max(1,summary.series.length-1),y:top+(max-item.balance)/span*plot}));
  const path=coords.map((point,i)=>`${i?'L':'M'}${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(' ');
  const area=coords.length?`${path} L${coords.at(-1).x},${height-bottom} L${left},${height-bottom} Z`:'';
  $('#finance-chart').innerHTML=`<svg class="finance-line-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Баланс по дням выбранного месяца"><defs><linearGradient id="finance-area" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#a8cbbd" stop-opacity=".27"/><stop offset="1" stop-color="#a8cbbd" stop-opacity=".01"/></linearGradient></defs>${[0,.25,.5,.75,1].map(f=>`<line x1="${left}" y1="${top+f*plot}" x2="${width-right}" y2="${top+f*plot}" stroke="#efedf5" stroke-dasharray="3 5"/><text x="0" y="${top+f*plot+4}">${moneyShort.format((max-f*span)/100)}</text>`).join('')}<path d="${area}" fill="url(#finance-area)"/><path class="finance-draw" d="${path}" fill="none" stroke="${summary.balance<0?'#c78c9e':'#83b19d'}" stroke-width="2.7" stroke-linejoin="round" stroke-linecap="round"/>${coords.filter((_,i)=>i===0||i===coords.length-1||i%5===0).map(p=>`<circle cx="${p.x}" cy="${p.y}" r="3" fill="white" stroke="#89b5a2" stroke-width="1.5"><title>${p.day}: ${formatMoney(p.balance)}</title></circle><text x="${p.x}" y="${height-6}" text-anchor="middle">${Number(p.day.slice(8))}</text>`).join('')}</svg>`;
  $('#finance-chart-caption').textContent=summary.selected.length?'Начальный остаток + доходы − расходы. Учитываются и операции до начала месяца.':'График оживёт после первой операции. Никаких выдуманных данных.';
}
function renderFinanceDonut(summary){
  let offset=0;const circumference=2*Math.PI*65,groups=summary.groups.filter(c=>c.total);
  const circles=groups.map(c=>{const length=c.total/summary.expenses*circumference;const result=`<circle cx="90" cy="90" r="65" fill="none" stroke="${c.color}" stroke-width="17" stroke-dasharray="${length} ${circumference-length}" stroke-dashoffset="${-offset}" transform="rotate(-90 90 90)"><title>${escapeHTML(c.name)}: ${formatMoney(c.total)}</title></circle>`;offset+=length;return result;}).join('');
  $('#finance-donut').innerHTML=`<svg viewBox="0 0 180 180" role="img" aria-label="Распределение расходов по категориям"><circle cx="90" cy="90" r="65" fill="none" stroke="#f0edf6" stroke-width="17"/>${circles}</svg><div class="finance-donut-center"><small>РАСХОДЫ</small><strong>${formatMoney(summary.expenses)}</strong><span>${groups.length} ${plural(groups.length,['категория','категории','категорий'])}</span></div>`;
  $('#finance-category-legend').innerHTML=groups.length?groups.slice(0,5).map(c=>`<button class="finance-legend-row" data-finance-category="${escapeHTML(c.id)}"><i style="background:${c.color}"></i><span>${escapeHTML(c.name)}</span><strong>${Math.round(c.total/summary.expenses*100)}%</strong></button>`).join(''):'<p class="finance-muted">Добавь расход, чтобы увидеть распределение.</p>';
}
function renderFinanceInsights(summary){
  const items=[];const top=summary.groups.find(c=>c.total);
  if(summary.balance<0)items.push(['rose','↘','Баланс ниже нуля',`Не хватает ${formatMoney(-summary.balance)} по внесённым операциям. Проверь доходы и начальный остаток.`]);
  else items.push(['mint','↗','Деньги под контролем',`На текущем балансе ${formatMoney(summary.balance)}. Сумма учитывает всю внесённую историю.`]);
  if(top)items.push(['violet',top.emoji,'Главная статья расходов',`${top.name}: ${formatMoney(top.total)} — ${Math.round(top.total/summary.expenses*100)}% расходов за месяц.`]);
  else items.push(['violet','✦','Увидеть картину целиком','Записывай даже небольшие покупки — категории покажут, из чего складываются траты.']);
  if(summary.budget&&summary.expenses>summary.budget)items.push(['rose','!','Месячный лимит превышен',`На ${formatMoney(summary.expenses-summary.budget)}. Это превышение лимита, а не сумма долга.`]);
  else if(summary.budget&&summary.current&&summary.projected>summary.budget)items.push(['amber','↗','Темп расходов выше лимита',`При текущем среднем темпе за месяц получится около ${formatMoney(summary.projected)}. Это линейная оценка.`]);
  else if(summary.expenses>summary.income)items.push(['amber','↘','Расходы выше доходов',`Разница за выбранный месяц — ${formatMoney(summary.expenses-summary.income)}. Она может покрываться прежним остатком.`]);
  else items.push(['mint','✓',summary.budget?'В пределах лимита':'Задай комфортный лимит',summary.budget?`До лимита осталось ${formatMoney(summary.remaining)}.`:'Общий лимит и ограничения по категориям помогут раньше замечать перерасход.']);
  $('#finance-insights').innerHTML=items.map(([tone,symbol,title,description])=>`<article class="finance-insight ${tone}"><span>${symbol}</span><div><h3>${escapeHTML(title)}</h3><p>${escapeHTML(description)}</p></div></article>`).join('');
}
function renderFinanceLedger(summary){
  const data=financeData(),query=financeSearch.toLocaleLowerCase('ru');
  const entries=summary.selected.filter(entry=>{
    const category=data.categories.find(c=>c.id===entry.categoryId);
    return(financeFilter==='all'||entry.categoryId===financeFilter)&&(!query||`${entry.note} ${category?.name||''}`.toLocaleLowerCase('ru').includes(query));
  });
  $('#finance-entry-count').textContent=entries.length;
  $('#finance-ledger').innerHTML=entries.length?entries.map(entry=>{const category=data.categories.find(c=>c.id===entry.categoryId);return `<div class="finance-entry" data-finance-entry="${entry.id}"><span class="finance-entry-emoji" style="--category-color:${category.color}">${category.emoji}</span><div class="finance-entry-title"><strong>${escapeHTML(entry.note||category.name)}</strong><span>${escapeHTML(category.name)} · ${new Date(entry.day+'T12:00:00').toLocaleDateString('ru-RU',{day:'numeric',month:'short'})}</span></div><strong class="finance-entry-amount ${entry.kind}">${entry.kind==='income'?'+':'−'}${formatMoney(entry.amountKopecks)}</strong><div class="finance-entry-actions">${entry.source?`<button class="org-linked-label" data-linked-finance="${entry.source}" data-entity="${entry.entityId}" aria-label="Открыть связанную запись">Связано ↗</button>`:`<button data-edit-finance="${entry.id}" aria-label="Изменить операцию">${icon('edit')}</button><button data-delete-finance="${entry.id}" aria-label="Удалить операцию">${icon('x')}</button>`}</div></div>`;}).join(''):`<div class="finance-empty"><span>↗</span><strong>${summary.selected.length?'Ничего не найдено':'Твоя финансовая история начинается здесь'}</strong><p>${summary.selected.length?'Измени поиск или категорию.':'Добавь доход или расход — остальное посчитаем за тебя.'}</p></div>`;
}
function renderFinanceBudgets(summary){
  const categories=summary.groups.filter(c=>c.total||c.budgetKopecks);
  $('#finance-category-budgets').innerHTML=(categories.length?categories:summary.groups.slice(0,4)).map(c=>{
    const pct=c.budgetKopecks?Math.round(c.total/c.budgetKopecks*100):0;
    return `<button class="finance-category-budget" data-edit-budget="${escapeHTML(c.id)}"><div><span>${c.emoji} ${escapeHTML(c.name)}</span><strong>${formatMoney(c.total)}</strong></div><div class="finance-category-track"><i class="${pct>100?'over':''}" style="width:${c.budgetKopecks?Math.min(100,pct):0}%;background:${pct>100?'#ce96a5':c.color}"></i></div><small>${c.budgetKopecks?(pct>100?'Перерасход '+formatMoney(c.total-c.budgetKopecks):'из '+formatMoney(c.budgetKopecks)):'Нажми, чтобы задать лимит'}<span>${c.budgetKopecks?pct+'%':'↗'}</span></small></button>`;
  }).join('');
}
function renderFinanceEntryCategories(){
  const selected=$('#finance-entry-category').value;
  const items=financeData().categories.filter(c=>c.kind===financeKind);
  $('#finance-entry-category').innerHTML=items.map(c=>`<option value="${escapeHTML(c.id)}">${c.emoji} ${escapeHTML(c.name)}</option>`).join('');
  if(items.some(c=>c.id===selected))$('#finance-entry-category').value=selected;
  document.querySelectorAll('[data-finance-kind]').forEach(b=>{b.classList.toggle('selected',b.dataset.financeKind===financeKind);b.setAttribute('aria-pressed',b.dataset.financeKind===financeKind);});
}
function openFinanceEntry(id=null){
  if(!ready||saving)return;const entry=financeData().transactions.find(e=>e.id===id);
  financeEntryId=id||crypto.randomUUID();financeEditing=Boolean(entry);financeKind=entry?.kind||'expense';
  $('#finance-entry-form').reset();$('#finance-entry-error').textContent='';
  $('#finance-entry-title').textContent=entry?'Изменить операцию':'Каждая сумма на своём месте';
  $('#finance-entry-amount').value=entry?(entry.amountKopecks/100).toFixed(2).replace('.',','):'';
  $('#finance-entry-date').value=entry?.day||todayKey;$('#finance-entry-date').max=todayKey;
  $('#finance-entry-note').value=entry?.note||'';renderFinanceEntryCategories();
  if(entry)$('#finance-entry-category').value=entry.categoryId;
  $('#finance-entry-dialog').showModal();$('#finance-entry-amount').focus();
}
$('#finance-add').addEventListener('click',()=>openFinanceEntry());
$('#finance-month').addEventListener('change',event=>{if(/^\d{4}-\d{2}$/.test(event.target.value)&&event.target.value<=todayKey.slice(0,7)){financeMonth=event.target.value;renderFinance();}});
$('#finance-category-filter').addEventListener('change',event=>{financeFilter=event.target.value;renderFinanceLedger(financeSummary());});
$('#finance-search').addEventListener('input',event=>{financeSearch=event.target.value;renderFinanceLedger(financeSummary());});
$('#finance-category-legend').addEventListener('click',event=>{const b=event.target.closest('[data-finance-category]');if(b){financeFilter=b.dataset.financeCategory;renderFinance();$('#finance-history-card').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});}});
document.querySelectorAll('[data-finance-kind]').forEach(button=>button.addEventListener('click',()=>{financeKind=button.dataset.financeKind;renderFinanceEntryCategories();}));
document.querySelectorAll('[data-close-finance]').forEach(button=>button.addEventListener('click',()=>$('#'+button.dataset.closeFinance).close()));
$('#finance-entry-form').addEventListener('submit',async event=>{
  event.preventDefault();if(saving||financeWorking)return;
  try{
    const amount=RitmoFinanceMath.parseAmount($('#finance-entry-amount').value);if(amount<=0)throw new Error('Сумма должна быть больше нуля.');
    const payload={id:financeEntryId,kind:financeKind,categoryId:$('#finance-entry-category').value,amountKopecks:amount,day:$('#finance-entry-date').value,note:$('#finance-entry-note').value.trim()};
    financeWorking=true;$('#finance-save-entry').disabled=true;$('#finance-entry-error').textContent='';
    if(await persist(financeEditing?`/api/finance/transactions/${financeEntryId}`:'/api/finance/transactions',financeEditing?'PATCH':'POST',payload)){
      financeMonth=payload.day.slice(0,7);financeFilter='all';financeSearch='';$('#finance-search').value='';renderFinance();$('#finance-entry-dialog').close();toast('Операция сохранена. Баланс пересчитан ✨');
    }else $('#finance-entry-error').textContent='Не удалось сохранить. Проверь соединение и повтори попытку.';
  }catch(error){$('#finance-entry-error').textContent=error.message;}
  finally{financeWorking=false;$('#finance-save-entry').disabled=false;}
});
$('#finance-ledger').addEventListener('click',async event=>{
  const linked=event.target.closest('[data-linked-finance]');if(linked){jumpToMoney(({savings:'savings',debt:'debts',plan:'planning'})[linked.dataset.linkedFinance],linked.dataset.entity);return;}
  const edit=event.target.closest('[data-edit-finance]');if(edit){openFinanceEntry(edit.dataset.editFinance);return;}
  const remove=event.target.closest('[data-delete-finance]');if(!remove||saving||financeWorking)return;
  if(!confirm('Удалить эту операцию? Баланс и статистика будут пересчитаны.'))return;
  financeWorking=true;try{if(await persist(`/api/finance/transactions/${remove.dataset.deleteFinance}`,'DELETE',{}))toast('Операция удалена');}finally{financeWorking=false;}
});
function openFinanceSettings(){
  if(!ready||saving)return;const data=financeData();
  $('#finance-opening').value=(data.openingBalanceKopecks/100).toFixed(2).replace('.',',');
  $('#finance-monthly-limit').value=data.monthlyBudgetKopecks?(data.monthlyBudgetKopecks/100).toFixed(2).replace('.',','):'';
  $('#finance-settings-error').textContent='';$('#finance-settings-dialog').showModal();
}
['#finance-settings','#finance-setup-button','#finance-budget-settings'].forEach(selector=>$(selector).addEventListener('click',openFinanceSettings));
$('#finance-settings-form').addEventListener('submit',async event=>{
  event.preventDefault();if(saving||financeWorking)return;
  try{
    const payload={openingBalanceKopecks:RitmoFinanceMath.parseAmount($('#finance-opening').value,true),monthlyBudgetKopecks:RitmoFinanceMath.parseAmount($('#finance-monthly-limit').value||'0')};
    financeWorking=true;$('#finance-save-settings').disabled=true;
    if(await persist('/api/finance/settings','PUT',payload)){$('#finance-settings-dialog').close();toast('Остаток и лимит обновлены');}
    else $('#finance-settings-error').textContent='Не сохранено. Повтори попытку.';
  }catch(error){$('#finance-settings-error').textContent=error.message;}finally{financeWorking=false;$('#finance-save-settings').disabled=false;}
});
$('#finance-new-category').addEventListener('click',()=>{
  if(saving)return;financeCategoryId=crypto.randomUUID();$('#finance-category-form').reset();$('#finance-new-category-error').textContent='';$('#finance-category-dialog').showModal();
});
$('#finance-category-form').addEventListener('submit',async event=>{
  event.preventDefault();if(saving||financeWorking)return;
  const payload={id:financeCategoryId,name:$('#finance-new-category-name').value.trim(),kind:financeKind,emoji:$('#finance-new-category-emoji').value,color:'#a68bd2'};
  financeWorking=true;$('#finance-save-category').disabled=true;
  try{if(await persist('/api/finance/categories','POST',payload)){renderFinanceEntryCategories();$('#finance-entry-category').value=financeCategoryId;$('#finance-category-dialog').close();}else $('#finance-new-category-error').textContent='Не удалось сохранить категорию.';}
  finally{financeWorking=false;$('#finance-save-category').disabled=false;}
});
$('#finance-category-budgets').addEventListener('click',event=>{
  const b=event.target.closest('[data-edit-budget]');if(!b||saving)return;
  const c=financeData().categories.find(c=>c.id===b.dataset.editBudget);financeBudgetId=c.id;
  $('#finance-budget-category-name').textContent=`${c.emoji} ${c.name}`;$('#finance-category-limit').value=c.budgetKopecks?(c.budgetKopecks/100).toFixed(2).replace('.',','):'';
  $('#finance-category-budget-error').textContent='';$('#finance-category-budget-dialog').showModal();
});
$('#finance-category-budget-form').addEventListener('submit',async event=>{
  event.preventDefault();if(saving||financeWorking)return;
  try{const amount=RitmoFinanceMath.parseAmount($('#finance-category-limit').value||'0');financeWorking=true;$('#finance-save-budget').disabled=true;
    if(await persist(`/api/finance/categories/${financeBudgetId}/budget`,'PUT',{budgetKopecks:amount})){$('#finance-category-budget-dialog').close();toast('Лимит категории сохранён');}else $('#finance-category-budget-error').textContent='Не сохранено. Повтори попытку.';
  }catch(error){$('#finance-category-budget-error').textContent=error.message;}finally{financeWorking=false;$('#finance-save-budget').disabled=false;}
});
$('#finance-export').addEventListener('click',()=>{
  const data=financeData(),entries=financeSummary().selected;
  if(!entries.length){toast('В выбранном месяце пока нет операций для выгрузки.');return;}
  const safe=value=>{
    const text=String(value),protectedText=/^-?\d+,\d{2}$/.test(text)?text:text.replace(/^[=+\-@\t\r]/,"'$&");
    return '"'+protectedText.replaceAll('"','""')+'"';
  };
  const rows=[['Дата','Тип','Категория','Сумма, RUB','Комментарий'],...entries.map(e=>[e.day,e.kind==='income'?'Доход':'Расход',data.categories.find(c=>c.id===e.categoryId)?.name||'',((e.kind==='expense'?-1:1)*e.amountKopecks/100).toFixed(2).replace('.',','),e.note])];
  const blob=new Blob(['\uFEFF'+rows.map(row=>row.map(safe).join(';')).join('\r\n')],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download=`ritmo-finance-${financeMonth}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
new ResizeObserver(()=>{if(view==='finance'&&ready)renderFinanceChart(financeSummary());}).observe($('#finance-chart'));
