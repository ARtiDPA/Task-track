/* A habit only contributes to the denominator from its creation date onward. */
globalThis.RitmoMetrics = Object.freeze({
  activeOn(habits, day) {
    return habits.filter(habit => habit.createdAt <= day);
  },
  rate(habits, days) {
    let possible = 0, completed = 0;
    for (const day of days) {
      for (const habit of habits) {
        if (habit.createdAt > day) continue;
        possible++;
        if (habit.logs.includes(day)) completed++;
      }
    }
    return possible ? Math.round(completed / possible * 100) : 0;
  },
  creationDate(habit, today) {
    const valid = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && value <= today &&
      !Number.isNaN(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
    if (valid(habit.createdAt)) return habit.createdAt;
    // Legacy habits did not record creation time. Use their oldest real mark.
    return (habit.logs || []).filter(valid).sort()[0] || today;
  }
});
