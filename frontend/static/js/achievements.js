globalThis.RitmoAchievements = Object.freeze({
  evaluate(habits,water) {
    const days=[...new Set(habits.flatMap(h=>h.logs))].sort();
    const total=habits.reduce((sum,h)=>sum+h.logs.length,0);
    let best=0;
    for(const habit of habits){
      let previous=null,run=0;
      for(const day of [...habit.logs].sort()){
        const current=Date.parse(day+'T12:00:00Z');
        run=previous!==null&&current-previous===86400000?run+1:1;
        best=Math.max(best,run);previous=current;
      }
    }
    const perfect=days.filter(day=>{
      const active=habits.filter(h=>h.createdAt<=day);
      return active.length&&active.every(h=>h.logs.includes(day));
    }).length;
    const categories=new Set(habits.filter(h=>h.logs.length).map(h=>h.category)).size;
    const weekends=days.filter(day=>[0,6].includes(new Date(day+'T12:00:00Z').getUTCDay())).length;
    const focused=Math.max(0,...habits.map(h=>h.logs.length));
    const items=[];
    function add(id,emoji,name,description,value,target,unit,category){
      items.push({id,emoji,name,description,value,target,unit,category,unlocked:value>=target,percent:Math.min(100,Math.round(value/target*100))});
    }
    add('first','🌱','Первый шаг','Выполни свою первую привычку',total,1,'выполнений','Шаги');
    for(const [target,emoji,name] of [[10,'✨','Уже в движении'],[25,'🌸','Хорошее начало'],[50,'💎','Маленькие победы'],[100,'🚀','Большие перемены'],[250,'🌟','Шаг за шагом'],[500,'🏅','Создавая себя'],[1000,'👑','Тысяча возможностей']])
      add('total-'+target,emoji,name,`Собери ${target} выполнений привычек`,total,target,'выполнений','Шаги');
    for(const [target,emoji,name] of [[3,'🕯️','Зажечь искру'],[7,'🔥','Поймать ритм'],[14,'🎵','Своя мелодия'],[30,'🏆','Сила постоянства'],[60,'🌳','Крепкие корни'],[100,'⚡','Сто дней в ритме'],[365,'☀️','Год с собой']])
      add('streak-'+target,emoji,name,`Поддерживай одну привычку ${target} дней подряд`,best,target,'дней','Серии');
    for(const [target,emoji,name] of [[1,'💫','Идеальный день'],[7,'🌈','Неделя побед'],[30,'🎆','Коллекция идеальных дней']])
      add('perfect-'+target,emoji,name,`Выполни все привычки за день ${target===1?'хотя бы раз':target+' раз'}`,perfect,target,'идеальных дней','Баланс');
    for(const [target,emoji,name] of [[7,'📅','Время для себя'],[30,'🍃','Месяц заботы'],[100,'🌅','Сто новых начал']])
      add('active-'+target,emoji,name,`Отметь привычки в ${target} разных днях`,days.length,target,'активных дней','Баланс');
    add('variety','🎨','Разные грани тебя','Выполни привычки из трёх разных категорий',categories,3,'категорий','Баланс');
    add('focused','🎯','Любимое дело','Выполни одну привычку 50 раз',focused,50,'выполнений','Баланс');
    add('weekends','🌻','Выходные в ритме','Найди время для привычек в два выходных дня',weekends,2,'выходных дня','Баланс');
    const summary=water?.summary||{entries:0,activeDays:0,goalDays:0};
    add('water-first','💧','Первый глоток','Отметь первый напиток в трекере воды',summary.entries,1,'записей','Вода');
    add('water-goal','🌊','Водный ритм','Достигни выбранной дневной цели воды',summary.goalDays,1,'дней с целью','Вода');
    add('water-week','🍵','Неделя глотков','Отмечай напитки в 7 разных днях',summary.activeDays,7,'активных дней','Вода');
    add('water-seven','🐳','На одной волне','Достигни дневной цели в 7 разных днях',summary.goalDays,7,'дней с целью','Вода');
    return items;
  }
});
