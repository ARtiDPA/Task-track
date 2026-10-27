globalThis.RitmoFinanceMath=Object.freeze({
  parseAmount(value,signed=false){
    const text=String(value).trim().replace(/[\s\u00a0\u202f]/g,'');
    const pattern=signed?/^-?\d{1,10}([.,]\d{1,2})?$/:/^\d{1,10}([.,]\d{1,2})?$/;
    if(!pattern.test(text))throw new Error('Введи сумму с точностью до копеек, например 1 250,50.');
    const negative=text.startsWith('-'),[rubles,kopecks='']=text.replace('-','').replace(',','.').split('.');
    const amount=(Number(rubles)*100+Number(kopecks.padEnd(2,'0')))*(negative?-1:1);
    if(!Number.isSafeInteger(amount)||Math.abs(amount)>100000000000)throw new Error('Сумма слишком большая.');
    return amount;
  },
  summarize(data,month,today){
    const entries=data.transactions||[],categories=data.categories||[],current=month===today.slice(0,7);
    const [year,mo]=month.split('-').map(Number),days=new Date(year,mo,0).getDate(),elapsed=current?Number(today.slice(8)):days;
    const selected=entries.filter(entry=>entry.day.startsWith(month));
    const income=selected.filter(e=>e.kind==='income').reduce((s,e)=>s+e.amountKopecks,0);
    const expenses=selected.filter(e=>e.kind==='expense').reduce((s,e)=>s+e.amountKopecks,0);
    const balance=data.openingBalanceKopecks+entries.reduce((s,e)=>s+(e.kind==='income'?1:-1)*e.amountKopecks,0);
    const groups=categories.filter(c=>c.kind==='expense').map(category=>({...category,total:selected.filter(e=>e.categoryId===category.id).reduce((s,e)=>s+e.amountKopecks,0)})).sort((a,b)=>b.total-a.total);
    const budget=data.monthlyBudgetKopecks||0,remaining=budget-expenses;
    const reserved=data.reservedKopecks||0,freeBalance=balance-reserved;
    const available=Math.max(0,budget?Math.min(freeBalance,remaining):freeBalance);
    const daysLeft=current?days-elapsed+1:0;
    const series=[];
    let running=data.openingBalanceKopecks+entries.filter(e=>e.day<month+'-01').reduce((s,e)=>s+(e.kind==='income'?1:-1)*e.amountKopecks,0);
    for(let day=1;day<=elapsed;day++){
      const key=month+'-'+String(day).padStart(2,'0');
      const daily=selected.filter(e=>e.day===key);
      const added=daily.filter(e=>e.kind==='income').reduce((s,e)=>s+e.amountKopecks,0);
      const spent=daily.filter(e=>e.kind==='expense').reduce((s,e)=>s+e.amountKopecks,0);
      running+=added-spent;series.push({day:key,balance:running,income:added,expenses:spent});
    }
    return {selected,income,expenses,balance,freeBalance,reserved,groups,budget,remaining,daysLeft,dailyAvailable:daysLeft?Math.floor(available/daysLeft):0,
      projected:elapsed?Math.round(expenses/elapsed*days):0,series,current,elapsed,days};
  }
});
