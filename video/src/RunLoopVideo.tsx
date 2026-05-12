import React from "react";
import { AbsoluteFill } from "remotion";
import { RunLoopScene } from "./scenes/RunLoopScene";
import { LangContext, type Lang } from "./i18n";

type Props = { lang?: Lang };

/**
 * Standalone composition for the run-loop demo. Embedded in README.md as the
 * visual explanation of what RunScreen does on every sprint delivery. The
 * `lang` prop drives all scene strings via i18n context.
 */
export const RunLoopVideo: React.FC<Props> = ({ lang = "pt" }) => (
  <LangContext.Provider value={lang}>
    <AbsoluteFill style={{ background: "#03050d" }}>
      <RunLoopScene />
    </AbsoluteFill>
  </LangContext.Provider>
);

export const RUN_LOOP_DURATION = 660; // 22s @ 30fps
