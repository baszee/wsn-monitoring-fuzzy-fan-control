// Warna kipas: ungu (keputusan kendali), abu-abu saat tidak tersedia.
// Kipas canvas bersama. Putaran sebanding dengan PWM; diam saat 0%; abu-abu saat tidak tersedia.
export function createFan(canvas) {
  const ctx = canvas.getContext("2d");
  const S = 200, C = 100, R = 94;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = S * dpr;
  canvas.height = S * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let target = 0, current = 0, angle = 0, last = null, disabled = false;

  function draw() {
    ctx.clearRect(0, 0, S, S);

    ctx.beginPath();
    ctx.arc(C, C, R, 0, Math.PI * 2);
    ctx.fillStyle = disabled ? "#f1f5f9" : "#f7f4ff";
    ctx.fill();
    ctx.strokeStyle = disabled ? "#e2e8f0" : "#e4dafc";
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.save();
    ctx.translate(C, C);
    ctx.rotate((angle * Math.PI) / 180);
    ctx.scale(1.2, 1.2);
    for (let i = 0; i < 4; i++) {
      ctx.save();
      ctx.rotate((i * Math.PI) / 2);
      const g = ctx.createLinearGradient(0, 0, 60, -30);
      g.addColorStop(0, disabled ? "#94a3b8" : "#5912ec");
      g.addColorStop(1, disabled ? "#cbd5e1" : "#9b7cf7");
      ctx.beginPath();
      ctx.moveTo(8, 0);
      ctx.bezierCurveTo(12, -20, 50, -35, 65, -20);
      ctx.bezierCurveTo(72, -12, 55, 5, 40, 8);
      ctx.bezierCurveTo(25, 12, 8, 18, 8, 0);
      ctx.fillStyle = g;
      ctx.globalAlpha = 0.9;
      ctx.fill();
      ctx.restore();
    }
    ctx.restore();

    ctx.beginPath();
    ctx.arc(C, C, 14, 0, Math.PI * 2);
    ctx.fillStyle = disabled ? "#94a3b8" : "#4a0fcb";
    ctx.fill();
  }

  function frame(ts) {
    if (last === null) last = ts;
    const dt = Math.min((ts - last) / 1000, 0.1);
    last = ts;
    current += (target - current) * (1 - Math.pow(0.02, dt));
    if (Math.abs(target - current) < 0.05) current = target;
    if (!still) angle = (angle + (current / 100) * 720 * dt) % 360;
    draw();
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  return {
    setTarget(pwm, isDisabled = false) {
      target = Math.max(0, Math.min(100, Number(pwm) || 0));
      disabled = isDisabled;
    },
  };
}
