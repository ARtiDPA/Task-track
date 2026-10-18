// Shared date arithmetic for the calendar, debt forecast and savings estimates.
globalThis.RitmoSchedule=Object.freeze({
  monthly(day,anchor,offset=0){
    const [y,m]=day.split('-').map(Number),first=new Date(Date.UTC(y,m-1+offset,1));
    const last=new Date(Date.UTC(first.getUTCFullYear(),first.getUTCMonth()+1,0)).getUTCDate();
    first.setUTCDate(Math.min(anchor,last));return first.toISOString().slice(0,10);
  },
  savingsForecast(pot,today){
    const remaining=Math.max(0,pot.targetKopecks-pot.balanceKopecks),amount=pot.contributionKopecks;
    if(!pot.targetKopecks)return {status:'reserve'};
    if(!remaining)return {status:'reached',day:today,count:0,days:0};
    if(!amount||!pot.contributionStartDay)return {status:'unconfigured'};
    const start=pot.contributionStartDay,monthly=pot.contributionInterval==='month',step=pot.contributionInterval==='week'?7:1;
    const ms=day=>Date.parse(day+'T12:00:00Z'),anchor=Number(start.slice(8));
    const dateAt=index=>monthly?this.monthly(start,anchor,index):new Date(ms(start)+index*step*86400000).toISOString().slice(0,10);
    let skipped=monthly?Math.max(0,(Number(today.slice(0,4))-Number(start.slice(0,4)))*12+Number(today.slice(5,7))-Number(start.slice(5,7))):Math.max(0,Math.ceil((ms(today)-ms(start))/(86400000*step)));
    if(monthly&&dateAt(skipped)<today)skipped++;
    const count=Math.ceil(remaining/amount),lastIndex=skipped+count-1;
    const maxIndex=monthly?(2100-Number(start.slice(0,4)))*12+12-Number(start.slice(5,7)):Math.floor((ms('2100-12-31')-ms(start))/(86400000*step));
    if(lastIndex>maxIndex)return {status:'distant',count};
    const firstDay=dateAt(skipped),day=dateAt(lastIndex),days=Math.round((ms(day)-ms(today))/86400000);
    const points=Array.from({length:Math.min(6,count)+1},(_,i)=>{
      const n=Math.round(i*count/Math.min(6,count));return {count:n,balance:Math.min(pot.targetKopecks,pot.balanceKopecks+n*amount),day:n?dateAt(skipped+n-1):today};
    });
    return {status:'scheduled',count,firstDay,day,days,lastContribution:remaining-(count-1)*amount,points};
  },
  debtOccurrences(debt,end,from='1900-01-01'){
    const rows=[];let day=debt.dueDay,remaining=debt.remainingKopecks,amount=debt.paymentKopecks||remaining;
    if(!day||remaining<=0)return rows;
    const repeating=debt.monthlyDay>0&&debt.monthlyPaymentKopecks>0;
    // At most 2,412 months in the supported date range. Never expand beyond the horizon.
    for(let i=0;day<=end&&remaining>0&&i<2413;i++){
      const payment=Math.min(amount,remaining);
      if(day>=from)rows.push({day,amount:payment});remaining-=payment;
      if(!repeating)break;
      day=this.monthly(day,debt.monthlyDay,1);amount=debt.monthlyPaymentKopecks;
    }
    return rows;
  }
});
