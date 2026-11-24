// Sets the desktop picture on every connected display (fill screen).
// Usage: setwallpaper /path/to/image.png
import AppKit

guard CommandLine.arguments.count == 2 else {
    FileHandle.standardError.write("usage: setwallpaper <image>\n".data(using: .utf8)!)
    exit(2)
}
let url = URL(fileURLWithPath: CommandLine.arguments[1])
let options: [NSWorkspace.DesktopImageOptionKey: Any] = [
    .imageScaling: NSImageScaling.scaleProportionallyUpOrDown.rawValue,
    .allowClipping: true,
]
var failed = false
for screen in NSScreen.screens {
    do {
        try NSWorkspace.shared.setDesktopImageURL(url, for: screen, options: options)
    } catch {
        FileHandle.standardError.write("failed on \(screen.localizedName): \(error)\n".data(using: .utf8)!)
        failed = true
    }
}
exit(failed ? 1 : 0)
