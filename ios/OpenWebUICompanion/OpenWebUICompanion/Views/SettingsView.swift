import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        NavigationStack {
            ZStack {
                TechBackground()
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        TechSectionLabel(title: "CHAT CONNECTION", systemImage: "bubble.left.and.bubble.right.fill")
                        TechPanel {
                            VStack(alignment: .leading, spacing: 14) {
                                Text("Open WebUI 聊天服務")
                                    .font(.headline)
                                TextField("https://ai.example.com", text: $store.baseURLText)
                                    .textInputAutocapitalization(.never)
                                    .autocorrectionDisabled()
                                    .keyboardType(.URL)
                                    .padding(.horizontal, 14)
                                    .frame(minHeight: 48)
                                    .background(Color.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                                Text("聊天、模型、Tools 與 Skills 都由這個 Open WebUI 服務提供。變更後請登出再登入。")
                                    .font(.caption)
                                    .foregroundStyle(TechTheme.secondaryText)
                                Button("儲存聊天位址") { store.saveSettings() }
                                    .buttonStyle(.bordered)
                                    .frame(minHeight: 44)
                            }
                            .padding(18)
                        }

                        TechSectionLabel(title: "SECURITY BOUNDARY", systemImage: "lock.shield.fill")
                        TechPanel {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("遠端桌面是獨立配對")
                                    .font(.headline)
                                Text("桌面工作區不再放在聊天設定中。請到「遠端桌面」掃描 Windows Desktop 顯示的一次性 QR Code。")
                                    .font(.subheadline)
                                    .foregroundStyle(TechTheme.secondaryText)
                            }
                            .padding(18)
                        }

                        TechPanel {
                            VStack(alignment: .leading, spacing: 12) {
                                Text("帳號")
                                    .font(.headline)
                                Button(role: .destructive) { store.signOut() } label: {
                                    Label("登出聊天服務", systemImage: "rectangle.portrait.and.arrow.right")
                                        .frame(maxWidth: .infinity, minHeight: 48)
                                }
                                .buttonStyle(.bordered)
                            }
                            .padding(18)
                        }

                        Text("Open WebUI Companion · Mobile workspace preview")
                            .font(.caption)
                            .foregroundStyle(TechTheme.secondaryText)
                            .frame(maxWidth: .infinity, alignment: .center)
                    }
                    .padding(20)
                    .padding(.bottom, 36)
                }
            }
            .navigationTitle("設定")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}
