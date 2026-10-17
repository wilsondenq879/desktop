import SwiftUI

enum TechTheme {
    static let ink = Color(red: 0.025, green: 0.045, blue: 0.075)
    static let panel = Color(red: 0.055, green: 0.085, blue: 0.125)
    static let panelStrong = Color(red: 0.075, green: 0.115, blue: 0.165)
    static let cyan = Color(red: 0.18, green: 0.86, blue: 0.98)
    static let teal = Color(red: 0.08, green: 0.78, blue: 0.68)
    static let magenta = Color(red: 0.94, green: 0.24, blue: 0.76)
    static let primaryText = Color.white.opacity(0.94)
    static let line = Color.white.opacity(0.12)
    static let secondaryText = Color.white.opacity(0.66)
    static let codeSurface = Color(red: 0.018, green: 0.035, blue: 0.060)
}

struct TechBackground: View {
    var body: some View {
        GeometryReader { proxy in
            ZStack {
                TechTheme.ink
                RadialGradient(
                    colors: [TechTheme.cyan.opacity(0.18), .clear],
                    center: .topTrailing,
                    startRadius: 12,
                    endRadius: max(proxy.size.width, proxy.size.height) * 0.72
                )
                RadialGradient(
                    colors: [TechTheme.magenta.opacity(0.12), .clear],
                    center: .bottomLeading,
                    startRadius: 10,
                    endRadius: max(proxy.size.width, proxy.size.height) * 0.58
                )
                LinearGradient(
                    colors: [.clear, Color.black.opacity(0.28)],
                    startPoint: .top,
                    endPoint: .bottom
                )
            }
        }
        .ignoresSafeArea()
        .accessibilityHidden(true)
    }
}

struct TechPanel<Content: View>: View {
    let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        content
            .background(TechTheme.panel.opacity(0.90), in: RoundedRectangle(cornerRadius: 22, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .stroke(TechTheme.line, lineWidth: 1)
            }
    }
}

struct TechSectionLabel: View {
    let title: String
    let systemImage: String

    var body: some View {
        Label(title.uppercased(), systemImage: systemImage)
            .font(.caption.weight(.bold))
            .tracking(1.1)
            .foregroundStyle(TechTheme.cyan)
    }
}
