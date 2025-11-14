import Foundation
import Vision
import ImageIO
import CoreGraphics
import AppKit

struct OCRRequest: Codable {
    let cmd: String
    let image_path: String?
    let page_index: Int?
    let width: Int?
    let height: Int?
    let dpi: Int?
    let languages: [String]?
    let recognition_level: String?
    let uses_cpu_only: Bool?
    let auto_detect_language: Bool?
}

struct OCRItemOut: Codable {
    struct BBox: Codable { let x: Double; let y: Double; let w: Double; let h: Double }
    let text: String
    let bbox: BBox
    let confidence: Double
}

struct OCRResponse: Codable {
    let type: String  // "result" or "error"
    let page_index: Int?
    let width: Int?
    let height: Int?
    let items: [OCRItemOut]?
    let message: String?
}

func loadCGImage(from path: String) throws -> CGImage {
    let url = URL(fileURLWithPath: path)
    guard let src = CGImageSourceCreateWithURL(url as CFURL, nil) else {
        throw NSError(domain: "OCRBridge", code: 1, userInfo: [NSLocalizedDescriptionKey: "无法创建图像源"]) }
    guard let cg = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
        throw NSError(domain: "OCRBridge", code: 2, userInfo: [NSLocalizedDescriptionKey: "无法读取CGImage"]) }
    return cg
}

let queue = OperationQueue()
queue.maxConcurrentOperationCount = ProcessInfo.processInfo.activeProcessorCount
queue.qualityOfService = .userInitiated

let encoder = JSONEncoder()
encoder.outputFormatting = []

func performOCR(path: String, pageIndex: Int, width: Int, height: Int, dpi: Int, langs: [String], recognitionLevel: String?, usesCPUOnly: Bool?, autoDetectLanguage: Bool?) {
    queue.addOperation {
        do {
            let cg = try loadCGImage(from: path)
            let req = VNRecognizeTextRequest()
            
            // 设置识别级别
            if let level = recognitionLevel, level == "fast" {
                req.recognitionLevel = .fast
            } else {
                req.recognitionLevel = .accurate  // 默认值
            }
            
            req.usesLanguageCorrection = true
            req.minimumTextHeight = 0.02 // 约束过小文字
            
            // 设置支持的语言，确保中文识别
            if !langs.isEmpty { 
                req.recognitionLanguages = langs 
            } else {
                req.recognitionLanguages = ["zh-Hans", "zh-Hant", "en-US"]
            }
            
            // 针对中文优化的额外设置
            if #available(macOS 13.0, *) {
                req.revision = VNRecognizeTextRequestRevision3
                // 自动语言检测（可与指定语言同时使用，提升混合文本识别）
                if let autoDetect = autoDetectLanguage {
                    req.automaticallyDetectsLanguage = autoDetect
                } else {
                    req.automaticallyDetectsLanguage = true  // 默认启用自动检测
                }
            }
            
            // 启用 Neural Engine/GPU 加速
            let options: [VNImageOption: Any] = [
                .properties: [:]
            ]
            let handler = VNImageRequestHandler(cgImage: cg, options: options)
            
            // 设置CPU/GPU使用
            if #available(macOS 12.0, *) {
                if let cpuOnly = usesCPUOnly {
                    req.usesCPUOnly = cpuOnly
                } else {
                    req.usesCPUOnly = false  // 默认启用 Neural Engine/GPU
                }
            }
            
            try handler.perform([req])
            let observations = (req.results as? [VNRecognizedTextObservation]) ?? []
            var items: [OCRItemOut] = []
            items.reserveCapacity(observations.count)
            for obs in observations {
                guard let top = obs.topCandidates(1).first else { continue }
                let bb = obs.boundingBox // 归一化坐标，原点左下
                let item = OCRItemOut(
                    text: top.string,
                    bbox: .init(x: Double(bb.origin.x), y: Double(bb.origin.y), w: Double(bb.size.width), h: Double(bb.size.height)),
                    confidence: Double(obs.confidence)
                )
                items.append(item)
            }
            let out = OCRResponse(type: "result", page_index: pageIndex, width: width, height: height, items: items, message: nil)
            if let data = try? encoder.encode(out) {
                if let s = String(data: data, encoding: .utf8) {
                    if let outputData = s.data(using: .utf8) {
                        FileHandle.standardOutput.write(outputData)
                        if let newlineData = "\n".data(using: .utf8) {
                            FileHandle.standardOutput.write(newlineData)
                        }
                    }
                }
            }
        } catch {
            let out = OCRResponse(type: "error", page_index: pageIndex, width: width, height: height, items: nil, message: error.localizedDescription)
            if let data = try? encoder.encode(out) {
                if let s = String(data: data, encoding: .utf8) {
                    if let outputData = s.data(using: .utf8) {
                        FileHandle.standardOutput.write(outputData)
                        if let newlineData = "\n".data(using: .utf8) {
                            FileHandle.standardOutput.write(newlineData)
                        }
                    }
                }
            }
        }
    }
}

// 主循环：读取JSON行命令
while let line = readLine() {
    guard let data = line.data(using: .utf8) else { continue }
    let decoder = JSONDecoder()
    guard let req = try? decoder.decode(OCRRequest.self, from: data) else {
        let out = OCRResponse(type: "error", page_index: nil, width: nil, height: nil, items: nil, message: "无法解析请求")
        if let d = try? encoder.encode(out) {
            if let s = String(data: d, encoding: .utf8) {
                if let outputData = s.data(using: .utf8) {
                    FileHandle.standardOutput.write(outputData)
                    if let newlineData = "\n".data(using: .utf8) {
                        FileHandle.standardOutput.write(newlineData)
                    }
                }
            }
        }
        continue
    }
    if req.cmd == "stop" { break }
    if req.cmd == "ocr" {
        guard let p = req.image_path, let idx = req.page_index, let w = req.width, let h = req.height else {
            let out = OCRResponse(type: "error", page_index: req.page_index, width: req.width, height: req.height, items: nil, message: "缺少必要字段")
            if let d = try? encoder.encode(out) {
                if let s = String(data: d, encoding: .utf8) {
                    if let outputData = s.data(using: .utf8) {
                        FileHandle.standardOutput.write(outputData)
                        if let newlineData = "\n".data(using: .utf8) {
                            FileHandle.standardOutput.write(newlineData)
                        }
                    }
                }
            }
            continue
        }
        let dpi = req.dpi ?? 300
        let langs = req.languages ?? ["zh-Hans", "zh-Hant", "en-US"]
        performOCR(path: p, pageIndex: idx, width: w, height: h, dpi: dpi, langs: langs, recognitionLevel: req.recognition_level, usesCPUOnly: req.uses_cpu_only, autoDetectLanguage: req.auto_detect_language)
    }
}

// 等待队列完成
queue.waitUntilAllOperationsAreFinished()