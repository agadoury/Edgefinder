// All 32 NFL teams, keyed by canonical nfldata team codes (LA, WAS, JAX, LV, …).
// Colors are hardcoded — no external logos or assets anywhere in the app.

export interface TeamInfo {
  name: string;
  city: string;
  primary: string;
  secondary: string;
}

export const TEAMS: Record<string, TeamInfo> = {
  ARI: { name: "Cardinals", city: "Arizona", primary: "#97233F", secondary: "#FFB612" },
  ATL: { name: "Falcons", city: "Atlanta", primary: "#A71930", secondary: "#A5ACAF" },
  BAL: { name: "Ravens", city: "Baltimore", primary: "#241773", secondary: "#9E7C0C" },
  BUF: { name: "Bills", city: "Buffalo", primary: "#00338D", secondary: "#C60C30" },
  CAR: { name: "Panthers", city: "Carolina", primary: "#0085CA", secondary: "#101820" },
  CHI: { name: "Bears", city: "Chicago", primary: "#0B162A", secondary: "#C83803" },
  CIN: { name: "Bengals", city: "Cincinnati", primary: "#FB4F14", secondary: "#101820" },
  CLE: { name: "Browns", city: "Cleveland", primary: "#311D00", secondary: "#FF3C00" },
  DAL: { name: "Cowboys", city: "Dallas", primary: "#003594", secondary: "#869397" },
  DEN: { name: "Broncos", city: "Denver", primary: "#FB4F14", secondary: "#002244" },
  DET: { name: "Lions", city: "Detroit", primary: "#0076B6", secondary: "#B0B7BC" },
  GB: { name: "Packers", city: "Green Bay", primary: "#203731", secondary: "#FFB612" },
  HOU: { name: "Texans", city: "Houston", primary: "#03202F", secondary: "#A71930" },
  IND: { name: "Colts", city: "Indianapolis", primary: "#002C5F", secondary: "#A2AAAD" },
  JAX: { name: "Jaguars", city: "Jacksonville", primary: "#006778", secondary: "#D7A22A" },
  KC: { name: "Chiefs", city: "Kansas City", primary: "#E31837", secondary: "#FFB81C" },
  LA: { name: "Rams", city: "Los Angeles", primary: "#003594", secondary: "#FFA300" },
  LAC: { name: "Chargers", city: "Los Angeles", primary: "#0080C6", secondary: "#FFC20E" },
  LV: { name: "Raiders", city: "Las Vegas", primary: "#101820", secondary: "#A5ACAF" },
  MIA: { name: "Dolphins", city: "Miami", primary: "#008E97", secondary: "#FC4C02" },
  MIN: { name: "Vikings", city: "Minnesota", primary: "#4F2683", secondary: "#FFC62F" },
  NE: { name: "Patriots", city: "New England", primary: "#002244", secondary: "#C60C30" },
  NO: { name: "Saints", city: "New Orleans", primary: "#101820", secondary: "#D3BC8D" },
  NYG: { name: "Giants", city: "New York", primary: "#0B2265", secondary: "#A71930" },
  NYJ: { name: "Jets", city: "New York", primary: "#125740", secondary: "#FFFFFF" },
  PHI: { name: "Eagles", city: "Philadelphia", primary: "#004C54", secondary: "#A5ACAF" },
  PIT: { name: "Steelers", city: "Pittsburgh", primary: "#101820", secondary: "#FFB612" },
  SEA: { name: "Seahawks", city: "Seattle", primary: "#002244", secondary: "#69BE28" },
  SF: { name: "49ers", city: "San Francisco", primary: "#AA0000", secondary: "#B3995D" },
  TB: { name: "Buccaneers", city: "Tampa Bay", primary: "#D50A0A", secondary: "#34302B" },
  TEN: { name: "Titans", city: "Tennessee", primary: "#0C2340", secondary: "#4B92DB" },
  WAS: { name: "Commanders", city: "Washington", primary: "#5A1414", secondary: "#FFB612" },
};

export function team(code: string): TeamInfo {
  return TEAMS[code] ?? { name: code, city: code, primary: "#334155", secondary: "#94a3b8" };
}

/** Full display name, e.g. "Buffalo Bills". */
export function teamFullName(code: string): string {
  const t = team(code);
  return `${t.city} ${t.name}`;
}

/** Pick a readable initials color for a monogram sitting on the team's primary color. */
export function monogramInk(primary: string): string {
  const hex = primary.replace("#", "");
  const r = parseInt(hex.slice(0, 2), 16) / 255;
  const g = parseInt(hex.slice(2, 4), 16) / 255;
  const b = parseInt(hex.slice(4, 6), 16) / 255;
  const lin = (c: number) => (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
  const lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  return lum > 0.35 ? "#0b1220" : "#ffffff";
}

export function initials(name: string): string {
  const parts = name.replace(/\./g, "").split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
