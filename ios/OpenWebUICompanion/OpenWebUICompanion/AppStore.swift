import Foundation
import SwiftUI

@MainActor
final class AppStore: ObservableObject {
    @Published var baseURLText: String
    @Published var desktopURLText: String
    @Published var desktopAPIKeyText: String
    @Published var email = ""
    @Published var password = ""
    @Published var isAuthenticated = false
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var serverProfiles: [ServerProfile] = []
    @Published var selectedServerID: UUID?
    @Published var models: [OpenWebUIModel] = []
    @Published var selectedModelID = ""
    @Published var tools: [OpenWebUITool] = []
    @Published var skills: [OpenWebUISkill] = []
    @Published var selectedToolIDs: Set<String> = []
    @Published var selectedSkillIDs: Set<String> = []
    @Published var webSearchEnabled = false
    @Published var imageGenerationEnabled = false
    @Published var codeInterpreterEnabled = false
    @Published var memoryEnabled = false
    @Published var toolLoadError: String?
    @Published var skillLoadError: String?
    @Published var isRefreshingCapabilities = false
    @Published var messages: [ChatMessage] = []
    @Published var chatSessions: [ChatSession] = []
    @Published private(set) var activeChatID: UUID?
    @Published var canvasDocuments: [CanvasDocument] = []
    @Published var desktopConnection = DesktopConnection(url: "")
    @Published var desktopWorkspaces: [DesktopWorkspace] = []

    private let keychain = KeychainStore.shared
    private let desktopClient = DesktopCompanionClient()
    private var client: OpenWebUIClient?
    private let chatSessionsKey = "openwebui.chatSessions.v1"
    private let nativeFeaturesKey = "openwebui.nativeFeatures.v1"
    private let serverProfilesKey = "openwebui.serverProfiles.v1"
    private let selectedServerKey = "openwebui.selectedServerID.v1"

    var activeServer: ServerProfile? {
        guard let selectedServerID else { return nil }
        return serverProfiles.first(where: { $0.id == selectedServerID })
    }

    init() {
        baseURLText = UserDefaults.standard.string(forKey: "openwebui.baseURL") ?? "http://127.0.0.1:8080"
        desktopURLText = UserDefaults.standard.string(forKey: "openwebui.desktopURL") ?? ""
        desktopAPIKeyText = keychain.read("desktopAPIKey") ?? ""
        loadNativeFeatureSettings()
        loadServerProfiles()
        migrateLegacyServerIfNeeded()
        loadChatSessions()
        if let savedToken = keychain.read("token"),
           let savedURL = keychain.read("baseURL"),
           let url = URL(string: savedURL) {
            client = OpenWebUIClient(baseURL: url, token: savedToken)
            isAuthenticated = true
            baseURLText = savedURL
            Task { await refreshModels() }
        }
    }

    func signIn() async {
        errorMessage = nil
        guard let url = normalizedBaseURL() else {
            errorMessage = APIError.invalidURL.localizedDescription
            return
        }
        if isLoopback(url) {
            errorMessage = APIError.loopbackURL.localizedDescription
            return
        }
        baseURLText = url.absoluteString
        isLoading = true
        defer { isLoading = false }
        do {
            let newClient = OpenWebUIClient(baseURL: url)
            let response = try await newClient.signIn(email: email.trimmingCharacters(in: .whitespacesAndNewlines), password: password)
            try keychain.save(response.token, for: "token")
            try keychain.save(url.absoluteString, for: "baseURL")
            UserDefaults.standard.set(url.absoluteString, forKey: "openwebui.baseURL")
            client = newClient
            isAuthenticated = true
            password = ""
            await refreshModels()
        } catch is URLError {
            errorMessage = APIError.connectionFailed(url.absoluteString).localizedDescription
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func signOut() {
        keychain.delete("token")
        keychain.delete("baseURL")
        client = nil
        isAuthenticated = false
        models = []
        tools = []
        skills = []
        selectedToolIDs = []
        selectedSkillIDs = []
        resetNativeFeatures()
        messages = []
        chatSessions = []
        activeChatID = nil
        UserDefaults.standard.removeObject(forKey: chatSessionsKey)
        canvasDocuments = []
        desktopWorkspaces = []
    }

    func refreshModels() async {
        guard let client else { return }
        do {
            let loaded = try await client.fetchModels()
            models = loaded
            if !loaded.contains(where: { $0.id == selectedModelID }) { selectedModelID = loaded.first?.id ?? "" }
        } catch { errorMessage = error.localizedDescription }

        await refreshCapabilities()
    }

    func refreshCapabilities() async {
        guard let client else { return }
        isRefreshingCapabilities = true
        defer { isRefreshingCapabilities = false }

        do {
            let loadedTools = try await client.fetchTools()
            tools = loadedTools
            toolLoadError = nil
            selectedToolIDs = selectedToolIDs.intersection(Set(loadedTools.map(\.id)))
        } catch {
            toolLoadError = error.localizedDescription
        }

        do {
            let loadedSkills = try await client.fetchSkills()
            skills = loadedSkills
            skillLoadError = nil
            selectedSkillIDs = selectedSkillIDs.intersection(Set(loadedSkills.filter { $0.isActive != false }.map(\.id)))
        } catch {
            skillLoadError = error.localizedDescription
        }
    }

    func sendMessage(_ text: String, attachments: [FileAttachment] = []) async {
        let content = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !content.isEmpty, let client, !selectedModelID.isEmpty, !isLoading else { return }
        errorMessage = nil
        if activeChatID == nil {
            activeChatID = UUID()
        }
        messages.append(ChatMessage(role: .user, content: content, attachments: attachments))
        let assistantIndex = messages.count
        messages.append(ChatMessage(role: .assistant, content: ""))
        persistActiveChat(defaultTitle: ChatSession.title(for: content))
        isLoading = true
        defer {
            isLoading = false
            persistActiveChat(defaultTitle: ChatSession.title(for: content))
        }
        do {
            let history = messages.dropLast().filter { $0.role != .system }
            for try await delta in client.streamChat(
                model: selectedModelID,
                messages: Array(history),
                attachments: attachments,
                toolIDs: Array(selectedToolIDs),
                skillIDs: Array(selectedSkillIDs),
                features: nativeFeatures
            ) {
                messages[assistantIndex].content += delta
            }
            captureCanvasIfPresent(messages[assistantIndex].content)
        } catch {
            messages[assistantIndex].content = ""
            errorMessage = error.localizedDescription
        }
    }

    func uploadFile(data: Data, fileName: String, mimeType: String) async -> FileAttachment? {
        guard let client else { return nil }
        do { return try await client.uploadFile(data: data, fileName: fileName, mimeType: mimeType) }
        catch { errorMessage = error.localizedDescription; return nil }
    }

    func saveSettings() {
        UserDefaults.standard.set(baseURLText.trimmingCharacters(in: .whitespacesAndNewlines), forKey: "openwebui.baseURL")
    }

    @discardableResult
    func saveServer(id: UUID? = nil, name: String, url: String) -> String? {
        guard let normalizedURL = normalizedServerURL(url) else {
            return "請輸入完整的 http:// 或 https:// Open WebUI 位址。"
        }

        let duplicate = serverProfiles.first {
            $0.url.caseInsensitiveCompare(normalizedURL) == .orderedSame && $0.id != id
        }
        if duplicate != nil { return "這個伺服器位址已經在清單中。" }

        let profile = ServerProfile(
            id: id ?? UUID(),
            name: name.trimmingCharacters(in: .whitespacesAndNewlines),
            url: normalizedURL,
            lastUsedAt: Date()
        )
        if let id, let index = serverProfiles.firstIndex(where: { $0.id == id }) {
            serverProfiles[index] = profile
        } else {
            serverProfiles.insert(profile, at: 0)
        }
        selectServer(profile)
        saveServerProfiles()
        return nil
    }

    func selectServer(_ server: ServerProfile) {
        selectedServerID = server.id
        if let index = serverProfiles.firstIndex(where: { $0.id == server.id }) {
            serverProfiles[index].lastUsedAt = Date()
            baseURLText = serverProfiles[index].url
            UserDefaults.standard.set(baseURLText, forKey: "openwebui.baseURL")
        }
        UserDefaults.standard.set(server.id.uuidString, forKey: selectedServerKey)
        saveServerProfiles()
    }

    func deleteServer(_ server: ServerProfile) {
        serverProfiles.removeAll { $0.id == server.id }
        if selectedServerID == server.id {
            selectedServerID = serverProfiles.sorted { $0.lastUsedAt > $1.lastUsedAt }.first?.id
            if let activeServer { selectServer(activeServer) }
            else { UserDefaults.standard.removeObject(forKey: selectedServerKey) }
        }
        saveServerProfiles()
    }

    func startNewChat() {
        activeChatID = nil
        messages = []
        errorMessage = nil
    }

    func setWebSearch(_ enabled: Bool) {
        webSearchEnabled = enabled
        saveNativeFeatureSettings()
    }

    func setImageGeneration(_ enabled: Bool) {
        imageGenerationEnabled = enabled
        saveNativeFeatureSettings()
    }

    func setCodeInterpreter(_ enabled: Bool) {
        codeInterpreterEnabled = enabled
        saveNativeFeatureSettings()
    }

    func setMemory(_ enabled: Bool) {
        memoryEnabled = enabled
        saveNativeFeatureSettings()
    }

    func resetNativeFeatures() {
        webSearchEnabled = false
        imageGenerationEnabled = false
        codeInterpreterEnabled = false
        memoryEnabled = false
        saveNativeFeatureSettings()
    }

    func selectChat(_ session: ChatSession) {
        activeChatID = session.id
        messages = session.messages
        if models.contains(where: { $0.id == session.modelID }) {
            selectedModelID = session.modelID
        }
        errorMessage = nil
    }

    func deleteChat(_ session: ChatSession) {
        chatSessions.removeAll { $0.id == session.id }
        if activeChatID == session.id { startNewChat() }
        saveChatSessions()
    }

    func pairDesktop(using pairingURL: String) async {
        errorMessage = nil
        do {
            let pairing = try await desktopClient.pair(pairingURL: pairingURL)
            let companionURL = try desktopClient.companionBaseURL(fromPairingURL: pairingURL)
            try keychain.save(pairing.apiKey, for: "desktopAPIKey")
            UserDefaults.standard.set(companionURL, forKey: "openwebui.desktopURL")
            desktopURLText = companionURL
            desktopAPIKeyText = pairing.apiKey
            desktopConnection.url = companionURL
            await testDesktopConnection()
        } catch {
            errorMessage = error.localizedDescription
            desktopConnection.status = .unavailable
            desktopConnection.detail = "無法完成配對。請確認 QR Code 尚未過期，且手機可連到這台桌面電腦。"
        }
    }

    func unpairDesktop() {
        keychain.delete("desktopAPIKey")
        UserDefaults.standard.removeObject(forKey: "openwebui.desktopURL")
        desktopURLText = ""
        desktopAPIKeyText = ""
        desktopConnection = DesktopConnection(url: "")
        desktopWorkspaces = []
    }

    func testDesktopConnection() async {
        desktopConnection.status = .checking
        desktopConnection.url = desktopURLText
        desktopConnection.status = await desktopClient.check(urlString: desktopURLText, apiKey: desktopAPIKeyText)
        if desktopConnection.status == .connected {
            desktopConnection.detail = "已連線，可取得桌面任務狀態。"
            await refreshDesktopWorkspaces()
        } else {
            desktopWorkspaces = []
            desktopConnection.detail = "請確認桌面端已啟動、API Key 正確，並使用 LAN、Tailscale 或 ZeroTier 位址。"
        }
    }

    func refreshDesktopWorkspaces() async {
        guard !desktopURLText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              !desktopAPIKeyText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            desktopWorkspaces = []
            return
        }
        do {
            desktopWorkspaces = try await desktopClient.fetchWorkspaces(
                urlString: desktopURLText,
                apiKey: desktopAPIKeyText
            )
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func normalizedBaseURL() -> URL? {
        var value = baseURLText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty else { return nil }
        if !value.contains("://") { value = "http://\(value)" }
        while value.hasSuffix("/") { value.removeLast() }
        guard let url = URL(string: value),
              ["http", "https"].contains(url.scheme?.lowercased()),
              url.host != nil else { return nil }
        return url
    }

    private func isLoopback(_ url: URL) -> Bool {
        guard let host = url.host?.lowercased() else { return false }
        return host == "127.0.0.1" || host == "localhost" || host == "::1"
    }

    private func captureCanvasIfPresent(_ response: String) {
        guard let document = CanvasDocument.fromAssistantResponse(response) else { return }
        guard !canvasDocuments.contains(where: { $0.html == document.html }) else { return }
        canvasDocuments.insert(document, at: 0)
    }

    private func loadChatSessions() {
        guard let data = UserDefaults.standard.data(forKey: chatSessionsKey),
              let saved = try? JSONDecoder().decode([ChatSession].self, from: data) else { return }
        chatSessions = saved.sorted { $0.updatedAt > $1.updatedAt }
    }

    private func loadServerProfiles() {
        if let data = UserDefaults.standard.data(forKey: serverProfilesKey),
           let saved = try? JSONDecoder().decode([ServerProfile].self, from: data) {
            serverProfiles = saved.sorted { $0.lastUsedAt > $1.lastUsedAt }
        }
        if let rawID = UserDefaults.standard.string(forKey: selectedServerKey) {
            selectedServerID = UUID(uuidString: rawID)
        }
        if selectedServerID == nil || !serverProfiles.contains(where: { $0.id == selectedServerID }) {
            selectedServerID = serverProfiles.first?.id
        }
    }

    private func migrateLegacyServerIfNeeded() {
        guard serverProfiles.isEmpty,
              let legacyURL = normalizedServerURL(baseURLText),
              !isLoopback(URL(string: legacyURL)!) else { return }
        let legacy = ServerProfile(name: "Open WebUI", url: legacyURL)
        serverProfiles = [legacy]
        selectedServerID = legacy.id
        saveServerProfiles()
    }

    private func saveServerProfiles() {
        let ordered = serverProfiles.sorted { $0.lastUsedAt > $1.lastUsedAt }
        serverProfiles = ordered
        guard let data = try? JSONEncoder().encode(ordered) else { return }
        UserDefaults.standard.set(data, forKey: serverProfilesKey)
        if let selectedServerID {
            UserDefaults.standard.set(selectedServerID.uuidString, forKey: selectedServerKey)
        }
    }

    private func normalizedServerURL(_ rawValue: String) -> String? {
        var value = rawValue.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty else { return nil }
        if !value.contains("://") { value = "http://\(value)" }
        while value.hasSuffix("/") { value.removeLast() }
        guard let url = URL(string: value),
              ["http", "https"].contains(url.scheme?.lowercased()),
              url.host != nil else { return nil }
        return url.absoluteString
    }

    private var nativeFeatures: [String: Bool] {
        [
            "web_search": webSearchEnabled,
            "image_generation": imageGenerationEnabled,
            "code_interpreter": codeInterpreterEnabled,
            "memory": memoryEnabled
        ]
    }

    private func loadNativeFeatureSettings() {
        guard let values = UserDefaults.standard.dictionary(forKey: nativeFeaturesKey) as? [String: Bool] else { return }
        webSearchEnabled = values["web_search"] ?? false
        imageGenerationEnabled = values["image_generation"] ?? false
        codeInterpreterEnabled = values["code_interpreter"] ?? false
        memoryEnabled = values["memory"] ?? false
    }

    private func saveNativeFeatureSettings() {
        UserDefaults.standard.set(nativeFeatures, forKey: nativeFeaturesKey)
    }

    private func saveChatSessions() {
        guard let data = try? JSONEncoder().encode(chatSessions) else { return }
        UserDefaults.standard.set(data, forKey: chatSessionsKey)
    }

    private func persistActiveChat(defaultTitle: String) {
        guard let activeChatID, !messages.isEmpty else { return }
        let existing = chatSessions.first(where: { $0.id == activeChatID })
        let session = ChatSession(
            id: activeChatID,
            title: existing?.title ?? defaultTitle,
            modelID: selectedModelID,
            messages: messages,
            createdAt: existing?.createdAt ?? Date(),
            updatedAt: Date()
        )
        chatSessions.removeAll { $0.id == activeChatID }
        chatSessions.insert(session, at: 0)
        saveChatSessions()
    }
}

private extension CanvasDocument {
    static func fromAssistantResponse(_ value: String) -> CanvasDocument? {
        let html: String
        if let htmlFence = value.range(of: "```html", options: .caseInsensitive) {
            let bodyStart = value[htmlFence.upperBound...].drop(while: { $0 == "\n" || $0 == "\r" })
            let body = String(bodyStart)
            html = body.components(separatedBy: "```").first ?? body
        } else if let documentStart = value.range(of: "<!doctype html", options: .caseInsensitive) ?? value.range(of: "<html", options: .caseInsensitive) {
            html = String(value[documentStart.lowerBound...])
        } else {
            return nil
        }

        let title: String
        if let titleStart = html.range(of: "<title>", options: .caseInsensitive),
           let titleEnd = html.range(of: "</title>", options: .caseInsensitive, range: titleStart.upperBound..<html.endIndex) {
            title = String(html[titleStart.upperBound..<titleEnd.lowerBound]).trimmingCharacters(in: .whitespacesAndNewlines)
        } else {
            title = "未命名網頁"
        }
        let preview = value.replacingOccurrences(of: "\n", with: " ").prefix(100)
        return CanvasDocument(title: title.isEmpty ? "未命名網頁" : title, html: html, sourcePreview: String(preview))
    }
}
