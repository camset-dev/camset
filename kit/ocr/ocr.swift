// Text in images with Apple's Vision framework, for the camset kit (kit/camkit/ocr.py).
// Usage: ocr IMAGE...
// Prints one JSON line per image, in the order given: {"file": ..., "lines": [{"text", "conf", "x", "y", "w", "h"}]},
// with "error" too, and "lines" empty, when the image could not be read, Vision failed on it, or its result could not
// be written. kit/camkit/ocr.py matches each line to its frame by "file", and takes a line carrying "error" as a
// failed reading (it raises, with these words and the frame's name), never as a frame without text. Boxes are in the
// image's pixels, origin top-left, lines in reading order (readingOrder). Language correction is off: menu labels are
// not prose.
import AppKit
import Foundation
import Vision

struct Line {
    let text: String
    let conf: Double
    let x: Int, y: Int, w: Int, h: Int

    var json: [String: Any] { ["text": text, "conf": conf, "x": x, "y": y, "w": w, "h": h] }
}

// Reading order as the kit's runs were made with: two lines more than 8 px apart in height by their top edges, else
// by their left edges. That comparison is no strict ordering (of lines with tops at 0, 6 and 12 px, the first two and
// the last two go by left edge, the first and last by top), so where tops chain like that the order is the sort's,
// and kit/camkit/ocr.py's RapidOCR path, which groups rows by their first line, can order them otherwise. It is kept
// as it was, since the a1 II's frames were read with it.
func readingOrder(_ lines: [Line]) -> [Line] {
    lines.sorted { a, b in abs(a.y - b.y) > 8 ? a.y < b.y : a.x < b.x }
}

// The image's text lines, or why there are none to give.
func recognize(_ path: String) -> (lines: [Line], error: String?) {
    guard let picture = NSImage(contentsOfFile: path),
          let image = picture.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        return ([], "the image could not be read")
    }
    let width = Double(image.width), height = Double(image.height)
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    do {
        try VNImageRequestHandler(cgImage: image).perform([request])
    } catch {
        return ([], "Vision: \(error.localizedDescription)")
    }
    var lines: [Line] = []
    for observation in request.results ?? [] {
        guard let best = observation.topCandidates(1).first else { continue }
        let b = observation.boundingBox   // normalised, origin bottom-left
        let conf = Double(best.confidence)
        lines.append(Line(text: best.string, conf: conf.isFinite ? conf : 0,
                          x: Int(b.minX * width), y: Int((1 - b.maxY) * height),
                          w: Int(b.width * width), h: Int(b.height * height)))
    }
    return (readingOrder(lines), nil)
}

// A JSON string literal, for the line written when JSONSerialization cannot write a result.
func jsonString(_ s: String) -> String {
    var out = "\""
    for u in s.unicodeScalars {
        switch u {
        case "\"": out += "\\\""
        case "\\": out += "\\\\"
        case "\n": out += "\\n"
        case _ where u.value < 0x20: out += String(format: "\\u%04x", u.value)
        default: out.unicodeScalars.append(u)
        }
    }
    return out + "\""
}

for path in CommandLine.arguments.dropFirst() {
    let (lines, error) = recognize(path)
    var row: [String: Any] = ["file": path, "lines": lines.map { $0.json }]
    if let error = error { row["error"] = error }
    // checked first: JSONSerialization raises (it does not throw) on what JSON cannot hold, and every image must still
    // get its line, naming it, so ocr.py says which frame failed
    let data = JSONSerialization.isValidJSONObject(row) ? try? JSONSerialization.data(withJSONObject: row, options: [.sortedKeys]) : nil
    print(data.map { String(decoding: $0, as: UTF8.self) }
          ?? "{\"error\":\"the result could not be written\",\"file\":\(jsonString(path)),\"lines\":[]}")
}
