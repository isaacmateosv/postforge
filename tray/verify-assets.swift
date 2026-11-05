// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later
// See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
// Verify the actual release artwork, rather than only checking that files exist.
import AppKit

func require(_ condition: Bool, _ message: String) {
    if !condition { FileHandle.standardError.write(Data("Artifact check failed: \(message)\n".utf8)); exit(1) }
}
let arguments = CommandLine.arguments
require(arguments.count == 3, "expected app PNG and menu bar PNG")
func bitmap(_ path: String) -> NSBitmapImageRep {
    guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)), let image = NSBitmapImageRep(data: data) else {
        FileHandle.standardError.write(Data("Cannot load \(path)\n".utf8)); exit(1)
    }
    return image
}
let app = bitmap(arguments[1])
require(app.pixelsWide == 512 && app.pixelsHigh == 512, "app icon must be 512×512")
var blue = 0, gold = 0, transparent = 0
for y in 0..<app.pixelsHigh {
    for x in 0..<app.pixelsWide {
        guard let color = app.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB) else { continue }
        if color.alphaComponent < 0.01 { transparent += 1 }
        if color.alphaComponent > 0.95 && color.blueComponent > 0.7 && color.greenComponent > 0.3 && color.redComponent < 0.3 { blue += 1 }
        if color.alphaComponent > 0.95 && color.redComponent > 0.85 && color.greenComponent > 0.55 && color.blueComponent < 0.65 { gold += 1 }
    }
}
require(blue > 1000 && gold > 10, "colorful foreground lost its blue plane or gold accent")
require(transparent > 10000, "app icon lost transparent corners")
let tray = bitmap(arguments[2])
require(tray.pixelsHigh == 54 && tray.pixelsWide <= 54, "menu bar glyph size")
var ink = 0
for y in 0..<tray.pixelsHigh {
    for x in 0..<tray.pixelsWide {
        guard let color = tray.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB), color.alphaComponent > 0.05 else { continue }
        require(abs(color.redComponent - color.greenComponent) < 0.01 && abs(color.greenComponent - color.blueComponent) < 0.01, "menu bar icon must remain monochrome")
        ink += 1
    }
}
require(ink > 200, "menu bar glyph is empty")
print("PASS: colorful app foreground, transparent corners, monochrome 54px menu bar glyph")
