globalThis.RitmoFocus=Object.freeze({
  summary(data,today,period=7){
    const dayMs=86400000,start=Date.parse(today+'T12:00:00Z'),daily=new Map((data.daily||[]).map(d=>[d.day,d.milliseconds]));
    const series=Array.from({length:period},(_,i)=>{const day=new Date(start-(period-1-i)*dayMs).toISOString().slice(0,10);return {day,milliseconds:daily.get(day)||0};});
    let streak=0,cursor=start;if((daily.get(today)||0)<60000)cursor-=dayMs;
    while((daily.get(new Date(cursor).toISOString().slice(0,10))||0)>=60000){streak++;cursor-=dayMs;}
    const todayMs=daily.get(today)||0,periodMs=series.reduce((s,d)=>s+d.milliseconds,0);
    return {series,todayMs,periodMs,streak,goalPercent:Math.min(100,todayMs/((data.settings?.goalMinutes||120)*60000)*100),activeDays:series.filter(d=>d.milliseconds>=60000).length};
  }
});
