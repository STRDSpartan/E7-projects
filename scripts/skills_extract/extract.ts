// Exécute les fonctions de chaque compétence avec des conditions neutres → JSON sur stdout.
const stats: Record<string, number> = {};
const iv: any = new Proxy({}, {
  get: (_t, p: any) => {
    const k = String(p);
    if (k.startsWith("casterFinal") || k.startsWith("targetFinal")) return () => stats[k] ?? 0;
    if (k === "inputOverrides") return {};
    return 0;
  },
});
const art: any = new Proxy({}, { get: () => () => 0 });
const call = (f: any, ...a: any[]) => { try { const v = typeof f === "function" ? f(...a) : f; return typeof v === "number" && isFinite(v) ? Math.round(v * 1e6) / 1e6 : (typeof v === "boolean" ? v : null); } catch { return null; } };
const out: any = {};
let bad = 0;
for (const [key, hero] of Object.entries(Heroes as any)) {
  const h: any = (hero as any).o;
  const skills: any = {};
  for (const [sid, sk] of Object.entries(h.skills || {})) {
    const s: any = (sk as any).o;
    if (!s.rate) continue; // compétence sans dégâts directs
    const flat: any = {};
    for (const stat of ["casterFinalMaxHP", "casterFinalDefense", "casterFinalSpeed", "targetFinalMaxHP"]) {
      for (const k of Object.keys(stats)) delete stats[k];
      stats[stat] = 1000;
      const v = call(s.flat, false, iv, art);
      if (v) flat[stat.replace("casterFinal", "caster_").replace("targetFinal", "target_")] = Math.round(v / 1000 * 1e6) / 1e6;
    }
    for (const k of Object.keys(stats)) delete stats[k];
    const tips = (f: any) => { try { return f ? Object.keys(f(false) || {}) : []; } catch { return []; } };
    const e: any = {
      rate: call(s.rate, false, iv, false), pow: call(s.pow, false, iv) ?? 1,
      enhance: s.enhance || [], aoe: !!call(s.isAOE, iv, false), single: !!call(s.isSingle, iv, false),
      pen: call(s.penetrate, false, iv, art, 0, 0) ?? 0, no_crit: !!s.noCrit,
    };
    if (s.soulburn) { e.rate_sb = call(s.rate, true, iv, false); e.pow_sb = call(s.pow, true, iv) ?? e.pow; }
    if (Object.keys(flat).length) e.flat = flat;
    const cond = [...tips(s.multTip), ...tips(s.penetrateTip), ...tips(s.rateTip), ...tips(s.powTip), ...tips(s.flatTip)];
    if (s.mult || s.fixed || s.aftermath || s.detonate) e.conditional = cond.length ? cond : ["oui"];
    if (e.rate === null) bad++;
    skills[sid] = e;
  }
  out[key] = { element: h.element, class: h.class, base: { atk: h.baseAttack, hp: h.baseHP, def: h.baseDefense }, skills };
}
console.error("héros", Object.keys(out).length, "compétences sans taux lisible", bad);
console.log(JSON.stringify(out));
