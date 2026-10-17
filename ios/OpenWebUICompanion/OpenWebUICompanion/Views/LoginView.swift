import SwiftUI

struct LoginView: View {
    @EnvironmentObject private var store: AppStore
    @FocusState private var focusedField: Field?

    private enum Field { case url, email, password }

    var body: some View {
        NavigationStack {
            ZStack {
                TechBackground()
                ScrollView {
                    VStack(alignment: .leading, spacing: 24) {
                        VStack(alignment: .leading, spacing: 10) {
                            ZStack {
                                RoundedRectangle(cornerRadius: 20, style: .continuous)
                                    .fill(TechTheme.cyan.opacity(0.14))
                                    .frame(width: 64, height: 64)
                                Image(systemName: "bolt.horizontal.circle.fill")
                                    .font(.system(size: 34, weight: .bold))
                                    .foregroundStyle(TechTheme.cyan)
                            }
                            TechSectionLabel(title: "INDEPENDENT AI WORKSPACE", systemImage: "sparkles")
                            Text("Open WebUI\nCompanion")
                                .font(.system(size: 34, weight: .bold, design: .rounded))
                            Text("先連接你的聊天服務；桌面工作站會在登入後，透過獨立 QR 配對連結。")
                                .foregroundStyle(TechTheme.secondaryText)
                        }
                        .padding(.top, 36)

                        TechPanel {
                            VStack(spacing: 14) {
                                LabeledField(title: "Open WebUI 位址", text: $store.baseURLText, placeholder: "https://ai.example.com", systemImage: "link", keyboard: .URL)
                                    .focused($focusedField, equals: .url)
                                LabeledField(title: "Email", text: $store.email, placeholder: "you@example.com", systemImage: "person", keyboard: .emailAddress)
                                    .focused($focusedField, equals: .email)
                                SecureLabeledField(title: "密碼", text: $store.password, placeholder: "輸入密碼", systemImage: "lock")
                                    .focused($focusedField, equals: .password)
                            }
                            .padding(18)
                        }

                    if let error = store.errorMessage {
                        Label(error, systemImage: "exclamationmark.triangle.fill")
                            .font(.subheadline)
                            .foregroundStyle(.red)
                            .fixedSize(horizontal: false, vertical: true)
                    }

                        Button {
                        focusedField = nil
                        Task { await store.signIn() }
                        } label: {
                        HStack {
                            if store.isLoading { ProgressView().tint(.white) }
                            Text(store.isLoading ? "登入中…" : "登入")
                                .fontWeight(.semibold)
                        }
                        .frame(maxWidth: .infinity, minHeight: 52)
                    }
                        .buttonStyle(.borderedProminent)
                        .tint(TechTheme.cyan)
                        .disabled(store.isLoading || store.email.isEmpty || store.password.isEmpty)
                        .accessibilityLabel("登入 Open WebUI")

                        Text("請填入手機可連到的 Open WebUI 聊天服務。127.0.0.1 指向手機本身；桌面工作區配對則不在這一頁設定。")
                            .font(.footnote)
                            .foregroundStyle(TechTheme.secondaryText)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(.horizontal, 20)
                    .padding(.bottom, 32)
                }
            }
            .navigationBarHidden(true)
        }
    }
}

private struct LabeledField: View {
    let title: String
    @Binding var text: String
    let placeholder: String
    let systemImage: String
    let keyboard: UIKeyboardType

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(title).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            HStack(spacing: 10) {
                Image(systemName: systemImage).foregroundStyle(TechTheme.cyan).frame(width: 22)
                TextField(placeholder, text: $text)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(keyboard)
            }
            .padding(.horizontal, 14)
            .frame(minHeight: 50)
            .background(Color.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
    }
}

private struct SecureLabeledField: View {
    let title: String
    @Binding var text: String
    let placeholder: String
    let systemImage: String

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(title).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            HStack(spacing: 10) {
                Image(systemName: systemImage).foregroundStyle(TechTheme.cyan).frame(width: 22)
                SecureField(placeholder, text: $text)
            }
            .padding(.horizontal, 14)
            .frame(minHeight: 50)
            .background(Color.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
    }
}
