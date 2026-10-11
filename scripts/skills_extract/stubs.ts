// Classes factices pour exécuter heroes.ts (E7Calc, licence ISC) hors de son application.
// Extraction des multiplicateurs (exécution des fonctions avec des conditions neutres)
class Hero { o: any; constructor(o: any) { this.o = o; } }
class Skill { o: any; constructor(o: any) { this.o = o; } }
class AftermathSkill { o: any; constructor(o: any) { this.o = o; } }
class Artifact {}
type DamageFormData = any;
const named = () => new Proxy({}, { get: (_t, p) => String(p) });
const HeroClass: any = named(), HeroElement: any = named(), DoT: any = named(), HitType: any = named();
// TODO: don't have separate entries for target and caster for the same condition
