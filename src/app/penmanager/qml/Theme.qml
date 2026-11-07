pragma Singleton
import QtQuick

// Liquid-glass design system.
//
// One place for every visual token. `mode` switches the entire palette between
// light and dark glass; `accentName` picks the single highlight colour; the
// wallpaper choice lives here too so panels can tint themselves to it.
// Values are resolved at runtime, so switching theme updates every binding.
QtObject {
    id: theme

    property string mode: "light"        // "light" | "dark"
    property string accentName: "blue"   // key of accentChoices
    property string wallpaper: "aurora"  // aurora | sunset | ocean | midnight | none | file path

    readonly property bool dark: mode === "dark"

    // ------------------------------------------------------------- accent
    readonly property var accentChoices: ({
        blue: "#2563EB",
        teal: "#0D9488",
        indigo: "#4F46E5",
        violet: "#7C3AED",
        rose: "#E11D48",
        amber: "#B45309",
        emerald: "#059669"
    })

    readonly property color accent: accentChoices[accentName] || accentChoices.blue
    readonly property color accentHover: Qt.darker(accent, 1.12)
    readonly property color accentPressed: Qt.darker(accent, 1.28)
    readonly property color accentSoft: Qt.rgba(accent.r, accent.g, accent.b, dark ? 0.22 : 0.12)
    readonly property color accentGlow: Qt.rgba(accent.r, accent.g, accent.b, dark ? 0.45 : 0.30)
    readonly property color textOnAccent: "#FFFFFF"

    // ----------------------------------------------------------- surfaces
    readonly property color bg: dark ? "#0A0E16" : "#EDF1F8"
    readonly property color bgDeep: dark ? "#06090F" : "#E3E9F3"
    readonly property color surface: dark ? "#A6111A28" : "#96FFFFFF"
    // Fully opaque surface for modal dialogs (glass would let the page ghost through).
    readonly property color dialog: dark ? "#141A24" : "#FFFFFF"

    readonly property color surfaceRaised: dark ? "#CC121B28" : "#D9FFFFFF"
    readonly property color sidebar: dark ? "#80101926" : "#8CFFFFFF"
    readonly property color navbar: dark ? "#80101926" : "#8CFFFFFF"
    readonly property color panel: dark ? "#1AFFFFFF" : "#66FFFFFF"
    readonly property color panelHover: dark ? "#26FFFFFF" : "#99FFFFFF"
    readonly property color panelActive: dark ? "#33FFFFFF" : "#B8FFFFFF"

    // ------------------------------------------------------------ strokes
    readonly property color hairline: dark ? "#26FFFFFF" : "#330F172A"
    readonly property color hairlineStrong: dark ? "#3DFFFFFF" : "#520F172A"
    readonly property color outline: hairlineStrong
    readonly property color shadow: dark ? "#7A000000" : "#2E0F172A"
    readonly property color sheen: dark ? "#1AFFFFFF" : "#CCFFFFFF"

    // --------------------------------------------------------------- text
    readonly property color text: dark ? "#F1F5F9" : "#0F172A"
    readonly property color textSecondary: dark ? "#CBD5E1" : "#334155"
    readonly property color textDim: dark ? "#94A3B8" : "#64748B"
    readonly property color textFaint: dark ? "#64748B" : "#94A3B8"

    // ------------------------------------------------------------ statuses
    readonly property color ok: dark ? "#34D399" : "#059669"
    readonly property color okSoft: dark ? "#1F34D399" : "#1A059669"
    readonly property color warn: dark ? "#FBBF24" : "#B45309"
    readonly property color warnSoft: dark ? "#1FFBBF24" : "#1AB45309"
    readonly property color danger: dark ? "#F87171" : "#DC2626"
    readonly property color dangerSoft: dark ? "#1FF87171" : "#1ADC2626"
    readonly property color info: accent

    // --------------------------------------------------------- typography
    readonly property string fontDisplay: "Segoe UI"
    readonly property string fontText: "Segoe UI"
    readonly property string fontMono: "Cascadia Mono"

    readonly property int sizeDisplay: 20
    readonly property int sizeTitle: 14
    readonly property int sizeBody: 14
    readonly property int sizeSmall: 13
    readonly property int sizeMeta: 12
    readonly property int sizeMono: 12

    // ------------------------------------------------------------ metrics
    readonly property int radiusWindow: 14
    readonly property int radiusPanel: 14
    readonly property int radiusControl: 9
    readonly property int radiusPill: 999

    readonly property int gap1: 4
    readonly property int gap2: 8
    readonly property int gap3: 12
    readonly property int gap4: 16
    readonly property int gap5: 20
    readonly property int gap6: 24

    readonly property int titleBarHeight: 56
    readonly property int sidebarWidth: 260
    readonly property int controlHeight: 36
    readonly property int rowHeight: 36

    /** "#AARRGGBB" from a "#RRGGBB" colour and a 0..1 alpha. */
    function alpha(hex, a) {
        var v = Math.round(Math.max(0, Math.min(1, a)) * 255)
        var c = String(hex)
        if (c.charAt(0) !== "#" || c.length !== 7)
            return c
        return "#" + (v < 16 ? "0" : "") + v.toString(16) + c.substring(1)
    }

    /** Persisted shape used by Backend.uiSettings()/saveUiSettings(). */
    function toJson() {
        return JSON.stringify({ mode: mode, accent: accentName, wallpaper: wallpaper })
    }

    function apply(settings) {
        if (!settings)
            return
        if (settings.mode === "light" || settings.mode === "dark")
            mode = settings.mode
        if (settings.accent && accentChoices[settings.accent])
            accentName = settings.accent
        if (typeof settings.wallpaper === "string" && settings.wallpaper.length > 0)
            wallpaper = settings.wallpaper
    }
}
