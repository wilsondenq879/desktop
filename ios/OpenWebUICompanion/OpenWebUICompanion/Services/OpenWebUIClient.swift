import Foundation

final class OpenWebUIClient {
    private let decoder = JSONDecoder()
    private let encoder = JSONEncoder()

    var baseURL: URL
    var token: String?

    init(baseURL: URL, token: String? = nil) {
        self.baseURL = baseURL
        self.token = token
    }

    func signIn(email: String, password: String) async throws -> SignInResponse {
        let response: SignInResponse = try await request(
            path: "api/v1/auths/signin",
            method: "POST",
            body: ["email": email, "password": password],
            authenticated: false
        )
        token = response.token
        return response
    }

    func fetchModels() async throws -> [OpenWebUIModel] {
        let data = try await rawRequest(path: "api/models", method: "GET", body: nil)
        if let envelope = try? decoder.decode(ModelEnvelope.self, from: data) {
            return envelope.data ?? envelope.models ?? []
        }
        if let models = try? decoder.decode([OpenWebUIModel].self, from: data) {
            return models
        }
        throw APIError.emptyModelList
    }

    func fetchTools() async throws -> [OpenWebUITool] {
        try await fetchCollection(
            paths: [
                "api/v1/tools/",
                "api/v1/tools/list",
                "api/v1/tools",
                "api/v1/functions/",
                "api/v1/functions"
            ],
            collectionKeys: ["data", "items", "tools", "functions"],
            as: OpenWebUITool.self
        )
    }

    func fetchSkills() async throws -> [OpenWebUISkill] {
        try await fetchCollection(
            paths: [
                "api/v1/skills/",
                "api/v1/skills/list",
                "api/v1/skills",
                "api/skills/",
                "api/skills"
            ],
            collectionKeys: ["data", "items", "skills"],
            as: OpenWebUISkill.self
        )
    }

    func uploadFile(data: Data, fileName: String, mimeType: String) async throws -> FileAttachment {
        guard let url = endpoint("api/v1/files/") else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token ?? "")", forHTTPHeaderField: "Authorization")
        let boundary = "Boundary-\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        var body = Data()
        body.append(Data("--\(boundary)\r\n".utf8))
        body.append(Data("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileName.replacingOccurrences(of: "\"", with: ""))\"\r\n".utf8))
        body.append(Data("Content-Type: \(mimeType)\r\n\r\n".utf8))
        body.append(data)
        body.append(Data("\r\n--\(boundary)--\r\n".utf8))
        request.httpBody = body
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response: response, data: data)
        let payload = try decoder.decode(FileUploadResponse.self, from: data)
        return FileAttachment(id: payload.id, name: fileName, mimeType: mimeType)
    }

    func streamChat(
        model: String,
        messages: [ChatMessage],
        attachments: [FileAttachment],
        toolIDs: [String] = [],
        skillIDs: [String] = [],
        features: [String: Bool] = [:]
    ) -> AsyncThrowingStream<String, Error> {
        AsyncThrowingStream { continuation in
            Task {
                do {
                    guard let url = endpoint("api/chat/completions") else { throw APIError.invalidURL }
                    var request = URLRequest(url: url)
                    request.httpMethod = "POST"
                    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                    request.setValue("Bearer \(token ?? "")", forHTTPHeaderField: "Authorization")
                    let apiMessages = messages.map { ["role": $0.role.rawValue, "content": $0.content] }
                    var payload: [String: Any] = [
                        "model": model,
                        "stream": true,
                        "messages": apiMessages
                    ]
                    if !attachments.isEmpty {
                        payload["files"] = attachments.map { ["type": "file", "id": $0.id] }
                    }
                    if !toolIDs.isEmpty { payload["tool_ids"] = toolIDs }
                    // Skills are a separate Workspace resource in current Open WebUI
                    // versions. Sending them in tool_ids silently prevents the
                    // skill instruction from being resolved.
                    if !skillIDs.isEmpty { payload["skill_ids"] = skillIDs }
                    if !features.isEmpty { payload["features"] = features }
                    request.httpBody = try JSONSerialization.data(withJSONObject: payload)
                    let (bytes, response) = try await URLSession.shared.bytes(for: request)
                    guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
                    guard (200..<300).contains(http.statusCode) else {
                        let message = (try? await bytes.lines.reduce(into: "") { result, line in
                            result += line
                        }) ?? ""
                        throw APIError.server(statusCode: http.statusCode, message: message)
                    }
                    for try await line in bytes.lines {
                        guard line.hasPrefix("data:") else { continue }
                        let value = line.dropFirst(5).trimmingCharacters(in: .whitespaces)
                        if value == "[DONE]" { break }
                        guard let data = value.data(using: .utf8),
                              let chunk = try? JSONDecoder().decode(StreamChunk.self, from: data) else { continue }
                        let delta = chunk.choices?.first?.delta?.content ?? chunk.choices?.first?.message?.content
                        if let delta, !delta.isEmpty { continuation.yield(delta) }
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    private func request<T: Decodable>(
        path: String,
        method: String,
        body: [String: String]?,
        authenticated: Bool
    ) async throws -> T {
        let data = try await rawRequest(path: path, method: method, body: body, authenticated: authenticated)
        do { return try decoder.decode(T.self, from: data) }
        catch { throw APIError.invalidResponse }
    }

    private func rawRequest(
        path: String,
        method: String,
        body: [String: String]?,
        authenticated: Bool = true
    ) async throws -> Data {
        guard let url = endpoint(path) else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if body != nil { request.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        if authenticated, let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let body { request.httpBody = try encoder.encode(body) }
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response: response, data: data)
        return data
    }

    private func fetchCollection<T: Decodable>(
        paths: [String],
        collectionKeys: [String],
        as type: T.Type
    ) async throws -> [T] {
        var failures: [String] = []
        for path in paths {
            do {
                let data = try await rawRequest(path: path, method: "GET", body: nil)
                if let values = try? decoder.decode([T].self, from: data) { return values }
                if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    if let values = decodeNestedCollection(
                        object,
                        collectionKeys: Set(collectionKeys),
                        as: T.self
                    ) {
                        return values
                    }
                }
                failures.append("\(path)：\(payloadSummary(data))")
            } catch {
                failures.append("\(path)：\(error.localizedDescription)")
            }
        }
        throw APIError.capabilityUnavailable(failures.joined(separator: "\n"))
    }

    /// Open WebUI endpoints have returned direct arrays, object indexes, and
    /// envelopes such as `{ data: { items: [...] } }` across releases.  Locate
    /// a collection by its decodable item shape rather than relying on one
    /// server-version-specific wrapper key.
    private func decodeNestedCollection<T: Decodable>(
        _ object: [String: Any],
        collectionKeys: Set<String>,
        as type: T.Type,
        depth: Int = 0
    ) -> [T]? {
        guard depth < 5 else { return nil }

        if JSONSerialization.isValidJSONObject(object),
           let objectData = try? JSONSerialization.data(withJSONObject: object),
           let indexed = try? decoder.decode([String: T].self, from: objectData) {
            return indexed.values.sorted { String(describing: $0) < String(describing: $1) }
        }

        // Prefer Open WebUI's known wrappers. This preserves the expected
        // ordering whenever the response exposes an ordered array.
        for key in collectionKeys {
            guard let candidate = object[key] else { continue }
            if let decoded = decodeCollectionValue(candidate, collectionKeys: collectionKeys, as: T.self, depth: depth + 1) {
                return decoded
            }
        }

        // Some reverse proxies or older Desktop builds wrap the payload in an
        // unnamed object. Walk those values as a final compatibility path.
        for candidate in object.values {
            if let decoded = decodeCollectionValue(candidate, collectionKeys: collectionKeys, as: T.self, depth: depth + 1) {
                return decoded
            }
        }
        return nil
    }

    private func decodeCollectionValue<T: Decodable>(
        _ value: Any,
        collectionKeys: Set<String>,
        as type: T.Type,
        depth: Int
    ) -> [T]? {
        guard JSONSerialization.isValidJSONObject(value),
              let data = try? JSONSerialization.data(withJSONObject: value) else { return nil }
        if let decoded = try? decoder.decode([T].self, from: data) { return decoded }
        if let indexed = try? decoder.decode([String: T].self, from: data) { return Array(indexed.values) }
        guard let nestedObject = value as? [String: Any] else { return nil }
        return decodeNestedCollection(nestedObject, collectionKeys: collectionKeys, as: T.self, depth: depth)
    }

    private func payloadSummary(_ data: Data) -> String {
        guard let preview = String(data: data.prefix(140), encoding: .utf8) else {
            return "回應不是可讀取的 JSON"
        }
        let compact = preview
            .replacingOccurrences(of: "\n", with: " ")
            .replacingOccurrences(of: "\r", with: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        if compact.hasPrefix("<") { return "伺服器回傳 HTML，不是 API JSON" }
        return "回應結構無法辨識：\(compact)"
    }

    private func endpoint(_ path: String) -> URL? {
        var url = baseURL
        for component in path.split(separator: "/") { url.appendPathComponent(String(component)) }
        return url
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            if http.statusCode == 401 { throw APIError.unauthorized }
            let message = String(data: data, encoding: .utf8) ?? HTTPURLResponse.localizedString(forStatusCode: http.statusCode)
            throw APIError.server(statusCode: http.statusCode, message: message)
        }
    }

    private struct ModelEnvelope: Decodable {
        let data: [OpenWebUIModel]?
        let models: [OpenWebUIModel]?
    }

    private struct FileUploadResponse: Decodable { let id: String }

    private struct StreamChunk: Decodable {
        let choices: [Choice]?
        struct Choice: Decodable {
            let delta: Delta?
            let message: Delta?
        }
        struct Delta: Decodable { let content: String? }
    }
}
