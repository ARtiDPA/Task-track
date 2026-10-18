let waterAmount=250,pendingWaterEntry=null,waterProfileId=null,waterWorking=false;
const waterIcons={drop:'<path d="M12 3C9 7 5 11 5 15a7 7 0 0 0 14 0c0-4-4-8-7-12Z"/>',glass:'<path d="m5 3 2 18h10l2-18H5Zm1 6h12"/>',plus:'<path d="M12 5v14M5 12h14"/>',undo:'<path d="M4 9h10a6 6 0 1 1-6 10M4 9l5-5M4 9l5 5"/>'};
function waterIcon(name){return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${waterIcons[name]||waterIcons.drop}</svg>`;}
document.querySelectorAll('[data-water-icon]').forEach(el=>el.innerHTML=waterIcon(el.dataset.waterIcon));
const numberRu=value=>value.toLocaleString('ru-RU',{maximumFractionDigits:1});
function renderWater(){
  if(waterProfileId!==currentUser?.id){pendingWaterEntry=null;waterProfileId=currentUser?.id;}
  const water=state.water||{profile:null,goalMl:1750,totalMl:0,entries:[],history:[]};
  const configured=Boolean(water.profile),percent=Math.round(water.totalMl/water.goalMl*100),capped=Math.min(100,percent);
  $('#water-onboarding').hidden=configured;$('#water-tracker-content').hidden=!configured;
  $('#water-edit-profile').hidden=!configured;
  $('#water-total').textContent=numberRu(water.totalMl);$('#water-target').textContent=numberRu(water.goalMl);
  $('#water-glass-count').textContent=numberRu(water.totalMl/250);$('#water-glass-goal').textContent=numberRu(water.goalMl/250);
  $('#water-progress-label').textContent=`${percent}% дневной цели`;
  $('#water-progress-bar').style.width=capped+'%';
  $('#body-progress').textContent=capped+'%';
  $('#human-water-level').style.setProperty('--water-y',`${440-capped*4.2}px`);
  $('#human-visual').setAttribute('aria-label',`Выпито ${water.totalMl} из ${water.goalMl} миллилитров, ${percent}% дневной цели`);
  $('#water-body-message').textContent=!configured?'Твой ритм заботы о себе':percent>=100?'Цель на сегодня достигнута':percent>=50?'Уже больше половины пути':water.totalMl?'Каждый глоток — маленькая забота':'Начни с одного стакана';
  const remaining=Math.max(0,water.goalMl-water.totalMl);
  $('#water-remaining').textContent=remaining?`До цели ещё ${numberRu(remaining)} мл. Распределяй напитки в течение дня.`:'Сегодня цель выполнена. Не нужно пить через силу ради цифры.';
  $('#water-glasses').innerHTML=Array.from({length:Math.ceil(water.goalMl/250)},(_,i)=>{
    const fill=Math.min(100,Math.max(0,(water.totalMl-i*250)/250*100));
    return `<span class="water-glass ${fill===100?'filled':''}" title="Стакан ${i+1}: ${Math.min(250,Math.max(0,water.totalMl-i*250))} / 250 мл"><span class="glass-liquid" style="height:${fill}%"></span>${waterIcon('glass')}</span>`;
  }).join('');
  $('#water-profile-summary').textContent=configured?`${numberRu(water.profile.heightCm)} см · ${numberRu(water.profile.weightKg)} кг · стакан 250 мл`:'Стакан в Ritmo — 250 мл';
  $('#water-entry-count').textContent=water.entries.length;
  $('#water-entry-list').innerHTML=water.entries.length?[...water.entries].reverse().map(entry=>`<div class="water-entry"><span class="water-entry-drop">${waterIcon('drop')}</span><div><strong>+ ${numberRu(entry.amountMl)} мл</strong><span>${new Date(entry.createdAt).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'})}</span></div><button class="water-remove-entry" data-remove-water="${escapeHTML(entry.id)}" aria-label="Удалить запись ${entry.amountMl} мл">${icon('x')}</button></div>`).join(''):'<div class="water-empty">Первый стакан ждёт своего момента.<br>Отметь воду или другой напиток, когда выпьешь.</div>';
  $('#water-retry').hidden=!pendingWaterEntry;
  const last7=Array.from({length:7},(_,i)=>shiftDate(today,i-6));
  $('#water-week').innerHTML=last7.map(day=>{
    const key=dateKey(day),record=water.history.find(item=>item.day===key),value=record?.totalMl||0,goal=record?.goalMl||water.goalMl,pct=Math.min(100,value/goal*100);
    return `<div class="water-week-day ${key===todayKey?'current':''}" title="${day.toLocaleDateString('ru-RU')}: ${value} / ${goal} мл"><span class="water-week-volume">${value?numberRu(value/1000):'—'}</span><div class="water-week-track"><i style="height:${pct}%"></i></div><span>${dayNames[(day.getDay()+6)%7]}</span></div>`;
  }).join('');
}
function openWaterSettings(){
  if(!ready||saving)return;
  const profile=state.water?.profile;
  $('#water-height').value=profile?.heightCm||'';$('#water-weight').value=profile?.weightKg||'';
  $('#water-goal-input').value=profile?.goalMl||1750;$('#water-adult').checked=Boolean(profile);
  $('#water-settings-error').textContent='';updateGoalPreview();$('#water-settings-dialog').showModal();
}
function updateGoalPreview(){
  const ml=Number($('#water-goal-input').value)||0;
  $('#water-goal-preview').textContent=`${numberRu(ml/250)} ${plural(Math.round(ml/250),['стакан','стакана','стаканов'])} · ${numberRu(ml/1000)} л`;
  document.querySelectorAll('[data-water-goal]').forEach(button=>{
    button.classList.toggle('selected',Number(button.dataset.waterGoal)===ml);
    button.setAttribute('aria-pressed',Number(button.dataset.waterGoal)===ml);
  });
}
['#water-start','#water-edit-profile'].forEach(selector=>$(selector).addEventListener('click',openWaterSettings));
$('#water-close-settings').addEventListener('click',()=>$('#water-settings-dialog').close());
$('#water-goal-input').addEventListener('input',updateGoalPreview);
document.querySelectorAll('[data-water-goal]').forEach(button=>button.addEventListener('click',()=>{$('#water-goal-input').value=button.dataset.waterGoal;updateGoalPreview();}));
$('#water-settings-form').addEventListener('submit',async event=>{
  event.preventDefault();if(saving||waterWorking)return;
  waterWorking=true;$('#water-save-settings').disabled=true;$('#water-settings-error').textContent='';
  const data={heightCm:Number($('#water-height').value),weightKg:Number($('#water-weight').value),goalMl:Number($('#water-goal-input').value),adult:$('#water-adult').checked};
  try {
    if(await persist('/api/water/settings','PUT',data)){$('#water-settings-dialog').close();toast('Твой водный ритм настроен 💧');}
    else $('#water-settings-error').textContent='Настройки не сохранены. Повтори попытку.';
  }finally{waterWorking=false;$('#water-save-settings').disabled=false;}
});
document.querySelectorAll('[data-water-amount]').forEach(button=>button.addEventListener('click',()=>{
  waterAmount=Number(button.dataset.waterAmount);
  document.querySelectorAll('[data-water-amount]').forEach(el=>{el.classList.toggle('selected',el===button);el.setAttribute('aria-pressed',el===button);});
  $('#water-add-label').textContent=`Добавить ${waterAmount} мл`;
}));
async function addWater(){
  if(!ready||saving||waterWorking)return;
  if(pendingWaterEntry&&pendingWaterEntry.amountMl!==waterAmount){toast('Повтори сохранение предыдущей записи, чтобы не потерять стакан.');return;}
  waterWorking=true;$('#water-add').disabled=true;
  const previous=state.water?.totalMl||0,goal=state.water?.goalMl||1750;
  pendingWaterEntry=pendingWaterEntry||{id:crypto.randomUUID(),amountMl:waterAmount};
  try {
    if(await persist('/api/water/entries','POST',pendingWaterEntry)){
      pendingWaterEntry=null;renderWater();
      $('#human-visual').classList.remove('water-splash');void $('#human-visual').offsetWidth;$('#human-visual').classList.add('water-splash');
      if(previous<goal&&state.water.totalMl>=goal){celebrate();toast('Твоя цель на сегодня выполнена 💧');}
      else toast('Ещё один глоток заботы о себе 💧');
    }else renderWater();
  }finally{waterWorking=false;$('#water-add').disabled=false;}
}
$('#water-add').addEventListener('click',addWater);
$('#water-retry').addEventListener('click',()=>{if(pendingWaterEntry){waterAmount=pendingWaterEntry.amountMl;addWater();}});
$('#water-entry-list').addEventListener('click',async event=>{
  const button=event.target.closest('[data-remove-water]');if(!button||saving||waterWorking)return;
  if(pendingWaterEntry){toast('Сначала повтори сохранение предыдущего стакана.');return;}
  waterWorking=true;button.disabled=true;
  try{if(await persist(`/api/water/entries/${encodeURIComponent(button.dataset.removeWater)}`,'DELETE',{}))toast('Запись убрана из сегодняшнего прогресса');}
  finally{waterWorking=false;if(button.isConnected)button.disabled=false;}
});
