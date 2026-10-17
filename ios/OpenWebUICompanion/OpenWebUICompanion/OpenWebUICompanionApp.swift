import SwiftUI

@main
struct OpenWebUICompanionApp: App {
    @StateObject private var store = AppStore()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(store)
                .tint(Color(red: 0.05, green: 0.58, blue: 0.52))
        }
    }
}
