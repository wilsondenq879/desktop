import Foundation

final class DesktopCompanionClient {
    func pair(pairingURL: String) async throws -> DesktopPairingResponse {
        guard let url = normalizedURL(pairingURL) else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 10
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "Desktop pairing failed."
            throw APIError.server(statusCode: http.statusCode, message: message)
        }
        return try JSONDecoder().decode(DesktopPairingResponse.self, from: data)
    }

    func companionBaseURL(fromPairingURL pairingURL: String) throws -> String {
        guard let url = normalizedURL(pairingURL),
              let scheme = url.scheme,
              let host = url.host else { throw APIError.invalidURL }
        var components = URLComponents()
        components.scheme = scheme
        components.host = host
        components.port = url.port
        guard let value = components.url?.absoluteString else { throw APIError.invalidURL }
        return value
    }

    func check(urlString: String, apiKey: String) async -> DesktopConnection.ConnectionStatus {
        guard let url = normalizedURL(urlString) else { return .unavailable }
        var request = URLRequest(url: url.appendingPathComponent("health"))
        request.timeoutInterval = 3
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else { return .unavailable }
            return .connected
        } catch {
            return .unavailable
        }
    }

    func fetchWorkspaces(urlString: String, apiKey: String) async throws -> [DesktopWorkspace] {
        guard let url = normalizedURL(urlString) else { throw APIError.invalidURL }
        var request = URLRequest(url: url.appendingPathComponent("api/desktop/workspaces"))
        request.timeoutInterval = 8
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "Desktop Companion API request failed."
            throw APIError.server(statusCode: http.statusCode, message: message)
        }
        return try JSONDecoder().decode(DesktopWorkspacesResponse.self, from: data).workspaces
    }

    private func normalizedURL(_ value: String) -> URL? {
        var trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        if !trimmed.contains("://") { trimmed = "http://\(trimmed)" }
        guard let url = URL(string: trimmed), url.scheme == "http" || url.scheme == "https" else { return nil }
        return url
    }
}

private struct DesktopWorkspacesResponse: Decodable, Sendable {
    let workspaces: [DesktopWorkspace]
}
