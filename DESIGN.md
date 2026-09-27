# VITALSYNC Design System

A restrained, high-signal design system for multi-surface physiological monitoring across watchOS, desktop control rooms, and internal simulation testbeds.

---

## 1. Principles

1. **Restraint over decoration.** Every element must answer a clinical or operational question. No decorative gradients, marquee tickers, or unrequested chrome.
2. **Hierarchy via scale, not color.** A single 48px number communicates faster than four colorful badges. Use type scale and weight before reaching for a status color.
3. **Conversational, human copy.** Write sentence-case, direct summaries ("Heart rate is slightly elevated") instead of shouting uppercase alarms ("TACHYCARDIA ANOMALY DETECTED").
4. **Honest numbers.** Do not display artificial precision ("72.0 BPM" $\to$ "72", "99% Confidence" $\to$ removed). Show empty states (`—`) until authentic telemetry arrives.

---

## 2. Color Tokens

The entire system uses a disciplined 6-token semantic palette across all surfaces.

| Token | Hex / Value | Purpose |
| :--- | :--- | :--- |
| **Canvas Background** | `#090a0f` | Pure deep slate for high contrast and OLED efficiency |
| **Surface** | `#111318` | Standard card and container background |
| **Surface Subtle** | `#171922` | Secondary containers, inputs, and tab tracks |
| **Border / Rule** | `rgba(255, 255, 255, 0.08)` | 1px clean separation line |
| **Primary Text** | `#f8fafc` | High-contrast body, titles, and active readouts |
| **Muted Text** | `#8e95a5` | Units, descriptions, and labels |
| **Dim Text** | `#555b6a` | Inactive captions and placeholders |
| **Accent Blue** | `#3b82f6` | Interactive focus rings, active tabs, primary buttons |
| **Normal (Success)** | `#10b981` | Stable vitals, active connection, healthy state |
| **Warning (Caution)** | `#f59e0b` | Mild baseline deviation, initial escalation warning |
| **Critical (Danger)** | `#ef4444` | Immediate anomaly, unacknowledged caretaker alert |

*Rule:* Never introduce arbitrary tertiary colors (no purple root-cause chips, no teal meters, no cyan badges).

---

## 3. Typography Scale

We use **Inter** for all UI chrome and body copy, and **JetBrains Mono** with `font-variant-numeric: tabular-nums` for fluctuating numerical values and telemetry timestamps.

| Step | Size | Line Height | Weight | Usage |
| :--- | :--- | :--- | :--- | :--- |
| `caption` | 11px | 14px | 400 / 600 | Axis keys, unit labels, badges |
| `small` | 12px | 16px | 400 / 500 | Metadata, helper notes, sub-labels |
| `body` | 14px | 20px | 400 / 500 | Standard card content, table rows, button labels |
| `title` | 16px | 22px | 600 | Section titles, panel headers |
| `headline` | 20px | 26px | 600 | Device status, modal headers |
| `metric-sm` | 24px | 28px | 700 | Secondary sensor readouts (SpO2, Temp, Accel) |
| `metric-md` | 32px | 36px | 700 | Primary risk scores and watch metrics |
| `metric-lg` | 48px | 52px | 700 | Primary hero vitals (Heart rate on watch) |

*Rule:* Never use font sizes between scale steps (no `0.78rem`, `13px`, or `15px`).

---

## 4. Spacing & Radius

Spatial harmony is maintained through an 8-point base grid with 4px half-steps.

- **Spacing scale:** `4px`, `8px`, `12px`, `16px`, `24px`, `32px`, `48px`.
- **Radii scale:**
  - `4px` (`var(--radius-sm)`): Buttons, input fields, and tags.
  - `8px` (`var(--radius-md)`): Sub-cards and nested panels.
  - `12px` (`var(--radius-lg)`): Main cards and panels.
  - `20px` / `38px` / `44px`: Watch screen and chassis bezels.
  - `9999px`: Pills and round status dots.

---

## 5. Motion Principles

Motion should guide attention, never distract.

- **Duration & Easing:** Standard micro-interactions (hover, active, tab switch) use `150ms` or `200ms ease`.
- **Single Critical Motion:** Exactly one recurring animation exists in the entire system:
  - `criticalPulse` (1.8s smooth ease-in-out pulse) on the watch alert border or critical status badge during unacknowledged medical alerts.
- **Forbidden:** No haptic shake loops, no continuous glowing dots, no marquee tickers, no bouncy springs.

---

## 6. The 4 Rules for Contributors

1. **No decorative emojis.** Always use clean 1.5px stroke SVGs (Lucide/Phosphor style) sized at 12px, 15px, or 18px. Never use emojis (`❤️`, `💧`, `🏃`) in chrome or alerts.
2. **Empty states first.** Never hardcode fake patient numbers or test phone numbers into HTML templates. Initialize templates with `—` and allow JavaScript to bind live data.
3. **No self-narrating comments.** Do not write comments that restate what the code clearly does (`// Heart Rate`, `// 1. Update Diagnostics`, `/* Metal Bezel Layer */`). Keep comments strictly for non-obvious engineering decisions or medical safety constraints.
4. **Group by feature, not noun.** Maintain flat, focused files under `src/` or `components/`. Do not create a separate JavaScript file for every minor noun in the UI.
