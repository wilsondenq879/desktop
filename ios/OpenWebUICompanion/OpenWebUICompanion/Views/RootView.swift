import SwiftUI

/// The companion deliberately leaves chat behaviour to Open WebUI itself.
/// This keeps the mobile experience feature-for-feature aligned with the web
/// client, while the native shell only owns trusted server selection.
struct RootView: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        Group {
            if store.activeServer != nil {
                OpenWebUIWebWorkspaceView()
            } else {
                ServerOnboardingView()
            }
        }
        .preferredColorScheme(.dark)
    }
}

private struct OpenWebUIWebWorkspaceView: View {
    @EnvironmentObject private var store: AppStore
    @State private var showingServerManager = false
    @State private var isLoading = true
    @State private var loadError: String?
    @State private var reloadID = UUID()

    var body: some View {
        if let server = store.activeServer, let url = URL(string: server.url) {
            NavigationStack {
                ZStack(alignment: .top) {
                    OpenWebUIWebView(
                        url: url,
                        reloadID: reloadID,
                        isLoading: $isLoading,
                        errorMessage: $loadError
                    )
                    .id(server.id)
                    .ignoresSafeArea(edges: .bottom)

                    if isLoading {
                        ProgressView()
                            .tint(TechTheme.cyan)
                            .padding(.top, 7)
                    }

                    if let loadError {
                        VStack(spacing: 10) {
                            Label("無法載入 \(server.displayName)", systemImage: "wifi.exclamationmark")
                                .font(.subheadline.weight(.semibold))
                            Text(loadError)
                                .font(.caption)
                                .multilineTextAlignment(.center)
                                .foregroundStyle(TechTheme.secondaryText)
                            Button("重試") { reloadID = UUID() }
                                .buttonStyle(.bordered)
                        }
                        .padding(18)
                        .background(TechTheme.panelStrong, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                        .overlay { RoundedRectangle(cornerRadius: 18, style: .continuous).stroke(TechTheme.line) }
                        .padding(24)
                        .frame(maxHeight: .infinity, alignment: .center)
                    }
                }
                .navigationTitle(server.displayName)
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarLeading) {
                        Menu {
                            ForEach(store.serverProfiles) { profile in
                                Button {
                                    store.selectServer(profile)
                                    reloadID = UUID()
                                } label: {
                                    Label(
                                        profile.displayName,
                                        systemImage: profile.id == store.selectedServerID ? "checkmark.circle.fill" : "server.rack"
                                    )
                                }
                            }
                            Divider()
                            Button { showingServerManager = true } label: {
                                Label("管理伺服器", systemImage: "slider.horizontal.3")
                            }
                        } label: {
                            Image(systemName: "server.rack")
                        }
                        .accessibilityLabel("切換 Open WebUI 伺服器")
                    }
                    ToolbarItem(placement: .topBarTrailing) {
                        Button { reloadID = UUID() } label: {
                            Image(systemName: "arrow.clockwise")
                        }
                        .accessibilityLabel("重新整理 Open WebUI")
                    }
                }
                .sheet(isPresented: $showingServerManager) {
                    ServerManagerView()
                        .presentationDetents([.medium, .large])
                }
            }
        } else {
            ServerOnboardingView()
        }
    }
}

private struct ServerOnboardingView: View {
    @EnvironmentObject private var store: AppStore
    @State private var showingNewServer = true

    var body: some View {
        ZStack {
            TechBackground()
            VStack(spacing: 20) {
                Spacer()
                ZStack {
                    Circle().fill(TechTheme.cyan.opacity(0.14)).frame(width: 82, height: 82)
                    Image(systemName: "server.rack")
                        .font(.system(size: 34, weight: .semibold))
                        .foregroundStyle(TechTheme.cyan)
                }
                TechSectionLabel(title: "OPEN WEBUI MOBILE", systemImage: "network")
                Text("選擇一台 Open WebUI")
                    .font(.title2.bold())
                Text("這個 App 保留原始 Web 介面：聊天紀錄、Skills、Tools、網路搜尋和 Canvas 都和瀏覽器同步。App 只記住並切換你的伺服器位址。")
                    .font(.subheadline)
                    .multilineTextAlignment(.center)
                    .foregroundStyle(TechTheme.secondaryText)
                    .padding(.horizontal, 28)
                Button { showingNewServer = true } label: {
                    Label("新增 Open WebUI 伺服器", systemImage: "plus.circle.fill")
                        .frame(minHeight: 48)
                }
                .buttonStyle(.borderedProminent)
                .tint(TechTheme.cyan)
                Spacer()
            }
            .padding(20)
        }
        .sheet(isPresented: $showingNewServer) {
            ServerEditorView(profile: nil)
                .interactiveDismissDisabled(store.serverProfiles.isEmpty)
        }
    }
}

private struct ServerManagerView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    @State private var editingProfile: ServerProfile?
    @State private var showingNewServer = false

    var body: some View {
        NavigationStack {
            List {
                Section {
                    ForEach(store.serverProfiles) { profile in
                        Button {
                            store.selectServer(profile)
                            dismiss()
                        } label: {
                            HStack(spacing: 12) {
                                Image(systemName: profile.id == store.selectedServerID ? "checkmark.circle.fill" : "server.rack")
                                    .foregroundStyle(profile.id == store.selectedServerID ? TechTheme.cyan : TechTheme.secondaryText)
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(profile.displayName).font(.body.weight(.semibold))
                                    Text(profile.url).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                                }
                                Spacer(minLength: 0)
                            }
                            .frame(minHeight: 48)
                        }
                        .foregroundStyle(.primary)
                        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                            Button { editingProfile = profile } label: {
                                Label("編輯", systemImage: "pencil")
                            }
                            .tint(TechTheme.cyan)
                            Button(role: .destructive) { store.deleteServer(profile) } label: {
                                Label("刪除", systemImage: "trash")
                            }
                        }
                    }
                } header: {
                    Text("已儲存的 Open WebUI")
                } footer: {
                    Text("登入狀態、對談、Skills、Tools 與 Canvas 由每台 Open WebUI 自己管理；切換回同一台時會保留其 Web 登入狀態。")
                }
            }
            .navigationTitle("伺服器")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { Button("完成") { dismiss() } }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showingNewServer = true } label: { Image(systemName: "plus") }
                        .accessibilityLabel("新增伺服器")
                }
            }
            .sheet(isPresented: $showingNewServer) { ServerEditorView(profile: nil) }
            .sheet(item: $editingProfile) { profile in ServerEditorView(profile: profile) }
        }
    }
}

private struct ServerEditorView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss
    let profile: ServerProfile?
    @State private var name = ""
    @State private var url = ""
    @State private var validationMessage: String?

    init(profile: ServerProfile?) {
        self.profile = profile
        _name = State(initialValue: profile?.name ?? "")
        _url = State(initialValue: profile?.url ?? "")
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("伺服器") {
                    TextField("名稱，例如 家中 AI", text: $name)
                        .textInputAutocapitalization(.never)
                    TextField("http://192.168.50.166:3000", text: $url)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                }
                Section {
                    Text("手機必須能透過區域網路、Tailscale 或 ZeroTier 連線到這個位址。登入頁會直接由原本的 Open WebUI Web 介面提供。")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                if let validationMessage {
                    Section { Text(validationMessage).foregroundStyle(.red) }
                }
            }
            .navigationTitle(profile == nil ? "新增伺服器" : "編輯伺服器")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { Button("取消") { dismiss() } }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("儲存") {
                        validationMessage = store.saveServer(id: profile?.id, name: name, url: url)
                        if validationMessage == nil { dismiss() }
                    }
                    .disabled(url.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
        }
    }
}
