// Plain-English tiers for the 0–100 strength score. Thresholds line up with
// the how-it-works copy: "strong calls" are leans with strength 60+.
export type StrengthTierId = "coinflip" | "slight" | "solid" | "strong";

export interface StrengthTier {
  id: StrengthTierId;
  label: string;
  /** One-liner used in tooltips. */
  blurb: string;
}

const TIERS: { min: number; tier: StrengthTier }[] = [
  {
    min: 60,
    tier: {
      id: "strong",
      label: "Strong",
      blurb: "The model leans hard — its strongest class of call.",
    },
  },
  {
    min: 40,
    tier: {
      id: "solid",
      label: "Solid",
      blurb: "A clear lean, but with real room for the other side.",
    },
  },
  {
    min: 15,
    tier: {
      id: "slight",
      label: "Slight",
      blurb: "The model tilts one way, barely.",
    },
  },
  {
    min: 0,
    tier: {
      id: "coinflip",
      label: "Coin flip",
      blurb: "Basically 50/50 — the model has no real opinion.",
    },
  },
];

export function strengthTier(value: number): StrengthTier {
  for (const { min, tier } of TIERS) {
    if (value >= min) return tier;
  }
  return TIERS[TIERS.length - 1].tier;
}

/** "Coin flip (0–14), Slight (15–39), Solid (40–59), Strong (60+)" — for tooltips. */
export const TIER_SCALE_COPY =
  "Coin flip (0–14), Slight (15–39), Solid (40–59), Strong (60+)";
