// Shared date arithmetic for the calendar, debt forecast and savings estimates.
globalThis.RitmoSchedule=Object.freeze({
  monthly(day,anchor,offset=0){
    const [y,m]=day.split('-').map(Number),first=new Date(Date.UTC(y,m-1+offset,1));
    const last=new Date(Date.UTC(first.getUTCFullYear(),first.getUTCMonth()+1,0)).getUTCDate();
    first.setUTCDate(Math.min(anchor,last));return first.toISOString().slice(0,10);
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
