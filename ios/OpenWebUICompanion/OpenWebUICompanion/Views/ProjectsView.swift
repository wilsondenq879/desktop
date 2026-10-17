import SwiftUI

struct ProjectsView: View {
    @EnvironmentObject private var store: AppStore
    @State private var showingScanner = false
    @State private var showingManualPair = false
    @State private var manualPairingURL = ""
    @State private var scannerError: String?

    private var isPaired: Bool {
        !store.desktopURLText.isEmpty && !store.desktopAPIKeyText.isEmpty
    }

    var body: some View {
        NavigationStack {
            ZStack {
                TechBackground()
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        header
                        if isPaired { pairedDesktop } else { pairingIntro }
                    }
                    .padding(20)
                    .padding(.bottom, 36)
                }
            }
            .navigationTitle("遠端桌面")
            .navigationBarTitleDisplayMode(.inline)
            .task {
                if isPaired { await store.testDesktopConnection() }
            }
            .sheet(isPresented: $showingScanner) {
                NavigationStack {
                    ZStack {
                        QRCodeScannerView(
                            onCode: { value in
                                showingScanner = false
                                Task { await store.pairDesktop(using: value) }
                            },
                            onFailure: { message in scannerError = message }
                        )
                        VStack {
                            Spacer()
                            Text("對準 Windows Desktop 顯示的配對 QR Code")
                                .font(.subheadline.weight(.medium))
                                .padding(.horizontal, 16)
                                .padding(.vertical, 10)
                                .background(.black.opacity(0.66), in: Capsule())
                                .padding(.bottom, 48)
                        }
                    }
                    .navigationTitle("掃描配對")
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("取消") { showingScanner = false } } }
                }
            }
            .sheet(isPresented: $showingManualPair) {
                NavigationStack {
                    Form {
                        Section("配對連結") {
                            TextField("貼上桌面端提供的配對連結", text: $manualPairingURL, axis: .vertical)
                                .textInputAutocapitalization(.never)
                                .autocorrectionDisabled()
                        }
                        Section {
                            Text("配對連結僅能使用一次，而且五分鐘後會失效。這不是 Open WebUI 聊天網址。")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .navigationTitle("手動配對")
                    .toolbar {
                        ToolbarItem(placement: .topBarLeading) { Button("取消") { showingManualPair = false } }
                        ToolbarItem(placement: .topBarTrailing) {
                            Button("配對") {
                                showingManualPair = false
                                Task { await store.pairDesktop(using: manualPairingURL) }
                            }
                            .disabled(manualPairingURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                        }
                    }
                }
            }
            .alert("無法掃描 QR Code", isPresented: Binding(
                get: { scannerError != nil },
                set: { if !$0 { scannerError = nil } }
            )) {
                Button("好", role: .cancel) {}
            } message: {
                Text(scannerError ?? "")
            }
        }
    }

    private var header: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 6) {
                TechSectionLabel(title: "PAIRED COMPUTE", systemImage: "desktopcomputer.and.macbook")
                Text("遠端桌面")
                    .font(.largeTitle.bold())
                Text(isPaired ? "這個區域只處理已配對 Windows Desktop 的任務與成品。" : "先掃描桌面版 QR Code，才會開啟遠端工作區。")
                    .font(.subheadline)
                    .foregroundStyle(TechTheme.secondaryText)
            }
            Spacer()
            Image(systemName: "link.badge.plus")
                .font(.title)
                .foregroundStyle(isPaired ? TechTheme.teal : TechTheme.magenta)
                .accessibilityHidden(true)
        }
    }

    private var pairingIntro: some View {
        VStack(spacing: 14) {
            TechPanel {
                VStack(alignment: .leading, spacing: 18) {
                    HStack {
                        ZStack {
                            RoundedRectangle(cornerRadius: 18, style: .continuous)
                                .fill(TechTheme.magenta.opacity(0.18))
                                .frame(width: 62, height: 62)
                            Image(systemName: "qrcode.viewfinder")
                                .font(.title2)
                                .foregroundStyle(TechTheme.magenta)
                        }
                        Spacer()
                        Text("DESKTOP LINK")
                            .font(.caption.weight(.bold))
                            .tracking(1)
                            .foregroundStyle(TechTheme.secondaryText)
                    }
                    Text("配對你的 Windows 工作站")
                        .font(.title3.bold())
                    Text("手機聊天保持獨立；只有在此完成配對後，App 才能查看專案進度、檔案變更與完成品。")
                        .font(.subheadline)
                        .foregroundStyle(TechTheme.secondaryText)
                    Button { showingScanner = true } label: {
                        Label("掃描桌面 QR Code", systemImage: "qrcode.viewfinder")
                            .frame(maxWidth: .infinity, minHeight: 48)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(TechTheme.cyan)
                    .accessibilityLabel("掃描桌面配對 QR Code")
                    Button("手動貼上配對連結") { showingManualPair = true }
                        .frame(maxWidth: .infinity, minHeight: 44)
                }
                .padding(20)
            }
            connectionBoundary
        }
    }

    private var pairedDesktop: some View {
        VStack(alignment: .leading, spacing: 16) {
            TechPanel {
                VStack(alignment: .leading, spacing: 14) {
                    HStack {
                        Image(systemName: store.desktopConnection.status == .connected ? "checkmark.seal.fill" : "bolt.horizontal.circle")
                            .font(.title2)
                            .foregroundStyle(store.desktopConnection.status == .connected ? TechTheme.teal : .orange)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Windows Desktop")
                                .font(.headline)
                            Text(store.desktopURLText)
                                .font(.caption.monospaced())
                                .foregroundStyle(TechTheme.secondaryText)
                                .lineLimit(1)
                        }
                        Spacer()
                        Circle()
                            .fill(store.desktopConnection.status == .connected ? TechTheme.teal : .orange)
                            .frame(width: 10, height: 10)
                            .accessibilityLabel(store.desktopConnection.status == .connected ? "已連線" : "連線中或不可用")
                    }
                    HStack(spacing: 12) {
                        Button { Task { await store.testDesktopConnection() } } label: {
                            Label(store.desktopConnection.status == .checking ? "檢查中…" : "重新連線", systemImage: "arrow.clockwise")
                        }
                        .buttonStyle(.bordered)
                        .disabled(store.desktopConnection.status == .checking)
                        Button("解除配對", role: .destructive) { store.unpairDesktop() }
                            .buttonStyle(.bordered)
                    }
                    if !store.desktopConnection.detail.isEmpty {
                        Text(store.desktopConnection.detail)
                            .font(.caption)
                            .foregroundStyle(TechTheme.secondaryText)
                    }
                }
                .padding(18)
            }
            workspaceList
        }
    }

    private var workspaceList: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                TechSectionLabel(title: "DESKTOP ACTIVITY", systemImage: "waveform.path.ecg")
                Spacer()
                Button { Task { await store.refreshDesktopWorkspaces() } } label: {
                    Image(systemName: "arrow.clockwise")
                        .frame(width: 44, height: 44)
                }
                .buttonStyle(.plain)
                .disabled(store.desktopConnection.status != .connected)
                .accessibilityLabel("重新整理桌面工作紀錄")
            }
            if store.desktopWorkspaces.isEmpty {
                TechPanel {
                    Text(store.desktopConnection.status == .connected ? "目前沒有可顯示的桌面工作紀錄。" : "連線後會在這裡顯示桌面端的任務、變更與成品。")
                        .font(.subheadline)
                        .foregroundStyle(TechTheme.secondaryText)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(18)
                }
            } else {
                ForEach(store.desktopWorkspaces) { workspace in
                    WorkspaceRow(workspace: workspace)
                }
            }
        }
    }

    private var connectionBoundary: some View {
        TechPanel {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: "lock.shield.fill")
                    .foregroundStyle(TechTheme.teal)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 4) {
                    Text("聊天與桌面控制分離")
                        .font(.subheadline.weight(.semibold))
                    Text("QR 配對只授權遠端桌面工作區；不會帶走你的 Open WebUI 帳密或改變聊天服務。")
                        .font(.caption)
                        .foregroundStyle(TechTheme.secondaryText)
                }
            }
            .padding(16)
        }
    }
}

private struct WorkspaceRow: View {
    let workspace: DesktopWorkspace

    private var statusColor: Color {
        switch workspace.status {
        case "complete", "restored": return TechTheme.teal
        case "failed": return .red
        case "running", "capturing": return .orange
        default: return TechTheme.secondaryText
        }
    }

    var body: some View {
        TechPanel {
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: workspace.status == "failed" ? "exclamationmark.triangle.fill" : "folder.fill")
                        .foregroundStyle(statusColor)
                        .frame(width: 24)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(workspace.projectName).font(.subheadline.weight(.semibold)).lineLimit(1)
                        Text(workspace.projectPath).font(.caption.monospaced()).foregroundStyle(TechTheme.secondaryText).lineLimit(1)
                    }
                    Spacer()
                    Text(workspace.status.uppercased())
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(statusColor)
                }
                HStack(spacing: 14) {
                    Label("\(workspace.changes.count) 變更", systemImage: "pencil.line")
                    Label("\(workspace.artifacts.count) 成品", systemImage: "doc.richtext")
                }
                .font(.caption)
                .foregroundStyle(TechTheme.secondaryText)
            }
            .padding(16)
        }
    }
}
