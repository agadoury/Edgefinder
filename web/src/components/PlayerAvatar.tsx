"use client";

import { useState } from "react";
import { MonogramAvatar } from "./ui";
import { team } from "../lib/teams";

/**
 * Player portrait on a team-colored backdrop. ESPN headshots are cutout
 * PNGs with transparent backgrounds, so the team gradient shows through
 * behind the player. Any load failure downgrades to the monogram avatar.
 */
export function PlayerAvatar({
  name,
  teamCode,
  size = 36,
  src,
}: {
  name: string;
  teamCode: string;
  size?: number;
  src?: string;
}) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return <MonogramAvatar name={name} teamCode={teamCode} size={size} />;
  }
  const t = team(teamCode);
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full select-none"
      style={{
        width: size,
        height: size,
        background: `linear-gradient(160deg, ${t.primary}, ${t.primary}99)`,
        boxShadow: `inset 0 0 0 2px ${t.secondary}55, 0 0 0 1px rgba(255,255,255,0.10)`,
      }}
    >
      {/* Hotlinked portrait; plain img so a CDN failure can swap to the monogram. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt=""
        loading="lazy"
        draggable={false}
        onError={() => setFailed(true)}
        className="h-full w-full object-cover"
        style={{ objectPosition: "center top" }}
      />
    </span>
  );
}
