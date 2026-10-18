globalThis.RitmoPlanner=Object.freeze({
  calculate(finance,organizer,today,end,options={}){
    const startMs=Date.parse(today+'T12:00:00Z'),endMs=Date.parse(end+'T12:00:00Z');
    const days=Math.round((endMs-startMs)/86400000)+1;
    if(!/^\d{4}-\d{2}-\d{2}$/.test(end)||!Number.isFinite(days)||days<1||days>366||new Date(endMs).toISOString().slice(0,10)!==end)throw new Error('Выбери дату от сегодняшней до года вперёд.');
    const includeIncome=options.includeIncome!==false,includeDebts=options.includeDebts!==false;
    const balance=finance.openingBalanceKopecks+(finance.transactions||[]).reduce((sum,t)=>sum+(t.kind==='income'?1:-1)*t.amountKopecks,0);
    const reserved=organizer.reservedKopecks||0,free=balance-reserved;
    const items=[];
    for(const plan of organizer.plans||[]){
      if(plan.status!=='pending'||plan.day>end||(plan.kind==='income'&&!includeIncome))continue;
      items.push({id:plan.id,day:plan.day<today?today:plan.day,originalDay:plan.day,name:plan.name,kind:plan.kind,amount:plan.amountKopecks,source:'plan'});
    }
    if(includeDebts)for(const debt of organizer.debts||[]){
      if(debt.remainingKopecks<=0||!debt.dueDay||debt.dueDay>end||(debt.direction==='owed'&&!includeIncome))continue;
      for(const occurrence of RitmoSchedule.debtOccurrences(debt,end))items.push({id:debt.id,day:occurrence.day<today?today:occurrence.day,originalDay:occurrence.day,name:debt.name,kind:debt.direction==='owe'?'expense':'income',amount:occurrence.amount,source:'debt'});
    }
    items.sort((a,b)=>a.day.localeCompare(b.day)||a.kind.localeCompare(b.kind));
    const income=items.filter(i=>i.kind==='income').reduce((s,i)=>s+i.amount,0),expenses=items.filter(i=>i.kind==='expense').reduce((s,i)=>s+i.amount,0);
    const changes=new Map();for(const item of items)changes.set(item.day,(changes.get(item.day)||0)+(item.kind==='income'?1:-1)*item.amount);
    let running=free,daily=Infinity,firstShortfall=null;const series=[];
    for(let i=0;i<days;i++){
      const day=new Date(startMs+i*86400000).toISOString().slice(0,10);running+=changes.get(day)||0;
      daily=Math.min(daily,Math.floor(running/(i+1)));
      if(running<0&&!firstShortfall)firstShortfall=day;
      series.push({day,balance:running});
    }
    daily=Math.max(0,daily);
    return {days,balance,reserved,free,income,expenses,ending:running,daily,week:daily*Math.min(7,days),period:daily*days,firstShortfall,series,items,
      overdue:items.filter(i=>i.originalDay<today).length,undatedDebts:(organizer.debts||[]).filter(d=>d.remainingKopecks>0&&!d.dueDay).length};
  }
});
