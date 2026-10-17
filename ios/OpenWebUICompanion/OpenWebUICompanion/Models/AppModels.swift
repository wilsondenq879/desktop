import Foundation

struct ServerProfile: Identifiable, Hashable, Codable, Sendable {
    let id: UUID
    var name: String
    var url: String
    var lastUsedAt: Date

    init(id: UUID = UUID(), name: String, url: String, lastUsedAt: Date = Date()) {
        self.id = id
        self.name = name
        self.url = url
        self.lastUsedAt = lastUsedAt
    }

    var displayName: String {
        let compact = name.trimmingCharacters(in: .whitespacesAndNewlines)
        return compact.isEmpty ? url : compact
    }
}

struct OpenWebUIUser: Codable, Sendable {
    let id: String?
    let email: String?
    let name: String?
}

struct SignInResponse: Codable, Sendable {
    let token: String
    let user: OpenWebUIUser?
}

struct OpenWebUIModel: Codable, Identifiable, Hashable, Sendable {
    let id: String
    let name: String?
    let ownedBy: String?

    var displayName: String { name ?? id }

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case ownedBy = "owned_by"
    }
}

struct OpenWebUITool: Decodable, Identifiable, Hashable, Sendable {
    let id: String
    let name: String?
    let description: String?

    var displayName: String { name ?? id }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        let meta = try? container.decode(CapabilityMeta.self, forKey: .meta)
        let info = try? container.decode(CapabilityInfo.self, forKey: .info)
        name = (try? container.decode(String.self, forKey: .name)) ?? meta?.name ?? info?.meta?.name
        description = (try? container.decode(String.self, forKey: .description)) ?? meta?.description ?? info?.meta?.description
    }

    private enum CodingKeys: String, CodingKey { case id, name, description, meta, info }
}

struct OpenWebUISkill: Decodable, Identifiable, Hashable, Sendable {
    let id: String
    let name: String?
    let description: String?
    let isActive: Bool?

    var displayName: String { name ?? id }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        let meta = try? container.decode(CapabilityMeta.self, forKey: .meta)
        let info = try? container.decode(CapabilityInfo.self, forKey: .info)
        name = (try? container.decode(String.self, forKey: .name)) ?? meta?.name ?? info?.meta?.name
        description = (try? container.decode(String.self, forKey: .description)) ?? meta?.description ?? info?.meta?.description
        isActive = (try? container.decode(Bool.self, forKey: .isActive)) ?? meta?.isActive ?? info?.meta?.isActive
    }

    private enum CodingKeys: String, CodingKey { case id, name, description, meta, info, isActive = "is_active" }
}

private struct CapabilityInfo: Decodable, Hashable, Sendable { let meta: CapabilityMeta? }
private struct CapabilityMeta: Decodable, Hashable, Sendable {
    let name: String?
    let description: String?
    let isActive: Bool?

    enum CodingKeys: String, CodingKey { case name, description, isActive = "is_active" }
}

struct ChatMessage: Identifiable, Hashable, Codable, Sendable {
    let id: UUID
    let role: Role
    var content: String
    var createdAt: Date
    var attachments: [FileAttachment]

    enum Role: String, Codable, Sendable {
        case user
        case assistant
        case system
    }

    init(role: Role, content: String, attachments: [FileAttachment] = []) {
        self.id = UUID()
        self.role = role
        self.content = content
        self.createdAt = Date()
        self.attachments = attachments
    }
}

struct FileAttachment: Identifiable, Hashable, Codable, Sendable {
    let id: String
    let name: String
    let mimeType: String
}

struct ChatSession: Identifiable, Hashable, Codable, Sendable {
    let id: UUID
    var title: String
    var modelID: String
    var messages: [ChatMessage]
    let createdAt: Date
    var updatedAt: Date

    init(id: UUID = UUID(), title: String, modelID: String, messages: [ChatMessage], createdAt: Date = Date(), updatedAt: Date = Date()) {
        self.id = id
        self.title = title
        self.modelID = modelID
        self.messages = messages
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }

    static func title(for text: String) -> String {
        let firstLine = text
            .split(whereSeparator: \.isNewline)
            .first
            .map(String.init) ?? "新對話"
        let compact = firstLine.trimmingCharacters(in: .whitespacesAndNewlines)
        guard compact.count > 28 else { return compact.isEmpty ? "新對話" : compact }
        return String(compact.prefix(28)) + "…"
    }
}

struct CanvasDocument: Identifiable, Hashable, Sendable {
    let id: UUID
    let title: String
    let html: String
    let createdAt: Date
    let sourcePreview: String

    init(title: String, html: String, sourcePreview: String) {
        self.id = UUID()
        self.title = title
        self.html = html
        self.createdAt = Date()
        self.sourcePreview = sourcePreview
    }
}

struct DesktopPairingResponse: Decodable, Sendable {
    let version: Int
    let apiKey: String
    let expiresAt: String
    let service: String

    enum CodingKeys: String, CodingKey {
        case version
        case apiKey
        case expiresAt
        case service
    }
}

struct DesktopConnection: Sendable {
    var url: String
    var status: ConnectionStatus = .unknown
    var detail: String = ""

    enum ConnectionStatus: String, Sendable {
        case unknown
        case checking
        case connected
        case unavailable
    }
}

struct WorkspaceActivity: Codable, Identifiable, Sendable {
    let id: String
    let label: String
    let detail: String?
    let status: String
    let time: String
}

struct WorkspaceChange: Codable, Identifiable, Sendable {
    var id: String { path }
    let path: String
    let kind: String
    let restorable: Bool
    let beforeSize: Int
    let afterSize: Int
    let previewable: Bool
}

struct WorkspaceArtifact: Codable, Identifiable, Sendable {
    var id: String { path }
    let path: String
    let name: String
    let `extension`: String
    let size: Int
    let kind: String
    let previewKind: String
}

struct WorkspaceLimits: Codable, Sendable {
    let files: Int
    let snapshotBytes: Int
    let skippedFiles: Int
    let truncated: Bool
}

struct DesktopWorkspace: Codable, Identifiable, Sendable {
    let id: String
    let connectionId: String
    let chatId: String
    let projectPath: String
    let status: String
    let startedAt: String
    let completedAt: String?
    let restoredAt: String?
    let activities: [WorkspaceActivity]
    let changes: [WorkspaceChange]
    let artifacts: [WorkspaceArtifact]
    let limits: WorkspaceLimits
    let error: String?

    var projectName: String {
        projectPath.replacingOccurrences(of: "\\", with: "/").split(separator: "/").last.map(String.init) ?? projectPath
    }
}

enum APIError: LocalizedError, Sendable {
    case invalidURL
    case loopbackURL
    case connectionFailed(String)
    case unauthorized
    case server(statusCode: Int, message: String)
    case invalidResponse
    case emptyModelList
    case capabilityUnavailable(String)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "伺服器位址格式不正確。"
        case .loopbackURL:
            return "手機不能連到 127.0.0.1 或 localhost。請填入 Windows 電腦的區域網路、Tailscale 或 ZeroTier 位址。"
        case let .connectionFailed(address):
            return "無法連線到 \(address)。請確認 Windows 上的 Open WebUI 已啟動、服務監聽區域網路，且防火牆已放行該連接埠。"
        case .unauthorized:
            return "登入資訊已失效，請重新登入。"
        case let .server(statusCode, message):
            return "伺服器錯誤（\(statusCode)）：\(message)"
        case .invalidResponse:
            return "伺服器回應格式無法解析。"
        case .emptyModelList:
            return "目前沒有可用模型。"
        case let .capabilityUnavailable(detail):
            return "無法讀取 Workspace 能力。\n\(detail)"
        }
    }
}
