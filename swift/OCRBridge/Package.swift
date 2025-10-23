// swift-tools-version:5.8
import PackageDescription

let package = Package(
    name: "OCRBridge",
    platforms: [
        .macOS(.v12)
    ],
    products: [
        .executable(name: "ocrbridge", targets: ["OCRBridge"])
    ],
    targets: [
        .executableTarget(
            name: "OCRBridge",
            dependencies: [],
            linkerSettings: [
                .linkedFramework("Vision"),
                .linkedFramework("AppKit"),
                .linkedFramework("CoreGraphics"),
                .linkedFramework("ImageIO")
            ]
        )
    ]
)