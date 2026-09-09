---
name: 粤乡智匠
description: 农村学员从技能学习到岗位机会的信息系统原型
colors:
  ink: "#080a0b"
  paper: "#f4f6f6"
  signal: "#18d1ff"
  state: "#c8eb21"
  surface-0: "#050607"
  surface-1: "#0b0f11"
  surface-2: "#101518"
  muted: "#a7b1b4"
  line: "rgb(244 246 246 / 0.18)"
  line-strong: "rgb(244 246 246 / 0.42)"
typography:
  display:
    fontFamily: "Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "4.15rem"
    fontWeight: 700
    lineHeight: 0.96
    letterSpacing: "0"
  headline:
    fontFamily: "Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "clamp(2.1rem, 4vw, 3.5rem)"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0"
  title:
    fontFamily: "Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "1.35rem"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "0"
  body:
    fontFamily: "Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.65
    letterSpacing: "0"
  label:
    fontFamily: "Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "0"
rounded:
  structural: "2px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "18px"
  lg: "24px"
  xl: "36px"
components:
  button-primary:
    backgroundColor: "transparent"
    textColor: "{colors.signal}"
    rounded: "{rounded.structural}"
    padding: "0 18px"
    height: "46px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.paper}"
    rounded: "{rounded.structural}"
    padding: "0 18px"
    height: "46px"
  chip:
    backgroundColor: "transparent"
    textColor: "{colors.signal}"
    rounded: "{rounded.structural}"
    padding: "5px 8px"
  field:
    backgroundColor: "{colors.surface-0}"
    textColor: "{colors.paper}"
    rounded: "{rounded.structural}"
    padding: "8px 10px"
    height: "42px"
  stage-card:
    backgroundColor: "rgb(5 6 7 / 0.88)"
    textColor: "{colors.paper}"
    rounded: "{rounded.structural}"
---

# Design System: 粤乡智匠

## Overview

**Creative North Star: "Rural Signal Console"**

The system reads as a working information console for Guangdong's rural skill-and-employment network: a near-black stage carries structured data, while cyan marks the next actionable signal. Lime is reserved for live-state confirmation. Composition is dense but explicit; every surface states whether it is showing Flask data or demo content.

This is an original Vue 3 implementation guided by Ark industrial-information grammar. It does not use protected Hypergryph or Arknights/Endfield assets. **Key characteristics:** near-black stage; 1px white rules; 2px corners; cyan action signals; directional stage art; exposed API/demo source; tabular data and spatial labels.

## Colors

The palette is a cold information field: deep ink for stage, pale paper for rules and text, cyan for action, lime for live state, and low-alpha paper lines for structure.

### Primary
- **Signal Cyan** (#18d1ff): primary action, focus ring, selected module marker, code chips, and directional emphasis.

### Secondary
- **State Lime** (#c8eb21): confirms live Flask connection and other positive system state. Do not use it as decoration.

### Neutral
- **Ink Stage** (#080a0b): page background.
- **Deep Shell** (#050607): highest-contrast panels, inputs, footer, and stage background.
- **Instrument Surface** (#0b0f11): metric cells and secondary panels.
- **Construction Surface** (#101518): available third surface when a section needs separation without a border.
- **Rule Paper** (#f4f6f6): primary text, headers, and light structural content.
- **Console Muted** (#a7b1b4): metadata, captions, inactive navigation, and explanatory copy.
- **Hairline** (`rgb(244 246 246 / 0.18)`): internal grid and low-priority dividers.
- **Strong Rule** (`rgb(244 246 246 / 0.42)`): major panel edges and high-priority dividers.

## Typography

**Display Font:** Noto Sans SC (with Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif fallbacks)
**Body Font:** Noto Sans SC (with the same CJK fallback stack)

**Character:** one disciplined CJK sans; hierarchy comes from weight, size, and data rhythm rather than display-serif contrast.

### Hierarchy
- **Display** (700, 4.15rem, 0.96): learner-home hero headline only.
- **Headline** (700, `clamp(2.1rem, 4vw, 3.5rem)`, 1): module section titles.
- **Title** (700, 1.35rem, 1.25): dialogs and compact panel headings.
- **Body** (400, 1rem, 1.65): learner-facing instructions and module summaries.
- **Label** (400, 0.78rem, 1.45): metadata, source labels, field labels, and captions.
- **Data**: use `font-variant-numeric: tabular-nums` for counts, coordinates, salary, time, and generated timestamps.

## Layout

The desktop shell is 1520px maximum width with 24px side padding. Sections are full-bleed bands with centered inner content. The hero is an asymmetric two-column stage (`0.82fr / 1.18fr`); module compositions vary by task but reuse the same frame grammar.

Primary breakpoints are 1180px (header compression), 1080px (module grids become single-column), 900px (two-column footer/notes collapse), 700px (mobile paddings and stacked controls), and 640px (compact header with a module menu). At 320px the layout must remain horizontal-overflow free.

## Elevation & Depth

Depth is primarily structural: grid overlays, stage art, 1px rules, tonal panels, and edge markers. The hero dossier may use one wide soft shadow (`12px 14px 40px rgb(0 0 0 / 0.42)`) to separate the instrument from the stage; smaller cards stay flat.

## Shapes

Use a 2px radius for buttons, panels, fields, and stage cards. Rely on full-width bands, squared metric grids, hairline dividers, and corner ticks instead of rounded cards or pills. Icon containers and data chips share the same squared geometry.

## Components

### Buttons
- **Shape:** squared, 2px radius, 1px border, transparent base.
- **Primary action:** signal cyan text and border, transparent background, 46px height, 0 18px padding; hover/focus uses `rgb(24 209 255 / 0.12)` background.
- **Ghost action:** pale paper text with strong-rule border; hover/focus uses the same cyan tint.
- **Icon button:** 36px square with a screen-reader label; border turns signal cyan on hover or focus.
- **Disabled:** 58% opacity and `cursor: not-allowed`.

### Chips
- **Style:** transparent background, cyan text, 1px hairline border, 0.76rem text.
- **State:** source pills use a 7px square; live state is lime, mixed/demo state is cyan.

### Cards / Containers
- **Stage card:** near-black `rgb(5 6 7 / 0.88)` background, 1px strong rule, 2px radius, and a cyan edge marker at the top-left or top-right.
- **Metric grid:** 1px gap on a hairline background, each cell 66–88px minimum height, labels above tabular values.
- **List rows:** hairline dividers, tag/title/meta/detail columns, and no nested cards.

### Inputs / Fields
- **Style:** deep shell background, 1px strong rule, 2px radius, 42px minimum height, 0.78rem labels above.
- **Hover:** border becomes `rgb(24 209 255 / 0.62)`.
- **Focus:** global 2px signal-cyan outline with 3px offset.
- **Error:** `#ff9c9c` text, `rgb(255 138 138 / 0.44)` border, and 8% red background.

### Navigation
- **Desktop:** inline module links with muted text; hover/focus turns paper with a cyan bottom rule.
- **Mobile:** six links collapse behind a 36px menu button; opened links are full-width, 44px minimum height, and close on selection.

## Do's and Don'ts

### Do:
- **Do** reserve cyan for actions, selection, focus, and directional data signals.
- **Do** label every data surface as Flask, mixed, or demo content.
- **Do** use squared panels, 1px rules, and tabular numerals for the console finish.
- **Do** test 320px, keyboard focus, and reduced-motion states as part of UI completion.

### Don't:
- **Don't** introduce protected Hypergryph/Arknights/Endfield logos, artwork, UI screenshots, or assets.
- **Don't** use lime as decoration; it identifies live state.
- **Don't** hide source status or present mock metrics as production data.
- **Don't** replace the squared console grammar with rounded cards, gradients, or glass decoration.
