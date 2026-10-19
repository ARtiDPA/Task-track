// Audio is unlocked by Start / Resume / Check sound, then scheduled on the audio clock.
globalThis.RitmoFocusSound=(()=>{
  let context=null,alarm=null,pending=null;const notified=new Set(),voices=new Set();
  const status=()=>window.dispatchEvent(new CustomEvent('ritmo:focus-sound-status',{detail:{ready:context?.state==='running',pending:Boolean(pending),supported:Boolean(globalThis.AudioContext||globalThis.webkitAudioContext)}}));
  function stop(chime){if(!chime)return;for(const node of chime.nodes){node.onended=null;try{node.stop();}catch{}try{node.disconnect();node.focusGain.disconnect();}catch{}voices.delete(node);}if(alarm===chime)alarm=null;}
  function mark(id){if(!id||notified.has(id))return;notified.add(id);if(notified.size>200)notified.delete(notified.values().next().value);window.dispatchEvent(new CustomEvent('ritmo:focus-sound',{detail:{sessionId:id}}));}
  function chime(at,id=null){
    const result={id,at,nodes:[]};
    [523.25,659.25,783.99].forEach((frequency,i)=>{
      const oscillator=context.createOscillator(),gain=context.createGain(),start=at+i*.28;
      oscillator.type='sine';oscillator.frequency.setValueAtTime(frequency,start);
      gain.gain.setValueAtTime(0,start);gain.gain.linearRampToValueAtTime(.16,start+.025);gain.gain.exponentialRampToValueAtTime(.001,start+.55);
      oscillator.connect(gain);gain.connect(context.destination);oscillator.start(start);oscillator.stop(start+.6);
      oscillator.focusGain=gain;result.nodes.push(oscillator);voices.add(oscillator);
      oscillator.onended=()=>{if(i===0)mark(id);voices.delete(oscillator);oscillator.disconnect();gain.disconnect();if(i===2&&alarm===result)alarm=null;};
    });return result;
  }
  async function unlock(test=false){
    try{
      const Constructor=globalThis.AudioContext||globalThis.webkitAudioContext;if(!Constructor){status();return false;}
      if(!context||context.state==='closed')context=new Constructor();
      if(context.state!=='running')await context.resume();
      if(context.state!=='running'){status();return false;}
      if(pending){chime(context.currentTime+.03,pending);pending=null;}
      else if(test)chime(context.currentTime+.03);
      status();return true;
    }catch{status();return false;}
  }
  function sync(active){
    if(alarm&&notified.has(alarm.id))return; // Let an already triggered chime ring out.
    if(!active||active.status!=='running'||!context||context.state!=='running'){stop(alarm);return;}
    if(notified.has(active.id))return;
    const at=context.currentTime+Math.max(0,active.remainingMs)/1000;
    if(alarm?.id===active.id&&Math.abs(alarm.at-at)<1.5)return;
    stop(alarm);alarm=chime(at,active.id);
  }
  function complete(id){
    if(!id||notified.has(id))return;
    mark(id);
    if(context?.state==='running'){
      if(!alarm||alarm.id!==id||Math.abs(alarm.at-context.currentTime)>1.5){stop(alarm);alarm=chime(context.currentTime+.03,id);}
    }else{stop(alarm);pending=id;}
    status();
  }
  function reset(){stop(alarm);for(const node of voices){node.onended=null;try{node.stop();node.disconnect();node.focusGain.disconnect();}catch{}}voices.clear();notified.clear();pending=null;status();}
  return Object.freeze({unlock,sync,complete,reset});
})();
