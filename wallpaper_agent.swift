// Resident wallpaper agent (LaunchAgent, KeepAlive).
//
// macOS only lets an app set the picture of the Space that is currently visible on each display, so
// the renderer alone leaves every other Space on an old frame. This agent:
//   • on a Space switch or display change  → puts the current frame on whatever is now visible
//   • on wake / screen wake / unlock / clock change → re-renders if the frame is stale, else re-applies
//
// It never renders itself; it kickstarts the render LaunchAgent (local.dynamic-wallpaper).
// Debug: `kill -USR1 <pid>` simulates a wake, `kill -USR2 <pid>` simulates a Space switch.
//
// Usage: wallpaper-agent [runtime dir]   (default ~/Library/Application Support/DynamicWallpaper)
import AppKit
import Foundation

let fm = FileManager.default
let dir = CommandLine.arguments.count > 1
    ? URL(fileURLWithPath: CommandLine.arguments[1])
    : fm.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/DynamicWallpaper")
let stateURL = dir.appendingPathComponent("state.json")
let framesDir = dir.appendingPathComponent("frames")
let renderJob = "gui/\(getuid())/local.dynamic-wallpaper"
let staleAfter: TimeInterval = 10 * 60   // re-render on wake if the frame is older than this
let options: [NSWorkspace.DesktopImageOptionKey: Any] = [
    .imageScaling: NSImageScaling.scaleProportionallyUpOrDown.rawValue,
    .allowClipping: true,
]

let stamp: DateFormatter = {
    let f = DateFormatter()
    f.dateFormat = "yyyy-MM-dd HH:mm:ss"
    return f
}()

func log(_ msg: String) {
    print("\(stamp.string(from: Date()))  \(msg)")
    fflush(stdout)
}

/// The frame the renderer last produced: state.json's "current", else the newest frame on disk
/// (state.json may be mid-replace, or the frame may already be cleaned up).
func currentFrame() -> URL? {
    if let data = try? Data(contentsOf: stateURL),
       let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
       let path = obj["current"] as? String, fm.fileExists(atPath: path) {
        return URL(fileURLWithPath: path)
    }
    let files = (try? fm.contentsOfDirectory(at: framesDir, includingPropertiesForKeys: nil)) ?? []
    return files
        .filter { $0.lastPathComponent.hasPrefix("wallpaper-") && $0.pathExtension == "png" }
        .max { $0.lastPathComponent < $1.lastPathComponent }
}

func age(of url: URL) -> TimeInterval {
    let mtime = (try? fm.attributesOfItem(atPath: url.path)[.modificationDate]) as? Date
    return mtime.map { Date().timeIntervalSince($0) } ?? .infinity
}

/// Put the current frame on the visible Space of every display, skipping displays already showing it.
func apply(_ reason: String) {
    guard let frame = currentFrame() else {
        log("\(reason): no frame rendered yet")
        return
    }
    var set: [String] = [], failed: [String] = []
    for screen in NSScreen.screens {
        if NSWorkspace.shared.desktopImageURL(for: screen)?.standardizedFileURL == frame.standardizedFileURL {
            continue
        }
        do {
            try NSWorkspace.shared.setDesktopImageURL(frame, for: screen, options: options)
            set.append(screen.localizedName)
        } catch {
            failed.append("\(screen.localizedName) (\(error.localizedDescription))")
        }
    }
    var line = "\(reason): "
    line += set.isEmpty ? "already current (\(frame.lastPathComponent))"
                        : "set \(frame.lastPathComponent) on \(set.joined(separator: ", "))"
    if !failed.isEmpty { line += "  FAILED on \(failed.joined(separator: ", "))" }
    log(line)
}

func kickstartRender() {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/bin/launchctl")
    p.arguments = ["kickstart", renderJob]   // no -k: if a render is already running, leave it alone
    do { try p.run() } catch { log("kickstart failed: \(error)") }
}

/// Wake-type events arrive in bursts (wake, screens wake, unlock…); act once, 3 s after the last one.
var pendingWake: DispatchWorkItem?
func onWake(_ reason: String) {
    pendingWake?.cancel()
    let work = DispatchWorkItem {
        guard let frame = currentFrame() else { log("\(reason): no frame yet -> rendering"); kickstartRender(); return }
        let minutes = Int(age(of: frame) / 60)
        if age(of: frame) > staleAfter {
            log("\(reason): frame is \(minutes) min old -> rendering")
            kickstartRender()
        } else {
            apply("\(reason) (frame \(minutes) min old)")
        }
    }
    pendingWake = work
    DispatchQueue.main.asyncAfter(deadline: .now() + 3, execute: work)
}

let ws = NSWorkspace.shared.notificationCenter
ws.addObserver(forName: NSWorkspace.activeSpaceDidChangeNotification, object: nil, queue: .main) { _ in
    apply("space switch")
}
for (name, label) in [(NSWorkspace.didWakeNotification, "wake"),
                      (NSWorkspace.screensDidWakeNotification, "screens wake"),
                      (NSWorkspace.sessionDidBecomeActiveNotification, "session active")] {
    ws.addObserver(forName: name, object: nil, queue: .main) { _ in onWake(label) }
}
DistributedNotificationCenter.default().addObserver(
    forName: Notification.Name("com.apple.screenIsUnlocked"), object: nil, queue: .main) { _ in onWake("unlock") }
NotificationCenter.default.addObserver(forName: .NSSystemClockDidChange, object: nil, queue: .main) { _ in
    onWake("clock changed")
}
NotificationCenter.default.addObserver(forName: NSApplication.didChangeScreenParametersNotification,
                                       object: nil, queue: .main) { _ in
    DispatchQueue.main.asyncAfter(deadline: .now() + 1) { apply("displays changed") }
}

// Debug hooks so the handlers can be exercised without sleeping the Mac.
signal(SIGUSR1, SIG_IGN)
signal(SIGUSR2, SIG_IGN)
let usr1 = DispatchSource.makeSignalSource(signal: SIGUSR1, queue: .main)
usr1.setEventHandler { onWake("test wake (SIGUSR1)") }
usr1.resume()
let usr2 = DispatchSource.makeSignalSource(signal: SIGUSR2, queue: .main)
usr2.setEventHandler { apply("test apply (SIGUSR2)") }
usr2.resume()

let app = NSApplication.shared
app.setActivationPolicy(.prohibited)
DispatchQueue.main.async { log("agent started (pid \(getpid()), runtime \(dir.path))"); apply("startup") }
app.run()
