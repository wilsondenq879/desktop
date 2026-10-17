import AVFoundation
import SwiftUI

struct QRCodeScannerView: UIViewControllerRepresentable {
    let onCode: (String) -> Void
    let onFailure: (String) -> Void

    func makeUIViewController(context: Context) -> QRCodeScannerController {
        let controller = QRCodeScannerController()
        controller.onCode = onCode
        controller.onFailure = onFailure
        return controller
    }

    func updateUIViewController(_ uiViewController: QRCodeScannerController, context: Context) {}
}

final class QRCodeScannerController: UIViewController, AVCaptureMetadataOutputObjectsDelegate {
    var onCode: ((String) -> Void)?
    var onFailure: ((String) -> Void)?
    private let session = AVCaptureSession()
    private var previewLayer: AVCaptureVideoPreviewLayer?
    private var didReadCode = false

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        configureCamera()
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        previewLayer?.frame = view.bounds
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        session.stopRunning()
    }

    private func configureCamera() {
        AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
            DispatchQueue.main.async {
                guard let self else { return }
                guard granted else {
                    self.onFailure?("請允許相機權限，才能掃描桌面端配對 QR Code。")
                    return
                }
                guard let device = AVCaptureDevice.default(for: .video) else {
                    self.onFailure?("此裝置無法使用相機掃描 QR Code。")
                    return
                }
                do {
                    let input = try AVCaptureDeviceInput(device: device)
                    guard self.session.canAddInput(input) else { throw ScannerError.inputUnavailable }
                    self.session.addInput(input)
                    let output = AVCaptureMetadataOutput()
                    guard self.session.canAddOutput(output) else { throw ScannerError.outputUnavailable }
                    self.session.addOutput(output)
                    output.setMetadataObjectsDelegate(self, queue: .main)
                    output.metadataObjectTypes = [.qr]
                    let layer = AVCaptureVideoPreviewLayer(session: self.session)
                    layer.videoGravity = .resizeAspectFill
                    layer.frame = self.view.bounds
                    self.view.layer.addSublayer(layer)
                    self.previewLayer = layer
                    DispatchQueue.global(qos: .userInitiated).async { self.session.startRunning() }
                } catch {
                    self.onFailure?("無法啟動相機：\(error.localizedDescription)")
                }
            }
        }
    }

    func metadataOutput(
        _ output: AVCaptureMetadataOutput,
        didOutput metadataObjects: [AVMetadataObject],
        from connection: AVCaptureConnection
    ) {
        guard !didReadCode,
              let code = metadataObjects.compactMap({ $0 as? AVMetadataMachineReadableCodeObject }).first?.stringValue else { return }
        didReadCode = true
        session.stopRunning()
        onCode?(code)
    }

    private enum ScannerError: LocalizedError {
        case inputUnavailable
        case outputUnavailable

        var errorDescription: String? {
            switch self {
            case .inputUnavailable: return "相機輸入不可用。"
            case .outputUnavailable: return "QR Code 掃描器不可用。"
            }
        }
    }
}
