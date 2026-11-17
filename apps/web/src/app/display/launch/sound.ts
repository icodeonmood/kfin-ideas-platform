/**
 * The launch sound (DEC-046, DEC-050; L-DISPLAY.launch/4): a bell at 0:00, then a soft crackle as the spark rises at
 * 0:04. Synthesised with Web Audio, only after the operator presses Start (the gesture sound needs); there are no
 * audio files. Shared by the launch screen (S-LAUNCH, /display/launch) and the older /launch until it is retired.
 */
const CRACKLE_AT_S = 4;

/**
 * One bell tone (a few inharmonic, decaying sine partials), then a soft crackle of short noise bursts. With reduced
 * motion the screen jumps to its last frame, so only the bell plays: no crackle over a still picture (review A4).
 */
export function playSignature(ctx: AudioContext, crackle: boolean) {
  const t0 = ctx.currentTime + 0.05;
  const master = ctx.createGain();
  master.gain.value = 0.32;
  master.connect(ctx.destination);

  const base = 392; // G4
  const partials: [number, number, number][] = [
    [1, 1, 4.5],
    [2.0, 0.42, 3.2],
    [2.76, 0.3, 2.4],
    [5.4, 0.12, 1.4],
  ];
  for (const [ratio, amp, decay] of partials) {
    const osc = ctx.createOscillator();
    const env = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = base * ratio;
    env.gain.setValueAtTime(0.0001, t0);
    env.gain.exponentialRampToValueAtTime(amp, t0 + 0.012);
    env.gain.exponentialRampToValueAtTime(0.0001, t0 + decay);
    osc.connect(env).connect(master);
    osc.start(t0);
    osc.stop(t0 + decay + 0.1);
  }
  if (!crackle) return;

  const noise = ctx.createBuffer(1, Math.floor(ctx.sampleRate * 0.05), ctx.sampleRate);
  const data = noise.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  let at = t0 + CRACKLE_AT_S;
  for (let i = 0; i < 16; i++) {
    const src = ctx.createBufferSource();
    const band = ctx.createBiquadFilter();
    const env = ctx.createGain();
    src.buffer = noise;
    band.type = "bandpass";
    band.frequency.value = 2500 + Math.random() * 4000;
    band.Q.value = 6;
    const peak = 0.05 + Math.random() * 0.12;
    env.gain.setValueAtTime(0.0001, at);
    env.gain.exponentialRampToValueAtTime(peak, at + 0.004);
    env.gain.exponentialRampToValueAtTime(0.0001, at + 0.04);
    src.connect(band).connect(env).connect(master);
    src.start(at);
    src.stop(at + 0.05);
    at += 0.04 + Math.random() * 0.1;
  }
}
