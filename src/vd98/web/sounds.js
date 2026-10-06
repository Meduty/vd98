// Original retro-style cues synthesized with Web Audio (no sound assets shipped).
const Sounds = (() => {
  let ctx = null;

  function audio() {
    if (!ctx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return null;
      ctx = new Ctx();
    }
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  }

  // notes: [frequencyHz, startSec, durationSec]
  function play(notes, type = "square", volume = 0.08) {
    const ac = audio();
    if (!ac) return;
    const t0 = ac.currentTime + 0.01;
    for (const [freq, start, dur] of notes) {
      const osc = ac.createOscillator();
      const gain = ac.createGain();
      osc.type = type;
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0, t0 + start);
      gain.gain.linearRampToValueAtTime(volume, t0 + start + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + start + dur);
      osc.connect(gain).connect(ac.destination);
      osc.start(t0 + start);
      osc.stop(t0 + start + dur + 0.02);
    }
  }

  return {
    start: () => play([[523.25, 0, 0.08], [659.25, 0.07, 0.12]]),
    done: () => play([[392, 0, 0.18], [523.25, 0.12, 0.18], [659.25, 0.24, 0.18], [783.99, 0.36, 0.45]], "triangle", 0.12),
    error: () => play([[220, 0, 0.25], [207.65, 0, 0.25], [164.81, 0.18, 0.35]], "sawtooth", 0.05),
    click: () => play([[1200, 0, 0.02]], "square", 0.03),
  };
})();
