import SwiftUI
import WebKit

struct CanvasView: View {
    @EnvironmentObject private var store: AppStore
    @State private var selectedDocument: CanvasDocument?

    var body: some View {
        NavigationStack {
            ZStack {
                TechBackground()
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        HStack(alignment: .top) {
                            VStack(alignment: .leading, spacing: 6) {
                                TechSectionLabel(title: "LIVE OUTPUT", systemImage: "rectangle.3.group.bubble.left")
                                Text("Canvas")
                                    .font(.largeTitle.bold())
                                Text("對話中產生的 HTML 網頁會直接在這裡預覽。")
                                    .font(.subheadline)
                                    .foregroundStyle(TechTheme.secondaryText)
                            }
                            Spacer()
                            Image(systemName: "sparkles.rectangle.stack.fill")
                                .font(.title)
                                .foregroundStyle(TechTheme.cyan)
                                .accessibilityHidden(true)
                        }

                        if store.canvasDocuments.isEmpty {
                            TechPanel {
                                VStack(alignment: .leading, spacing: 14) {
                                    Image(systemName: "chevron.left.forwardslash.chevron.right")
                                        .font(.system(size: 34, weight: .semibold))
                                        .foregroundStyle(TechTheme.teal)
                                        .accessibilityHidden(true)
                                    Text("還沒有可預覽的網頁")
                                        .font(.headline)
                                    Text("在聊天中要求模型「做一個可在 Canvas 預覽的單檔 HTML 網頁」。完成後會自動出現在這裡。")
                                        .font(.subheadline)
                                        .foregroundStyle(TechTheme.secondaryText)
                                }
                                .padding(20)
                            }
                        } else {
                            ForEach(store.canvasDocuments) { document in
                                Button {
                                    selectedDocument = document
                                } label: {
                                    TechPanel {
                                        HStack(spacing: 14) {
                                            ZStack {
                                                RoundedRectangle(cornerRadius: 14, style: .continuous)
                                                    .fill(TechTheme.cyan.opacity(0.16))
                                                    .frame(width: 52, height: 52)
                                                Image(systemName: "globe.asia.australia.fill")
                                                    .foregroundStyle(TechTheme.cyan)
                                            }
                                            VStack(alignment: .leading, spacing: 4) {
                                                Text(document.title)
                                                    .font(.headline)
                                                    .lineLimit(1)
                                                Text(document.sourcePreview)
                                                    .font(.caption)
                                                    .foregroundStyle(TechTheme.secondaryText)
                                                    .lineLimit(2)
                                            }
                                            Spacer(minLength: 0)
                                            Image(systemName: "arrow.up.right.square")
                                                .foregroundStyle(TechTheme.cyan)
                                        }
                                        .padding(16)
                                    }
                                }
                                .buttonStyle(.plain)
                                .accessibilityLabel("開啟 Canvas：\(document.title)")
                            }
                        }
                    }
                    .padding(20)
                    .padding(.bottom, 36)
                }
            }
            .navigationTitle("Canvas")
            .navigationBarTitleDisplayMode(.inline)
            .navigationDestination(item: $selectedDocument) { document in
                CanvasPreviewView(document: document)
            }
        }
    }
}

private struct CanvasPreviewView: View {
    let document: CanvasDocument

    var body: some View {
        WebPreview(html: document.html)
            .navigationTitle(document.title)
            .navigationBarTitleDisplayMode(.inline)
            .ignoresSafeArea(edges: .bottom)
    }
}

private struct WebPreview: UIViewRepresentable {
    let html: String

    func makeUIView(context: Context) -> WKWebView {
        let preferences = WKWebpagePreferences()
        preferences.allowsContentJavaScript = true
        let configuration = WKWebViewConfiguration()
        configuration.defaultWebpagePreferences = preferences
        let view = WKWebView(frame: .zero, configuration: configuration)
        view.isOpaque = false
        view.backgroundColor = .clear
        view.scrollView.backgroundColor = .clear
        return view
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {
        uiView.loadHTMLString(html, baseURL: nil)
    }
}
