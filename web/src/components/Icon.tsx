import React from "react";
import Svg, { Circle, G, Line, Path, Polyline, Rect } from "react-native-svg";
import { theme } from "../theme";

export type IconName =
  | "home"
  | "sprint"
  | "play"
  | "kanban"
  | "folder"
  | "link"
  | "model"
  | "settings"
  | "help"
  | "bell"
  | "compass"
  | "clipboard"
  | "check"
  | "x"
  | "eye"
  | "search"
  | "filter"
  | "chevron-down"
  | "chevron-right"
  | "chevron-left"
  | "arrow-right"
  | "plus"
  | "download"
  | "upload"
  | "refresh"
  | "alert"
  | "lock"
  | "users"
  | "user"
  | "shield"
  | "chart"
  | "doc"
  | "branch"
  | "github"
  | "jira"
  | "azure"
  | "microsoft"
  | "logo"
  | "clock"
  | "calendar"
  | "heart"
  | "pie"
  | "more"
  | "external"
  | "trending"
  | "headset"
  | "sliders";

type Props = {
  name: IconName;
  size?: number;
  color?: string;
  strokeWidth?: number;
};

export const Icon: React.FC<Props> = ({
  name,
  size = 16,
  color = theme.textMuted,
  strokeWidth = 1.6,
}) => {
  const common = {
    stroke: color,
    strokeWidth,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    fill: "none" as const,
  };

  switch (name) {
    case "logo":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path
            d="M16 4 H8 C5.79 4 4 5.79 4 8 V10 C4 12.21 5.79 14 8 14 H16 C18.21 14 20 15.79 20 18 V18 C20 20.21 18.21 22 16 22 H6"
            stroke={color}
            strokeWidth={2.6}
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        </Svg>
      );
    case "home":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M3 11 L12 4 L21 11 V20 a1 1 0 0 1 -1 1 H15 V14 H9 V21 H4 a1 1 0 0 1 -1 -1 Z" {...common} />
        </Svg>
      );
    case "sprint":
    case "clock":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Circle cx="12" cy="12" r="9" {...common} />
          <Polyline points="12 7 12 12 16 14" {...common} />
        </Svg>
      );
    case "play":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M7 5 L19 12 L7 19 Z" {...common} fill={color} />
        </Svg>
      );
    case "kanban":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Rect x="3" y="4" width="6" height="16" rx="1.5" {...common} />
          <Rect x="11" y="4" width="6" height="10" rx="1.5" {...common} />
          <Rect x="19" y="4" width="2" height="14" rx="1" {...common} />
        </Svg>
      );
    case "folder":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M3 7 a2 2 0 0 1 2 -2 H9 L11 7 H19 a2 2 0 0 1 2 2 V18 a2 2 0 0 1 -2 2 H5 a2 2 0 0 1 -2 -2 Z" {...common} />
        </Svg>
      );
    case "link":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M10 14 a4 4 0 0 0 5.66 0 l3.17 -3.17 a4 4 0 0 0 -5.66 -5.66 l-1.17 1.17" {...common} />
          <Path d="M14 10 a4 4 0 0 0 -5.66 0 l-3.17 3.17 a4 4 0 0 0 5.66 5.66 l1.17 -1.17" {...common} />
        </Svg>
      );
    case "model":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Circle cx="12" cy="12" r="9" {...common} />
          <Path d="M12 3 a14 14 0 0 0 0 18" {...common} />
          <Path d="M12 3 a14 14 0 0 1 0 18" {...common} />
          <Line x1="3" y1="12" x2="21" y2="12" {...common} />
        </Svg>
      );
    case "settings":
    case "sliders":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Circle cx="12" cy="12" r="3" {...common} />
          <Path d="M19.4 15 a1.65 1.65 0 0 0 .33 1.82 l.06 .06 a2 2 0 0 1 -2.83 2.83 l-.06 -.06 a1.65 1.65 0 0 0 -1.82 -.33 a1.65 1.65 0 0 0 -1 1.51 V21 a2 2 0 0 1 -4 0 v-.09 A1.65 1.65 0 0 0 9 19.4 a1.65 1.65 0 0 0 -1.82 .33 l-.06 .06 a2 2 0 0 1 -2.83 -2.83 l.06 -.06 a1.65 1.65 0 0 0 .33 -1.82 a1.65 1.65 0 0 0 -1.51 -1 H3 a2 2 0 0 1 0 -4 h.09 A1.65 1.65 0 0 0 4.6 9 a1.65 1.65 0 0 0 -.33 -1.82 l-.06 -.06 a2 2 0 0 1 2.83 -2.83 l.06 .06 a1.65 1.65 0 0 0 1.82 .33 H9 a1.65 1.65 0 0 0 1 -1.51 V3 a2 2 0 0 1 4 0 v.09 a1.65 1.65 0 0 0 1 1.51 a1.65 1.65 0 0 0 1.82 -.33 l.06 -.06 a2 2 0 0 1 2.83 2.83 l-.06 .06 a1.65 1.65 0 0 0 -.33 1.82 V9 a1.65 1.65 0 0 0 1.51 1 H21 a2 2 0 0 1 0 4 h-.09 a1.65 1.65 0 0 0 -1.51 1 Z" {...common} />
        </Svg>
      );
    case "help":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Circle cx="12" cy="12" r="9" {...common} />
          <Path d="M9.5 9 a2.5 2.5 0 1 1 4.5 1.5 c-.7 .8 -2 1.5 -2 2.5" {...common} />
          <Line x1="12" y1="17" x2="12.01" y2="17" {...common} />
        </Svg>
      );
    case "bell":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M18 16 V11 a6 6 0 0 0 -12 0 V16 L4 18 H20 Z" {...common} />
          <Path d="M10 21 a2 2 0 0 0 4 0" {...common} />
        </Svg>
      );
    case "compass":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Circle cx="12" cy="12" r="9" {...common} />
          <Path d="M14.5 9.5 L11 13 L9.5 14.5 L13 11 L14.5 9.5 Z M14.5 9.5 L11 13" {...common} fill={color} />
          <Path d="M9.5 14.5 L13 11" {...common} />
        </Svg>
      );
    case "clipboard":
    case "doc":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Rect x="5" y="4" width="14" height="17" rx="2" {...common} />
          <Path d="M9 4 V2 H15 V4" {...common} />
          <Line x1="8" y1="10" x2="16" y2="10" {...common} />
          <Line x1="8" y1="14" x2="14" y2="14" {...common} />
        </Svg>
      );
    case "check":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Polyline points="5 12 10 17 19 7" {...common} strokeWidth={strokeWidth + 0.5} />
        </Svg>
      );
    case "x":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Line x1="6" y1="6" x2="18" y2="18" {...common} />
          <Line x1="18" y1="6" x2="6" y2="18" {...common} />
        </Svg>
      );
    case "eye":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M1 12 S5 5 12 5 S23 12 23 12 S19 19 12 19 S1 12 1 12 Z" {...common} />
          <Circle cx="12" cy="12" r="3" {...common} />
        </Svg>
      );
    case "search":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Circle cx="11" cy="11" r="7" {...common} />
          <Line x1="21" y1="21" x2="16.65" y2="16.65" {...common} />
        </Svg>
      );
    case "filter":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M3 5 H21 L14 13 V20 L10 18 V13 Z" {...common} />
        </Svg>
      );
    case "chevron-down":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Polyline points="6 9 12 15 18 9" {...common} />
        </Svg>
      );
    case "chevron-right":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Polyline points="9 6 15 12 9 18" {...common} />
        </Svg>
      );
    case "chevron-left":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Polyline points="15 6 9 12 15 18" {...common} />
        </Svg>
      );
    case "arrow-right":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Line x1="5" y1="12" x2="19" y2="12" {...common} />
          <Polyline points="12 5 19 12 12 19" {...common} />
        </Svg>
      );
    case "plus":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Line x1="12" y1="5" x2="12" y2="19" {...common} strokeWidth={strokeWidth + 0.4} />
          <Line x1="5" y1="12" x2="19" y2="12" {...common} strokeWidth={strokeWidth + 0.4} />
        </Svg>
      );
    case "download":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M21 15 V19 a2 2 0 0 1 -2 2 H5 a2 2 0 0 1 -2 -2 V15" {...common} />
          <Polyline points="7 10 12 15 17 10" {...common} />
          <Line x1="12" y1="15" x2="12" y2="3" {...common} />
        </Svg>
      );
    case "upload":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M21 15 V19 a2 2 0 0 1 -2 2 H5 a2 2 0 0 1 -2 -2 V15" {...common} />
          <Polyline points="17 8 12 3 7 8" {...common} />
          <Line x1="12" y1="3" x2="12" y2="15" {...common} />
        </Svg>
      );
    case "refresh":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Polyline points="23 4 23 10 17 10" {...common} />
          <Polyline points="1 20 1 14 7 14" {...common} />
          <Path d="M3.51 9 a9 9 0 0 1 14.85 -3.36 L23 10" {...common} />
          <Path d="M20.49 15 a9 9 0 0 1 -14.85 3.36 L1 14" {...common} />
        </Svg>
      );
    case "alert":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M10.29 3.86 L1.82 18 a2 2 0 0 0 1.71 3 H20.47 a2 2 0 0 0 1.71 -3 L13.71 3.86 a2 2 0 0 0 -3.42 0 Z" {...common} />
          <Line x1="12" y1="9" x2="12" y2="13" {...common} />
          <Line x1="12" y1="17" x2="12.01" y2="17" {...common} />
        </Svg>
      );
    case "lock":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Rect x="4" y="11" width="16" height="11" rx="2" {...common} />
          <Path d="M8 11 V7 a4 4 0 1 1 8 0 V11" {...common} />
        </Svg>
      );
    case "users":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M17 21 V19 a4 4 0 0 0 -4 -4 H5 a4 4 0 0 0 -4 4 V21" {...common} />
          <Circle cx="9" cy="7" r="4" {...common} />
          <Path d="M23 21 V19 a4 4 0 0 0 -3 -3.87" {...common} />
          <Path d="M16 3.13 a4 4 0 0 1 0 7.75" {...common} />
        </Svg>
      );
    case "user":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M20 21 V19 a4 4 0 0 0 -4 -4 H8 a4 4 0 0 0 -4 4 V21" {...common} />
          <Circle cx="12" cy="7" r="4" {...common} />
        </Svg>
      );
    case "shield":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M12 2 L4 5 V11 c0 5 3.5 8.5 8 10 c4.5 -1.5 8 -5 8 -10 V5 Z" {...common} />
        </Svg>
      );
    case "chart":
    case "trending":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Polyline points="3 17 9 11 13 15 21 7" {...common} />
          <Polyline points="14 7 21 7 21 14" {...common} />
        </Svg>
      );
    case "branch":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Line x1="6" y1="3" x2="6" y2="15" {...common} />
          <Circle cx="18" cy="6" r="3" {...common} />
          <Circle cx="6" cy="18" r="3" {...common} />
          <Path d="M18 9 a9 9 0 0 1 -9 9" {...common} />
        </Svg>
      );
    case "github":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path
            d="M12 2 a10 10 0 0 0 -3.16 19.49 c.5 .09 .68 -.22 .68 -.48 v-1.7 c-2.78 .6 -3.37 -1.34 -3.37 -1.34 c-.45 -1.15 -1.11 -1.46 -1.11 -1.46 c-.91 -.62 .07 -.61 .07 -.61 c1 .07 1.53 1.03 1.53 1.03 c.89 1.53 2.34 1.09 2.91 .83 c.09 -.65 .35 -1.09 .63 -1.34 c-2.22 -.25 -4.55 -1.11 -4.55 -4.94 c0 -1.09 .39 -1.98 1.03 -2.68 c-.1 -.25 -.45 -1.27 .1 -2.64 c0 0 .84 -.27 2.75 1.02 a9.5 9.5 0 0 1 5 0 c1.91 -1.29 2.75 -1.02 2.75 -1.02 c.55 1.37 .2 2.39 .1 2.64 c.64 .7 1.03 1.59 1.03 2.68 c0 3.84 -2.34 4.69 -4.57 4.94 c.36 .31 .68 .92 .68 1.85 v2.74 c0 .27 .18 .58 .69 .48 A10 10 0 0 0 12 2"
            fill={color}
          />
        </Svg>
      );
    case "jira":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path
            d="M11.53 2 H22 v10.47 a4.06 4.06 0 0 1 -4.06 4.06 H11.53 Z"
            fill={color}
          />
          <Path
            d="M6.06 7.47 H16.53 V17.94 A4.06 4.06 0 0 1 12.47 22 H6.06 Z"
            fill={color}
            opacity={0.7}
          />
        </Svg>
      );
    case "azure":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path
            d="M14.5 2 L22 12 L14.5 22 L11 19 L17 12 L11 5 Z"
            fill={color}
          />
          <Path d="M11 5 L2 12 L11 19 V14 L8 12 L11 10 Z" fill={color} opacity={0.7} />
        </Svg>
      );
    case "microsoft":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Rect x="2" y="2" width="9.5" height="9.5" fill="#f25022" />
          <Rect x="12.5" y="2" width="9.5" height="9.5" fill="#7fba00" />
          <Rect x="2" y="12.5" width="9.5" height="9.5" fill="#00a4ef" />
          <Rect x="12.5" y="12.5" width="9.5" height="9.5" fill="#ffb900" />
        </Svg>
      );
    case "calendar":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Rect x="3" y="5" width="18" height="16" rx="2" {...common} />
          <Line x1="16" y1="3" x2="16" y2="7" {...common} />
          <Line x1="8" y1="3" x2="8" y2="7" {...common} />
          <Line x1="3" y1="10" x2="21" y2="10" {...common} />
        </Svg>
      );
    case "heart":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M20.84 4.61 a5.5 5.5 0 0 0 -7.78 0 L12 5.67 l-1.06 -1.06 a5.5 5.5 0 0 0 -7.78 7.78 l8.84 8.84 l8.84 -8.84 a5.5 5.5 0 0 0 0 -7.78 Z" {...common} />
        </Svg>
      );
    case "pie":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M21.21 15.89 A10 10 0 1 1 8 2.83" {...common} />
          <Path d="M22 12 A10 10 0 0 0 12 2 V12 Z" {...common} fill={color} />
        </Svg>
      );
    case "more":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Circle cx="12" cy="12" r="1.4" fill={color} stroke="none" />
          <Circle cx="12" cy="5.5" r="1.4" fill={color} stroke="none" />
          <Circle cx="12" cy="18.5" r="1.4" fill={color} stroke="none" />
        </Svg>
      );
    case "external":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M18 13 V19 a2 2 0 0 1 -2 2 H5 a2 2 0 0 1 -2 -2 V8 a2 2 0 0 1 2 -2 H11" {...common} />
          <Polyline points="15 3 21 3 21 9" {...common} />
          <Line x1="10" y1="14" x2="21" y2="3" {...common} />
        </Svg>
      );
    case "headset":
      return (
        <Svg width={size} height={size} viewBox="0 0 24 24">
          <Path d="M3 18 V13 a9 9 0 0 1 18 0 V18" {...common} />
          <Path d="M21 19 a2 2 0 0 1 -2 2 H18 V15 H21 Z M3 19 a2 2 0 0 0 2 2 H6 V15 H3 Z" {...common} />
        </Svg>
      );
    default:
      return null;
  }
};

export default Icon;
