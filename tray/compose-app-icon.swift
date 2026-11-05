// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later
// See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
// Draws the PostForge app icon: the colorful foreground on a blue macOS-style squircle.
//   compose-app-icon glyph.svg out.png pixels
import AppKit

let args = CommandLine.arguments
guard args.count == 4, let pixels = Int(args[3]), pixels > 0,
      let glyph = NSImage(contentsOf: URL(fileURLWithPath: args[1])) else {
    FileHandle.standardError.write(Data("usage: compose-app-icon glyph.svg out.png pixels\n".utf8))
    exit(2)
}
guard let rep = NSBitmapImageRep(
    bitmapDataPlanes: nil, pixelsWide: pixels, pixelsHigh: pixels, bitsPerSample: 8, samplesPerPixel: 4,
    hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0) else { exit(3) }

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
let canvas = CGFloat(pixels)
NSColor.clear.set()
NSRect(x: 0, y: 0, width: canvas, height: canvas).fill(using: .copy)

// Apple's icon grid: the body fills 80% of the canvas, the rest is room for the shadow.
let body = NSRect(x: canvas * 0.1, y: canvas * 0.1, width: canvas * 0.8, height: canvas * 0.8)
let shape = NSBezierPath(roundedRect: body, xRadius: body.width * 0.225, yRadius: body.width * 0.225)

NSGraphicsContext.saveGraphicsState()
let shadow = NSShadow()
shadow.shadowColor = NSColor(calibratedWhite: 0, alpha: 0.35)
shadow.shadowBlurRadius = canvas * 0.02
shadow.shadowOffset = NSSize(width: 0, height: -canvas * 0.01)
shadow.set()
NSColor(calibratedRed: 0.10, green: 0.17, blue: 0.30, alpha: 1).setFill()
shape.fill()
NSGraphicsContext.restoreGraphicsState()

NSGradient(
    starting: NSColor(calibratedRed: 0.17, green: 0.29, blue: 0.50, alpha: 1),
    ending: NSColor(calibratedRed: 0.07, green: 0.12, blue: 0.23, alpha: 1))?
    .draw(in: shape, angle: -90)

// The supplied 1254px foreground is already centered. Fit its square canvas inside
// the tile so the calendar/plane remain legible without clipping the orbital accents.
let side = body.width * 0.96
let glyphRect = NSRect(x: body.midX - side / 2, y: body.midY - side / 2,
                       width: side, height: side)
glyph.draw(in: glyphRect, from: .zero, operation: .sourceOver, fraction: 1)
NSGraphicsContext.restoreGraphicsState()

guard let png = rep.representation(using: .png, properties: [:]) else { exit(4) }
try png.write(to: URL(fileURLWithPath: args[2]))
