import SwiftUI
import UniformTypeIdentifiers

struct ChatView: View {
    @EnvironmentObject private var store: AppStore
    @State private var draft = ""
    @State private var showingModelPicker = false
    @State private var showingCapabilityPicker = false
    @State private var showingImporter = false
    @State private var showingHistory = false
    @State private var attachments: [FileAttachment] = []
    @FocusState private var composerFocused: Bool

    var body: some View {
        NavigationStack {
            ZStack {
                TechBackground()
                VStack(spacing: 0) {
                    if store.messages.isEmpty { emptyState }
                    else { messageList }
                    composer
                }
                if showingHistory {
                    Color.black.opacity(0.54)
                        .ignoresSafeArea()
                        .contentShape(Rectangle())
                        .onTapGesture { closeHistory() }
                        .transition(.opacity)
                        .zIndex(1)
                    ChatHistoryDrawer(onClose: closeHistory)
                        .frame(maxWidth: 326, maxHeight: .infinity, alignment: .leading)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .transition(.move(edge: .leading).combined(with: .opacity))
                        .zIndex(2)
                }
            }
            .navigationTitle("Workspace")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button { toggleHistory() } label: {
                        Image(systemName: "sidebar.left")
                            .frame(width: 44, height: 44)
                    }
                    .accessibilityLabel("開啟對談紀錄")
                    .accessibilityHint("顯示及切換已儲存的對談")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showingModelPicker = true } label: {
                        Label(store.models.first(where: { $0.id == store.selectedModelID })?.displayName ?? "選擇模型", systemImage: "cpu")
                            .labelStyle(.iconOnly)
                            .foregroundStyle(TechTheme.cyan)
                    }
                    .accessibilityLabel("選擇模型")
                    .disabled(store.models.isEmpty)
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showingCapabilityPicker = true } label: {
                        Image(systemName: capabilityCount > 0 ? "wrench.and.screwdriver.fill" : "wrench.and.screwdriver")
                            .foregroundStyle(capabilityCount > 0 ? TechTheme.teal : TechTheme.cyan)
                    }
                    .accessibilityLabel("選擇 Tools 與 Skills")
                }
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button("收起") { composerFocused = false }
                        .accessibilityLabel("收起鍵盤")
                }
            }
            .sheet(isPresented: $showingModelPicker) {
                ModelPickerView()
                    .presentationDetents([.medium, .large])
            }
            .sheet(isPresented: $showingCapabilityPicker) {
                CapabilityPickerView()
                    .presentationDetents([.medium, .large])
            }
            .fileImporter(isPresented: $showingImporter, allowedContentTypes: [.data, .image, .pdf, .plainText], allowsMultipleSelection: false) { result in
                guard case let .success(urls) = result, let url = urls.first else { return }
                Task {
                    let secured = url.startAccessingSecurityScopedResource()
                    defer { if secured { url.stopAccessingSecurityScopedResource() } }
                    guard let data = try? Data(contentsOf: url) else { return }
                    let type = UTType(filenameExtension: url.pathExtension)?.preferredMIMEType ?? "application/octet-stream"
                    if let file = await store.uploadFile(data: data, fileName: url.lastPathComponent, mimeType: type) { attachments.append(file) }
                }
            }
            .task { await store.refreshModels() }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 18) {
            Spacer()
            TechPanel {
                VStack(spacing: 15) {
                    ZStack {
                        Circle().fill(TechTheme.cyan.opacity(0.14)).frame(width: 76, height: 76)
                        Image(systemName: "sparkles.rectangle.stack.fill")
                            .font(.system(size: 34, weight: .semibold))
                            .foregroundStyle(TechTheme.cyan)
                    }
                    TechSectionLabel(title: "MOBILE AI WORKSPACE", systemImage: "bolt.fill")
                    Text("開始一個對話")
                        .font(.title2.bold())
                    Text("直接聊天、選 Tools／Skills，或請模型產生單檔 HTML 網頁並在 Canvas 預覽。桌面控制則保持在獨立的遠端桌面分頁。")
                        .multilineTextAlignment(.center)
                        .font(.subheadline)
                        .foregroundStyle(TechTheme.secondaryText)
                    if !store.selectedModelID.isEmpty {
                        Text(store.selectedModelID)
                            .font(.caption.monospaced())
                            .foregroundStyle(TechTheme.cyan)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(TechTheme.cyan.opacity(0.12), in: Capsule())
                    }
                }
                .padding(24)
            }
            .padding(.horizontal, 20)
            Spacer()
        }
    }

    private var messageList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 16) {
                    ForEach(store.messages) { message in MessageBubble(message: message).id(message.id) }
                }
                .padding(16)
            }
            .scrollDismissesKeyboard(.interactively)
            .onChange(of: store.messages.count) { _, _ in
                if let id = store.messages.last?.id { withAnimation(.easeOut(duration: 0.2)) { proxy.scrollTo(id, anchor: .bottom) } }
            }
        }
    }

    private var composer: some View {
        VStack(spacing: 8) {
            if capabilityCount > 0 {
                HStack(spacing: 6) {
                    Image(systemName: "wrench.and.screwdriver.fill")
                    Text("已選 (capabilityCount) 個 Tool／Skill")
                    Spacer()
                    Button("管理") { showingCapabilityPicker = true }
                }
                .font(.caption)
                .foregroundStyle(TechTheme.cyan)
                .padding(.horizontal, 10)
            }
            if !attachments.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack { ForEach(attachments) { file in Label(file.name, systemImage: "paperclip").font(.caption).padding(.horizontal, 10).padding(.vertical, 7).background(.teal.opacity(0.12), in: Capsule()) } }
                }
            }
            HStack(alignment: .bottom, spacing: 8) {
                Button { showingImporter = true } label: { Image(systemName: "plus").font(.title3).frame(width: 44, height: 44) }
                    .accessibilityLabel("加入檔案")
                Button {
                    store.setWebSearch(!store.webSearchEnabled)
                } label: {
                    Image(systemName: store.webSearchEnabled ? "globe.americas.fill" : "globe.americas")
                        .font(.body.weight(.semibold))
                        .foregroundStyle(store.webSearchEnabled ? TechTheme.cyan : TechTheme.secondaryText)
                        .frame(width: 36, height: 44)
                }
                .accessibilityLabel(store.webSearchEnabled ? "關閉網路搜尋" : "開啟網路搜尋")
                TextField("輸入訊息…", text: $draft, axis: .vertical)
                    .lineLimit(1...5)
                    .focused($composerFocused)
                    .submitLabel(.send)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 11)
                    .background(TechTheme.panelStrong, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                Button {
                    let text = draft
                    draft = ""
                    composerFocused = false
                    let files = attachments
                    attachments = []
                    Task { await store.sendMessage(text, attachments: files) }
                } label: {
                    Image(systemName: store.isLoading ? "hourglass" : "arrow.up.circle.fill")
                        .font(.title2)
                        .frame(width: 44, height: 44)
                }
                .disabled(store.isLoading || draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || store.selectedModelID.isEmpty)
                .accessibilityLabel("送出訊息")
            }
        }
        .padding(.horizontal, 12)
        .padding(.top, 8)
        .padding(.bottom, 8)
        .padding(.horizontal, 4)
        .background(TechTheme.ink.opacity(0.94))
    }

    private var capabilityCount: Int {
        store.selectedToolIDs.count + store.selectedSkillIDs.count
    }

    private func toggleHistory() {
        withAnimation(.snappy(duration: 0.24)) { showingHistory.toggle() }
    }

    private func closeHistory() {
        withAnimation(.easeOut(duration: 0.16)) { showingHistory = false }
    }
}

private struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            if message.role == .assistant { Image(systemName: "sparkles").foregroundStyle(TechTheme.cyan).frame(width: 28, height: 28) }
            VStack(alignment: .leading, spacing: 6) {
                Text(message.role == .user ? "你" : "模型").font(.caption.weight(.semibold)).foregroundStyle(TechTheme.secondaryText)
                if message.content.isEmpty, message.role == .assistant {
                    HStack(spacing: 8) {
                        ProgressView().controlSize(.small).tint(TechTheme.cyan)
                        Text("正在整理回覆…")
                            .foregroundStyle(TechTheme.secondaryText)
                    }
                    .font(.subheadline)
                } else if message.role == .assistant {
                    MarkdownMessageView(markdown: message.content)
                } else {
                    Text(message.content)
                        .foregroundStyle(TechTheme.primaryText)
                        .textSelection(.enabled)
                }
                if !message.attachments.isEmpty { ForEach(message.attachments) { Label($0.name, systemImage: "paperclip").font(.caption).foregroundStyle(.secondary) } }
            }
            .padding(12)
            .background(message.role == .user ? TechTheme.teal.opacity(0.16) : TechTheme.panel, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .stroke(message.role == .user ? TechTheme.teal.opacity(0.26) : TechTheme.line, lineWidth: 1)
            }
            if message.role == .user { Spacer(minLength: 34) }
        }
    }
}

private struct ModelPickerView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List(store.models) { model in
                Button { store.selectedModelID = model.id; dismiss() } label: {
                    HStack {
                        Image(systemName: model.id == store.selectedModelID ? "checkmark.circle.fill" : "circle")
                            .foregroundStyle(model.id == store.selectedModelID ? .teal : .secondary)
                        VStack(alignment: .leading) { Text(model.displayName); if let owner = model.ownedBy { Text(owner).font(.caption).foregroundStyle(.secondary) } }
                    }
                }
                .foregroundStyle(.primary)
                .frame(minHeight: 44)
            }
            .navigationTitle("選擇模型")
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("完成") { dismiss() } } }
        }
    }
}

private struct CapabilityPickerView: View {
    @EnvironmentObject private var store: AppStore
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                Section {
                    nativeFeatureToggle(
                        title: "網路搜尋",
                        detail: "讓 Open WebUI 在本則對話中使用已設定的網路搜尋服務。",
                        icon: "globe.americas",
                        isOn: store.webSearchEnabled
                    ) { store.setWebSearch($0) }
                    nativeFeatureToggle(
                        title: "產生圖片",
                        detail: "使用伺服器已設定的圖片生成服務。",
                        icon: "photo.badge.plus",
                        isOn: store.imageGenerationEnabled
                    ) { store.setImageGeneration($0) }
                    nativeFeatureToggle(
                        title: "程式執行",
                        detail: "使用 Open WebUI 的 Code Interpreter（伺服器必須已啟用）。",
                        icon: "terminal",
                        isOn: store.codeInterpreterEnabled
                    ) { store.setCodeInterpreter($0) }
                    nativeFeatureToggle(
                        title: "記憶",
                        detail: "允許本則對話使用 Open WebUI 的記憶功能。",
                        icon: "brain.head.profile",
                        isOn: store.memoryEnabled
                    ) { store.setMemory($0) }
                } header: {
                    Label("內建功能", systemImage: "slider.horizontal.3")
                } footer: {
                    Text("這些是 Open WebUI 的內建功能，不會列在 Workspace Tools。是否可用仍由伺服器管理員設定與模型能力決定。")
                }

                Section {
                    if store.tools.isEmpty {
                        Text(store.toolLoadError ?? "目前沒有可用 Tools。請確認它已在 Open WebUI 對此帳號啟用。")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(store.tools) { tool in
                            capabilityRow(
                                id: tool.id,
                                title: tool.displayName,
                                detail: tool.description,
                                selected: store.selectedToolIDs.contains(tool.id),
                                icon: "wrench.and.screwdriver"
                            ) {
                                toggleTool(tool.id)
                            }
                        }
                    }
                } header: {
                    Label("Tools", systemImage: "wrench.and.screwdriver")
                } footer: {
                    Text("選取的 Tools 會在下一則訊息透過 Open WebUI tool_ids 傳送。")
                }

                Section {
                    let activeSkills = store.skills.filter { $0.isActive != false }
                    if activeSkills.isEmpty {
                        Text(store.skillLoadError ?? "目前沒有可用 Skills。請確認它已在 Open WebUI Workspace 啟用，然後重新整理。")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(activeSkills) { skill in
                            capabilityRow(
                                id: skill.id,
                                title: skill.displayName,
                                detail: skill.description,
                                selected: store.selectedSkillIDs.contains(skill.id),
                                icon: "sparkles"
                            ) {
                                toggleSkill(skill.id)
                            }
                        }
                    }
                } header: {
                    Label("Skills", systemImage: "sparkles")
                } footer: {
                    Text("選取的 Skills 會在下一則訊息透過 Open WebUI skill_ids 傳送。")
                }
            }
            .navigationTitle("Tools／Skills")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("清除") {
                        store.selectedToolIDs.removeAll()
                        store.selectedSkillIDs.removeAll()
                        store.resetNativeFeatures()
                    }
                    .disabled(
                        store.selectedToolIDs.isEmpty && store.selectedSkillIDs.isEmpty &&
                        !store.webSearchEnabled && !store.imageGenerationEnabled &&
                        !store.codeInterpreterEnabled && !store.memoryEnabled
                    )
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("完成") { dismiss() }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { Task { await store.refreshCapabilities() } } label: {
                        Image(systemName: store.isRefreshingCapabilities ? "arrow.triangle.2.circlepath.circle.fill" : "arrow.clockwise")
                    }
                    .accessibilityLabel("重新整理 Tools 與 Skills")
                    .disabled(store.isRefreshingCapabilities)
                }
            }
        }
        .task { await store.refreshCapabilities() }
    }

    @ViewBuilder
    private func capabilityRow(
        id: String,
        title: String,
        detail: String?,
        selected: Bool,
        icon: String,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: selected ? "checkmark.circle.fill" : "circle")
                    .foregroundStyle(selected ? .teal : .secondary)
                Image(systemName: icon)
                    .foregroundStyle(.teal)
                    .frame(width: 22)
                VStack(alignment: .leading, spacing: 3) {
                    Text(title).lineLimit(1)
                    if let detail, !detail.isEmpty {
                        Text(detail).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                    }
                }
                Spacer(minLength: 0)
            }
        }
        .foregroundStyle(.primary)
        .frame(minHeight: 48)
        .accessibilityLabel("\(title)\(selected ? "，已選取" : "")")
    }

    @ViewBuilder
    private func nativeFeatureToggle(
        title: String,
        detail: String,
        icon: String,
        isOn: Bool,
        set: @escaping (Bool) -> Void
    ) -> some View {
        Toggle(isOn: Binding(get: { isOn }, set: set)) {
            HStack(spacing: 12) {
                Image(systemName: icon)
                    .foregroundStyle(TechTheme.cyan)
                    .frame(width: 22)
                VStack(alignment: .leading, spacing: 3) {
                    Text(title)
                    Text(detail).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                }
            }
        }
        .tint(TechTheme.cyan)
        .frame(minHeight: 52)
    }

    private func toggleTool(_ id: String) {
        if store.selectedToolIDs.contains(id) { store.selectedToolIDs.remove(id) }
        else { store.selectedToolIDs.insert(id) }
    }

    private func toggleSkill(_ id: String) {
        if store.selectedSkillIDs.contains(id) { store.selectedSkillIDs.remove(id) }
        else { store.selectedSkillIDs.insert(id) }
    }
}

private struct ChatHistoryDrawer: View {
    @EnvironmentObject private var store: AppStore
    let onClose: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("對談紀錄").font(.title3.bold())
                    Text("保存在此 iPhone").font(.caption).foregroundStyle(TechTheme.secondaryText)
                }
                Spacer()
                Button(action: onClose) {
                    Image(systemName: "xmark")
                        .frame(width: 44, height: 44)
                }
                .accessibilityLabel("關閉對談紀錄")
            }
            .padding(.horizontal, 20)
            .padding(.top, 18)
            .padding(.bottom, 14)

            Button {
                store.startNewChat()
                onClose()
            } label: {
                Label("新增對話", systemImage: "square.and.pencil")
                    .frame(maxWidth: .infinity, minHeight: 48)
            }
            .buttonStyle(.borderedProminent)
            .tint(TechTheme.cyan)
            .padding(.horizontal, 16)
            .padding(.bottom, 14)

            if store.chatSessions.isEmpty {
                VStack(spacing: 10) {
                    Image(systemName: "clock.arrow.circlepath")
                        .font(.title2)
                        .foregroundStyle(TechTheme.cyan)
                    Text("尚未有已儲存的對談")
                        .font(.subheadline.weight(.medium))
                    Text("送出第一則訊息後，對話會自動保留在這裡。")
                        .font(.caption)
                        .multilineTextAlignment(.center)
                        .foregroundStyle(TechTheme.secondaryText)
                }
                .frame(maxWidth: .infinity)
                .padding(28)
            } else {
                List {
                    ForEach(store.chatSessions) { session in
                        Button {
                            store.selectChat(session)
                            onClose()
                        } label: {
                            VStack(alignment: .leading, spacing: 5) {
                                HStack(spacing: 8) {
                                    Text(session.title)
                                        .font(.subheadline.weight(.semibold))
                                        .lineLimit(2)
                                    Spacer()
                                    if store.activeChatID == session.id {
                                        Image(systemName: "checkmark.circle.fill")
                                            .foregroundStyle(TechTheme.teal)
                                            .accessibilityHidden(true)
                                    }
                                }
                                Text(session.updatedAt, style: .relative)
                                    .font(.caption)
                                    .foregroundStyle(TechTheme.secondaryText)
                            }
                            .padding(.vertical, 5)
                        }
                        .listRowBackground(store.activeChatID == session.id ? TechTheme.cyan.opacity(0.12) : TechTheme.panel.opacity(0.82))
                        .swipeActions(edge: .trailing) {
                            Button(role: .destructive) { store.deleteChat(session) } label: {
                                Label("刪除", systemImage: "trash")
                            }
                        }
                    }
                }
                .listStyle(.plain)
                .scrollContentBackground(.hidden)
            }
            Spacer(minLength: 0)
        }
        .background(TechTheme.ink.opacity(0.985))
        .overlay(alignment: .trailing) { Rectangle().fill(TechTheme.line).frame(width: 1) }
        .ignoresSafeArea(edges: .bottom)
    }
}
