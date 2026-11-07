// Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
// SPDX-License-Identifier: GPL-3.0-or-later
// See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
// PostForge menu bar app: turn the stack on and off, see what is waiting to be sent, and
// get warned before anything turns it off with work pending.
//
// It holds no state of its own: it polls `scripts/lib/machine_state.py --json` and runs
// `postforge.sh start` / `stop --force` (after its own warning). Build with tray/build.sh.
// It also hosts the New Post window (a regular Dock app, so the window is reachable without the menu).
import AppKit
import IOKit.pwr_mgt
import UniformTypeIdentifiers
import ServiceManagement
import UserNotifications

// MARK: - What machine_state.py reports

struct ScheduledPost: Decodable {
    let id: String
    let at: String
    let provider: String
    let channel: String
    let text: String
}

struct WorkJob: Decodable {
    let kind: String
    let label: String
    let since: Int
}

struct Pending: Decodable {
    let total: Int
    let scheduled: Int
    let overdue: Int
    let jobs: [WorkJob]
    let next: ScheduledPost?
    let fromCache: Bool
    let cachedAt: String?
    let whatsapp: WhatsAppPending?
}

struct WhatsAppPending: Decodable {
    let pending: Int
    let awaitingApproval: Int
    let approved: Int
    let needsReview: Int?
    let confirmations: Int
    let next: String?
}

struct Services: Decodable {
    let postiz: Bool
    let evolution: Bool
    let whatsapp: String?
    let scheduler: Bool  // a Postiz worker polls Temporal; without it scheduled posts never go out
    let tunnel: Bool
}

struct LastStatus: Decodable {
    let id: String
    let ts: Int
    let received: Int
    let viewed: Int
    let text: String
    let viewerNames: [String]?  // up to 15, the primary phone left out
}

/// A channel that needs reconnecting, or will soon (Facebook and Instagram can't renew themselves).
struct ChannelAlert: Decodable {
    let provider: String
    let network: String  // "Instagram", "Facebook Page", …
    let channel: String
    let reason: String  // expires soon | expired | disconnected | setup not finished
    let urgent: Bool
    let expires: String?
    let daysLeft: Int?
    let guide: String  // docs/reconnect/…, relative to the project
    let steps: [String]

    var key: String { provider + "|" + channel }

    var headline: String {
        let network = uiNetwork(self.network)
        switch reason {
        case "expires soon": return ui("Reconnect \(network) by \(expires.map { shortDay(iso: $0) } ?? "soon")", "Vuelve a conectar \(network) antes del \(expires.map { shortDay(iso: $0) } ?? "pronto")")
        case "expired": return ui("\(network) stopped working", "\(network) dejó de funcionar")
        case "disconnected": return ui("\(network) is disconnected", "\(network) está desconectado")
        default: return ui("\(network) setup isn't finished", "La configuración de \(network) está incompleta")
        }
    }
}

struct ChannelInfo: Decodable {
    let provider: String
    let network: String
    let channel: String
    let renews: Bool
    let expires: String?

    var key: String { provider + "|" + channel }
}

struct MaintenanceComponent: Decodable {
    let name: String
    let kind: String
}

struct EvolutionUpdateStatus: Decodable {
    let installed: String
    let latest: String
    let updateAvailable: Bool
}

struct MaintenanceStatus: Decodable {
    let updatesAvailable: Bool
    let components: [MaintenanceComponent]
    let dockerStack: String
    let checkComplete: Bool?
    var evolution: EvolutionUpdateStatus? = nil
}

struct PackageAsset: Decodable {
    let name: String
    let browserDownloadUrl: String?

    enum CodingKeys: String, CodingKey {
        case name
        case browserDownloadUrl = "browser_download_url"
    }
}

struct PackageRelease: Decodable {
    let tagName: String
    let htmlUrl: String?
    let draft: Bool
    let prerelease: Bool
    let assets: [PackageAsset]

    enum CodingKeys: String, CodingKey {
        case tagName = "tag_name"
        case htmlUrl = "html_url"
        case draft
        case prerelease
        case assets
    }
}

struct PackageUpdateState {
    let installedVersion: String
    let latestVersion: String
    let releaseURL: URL
    let packageURL: URL
    let packageName: String
    let checksumURL: URL
}

struct MachineState: Decodable {
    let state: String  // off | starting | stopping | on | partial
    let activity: String?  // idle | active, only while on
    let idleStopped: Bool?
    let docker: Bool
    let services: Services
    let pending: Pending
    let scheduled: [ScheduledPost]
    let drafts: Int?
    let failedPosts: Int?  // failed in the last 24 h
    let lastStatus: LastStatus?
    let channels: [ChannelInfo]?
    let channelAlerts: [ChannelAlert]?
    let channelsFromCache: Bool?
    let postizUrl: String

    var isUp: Bool { state == "on" }
}

// MARK: - Helpers

let isoParser: ISO8601DateFormatter = {
    let f = ISO8601DateFormatter()
    f.formatOptions = [.withInternetDateTime]
    return f
}()

func shortDate(_ date: Date) -> String {
    let f = DateFormatter()
    f.locale = Locale(identifier: UserDefaults.standard.string(forKey: "uiLanguage") == "es" ? "es_EC" : "en_US")
    f.dateFormat = Calendar.current.isDateInToday(date) ? (UserDefaults.standard.string(forKey: "uiLanguage") == "es" ? "'hoy' HH:mm" : "'today' HH:mm") : "EEE d MMM HH:mm"
    return f.string(from: date)
}

func shortDate(iso: String) -> String {
    guard let date = isoParser.date(from: iso) else { return iso }
    return shortDate(date)
}

func shortDay(iso: String) -> String {
    guard let date = isoParser.date(from: iso) else { return iso }
    let f = DateFormatter()
    f.locale = Locale(identifier: UserDefaults.standard.string(forKey: "uiLanguage") == "es" ? "es_EC" : "en_US")
    f.dateFormat = "EEE d MMM"
    return f.string(from: date)
}

func plural(_ n: Int, _ word: String) -> String { "\(n) \(word)\(n == 1 ? "" : "s")" }

func fourCC(_ s: String) -> UInt32 { s.utf8.reduce(0) { ($0 << 8) | UInt32($1) } }

func postForgeImage() -> NSImage {
    let size = 18.0
    if let path = Bundle.main.path(forResource: "PostForgeTray", ofType: "png"),
       let image = NSImage(contentsOfFile: path) {
        // Use the Retina mask at a fixed menu bar size.
        image.size = NSSize(width: size * image.size.width / image.size.height, height: size)
        image.isTemplate = true  // black template mask: macOS tints it for light and dark menu bars
        return image
    }

    let image = NSImage(size: NSSize(width: 24, height: 24))
    image.lockFocus()
    let plane = NSBezierPath()
    plane.move(to: NSPoint(x: 3, y: 12))
    plane.line(to: NSPoint(x: 21, y: 21))
    plane.line(to: NSPoint(x: 15, y: 5))
    plane.line(to: NSPoint(x: 11, y: 11))
    plane.close()
    NSColor.black.setFill()
    plane.fill()
    let spark = NSBezierPath()
    spark.move(to: NSPoint(x: 19, y: 22))
    spark.line(to: NSPoint(x: 21, y: 20))
    spark.line(to: NSPoint(x: 23, y: 18))
    spark.line(to: NSPoint(x: 20, y: 17))
    spark.line(to: NSPoint(x: 19, y: 14))
    spark.line(to: NSPoint(x: 18, y: 17))
    spark.line(to: NSPoint(x: 15, y: 18))
    spark.line(to: NSPoint(x: 18, y: 19))
    spark.close()
    spark.fill()
    image.unlockFocus()
    image.size = NSSize(width: size, height: size)
    image.isTemplate = true
    return image
}

/// Runs a command with a PATH that finds docker, ollama and ffmpeg (apps launched from Finder get
/// only /usr/bin:/bin). Returns the exit code and combined output (stdout only with `quietErrors`,
/// for commands that print JSON there and progress on stderr). Call off the main thread.
func runCommand(_ args: [String], in dir: String, timeout: TimeInterval, quietErrors: Bool = false) -> (Int32, String) {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: args[0])
    process.arguments = Array(args.dropFirst())
    process.currentDirectoryURL = URL(fileURLWithPath: dir)
    var env = ProcessInfo.processInfo.environment
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    env["LANG"] = env["LANG"] ?? "en_US.UTF-8"
    env["PYTHONIOENCODING"] = "utf-8"
    process.environment = env
    let pipe = Pipe()
    process.standardOutput = pipe
    process.standardError = quietErrors ? FileHandle.nullDevice : pipe
    do {
        try process.run()
    } catch {
        return (-1, "Could not run \(args[0]): \(error.localizedDescription)")
    }
    let killer = DispatchWorkItem { if process.isRunning { process.terminate() } }
    DispatchQueue.global().asyncAfter(deadline: .now() + timeout, execute: killer)
    let data = pipe.fileHandleForReading.readDataToEndOfFile()
    process.waitUntilExit()
    killer.cancel()
    return (process.terminationStatus, String(decoding: data, as: UTF8.self))
}

// MARK: - App

final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate, UNUserNotificationCenterDelegate {
    let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    let defaults = UserDefaults.standard
    let project: String

    var state: MachineState?
    var stateError: String?
    var busy: String? { didSet { idleSince = nil; updateButton() } }
    var windowWork = 0 { didSet { idleSince = nil; updateButton() } }
    var planningWork = 0 { didSet { idleSince = nil; updateButton() } }
    var activeProcessCount: Int {
        (busy != nil || state?.state == "starting" || state?.state == "stopping" ? 1 : 0)
            + windowWork + max(planningWork, state?.pending.jobs.count ?? 0)
            + (operationIsUpdateCheck && (packageCheckInFlight || maintenanceCheckInFlight) ? 1 : 0)
    }
    var updatesAvailable: Bool {
        latestPackageUpdate != nil || maintenance?.updatesAvailable == true || maintenance?.evolution?.updateAvailable == true
    }
    var pollTimer: Timer?
    var polling = false
    var menuOpen = false
    var newPost: NewPostWindow?
    var backupWindow: BackupWindow?
    var whatsappWindow: WhatsAppWindow?
    var uninstalling = false
    var notifications: UNAuthorizationStatus?  // nil until macOS answers
    var quittingFromMenu = false
    var sleepAssertion: IOPMAssertionID = 0
    var remindedPosts = Set<String>()
    var openPostizWhenUp = false  // "Turn On and Open Postiz" from a reconnect warning
    var maintenance: MaintenanceStatus?
    var maintenanceCheckInFlight = false
    var maintenanceTimer: Timer?
    var updateNoticeShown = false
    var notifiedPackageVersion: String?
    var notifiedEvolutionVersion: String?
    var latestPackageUpdate: PackageUpdateState?
    var packageCheckFailing = false
    var packageCheckInFlight = false
    var operationWindow: NSWindow?
    var operationLabel: NSTextField?
    var operationStage: String?
    var operationSpinner: NSProgressIndicator?
    var operationCloseButton: NSButton?
    var operationActionButton: NSButton?
    var operationIsUpdateCheck = false
    var aboutWindow: NSWindow?
    var flowWindow: NSWindow?
    var licenseWindow: NSWindow?
    var guideWindow: UserGuideWindow?
    var idleSince: Date?
    var wakeSchedule: (at: String, retryAfter: Date)?
    var wokeFromSleep = false

    var spanish: Bool {
        defaults.string(forKey: "uiLanguage") == "es"
    }

    func text(_ english: String, _ spanishText: String) -> String {
        spanish ? spanishText : english
    }

    override init() {
        let configured = Bundle.main.object(forInfoDictionaryKey: "PMProjectDir") as? String
        project = UserDefaults.standard.string(forKey: "projectDir") ?? configured
            ?? (NSHomeDirectory() + "/postforge")
        super.init()
    }

    /// The shipped Siri shortcuts open the composer through postforge://new-post.
    /// Keep accepting older user-created shortcuts that use publishmachine://.
    func application(_ application: NSApplication, open urls: [URL]) {
        let schemes: Set<String> = ["postforge", "publishmachine"]
        if urls.contains(where: { schemes.contains($0.scheme ?? "") && $0.host == "new-post" }) { openNewPost() }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { openNewPost() }
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return false
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        if let path = Bundle.main.path(forResource: "PostForge", ofType: "icns"), let icon = NSImage(contentsOfFile: path) { NSApp.applicationIconImage = icon }
        NSApp.mainMenu = buildMainMenu()
        if CommandLine.arguments.contains("--check-updates-once") {
            showOperation(text("Checking PostForge and Docker components…", "Revisando PostForge y los componentes de Docker…"), updateCheck: true)
            checkForUpdates()
            return
        }
        if let index = CommandLine.arguments.firstIndex(of: "--snapshot-new-post"), index + 1 < CommandLine.arguments.count {
            snapshotNewPost(to: CommandLine.arguments[index + 1])  // debugging: renders the window to a PNG, then quits
        }
        if let index = CommandLine.arguments.firstIndex(of: "--snapshot-updates"), index + 1 < CommandLine.arguments.count {
            showOperation(text("2/5 · Downloading components…", "2/5 · Descargando componentes…")); snapshot(operationWindow!, to: CommandLine.arguments[index + 1])
        }
        if let index = CommandLine.arguments.firstIndex(of: "--snapshot-flow"), index + 1 < CommandLine.arguments.count {
            showPublishingFlow(); snapshot(flowWindow!, to: CommandLine.arguments[index + 1])
        }
        if let index = CommandLine.arguments.firstIndex(of: "--snapshot-license"), index + 1 < CommandLine.arguments.count {
            showLicense(); snapshot(licenseWindow!, to: CommandLine.arguments[index + 1])
        }
        if let index = CommandLine.arguments.firstIndex(of: "--snapshot-about"), index + 1 < CommandLine.arguments.count {
            showAbout(); snapshot(aboutWindow!, to: CommandLine.arguments[index + 1])
        }
        for (flag, make) in [("--snapshot-backup", { (d: AppDelegate) in BackupWindow(delegate: d).window }),
                             ("--snapshot-whatsapp", { (d: AppDelegate) in WhatsAppWindow(delegate: d).window })] {
            if let index = CommandLine.arguments.firstIndex(of: flag), index + 1 < CommandLine.arguments.count {
                snapshot(make(self), to: CommandLine.arguments[index + 1])
            }
        }
        let dumping = CommandLine.arguments.contains("--dump-menu")
        if !dumping && NSRunningApplication.runningApplications(withBundleIdentifier: Bundle.main.bundleIdentifier ?? "").count > 1 {
            NSApp.terminate(nil)  // already running
            return
        }
        defaults.register(defaults: ["keepAwake": true, "remindWhenOff": true, "remindMinutes": 30,
                                     "uiLanguage": "en", "autoStopWhenIdle": true, "idleStopMinutes": 60])

        DispatchQueue.main.async {
            self.openNewPost()
        }

        let menu = NSMenu()
        menu.autoenablesItems = false
        menu.delegate = self
        statusItem.button?.title = ""
        statusItem.button?.imagePosition = .imageOnly
        statusItem.button?.imageScaling = .scaleNone
        statusItem.button?.target = self
        statusItem.button?.action = #selector(showStatusMenu)
        statusItem.menu = menu
        menuNeedsUpdate(menu)
        updateButton()
        openNewPost()

        let center = UNUserNotificationCenter.current()
        center.delegate = self
        configureNotificationActions()
        center.requestAuthorization(options: [.alert, .sound]) { _, _ in self.refreshNotificationStatus() }

        NSWorkspace.shared.notificationCenter.addObserver(
            self, selector: #selector(didWake), name: NSWorkspace.didWakeNotification, object: nil)
        _ = NSEvent.addLocalMonitorForEvents(matching: [.keyDown, .leftMouseDown, .rightMouseDown, .scrollWheel]) { [weak self] event in
            self?.idleSince = nil
            return event
        }
        poll()
        scheduleMaintenanceCheck()
        checkForUpdates(notifyIfAvailable: true)
    }

    /// The menu bar at the top of the screen while PostForge is frontmost.
    func buildMainMenu() -> NSMenu {
        let main = NSMenu()
        func submenu(_ title: String, _ items: [NSMenuItem]) {
            let holder = NSMenuItem(title: title, action: nil, keyEquivalent: "")
            let menu = NSMenu(title: title)
            items.forEach(menu.addItem)
            holder.submenu = menu
            main.addItem(holder)
        }
        func item(_ title: String, _ selector: Selector?, _ key: String = "", target: AnyObject? = nil,
                  modifiers: NSEvent.ModifierFlags = [.command]) -> NSMenuItem {
            let i = NSMenuItem(title: title, action: selector, keyEquivalent: key)
            i.keyEquivalentModifierMask = modifiers
            i.target = target
            return i
        }
        let hide = item(text("Hide PostForge", "Ocultar PostForge"), #selector(NSApplication.hide(_:)), "h")
        let hideOthers = item(text("Hide Others", "Ocultar otros"), #selector(NSApplication.hideOtherApplications(_:)), "h",
                              modifiers: [.command, .option])
        submenu("PostForge", [
            item(text("About PostForge", "Acerca de PostForge"), #selector(showAbout), target: self),
            .separator(),
            item(text("Open Log", "Abrir registro"), #selector(openLog), target: self),
            item(text("Check for Updates…", "Buscar actualizaciones…"), #selector(checkUpdatesFromMenu), target: self),
            item(text("Backup & Move…", "Respaldo y traslado…"), #selector(openBackupWindow), target: self),
            item(text("Uninstall PostForge…", "Desinstalar PostForge…"), #selector(uninstallPostForge), target: self),
            .separator(),
            hide, hideOthers,
            .separator(),
            item(text("Quit PostForge", "Salir de PostForge"), #selector(quitApp), "q", target: self),
        ])
        submenu(text("Post", "Publicación"), [
            item(text("New Post…", "Nueva publicación…"), #selector(openNewPost), "n", target: self),
            item(text("Open Postiz Calendar", "Abrir calendario de Postiz"), #selector(openPostiz), "o", target: self),
            .separator(),
            item(text("Turn On", "Encender"), #selector(turnOn), target: self),
            item(text("Turn Off…", "Apagar…"), #selector(turnOff), target: self),
        ])
        submenu(text("Edit", "Edición"), [
            item(text("Undo", "Deshacer"), Selector(("undo:")), "z"),
            item(text("Redo", "Rehacer"), Selector(("redo:")), "z", modifiers: [.command, .shift]),
            .separator(),
            item(text("Cut", "Cortar"), #selector(NSText.cut(_:)), "x"),
            item(text("Copy", "Copiar"), #selector(NSText.copy(_:)), "c"),
            item(text("Paste", "Pegar"), #selector(NSText.paste(_:)), "v"),
            item(text("Select All", "Seleccionar todo"), #selector(NSText.selectAll(_:)), "a"),
        ])
        submenu(text("Window", "Ventana"), [
            item(text("Minimize", "Minimizar"), #selector(NSWindow.performMiniaturize(_:)), "m"),
            item(text("Close", "Cerrar"), #selector(NSWindow.performClose(_:)), "w"),
        ])
        submenu(text("Help", "Ayuda"), [
            item(text("PostForge Help", "Ayuda de PostForge"), #selector(showUserGuide), target: self),
        ])
        return main
    }

    // MARK: Polling

    @objc func didWake() {
        idleSince = nil
        wokeFromSleep = true
        poll()
    }

    func poll() {
        if polling || uninstalling { return }
        polling = true
        let dir = project
        DispatchQueue.global(qos: .utility).async {
            let (code, output) = runCommand(["/usr/bin/python3", dir + "/scripts/lib/machine_state.py", "--json"],
                                            in: dir, timeout: 45)
            DispatchQueue.main.async { self.finishPoll(code: code, output: output) }
        }
    }

    func finishPoll(code: Int32, output: String) {
        polling = false
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        if code == 0, let line = output.split(separator: "\n").last,
           let new = try? decoder.decode(MachineState.self, from: Data(line.utf8)) {
            let old = state
            state = new
            newPost?.refreshState(new)
            whatsappWindow?.refresh(new)
            if stateError != nil { log("State check works again.") }
            stateError = nil
            if let old = old { announceChanges(from: old, to: new) }
            remindIfOff(new)
            scheduleWake(for: new.pending.next)
            if wokeFromSleep {
                wokeFromSleep = false
                if new.state == "off", new.pending.next != nil {
                    turnOn()
                }
            }
            if !CommandLine.arguments.contains("--dump-menu") { warnAboutChannels(new) }  // a dump mustn't use up warnings
        } else {
            if stateError == nil { log("State check failed (exit \(code)):\n\(output)") }
            stateError = output.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: "\n").last.map(String.init)
                ?? "machine_state.py exited \(code)"
        }
        updateButton()
        updateSleepAssertion()
        if menuOpen, let menu = statusItem.menu { menuNeedsUpdate(menu) }  // fresh numbers while it's open
        if CommandLine.arguments.contains("--dump-menu") { dumpMenu() }
        stopWhenIdleIfNeeded()
        scheduleNextPoll()
    }

    /// `PostForgeTray --snapshot-new-post | --snapshot-backup | --snapshot-whatsapp out.png`: a window as an
    /// image (no screen capture).
    func snapshotNewPost(to path: String) {
        let post = NewPostWindow(project: project)
        let status = runCommand(["/usr/bin/python3", project + "/scripts/lib/machine_state.py", "--json"], in: project, timeout: 20, quietErrors: true)
        let decoder = JSONDecoder(); decoder.keyDecodingStrategy = .convertFromSnakeCase
        if status.0 == 0, let data = status.1.data(using: .utf8), let state = try? decoder.decode(MachineState.self, from: data) { post.refreshState(state) }
        snapshot(post.window, to: path)
    }

    func snapshot(_ window: NSWindow, to path: String) {
        let view = window.contentView!
        view.layoutSubtreeIfNeeded()
        if CommandLine.arguments.contains("--dump-snapshot-text") {
            func dump(_ view: NSView) {
                if let label = view as? NSTextField { print(label.stringValue, "frame:", label.frame) }
                view.subviews.forEach(dump)
            }
            dump(view)
        }
        window.displayIfNeeded()
        view.displayIfNeeded()
        if let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) {
            view.cacheDisplay(in: view.bounds, to: rep)
            try? rep.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: path))
        }
        exit(0)
    }

    /// `PostForgeTray --dump-menu`: print the button and menu after one poll, then quit.
    func dumpMenu() {
        let answered = DispatchSemaphore(value: 0)
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            self.notifications = settings.authorizationStatus  // main is blocked on the semaphore meanwhile
            answered.signal()
        }
        _ = answered.wait(timeout: .now() + 3)
        let menu = NSMenu()
        menuNeedsUpdate(menu)
        print("[button] \(statusItem.button?.title ?? "") · \(statusItem.button?.toolTip ?? "")")
        let allowed = notifications == .authorized || notifications == .provisional
        print("[notifications] " + (notifications == nil ? "unknown" : allowed ? "allowed"
            : notifications == .notDetermined ? "not asked yet" : "off in System Settings"))
        func show(_ menu: NSMenu, _ indent: String) {
            for item in menu.items {
                if item.isSeparatorItem { print(indent + "────"); continue }
                let mark = item.state == .on ? "✓ " : ""
                let dim = item.action != nil && !item.isEnabled ? "  (disabled)" : ""
                print(indent + mark + (item.title.isEmpty ? item.attributedTitle?.string ?? "" : item.title) + dim)
                if let sub = item.submenu { show(sub, indent + "    ") }
            }
        }
        show(menu, "")
        exit(0)
    }

    func scheduleNextPoll() {
        pollTimer?.invalidate()
        var seconds: TimeInterval = 60
        if busy != nil || state?.state == "starting" || state?.state == "stopping" {
            seconds = 5
        } else if state?.state == "off" {
            let soon = (state?.pending.next).flatMap { isoParser.date(from: $0.at) }.map { $0.timeIntervalSinceNow < 3600 } ?? false
            seconds = soon ? 30 : (state?.pending.total == 0 ? 300 : 120)
        }

        pollTimer = Timer.scheduledTimer(withTimeInterval: seconds, repeats: false) { [weak self] _ in self?.poll() }
    }

    func scheduleMaintenanceCheck() {
        maintenanceTimer?.invalidate()
        maintenanceTimer = Timer.scheduledTimer(withTimeInterval: 3600, repeats: false) { [weak self] _ in
            self?.checkForUpdates(notifyIfAvailable: true)
        }
    }

    func checkForUpdates(notifyIfAvailable: Bool = false) {
        if maintenanceCheckInFlight || packageCheckInFlight { return }
        maintenanceCheckInFlight = true
        maintenance = nil
        packageCheckFailing = false
        refreshPackageUpdateStatus(notifyIfAvailable: notifyIfAvailable)
        updateButton()
        let dir = project
        DispatchQueue.global(qos: .utility).async {
            let result = runCommand(["/bin/bash", dir + "/scripts/maintenance.sh", "check", "--json"],
                                    in: dir, timeout: 60, quietErrors: true)
            DispatchQueue.main.async {
                self.maintenanceCheckInFlight = false

                let decoder = JSONDecoder()
                decoder.keyDecodingStrategy = .convertFromSnakeCase
                if result.0 == 0, let data = result.1.data(using: .utf8),
                   let status = try? decoder.decode(MaintenanceStatus.self, from: data) {
                    self.maintenance = status
                    if notifyIfAvailable && status.updatesAvailable && !self.updateNoticeShown {
                        self.updateNoticeShown = true
                        self.notify("Stable updates are available",
                                    "Open the tray menu to review them. Host tools remain manual; the approved action updates the Docker stack.")
                    }
                    if !status.updatesAvailable { self.updateNoticeShown = false }
                    if notifyIfAvailable, let evolution = status.evolution, evolution.updateAvailable,
                       self.notifiedEvolutionVersion != evolution.latest {
                        self.notifiedEvolutionVersion = evolution.latest
                        self.notify(self.text("Evolution update available", "Actualización de Evolution disponible"),
                                    self.text("A newer upstream release is available for review.", "Hay una versión nueva del proveedor para revisar."))
                    }
                    if let menu = self.statusItem.menu { self.menuNeedsUpdate(menu) }
                } else {
                    self.log("maintenance check failed (exit \(result.0))\n\(result.1)")
                }
                self.updateButton()
                self.finishUpdateCheckIfReady()
                self.scheduleMaintenanceCheck()
            }
        }
    }

    func currentPostForgeVersion() -> String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0.1"
    }

    func versionIsNewer(_ candidate: String, than current: String) -> Bool {
        func parse(_ value: String) -> ([Int], [String]?)? {
            var version = value.trimmingCharacters(in: .whitespacesAndNewlines)
            if version.hasPrefix("v") { version.removeFirst() }
            guard !version.isEmpty else { return nil }
            version = String(version.split(separator: "+", maxSplits: 1, omittingEmptySubsequences: false)[0])
            let parts = version.split(separator: "-", maxSplits: 1, omittingEmptySubsequences: false)
            let core = parts[0].split(separator: ".", omittingEmptySubsequences: false)
            guard core.count == 3, core.allSatisfy({ !$0.isEmpty && $0.allSatisfy({ $0.isNumber }) }),
                  core.compactMap({ Int($0) }).count == 3 else { return nil }
            let prerelease = parts.count == 2 ? parts[1].split(separator: ".", omittingEmptySubsequences: false).map(String.init) : nil
            if let prerelease, prerelease.contains(where: { $0.isEmpty }) { return nil }
            return (core.compactMap { Int($0) }, prerelease)
        }
        guard let (a, preA) = parse(candidate), let (b, preB) = parse(current) else { return false }
        for index in 0..<3 where a[index] != b[index] { return a[index] > b[index] }
        if preA == nil { return preB != nil }
        guard let preB, let preA else { return false }
        for index in 0..<min(preA.count, preB.count) where preA[index] != preB[index] {
            if let numberA = Int(preA[index]), let numberB = Int(preB[index]) { return numberA > numberB }
            if Int(preA[index]) != nil { return false }
            if Int(preB[index]) != nil { return true }
            return preA[index] > preB[index]
        }
        return preA.count > preB.count
    }

    func refreshPackageUpdateStatus(notifyIfAvailable: Bool = false) {
        guard !packageCheckInFlight else { return }
        packageCheckInFlight = true
        let current = currentPostForgeVersion()
        let directory = project
        DispatchQueue.global(qos: .utility).async {
            let result = runCommand([
                "/usr/bin/curl",
                "-sSL",
                "--max-time", "20",
                "-w", "\n%{http_code}",
                "-H",
                "Accept: application/vnd.github+json",
                "https://api.github.com/repos/isaacmateosv/postforge/releases/latest"
            ], in: directory, timeout: 25, quietErrors: true)
            DispatchQueue.main.async {
                self.consumePackageRelease(result, current: current, notifyIfAvailable: notifyIfAvailable)
            }
        }
    }

    func consumePackageRelease(_ result: (Int32, String), current: String, notifyIfAvailable: Bool) {
        defer {
            packageCheckInFlight = false
            updateButton()
            finishUpdateCheckIfReady()
        }
        let body = result.1.split(separator: "\n", omittingEmptySubsequences: false).dropLast().joined(separator: "\n")
        let status = Int(result.1.split(separator: "\n").last ?? "") ?? 0
        if result.0 != 0 || status == 0 {
            if !packageCheckFailing { self.log("package update check failed (exit \(result.0)); will keep retrying quietly") }
            packageCheckFailing = true
            return
        }
        packageCheckFailing = false
        guard status == 200, let data = body.data(using: .utf8) else {
            packageCheckFailing = status != 404
            // 404 means no release has been published yet; that is not an error.
            self.latestPackageUpdate = nil
            if let menu = self.statusItem.menu { self.menuNeedsUpdate(menu) }
            return
        }
        do {
            let decoder = JSONDecoder()
            let release = try decoder.decode(PackageRelease.self, from: data)
            guard !release.draft, !release.prerelease else {
                self.latestPackageUpdate = nil
                if let menu = self.statusItem.menu { self.menuNeedsUpdate(menu) }
                return
            }
            let preferred = release.assets.first { $0.name.lowercased().hasSuffix(".pkg") }
            guard let preferred,
                  let checksumURL = release.assets.first(where: { $0.name == preferred.name + ".sha256" })?.browserDownloadUrl.flatMap(URL.init(string:)) else {
                self.packageCheckFailing = true
                self.latestPackageUpdate = nil
                if let menu = self.statusItem.menu { self.menuNeedsUpdate(menu) }
                return
            }
            let packageName = preferred.name
            let releaseURL = URL(string: release.htmlUrl ?? "https://github.com/isaacmateosv/postforge/releases/latest") ?? URL(string: "https://github.com/isaacmateosv/postforge/releases")!
            let packageURL = preferred.browserDownloadUrl.flatMap(URL.init(string:)) ?? releaseURL
            if self.versionIsNewer(release.tagName, than: current) {
                self.latestPackageUpdate = PackageUpdateState(installedVersion: current,
                                                            latestVersion: release.tagName,
                                                            releaseURL: releaseURL,
                                                            packageURL: packageURL,
                                                            packageName: packageName, checksumURL: checksumURL)
                if notifyIfAvailable && self.notifiedPackageVersion != release.tagName {
                    self.notifiedPackageVersion = release.tagName
                    self.notify("PostForge update is available",
                                text("Latest stable release: \(release.tagName). Install it from the tray menu.", "Versión estable disponible: \(release.tagName). Instálala desde el menú de la barra."))
                }
            } else {
                self.latestPackageUpdate = nil
            }
            if let menu = self.statusItem.menu { self.menuNeedsUpdate(menu) }
        } catch {
            self.packageCheckFailing = true
            self.log("Failed to decode latest GitHub release: \(error.localizedDescription)")
        }
    }

    @objc func downloadLatestPackage() {
        guard busy == nil, let update = latestPackageUpdate else { return }
        let confirmed = ask(
            text("Install PostForge \(update.latestVersion)?", "¿Instalar PostForge \(update.latestVersion)?"),
            text("Download and install the stable package. Running PostForge services and the tray app may restart briefly.",
                 "Descarga e instala el paquete estable. Los servicios activos de PostForge y la app pueden reiniciarse brevemente."),
            safe: text("Cancel", "Cancelar"),
            risky: text("Install Update", "Instalar actualización"))
        guard confirmed else { return }

        guard update.packageName == URL(fileURLWithPath: update.packageName).lastPathComponent,
              update.packageURL.scheme == "https", update.packageURL.host == "github.com",
              update.checksumURL.scheme == "https", update.checksumURL.host == "github.com" else { return }
        busy = text("Downloading update…", "Descargando actualización…")
        showOperation(busy!)
        updateButton()
        let destination = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".pkg")
        DispatchQueue.global(qos: .userInitiated).async {
            defer { try? FileManager.default.removeItem(at: destination) }
            let result = runCommand([
                "/usr/bin/curl",
                "-fL",
                "--max-time", "120",
                "--retry",
                "2",
                "-o",
                destination.path,
                update.packageURL.absoluteString
            ], in: self.project, timeout: 180, quietErrors: true)
            guard result.0 == 0 else {
                DispatchQueue.main.async {
                    self.busy = nil
                    self.finishOperation(false)
                    self.log("Package download failed (exit \(result.0))\n\(result.1)")
                    self.alert(self.text("Update download failed", "No se pudo descargar la actualización"),
                               self.text("Check your network connection or install manually from the release page.",
                                         "Revisa la conexión o instala manualmente desde la página de la versión."))
                    NSWorkspace.shared.open(update.releaseURL)
                }
                return
            }
            let checksumFile = destination.appendingPathExtension("sha256")
            defer { try? FileManager.default.removeItem(at: destination); try? FileManager.default.removeItem(at: checksumFile) }
            let checksumDownload = runCommand(["/usr/bin/curl", "-fLsS", "--max-time", "20", "-o", checksumFile.path, update.checksumURL.absoluteString], in: self.project, timeout: 25, quietErrors: true)
            let expected = (try? String(contentsOf: checksumFile, encoding: .utf8))?.split(whereSeparator: { $0.isWhitespace }).first.map(String.init) ?? ""
            let actual = runCommand(["/usr/bin/shasum", "-a", "256", destination.path], in: self.project, timeout: 30, quietErrors: true)
            guard checksumDownload.0 == 0, expected.count == 64, actual.0 == 0,
                  actual.1.split(separator: " ").first.map(String.init)?.lowercased() == expected.lowercased() else {
                DispatchQueue.main.async {
                    self.busy = nil; self.finishOperation(false)
                    self.alert(self.text("Update verification failed", "No se pudo verificar la actualización"), self.text("The package checksum did not match. Check the release and try again.", "La suma de verificación del paquete no coincide. Revisa la versión y vuelve a intentar."))
                }
                return
            }
            DispatchQueue.main.async { self.operationLabel?.stringValue = self.text("Installing… macOS may request your password.", "Instalando… macOS puede pedirte la contraseña.") }
            let quotedPath = destination.path.replacingOccurrences(of: "\\", with: "\\\\")
                .replacingOccurrences(of: "\"", with: "\\\"")
            let script = "do shell script \"installer -pkg \\\"\(quotedPath)\\\" -target /\" with administrator privileges"
            let install = runCommand(["/usr/bin/osascript", "-e", script], in: self.project, timeout: 900, quietErrors: true)
            DispatchQueue.main.async {
                try? FileManager.default.removeItem(at: destination)
                self.busy = nil
                self.finishOperation(install.0 == 0)
                if install.0 == 0 {
                    self.notify(self.text("PostForge updated", "PostForge actualizado"), self.text("Version \(update.latestVersion) installed.", "Se instaló la versión \(update.latestVersion)."))
                    self.latestPackageUpdate = nil
                    if let menu = self.statusItem.menu { self.menuNeedsUpdate(menu) }
                } else {
                    self.log("Package install failed (exit \(install.0))\n\(install.1)")
                    self.alert(self.text("Update install failed", "No se pudo instalar la actualización"),
                               self.text("Download the package from the GitHub release page and run it manually.",
                                         "Descarga el paquete desde la página de la versión en GitHub e instálalo manualmente."))
                    NSWorkspace.shared.open(update.releaseURL)
                }
            }
        }
    }

    // MARK: Notifications

    func notify(_ title: String, _ body: String, turnOnButton: Bool = false) {
        let content = UNMutableNotificationContent()
        content.title = localizedUI(title)
        content.body = localizedUI(body)
        content.sound = .default
        if turnOnButton { content.categoryIdentifier = "OFF_WITH_WORK" }
        UNUserNotificationCenter.current().add(
            UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil))
    }

    func configureNotificationActions() {
        let turnOn = UNNotificationAction(identifier: "TURN_ON", title: text("Turn On", "Encender"), options: [])
        UNUserNotificationCenter.current().setNotificationCategories([
            UNNotificationCategory(identifier: "OFF_WITH_WORK", actions: [turnOn], intentIdentifiers: [], options: [])
        ])
    }

    /// Whether macOS lets the app show its warnings; the menu offers "Allow Notifications…" when it doesn't.
    func refreshNotificationStatus() {
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            DispatchQueue.main.async { self.notifications = settings.authorizationStatus }
        }
    }

    func nextPostLine(_ st: MachineState) -> String {
        guard let next = st.pending.next else { return "" }
        return text("Next: \(shortDate(iso: next.at)) on \(next.provider).", "Siguiente: \(shortDate(iso: next.at)) en \(next.provider).")
    }

    func announceChanges(from old: MachineState, to new: MachineState) {
        if !old.isUp && new.state == "on" {
            notify("PostForge is on", "Postiz, WhatsApp and the tunnel are up.")
        }
        if openPostizWhenUp && new.state == "on" {
            openPostizWhenUp = false
            openPostizChannels()
        }
        if new.channelsFromCache == false {
            let open = Set((new.channelAlerts ?? []).map(\.key))
            for alert in old.channelAlerts ?? [] where !open.contains(alert.key) {
                guard let ch = new.channels?.first(where: { $0.key == alert.key }) else { continue }
                let until = ch.renews ? text("It renews itself.", "Se renueva automáticamente.") : ch.expires.map { text("Good until \(shortDay(iso: $0)).", "Vigente hasta el \(shortDay(iso: $0)).") } ?? ""
                notify(text("\(alert.network) works again", "\(alert.network) vuelve a funcionar"), text("\(alert.channel) is reconnected. \(until)", "\(alert.channel) está conectado de nuevo. \(until)"))
            }
        }
        if old.isUp && new.state == "off" {
            if new.pending.total > 0 {
                notify(text("PostForge is off with \(plural(new.pending.total, "item")) waiting", "PostForge está apagado con \(new.pending.total) envíos pendientes"),
                       text("Scheduled posts go out late, when it is on again. \(nextPostLine(new))", "Las publicaciones se enviarán con retraso cuando se encienda de nuevo. \(nextPostLine(new))"), turnOnButton: true)
            } else {
                notify("PostForge is off", "Nothing was waiting to be sent.")
            }
        }
        if old.state == "on" && new.state == "on" && old.pending.total > 0 && new.pending.total == 0 {
            notify("Everything is sent", "Nothing is waiting. You can turn PostForge off.")
        }
        if (new.failedPosts ?? 0) > (old.failedPosts ?? 0) {
            notify("A post failed", "Open Postiz to see what went wrong.")
        }
        if old.services.scheduler && new.isUp && !new.services.scheduler {
            notify("Scheduler stopped", "Scheduled posts won't publish. Turn PostForge off and on again.")
        }
        if old.services.whatsapp == "open" && new.isUp && new.services.whatsapp != "open" && new.services.evolution {
            notify("WhatsApp disconnected", text("State: \(new.services.whatsapp ?? "unknown"). It may need to be linked again.", "Estado: \(new.services.whatsapp ?? "desconocido"). Puede que debas vincular WhatsApp otra vez."))
        }
    }

    /// While off, remind before each scheduled post (cached at the last stop).
    func remindIfOff(_ st: MachineState) {
        guard st.state == "off", defaults.bool(forKey: "remindWhenOff") else { return }
        let lead = TimeInterval(defaults.integer(forKey: "remindMinutes") * 60)
        for post in st.scheduled where !remindedPosts.contains(post.id) {
            guard let at = isoParser.date(from: post.at), at.timeIntervalSinceNow < lead else { continue }
            remindedPosts.insert(post.id)
            let when = at.timeIntervalSinceNow < 0 ? text("was due \(shortDate(at))", "debía enviarse el \(shortDate(at))") : text("is scheduled for \(shortDate(at))", "está programada para el \(shortDate(at))")
            notify("PostForge is off", text("A \(post.provider) post \(when). Turn it on to publish it.", "Una publicación de \(post.provider) \(when). Enciende PostForge para enviarla."), turnOnButton: true)
        }
    }

    /// One notification per channel and stage (first warning, a week, three days and a day before,
    /// then expired or disconnected), remembered across restarts. Works while the stack is off too,
    /// from the expiry dates cached at the last poll. A channel that works again starts over.
    func warnAboutChannels(_ st: MachineState) {
        let alerts = st.channelAlerts ?? []
        var told = Set(defaults.stringArray(forKey: "channelAlertsTold") ?? [])
        for alert in alerts {
            let days = alert.daysLeft ?? 99
            let stage = alert.urgent ? alert.reason : days <= 1 ? "1d" : days <= 3 ? "3d" : days <= 7 ? "7d" : "soon"
            let key = alert.key + "|" + stage
            if told.contains(key) { continue }
            told.insert(key)
            notify(alert.headline, text("\(alert.channel). Open the PostForge menu → Reconnect for the steps.", "\(alert.channel). Abre el menú de PostForge → Volver a conectar para ver los pasos."))
        }
        let open = Set(alerts.map(\.key))
        told = told.filter { entry in open.contains { entry.hasPrefix($0 + "|") } }
        defaults.set(Array(told), forKey: "channelAlertsTold")
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound])
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        let action = response.actionIdentifier
        DispatchQueue.main.async {
            if action == "TURN_ON" { self.turnOn() } else { self.statusItem.button?.performClick(nil) }
        }
        completionHandler()
    }

    // MARK: Keep awake

    /// Idle sleep would stop scheduled posts and sends. Closing the lid still sleeps the Mac.
    func updateSleepAssertion() {
        let waiting = (state?.isUp ?? false) && (state?.pending.total ?? 0) > 0
        let want = busy != nil || (waiting && defaults.bool(forKey: "keepAwake"))
        if want && sleepAssertion == 0 {
            IOPMAssertionCreateWithName(kIOPMAssertionTypePreventUserIdleSystemSleep as CFString,
                                        IOPMAssertionLevel(kIOPMAssertionLevelOn),
                                        "PostForge has posts waiting to be sent" as CFString, &sleepAssertion)
        } else if !want && sleepAssertion != 0 {
            IOPMAssertionRelease(sleepAssertion)
            sleepAssertion = 0
        }
    }

    // MARK: Menu bar button

    func statusIndicatorColor() -> NSColor {
        if let busy = busy {
            return busy.contains("Checking") || busy.contains("Turning") ? .systemOrange : .systemOrange
        }
        if let st = state {
            if st.state == "on" && (st.channelAlerts ?? []).filter(\.urgent).isEmpty && stateError == nil {
                return .systemGreen
            }
            if st.state == "partial" || st.state == "starting" || st.state == "stopping" ||
                (st.channelAlerts ?? []).contains(where: { $0.urgent || $0.reason == "expired" || $0.reason == "disconnected" }) {
                return .systemOrange
            }
            if stateError != nil || st.state == "off" && (st.pending.total > 0 || (st.failedPosts ?? 0) > 0) {
                return .systemRed
            }
            return .systemOrange
        }
        if stateError != nil { return .systemRed }
        return .systemOrange
    }

    func updateButton() {
        let active = activeProcessCount
        NSApp.dockTile.badgeLabel = active > 0 ? String(active) : nil
        newPost?.refreshUpdates(available: updatesAvailable)
        guard let button = statusItem.button else { return }
        var symbol = "paperplane"
        var count = 0
        var tip = "PostForge"
        if let busy = busy {
            symbol = "paperplane.fill"
            tip = busy
        } else if let st = state {
            count = st.pending.total
            switch st.state {
            case "on":
                symbol = "paperplane.fill"
                tip = st.activity == "active" ? text("On: \(plural(count, "item")) waiting", "Encendido: \(count) pendientes") : "On: nothing waiting (idle)"
            case "starting", "stopping":
                symbol = "paperplane.fill"
                tip = st.state == "starting" ? text("Starting…", "Iniciando…") : text("Stopping…", "Apagando…")
            case "partial":
                symbol = "exclamationmark.triangle"
                tip = "Partly running: use Turn On to restore all services"
            default:
                tip = st.idleStopped == true ? text("Idle · WhatsApp intake paused", "Inactivo · recepción de WhatsApp pausada") : count > 0 ? text("Off: \(plural(count, "scheduled post")) waiting", "Apagado: \(count) publicaciones pendientes") : "Off"
            }
        } else if stateError != nil {
            symbol = "exclamationmark.triangle"
            tip = "Can't read the machine state"
        }
        if busy == nil, let alerts = state?.channelAlerts, !alerts.isEmpty {
            if alerts.contains(where: \.urgent) { symbol = "exclamationmark.triangle" }
            tip += " · " + alerts.map(\.headline).joined(separator: "; ")
        }
        let image: NSImage?
        if symbol == "paperplane" || symbol == "paperplane.fill" {
            image = postForgeImage()
        } else {
            let config = NSImage.SymbolConfiguration(pointSize: 8, weight: .semibold)
            image = NSImage(systemSymbolName: symbol, accessibilityDescription: "PostForge")?.withSymbolConfiguration(config)
            image?.isTemplate = true
        }
        button.image = image
        button.alphaValue = symbol == "paperplane" ? 0.5 : 1  // the glyph is dimmed while the stack is off
        button.imagePosition = .imageLeading
        button.imageScaling = .scaleNone
        button.title = (active > 0 ? " \(active)" : "") + (updatesAvailable ? " •" : "")
        if active > 0 { tip += text(" · \(active) running", " · \(active) en curso") }
        if updatesAvailable { tip += text(" · Updates available", " · Hay actualizaciones disponibles") }
        button.toolTip = "PostForge: " + tip
    }

    // MARK: Menu

    /// Opening the menu checks again, so views and sends show up without waiting for the timer.
    func menuWillOpen(_ menu: NSMenu) {
        menuOpen = true
        idleSince = nil
        refreshNotificationStatus()
        poll()
    }

    func menuDidClose(_ menu: NSMenu) { menuOpen = false }

    func idleStopDue(at now: Date) -> Bool {
        guard defaults.bool(forKey: "autoStopWhenIdle"), !uninstalling, !menuOpen,
              busy == nil, windowWork == 0, planningWork == 0, stateError == nil,
              let st = state, st.isUp, !st.pending.fromCache, st.pending.total == 0 else {
            idleSince = nil
            return false
        }
        if idleSince == nil { idleSince = now }
        let minutes = max(1, defaults.integer(forKey: "idleStopMinutes"))
        return now.timeIntervalSince(idleSince ?? now) >= TimeInterval(minutes * 60)
    }

    func stopWhenIdleIfNeeded() {
        guard idleStopDue(at: Date()) else { return }
        var args = ["stop", "--idle"]
        if defaults.bool(forKey: "whatsappIdleNotice") { args.append("--notify-self") }
        runLifecycle(args, busyText: text("Entering idle mode…", "Entrando en modo inactivo…"), showProgress: false) { code, _ in
            if code == 0 {
                self.notify(self.text("PostForge is idle", "PostForge está inactivo"),
                            self.text("Services are off. WhatsApp intake resumes when you turn PostForge on.",
                                      "Los servicios están apagados. La recepción de WhatsApp se reanuda al encender PostForge."))
            } else if code != 3 {
                self.notify("PostForge didn't stop cleanly", "See Open Log in the menu bar app.")
            }
        }
    }

    func scheduleWake(for post: ScheduledPost?) {
        guard let post, let at = isoParser.date(from: post.at), at > Date() else {
            wakeSchedule = nil
            return
        }
        if let wakeSchedule, wakeSchedule.at == post.at, wakeSchedule.retryAfter > Date() { return }
        wakeSchedule = (post.at, .distantFuture)
        let dir = project
        DispatchQueue.global(qos: .utility).async {
            let result = runCommand(["/usr/bin/python3", dir + "/scripts/schedule-wake.py", "--at", post.at],
                                    in: dir, timeout: 20)
            if result.0 != 0 {
                self.log("wake scheduling failed (exit \(result.0))")
                DispatchQueue.main.async {
                    if self.wakeSchedule?.at == post.at {
                        self.wakeSchedule = (post.at, Date().addingTimeInterval(900))
                    }
                }
            }
        }
    }

    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        let st = state
        let up = st?.isUp ?? false
        let canAct = busy == nil && st?.state != "starting" && st?.state != "stopping"
        let isOff = st?.state == "off" || st?.state == "partial" || st == nil

        // 1. One status line: is it working?
        let header: String
        if let busy = busy {
            header = busy
        } else if let st = st {
            switch st.state {
            case "on": header = text("Ready to post", "Listo para publicar")
            case "partial": header = text("Needs attention", "Requiere atención")
            case "starting": header = text("Turning on…", "Encendiendo…")
            case "stopping": header = text("Turning off…", "Apagando…")
            default: header = st.idleStopped == true ? text("Idle · services off", "Inactivo · servicios apagados") : st.docker ? text("Off", "Apagado") : text("Off (Docker Desktop not running)", "Apagado (Docker Desktop no está abierto)")
            }
        } else {
            header = stateError == nil ? text("Checking…", "Comprobando…") : text("Can't read status", "No se puede leer el estado")
        }
        let title = NSMenuItem(title: "", action: nil, keyEquivalent: "")
        let combined = NSMutableAttributedString()
        combined.append(NSAttributedString(string: "● ", attributes: [
            .font: NSFont.boldSystemFont(ofSize: 13), .foregroundColor: statusIndicatorColor()]))
        combined.append(NSAttributedString(string: header, attributes: [
            .font: NSFont.boldSystemFont(ofSize: 13), .foregroundColor: NSColor.labelColor]))
        title.attributedTitle = combined
        title.isEnabled = false
        menu.addItem(title)
        if let error = stateError { menu.addItem(info("⚠︎ " + String(error.prefix(80)))) }
        menu.addItem(.separator())

        // 2. What you came to do.
        let newPostItem = action(text("New Post…", "Nueva publicación…"), #selector(openNewPost), enabled: up)
        newPostItem.keyEquivalent = "n"
        menu.addItem(newPostItem)
        let draftOptions = NSMenu()
        draftOptions.autoenablesItems = false
        for (index, title) in [
            text("Posts Only…", "Solo publicaciones…"),
            text("Stories Only…", "Solo historias…"),
            text("Posts and Stories…", "Publicaciones e historias…"),
            text("Choose Cover Image…", "Elegir imagen de portada…"),
            text("Set Cover Timestamp…", "Indicar segundo de portada…"),
        ].enumerated() {
            if index == 3 { draftOptions.addItem(.separator()) }
            let item = action(title, #selector(openDraftOption(_:)), enabled: up)
            item.tag = index + 1
            draftOptions.addItem(item)
        }
        let optionsItem = NSMenuItem(title: text("Draft Options", "Opciones de borrador"), action: nil, keyEquivalent: "")
        optionsItem.submenu = draftOptions
        optionsItem.isEnabled = up
        menu.addItem(optionsItem)
        menu.addItem(action(text("Open Postiz Calendar", "Abrir calendario de Postiz"), #selector(openPostiz), enabled: up))
        menu.addItem(action(text("WhatsApp Plans & Receipts…", "Planes y confirmaciones de WhatsApp…"), #selector(reviewWhatsAppPlans), enabled: true))
        if isOff {
            menu.addItem(action(st?.state == "partial" ? text("Restore All Services", "Restaurar todos los servicios") :
                                text("Turn On", "Encender"),
                                #selector(turnOn), enabled: canAct && st != nil))
        } else {
            menu.addItem(action(text("Turn Off…", "Apagar…"), #selector(turnOff), enabled: canAct))
        }

        // 3. What needs you.
        var attention: [NSMenuItem] = []
        if let st = st {
            for alert in st.channelAlerts ?? [] {
                let item = action((alert.urgent ? "✗ " : "⚠︎ ") + alert.headline + "…", #selector(reconnectChannel(_:)),
                                  enabled: busy == nil)
                item.representedObject = alert.key
                attention.append(item)
            }
            if st.isUp && !st.services.scheduler && st.services.postiz {
                attention.append(info(text("⚠︎ Scheduled posts won't publish: scheduler is stopped",
                                           "⚠︎ Las publicaciones programadas no saldrán: el programador está detenido")))
            }
            if let errors = st.failedPosts, errors > 0 {
                attention.append(info(text("⚠︎ \(plural(errors, "post")) failed in the last 24 h", "⚠︎ \(errors) publicaciones fallaron en 24 h")))
            }
            if let count = st.pending.whatsapp?.needsReview, count > 0 {
                attention.append(info(text("⚠︎ WhatsApp Status delivery needs review (\(count))",
                                           "⚠︎ Hay Estados de WhatsApp por revisar (\(count))")))
            }
            if let wa = st.pending.whatsapp, wa.confirmations > 0 {
                attention.append(action(text("Review WhatsApp Plans (\(wa.confirmations))…", "Revisar planes de WhatsApp (\(wa.confirmations))…"),
                                        #selector(reviewWhatsAppPlans), enabled: true))
            }
        }
        if !attention.isEmpty {
            menu.addItem(.separator())
            menu.addItem(sectionHeader(text("Needs your attention", "Requiere tu atención")))
            attention.forEach(menu.addItem)
        }

        if let st = st {
            menu.addItem(.separator())
            menu.addItem(sectionHeader(text("Posting activity", "Actividad de publicaciones")))
            addWorkItems(st, to: menu)
            let connections = connectionLines(st)
            if !connections.isEmpty {
                menu.addItem(.separator())
                menu.addItem(sectionHeader(text("Channel connections", "Conexiones de canales")))
                for line in connections { menu.addItem(info(line)) }
            }
        }

        menu.addItem(.separator())
        menu.addItem(action(updatesAvailable ? text("Updates Available…", "Actualizaciones disponibles…") :
                            text("Check for Updates…", "Buscar actualizaciones…"),
                            #selector(checkUpdatesFromMenu), enabled: busy == nil))
        let tools = NSMenuItem(title: text("Settings & Tools", "Ajustes y herramientas"), action: nil, keyEquivalent: "")
        tools.submenu = settingsMenu(up: up, canAct: canAct)
        menu.addItem(tools)
        menu.addItem(.separator())
        menu.addItem(action(text("PostForge Help", "Ayuda de PostForge"), #selector(showUserGuide), enabled: true))
        menu.addItem(action(text("About PostForge", "Acerca de PostForge"), #selector(showAbout), enabled: true))
        menu.addItem(action(up ? text("Quit PostForge (posting keeps running)", "Salir de PostForge (sigue publicando)") :
                            text("Quit PostForge", "Salir de PostForge"),
                            #selector(quitApp), enabled: true))
    }

    func settingsMenu(up: Bool, canAct: Bool) -> NSMenu {
        let menu = NSMenu()
        menu.autoenablesItems = false

        menu.addItem(sectionHeader(text("Behavior", "Comportamiento")))
        menu.addItem(toggle(text("Turn Off When Idle", "Apagar al estar inactivo"), key: "autoStopWhenIdle"))
        menu.addItem(toggle(text("Notify My WhatsApp Before Idle", "Avisarme por WhatsApp antes de apagar"), key: "whatsappIdleNotice"))
        menu.addItem(toggle(text("Keep Mac Awake While Posts Wait", "Mantener Mac activa mientras espera"), key: "keepAwake"))
        menu.addItem(toggle(text("Remind Me Before Posts When Off", "Recordarme antes de publicar apagado"), key: "remindWhenOff"))
        let login = action(text("Open at Login", "Abrir al iniciar sesión"), #selector(toggleLogin), enabled: true)
        login.state = SMAppService.mainApp.status == .enabled ? .on : .off
        menu.addItem(login)
        if let status = notifications, status != .authorized && status != .provisional {
            menu.addItem(action(status == .notDetermined ? "Allow Notifications…" : "Allow Notifications (off in System Settings)…",
                                #selector(allowNotifications), enabled: true))
        }
        let language = NSMenuItem(title: text("Language", "Idioma"), action: nil, keyEquivalent: "")
        let languageMenu = NSMenu()
        languageMenu.addItem(languageChoice("English", code: "en"))
        languageMenu.addItem(languageChoice("Español (Ecuador)", code: "es"))
        language.submenu = languageMenu
        menu.addItem(language)

        menu.addItem(.separator())
        menu.addItem(sectionHeader(text("Channels", "Canales")))
        let audience = statusAudience()
        let audienceMenu = NSMenu()
        audienceMenu.addItem(audienceChoice(text("Public: all contacts", "Público: todos los contactos"), value: "all", current: audience))
        audienceMenu.addItem(audienceChoice(text("Private: test recipients", "Privado: destinatarios de prueba"), value: "test", current: audience))
        audienceMenu.addItem(action(text("Configure test numbers…", "Configurar números de prueba…"),
                                    #selector(editTestRecipients), enabled: true))
        let audienceItem = NSMenuItem(title: text("WhatsApp Status Audience", "Audiencia del estado de WhatsApp"),
                                      action: nil, keyEquivalent: "")
        audienceItem.submenu = audienceMenu
        menu.addItem(audienceItem)
        menu.addItem(action(text("Open WhatsApp Manager", "Abrir WhatsApp Manager"), #selector(openEvolution), enabled: up))
        menu.addItem(action(text("Tunnel URL…", "URL del túnel…"), #selector(editTunnelURL), enabled: busy == nil))
        menu.addItem(action(text("Gateway Access…", "Acceso a la puerta de enlace…"), #selector(editGatewayAccess), enabled: busy == nil))

        menu.addItem(.separator())
        menu.addItem(sectionHeader(text("Maintenance", "Mantenimiento")))
        menu.addItem(action(text("Saved History: \(retentionDays()) days…", "Historial guardado: \(retentionDays()) días…"), #selector(editRetention), enabled: busy == nil))
        menu.addItem(action(text("Restart Everything…", "Reiniciar todo…"), #selector(restartEverything), enabled: canAct))
        menu.addItem(action(text("Backup & Move…", "Respaldo y traslado…"), #selector(openBackupWindow), enabled: true))
        menu.addItem(action(text("Open Log", "Abrir registro"), #selector(openLog), enabled: true))
        menu.addItem(.separator())
        menu.addItem(action(text("Uninstall PostForge…", "Desinstalar PostForge…"), #selector(uninstallPostForge), enabled: busy == nil))
        return menu
    }

    func addWorkItems(_ st: MachineState, to menu: NSMenu) {
        let pending = st.pending
        if pending.scheduled > 0 {
            var label = text("Scheduled posts: \(pending.scheduled)", "Publicaciones programadas: \(pending.scheduled)")
            if pending.overdue > 0 { label += text(" (\(pending.overdue) overdue)", " (\(pending.overdue) atrasadas)") }
            if pending.fromCache, let cached = pending.cachedAt { label += text(" · as of \(shortDate(iso: cached))", " · al \(shortDate(iso: cached))") }
            let item = info(label, interactive: true)
            let sub = NSMenu()
            for post in st.scheduled {
                sub.addItem(info("\(shortDate(iso: post.at))  ·  \(post.provider)  ·  \(post.text.prefix(48))"))
            }
            if pending.scheduled > st.scheduled.count {
                sub.addItem(info(text("… and \(pending.scheduled - st.scheduled.count) more", "… y \(pending.scheduled - st.scheduled.count) más")))
            }
            item.submenu = sub
            menu.addItem(item)
            if let next = pending.next { menu.addItem(info(text("Next: \(shortDate(iso: next.at)) · \(next.provider)", "Siguiente: \(shortDate(iso: next.at)) · \(next.provider)"))) }
        } else {
            menu.addItem(info(text("No scheduled posts waiting", "No hay publicaciones programadas pendientes")))
        }
        for job in pending.jobs {
            menu.addItem(info(text("Sending now: \(job.kind) · \(job.label.prefix(40))", "Enviando ahora: \(job.kind) · \(job.label.prefix(40))")))
        }
        if let drafts = st.drafts, drafts > 0 { menu.addItem(info(text("Drafts to review in Postiz: \(drafts)", "Borradores para revisar en Postiz: \(drafts)"))) }
        if let wa = pending.whatsapp {
            if wa.pending > 0 {
                var parts: [String] = []
                if wa.awaitingApproval > 0 { parts.append(text("\(wa.awaitingApproval) awaiting approval", "\(wa.awaitingApproval) esperando aprobación")) }
                if wa.approved > 0 { parts.append(text("\(wa.approved) approved", "\(wa.approved) aprobados")) }
                menu.addItem(info(text("WhatsApp Status: " + parts.joined(separator: ", "), "Estado de WhatsApp: " + parts.joined(separator: ", "))))
                if st.isUp && wa.awaitingApproval > 0 {
                    let statusMenu = NSMenu()
                    statusMenu.autoenablesItems = false
                    for status in pendingStatusApprovals().suffix(8).reversed() {
                        guard let id = status["id"] as? String else { continue }
                        let when = (status["when"] as? String).map { shortDate(iso: $0) } ?? ""
                        let caption = (status["caption"] as? String ?? "").split(whereSeparator: \.isNewline).joined(separator: " ")
                        let entry = action("\(when) · \(caption.prefix(36))", #selector(approveStatusFromMenu(_:)), enabled: busy == nil)
                        entry.representedObject = id
                        statusMenu.addItem(entry)
                    }
                    if !statusMenu.items.isEmpty {
                        let approval = NSMenuItem(title: text("Approve WhatsApp Status…", "Aprobar Estado de WhatsApp…"),
                                                  action: nil, keyEquivalent: "")
                        approval.submenu = statusMenu
                        menu.addItem(approval)
                    }
                }
                if let next = wa.next { menu.addItem(info(text("Next WhatsApp Status: \(shortDate(iso: next))", "Siguiente estado de WhatsApp: \(shortDate(iso: next))"))) }
            }
        }
        if let last = st.lastStatus {
            let when = shortDate(Date(timeIntervalSince1970: TimeInterval(last.ts)))
            let item = info(text("Last WhatsApp status: \(when) · \(last.viewed) viewed",
                                "Último estado de WhatsApp: \(when) · \(last.viewed) vistos"), interactive: true)
            let sub = NSMenu()
            let statusText = last.text.split(whereSeparator: \.isNewline).joined(separator: " ")
            if !statusText.isEmpty { sub.addItem(info("“\(statusText.prefix(50))”")) }
            sub.addItem(info(text("Received by \(last.received) · viewed by \(last.viewed)",
                                  "Recibido por \(last.received) · visto por \(last.viewed)")))
            let names = last.viewerNames ?? []
            if names.isEmpty {
                sub.addItem(info(text("No views yet. Views show only if both phones have read receipts on.",
                                      "Aún no hay vistas. Solo aparecen si ambos teléfonos tienen confirmaciones de lectura activadas.")))
            } else {
                sub.addItem(.separator())
                for name in names { sub.addItem(info("👁 " + name)) }
                if last.viewed > names.count { sub.addItem(info(text("… and \(last.viewed - names.count) more", "… y \(last.viewed - names.count) más"))) }
            }
            item.submenu = sub
            menu.addItem(item)
        }
    }

    func sectionHeader(_ title: String) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: nil, keyEquivalent: "")
        item.isEnabled = false
        item.attributedTitle = NSAttributedString(
            string: title,
            attributes: [
                .font: NSFont.systemFont(ofSize: 10, weight: .semibold),
                .foregroundColor: NSColor.secondaryLabelColor,
                .kern: 0.8,
            ])
        return item
    }

    func info(_ text: String, interactive: Bool = false) -> NSMenuItem {
        let item = NSMenuItem(title: localizedUI(text), action: nil, keyEquivalent: "")
        item.isEnabled = interactive
        item.attributedTitle = NSAttributedString(
            string: localizedUI(text),
            attributes: [
                .font: NSFont.systemFont(ofSize: 12),
                .foregroundColor: interactive ? NSColor.labelColor : NSColor.secondaryLabelColor,
            ])
        return item
    }

    func action(_ title: String, _ selector: Selector, enabled: Bool) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: selector, keyEquivalent: "")
        item.target = self
        item.isEnabled = enabled
        return item
    }

    func toggle(_ title: String, key: String) -> NSMenuItem {
        let item = action(title, #selector(flipSetting(_:)), enabled: true)
        item.representedObject = key
        item.state = defaults.bool(forKey: key) ? .on : .off
        return item
    }

    func languageChoice(_ title: String, code: String) -> NSMenuItem {
        let item = action(title, #selector(changeLanguage(_:)), enabled: true)
        item.representedObject = code
        item.state = defaults.string(forKey: "uiLanguage") == code ? .on : .off
        return item
    }

    func statusAudience() -> String {
        guard let contents = try? String(contentsOfFile: project + "/.env", encoding: .utf8) else { return "all" }
        return contents.split(separator: "\n").first { $0.hasPrefix("WA_STATUS_AUDIENCE=") }
            .map { String($0.dropFirst("WA_STATUS_AUDIENCE=".count)) } ?? "all"
    }

    func audienceChoice(_ title: String, value: String, current: String) -> NSMenuItem {
        let item = action(title, #selector(changeStatusAudience(_:)), enabled: true)
        item.representedObject = value
        item.state = current == value ? .on : .off
        return item
    }

    // MARK: Actions

    @objc func flipSetting(_ sender: NSMenuItem) {
        guard let key = sender.representedObject as? String else { return }
        defaults.set(!defaults.bool(forKey: key), forKey: key)
        updateSleepAssertion()
    }

    @objc func changeLanguage(_ sender: NSMenuItem) {
        guard let code = sender.representedObject as? String else { return }
        defaults.set(code, forKey: "uiLanguage")
        try? code.write(toFile: project + "/run/ui-language", atomically: true, encoding: .utf8)
        NSApp.mainMenu = buildMainMenu()
        configureNotificationActions()
        refreshLocalizedWindows()
        if let menu = statusItem.menu { menuNeedsUpdate(menu) }
        poll()
    }

    @objc func changeStatusAudience(_ sender: NSMenuItem) {
        guard let value = sender.representedObject as? String else { return }
        let path = project + "/.env"
        guard var contents = try? String(contentsOfFile: path, encoding: .utf8) else {
            alert(text("Cannot read .env", "No se puede leer .env"), text("Check the project configuration.", "Revisa la configuración del proyecto."))
            return
        }
        let line = "WA_STATUS_AUDIENCE=\(value)"
        if let range = contents.range(of: #"(?m)^WA_STATUS_AUDIENCE=.*$"#, options: .regularExpression) {
            contents.replaceSubrange(range, with: line)
        } else {
            contents += "\n\(line)\n"
        }
        do {
            try contents.write(toFile: path, atomically: true, encoding: .utf8)
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: path)
            if let menu = statusItem.menu { menuNeedsUpdate(menu) }
        } catch {
            alert(text("Could not save status audience", "No se pudo guardar la audiencia"),
                  error.localizedDescription)
        }
    }

    func testRecipients() -> String {
        guard let contents = try? String(contentsOfFile: project + "/.env", encoding: .utf8) else { return "" }
        return contents.split(separator: "\n").first { $0.hasPrefix("WA_TEST_RECIPIENTS=") }
            .map { String($0.dropFirst("WA_TEST_RECIPIENTS=".count)) } ?? ""
    }

    @objc func editTestRecipients() {
        let dialog = NSAlert()
        dialog.messageText = text("Test WhatsApp recipients", "Destinatarios de prueba de WhatsApp")
        dialog.informativeText = text("Enter country-code numbers separated by commas, without + signs.\nExample: 593991234567,593998765432",
                                      "Ingresa números con código de país separados por comas, sin signos +.\nEjemplo: 593991234567,593998765432")
        let field = NSTextField(string: testRecipients())
        field.frame = NSRect(x: 0, y: 0, width: 360, height: 24)
        field.placeholderString = "593991234567,593998765432"
        dialog.accessoryView = field
        dialog.addButton(withTitle: text("Save", "Guardar"))
        dialog.addButton(withTitle: text("Cancel", "Cancelar"))
        NSApp.activate(ignoringOtherApps: true)
        guard dialog.runModal() == .alertFirstButtonReturn else { return }

        let value = field.stringValue.replacingOccurrences(of: " ", with: "")
        let numbers = value.split(separator: ",").map(String.init)
        guard !value.isEmpty, !numbers.isEmpty,
              numbers.allSatisfy({ $0.range(of: #"^[0-9]{7,15}$"#, options: .regularExpression) != nil }) else {
            alert(text("Invalid test numbers", "Números de prueba inválidos"),
                  text("Use 7–15 digits per number, separated by commas.", "Usa entre 7 y 15 dígitos por número, separados por comas."))
            return
        }
        updateEnvValue(key: "WA_TEST_RECIPIENTS", value: numbers.joined(separator: ","))
    }

    @objc func editCaptionFinalTag() {
        let contents = (try? String(contentsOfFile: project + "/.env", encoding: .utf8)) ?? ""
        let current = contents.split(separator: "\n").first { $0.hasPrefix("CAPTION_FINAL_TAG=") }
            .map { String($0.dropFirst("CAPTION_FINAL_TAG=".count)).trimmingCharacters(in: CharacterSet(charactersIn: "\"'")) } ?? ""
        let field = NSTextField(string: current)
        field.placeholderString = "#MiNegocio"
        field.frame = NSRect(x: 0, y: 0, width: 250, height: 24)
        let dialog = NSAlert()
        dialog.messageText = text("Final hashtag", "Etiqueta final")
        dialog.informativeText = text("This hashtag goes at the end of new captions. Leave it blank to skip it.",
                                      "Esta etiqueta va al final de los textos nuevos. Déjala en blanco si prefieres omitirla.")
        dialog.accessoryView = field
        dialog.addButton(withTitle: text("Save", "Guardar"))
        dialog.addButton(withTitle: text("Cancel", "Cancelar"))
        dialog.window.initialFirstResponder = field
        guard dialog.runModal() == .alertFirstButtonReturn else { return }
        let raw = field.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        let tag = raw.isEmpty || raw.hasPrefix("#") ? raw : "#" + raw
        guard tag.isEmpty || tag.range(of: #"^#[\p{L}\p{N}_]{1,60}$"#, options: .regularExpression) != nil else {
            alert(text("Invalid hashtag", "Etiqueta no válida"),
                  text("Use one hashtag with letters, numbers or underscores, without spaces.",
                       "Usa una sola etiqueta con letras, números o guiones bajos, sin espacios."))
            return
        }
        updateEnvValue(key: "CAPTION_FINAL_TAG", value: "\"\(tag)\"")
        newPost?.draftOptionsChanged()
    }

    func updateEnvValue(key: String, value: String) {
        let path = project + "/.env"
        guard var contents = try? String(contentsOfFile: path, encoding: .utf8) else {
            alert(text("Cannot read .env", "No se puede leer .env"),
                  text("Check the project configuration.", "Revisa la configuración del proyecto."))
            return
        }
        let line = "\(key)=\(value)"
        let pattern = "(?m)^" + NSRegularExpression.escapedPattern(for: key) + "=.*$"
        if let range = contents.range(of: pattern, options: .regularExpression) {
            contents.replaceSubrange(range, with: line)
        } else {
            contents += "\n\(line)\n"
        }
        do {
            try contents.write(toFile: path, atomically: true, encoding: .utf8)
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: path)
            if let menu = statusItem.menu { menuNeedsUpdate(menu) }
        } catch {
            alert(text("Could not save settings", "No se pudieron guardar los ajustes"),
                  error.localizedDescription)
        }
    }

    /// Not asked yet: show macOS's prompt again. Turned off: open the app's page in System Settings.
    @objc func allowNotifications() {
        if notifications == .notDetermined {
            UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { _, _ in
                self.refreshNotificationStatus()
            }
            return
        }
        let page = "x-apple.systempreferences:com.apple.Notifications-Settings.extension?id=" + (Bundle.main.bundleIdentifier ?? "")
        if let url = URL(string: page) { NSWorkspace.shared.open(url) }
    }

    @objc func toggleLogin() {
        do {
            if SMAppService.mainApp.status == .enabled {
                try SMAppService.mainApp.unregister()
            } else {
                try SMAppService.mainApp.register()
            }
        } catch {
            alert(text("Couldn't change Open at Login", "No se pudo cambiar Abrir al iniciar sesión"), error.localizedDescription)
        }
    }

    @objc func turnOn() {
        runLifecycle(["start"], busyText: "Turning on…") { code, _ in
            if code != 0 { self.notify("PostForge didn't start", "See Open Log in the menu bar app.") }
        }
    }

    @objc func turnOff() {
        busy = text("Checking what's waiting…", "Revisando los envíos pendientes…")
        updateButton()
        let dir = project
        DispatchQueue.global(qos: .userInitiated).async {
            let (code, output) = runCommand(["/usr/bin/python3", dir + "/scripts/lib/machine_state.py", "--json"],
                                            in: dir, timeout: 45)
            DispatchQueue.main.async {
                self.busy = nil
                self.finishPoll(code: code, output: output)
                self.confirmAndStop()
            }
        }
    }

    func confirmAndStop() {
        guard let st = state else {
            if ask("Can't check what's waiting", "Turn PostForge off anyway?",
                   safe: "Keep Running", risky: "Turn Off Anyway") { stop() }
            return
        }
        if st.pending.total == 0 { stop(); return }
        var lines: [String] = st.scheduled.prefix(6).map { "• \(shortDate(iso: $0.at)) · \($0.provider) · \($0.text.prefix(40))" }
        if st.pending.scheduled > 6 { lines.append(text("• … and \(st.pending.scheduled - 6) more", "• … y \(st.pending.scheduled - 6) más")) }
        lines += st.pending.jobs.map { text("• Sending now: \($0.label.prefix(50))", "• Enviando ahora: \($0.label.prefix(50))") }
        if let wa = st.pending.whatsapp {
            if wa.confirmations > 0 { lines.append(text("• \(wa.confirmations) WhatsApp plan(s) awaiting confirmation", "• \(wa.confirmations) planes de WhatsApp pendientes de confirmación")) }
            if wa.approved > 0, let next = wa.next {
                lines.append(text("• \(wa.approved) approved WhatsApp Status(es), next \(shortDate(iso: next))", "• \(wa.approved) estados de WhatsApp aprobados; siguiente: \(shortDate(iso: next))"))
            }
        }
        var detail = lines.joined(separator: "\n")
        if st.pending.scheduled > 0 || !st.pending.jobs.isEmpty || (st.pending.whatsapp?.approved ?? 0) > 0 {
            detail += text("\n\nIf you turn it off now, scheduled posts go out late, as soon as PostForge is on again. A WhatsApp status that is still sending may reach only part of its audience.", "\n\nSi lo apagas ahora, las publicaciones se enviarán con retraso cuando PostForge vuelva a encenderse. Un estado de WhatsApp que se está enviando podría llegar solo a parte de sus destinatarios.")
        } else {
            detail += text("\n\nPending WhatsApp plans will remain saved, but drafts and statuses will wait until you turn it on again.", "\n\nLos planes pendientes de WhatsApp seguirán guardados, pero los borradores y estados esperarán hasta que vuelvas a encenderlo.")
        }
        if ask(text("\(plural(st.pending.total, "item")) still waiting to be sent", "Hay \(st.pending.total) envíos pendientes"), detail,
               safe: "Keep Running", risky: "Turn Off Anyway") { stop() }
    }

    func stop() {
        runLifecycle(["stop", "--force"], busyText: "Turning off…") { code, _ in
            if code != 0 { self.notify("PostForge didn't stop cleanly", "See Open Log in the menu bar app.") }
        }
    }

    @objc func restartEverything() {
            let count = state?.pending.total ?? 0
            let detail = count > 0
                ? text("\(plural(count, "item")) is waiting. It will remain saved, but scheduled work may be delayed while the stack restarts.", "Hay \(count) envíos pendientes. Seguirán guardados, pero podrían retrasarse mientras se reinician los servicios.")
                : text("The PostForge stack will restart. Docker Desktop and other containers will remain running.", "Se reiniciarán los servicios de PostForge. Docker Desktop y los demás contenedores seguirán funcionando.")
            if ask("Restart PostForge?", detail,
                   safe: "Cancel", risky: "Restart Now") {
                runLifecycle(["restart"], busyText: "Restarting everything…") { code, _ in
                    if code != 0 {
                        self.notify("PostForge didn't restart cleanly", "See Open Log in the menu bar app.")
                    }
                }

            }
        }

    @objc func checkUpdatesFromMenu() { openUpdates() }

    @objc func applyStableUpdates() {
        let detail = text("A code and image rollback snapshot will be created. Declared Docker images download before services restart, then health is verified. Database migrations are not reversed by rollback. Homebrew tools are updated separately.", "Se creará un respaldo del código y las imágenes para volver atrás. Los componentes de Docker se descargan antes de reiniciar los servicios y luego se verifica su funcionamiento. Volver atrás no revierte las migraciones de la base de datos. Las herramientas de Homebrew se actualizan por separado.")
        guard ask(text("Apply stable Docker updates?", "¿Actualizar los componentes de Docker?"), detail, safe: text("Cancel", "Cancelar"), risky: text("Update and Restart", "Actualizar y reiniciar")) else { return }
        runLifecycle(["maintenance", "update", "--apply", "--yes"], busyText: self.text("Updating safely…", "Actualizando de forma segura…")) { code, output in
            if code != 0 {
                self.notify("Update did not complete", output.isEmpty ? "See Open Log in the menu bar app." : String(output.suffix(180)))
            } else {
                self.maintenance = nil
                self.updateNoticeShown = false
                self.notify("PostForge updated", "The Docker stack was refreshed and health was checked.")
            }
        }
    }

    @objc func editGatewayAccess() {
        let command = ["/usr/bin/python3", project + "/v2/gateway_setup.py"]
        let (code, output) = runCommand(command + ["list-users"], in: project, timeout: 5, quietErrors: true)
        guard code == 0, let data = output.data(using: .utf8),
              let users = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]],
              !users.isEmpty else {
            alert(text("Set up gateway users first", "Primero configura los usuarios de acceso"),
                  text("Provision users and authenticator codes locally using the gateway setup guide.",
                       "Configura los usuarios y sus códigos de autenticación en el equipo según la guía de acceso."))
            return
        }
        let choices = users.compactMap { user -> (String, Bool)? in
            guard let email = user["email"] as? String, let allowed = user["allowed"] as? Bool else { return nil }
            return (email, allowed)
        }
        guard !choices.isEmpty else { return }
        let popup = NSPopUpButton(frame: NSRect(x: 0, y: 0, width: 380, height: 28), pullsDown: false)
        popup.addItems(withTitles: choices.map { email, allowed in
            email + (allowed ? text(" · Allowed", " · Permitido") : text(" · Blocked", " · Bloqueado"))
        })
        let dialog = NSAlert()
        dialog.messageText = text("Gateway allowlist", "Lista de acceso")
        dialog.informativeText = text("Select a user and choose whether to allow or block them. Restart the identity service to apply the change and clear existing gateway sessions.",
                                      "Elige un usuario y decide si permitir o bloquear su acceso. Reinicia el servicio de identidad para aplicar el cambio y cerrar las sesiones de acceso actuales.")
        dialog.accessoryView = popup
        dialog.addButton(withTitle: text("Cancel", "Cancelar"))
        dialog.addButton(withTitle: text("Allow", "Permitir"))
        dialog.addButton(withTitle: text("Block", "Bloquear"))
        NSApp.activate(ignoringOtherApps: true)
        let answer = dialog.runModal()
        guard answer == .alertSecondButtonReturn || answer == .alertThirdButtonReturn,
              choices.indices.contains(popup.indexOfSelectedItem) else { return }
        let email = choices[popup.indexOfSelectedItem].0
        let (result, _) = runCommand(command + ["set-allowed", email, answer == .alertSecondButtonReturn ? "allow" : "deny"],
                                     in: project, timeout: 5, quietErrors: true)
        if result == 0 {
            alert(text("Gateway access saved", "Acceso guardado"),
                  text("Restart the identity service from the gateway setup to apply it.", "Reinicia el servicio de identidad según la guía de acceso para aplicarlo."))
        } else {
            alert(text("Couldn't change gateway access", "No se pudo cambiar el acceso"),
                  text("Keep at least one user allowed and verify the gateway configuration.", "Mantén al menos un usuario permitido y verifica la configuración de acceso."))
        }
    }

    @objc func editTunnelURL() {
        let current = (try? String(contentsOfFile: project + "/.env", encoding: .utf8))?
            .split(separator: "\n").first { $0.hasPrefix("FRONTEND_URL=") }
            .map { String($0.dropFirst("FRONTEND_URL=".count)) } ?? ""
        let field = NSTextField(string: current)
        field.frame = NSRect(x: 0, y: 0, width: 360, height: 24)
        let dialog = NSAlert()
        dialog.messageText = text("Tunnel URL", "URL del túnel")
        dialog.informativeText = text("Enter the HTTPS domain used by ngrok or your custom domain. Postiz will briefly restart. If verification fails, PostForge will restore the previous URL. Update your providers’ OAuth callback URLs for the new domain.",
                                      "Escribe el dominio HTTPS de ngrok o tu dominio personalizado. Las URL relacionadas de Postiz se actualizarán juntas; reinicia después.")
        dialog.accessoryView = field
        dialog.addButton(withTitle: text("Save", "Guardar"))
        dialog.addButton(withTitle: text("Cancel", "Cancelar"))
        NSApp.activate(ignoringOtherApps: true)
        guard dialog.runModal() == .alertFirstButtonReturn else { return }
        let value = field.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty else {
            alert(text("Couldn't change tunnel URL", "No se pudo cambiar la URL del túnel"),
                  text("Enter an HTTPS domain.", "Escribe un dominio HTTPS."))
            return
        }
        runLifecycle(["tunnel-url", value], busyText: text("Changing tunnel URL…", "Cambiando la URL del túnel…")) { code, output in
            if code == 0 {
                self.alert(self.text("Tunnel URL verified", "URL del túnel verificada"),
                           self.text("Check Postiz sign-in and your providers’ OAuth settings on the new domain.",
                                     "Verifica el inicio de sesión en Postiz y la configuración de OAuth de tus proveedores en el nuevo dominio."))
            } else {
                self.alert(self.text("Couldn't change tunnel URL", "No se pudo cambiar la URL del túnel"), failureSummary(output))
            }
        }
    }

    // MARK: Backup & Move, WhatsApp review, uninstall

    @objc func openBackupWindow() {
        if backupWindow == nil { backupWindow = BackupWindow(delegate: self) }
        backupWindow?.show()
    }

    @objc func reviewWhatsAppPlans() {
        if whatsappWindow == nil { whatsappWindow = WhatsAppWindow(delegate: self) }
        whatsappWindow?.show(state: state)
    }

    func recordBackup(path: String) {
        defaults.set(Date(), forKey: "lastBackupDate")
        defaults.set(path, forKey: "lastBackupPath")
    }

    /// The last backup made here, if its folder still holds the encrypted credentials.
    func lastBackup() -> (date: Date, path: String)? {
        guard let date = defaults.object(forKey: "lastBackupDate") as? Date,
              let path = defaults.string(forKey: "lastBackupPath"),
              FileManager.default.fileExists(atPath: path + "/credentials.env.enc") else { return nil }
        return (date, path)
    }

    @objc func uninstallPostForge() {
        let backup = lastBackup()
        var detail = text("This permanently removes from this Mac:\n", "Esto elimina de forma permanente de este Mac:\n")
            + text("• The PostForge app and its project folder\n• Your credentials (.env) and settings\n• Every Postiz post, draft, channel and uploaded file\n• The WhatsApp session and all logs\n• The PostForge Docker containers and installer files\n",
                   "• La app PostForge y su carpeta de proyecto\n• Tus credenciales (.env) y ajustes\n• Todas las publicaciones, borradores, canales y archivos de Postiz\n• La sesión de WhatsApp y todos los registros\n• Los contenedores de Docker y los archivos de instalación de PostForge\n")
            + "\n"
        if let backup = backup {
            let when = DateFormatter.localizedString(from: backup.date, dateStyle: .medium, timeStyle: .short)
            detail += text("Last backup: \(when)\n\(backup.path)", "Último respaldo: \(when)\n\(backup.path)")
        } else {
            detail += text("⚠︎ NO BACKUP WAS EXPORTED. If you continue, everything above is lost and cannot be recovered.",
                           "⚠︎ NO SE EXPORTÓ NINGÚN RESPALDO. Si continúas, todo lo anterior se pierde y no se puede recuperar.")
        }
        detail += "\n\n" + text("Posts already published on your social networks are not touched. Docker Desktop stays installed.",
                                "Las publicaciones ya publicadas en tus redes no se tocan. Docker Desktop sigue instalado.")
        let first = NSAlert()
        first.alertStyle = .critical
        first.messageText = text("Uninstall PostForge?", "¿Desinstalar PostForge?")
        first.informativeText = detail
        first.addButton(withTitle: text("Cancel", "Cancelar"))
        first.addButton(withTitle: text("Export Backup First…", "Exportar respaldo primero…"))
        first.addButton(withTitle: text("Continue…", "Continuar…"))
        NSApp.activate(ignoringOtherApps: true)
        switch first.runModal() {
        case .alertSecondButtonReturn: openBackupWindow(); return
        case .alertThirdButtonReturn: break
        default: return
        }

        let understood = NSButton(checkboxWithTitle: backup == nil
            ? text("I understand that without a backup everything is lost forever", "Entiendo que sin respaldo todo se pierde para siempre")
            : text("I understand this cannot be undone", "Entiendo que esto no se puede deshacer"), target: nil, action: nil)
        let field = NSTextField()
        field.placeholderString = "UNINSTALL"
        let stack = NSStackView(views: [understood, field])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 10
        field.widthAnchor.constraint(equalToConstant: 320).isActive = true
        stack.frame = NSRect(x: 0, y: 0, width: 320, height: 56)
        let second = NSAlert()
        second.alertStyle = .critical
        second.messageText = text("Final confirmation", "Confirmación final")
        second.informativeText = text("Type UNINSTALL to remove PostForge and all its data from this Mac.",
                                      "Escribe UNINSTALL para quitar PostForge y todos sus datos de este Mac.")
        second.accessoryView = stack
        second.addButton(withTitle: text("Cancel", "Cancelar"))
        second.addButton(withTitle: text("Uninstall Everything", "Desinstalar todo"))
        guard second.runModal() == .alertSecondButtonReturn else { return }
        guard understood.state == .on, field.stringValue.trimmingCharacters(in: .whitespaces) == "UNINSTALL" else {
            alert(text("Nothing was removed", "No se eliminó nada"),
                  text("Tick the box and type UNINSTALL exactly to confirm.", "Marca la casilla y escribe UNINSTALL exactamente para confirmar."))
            return
        }
        performUninstall()
    }

    func performUninstall() {
        uninstalling = true
        pollTimer?.invalidate()
        maintenanceTimer?.invalidate()
        [newPost?.window, backupWindow?.window, whatsappWindow?.window].forEach { $0?.orderOut(nil) }
        if sleepAssertion != 0 { IOPMAssertionRelease(sleepAssertion); sleepAssertion = 0 }
        try? SMAppService.mainApp.unregister()
        statusItem.button?.title = ""
        statusItem.button?.toolTip = "PostForge: uninstalling"

        let spinner = NSProgressIndicator()
        spinner.style = .spinning
        spinner.controlSize = .small
        spinner.startAnimation(nil)
        let label = NSTextField(labelWithString: text("Removing PostForge…", "Quitando PostForge…"))
        label.font = .systemFont(ofSize: 13, weight: .medium)
        let row = NSStackView(views: [spinner, label])
        row.spacing = 12
        row.alignment = .centerY
        row.edgeInsets = NSEdgeInsets(top: 22, left: 26, bottom: 22, right: 26)
        let panel = NSPanel(contentRect: .zero, styleMask: [.titled, .fullSizeContentView], backing: .buffered, defer: false)
        panel.titlebarAppearsTransparent = true
        panel.appearance = NSAppearance(named: .darkAqua)
        panel.backgroundColor = BackgroundView.color
        panel.contentView = row
        panel.setContentSize(row.fittingSize)
        panel.center()
        panel.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        let dir = project
        DispatchQueue.global(qos: .userInitiated).async {
            let (code, output) = runStreaming(["/bin/bash", dir + "/scripts/uninstall.sh", "--purge-data", "--yes", "--keep-app-running"],
                                              in: dir, timeout: 900) { line in
                guard line.hasPrefix("STEP ") else { return }
                let parts = line.dropFirst(5).split(separator: " ", maxSplits: 1).map(String.init)
                if parts.count == 2 { DispatchQueue.main.async { label.stringValue = parts[1] + "…" } }
            }
            DispatchQueue.main.async {
                panel.orderOut(nil)
                if code == 0 {
                    self.alert(self.text("PostForge was uninstalled", "PostForge se desinstaló"),
                               self.text("The app, its data and its Docker containers were removed. Your published posts are untouched.",
                                         "Se quitaron la app, sus datos y sus contenedores de Docker. Tus publicaciones ya publicadas siguen intactas."))
                } else {
                    self.alert(self.text("The uninstall had problems", "La desinstalación tuvo problemas"),
                               failureSummary(output))
                    self.uninstalling = false
                    self.poll()
                    self.scheduleMaintenanceCheck()
                    return
                }
                self.quittingFromMenu = true
                NSApp.terminate(nil)
            }
        }
    }

    @objc func openUpdates() {
        if let window = operationWindow, busy != nil { window.makeKeyAndOrderFront(nil); return }
        showOperation(text("Checking PostForge and Docker components…", "Revisando PostForge y los componentes de Docker…"), updateCheck: true)
        checkForUpdates(notifyIfAvailable: true)
    }

    func finishUpdateCheckIfReady() {
        guard !maintenanceCheckInFlight, !packageCheckInFlight, busy == nil,
              operationIsUpdateCheck else { return }
        let incomplete = packageCheckFailing || maintenance?.checkComplete != true
        let appUpdate = latestPackageUpdate
        let componentCount = maintenance?.components.filter { $0.kind == "docker" }.count ?? 0
        let evolution = maintenance?.evolution
        let evolutionUpdate = evolution?.updateAvailable == true
        let available = appUpdate != nil || componentCount > 0 || evolutionUpdate
        let heading = incomplete ? text("Some checks could not finish.", "No se pudieron completar algunas revisiones.") :
            available ? text("Updates are available.", "Hay actualizaciones disponibles.") :
            text("You’re up to date.", "Todo está actualizado.")
        let appStatus = packageCheckFailing ? text("PostForge: could not verify the latest release.", "PostForge: no se pudo verificar la versión más reciente.") :
            appUpdate.map { text("PostForge \($0.latestVersion) is ready to install.", "PostForge \($0.latestVersion) está listo para instalar.") } ??
            text("PostForge \(currentPostForgeVersion()): up to date.", "PostForge \(currentPostForgeVersion()): actualizado.")
        let dockerStatus = maintenance?.checkComplete != true ? text("Docker: some components could not be checked. Try again.", "Docker: no se pudieron revisar algunos componentes. Vuelve a intentar.") :
            componentCount > 0 ? text("Docker: \(componentCount) component update(s) available.", "Docker: hay \(componentCount) actualizaciones de componentes disponibles.") :
            text("Docker components: up to date.", "Componentes de Docker: actualizados.")
        let evolutionStatus = evolution.map {
            $0.updateAvailable
                ? text("Evolution API & Manager: \($0.latest) is available upstream. A compatible PostForge release is required.",
                       "API y Manager de Evolution: la versión \($0.latest) está disponible. Hace falta una versión compatible de PostForge.")
                : text("Evolution API & Manager \($0.installed): up to date.", "API y Manager de Evolution \($0.installed): actualizados.")
        } ?? text("Evolution API & Manager: release check unavailable.", "API y Manager de Evolution: no se pudo consultar la versión.")
        operationLabel?.stringValue = [heading, appStatus, dockerStatus, evolutionStatus].joined(separator: "\n\n")
        operationSpinner?.stopAnimation(nil)
        operationSpinner?.isHidden = true
        operationCloseButton?.title = text("Done", "Listo")
        operationActionButton?.isHidden = !available && !incomplete
        operationActionButton?.title = appUpdate != nil ? text("Install App Update…", "Actualizar la app…") :
            componentCount > 0 ? text("Update Components…", "Actualizar componentes…") :
            evolutionUpdate ? text("Evolution Release Notes…", "Notas de la versión de Evolution…") : text("Try Again", "Volver a intentar")
        if CommandLine.arguments.contains("--check-updates-once") {
            print(operationLabel?.stringValue ?? "")
            precondition(operationSpinner?.isHidden == true)
            if let index = CommandLine.arguments.firstIndex(of: "--snapshot-update-result"), index + 1 < CommandLine.arguments.count {
                snapshot(operationWindow!, to: CommandLine.arguments[index + 1])
            }
            exit(incomplete ? 1 : 0)
        }
    }

    @objc func performUpdateAction() {
        if latestPackageUpdate != nil { downloadLatestPackage() }
        else if maintenance?.updatesAvailable == true { applyStableUpdates() }
        else if maintenance?.evolution?.updateAvailable == true {
            if let url = URL(string: "https://github.com/evolution-foundation/evolution-api/releases/latest") {
                NSWorkspace.shared.open(url)
            }
        } else { openUpdates() }
    }

    @objc func closeOperation() { operationWindow?.orderOut(nil) }

    func retentionDays() -> Int {
        let contents = (try? String(contentsOfFile: project + "/.env", encoding: .utf8)) ?? ""
        return contents.split(separator: "\n").first { $0.hasPrefix("PM_RETENTION_DAYS=") }
            .flatMap { Int($0.dropFirst("PM_RETENTION_DAYS=".count)) }.flatMap { $0 > 0 ? $0 : nil } ?? 30
    }

    @objc func editRetention() {
        let field = NSTextField(string: String(retentionDays()))
        field.frame = NSRect(x: 0, y: 0, width: 240, height: 24)
        let dialog = NSAlert()
        dialog.messageText = text("Saved history retention", "Tiempo de conservación del historial")
        dialog.informativeText = text("Default: 30 days. This sets the cleanup age for logs and unused uploaded media. Cleanup requires a separate review and apply command; changing this value deletes nothing. Scheduled posts and the database are preserved.", "Por defecto: 30 días. Define la antigüedad para limpiar registros y archivos subidos que ya no se usan. Debes revisar y ejecutar la limpieza por separado; cambiar este valor no borra nada. Se conservan la base de datos y las publicaciones programadas.")
        dialog.accessoryView = field
        dialog.addButton(withTitle: text("Save", "Guardar"))
        dialog.addButton(withTitle: text("Cancel", "Cancelar"))
        guard dialog.runModal() == .alertFirstButtonReturn else { return }
        guard let days = Int(field.stringValue), (1...36500).contains(days) else {
            alert(text("Invalid days", "Cantidad de días inválida"), text("Enter a whole number from 1 to 36500.", "Ingresa un número entero entre 1 y 36500.")); return
        }
        updateEnvValue(key: "PM_RETENTION_DAYS", value: String(days))
    }

    func connectionLines(_ state: MachineState) -> [String] {
        let channels = state.channels ?? []
        let manual = channels.filter { !$0.renews }.sorted { ($0.expires ?? "~") < ($1.expires ?? "~") }
        var lines = manual.map { channel -> String in
            let network = uiNetwork(channel.network)
            guard let expiry = channel.expires.flatMap({ isoParser.date(from: $0) }) else {
                return text("\(network): expiry unavailable", "\(network): vencimiento no disponible")
            }
            let minutes = Int(expiry.timeIntervalSinceNow / 60)
            if minutes <= 0 { return text("\(network): reconnect now", "\(network): vuelve a conectar ahora") }
            let remaining = "\(minutes / 1440)d \((minutes % 1440) / 60)h \(minutes % 60)m"
            return text("\(network): reconnect in \(remaining)", "\(network): vuelve a conectar en \(remaining)")
        }
        if channels.contains(where: { $0.renews }) {
            lines.append(text("Automatic renewal available for other channels", "Otros canales admiten renovación automática"))
        }
        if state.channelsFromCache == true { lines.append(text("Connection dates from saved status", "Fechas de conexión del último estado guardado")) }
        return lines
    }

    @objc func showAbout() {
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 520, height: 440),
                              styleMask: [.titled, .closable], backing: .buffered, defer: false)
        window.title = text("About PostForge", "Acerca de PostForge")
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.appearance = NSAppearance(named: .darkAqua)
        window.isReleasedWhenClosed = false
        let root = NSView()
        root.wantsLayer = true
        root.layer?.backgroundColor = NSColor(calibratedWhite: 0.14, alpha: 1).cgColor
        window.contentView = root
        let icon = NSImageView(image: NSApp.applicationIconImage)
        icon.imageScaling = .scaleProportionallyUpOrDown
        icon.widthAnchor.constraint(equalToConstant: 96).isActive = true
        icon.heightAnchor.constraint(equalToConstant: 96).isActive = true
        func centered(_ value: String, size: CGFloat = 13, weight: NSFont.Weight = .regular, lines: Int = 2) -> NSTextField {
            let label = windowLabel(value, size: size, weight: weight, lines: lines, width: 460)
            label.alignment = .center
            label.translatesAutoresizingMaskIntoConstraints = false
            label.widthAnchor.constraint(equalToConstant: 460).isActive = true
            let rowCount = value.components(separatedBy: "\n").count
            label.heightAnchor.constraint(equalToConstant: CGFloat(rowCount) * ceil(size * 1.35) + 2).isActive = true
            label.setContentHuggingPriority(.required, for: .vertical)
            label.setContentCompressionResistancePriority(.required, for: .vertical)
            return label
        }
        let version = currentPostForgeVersion()
        let build = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? version
        let title = centered("PostForge", size: 24, weight: .bold, lines: 1)
        let versionLabel = centered(text("Version \(version) (\(build))", "Versión \(version) (\(build))"), lines: 2)
        let copyright = centered(text("Copyright © 2026 Isaac Mateo Sarzosa Valencia\n(isaacmateosv) and contributors.",
                                     "Copyright © 2026 Isaac Mateo Sarzosa Valencia\n(isaacmateosv) y colaboradores."))
        let license = centered(text("Free software (GPL-3.0-or-later).\nProvided without warranty.",
                                   "Software libre (GPL-3.0-or-later).\nSe distribuye sin garantía."))
        let independence = centered(text("Independent publishing companion.\nNot affiliated with or endorsed by Postiz, Meta,\nTikTok, Google or the other integrated services.",
                                        "Herramienta independiente de publicación.\nSin afiliación ni respaldo de Postiz, Meta, TikTok,\nGoogle ni los demás servicios integrados."), size: 12, lines: 3)
        independence.textColor = .secondaryLabelColor
        let flow = NSButton(title: text("How It Works…", "Cómo funciona…"), target: self, action: #selector(showPublishingFlow))
        let legal = NSButton(title: text("License & Notices…", "Licencia y avisos…"), target: self, action: #selector(showLicense))
        for button in [flow, legal] { button.bezelStyle = .rounded }
        let actions = NSStackView(views: [flow, legal]); actions.spacing = 12
        let stack = NSStackView(views: [icon, title, versionLabel, copyright, license, independence, actions])
        stack.orientation = .vertical; stack.spacing = 12; stack.alignment = .centerX
        stack.translatesAutoresizingMaskIntoConstraints = false
        root.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: root.leadingAnchor, constant: 30),
            stack.trailingAnchor.constraint(equalTo: root.trailingAnchor, constant: -30),
            stack.topAnchor.constraint(equalTo: root.topAnchor, constant: 30),
            stack.bottomAnchor.constraint(lessThanOrEqualTo: root.bottomAnchor, constant: -22),
        ])
        aboutWindow?.close(); aboutWindow = window
        window.center(); window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
    }

    @objc func showUserGuide() {
        if guideWindow == nil { guideWindow = UserGuideWindow() }
        guideWindow?.refresh(spanish: spanish)
        guideWindow?.window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc func showLicense() {
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 680, height: 560),
                              styleMask: [.titled, .closable, .resizable], backing: .buffered, defer: false)
        window.title = text("PostForge — License & Notices", "PostForge — Licencia y avisos")
        window.appearance = NSAppearance(named: .darkAqua)
        window.isReleasedWhenClosed = false
        let scroll = NSScrollView(frame: window.contentView!.bounds)
        scroll.autoresizingMask = [.width, .height]
        scroll.hasVerticalScroller = true
        let content = NSTextView(frame: scroll.bounds)
        content.isEditable = false; content.isRichText = false
        content.font = .monospacedSystemFont(ofSize: 12, weight: .regular)
        content.textContainerInset = NSSize(width: 20, height: 20)
        content.isVerticallyResizable = true
        content.autoresizingMask = [.width]
        content.textContainer?.widthTracksTextView = true
        content.string = ["COPYRIGHT", "LICENSE", "NOTICE"].map { name in
            guard let path = Bundle.main.path(forResource: name, ofType: "txt"),
                  let text = try? String(contentsOfFile: path, encoding: .utf8) else { return "\(name): unavailable" }
            return text
        }.joined(separator: "\n\n────────────────────────────────────────\n\n")
        scroll.documentView = content
        window.contentView?.addSubview(scroll)
        licenseWindow?.close(); licenseWindow = window
        window.center(); window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
    }

    @objc func showPublishingFlow() {
        let window = makeSecondaryWindow(title: text("How PostForge works", "Cómo funciona PostForge"), height: 440)
        let root = BackgroundView()
        let title = windowLabel("PostForge", size: 24, weight: .bold)
        let stages = [text("1 · Media + your idea\nMac app or WhatsApp self-chat", "1 · Archivos + tu idea\nApp para Mac o chat contigo en WhatsApp"),
                      text("2 · Local AI → preview → your approval", "2 · IA local → vista previa → tu aprobación"),
                      text("3 · Postiz drafts → review & schedule", "3 · Borradores en Postiz → revisión y programación"),
                      text("4 · Temporal → connected social channels", "4 · Temporal → redes sociales conectadas")]
        var views: [NSView] = [title]
        for (index, stage) in stages.enumerated() {
            if index > 0 { views.append(windowLabel("↓", size: 16, color: .systemTeal)) }
            let label = windowLabel(stage, size: 14, lines: 2, width: 460)
            let panel = Panel(label, insets: NSEdgeInsets(top: 12, left: 16, bottom: 12, right: 16))
            views.append(panel)
        }
        views.append(windowLabel(text("History: \(retentionDays()) days · configurable in Settings & Tools\nThe tray monitors health, connections and updates.", "Historial: \(retentionDays()) días · configurable en Ajustes y herramientas\nLa barra muestra el estado, las conexiones y las actualizaciones."), size: 12, color: .secondaryLabelColor, lines: 3, width: 490))
        let main = layoutSections(views, in: root, top: 24, spacing: 8)
        main.alignment = .centerX
        window.contentView = root
        flowWindow?.close(); flowWindow = window
        window.center(); window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
    }

    func showOperation(_ title: String, updateCheck: Bool = false) {
        operationStage = nil
        operationIsUpdateCheck = updateCheck
        if operationWindow == nil {
            let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 480, height: 260), styleMask: [.titled, .closable], backing: .buffered, defer: false)
            window.isReleasedWhenClosed = false
            window.appearance = NSAppearance(named: .darkAqua)
            window.contentView = BackgroundView()
            let label = windowLabel(title, lines: 10, width: 420)
            label.frame = NSRect(x: 30, y: 95, width: 420, height: 155)
            let spinner = NSProgressIndicator(frame: NSRect(x: 30, y: 70, width: 420, height: 16))
            spinner.style = .bar; spinner.isIndeterminate = true
            let close = NSButton(title: text("Close", "Cerrar"), target: self, action: #selector(closeOperation))
            close.bezelStyle = .rounded; close.frame = NSRect(x: 350, y: 20, width: 100, height: 32)
            close.keyEquivalent = "\r"
            let action = NSButton(title: "", target: self, action: #selector(performUpdateAction))
            action.bezelStyle = .rounded; action.frame = NSRect(x: 30, y: 20, width: 240, height: 32)
            window.contentView?.addSubview(label); window.contentView?.addSubview(spinner)
            window.contentView?.addSubview(close); window.contentView?.addSubview(action)
            operationCloseButton = close; operationActionButton = action
            operationWindow = window; operationLabel = label; operationSpinner = spinner
            window.center()
        }
        operationWindow?.title = text("PostForge Updates & Progress", "PostForge: actualizaciones y progreso")
        operationLabel?.stringValue = title
        operationSpinner?.isHidden = false
        operationSpinner?.startAnimation(nil)
        operationCloseButton?.title = text("Close", "Cerrar")
        operationActionButton?.isHidden = true
        operationWindow?.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
    }

    func finishOperation(_ success: Bool) {
        operationStage = nil
        operationSpinner?.stopAnimation(nil)
        operationSpinner?.isHidden = true
        operationCloseButton?.title = text("Done", "Listo")
        operationLabel?.stringValue = success ? text("Completed. PostForge status is refreshing.", "Listo. Actualizando el estado de PostForge.") : text("Could not complete. Open the log for details and recovery instructions.", "No se pudo completar. Abre el registro para ver los detalles y los pasos de recuperación.")
    }

    func localizedOperation(_ line: String) -> String {
        guard spanish else { return line }
        let stages = ["1/2": "Reiniciando Postiz y ngrok", "2/2": "Verificando el túnel y el programador", "1/5": "Preparando el respaldo", "2/5": "Descargando componentes", "3/5": "Reiniciando servicios", "4/5": "Verificando el funcionamiento", "5/5": "Actualización completada"]
        let number = line.split(separator: " ").dropFirst().first.map(String.init) ?? ""
        return stages[number].map { "\(number) · \($0)…" } ?? text("Working…", "Procesando…")
    }

    func refreshLocalizedWindows() {
        guideWindow?.refresh(spanish: spanish)
        busy = busy.map(localizedUI)
        func walk(_ view: NSView) {
            if let label = view as? NSTextField {
                if !label.isEditable { label.stringValue = localizedUI(label.stringValue) }
                if let placeholder = label.placeholderString { label.placeholderString = localizedUI(placeholder) }
            }
            if let button = view as? NSButton, !(button is NSPopUpButton) {
                button.title = localizedUI(button.title)
            }
            if let tip = view.toolTip { view.toolTip = localizedUI(tip) }
            for child in view.subviews { walk(child) }
        }
        for window in [newPost?.window, backupWindow?.window, whatsappWindow?.window, operationWindow].compactMap({ $0 }) {
            window.title = localizedUI(window.title)
            if let content = window.contentView { walk(content) }
        }
        if let stage = operationStage { operationLabel?.stringValue = localizedOperation(stage) }
        if operationIsUpdateCheck { finishUpdateCheckIfReady() }
        updateButton()
        newPost?.refreshState(state)
        newPost?.refreshPlacementLabels()
        newPost?.refreshStepLabels()
        newPost?.updateCaptionVersions()
        if let report = newPost?.lastReport { newPost?.report(report.0, dryRun: report.1, exitCode: report.2) }
        if let state = state { whatsappWindow?.refresh(state) }
        if aboutWindow?.isVisible == true { showAbout() }
        if flowWindow?.isVisible == true { showPublishingFlow() }
        if licenseWindow?.isVisible == true { showLicense() }
    }

    func runLifecycle(_ args: [String], busyText: String, showProgress: Bool = true, done: @escaping (Int32, String) -> Void) {
        busy = localizedUI(busyText)
        if showProgress { showOperation(localizedUI(busyText)) }
        updateButton()
        updateSleepAssertion()
        scheduleNextPoll()
        let dir = project
        DispatchQueue.global(qos: .userInitiated).async {
            let (code, output) = runStreaming(["/bin/bash", dir + "/postforge.sh"] + args, in: dir, timeout: 900) { line in
                if showProgress, line.hasPrefix("STEP ") {
                    DispatchQueue.main.async { self.operationStage = line; self.operationLabel?.stringValue = self.localizedOperation(line) }
                }
            }
            DispatchQueue.main.async {
                self.log("postforge.sh \(args.joined(separator: " ")) -> exit \(code)\n\(output)")
                self.busy = nil
                if showProgress { self.finishOperation(code == 0) }
                done(code, output)
                self.poll()
            }
        }
    }

    @objc func showStatusMenu() {
        guard let menu = statusItem.menu else { return }
        menuNeedsUpdate(menu)
        guard let button = statusItem.button else { return }
        let point = NSPoint(x: button.bounds.midX, y: button.bounds.midY)
        menu.popUp(positioning: nil, at: point, in: button)
    }

    @objc func toggleMainWindow() {
        if newPost == nil { newPost = NewPostWindow(project: project) }
        newPost?.refreshState(state)
        if newPost?.window.isVisible == true {
            newPost?.window.orderOut(nil)
        } else {
            newPost?.show()
        }
    }

    /// Drop media, say where and when: drafts land on the Postiz calendar (scripts/plan-post.sh).
    @objc func openNewPost() {
        if newPost == nil { newPost = NewPostWindow(project: project) }
        newPost?.refreshState(state)
        newPost?.show()
    }

    @objc func openDraftOption(_ sender: NSMenuItem) {
        openNewPost()
        guard let composer = newPost else { return }
        switch sender.tag {
        case 1...3:
            composer.placementMenu.selectItem(at: sender.tag)
            composer.draftOptionsChanged()
        case 4:
            composer.chooseCoverImage()
        case 5:
            composer.editCover()
        default:
            break
        }
    }

    func pendingStatusApprovals() -> [[String: Any]] {
        guard let data = FileManager.default.contents(atPath: project + "/run/whatsapp-pending.json"),
              let items = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]] else { return [] }
        return items.filter { $0["status"] as? String == "pending" && $0["approved"] as? Bool != true }
    }

    @objc func approveStatusFromMenu(_ sender: NSMenuItem) {
        if let id = sender.representedObject as? String { approveStatus(id) }
    }

    func approveStatus(_ id: String, onSuccess: (() -> Void)? = nil) {
        guard let status = pendingStatusApprovals().first(where: { $0["id"] as? String == id }) else {
            alert(text("Status unavailable", "Estado no disponible"),
                  text("This Status has already been approved or is no longer in the queue.",
                       "Este Estado ya fue aprobado o salió de la cola."))
            return
        }
        let when = (status["when"] as? String).map { shortDate(iso: $0) } ?? ""
        let caption = String((status["caption"] as? String ?? "").prefix(120))
        let detail = [when, caption, text("If the scheduled time has passed, it can send as soon as WhatsApp is available.",
                                          "Si la hora programada ya pasó, el Estado puede enviarse en cuanto WhatsApp esté disponible.")].joined(separator: "\n\n")
        guard ask(text("Approve this WhatsApp Status?", "¿Aprobar este Estado de WhatsApp?"), detail,
                  safe: text("Cancel", "Cancelar"), risky: text("Approve Status", "Aprobar Estado")) else { return }
        let dir = project
        windowWork += 1
        DispatchQueue.global(qos: .userInitiated).async {
            let (code, output) = runCommand(["/usr/bin/python3", dir + "/scripts/lib/wa_inbox.py",
                                             "--send-status-approval", id], in: dir, timeout: 60)
            DispatchQueue.main.async {
                self.windowWork -= 1
                if code == 0 {
                    onSuccess?()
                    self.alert(self.text("Approval sent", "Aprobación enviada"),
                               self.text("Check your WhatsApp self-chat for confirmation.", "Revisa tu chat contigo en WhatsApp para confirmar."))
                } else {
                    self.log("Status approval failed: \(output)")
                    self.alert(self.text("Couldn’t send the approval", "No se pudo enviar la aprobación"),
                               self.text("Check that PostForge is on and WhatsApp is linked.", "Verifica que PostForge esté encendido y WhatsApp esté vinculado."))
                }
                self.poll()
            }
        }
    }

    @objc func openPostiz() {
        if let url = URL(string: state?.postizUrl ?? "http://localhost:4200") { NSWorkspace.shared.open(url) }
    }

    /// The steps for one channel, then Postiz (turning the stack on first if needed) or the guide.
    /// `postforge.sh channels --reconnect` is the same walk-through in Terminal.
    @objc func reconnectChannel(_ sender: NSMenuItem) {
        guard let key = sender.representedObject as? String,
              let alert = state?.channelAlerts?.first(where: { $0.key == key }) else { return }
        let up = state?.isUp ?? false
        let reconnect = text("Open Postiz → Channels, select the affected channel and reconnect it. Sign in with the account that owns that channel, keep the requested permissions and select the same account or Page. Then return to PostForge and check its status.", "Abre Postiz → Canales, selecciona el canal afectado y vuelve a conectarlo. Inicia sesión con la cuenta que administra ese canal, conserva los permisos solicitados y selecciona la misma cuenta o página. Luego vuelve a PostForge y revisa el estado.")
        let steps = spanish ? (up ? [reconnect] : ["Enciende PostForge.", reconnect]) : (up ? Array(alert.steps.dropFirst()) : alert.steps)
        let dialog = NSAlert()
        dialog.messageText = alert.headline
        dialog.informativeText = "\(alert.channel)\n\n"
            + steps.enumerated().map { "\($0.offset + 1). \($0.element)" }.joined(separator: "\n")
        dialog.addButton(withTitle: up ? text("Open Postiz", "Abrir Postiz") : text("Turn On and Open Postiz", "Encender y abrir Postiz"))
        dialog.addButton(withTitle: text("Open Guide", "Abrir guía"))
        dialog.addButton(withTitle: text("Later", "Más tarde"))
        NSApp.activate(ignoringOtherApps: true)
        switch dialog.runModal() {
        case .alertFirstButtonReturn:
            if up {
                openPostizChannels()
            } else {
                openPostizWhenUp = true
                turnOn()
            }
        case .alertSecondButtonReturn:
            NSWorkspace.shared.open(URL(fileURLWithPath: project + "/" + alert.guide))
        default:
            break
        }
    }

    func openPostizChannels() {
        if let url = URL(string: (state?.postizUrl ?? "http://localhost:4200") + "/launches") { NSWorkspace.shared.open(url) }
    }

    @objc func openEvolution() {
        NSWorkspace.shared.open(URL(string: "http://localhost:8080/manager")!)
    }

    @objc func openLog() {
        let path = logPath()
        if !FileManager.default.fileExists(atPath: path) { log("Log created.") }
        NSWorkspace.shared.open(URL(fileURLWithPath: path))
    }

    @objc func quitApp() {
        quittingFromMenu = true
        NSApp.terminate(nil)
    }

    // MARK: Shutdown / log out with work waiting

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if quittingFromMenu { return .terminateNow }
        let reasons: Set<UInt32> = Set(["shut", "rest", "rlgo", "logo", "rrst", "rsdn"].map(fourCC))
        guard let event = NSAppleEventManager.shared().currentAppleEvent,
              let why = event.attributeDescriptor(forKeyword: fourCC("why?")),
              reasons.contains(why.typeCodeValue) || reasons.contains(why.enumCodeValue),
              let st = state, st.isUp, st.pending.total > 0 else { return .terminateNow }
        let detail = text("\(nextPostLine(st)) If the Mac shuts down now, scheduled posts go out late, as soon as PostForge is on again.", "\(nextPostLine(st)) Si apagas la Mac ahora, las publicaciones se enviarán con retraso cuando PostForge vuelva a encenderse.")
        let proceed = ask(text("PostForge has \(plural(st.pending.total, "item")) waiting", "PostForge tiene \(st.pending.total) envíos pendientes"), detail,
                          safe: "Cancel Shutdown", risky: "Shut Down Anyway")
        return proceed ? .terminateNow : .terminateCancel
    }

    // MARK: Dialogs and log

    /// Warning dialog whose default (Return) button is the safe choice. True if the user picks `risky`.
    func ask(_ title: String, _ text: String, safe: String, risky: String) -> Bool {
        let alert = NSAlert()
        alert.alertStyle = .warning
        alert.messageText = localizedUI(title)
        alert.informativeText = localizedUI(text)
        alert.addButton(withTitle: localizedUI(safe))
        alert.addButton(withTitle: localizedUI(risky))
        NSApp.activate(ignoringOtherApps: true)
        return alert.runModal() == .alertSecondButtonReturn
    }

    func alert(_ title: String, _ text: String) {
        let alert = NSAlert()
        alert.messageText = localizedUI(title)
        alert.informativeText = localizedUI(text)
        NSApp.activate(ignoringOtherApps: true)
        alert.runModal()
    }

    func logPath() -> String { project + "/logs/tray.log" }

    func log(_ text: String) {
        if uninstalling { return }  // the project folder is being removed
        let stamp = ISO8601DateFormatter().string(from: Date())
        let entry = Data("[\(stamp)] \(text)\n".utf8)
        let path = logPath()
        try? FileManager.default.createDirectory(atPath: project + "/logs", withIntermediateDirectories: true)
        if let attributes = try? FileManager.default.attributesOfItem(atPath: path),
           let size = attributes[.size] as? NSNumber, size.intValue >= 10 * 1024 * 1024 {
            for index in stride(from: 4, through: 1, by: -1) {
                let old = "\(path).\(index)"
                let next = "\(path).\(index + 1)"
                try? FileManager.default.removeItem(atPath: next)
                try? FileManager.default.moveItem(atPath: old, toPath: next)
            }
            try? FileManager.default.moveItem(atPath: path, toPath: "\(path).1")
        }
        if let handle = FileHandle(forWritingAtPath: path) {
            handle.seekToEndOfFile()
            handle.write(entry)
            handle.closeFile()
        } else {
            FileManager.default.createFile(atPath: path, contents: entry)
        }
    }
}

// MARK: - New post window

/// The window's blue-black backdrop.
final class BackgroundView: NSView {
    static let color = NSColor(calibratedRed: 0.075, green: 0.105, blue: 0.165, alpha: 1)

    override func draw(_ dirtyRect: NSRect) {
        BackgroundView.color.setFill()
        dirtyRect.fill()
    }
}

/// A softly raised rounded container that pins its content inside the given insets.
final class Panel: NSView {
    enum Style { case card, input, output }

    init(_ content: NSView, insets: NSEdgeInsets, style: Style = .card) {
        super.init(frame: .zero)
        wantsLayer = true
        layer?.cornerRadius = 12
        layer?.masksToBounds = true
        switch style {
        case .card:
            layer?.borderWidth = 1
            layer?.borderColor = NSColor(white: 1, alpha: 0.10).cgColor
            layer?.backgroundColor = NSColor(white: 1, alpha: 0.05).cgColor
        case .input:  // lighter and outlined: it looks like something you type into
            layer?.borderWidth = 1
            layer?.borderColor = NSColor(white: 1, alpha: 0.18).cgColor
            layer?.backgroundColor = NSColor(white: 1, alpha: 0.09).cgColor
        case .output:  // darker and borderless: it looks like a result you read
            layer?.backgroundColor = NSColor(white: 0, alpha: 0.22).cgColor
        }
        content.translatesAutoresizingMaskIntoConstraints = false
        addSubview(content)
        NSLayoutConstraint.activate([
            content.leadingAnchor.constraint(equalTo: leadingAnchor, constant: insets.left),
            content.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -insets.right),
            content.topAnchor.constraint(equalTo: topAnchor, constant: insets.top),
            content.bottomAnchor.constraint(equalTo: bottomAnchor, constant: -insets.bottom),
        ])
    }

    required init?(coder: NSCoder) { nil }
}

/// A label that lets clicks through, used as the text box's placeholder.
final class PassthroughLabel: NSTextField {
    override func hitTest(_ point: NSPoint) -> NSView? { nil }
}

/// Takes photos and videos dragged in from Finder (or exported from Photos).
final class DropView: NSView {
    var onFiles: (([URL]) -> Void)?

    override init(frame: NSRect) {
        super.init(frame: frame)
        registerForDraggedTypes([.fileURL])
        wantsLayer = true
        layer?.cornerRadius = 12
        layer?.borderWidth = 1
        layer?.backgroundColor = NSColor(white: 1, alpha: 0.03).cgColor
        highlight(false)
    }

    required init?(coder: NSCoder) { nil }

    func highlight(_ on: Bool) {
        layer?.borderColor = (on ? NSColor.controlAccentColor : NSColor.separatorColor).cgColor
    }

    override func draggingEntered(_ sender: NSDraggingInfo) -> NSDragOperation {
        highlight(true)
        return .copy
    }

    override func draggingExited(_ sender: NSDraggingInfo?) { highlight(false) }

    override func performDragOperation(_ sender: NSDraggingInfo) -> Bool {
        highlight(false)
        let urls = sender.draggingPasteboard.readObjects(
            forClasses: [NSURL.self], options: [.urlReadingFileURLsOnly: true]) as? [URL] ?? []
        onFiles?(urls)
        return !urls.isEmpty
    }
}

/// Read the same Markdown files shipped in the repository without a web connection.
final class UserGuideWindow: NSObject {
    let window: NSWindow
    let topics = NSSegmentedControl(labels: ["Quick Start", "Technical"], trackingMode: .selectOne,
                                    target: nil, action: nil)
    let article = NSTextView()
    let shortcuts = NSButton(title: "", target: nil, action: nil)
    private var spanish = false

    override init() {
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 760, height: 630),
                          styleMask: [.titled, .closable, .resizable], backing: .buffered, defer: false)
        super.init()
        window.isReleasedWhenClosed = false
        window.contentMinSize = NSSize(width: 520, height: 400)
        window.center()
        topics.target = self
        topics.action = #selector(selectTopic)
        topics.selectedSegment = 0

        let scroll = NSScrollView()
        scroll.hasVerticalScroller = true
        scroll.autohidesScrollers = true
        article.isEditable = false
        article.isVerticallyResizable = true
        article.autoresizingMask = [.width]
        article.textContainer?.widthTracksTextView = true
        article.textContainerInset = NSSize(width: 26, height: 18)
        scroll.documentView = article

        let root = NSView()
        let icon = NSImageView(image: NSApp.applicationIconImage)
        icon.imageScaling = .scaleProportionallyDown
        shortcuts.target = self
        shortcuts.action = #selector(showShortcuts)
        let header = NSStackView(views: [icon, topics, shortcuts])
        header.spacing = 12
        header.alignment = .centerY
        header.translatesAutoresizingMaskIntoConstraints = false
        scroll.translatesAutoresizingMaskIntoConstraints = false
        root.addSubview(header)
        root.addSubview(scroll)
        NSLayoutConstraint.activate([
            icon.widthAnchor.constraint(equalToConstant: 32),
            icon.heightAnchor.constraint(equalToConstant: 32),
            header.topAnchor.constraint(equalTo: root.topAnchor, constant: 12),
            header.leadingAnchor.constraint(equalTo: root.leadingAnchor, constant: 24),
            scroll.topAnchor.constraint(equalTo: header.bottomAnchor, constant: 10),
            scroll.leadingAnchor.constraint(equalTo: root.leadingAnchor),
            scroll.trailingAnchor.constraint(equalTo: root.trailingAnchor),
            scroll.bottomAnchor.constraint(equalTo: root.bottomAnchor),
        ])
        window.contentView = root
    }

    func refresh(spanish: Bool) {
        self.spanish = spanish
        window.title = spanish ? "Ayuda de PostForge" : "PostForge Help"
        topics.setLabel(spanish ? "Inicio rápido" : "Quick Start", forSegment: 0)
        topics.setLabel(spanish ? "Técnica" : "Technical", forSegment: 1)
        shortcuts.title = spanish ? "Atajos de Siri…" : "Siri Shortcuts…"
        selectTopic()
    }

    @objc func showShortcuts() {
        if let resources = Bundle.main.resourceURL {
            NSWorkspace.shared.open(resources.appendingPathComponent("Shortcuts", isDirectory: true))
        }
    }

    @objc func selectTopic() {
        let name = (topics.selectedSegment == 1 ? "technical" : "quick") + (spanish ? "-es" : "-en")
        guard let url = Bundle.main.url(forResource: name, withExtension: "md", subdirectory: "Help"),
              let markdown = try? String(contentsOf: url, encoding: .utf8) else {
            article.string = spanish ? "La guía no está disponible." : "The guide is unavailable."
            return
        }
        article.textStorage?.setAttributedString(render(markdown))
        article.scrollRangeToVisible(NSRange(location: 0, length: 0))
    }

    private func render(_ markdown: String) -> NSAttributedString {
        let rendered = NSMutableAttributedString(string: "")
        var code = false
        for line in markdown.components(separatedBy: .newlines) {
            if line.hasPrefix("```") { code.toggle(); continue }
            let major = !code && line.hasPrefix("# ")
            let minor = !code && line.hasPrefix("## ")
            let body = major ? String(line.dropFirst(2)) : minor ? String(line.dropFirst(3)) :
                !code && line.hasPrefix("- ") ? "• " + String(line.dropFirst(2)) : line
            let style = NSMutableParagraphStyle()
            style.lineSpacing = code ? 2 : 3
            style.paragraphSpacing = major ? 12 : minor ? 6 : 1
            let pieces = code ? [body] : body.components(separatedBy: "**")
            for (index, piece) in pieces.enumerated() {
                let font: NSFont = code ? .monospacedSystemFont(ofSize: 12, weight: .regular) :
                    .systemFont(ofSize: major ? 28 : minor ? 18 : 14,
                                weight: major || minor || index % 2 == 1 ? .semibold : .regular)
                rendered.append(NSAttributedString(string: piece + (index == pieces.count - 1 ? "\n" : ""),
                    attributes: [.font: font, .foregroundColor: code ? NSColor.systemTeal : NSColor.labelColor,
                                 .paragraphStyle: style]))
            }
        }
        return rendered
    }
}

/// "New Post…": files plus one sentence (typed or dictated) become one Postiz draft per network at
/// that time. Preview shows the plan; Create Drafts makes them. Nothing publishes until approved in
/// Postiz (HITL). The work is done by scripts/plan-post.sh --json.
private final class ComposerSteps: NSTextField {
    private let accent = NSColor(srgbRed: 0.55, green: 0.79, blue: 1, alpha: 1)
    private var text = ""
    private var timer: Timer?
    private var interactionMonitor: Any?
    var isAnimating: Bool { timer != nil }

    func updateText(_ text: String) {
        self.text = text
        setAccessibilityLabel(text)
        render()
    }

    func startSweep(in window: NSWindow) {
        stopSweep()
        guard !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion else { return }
        let start = ProcessInfo.processInfo.systemUptime
        interactionMonitor = NSEvent.addLocalMonitorForEvents(
            matching: [.leftMouseDown, .rightMouseDown, .otherMouseDown, .keyDown, .scrollWheel]
        ) { [weak self, weak window] event in
            if event.window === window { self?.stopSweep() }
            return event
        }
        timer = Timer.scheduledTimer(withTimeInterval: 1.0 / 24, repeats: true) { [weak self, weak window] _ in
            guard let self else { return }
            let progress = (ProcessInfo.processInfo.systemUptime - start) / 1.8
            guard progress < 1, window?.isVisible == true else {
                self.stopSweep()
                return
            }
            self.render(progress: progress)
        }
    }

    func stopSweep() {
        timer?.invalidate()
        timer = nil
        if let interactionMonitor {
            NSEvent.removeMonitor(interactionMonitor)
            self.interactionMonitor = nil
        }
        render()
    }

    deinit {
        timer?.invalidate()
        if let interactionMonitor { NSEvent.removeMonitor(interactionMonitor) }
    }

    private func render(progress: Double? = nil) {
        let style = NSMutableParagraphStyle()
        style.lineBreakMode = .byWordWrapping
        style.alignment = .center
        let line = NSMutableAttributedString(string: text, attributes: [
            .font: NSFont.systemFont(ofSize: 12, weight: .semibold),
            .foregroundColor: accent, .paragraphStyle: style,
        ])
        if let progress {
            let width = 10.0
            let center = progress * (Double(line.length) + 2 * width) - width
            let start = max(0, Int(center - width))
            let end = min(line.length, Int(center + width) + 1)
            if start < end {
                for index in start..<end {
                    let strength = max(0, 1 - abs(Double(index) - center) / width)
                    if let color = accent.blended(withFraction: strength, of: .white) {
                        line.addAttribute(.foregroundColor, value: color, range: NSRange(location: index, length: 1))
                    }
                }
            }
        }
        attributedStringValue = line
    }
}

private final class MixingIndicator: NSView {
    private var timer: Timer?
    private var phase = 0.0

    override var intrinsicContentSize: NSSize { NSSize(width: 28, height: 25) }

    func start() {
        isHidden = false
        guard timer == nil, !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion else { return }
        timer = Timer.scheduledTimer(withTimeInterval: 0.08, repeats: true) { [weak self] _ in
            guard let self else { return }
            self.phase += 0.55
            self.needsDisplay = true
        }
    }

    func stop() {
        timer?.invalidate()
        timer = nil
        isHidden = true
    }

    override func draw(_ dirtyRect: NSRect) {
        let whisk = NSBezierPath()
        let x = 14 + sin(phase) * 4
        whisk.move(to: NSPoint(x: x + 5, y: 22))
        whisk.line(to: NSPoint(x: x, y: 12))
        whisk.curve(to: NSPoint(x: x - 3, y: 8),
                    controlPoint1: NSPoint(x: x + 4, y: 5), controlPoint2: NSPoint(x: x - 6, y: 4))
        whisk.line(to: NSPoint(x: x, y: 12))
        NSColor.systemOrange.setStroke()
        whisk.lineWidth = 1.7
        whisk.lineCapStyle = .round
        whisk.stroke()

        let bowl = NSBezierPath()
        bowl.move(to: NSPoint(x: 3, y: 12))
        bowl.line(to: NSPoint(x: 25, y: 12))
        bowl.curve(to: NSPoint(x: 3, y: 12),
                   controlPoint1: NSPoint(x: 23, y: 0), controlPoint2: NSPoint(x: 5, y: 0))
        NSColor.labelColor.setStroke()
        bowl.lineWidth = 1.6
        bowl.lineCapStyle = .round
        bowl.stroke()

        let sparks = NSBezierPath()
        for (index, center) in [NSPoint(x: 6, y: 19), NSPoint(x: 24, y: 21)].enumerated() {
            let radius = 1.4 + (1 + sin(phase + Double(index) * 2)) * 0.55
            sparks.move(to: NSPoint(x: center.x - radius, y: center.y))
            sparks.line(to: NSPoint(x: center.x + radius, y: center.y))
            sparks.move(to: NSPoint(x: center.x, y: center.y - radius))
            sparks.line(to: NSPoint(x: center.x, y: center.y + radius))
        }
        NSColor.systemYellow.setStroke()
        sparks.lineWidth = 1
        sparks.lineCapStyle = .round
        sparks.stroke()
    }
}

final class NewPostWindow: NSObject, NSTextViewDelegate, NSTextFieldDelegate {
    let project: String
    let window: NSWindow
    let files = NSTextField(labelWithString: "")
    let placeholder = PassthroughLabel(wrappingLabelWithString: "")
    let emptyState = NSStackView()
    let status = NSTextField(labelWithString: "")
    let turnOnButton = NSButton(title: "", target: nil, action: nil)
    let connections = NSTextField(wrappingLabelWithString: "")
    let instruction = NSTextView()
    private let steps = ComposerSteps()
    let result = NSTextView()
    let preview = NSButton(title: "Preview", target: nil, action: nil)
    let create = NSButton(title: "Create Drafts", target: nil, action: nil)
    let calendar = NSButton(title: "Open Postiz Calendar", target: nil, action: nil)
    let statusApproval = NSButton(title: "", target: nil, action: nil)
    var pendingStatusID: String?
    let updatesButton = NSButton(title: "", target: nil, action: nil)
    let spinner = NSProgressIndicator()
    var statsQueue = NSTextField(labelWithString: "0")
    var statsDrafts = NSTextField(labelWithString: "0")
    var statsNext = NSTextField(labelWithString: "")
    var media: [URL] = []
    let placementMenu = NSPopUpButton()
    let coverSecond = NSTextField()
    let coverFile = NSTextField(labelWithString: "")
    let chooseCover = NSButton()
    let clearCover = NSButton()
    let changeCover = NSButton()
    private let mixer = MixingIndicator()
    var coverLocked = false
    var coverAvailable = false
    var acceptedNoCover = false
    var coverURL: URL?
    var inputRevision = 0
    var ideaHeight: NSLayoutConstraint?
    var planExpanded = false
    var reviewURL: URL?
    var previewed = false
    var reviewedCaption: String?
    var reviewedThreadsCaption: String?
    var reviewedFinalTag: String?
    var reviewedYouTubeTitle: String?
    let captionVersions = NSPopUpButton()
    let alternateCaption = NSButton()
    var savedVersions: [(instruction: String, output: String)] = []
    var selectedVersion: Int?
    var canGenerateVariant = false
    var working = false
    var lastReport: (String, Bool, Int32)?

    init(project: String) {
        self.project = project
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 560, height: 790),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                          backing: .buffered, defer: false)
        super.init()
        window.title = "PostForge"
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.appearance = NSAppearance(named: .darkAqua)  // one look: the controls are drawn for dark
        window.backgroundColor = BackgroundView.color
        window.isMovableByWindowBackground = true
        window.contentMinSize = NSSize(width: 520, height: 730)
        window.isReleasedWhenClosed = false
        build()
        refreshState(nil)
        window.center()
    }

    func show() {
        let opening = !window.isVisible
        window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(instruction)
        NSApp.activate(ignoringOtherApps: true)
        if opening { steps.startSweep(in: window) }
    }

    func refreshStepLabels() {
        steps.updateText(t("1. Bake your idea  →  2. Review the plan  →  3. Create drafts",
                           "1. Hornea la idea  →  2. Revisa el plan  →  3. Crea los borradores"))
    }

    func t(_ english: String, _ spanish: String) -> String {
        (NSApp.delegate as? AppDelegate)?.text(english, spanish) ?? english
    }

    func refreshUpdates(available: Bool) {
        updatesButton.title = available ? t("Updates Available…", "Actualizaciones disponibles…") : t("Updates", "Actualizaciones")
        updatesButton.contentTintColor = available ? .systemOrange : nil
    }

    func refreshState(_ state: MachineState?) {
        let queued = state?.pending.total ?? 0
        let drafts = state?.drafts ?? 0
        let next = state?.pending.next
        statsQueue.stringValue = String(queued)
        statsDrafts.stringValue = String(drafts)
        statsNext.stringValue = next.map { "\(shortDate(iso: $0.at)) · \($0.provider)" }
            ?? t("Nothing scheduled", "Nada programado")
        statsQueue.textColor = queued > 0 ? .systemOrange : .secondaryLabelColor
        statsDrafts.textColor = drafts > 0 ? .systemBlue : .secondaryLabelColor
        statsNext.textColor = next != nil ? .systemGreen : .secondaryLabelColor

        var label = t("Checking…", "Comprobando…")
        var tone = NSColor.secondaryLabelColor
        switch state?.state {
        case "on": (label, tone) = (t("Running", "En marcha"), .systemGreen)
        case "off": (label, tone) = (state?.idleStopped == true
            ? t("Idle · services off", "Inactivo · servicios apagados") : t("Off", "Apagado"), .secondaryLabelColor)
        case "partial": (label, tone) = (t("Needs attention", "Requiere atención"), .systemOrange)
        case "starting": (label, tone) = (t("Starting…", "Iniciando…"), .systemOrange)
        case "stopping": (label, tone) = (t("Stopping…", "Apagando…"), .systemOrange)
        default: break
        }
        let delegate = NSApp.delegate as? AppDelegate
        let connection = state.map { delegate?.connectionLines($0).prefix(2).joined(separator: "\n") ?? "" } ?? ""
        status.stringValue = "● " + (delegate?.busy ?? label)
        connections.stringValue = connection
        connections.toolTip = state.map { delegate?.connectionLines($0).joined(separator: "\n") ?? "" }
        connections.isHidden = connection.isEmpty
        status.textColor = tone
        turnOnButton.isHidden = state?.state != "off" && state?.state != "partial"
    }

    func caption(_ text: String) -> NSTextField {
        let label = NSTextField(labelWithString: text)
        label.font = .systemFont(ofSize: 12, weight: .semibold)
        label.textColor = .secondaryLabelColor
        return label
    }

    func statCard(_ title: String, value: NSTextField, size: CGFloat) -> NSView {
        let name = NSTextField(labelWithString: title)
        name.font = .systemFont(ofSize: 11, weight: .medium)
        name.textColor = .secondaryLabelColor
        value.font = .systemFont(ofSize: size, weight: .semibold)
        value.lineBreakMode = .byTruncatingTail
        value.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        let stack = NSStackView(views: [name, value])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 2
        return Panel(stack, insets: NSEdgeInsets(top: 12, left: 14, bottom: 12, right: 14))
    }

    func scroll(_ view: NSTextView, editable: Bool) -> NSScrollView {
        let box = NSScrollView()
        box.hasVerticalScroller = true
        box.autohidesScrollers = true
        box.drawsBackground = false
        box.borderType = .noBorder
        box.documentView = view
        view.drawsBackground = false
        view.isEditable = editable
        view.isRichText = false
        view.font = .systemFont(ofSize: 13)
        view.textColor = .labelColor
        view.textContainerInset = NSSize(width: 8, height: 8)
        view.autoresizingMask = [.width]
        view.isVerticallyResizable = true
        view.textContainer?.widthTracksTextView = true
        return box
    }

    func build() {
        let root = BackgroundView()
        let inset: CGFloat = 28

        // Header: app icon, title and the service state
        let icon = NSImageView(image: NSApp.applicationIconImage)
        icon.imageScaling = .scaleProportionallyUpOrDown
        icon.translatesAutoresizingMaskIntoConstraints = false
        icon.widthAnchor.constraint(equalToConstant: 52).isActive = true
        icon.heightAnchor.constraint(equalToConstant: 52).isActive = true
        let title = NSTextField(labelWithString: "PostForge")
        title.font = .systemFont(ofSize: 22, weight: .semibold)
        title.textColor = .labelColor
        let subtitle = NSTextField(labelWithString: t("Plan a post, approve it in Postiz",
                                                      "Planea una publicación y apruébala en Postiz"))
        subtitle.font = .systemFont(ofSize: 12)
        subtitle.textColor = .secondaryLabelColor
        let titles = NSStackView(views: [title, subtitle])
        titles.orientation = .vertical
        titles.alignment = .leading
        titles.spacing = 1
        status.font = .systemFont(ofSize: 12, weight: .medium)
        let spacer = NSView()
        spacer.setContentHuggingPriority(NSLayoutConstraint.Priority(1), for: .horizontal)
        turnOnButton.title = t("Turn On", "Encender")
        turnOnButton.target = self
        turnOnButton.action = #selector(turnOnFromWindow)
        turnOnButton.controlSize = .small
        let serviceControls = NSStackView(views: [status, turnOnButton])
        serviceControls.orientation = .vertical
        serviceControls.alignment = .trailing
        serviceControls.spacing = 4
        let header = NSStackView(views: [icon, titles, spacer, serviceControls])
        header.spacing = 12
        header.alignment = .centerY

        // Overview
        let stats = NSStackView(views: [
            statCard(t("In queue", "En cola"), value: statsQueue, size: 26),
            statCard(t("Drafts", "Borradores"), value: statsDrafts, size: 26),
            statCard(t("Next post", "Próxima"), value: statsNext, size: 14),
        ])
        stats.distribution = .fillEqually
        stats.spacing = 12
        for card in stats.arrangedSubviews { card.heightAnchor.constraint(equalToConstant: 70).isActive = true }

        // Media
        let drop = DropView()
        drop.onFiles = { [weak self] urls in self?.add(urls) }
        drop.heightAnchor.constraint(equalToConstant: 72).isActive = true
        let dropIcon = NSImageView(image: NSImage(systemSymbolName: "photo.on.rectangle.angled",
                                                  accessibilityDescription: nil) ?? NSImage())
        dropIcon.contentTintColor = .secondaryLabelColor
        dropIcon.symbolConfiguration = NSImage.SymbolConfiguration(pointSize: 22, weight: .regular)
        let dropTitle = NSTextField(labelWithString: t("Drop photos or videos here", "Suelta fotos o videos aquí"))
        dropTitle.font = .systemFont(ofSize: 13, weight: .medium)
        dropTitle.textColor = .labelColor
        files.stringValue = t("No files yet", "Sin archivos")
        files.font = .systemFont(ofSize: 11)
        files.textColor = .secondaryLabelColor
        files.lineBreakMode = .byTruncatingMiddle
        files.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        let dropText = NSStackView(views: [dropTitle, files])
        dropText.orientation = .vertical
        dropText.alignment = .leading
        dropText.spacing = 2
        dropText.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        dropText.setContentHuggingPriority(NSLayoutConstraint.Priority(1), for: .horizontal)
        let browse = NSButton(title: t("Choose…", "Elegir…"), target: self, action: #selector(chooseFiles))
        let clear = NSButton(title: t("Clear", "Quitar"), target: self, action: #selector(clearFiles))
        browse.controlSize = .small
        clear.controlSize = .small
        let dropRow = NSStackView(views: [dropIcon, dropText, clear, browse])
        dropRow.spacing = 12
        dropRow.distribution = .fill
        dropRow.alignment = .centerY
        dropRow.translatesAutoresizingMaskIntoConstraints = false
        drop.addSubview(dropRow)
        NSLayoutConstraint.activate([
            dropRow.leadingAnchor.constraint(equalTo: drop.leadingAnchor, constant: 16),
            dropRow.trailingAnchor.constraint(equalTo: drop.trailingAnchor, constant: -16),
            dropRow.centerYAnchor.constraint(equalTo: drop.centerYAnchor),
        ])

        let placementLabel = caption(t("Create drafts for", "Crear borradores de"))
        refreshPlacementLabels()
        placementMenu.target = self
        placementMenu.action = #selector(draftOptionsChanged)
        let finalTagButton = NSButton(title: t("Final hashtag…", "Etiqueta final…"),
                                      target: NSApp.delegate, action: #selector(AppDelegate.editCaptionFinalTag))
        finalTagButton.controlSize = .small
        let placements = NSStackView(views: [placementLabel, placementMenu, finalTagButton])
        placements.spacing = 8

        chooseCover.title = t("Choose image…", "Elegir imagen…")
        chooseCover.target = self
        chooseCover.action = #selector(chooseCoverImage)
        clearCover.title = t("Clear", "Limpiar")
        clearCover.target = self
        clearCover.action = #selector(clearCoverImage)
        changeCover.title = t("Edit cover…", "Editar portada…")
        changeCover.target = self
        changeCover.action = #selector(editCover)
        changeCover.isHidden = true
        let coverLabel = caption(t("Video cover", "Portada del video"))
        coverSecond.placeholderString = t("Second", "Segundo")
        coverSecond.toolTip = t("Enter a second in the video, such as 12.5.", "Ingresa un segundo del video, por ejemplo 12,5.")
        coverSecond.delegate = self
        coverSecond.widthAnchor.constraint(equalToConstant: 72).isActive = true
        coverFile.lineBreakMode = .byTruncatingMiddle
        coverFile.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        let coverControls = NSStackView(views: [coverLabel, chooseCover, coverSecond, clearCover, changeCover, coverFile])
        coverControls.spacing = 6

        // Idea
        instruction.delegate = self
        let ideaPanel = Panel(scroll(instruction, editable: true), insets: NSEdgeInsets(), style: .input)
        ideaHeight = ideaPanel.heightAnchor.constraint(equalToConstant: 86)
        ideaHeight?.isActive = true
        placeholder.stringValue = t("Where, when and your idea. e.g. “Instagram and TikTok tomorrow at 6pm: fresh sourdough”",
                                    "Dónde, cuándo y tu idea. Ej.: “Instagram y TikTok mañana a las 6pm: pan de masa madre”")
        placeholder.font = .systemFont(ofSize: 13)
        placeholder.textColor = .tertiaryLabelColor
        placeholder.maximumNumberOfLines = 2
        placeholder.translatesAutoresizingMaskIntoConstraints = false
        ideaPanel.addSubview(placeholder)
        NSLayoutConstraint.activate([
            placeholder.leadingAnchor.constraint(equalTo: ideaPanel.leadingAnchor, constant: 13),
            placeholder.trailingAnchor.constraint(equalTo: ideaPanel.trailingAnchor, constant: -13),
            placeholder.topAnchor.constraint(equalTo: ideaPanel.topAnchor, constant: 8),
        ])

        // Actions
        let dictate = NSButton(title: t("Dictate", "Dictar"),
                               image: NSImage(systemSymbolName: "mic", accessibilityDescription: nil) ?? NSImage(),
                               target: self, action: #selector(startDictation))
        dictate.imagePosition = .imageLeading
        preview.title = t("👨‍🍳 Bake idea", "👨‍🍳 Hornea la idea")
        preview.target = self
        preview.action = #selector(runPreview)
        preview.controlSize = .large
        preview.font = .systemFont(ofSize: 14, weight: .semibold)
        preview.bezelColor = .systemBlue
        preview.widthAnchor.constraint(greaterThanOrEqualToConstant: 136).isActive = true
        preview.heightAnchor.constraint(greaterThanOrEqualToConstant: 32).isActive = true
        create.title = t("Create Drafts", "Crear borradores")
        create.target = self
        create.action = #selector(runCreate)
        create.keyEquivalent = "\r"
        create.isEnabled = false
        spinner.style = .spinning
        spinner.controlSize = .small
        spinner.isDisplayedWhenStopped = false
        let actionSpacer = NSView()
        actionSpacer.setContentHuggingPriority(NSLayoutConstraint.Priority(1), for: .horizontal)
        mixer.isHidden = true
        let actions = NSStackView(views: [dictate, actionSpacer, mixer, spinner, preview, create])
        actions.spacing = 10
        actions.alignment = .centerY

        steps.isEditable = false
        steps.isSelectable = false
        steps.isBordered = false
        steps.drawsBackground = false
        steps.maximumNumberOfLines = 2
        steps.alignment = .center
        refreshStepLabels()

        // Plan: a read-only result. Until there is one, an empty state explains what happens next.
        result.string = ""
        result.textColor = .labelColor
        result.font = .systemFont(ofSize: 13)
        let planPanel = Panel(scroll(result, editable: false), insets: NSEdgeInsets(), style: .output)
        result.isRichText = true
        result.textContainerInset = NSSize(width: 12, height: 12)
        planPanel.heightAnchor.constraint(greaterThanOrEqualToConstant: 110).isActive = true
        planPanel.setContentHuggingPriority(NSLayoutConstraint.Priority(1), for: .vertical)
        let emptyIcon = NSImageView(image: NSImage(systemSymbolName: "list.bullet.clipboard", accessibilityDescription: nil) ?? NSImage())
        emptyIcon.symbolConfiguration = NSImage.SymbolConfiguration(pointSize: 24, weight: .light)
        emptyIcon.contentTintColor = .tertiaryLabelColor
        let emptyTitle = NSTextField(labelWithString: t("Your plan appears here", "Tu plan aparecerá aquí"))
        emptyTitle.font = .systemFont(ofSize: 13, weight: .medium)
        emptyTitle.textColor = .secondaryLabelColor
        let emptyHint = NSTextField(wrappingLabelWithString: t(
            "Add your idea and press Bake idea. Nothing is published until you approve it in Postiz.",
            "Escribe tu idea y pulsa Hornea la idea. Nada se publica hasta que lo apruebes en Postiz."))
        emptyHint.font = .systemFont(ofSize: 12)
        emptyHint.textColor = .tertiaryLabelColor
        emptyHint.alignment = .center
        emptyHint.preferredMaxLayoutWidth = 320
        emptyState.setViews([emptyIcon, emptyTitle, emptyHint], in: .center)
        emptyState.orientation = .vertical
        emptyState.alignment = .centerX
        emptyState.spacing = 6
        emptyState.translatesAutoresizingMaskIntoConstraints = false
        planPanel.addSubview(emptyState)
        NSLayoutConstraint.activate([
            emptyState.centerXAnchor.constraint(equalTo: planPanel.centerXAnchor),
            emptyState.centerYAnchor.constraint(equalTo: planPanel.centerYAnchor),
            emptyState.leadingAnchor.constraint(greaterThanOrEqualTo: planPanel.leadingAnchor, constant: 20),
            emptyState.trailingAnchor.constraint(lessThanOrEqualTo: planPanel.trailingAnchor, constant: -20),
        ])

        // Footer: WhatsApp review on the left, backup tools on the right
        let whatsappButton = NSButton(title: t("WhatsApp", "WhatsApp"),
                                      image: NSImage(systemSymbolName: "bubble.left.and.bubble.right", accessibilityDescription: nil) ?? NSImage(),
                                      target: self, action: #selector(openWhatsAppFromWindow))
        whatsappButton.imagePosition = .imageLeading
        let backupButton = NSButton(title: t("Backup & Move", "Respaldo y traslado"),
                                    image: NSImage(systemSymbolName: "externaldrive", accessibilityDescription: nil) ?? NSImage(),
                                    target: self, action: #selector(openBackupFromWindow))
        backupButton.imagePosition = .imageLeading
        calendar.title = t("Open Postiz Calendar", "Abrir calendario de Postiz")
        calendar.image = NSImage(systemSymbolName: "calendar", accessibilityDescription: nil)
        calendar.imagePosition = .imageLeading
        calendar.target = self
        calendar.action = #selector(openCalendar)
        calendar.isHidden = true
        for button in [whatsappButton, backupButton, calendar] { button.controlSize = .small }
        let footerSpacer = NSView()
        footerSpacer.setContentHuggingPriority(NSLayoutConstraint.Priority(1), for: .horizontal)
        updatesButton.target = NSApp.delegate
        updatesButton.action = #selector(AppDelegate.openUpdates)
        updatesButton.controlSize = .small
        refreshUpdates(available: (NSApp.delegate as? AppDelegate)?.updatesAvailable == true)
        let footer = NSStackView(views: [whatsappButton, updatesButton, footerSpacer, backupButton])
        footer.spacing = 8
        footer.alignment = .centerY

        let mediaLabel = caption(t("Photos & videos", "Fotos y videos"))
        let ideaLabel = caption(t("Your request", "Tu pedido"))
        ideaPanel.toolTip = t("Use ‘idea:’ to generate a caption or ‘caption:’ to use your exact words.",
                              "Usa «idea:» para redactar un texto o «texto:» para usar tus palabras tal cual.")
        let planLabel = caption(t("Plan", "Plan"))
        let planSpacer = NSView()
        planSpacer.setContentHuggingPriority(NSLayoutConstraint.Priority(1), for: .horizontal)
        statusApproval.title = t("Approve Status…", "Aprobar Estado…")
        statusApproval.target = self
        statusApproval.action = #selector(approveStatusFromPlan)
        statusApproval.controlSize = .small
        statusApproval.isHidden = true
        captionVersions.target = self
        captionVersions.action = #selector(restoreCaptionVersion)
        captionVersions.controlSize = .small
        alternateCaption.title = t("Another Caption…", "Otra versión del texto…")
        alternateCaption.target = self
        alternateCaption.action = #selector(runAlternateCaption)
        alternateCaption.controlSize = .small
        updateCaptionVersions()
        let planHeader = NSStackView(views: [planLabel, planSpacer, captionVersions, alternateCaption, statusApproval, calendar])
        planHeader.alignment = .centerY
        connections.font = .systemFont(ofSize: 11)
        connections.textColor = .secondaryLabelColor
        let main = NSStackView(views: [header, steps, connections, stats, mediaLabel, drop, placements, coverControls, ideaLabel, ideaPanel, actions, planHeader, planPanel, footer])
        main.orientation = .vertical
        main.alignment = .leading
        main.spacing = 9
        main.edgeInsets = NSEdgeInsets(top: 34, left: inset, bottom: 16, right: inset)
        main.setCustomSpacing(13, after: header)
        main.setCustomSpacing(14, after: stats)
        for label in [mediaLabel, ideaLabel] { main.setCustomSpacing(6, after: label) }
        main.setCustomSpacing(13, after: actions)
        main.setCustomSpacing(12, after: planPanel)
        main.setCustomSpacing(6, after: planHeader)
        main.translatesAutoresizingMaskIntoConstraints = false
        for view in [header, steps, stats, drop, coverControls, ideaPanel, actions, planHeader, planPanel, footer] {
            view.widthAnchor.constraint(equalTo: main.widthAnchor, constant: -2 * inset).isActive = true
        }

        root.addSubview(main)
        NSLayoutConstraint.activate([
            main.leadingAnchor.constraint(equalTo: root.leadingAnchor),
            main.trailingAnchor.constraint(equalTo: root.trailingAnchor),
            main.topAnchor.constraint(equalTo: root.topAnchor),
            main.bottomAnchor.constraint(equalTo: root.bottomAnchor),
        ])
        window.contentView = root
    }

    func add(_ urls: [URL]) {
        media += urls.filter { !media.contains($0) }
        files.stringValue = media.isEmpty ? t("No files yet", "Sin archivos")
            : "\(media.count) · " + media.map { $0.lastPathComponent }.joined(separator: ", ")
        draftOptionsChanged()
    }

    func refreshPlacementLabels() {
        let selected = max(0, placementMenu.indexOfSelectedItem)
        placementMenu.removeAllItems()
        placementMenu.addItems(withTitles: [
            t("Automatic (posts and stories)", "Automático (publicaciones e historias)"),
            t("Posts only", "Solo publicaciones"),
            t("Stories only", "Solo historias"),
            t("Posts and stories", "Publicaciones e historias"),
        ])
        placementMenu.toolTip = t("Automatic follows your instruction and includes both formats where supported.",
                                  "Automático sigue tu instrucción e incluye ambos formatos donde se admiten.")
        placementMenu.selectItem(at: selected)
    }

    @objc func draftOptionsChanged() {
        savedVersions.removeAll()
        acceptedNoCover = false
        invalidateReviewedPlan()
    }

    func invalidateReviewedPlan() {
        inputRevision += 1
        selectedVersion = nil
        canGenerateVariant = false
        lastReport = nil
        reviewedCaption = nil
        reviewedThreadsCaption = nil
        reviewedFinalTag = nil
        reviewedYouTubeTitle = nil
        previewed = false
        preview.bezelColor = .systemBlue
        create.isEnabled = false
        coverLocked = false
        updateCoverControls()
        updateCaptionVersions()
    }

    func updateCoverControls() {
        chooseCover.isEnabled = !coverLocked && !working
        coverSecond.isEnabled = !coverLocked && !working
        clearCover.isEnabled = !coverLocked && !working
        clearCover.isHidden = coverLocked
        changeCover.isHidden = !coverLocked || !coverAvailable
        changeCover.isEnabled = !working
    }

    @objc func editCover() {
        guard !working else { return }
        if coverLocked {
            draftOptionsChanged()
            show(t("Choose a cover, then bake the idea again to review the updated plan.",
                   "Elige una portada y vuelve a hornear la idea para revisar el plan actualizado."))
        }
        window.makeFirstResponder(coverSecond)
    }

    func confirmPlanWithoutCover(_ output: String) -> Bool {
        guard !acceptedNoCover,
              let plan = (try? JSONSerialization.jsonObject(with: Data(output.utf8))) as? [String: Any],
              plan["video_without_cover"] as? Bool == true,
              let delegate = NSApp.delegate as? AppDelegate else { return true }
        acceptedNoCover = delegate.ask(
            t("Continue without a cover?", "¿Continuar sin portada?"),
            t("You can choose an image or a frame from the video. If you continue, each platform uses its default where applicable.",
              "Puedes elegir una imagen o un fotograma del video. Si continúas, cada plataforma usará su portada predeterminada cuando corresponda."),
            safe: t("Choose a cover", "Elegir portada"),
            risky: t("Continue without cover", "Continuar sin portada"))
        if !acceptedNoCover {
            invalidateReviewedPlan()
            show(t("Choose an image or enter a second from the video, then bake the idea again.",
                   "Elige una imagen o indica un segundo del video y vuelve a hornear la idea."))
            editCover()
        }
        return acceptedNoCover
    }

    func updateCaptionVersions() {
        captionVersions.removeAllItems()
        captionVersions.addItem(withTitle: t("Previous versions…", "Versiones anteriores…"))
        for index in savedVersions.indices {
            captionVersions.addItem(withTitle: t("Version \(index + 1)", "Versión \(index + 1)"))
        }
        captionVersions.selectItem(at: selectedVersion.map { $0 + 1 } ?? 0)
        captionVersions.isHidden = savedVersions.isEmpty
        captionVersions.isEnabled = !working
        alternateCaption.isHidden = !canGenerateVariant
        alternateCaption.isEnabled = !working
    }

    @objc func restoreCaptionVersion() {
        let index = captionVersions.indexOfSelectedItem - 1
        guard !working, savedVersions.indices.contains(index) else { return }
        let entry = savedVersions[index]
        instruction.string = entry.instruction
        placeholder.isHidden = !entry.instruction.isEmpty
        inputRevision += 1
        selectedVersion = index
        report(entry.output, dryRun: true, exitCode: 0)
    }

    @objc func runAlternateCaption() {
        guard canGenerateVariant, let reviewedCaption else { return }
        run(dryRun: true, previousCaption: reviewedCaption)
    }

    @objc func chooseCoverImage() {
        guard !working else { return }
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.image]
        if panel.runModal() == .OK, let url = panel.url {
            coverURL = url
            coverSecond.stringValue = ""
            coverFile.stringValue = url.lastPathComponent
            draftOptionsChanged()
        }
    }

    @objc func clearCoverImage() {
        coverURL = nil
        coverSecond.stringValue = ""
        coverFile.stringValue = ""
        draftOptionsChanged()
    }

    func controlTextDidChange(_ notification: Notification) {
        coverURL = nil
        coverFile.stringValue = ""
        draftOptionsChanged()
    }

    @objc func chooseFiles() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = true
        panel.allowedContentTypes = [.image, .movie]
        if panel.runModal() == .OK { add(panel.urls) }
    }

    @objc func clearFiles() {
        media = []
        clearCoverImage()
        add([])
    }

    func textDidChange(_ notification: Notification) {
        placeholder.isHidden = !instruction.string.isEmpty
        invalidateReviewedPlan()
    }

    @objc func startDictation() {
        window.makeFirstResponder(instruction)
        if !NSApp.sendAction(Selector(("startDictation:")), to: nil, from: self) {
            show("Dictation isn't on. Turn it on in System Settings → Keyboard → Dictation, then press the dictation key.")
        }
    }

    @objc func turnOnFromWindow() {
        guard let delegate = NSApp.delegate as? AppDelegate, delegate.busy == nil,
              delegate.state?.state == "off" || delegate.state?.state == "partial" else { return }
        delegate.turnOn()
    }

    @objc func runPreview() { run(dryRun: true) }
    @objc func runCreate() {
        guard previewed else {
            show("Preview the plan first. Nothing will be created until you confirm it.")
            return
        }
        run(dryRun: false)
    }

    @objc func openWhatsAppFromWindow() { (NSApp.delegate as? AppDelegate)?.reviewWhatsAppPlans() }
    @objc func openBackupFromWindow() { (NSApp.delegate as? AppDelegate)?.openBackupWindow() }

    @objc func approveStatusFromPlan() {
        guard let id = pendingStatusID, let delegate = NSApp.delegate as? AppDelegate else { return }
        delegate.approveStatus(id) { self.statusApproval.isHidden = true }
    }

    @objc func openCalendar() {
        if let url = reviewURL { NSWorkspace.shared.open(url) }
    }

    func show(_ rawText: String) {
        let text = localizedUI(rawText)
        result.string = text
        result.textColor = .labelColor
        emptyState.isHidden = !text.isEmpty
    }

    func run(dryRun: Bool, previousCaption: String? = nil) {
        guard !working else { return }
        if (NSApp.delegate as? AppDelegate)?.state?.state == "off" {
            show(t("Turn on PostForge to prepare a plan.", "Enciende PostForge para preparar un plan."))
            return
        }
        guard (NSApp.delegate as? AppDelegate)?.busy == nil else {
            show(t("Wait for the current operation to finish, then try again.", "Espera a que termine la operación actual y vuelve a intentar.")); return
        }
        let text = instruction.string.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return show("Say where, when, and your idea first.") }
        let revision = inputRevision
        var args = [project + "/scripts/plan-post.sh", "--json", "--ui-lang", t("English", "Spanish")]
        switch placementMenu.indexOfSelectedItem {
        case 1: args += ["--placement", "feed"]
        case 2: args += ["--placement", "story"]
        case 3: args += ["--placement", "both"]
        default: break
        }
        if let url = coverURL { args += ["--cover-image", url.path] }
        let second = coverSecond.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        if !second.isEmpty { args += ["--cover-second=\(second)"] }
        if dryRun {
            args.append("--dry-run")
            if let previousCaption { args.append("--alternate-caption=\(previousCaption)") }
        } else if let reviewedCaption {
            args.append("--reviewed-caption=\(reviewedCaption)")
            if let reviewedThreadsCaption { args.append("--reviewed-threads-caption=\(reviewedThreadsCaption)") }
            if let reviewedFinalTag { args.append("--final-tag=\(reviewedFinalTag)") }
            if let reviewedYouTubeTitle { args.append("--reviewed-youtube-title=\(reviewedYouTubeTitle)") }
        }
        for url in media { args += ["--media", url.path] }
        args.append(text)
        working = true
        updateCoverControls()
        updateCaptionVersions()
        preview.isEnabled = false
        create.isEnabled = false
        previewed = false
        if dryRun { mixer.start() } else { spinner.startAnimation(nil) }
        (NSApp.delegate as? AppDelegate)?.planningWork += 1
        show(dryRun ? t("Reading your plan and writing the caption…", "Leyendo tu plan y redactando el texto…") : t("Creating drafts…", "Creando borradores…"))
        DispatchQueue.global(qos: .userInitiated).async {
            let (code, output) = runCommand(args, in: self.project, timeout: 900, quietErrors: true)
            DispatchQueue.main.async {
                self.spinner.stopAnimation(nil)
                self.mixer.stop()
                if let delegate = NSApp.delegate as? AppDelegate {
                    delegate.planningWork -= 1
                    delegate.poll()
                }
                self.working = false
                self.updateCoverControls()
                self.updateCaptionVersions()
                self.preview.isEnabled = true
                if dryRun && revision != self.inputRevision {
                    self.invalidateReviewedPlan()
                    self.show(self.t("The draft options changed. Bake the idea again to review them.",
                                     "Cambiaste las opciones del borrador. Vuelve a hornear la idea para revisarlas."))
                    return
                }
                if dryRun && code == 0 && !self.confirmPlanWithoutCover(output) { return }
                self.report(output, dryRun: dryRun, exitCode: code)
                if dryRun && self.previewed {
                    self.savedVersions.append((instruction: text, output: output))
                    if self.savedVersions.count > 8 { self.savedVersions.removeFirst() }
                    self.selectedVersion = self.savedVersions.count - 1
                } else if !dryRun && code == 0 {
                    self.savedVersions.removeAll()
                    self.selectedVersion = nil
                }
                self.updateCaptionVersions()
            }
        }
    }

    func report(_ output: String, dryRun: Bool, exitCode: Int32) {
        lastReport = (output, dryRun, exitCode)
        canGenerateVariant = false
        defer {
            updateCaptionVersions()
            updateCoverControls()
        }
        guard let json = (try? JSONSerialization.jsonObject(with: Data(output.utf8))) as? [String: Any] else {
            return show("✖ \(dryRun ? t("Preview", "Vista previa") : t("Draft creation", "Creación de borradores")) \(t("failed", "falló")) (\(exitCode)).\n"
                        + String(output.suffix(800)))
        }
        if let error = json["error"] as? String {
            return show("✖ \(dryRun ? t("Preview", "Vista previa") : t("Draft creation", "Creación de borradores")) \(t("failed", "falló")):\n" + error
                        + t("\n\nNothing was created. Correct the request or retry.", "\n\nNo se creó nada. Corrige la solicitud o vuelve a intentar."))
        }
        let names = ["instagram": "Instagram", "facebook": "Facebook", "tiktok": "TikTok", "youtube": "YouTube",
                     "threads": "Threads", "whatsapp": "WhatsApp Status"]
        let document = NSMutableAttributedString(string: "")
        func line(_ value: String, size: CGFloat = 13, weight: NSFont.Weight = .regular,
                  color: NSColor = .labelColor, before: CGFloat = 0) {
            let style = NSMutableParagraphStyle()
            style.paragraphSpacingBefore = before
            style.paragraphSpacing = 5
            style.lineSpacing = 2
            document.append(NSAttributedString(string: value + "\n", attributes: [
                .font: NSFont.systemFont(ofSize: size, weight: weight),
                .foregroundColor: color, .paragraphStyle: style,
            ]))
        }
        let scheduled = (json["when_utc"] as? String).map { shortDate(iso: $0) }
            ?? (json["when_local"] as? String ?? "")
        line(dryRun ? t("🗓  Plan ready to review", "🗓  Plan listo para revisar")
                    : t("✓  Drafts prepared", "✓  Borradores preparados"), size: 18, weight: .bold)
        line(scheduled + t(" · local time", " · hora local"), weight: .medium, color: .secondaryLabelColor)
        line(t("📍  Destinations", "📍  Destinos"), weight: .semibold, before: 9)
        for target in json["targets"] as? [[String: Any]] ?? [] {
            let network = target["network"] as? String ?? ""
            let short = network == "youtube" && (json["short"] as? Bool ?? false) ? " (Short)" : ""
            let placementLabels = ["feed": t("Post", "Publicación"), "story": t("Story", "Historia"),
                                   "status": t("Status", "Estado")]
            let label = placementLabels[target["placement"] as? String ?? ""].map { " · " + $0 } ?? ""
            let cover: String
            if let seconds = target["cover_second"] as? Double {
                let timestamp = seconds.formatted(.number.locale(Locale(identifier: t("en_US", "es_EC"))))
                cover = t(" · Cover at \(timestamp) s", " · Portada en el segundo \(timestamp)")
            } else if target["cover"] as? String == "image" {
                cover = t(" · Cover image", " · Imagen de portada")
            } else { cover = "" }
            let channel = network == "whatsapp" ? t("WhatsApp Status", "Estado de WhatsApp") : target["channel"] as? String ?? ""
            line(network == "whatsapp" ? channel : "\(names[network] ?? network) · \(channel)\(short)\(label)\(cover)")
        }
        if let caption = json["caption"] as? String {
            var source = json["caption_source"] as? String ?? ""
            if source == "your text" { source = t("your text", "tu texto") }
            else if source == "reviewed caption" { source = t("reviewed caption", "texto revisado") }
            else if source.hasPrefix("written by ") && source.hasSuffix(" from your idea") {
                let model = String(source.dropFirst("written by ".count).dropLast(" from your idea".count))
                source = t("written by \(model) from your idea", "redactado por \(model) a partir de tu idea")
            }
            line(t("✍️  Caption", "✍️  Texto"), weight: .semibold, before: 9)
            if !source.isEmpty { line(source, size: 11, color: .secondaryLabelColor) }
            line(caption)
        }
        if let title = json["youtube_title"] as? String {
            line(t("▶  YouTube title", "▶  Título de YouTube"), weight: .semibold, before: 9)
            line(title)
        }
        if let threadsCaption = json["threads_caption"] as? String {
            line(t("✍️  Threads caption", "✍️  Texto para Threads"), weight: .semibold, before: 9)
            line(threadsCaption)
        }
        let notes = json["notes"] as? [String] ?? []
        let warnings = json["warnings"] as? [String] ?? []
        if !notes.isEmpty || !warnings.isEmpty {
            line(t("⚠️  Things to check", "⚠️  Por revisar"), weight: .semibold, before: 9)
            for note in notes { line(note, color: .secondaryLabelColor) }
            for warning in warnings { line(warning, color: .systemOrange) }
        }
        if !dryRun {
            line(t("Review and approve social drafts in the Postiz calendar.", "Revisa y aprueba los borradores en el calendario de Postiz."),
                 weight: .medium, color: .secondaryLabelColor, before: 9)
            reviewURL = (json["review_url"] as? String).flatMap(URL.init(string:))
            calendar.isHidden = reviewURL == nil
            pendingStatusID = json["whatsapp_pending_id"] as? String
            if let id = pendingStatusID,
               let delegate = NSApp.delegate as? AppDelegate,
               delegate.pendingStatusApprovals().contains(where: { $0["id"] as? String == id }) {
                statusApproval.isHidden = false
                line(t("WhatsApp Status needs separate approval. Use Approve Status above.",
                       "El Estado de WhatsApp necesita su propia aprobación. Pulsa Aprobar Estado arriba."),
                     weight: .semibold, color: .systemOrange, before: 6)
            } else { statusApproval.isHidden = true }
        } else {
            statusApproval.isHidden = true
            reviewedCaption = json["caption"] as? String
            canGenerateVariant = (json["caption_source"] as? String)?.hasPrefix("written by ") == true
            reviewedThreadsCaption = json["threads_caption"] as? String
            reviewedFinalTag = json["final_tag"] as? String
            reviewedYouTubeTitle = json["youtube_title"] as? String
            previewed = reviewedCaption != nil
            coverLocked = previewed
            coverAvailable = json["video_cover_available"] as? Bool == true
            preview.bezelColor = nil
            create.isEnabled = previewed
            line(t("Create drafts when you’re ready to continue.", "Cuando esté todo listo, pulsa Crear borradores."),
                 weight: .medium, color: .secondaryLabelColor, before: 9)
        }
        result.textStorage?.setAttributedString(document)
        result.scrollRangeToVisible(NSRange(location: 0, length: 0))
        emptyState.isHidden = true
        ideaHeight?.constant = 64
        if !planExpanded, let bounds = window.screen?.visibleFrame {
            planExpanded = true
            var frame = window.frame
            let extra = max(0, min(140, bounds.height - frame.height))
            if extra > 0 {
                frame.origin.y = max(bounds.minY, frame.minY - extra)
                frame.size.height += extra
                window.setFrame(frame, display: true, animate: window.isVisible)
            }
        }
    }
}

// MARK: - Shared window pieces

/// Runs a command and reports each output line as it appears, so a window can show progress.
/// `extraEnv` carries secrets (a passphrase) without putting them on the command line. Call off the main thread.
func runStreaming(_ args: [String], in dir: String, extraEnv: [String: String] = [:], timeout: TimeInterval,
                  onLine: @escaping (String) -> Void) -> (Int32, String) {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: args[0])
    process.arguments = Array(args.dropFirst())
    process.currentDirectoryURL = URL(fileURLWithPath: dir)
    var env = ProcessInfo.processInfo.environment
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    env["LANG"] = env["LANG"] ?? "en_US.UTF-8"
    env["PYTHONIOENCODING"] = "utf-8"
    extraEnv.forEach { env[$0.key] = $0.value }
    process.environment = env
    let pipe = Pipe()
    process.standardOutput = pipe
    process.standardError = pipe
    process.standardInput = FileHandle.nullDevice
    do { try process.run() } catch { return (-1, "Could not run \(args[0]): \(error.localizedDescription)") }
    let killer = DispatchWorkItem { if process.isRunning { process.terminate() } }
    DispatchQueue.global().asyncAfter(deadline: .now() + timeout, execute: killer)
    var collected = ""
    var pending = Data()
    let handle = pipe.fileHandleForReading
    while true {
        let chunk = handle.availableData
        if chunk.isEmpty { break }
        pending.append(chunk)
        while let newline = pending.firstIndex(of: 0x0A) {
            let line = String(decoding: pending[pending.startIndex..<newline], as: UTF8.self)
            pending.removeSubrange(pending.startIndex...newline)
            collected += line + "\n"
            onLine(line)
        }
    }
    if !pending.isEmpty {
        let line = String(decoding: pending, as: UTF8.self)
        collected += line
        onLine(line)
    }
    process.waitUntilExit()
    killer.cancel()
    return (process.terminationStatus, collected)
}

/// The last useful lines of a failed command: an explicit "✖" message if there is one, else the tail.
func failureSummary(_ output: String) -> String {
    let lines = output.split(whereSeparator: \.isNewline).map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
    let marked = lines.filter { $0.hasPrefix("✖") }
    if !marked.isEmpty { return marked.suffix(3).joined(separator: "\n") }
    let errors = lines.filter { $0.lowercased().contains("error") || $0.lowercased().contains("wrong passphrase") }
    return (errors.isEmpty ? lines.suffix(4) : errors.suffix(3)).joined(separator: "\n")
}

func windowLabel(_ text: String, size: CGFloat = 13, weight: NSFont.Weight = .regular,
                 color: NSColor = .labelColor, lines: Int = 1, width: CGFloat = 470) -> NSTextField {
    let label = lines == 1 ? NSTextField(labelWithString: text) : NSTextField(wrappingLabelWithString: text)
    label.font = .systemFont(ofSize: size, weight: weight)
    label.textColor = color
    if lines != 1 {
        label.maximumNumberOfLines = lines
        label.preferredMaxLayoutWidth = width
    }
    return label
}

func flexibleSpacer() -> NSView {
    let spacer = NSView()
    spacer.setContentHuggingPriority(NSLayoutConstraint.Priority(1), for: .horizontal)
    return spacer
}

/// A dark, fixed-width window shell shared by the secondary windows (same look as New Post).
func makeSecondaryWindow(title: String, height: CGFloat) -> NSWindow {
    let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 560, height: height),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                          backing: .buffered, defer: false)
    window.title = title
    window.titlebarAppearsTransparent = true
    window.titleVisibility = .hidden
    window.appearance = NSAppearance(named: .darkAqua)
    window.backgroundColor = BackgroundView.color
    window.isMovableByWindowBackground = true
    window.isReleasedWhenClosed = false
    window.contentMinSize = NSSize(width: 560, height: min(height, 480))
    window.contentMaxSize = NSSize(width: 560, height: 2000)
    return window
}

func windowHeader(title: String, subtitle: String) -> NSStackView {
    let icon = NSImageView(image: NSApp.applicationIconImage)
    icon.imageScaling = .scaleProportionallyUpOrDown
    icon.translatesAutoresizingMaskIntoConstraints = false
    icon.widthAnchor.constraint(equalToConstant: 44).isActive = true
    icon.heightAnchor.constraint(equalToConstant: 44).isActive = true
    let titles = NSStackView(views: [windowLabel(title, size: 20, weight: .semibold),
                                     windowLabel(subtitle, size: 12, color: .secondaryLabelColor, lines: 2, width: 400)])
    titles.orientation = .vertical
    titles.alignment = .leading
    titles.spacing = 1
    let header = NSStackView(views: [icon, titles])
    header.spacing = 12
    header.alignment = .centerY
    return header
}

/// Stacks sections top to bottom inside a window and pins them to its edges.
func layoutSections(_ views: [NSView], in root: NSView, inset: CGFloat = 28, top: CGFloat = 38,
                    spacing: CGFloat = 12) -> NSStackView {
    let main = NSStackView(views: views)
    main.orientation = .vertical
    main.alignment = .leading
    main.spacing = spacing
    main.edgeInsets = NSEdgeInsets(top: top, left: inset, bottom: 22, right: inset)
    main.translatesAutoresizingMaskIntoConstraints = false
    root.addSubview(main)
    NSLayoutConstraint.activate([
        main.leadingAnchor.constraint(equalTo: root.leadingAnchor),
        main.trailingAnchor.constraint(equalTo: root.trailingAnchor),
        main.topAnchor.constraint(equalTo: root.topAnchor),
        main.bottomAnchor.constraint(lessThanOrEqualTo: root.bottomAnchor),
    ])
    for view in views where !(view is NSTextField) {
        view.widthAnchor.constraint(equalTo: main.widthAnchor, constant: -2 * inset).isActive = true
    }
    return main
}

func panelStack(_ views: [NSView], spacing: CGFloat = 10) -> NSStackView {
    let stack = NSStackView(views: views)
    stack.orientation = .vertical
    stack.alignment = .leading
    stack.spacing = spacing
    for view in views where !(view is NSTextField) {
        view.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
    }
    return stack
}

func sectionCaption(_ text: String) -> NSTextField {
    windowLabel(text, size: 12, weight: .semibold, color: .secondaryLabelColor)
}

func secureField(_ placeholder: String) -> NSSecureTextField {
    let field = NSSecureTextField()
    field.placeholderString = placeholder
    field.controlSize = .large
    field.font = .systemFont(ofSize: 13)
    return field
}

// MARK: - Backup & Move window

/// One place for everything that moves or removes your data: export a backup, restore one, uninstall.
final class BackupWindow: NSObject {
    let delegate: AppDelegate
    let window: NSWindow
    var exportFolder = URL(fileURLWithPath: NSHomeDirectory() + "/Desktop")
    var restoreFolder: URL?
    var lastExportPath: String?

    let exportFolderLabel = windowLabel("", size: 12, color: .secondaryLabelColor)
    let exportPass = secureField("")
    let exportPass2 = secureField("")
    let exportButton = NSButton(title: "", target: nil, action: nil)
    let exportSpinner = NSProgressIndicator()
    let exportStatus = windowLabel("", size: 12, color: .secondaryLabelColor)
    let revealButton = NSButton(title: "", target: nil, action: nil)

    let restoreFolderLabel = windowLabel("", size: 12, color: .secondaryLabelColor)
    let restorePass = secureField("")
    let restoreButton = NSButton(title: "", target: nil, action: nil)
    let restoreSpinner = NSProgressIndicator()
    let restoreStatus = windowLabel("", size: 12, color: .secondaryLabelColor)

    var project: String { delegate.project }
    func t(_ english: String, _ spanish: String) -> String { delegate.text(english, spanish) }

    init(delegate: AppDelegate) {
        self.delegate = delegate
        window = makeSecondaryWindow(title: "PostForge", height: 700)
        super.init()
        build()
    }

    func show() {
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func build() {
        let root = BackgroundView()
        let header = windowHeader(title: t("Backup & Move", "Respaldo y traslado"),
                                  subtitle: t("Save your data, restore it, or remove PostForge", "Guarda tus datos, restáuralos o quita PostForge"))

        // Export
        exportPass.placeholderString = t("Passphrase (at least 12 characters)", "Contraseña (mínimo 12 caracteres)")
        exportPass2.placeholderString = t("Repeat the passphrase", "Repite la contraseña")
        let chooseExport = NSButton(title: t("Choose…", "Elegir…"), target: self, action: #selector(chooseExportFolder))
        chooseExport.controlSize = .small
        let exportRow = NSStackView(views: [windowLabel(t("Save to", "Guardar en"), size: 12, weight: .medium), exportFolderLabel,
                                            flexibleSpacer(), chooseExport])
        exportRow.spacing = 8
        exportRow.alignment = .centerY
        exportFolderLabel.lineBreakMode = .byTruncatingMiddle
        exportFolderLabel.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        exportButton.title = t("Export Backup", "Exportar respaldo")
        exportButton.target = self
        exportButton.action = #selector(runExport)
        exportButton.keyEquivalent = "\r"
        exportSpinner.style = .spinning
        exportSpinner.controlSize = .small
        exportSpinner.isDisplayedWhenStopped = false
        revealButton.title = t("Show in Finder", "Mostrar en Finder")
        revealButton.target = self
        revealButton.action = #selector(revealExport)
        revealButton.controlSize = .small
        revealButton.isHidden = true
        exportStatus.lineBreakMode = .byTruncatingTail
        exportStatus.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        let exportActions = NSStackView(views: [exportStatus, flexibleSpacer(), exportSpinner, revealButton, exportButton])
        exportActions.spacing = 10
        exportActions.alignment = .centerY
        let exportBody = panelStack([
            windowLabel(t("Saves encrypted credentials, gateway access settings if configured, and a verified Postiz export. Keep the folder private because the Postiz archive contains channel tokens.",
                          "Guarda tus credenciales cifradas, los ajustes de acceso seguro si están configurados y un respaldo verificado de Postiz. Mantén la carpeta en privado porque el respaldo de Postiz contiene tokens de tus canales."),
                        size: 12, color: .secondaryLabelColor, lines: 4),
            exportRow, exportPass, exportPass2,
            windowLabel(t("You will need this passphrase to restore. It can't be recovered if you forget it.",
                          "Necesitarás esta contraseña para restaurar. No se puede recuperar si la olvidas."),
                        size: 11, color: .tertiaryLabelColor, lines: 2),
            exportActions,
        ])
        let exportPanel = Panel(exportBody, insets: NSEdgeInsets(top: 14, left: 16, bottom: 14, right: 16))

        // Restore
        restorePass.placeholderString = t("Passphrase of the backup", "Contraseña del respaldo")
        let chooseRestore = NSButton(title: t("Choose…", "Elegir…"), target: self, action: #selector(chooseRestoreFolder))
        chooseRestore.controlSize = .small
        restoreFolderLabel.stringValue = t("No backup folder chosen", "Ninguna carpeta elegida")
        restoreFolderLabel.lineBreakMode = .byTruncatingMiddle
        restoreFolderLabel.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        let restoreRow = NSStackView(views: [windowLabel(t("Backup", "Respaldo"), size: 12, weight: .medium), restoreFolderLabel,
                                             flexibleSpacer(), chooseRestore])
        restoreRow.spacing = 8
        restoreRow.alignment = .centerY
        restoreButton.title = t("Restore…", "Restaurar…")
        restoreButton.target = self
        restoreButton.action = #selector(runRestore)
        restoreSpinner.style = .spinning
        restoreSpinner.controlSize = .small
        restoreSpinner.isDisplayedWhenStopped = false
        restoreStatus.lineBreakMode = .byTruncatingTail
        restoreStatus.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        let restoreActions = NSStackView(views: [restoreStatus, flexibleSpacer(), restoreSpinner, restoreButton])
        restoreActions.spacing = 10
        restoreActions.alignment = .centerY
        let restoreBody = panelStack([
            windowLabel(t("Brings back the credentials and Postiz data from a backup folder made by Export. This replaces what is on this Mac now. WhatsApp must be linked again by QR.",
                          "Recupera las credenciales y los datos de Postiz de una carpeta creada con Exportar. Reemplaza lo que hay ahora en este Mac. WhatsApp debe vincularse de nuevo con QR."),
                        size: 12, color: .secondaryLabelColor, lines: 4),
            restoreRow, restorePass, restoreActions,
        ])
        let restorePanel = Panel(restoreBody, insets: NSEdgeInsets(top: 14, left: 16, bottom: 14, right: 16))

        // Uninstall
        let uninstall = NSButton(title: t("Uninstall…", "Desinstalar…"), target: self, action: #selector(runUninstall))
        uninstall.contentTintColor = .systemRed
        let dangerRow = NSStackView(views: [
            windowLabel(t("Removes PostForge, its credentials, your Postiz data and all media from this Mac. Export a backup first: without one, everything is lost.",
                          "Quita PostForge, sus credenciales, tus datos de Postiz y todos los archivos de PostForge en este Mac. Exporta un respaldo antes: sin él, todo se pierde."),
                        size: 12, color: .secondaryLabelColor, lines: 4, width: 330), uninstall])
        dangerRow.spacing = 14
        dangerRow.alignment = .centerY
        let dangerPanel = Panel(dangerRow, insets: NSEdgeInsets(top: 14, left: 16, bottom: 14, right: 16))
        dangerPanel.layer?.borderColor = NSColor.systemRed.withAlphaComponent(0.45).cgColor

        let sections: [NSView] = [header, sectionCaption(t("Export a backup", "Exportar un respaldo")), exportPanel,
                                  sectionCaption(t("Restore a backup", "Restaurar un respaldo")), restorePanel,
                                  sectionCaption(t("Remove PostForge", "Quitar PostForge")), dangerPanel]
        let main = layoutSections(sections, in: root)
        main.setCustomSpacing(18, after: header)
        for caption in [sections[1], sections[3], sections[5]] { main.setCustomSpacing(6, after: caption) }
        main.setCustomSpacing(18, after: exportPanel)
        main.setCustomSpacing(18, after: restorePanel)
        window.contentView = root
        updateFolderLabels()
    }

    func updateFolderLabels() {
        exportFolderLabel.stringValue = exportFolder.path.replacingOccurrences(of: NSHomeDirectory(), with: "~")
        if let folder = restoreFolder { restoreFolderLabel.stringValue = folder.path.replacingOccurrences(of: NSHomeDirectory(), with: "~") }
    }

    @objc func chooseExportFolder() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = true
        panel.directoryURL = exportFolder
        panel.prompt = t("Choose", "Elegir")
        panel.message = t("PostForge creates a PostForge-migration folder inside the one you choose.",
                          "PostForge crea una carpeta PostForge-migration dentro de la que elijas.")
        if panel.runModal() == .OK, let url = panel.url { exportFolder = url; updateFolderLabels() }
    }

    @objc func chooseRestoreFolder() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.directoryURL = URL(fileURLWithPath: NSHomeDirectory() + "/Desktop")
        panel.prompt = t("Choose", "Elegir")
        panel.message = t("Select the PostForge-migration folder created by Export.",
                          "Selecciona la carpeta PostForge-migration creada con Exportar.")
        if panel.runModal() == .OK, let url = panel.url { restoreFolder = url; updateFolderLabels() }
    }

    func setStatus(_ label: NSTextField, _ text: String, error: Bool = false) {
        label.stringValue = text
        label.textColor = error ? .systemRed : .secondaryLabelColor
    }

    func progress(from line: String) -> String? {
        guard line.hasPrefix("STEP ") else { return nil }
        let parts = line.dropFirst(5).split(separator: " ", maxSplits: 1).map(String.init)
        guard parts.count == 2 else { return nil }
        let translations = [
            "Encrypting credentials and gateway settings": "Cifrando credenciales y ajustes de acceso",
            "Exporting Postiz data": "Exportando datos de Postiz",
            "Verifying backup": "Verificando el respaldo",
            "Validating backup credentials": "Validando las credenciales del respaldo",
            "Restoring Postiz and gateway data": "Restaurando datos de Postiz y del acceso seguro",
            "Finishing": "Finalizando",
        ]
        let label = t(parts[1], translations[parts[1]] ?? parts[1])
        return "\(parts[0].replacingOccurrences(of: "/", with: " / ")) · \(label)"
    }

    @objc func runExport() {
        let pass = exportPass.stringValue
        guard pass.count >= 12 else {
            return setStatus(exportStatus, t("Use a passphrase of at least 12 characters.", "Usa una contraseña de al menos 12 caracteres."), error: true)
        }
        guard pass == exportPass2.stringValue else {
            return setStatus(exportStatus, t("The two passphrases don't match.", "Las dos contraseñas no coinciden."), error: true)
        }
        let stamp = ISO8601DateFormatter().string(from: Date()).replacingOccurrences(of: ":", with: "")
            .replacingOccurrences(of: "-", with: "").replacingOccurrences(of: "T", with: "-").prefix(13)
        let out = exportFolder.appendingPathComponent("PostForge-migration-" + stamp).path
        exportButton.isEnabled = false
        revealButton.isHidden = true
        exportSpinner.startAnimation(nil)
        delegate.windowWork += 1
        setStatus(exportStatus, t("Starting…", "Iniciando…"))
        let dir = project
        DispatchQueue.global(qos: .userInitiated).async {
            let (code, output) = runStreaming(["/bin/bash", dir + "/scripts/migrate.sh", "export", out], in: dir,
                                              extraEnv: ["PM_PASSPHRASE": pass], timeout: 1800) { line in
                if let text = self.progress(from: line) {
                    DispatchQueue.main.async { self.setStatus(self.exportStatus, text) }
                }
            }
            DispatchQueue.main.async {
                self.exportSpinner.stopAnimation(nil)
                self.delegate.windowWork -= 1
                self.exportButton.isEnabled = true
                self.delegate.log("migration export -> exit \(code)\n\(output)")
                if code == 0 {
                    self.lastExportPath = out
                    self.delegate.recordBackup(path: out)
                    self.exportPass.stringValue = ""
                    self.exportPass2.stringValue = ""
                    self.revealButton.isHidden = false
                    self.setStatus(self.exportStatus, self.t("Backup ready. Keep the passphrase safe.", "Respaldo listo. Guarda bien la contraseña."))
                    self.exportStatus.textColor = .systemGreen
                } else {
                    let summary = failureSummary(output)
                    self.setStatus(self.exportStatus, self.t("The export failed. Nothing was changed.", "La exportación falló. No se cambió nada."), error: true)
                    self.delegate.alert(self.t("The export failed", "La exportación falló"),
                                        summary.isEmpty ? self.t("See Open Log in the PostForge menu.", "Consulta Abrir registro en el menú de PostForge.") : summary)
                }
            }
        }
    }

    @objc func revealExport() {
        if let path = lastExportPath { NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)]) }
    }

    @objc func runRestore() {
        guard let folder = restoreFolder else {
            return setStatus(restoreStatus, t("Choose the backup folder first.", "Elige primero la carpeta del respaldo."), error: true)
        }
        let pass = restorePass.stringValue
        guard !pass.isEmpty else {
            return setStatus(restoreStatus, t("Enter the backup's passphrase.", "Escribe la contraseña del respaldo."), error: true)
        }
        guard delegate.ask(t("Replace this Mac's PostForge data?", "¿Reemplazar los datos de PostForge de este Mac?"),
                           t("Restoring replaces your credentials, Postiz data and any gateway settings included in the backup. PostForge will stop during the restore.",
                             "La restauración reemplaza tus credenciales, los datos de Postiz y los ajustes de acceso seguro que estén en el respaldo. PostForge se detendrá durante el proceso."),
                           safe: t("Cancel", "Cancelar"), risky: t("Replace and Restore", "Reemplazar y restaurar")) else { return }
        restoreButton.isEnabled = false
        restoreSpinner.startAnimation(nil)
        delegate.windowWork += 1
        setStatus(restoreStatus, t("Checking backup…", "Revisando el respaldo…"))
        let dir = project
        DispatchQueue.global(qos: .userInitiated).async {
            let (code, output) = runStreaming(["/bin/bash", dir + "/scripts/migrate.sh", "import", folder.path, "--skip-installer", "--replace", "--stop-first"],
                                              in: dir, extraEnv: ["PM_PASSPHRASE": pass], timeout: 1800) { line in
                if let text = self.progress(from: line) {
                    DispatchQueue.main.async { self.setStatus(self.restoreStatus, text) }
                }
            }
            DispatchQueue.main.async {
                self.restoreSpinner.stopAnimation(nil)
                self.delegate.windowWork -= 1
                self.restoreButton.isEnabled = true
                self.delegate.log("migration import -> exit \(code)\n\(output)")
                if code == 0 {
                    self.restorePass.stringValue = ""
                    self.setStatus(self.restoreStatus, self.t("Restored.", "Restaurado."))
                    self.restoreStatus.textColor = .systemGreen
                    self.delegate.alert(self.t("Backup restored", "Respaldo restaurado"),
                                        self.t("Turn PostForge on, verify pending posts in Postiz, and link WhatsApp again by QR if you use it.",
                                               "Enciende PostForge, verifica las publicaciones pendientes en Postiz y vuelve a vincular WhatsApp con QR si lo usas."))
                } else {
                    self.setStatus(self.restoreStatus, self.t("The restore failed.", "La restauración falló."), error: true)
                    self.delegate.alert(self.t("The restore failed", "La restauración falló"), failureSummary(output))
                }
                self.delegate.poll()
            }
        }
    }

    @objc func runUninstall() { delegate.uninstallPostForge() }
}

// MARK: - WhatsApp review window

/// Plans waiting for approval (with an editable caption) and the receipts of the last Status.
final class WhatsAppWindow: NSObject {
    struct Plan {
        let id: String
        let path: String
        var caption: String
        let when: String
        let where_: String
        let warnings: String
    }

    let delegate: AppDelegate
    let window: NSWindow
    var plans: [Plan] = []
    var index = 0
    var state: MachineState?

    let pager = windowLabel("", size: 12, weight: .medium, color: .secondaryLabelColor)
    let previous = NSButton(image: NSImage(systemSymbolName: "chevron.left", accessibilityDescription: nil) ?? NSImage(), target: nil, action: nil)
    let next = NSButton(image: NSImage(systemSymbolName: "chevron.right", accessibilityDescription: nil) ?? NSImage(), target: nil, action: nil)
    let whenLabel = windowLabel("", size: 13, weight: .medium)
    let whereLabel = windowLabel("", size: 13, weight: .medium)
    let warnings = windowLabel("", size: 12, color: .systemOrange, lines: 3)
    let caption = NSTextView()
    let reject = NSButton(title: "", target: nil, action: nil)
    let approve = NSButton(title: "", target: nil, action: nil)
    let planStatus = windowLabel("", size: 12, color: .secondaryLabelColor)
    let planBody = NSStackView()
    let emptyPlans = NSStackView()
    let receipts = NSTextView()

    func t(_ english: String, _ spanish: String) -> String { delegate.text(english, spanish) }

    init(delegate: AppDelegate) {
        self.delegate = delegate
        window = makeSecondaryWindow(title: "PostForge", height: 700)
        super.init()
        build()
    }

    func show(state: MachineState?) {
        self.state = state
        reload()
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func refresh(_ state: MachineState?) {
        self.state = state
        if window.isVisible { reload() }
    }

    func build() {
        let root = BackgroundView()
        let header = windowHeader(title: "WhatsApp",
                                  subtitle: t("Approve plans before they become drafts, and see who received your Status",
                                              "Aprueba planes antes de que sean borradores y mira quién recibió tu Estado"))

        previous.target = self
        previous.action = #selector(showPrevious)
        next.target = self
        next.action = #selector(showNext)
        for button in [previous, next] { button.bezelStyle = .rounded; button.controlSize = .small }
        let pagerRow = NSStackView(views: [pager, flexibleSpacer(), previous, next])
        pagerRow.spacing = 6
        pagerRow.alignment = .centerY
        let whenRow = NSStackView(views: [windowLabel(t("When", "Cuándo"), size: 12, color: .secondaryLabelColor), whenLabel])
        let whereRow = NSStackView(views: [windowLabel(t("Where", "Dónde"), size: 12, color: .secondaryLabelColor), whereLabel])
        for row in [whenRow, whereRow] {
            row.spacing = 10
            row.alignment = .firstBaseline
            (row.arrangedSubviews[0] as? NSTextField)?.setContentHuggingPriority(.required, for: .horizontal)
            (row.arrangedSubviews[0] as? NSTextField)?.widthAnchor.constraint(equalToConstant: 56).isActive = true
        }
        whereLabel.lineBreakMode = .byTruncatingTail
        let captionBox = NSScrollView()
        captionBox.hasVerticalScroller = true
        captionBox.autohidesScrollers = true
        captionBox.drawsBackground = false
        captionBox.borderType = .noBorder
        captionBox.documentView = caption
        caption.drawsBackground = false
        caption.isRichText = false
        caption.font = .systemFont(ofSize: 13)
        caption.textColor = .labelColor
        caption.textContainerInset = NSSize(width: 8, height: 8)
        caption.autoresizingMask = [.width]
        caption.isVerticallyResizable = true
        caption.textContainer?.widthTracksTextView = true
        let captionPanel = Panel(captionBox, insets: NSEdgeInsets(), style: .input)
        captionPanel.heightAnchor.constraint(equalToConstant: 120).isActive = true
        reject.title = t("Reject", "Rechazar")
        reject.target = self
        reject.action = #selector(rejectPlan)
        approve.title = t("Approve", "Aprobar")
        approve.target = self
        approve.action = #selector(approvePlan)
        approve.keyEquivalent = "\r"
        planStatus.lineBreakMode = .byTruncatingTail
        planStatus.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        let actions = NSStackView(views: [planStatus, flexibleSpacer(), reject, approve])
        actions.spacing = 10
        actions.alignment = .centerY
        planBody.orientation = .vertical
        planBody.alignment = .leading
        planBody.spacing = 10
        for view in [pagerRow, whenRow, whereRow, windowLabel(t("Caption (you can edit it)", "Texto (puedes editarlo)"), size: 12, color: .secondaryLabelColor),
                     captionPanel, warnings, actions] {
            planBody.addArrangedSubview(view)
            if !(view is NSTextField) { view.widthAnchor.constraint(equalTo: planBody.widthAnchor).isActive = true }
        }
        let emptyIcon = NSImageView(image: NSImage(systemSymbolName: "checkmark.bubble", accessibilityDescription: nil) ?? NSImage())
        emptyIcon.symbolConfiguration = NSImage.SymbolConfiguration(pointSize: 24, weight: .light)
        emptyIcon.contentTintColor = .tertiaryLabelColor
        let emptyHint = windowLabel(t("Send a request to your own WhatsApp chat and the plan will appear here for approval.",
                                      "Envía una solicitud a tu propio chat de WhatsApp y el plan aparecerá aquí para aprobarlo."),
                                    size: 12, color: .tertiaryLabelColor, lines: 3)
        emptyHint.alignment = .center
        emptyPlans.setViews([emptyIcon, windowLabel(t("No plans are waiting", "No hay planes esperando"), size: 13, weight: .medium, color: .secondaryLabelColor),
                             emptyHint], in: .center)
        emptyPlans.orientation = .vertical
        emptyPlans.alignment = .centerX
        emptyPlans.spacing = 6
        let planHolder = NSStackView(views: [planBody, emptyPlans])
        planHolder.orientation = .vertical
        planHolder.alignment = .leading
        planBody.widthAnchor.constraint(equalTo: planHolder.widthAnchor).isActive = true
        emptyPlans.widthAnchor.constraint(equalTo: planHolder.widthAnchor).isActive = true
        let planPanel = Panel(planHolder, insets: NSEdgeInsets(top: 14, left: 16, bottom: 14, right: 16))

        let receiptsBox = NSScrollView()
        receiptsBox.hasVerticalScroller = true
        receiptsBox.autohidesScrollers = true
        receiptsBox.drawsBackground = false
        receiptsBox.borderType = .noBorder
        receiptsBox.documentView = receipts
        receipts.drawsBackground = false
        receipts.isEditable = false
        receipts.isRichText = false
        receipts.font = .systemFont(ofSize: 13)
        receipts.textColor = .labelColor
        receipts.textContainerInset = NSSize(width: 10, height: 10)
        receipts.autoresizingMask = [.width]
        receipts.isVerticallyResizable = true
        receipts.textContainer?.widthTracksTextView = true
        let receiptsPanel = Panel(receiptsBox, insets: NSEdgeInsets(), style: .output)
        receiptsPanel.heightAnchor.constraint(greaterThanOrEqualToConstant: 120).isActive = true
        receiptsPanel.setContentHuggingPriority(NSLayoutConstraint.Priority(1), for: .vertical)

        let manager = NSButton(title: t("Open WhatsApp Manager", "Abrir WhatsApp Manager"), target: self, action: #selector(openManager))
        manager.controlSize = .small
        let footer = NSStackView(views: [flexibleSpacer(), manager])
        footer.alignment = .centerY

        let plansCaption = sectionCaption(t("Plans awaiting your approval", "Planes esperando tu aprobación"))
        let receiptsCaption = sectionCaption(t("Status receipts", "Confirmaciones del Estado"))
        let sections: [NSView] = [header, plansCaption, planPanel, receiptsCaption, receiptsPanel, footer]
        let main = layoutSections(sections, in: root)
        main.bottomAnchor.constraint(equalTo: root.bottomAnchor).isActive = true
        main.setCustomSpacing(18, after: header)
        main.setCustomSpacing(6, after: plansCaption)
        main.setCustomSpacing(6, after: receiptsCaption)
        main.setCustomSpacing(18, after: planPanel)
        main.setCustomSpacing(14, after: receiptsPanel)
        window.contentView = root
        reload()
    }

    func loadPlans() -> [Plan] {
        let folder = delegate.project + "/run/wa-confirmations"
        let names = ((try? FileManager.default.contentsOfDirectory(atPath: folder)) ?? []).filter { $0.hasSuffix(".json") }
        func modified(_ name: String) -> Date {
            (try? FileManager.default.attributesOfItem(atPath: folder + "/" + name)[.modificationDate] as? Date) ?? .distantPast
        }
        return names.sorted { modified($0) > modified($1) }.compactMap { name in
            let path = folder + "/" + name
            guard let data = FileManager.default.contents(atPath: path),
                  let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return nil }
            let result = json["result"] as? [String: Any]
            let targets = (result?["targets"] as? [[String: Any]] ?? []).map { target -> String in
                let network = target["network"] as? String ?? ""
                let channel = target["channel"] as? String ?? ""
                return channel.isEmpty ? network : "\(network) · \(channel)"
            }
            let edited = (json["caption_override"] as? String) ?? (result?["caption"] as? String) ?? ""
            return Plan(id: (json["id"] as? String) ?? name.replacingOccurrences(of: ".json", with: ""), path: path,
                        caption: edited, when: (result?["when_utc"] as? String).map { shortDate(iso: $0) } ?? (result?["when_local"] as? String ?? "—"),
                        where_: targets.isEmpty ? "WhatsApp Status" : targets.joined(separator: ", "),
                        warnings: (result?["warnings"] as? [String] ?? []).map { "⚠ " + $0 }.joined(separator: "\n"))
        }
    }

    func reload() {
        let editing = plans.indices.contains(index) ? plans[index] : nil
        let edited = caption.string
        plans = loadPlans()
        index = min(index, max(plans.count - 1, 0))
        if let editing = editing, let same = plans.firstIndex(where: { $0.id == editing.id }) { index = same }
        showPlan()
        if let editing = editing, plans.indices.contains(index), plans[index].id == editing.id,
           edited != editing.caption { caption.string = edited }
        showReceipts()
    }

    func showPlan() {
        let has = !plans.isEmpty
        planBody.isHidden = !has
        emptyPlans.isHidden = has
        guard has else { return }
        let plan = plans[index]
        pager.stringValue = t("Plan \(index + 1) of \(plans.count)", "Plan \(index + 1) de \(plans.count)")
        previous.isEnabled = index > 0
        next.isEnabled = index < plans.count - 1
        whenLabel.stringValue = plan.when
        whereLabel.stringValue = plan.where_
        caption.string = plan.caption
        warnings.stringValue = plan.warnings
        warnings.isHidden = plan.warnings.isEmpty
        planStatus.stringValue = ""
    }

    func showReceipts() {
        var lines: [String] = []
        if let last = state?.lastStatus {
            lines.append("“" + last.text.split(whereSeparator: \.isNewline).joined(separator: " ").prefix(120) + "”")
            lines.append(shortDate(Date(timeIntervalSince1970: TimeInterval(last.ts))))
            lines.append("")
            lines.append(t("Received by \(last.received) · viewed by \(last.viewed)", "Recibido por \(last.received) · visto por \(last.viewed)"))
            let names = last.viewerNames ?? []
            if names.isEmpty {
                lines.append(t("No views yet. Views show only if both phones have read receipts on.",
                               "Aún no hay vistas. Solo aparecen si ambos teléfonos tienen confirmaciones de lectura activadas."))
            } else {
                lines.append("")
                lines += names.map { "👁  " + $0 }
                if last.viewed > names.count { lines.append(t("… and \(last.viewed - names.count) more", "… y \(last.viewed - names.count) más")) }
            }
        } else {
            lines.append(t("No Status has been sent yet, or PostForge is off.", "Aún no se ha enviado ningún Estado, o PostForge está apagado."))
        }
        receipts.string = lines.joined(separator: "\n")
    }

    @objc func showPrevious() { index = max(0, index - 1); showPlan() }
    @objc func showNext() { index = min(plans.count - 1, index + 1); showPlan() }
    @objc func openManager() { delegate.openEvolution() }

    /// Writes an edited caption into the saved plan; approval then uses it as the exact text.
    func saveCaptionIfChanged(_ plan: Plan) -> Bool {
        let edited = caption.string.trimmingCharacters(in: .whitespacesAndNewlines)
        guard edited != plan.caption.trimmingCharacters(in: .whitespacesAndNewlines) else { return true }
        guard let data = FileManager.default.contents(atPath: plan.path),
              var json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return false }
        json["caption_override"] = edited
        guard let out = try? JSONSerialization.data(withJSONObject: json, options: [.prettyPrinted]),
              (try? out.write(to: URL(fileURLWithPath: plan.path), options: .atomic)) != nil else { return false }
        return true
    }

    @objc func approvePlan() {
        guard plans.indices.contains(index) else { return }
        let plan = plans[index]
        guard saveCaptionIfChanged(plan) else {
            planStatus.stringValue = t("Couldn't save your caption.", "No se pudo guardar tu texto.")
            planStatus.textColor = .systemRed
            return
        }
        approve.isEnabled = false
        planStatus.stringValue = t("Sending approval…", "Enviando aprobación…")
        planStatus.textColor = .secondaryLabelColor
        let dir = delegate.project
        DispatchQueue.global(qos: .userInitiated).async {
            let result = runCommand(["/usr/bin/python3", dir + "/scripts/lib/wa_inbox.py", "--send-plan-approval", plan.id],
                                    in: dir, timeout: 60)
            DispatchQueue.main.async {
                self.approve.isEnabled = true
                self.delegate.log("send approval plan \(plan.id) -> exit \(result.0)\n\(result.1)")
                if result.0 == 0 {
                    self.planStatus.stringValue = self.t("Approval sent to your WhatsApp chat. Drafts appear in Postiz shortly.",
                                                         "Aprobación enviada a tu chat de WhatsApp. Los borradores aparecerán pronto en Postiz.")
                    self.planStatus.textColor = .systemGreen
                    DispatchQueue.main.asyncAfter(deadline: .now() + 4) { self.delegate.poll(); self.reload() }
                } else {
                    self.planStatus.stringValue = self.t("Couldn't send the approval.", "No se pudo enviar la aprobación.")
                    self.planStatus.textColor = .systemRed
                    self.delegate.alert(self.t("Couldn't send the approval", "No se pudo enviar la aprobación"),
                                        failureSummary(result.1).isEmpty ? self.t("Is WhatsApp connected? See Open Log in the menu.", "¿Está WhatsApp conectado? Consulta Abrir registro en el menú.") : failureSummary(result.1))
                }
            }
        }
    }

    @objc func rejectPlan() {
        guard plans.indices.contains(index) else { return }
        let plan = plans[index]
        guard delegate.ask(t("Reject this plan?", "¿Rechazar este plan?"),
                           t("It is deleted and no drafts are created.", "Se elimina y no se crean borradores."),
                           safe: t("Keep", "Conservar"), risky: t("Reject Plan", "Rechazar plan")) else { return }
        let result = runCommand(["/usr/bin/python3", delegate.project + "/scripts/lib/wa_inbox.py", "--reject-plan", plan.id],
                                in: delegate.project, timeout: 30)
        delegate.log("reject plan \(plan.id) -> exit \(result.0)\n\(result.1)")
        delegate.poll()
        reload()
    }
}


// Static UI copy in Ecuadorian Spanish; used to relabel open windows in place.
let uiSpanish: [String: String] = [
    "A post failed": "Una publicación falló",
    "About PostForge": "Acerca de PostForge",
    "Add your idea and press Bake idea. Nothing is published until you approve it in Postiz.": "Escribe tu idea y pulsa Hornea la idea. Nada se publica hasta que lo apruebes en Postiz.",
    "Allow Notifications (off in System Settings)…": "Permitir notificaciones (desactivadas en Configuración del Sistema)…",
    "Allow Notifications…": "Permitir notificaciones…",
    "Apply stable Docker updates?": "¿Actualizar los componentes de Docker?",
    "Approval sent to your WhatsApp chat. Drafts appear in Postiz shortly.": "Aprobación enviada a tu chat de WhatsApp. Los borradores aparecerán pronto en Postiz.",
    "Approve": "Aprobar",
    "Approve plans before they become drafts, and see who received your Status": "Aprueba planes antes de que sean borradores y mira quién recibió tu Estado",
    "Backup": "Respaldo",
    "Backup & Move": "Respaldo y traslado",
    "Backup & Move…": "Respaldo y traslado…",
    "Backup ready. Keep the passphrase safe.": "Respaldo listo. Guarda bien la contraseña.",
    "Backup restored": "Respaldo restaurado",
    "Behavior": "Comportamiento",
    "Brings back the credentials and Postiz data from a backup folder made by Export. This replaces what is on this Mac now. WhatsApp must be linked again by QR.": "Recupera las credenciales y los datos de Postiz de una carpeta creada con Exportar. Reemplaza lo que hay ahora en este Mac. WhatsApp debe vincularse de nuevo con QR.",
    "Can't check what's waiting": "No se pudieron revisar los envíos pendientes",
    "Can't read status": "No se puede leer el estado",
    "Can't read the machine state": "No se puede leer el estado de los servicios",
    "Cancel": "Cancelar",
    "Cancel Shutdown": "Cancelar apagado",
    "Cannot read .env": "No se puede leer .env",
    "Caption (you can edit it)": "Texto (puedes editarlo)",
    "Channels": "Canales",
    "Check complete. Available updates appear in the tray menu.": "Revisión terminada. Las actualizaciones disponibles aparecen en el menú de la barra.",
    "Check for Updates…": "Buscar actualizaciones…",
    "Check the project configuration.": "Revisa la configuración del proyecto.",
    "Check your network connection or install manually from the release page.": "Revisa la conexión o instala manualmente desde la página de la versión.",
    "Checking for updates…": "Buscando actualizaciones…",
    "Checking…": "Comprobando…",
    "Choose": "Elegir",
    "Choose the backup folder first.": "Elige primero la carpeta del respaldo.",
    "Choose…": "Elegir…",
    "Clear": "Quitar",
    "Close": "Cerrar",
    "Coming up": "Próximamente",
    "Completed. PostForge status is refreshing.": "Listo. Actualizando el estado de PostForge.",
    "Configure test numbers…": "Configurar números de prueba…",
    "Connection dates from saved status": "Fechas de conexión del último estado guardado",
    "Continue…": "Continuar…",
    "Copy": "Copiar",
    "Could not complete. Open the log for details and recovery instructions.": "No se pudo completar. Abre el registro para ver los detalles y los pasos de recuperación.",
    "Could not save status audience": "No se pudo guardar la audiencia",
    "Could not save test numbers": "No se pudieron guardar los números de prueba",
    "Couldn't change Open at Login": "No se pudo cambiar Abrir al iniciar sesión",
    "Couldn't save tunnel URL": "No se pudo guardar la URL del túnel",
    "Couldn't save your caption.": "No se pudo guardar tu texto.",
    "Couldn't send the approval": "No se pudo enviar la aprobación",
    "Couldn't send the approval.": "No se pudo enviar la aprobación.",
    "Approve Status…": "Aprobar Estado…",
    "Final hashtag…": "Etiqueta final…",
    "Create drafts for": "Crear borradores de",
    "Video cover": "Portada del video",
    "Choose image…": "Elegir imagen…",
    "Edit cover…": "Editar portada…",
    "Second": "Segundo",
    "Enter a second in the video, such as 12.5.": "Ingresa un segundo del video, por ejemplo 12,5.",
    "Create Drafts": "Crear borradores",
    "Saves encrypted credentials, gateway access settings if configured, and a verified Postiz export. Keep the folder private because the Postiz archive contains channel tokens.": "Guarda tus credenciales cifradas, los ajustes de acceso seguro si están configurados y un respaldo verificado de Postiz. Mantén la carpeta en privado porque el respaldo de Postiz contiene tokens de tus canales.",
    "Cut": "Cortar",
    "Default: 30 days. This sets the cleanup age for logs and unused uploaded media. Cleanup requires a separate review and apply command; changing this value deletes nothing. Scheduled posts and the database are preserved.": "Por defecto: 30 días. Define la antigüedad para limpiar registros y archivos subidos que ya no se usan. Debes revisar y ejecutar la limpieza por separado; cambiar este valor no borra nada. Se conservan la base de datos y las publicaciones programadas.",
    "Dictate": "Dictar",
    "Dictation isn't on. Turn it on in System Settings → Keyboard → Dictation, then press the dictation key.": "El dictado está desactivado. Actívalo en Configuración del Sistema → Teclado → Dictado y presiona la tecla de dictado.",
    "Download and install the stable package. Running PostForge services and the tray app may restart briefly.": "Descarga e instala el paquete estable. Los servicios activos de PostForge y la app pueden reiniciarse brevemente.",
    "Downloading update…": "Descargando actualización…",
    "Drafts": "Borradores",
    "Drop photos or videos here": "Suelta fotos o videos aquí",
    "Edit": "Edición",
    "Enter a whole number from 1 to 36500.": "Ingresa un número entero entre 1 y 36500.",
    "Enter country-code numbers separated by commas, without + signs.\nExample: 593991234567,593998765432": "Ingresa números con código de país separados por comas, sin signos +.\nEjemplo: 593991234567,593998765432",
    "Enter the HTTPS domain used by ngrok or your custom domain. Postiz will briefly restart. If verification fails, PostForge will restore the previous URL. Update your providers’ OAuth callback URLs for the new domain.": "Escribe el dominio HTTPS de ngrok o tu dominio personalizado. Las URL relacionadas de Postiz se actualizarán juntas; reinicia después.",
    "Enter the backup's passphrase.": "Escribe la contraseña del respaldo.",
    "Everything is sent": "Se envió todo",
    "Export Backup": "Exportar respaldo",
    "Export Backup First…": "Exportar respaldo primero…",
    "Export a backup": "Exportar un respaldo",
    "Final confirmation": "Confirmación final",
    "Hide Others": "Ocultar otros",
    "Hide PostForge": "Ocultar PostForge",
    "I understand that without a backup everything is lost forever": "Entiendo que sin respaldo todo se pierde para siempre",
    "I understand this cannot be undone": "Entiendo que esto no se puede deshacer",
    "In queue": "En cola",
    "Install Update": "Instalar actualización",
    "Installing… macOS may request your password.": "Instalando… macOS puede pedirte la contraseña.",
    "Invalid days": "Cantidad de días inválida",
    "Invalid test numbers": "Números de prueba inválidos",
    "Is WhatsApp connected? See Open Log in the menu.": "¿Está WhatsApp conectado? Consulta Abrir registro en el menú.",
    "It is deleted and no drafts are created.": "Se elimina y no se crean borradores.",
    "Keep": "Conservar",
    "Keep Mac Awake While Posts Wait": "Mantener Mac activa mientras espera",
    "Keep Running": "Mantener encendido",
    "Language": "Idioma",
    "Local AI → preview → your approval": "IA local → vista previa → tu aprobación",
    "Maintenance": "Mantenimiento",
    "Media + your idea\nApp window · WhatsApp self-chat": "Archivos + tu idea\nVentana de la app · Chat contigo en WhatsApp",
    "Minimize": "Minimizar",
    "Needs attention": "Requiere atención",
    "Needs your attention": "Requiere tu atención",
    "New Post…": "Nueva publicación…",
    "Next post": "Próxima",
    "No Status has been sent yet, or PostForge is off.": "Aún no se ha enviado ningún Estado, o PostForge está apagado.",
    "No backup folder chosen": "Ninguna carpeta elegida",
    "No files yet": "Sin archivos",
    "No plans are waiting": "No hay planes esperando",
    "No scheduled posts waiting": "No hay publicaciones programadas pendientes",
    "No views yet. Views show only if both phones have read receipts on.": "Aún no hay vistas. Solo aparecen si ambos teléfonos tienen confirmaciones de lectura activadas.",
    "Nothing is waiting. You can turn PostForge off.": "No hay envíos pendientes. Puedes apagar PostForge.",
    "Nothing scheduled": "Nada programado",
    "Nothing was removed": "No se eliminó nada",
    "Nothing was waiting to be sent.": "No había envíos pendientes.",
    "Off": "Apagado",
    "Off (Docker Desktop not running)": "Apagado (Docker Desktop no está abierto)",
    "On: nothing waiting (idle)": "Encendido: sin envíos pendientes (inactivo)",
    "Open Log": "Abrir registro",
    "Open Postiz Calendar": "Abrir calendario de Postiz",
    "Open Postiz to see what went wrong.": "Abre Postiz para revisar qué pasó.",
    "Open WhatsApp Manager": "Abrir WhatsApp Manager",
    "Open at Login": "Abrir al iniciar sesión",
    "Open the tray menu to review them. Host tools remain manual; the approved action updates the Docker stack.": "Abre el menú de la barra para revisarlas. Las herramientas del sistema se actualizan por separado; esta acción actualiza los componentes de Docker.",
    "Automatic renewal available for other channels": "Otros canales admiten renovación automática",
    "Partly running: use Turn On to restore all services": "Funcionamiento parcial: usa Encender para restaurar los servicios",
    "Passphrase (at least 12 characters)": "Contraseña (mínimo 12 caracteres)",
    "Passphrase of the backup": "Contraseña del respaldo",
    "Paste": "Pegar",
    "Photos & videos": "Fotos y videos",
    "Plan a post, approve it in Postiz": "Planea una publicación y apruébala en Postiz",
    "Plans awaiting your approval": "Planes esperando tu aprobación",
    "Post": "Publicación",
    "PostForge Updates & Progress": "PostForge: actualizaciones y progreso",
    "PostForge creates a PostForge-migration folder inside the one you choose.": "PostForge crea una carpeta PostForge-migration dentro de la que elijas.",
    "PostForge didn't restart cleanly": "PostForge no se reinició correctamente",
    "PostForge didn't start": "PostForge no pudo encenderse",
    "PostForge didn't stop cleanly": "PostForge no se apagó correctamente",
    "PostForge is idle": "PostForge está inactivo",
    "PostForge is off": "PostForge está apagado",
    "PostForge is on": "PostForge está encendido",
    "PostForge update is available": "Hay una actualización de PostForge disponible",
    "PostForge updated": "PostForge actualizado",
    "PostForge was uninstalled": "PostForge se desinstaló",
    "Postiz drafts → review & schedule": "Borradores en Postiz → revisión y programación",
    "Postiz, WhatsApp and the tunnel are up.": "Postiz, WhatsApp y el túnel están funcionando.",
    "Posts already published on your social networks are not touched. Docker Desktop stays installed.": "Las publicaciones ya publicadas en tus redes no se tocan. Docker Desktop sigue instalado.",
    "Preview": "Vista previa",
    "👨‍🍳 Bake idea": "👨‍🍳 Hornea la idea",
    "Preview the plan first. Nothing will be created until you confirm it.": "Revisa primero la vista previa del plan. No se creará nada hasta que lo confirmes.",
    "Private: test recipients": "Privado: destinatarios de prueba",
    "Public: all contacts": "Público: todos los contactos",
    "Quit PostForge": "Salir de PostForge",
    "Quit PostForge (posting keeps running)": "Salir de PostForge (sigue publicando)",
    "Ready to post": "Listo para publicar",
    "Redo": "Rehacer",
    "Reject": "Rechazar",
    "Reject Plan": "Rechazar plan",
    "Reject this plan?": "¿Rechazar este plan?",
    "Remind Me Before Posts When Off": "Recordarme antes de publicar apagado",
    "Remove PostForge": "Quitar PostForge",
    "Removes PostForge, its credentials, your Postiz data and all media from this Mac. Export a backup first: without one, everything is lost.": "Quita PostForge, sus credenciales, tus datos de Postiz y todos los archivos de PostForge en este Mac. Exporta un respaldo antes: sin él, todo se pierde.",
    "Removing PostForge…": "Quitando PostForge…",
    "Repeat the passphrase": "Repite la contraseña",
    "Replace and Restore": "Reemplazar y restaurar",
    "Replace this Mac's PostForge data?": "¿Reemplazar los datos de PostForge de este Mac?",
    "Restart Everything…": "Reiniciar todo…",
    "Restart Now": "Reiniciar ahora",
    "Restart PostForge to apply it.": "Reinicia PostForge para aplicarla.",
    "Restart PostForge?": "¿Reiniciar PostForge?",
    "Restarting everything…": "Reiniciando todo…",
    "Restore All Services": "Restaurar todos los servicios",
    "Restore a backup": "Restaurar un respaldo",
    "Restored.": "Restaurado.",
    "Restore…": "Restaurar…",
    "Restoring replaces your credentials, Postiz data and any gateway settings included in the backup. PostForge will stop during the restore.": "La restauración reemplaza tus credenciales, los datos de Postiz y los ajustes de acceso seguro que estén en el respaldo. PostForge se detendrá durante el proceso.",
    "Running": "En marcha",
    "Save": "Guardar",
    "Save to": "Guardar en",
    "Save your data, restore it, or remove PostForge": "Guarda tus datos, restáuralos o quita PostForge",
    "Saved history retention": "Tiempo de conservación del historial",
    "Say where, when, and your idea first.": "Primero indica las redes, la fecha, la hora y tu idea.",
    "Scheduled posts won't publish. Turn PostForge off and on again.": "Las publicaciones programadas no se enviarán. Apaga y vuelve a encender PostForge.",
    "Scheduler stopped": "El programador se detuvo",
    "See Open Log in the PostForge menu.": "Consulta Abrir registro en el menú de PostForge.",
    "See Open Log in the menu bar app.": "Abre el registro desde el menú de la barra.",
    "Select All": "Seleccionar todo",
    "Select the PostForge-migration folder created by Export.": "Selecciona la carpeta PostForge-migration creada con Exportar.",
    "Send a request to your own WhatsApp chat and the plan will appear here for approval.": "Envía una solicitud a tu propio chat de WhatsApp y el plan aparecerá aquí para aprobarlo.",
    "Sending approval…": "Enviando aprobación…",
    "Settings & Tools": "Ajustes y herramientas",
    "Show in Finder": "Mostrar en Finder",
    "Shut Down Anyway": "Apagar de todas formas",
    "Stable Updates Available…": "Actualizaciones estables disponibles…",
    "Stable updates are available": "Hay actualizaciones estables disponibles",
    "Starting…": "Iniciando…",
    "Status receipts": "Confirmaciones del Estado",
    "Stopping PostForge…": "Deteniendo PostForge…",
    "Stopping…": "Apagando…",
    "Temporal → connected social channels": "Temporal → redes sociales conectadas",
    "Test WhatsApp recipients": "Destinatarios de prueba de WhatsApp",
    "The Docker stack was refreshed and health was checked.": "Los componentes de Docker se actualizaron y se verificó su funcionamiento.",
    "The app, its data and its Docker containers were removed. Your published posts are untouched.": "Se quitaron la app, sus datos y sus contenedores de Docker. Tus publicaciones ya publicadas siguen intactas.",
    "The export failed": "La exportación falló",
    "The export failed. Nothing was changed.": "La exportación falló. No se cambió nada.",
    "The restore failed": "La restauración falló",
    "The restore failed.": "La restauración falló.",
    "The stack is turning off to save resources. Docker Desktop and Ollama stay running.": "Los servicios se están apagando para ahorrar recursos. Docker Desktop y Ollama siguen abiertos.",
    "The two passphrases don't match.": "Las dos contraseñas no coinciden.",
    "The uninstall had problems": "La desinstalación tuvo problemas",
    "This permanently removes from this Mac:\n": "Esto elimina de forma permanente de este Mac:\n",
    "Tick the box and type UNINSTALL exactly to confirm.": "Marca la casilla y escribe UNINSTALL exactamente para confirmar.",
    "Download the package from the GitHub release page and run it manually.": "Descarga el paquete desde la página de la versión en GitHub e instálalo manualmente.",
    "Tunnel URL": "URL del túnel",
    "Tunnel URL saved": "URL del túnel guardada",
    "Tunnel URL…": "URL del túnel…",
    "Turn Off Anyway": "Apagar de todas formas",
    "Turn Off…": "Apagar…",
    "Turn On": "Encender",
    "Turn PostForge off anyway?": "¿Apagar PostForge de todas formas?",
    "Turn PostForge on, verify pending posts in Postiz, and link WhatsApp again by QR if you use it.": "Enciende PostForge, verifica las publicaciones pendientes en Postiz y vuelve a vincular WhatsApp con QR si lo usas.",
    "Turning off…": "Apagando…",
    "Turning on…": "Encendiendo…",
    "Type UNINSTALL to remove PostForge and all its data from this Mac.": "Escribe UNINSTALL para quitar PostForge y todos sus datos de este Mac.",
    "Undo": "Deshacer",
    "Uninstall Everything": "Desinstalar todo",
    "Uninstall PostForge?": "¿Desinstalar PostForge?",
    "Uninstall PostForge…": "Desinstalar PostForge…",
    "Uninstall…": "Desinstalar…",
    "Update and Restart": "Actualizar y reiniciar",
    "Update did not complete": "No se completó la actualización",
    "Update download failed": "No se pudo descargar la actualización",
    "Update install failed": "No se pudo instalar la actualización",
    "Updates": "Actualizaciones",
    "Updates Available…": "Actualizaciones disponibles…",
    "Updating safely…": "Actualizando de forma segura…",
    "Use 7–15 digits per number, separated by commas.": "Usa entre 7 y 15 dígitos por número, separados por comas.",
    "Use a passphrase of at least 12 characters.": "Usa una contraseña de al menos 12 caracteres.",
    "Use an HTTPS domain without a path.": "Usa un dominio HTTPS sin ruta.",
    "WhatsApp Plans & Receipts…": "Planes y confirmaciones de WhatsApp…",
    "WhatsApp Status Audience": "Audiencia del estado de WhatsApp",
    "WhatsApp disconnected": "WhatsApp se desconectó",
    "When": "Cuándo",
    "Where": "Dónde",
    "Where, when and your idea. e.g. “Instagram and TikTok tomorrow at 6pm: fresh sourdough”": "Dónde, cuándo y tu idea. Ej.: “Instagram y TikTok mañana a las 6pm: pan de masa madre”",
    "Window": "Ventana",
    "Working…": "Procesando…",
    "You can finish by deleting ~/postforge by hand.": "Puedes terminar borrando ~/postforge a mano.",
    "You will need this passphrase to restore. It can't be recovered if you forget it.": "Necesitarás esta contraseña para restaurar. No se puede recuperar si la olvidas.",
    "Your idea": "Tu idea",
    "Your request": "Tu pedido",
    "Another Caption…": "Otra versión del texto…",
    "Use ‘idea:’ to generate a caption or ‘caption:’ to use your exact words.": "Usa «idea:» para redactar un texto o «texto:» para usar tus palabras tal cual.",
    "Your plan appears here": "Tu plan aparecerá aquí",
    "• The PostForge app and its project folder\n• Your credentials (.env) and settings\n• Every Postiz post, draft, channel and uploaded file\n• The WhatsApp session and all logs\n• The PostForge Docker containers and installer files\n": "• La app PostForge y su carpeta de proyecto\n• Tus credenciales (.env) y ajustes\n• Todas las publicaciones, borradores, canales y archivos de Postiz\n• La sesión de WhatsApp y todos los registros\n• Los contenedores de Docker y los archivos de instalación de PostForge\n",
    "⚠︎ NO BACKUP WAS EXPORTED. If you continue, everything above is lost and cannot be recovered.": "⚠︎ NO SE EXPORTÓ NINGÚN RESPALDO. Si continúas, todo lo anterior se pierde y no se puede recuperar.",
    "⚠︎ Scheduled posts won't publish: scheduler is stopped": "⚠︎ Las publicaciones programadas no saldrán: el programador está detenido",
]

func uiNetwork(_ value: String) -> String {
    value == "Facebook Page" ? ui("Facebook Page", "Página de Facebook") : value
}

func ui(_ english: String, _ spanish: String) -> String {
    UserDefaults.standard.string(forKey: "uiLanguage") == "es" ? spanish : english
}
func localizedUI(_ value: String) -> String {
    if UserDefaults.standard.string(forKey: "uiLanguage") == "es" { return uiSpanish[value] ?? value }
    return uiSpanish.first(where: { $0.value == value })?.key ?? value
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
if CommandLine.arguments.contains("--verify-ui") {
    let defaults = UserDefaults.standard
    let original = defaults.volatileDomain(forName: UserDefaults.argumentDomain)
    defaults.setVolatileDomain(["uiLanguage": "en"], forName: UserDefaults.argumentDomain)
    delegate.newPost = NewPostWindow(project: delegate.project)
    delegate.backupWindow = BackupWindow(delegate: delegate)
    delegate.whatsappWindow = WhatsAppWindow(delegate: delegate)
    delegate.newPost!.instruction.string = "Keep this idea / conserva esta idea"
    delegate.newPost!.media = [URL(fileURLWithPath: "/tmp/keep-this-photo.jpg")]
    defaults.setVolatileDomain(["uiLanguage": "es"], forName: UserDefaults.argumentDomain)
    delegate.refreshLocalizedWindows()
    precondition(delegate.newPost!.preview.title == "👨‍🍳 Hornea la idea")
    precondition(delegate.newPost!.create.title == "Crear borradores")
    precondition(delegate.newPost!.instruction.string == "Keep this idea / conserva esta idea")
    precondition(delegate.newPost!.media.count == 1)
    precondition(localizedUI("Restart Now") == "Reiniciar ahora")
    let trayMenu = NSMenu()
    trayMenu.autoenablesItems = false
    for (language, updates, about) in [
        ("es", "Buscar actualizaciones…", "Acerca de PostForge"),
        ("en", "Check for Updates…", "About PostForge"),
    ] {
        defaults.setVolatileDomain(["uiLanguage": language], forName: UserDefaults.argumentDomain)
        delegate.menuNeedsUpdate(trayMenu)
        precondition(trayMenu.items.dropLast().last?.title == about)
        precondition(trayMenu.items.last?.action == #selector(AppDelegate.quitApp))
        precondition(trayMenu.items.first(where: { $0.title == updates })?.action == #selector(AppDelegate.checkUpdatesFromMenu))
        let draftOptions = trayMenu.items.first {
            $0.title == (language == "es" ? "Opciones de borrador" : "Draft Options")
        }?.submenu
        precondition(draftOptions?.items.filter { $0.action == #selector(AppDelegate.openDraftOption(_:)) }.map(\.tag) == [1, 2, 3, 4, 5])
        let settings = trayMenu.items.compactMap(\.submenu).last!
        let reviewTitle = language == "es" ? "Planes y confirmaciones de WhatsApp…" : "WhatsApp Plans & Receipts…"
        let review = trayMenu.items.first { $0.title == reviewTitle }
        precondition(review?.action == #selector(AppDelegate.reviewWhatsAppPlans) && review?.isEnabled == true)
        precondition(settings.items.allSatisfy { $0.action != #selector(AppDelegate.reviewWhatsAppPlans) })
        precondition(settings.items.allSatisfy { $0.title != updates && $0.title != about })
    }

    let idleFixture = #"{"state":"on","docker":true,"services":{"postiz":true,"evolution":true,"scheduler":true,"tunnel":true},"pending":{"total":0,"scheduled":0,"overdue":0,"jobs":[],"fromCache":false},"scheduled":[],"postizUrl":"https://example.org"}"#
    delegate.state = try! JSONDecoder().decode(MachineState.self, from: Data(idleFixture.utf8))
    defaults.setVolatileDomain(["uiLanguage": "en", "autoStopWhenIdle": true, "idleStopMinutes": 1], forName: UserDefaults.argumentDomain)
    let idleStart = Date()
    precondition(!delegate.idleStopDue(at: idleStart))
    precondition(!delegate.idleStopDue(at: idleStart.addingTimeInterval(59)))
    precondition(delegate.idleStopDue(at: idleStart.addingTimeInterval(60)))
    delegate.windowWork = 1
    precondition(!delegate.idleStopDue(at: idleStart.addingTimeInterval(70)))
    delegate.windowWork = 0
    precondition(!delegate.idleStopDue(at: idleStart.addingTimeInterval(71)))
    delegate.stateError = "test unavailable"
    precondition(!delegate.idleStopDue(at: idleStart.addingTimeInterval(150)))
    delegate.state = nil
    delegate.stateError = nil
    let fixture = #"{"tag_name":"v9.0.0","html_url":"https://github.com/isaacmateosv/postforge/releases/tag/v9.0.0","draft":false,"prerelease":false,"assets":[{"name":"PostForge-9.0.0.pkg","browser_download_url":"https://github.com/isaacmateosv/postforge/releases/download/v9.0.0/PostForge-9.0.0.pkg"}]}"#
    let release = try! JSONDecoder().decode(PackageRelease.self, from: Data(fixture.utf8))
    precondition(release.tagName == "v9.0.0" && release.assets.first!.browserDownloadUrl != nil)
    precondition(delegate.versionIsNewer("v1.2.0", than: "1.1.0"))
    precondition(delegate.versionIsNewer("v1.2.0", than: "1.2.0-pre.1"))
    precondition(!delegate.versionIsNewer("1.2.0-pre.1", than: "1.2.0"))
    precondition(delegate.versionIsNewer("1.2.0-pre.10", than: "1.2.0-pre.2"))
    precondition(!delegate.versionIsNewer("1.2.0+build.4", than: "1.2.0"))
    precondition(!delegate.versionIsNewer("", than: "1.2.0"))
    defaults.setVolatileDomain(["uiLanguage": "en"], forName: UserDefaults.argumentDomain)
    delegate.refreshLocalizedWindows()
    precondition(delegate.newPost!.preview.title == "👨‍🍳 Bake idea")
    delegate.newPost!.placementMenu.selectItem(at: 2)
    defaults.setVolatileDomain(["uiLanguage": "es"], forName: UserDefaults.argumentDomain)
    delegate.refreshLocalizedWindows()
    precondition(delegate.newPost!.placementMenu.titleOfSelectedItem == "Solo historias")
    defaults.setVolatileDomain(["uiLanguage": "en"], forName: UserDefaults.argumentDomain)
    delegate.refreshLocalizedWindows()
    precondition(delegate.newPost!.placementMenu.titleOfSelectedItem == "Stories only")
    delegate.newPost!.placementMenu.selectItem(at: 0)
    let composer = delegate.newPost!
    let composerStack = composer.window.contentView!.subviews.compactMap { $0 as? NSStackView }.last!
    let steps = composerStack.arrangedSubviews[1] as! ComposerSteps
    precondition(steps.stringValue.hasPrefix("1. Bake your idea"))
    let stepStyle = steps.attributedStringValue.attribute(.paragraphStyle, at: 0, effectiveRange: nil) as? NSParagraphStyle
    precondition(stepStyle?.alignment == .center)
    defaults.setVolatileDomain(["uiLanguage": "es"], forName: UserDefaults.argumentDomain)
    delegate.refreshLocalizedWindows()
    precondition(steps.stringValue.hasPrefix("1. Hornea la idea"))
    defaults.setVolatileDomain(["uiLanguage": "en"], forName: UserDefaults.argumentDomain)
    delegate.refreshLocalizedWindows()
    steps.startSweep(in: composer.window)
    precondition(steps.isAnimating != NSWorkspace.shared.accessibilityDisplayShouldReduceMotion)
    steps.stopSweep()
    precondition(!steps.isAnimating)
    precondition(composer.preview.bezelColor == .systemBlue && !composer.create.isEnabled)
    let planFixture = #"{"when_local":"19:15","targets":[{"network":"instagram","channel":"Sample","placement":"story"}],"caption":"Sample caption","video_cover_available":true,"warnings":["Sample warning"]}"#
    composer.report(planFixture, dryRun: true, exitCode: 0)
    precondition(composer.result.string.contains("Plan ready to review"))
    precondition(composer.result.string.contains("Destinations"))
    precondition(composer.result.string.contains("Things to check"))
    precondition(composer.ideaHeight?.constant == 64 && composer.create.isEnabled)
    precondition(!composer.chooseCover.isEnabled && !composer.coverSecond.isEnabled && !composer.changeCover.isHidden)
    composer.editCover()
    precondition(composer.chooseCover.isEnabled && composer.coverSecond.isEnabled && !composer.create.isEnabled)
    let variant = #"{"when_local":"19:15","caption":"Earlier version","caption_source":"written by test from your idea"}"#
    composer.savedVersions = [(instruction: "Earlier idea", output: variant)]
    composer.updateCaptionVersions()
    composer.captionVersions.selectItem(at: 1)
    composer.restoreCaptionVersion()
    precondition(composer.instruction.string == "Earlier idea")
    precondition(composer.reviewedCaption == "Earlier version" && !composer.alternateCaption.isHidden)
    composer.draftOptionsChanged()
    precondition(composer.captionVersions.isHidden)
    precondition(composer.preview.bezelColor == .systemBlue && !composer.create.isEnabled)
    delegate.application(app, open: [URL(string: "postforge://new-post")!])
    precondition(delegate.newPost!.window.isVisible)
    delegate.newPost!.window.orderOut(nil)
    delegate.application(app, open: [URL(string: "publishmachine://new-post")!])
    precondition(delegate.newPost!.window.isVisible)

    let guide = UserGuideWindow()
    guide.refresh(spanish: false)
    precondition(guide.article.string.contains("PostForge Quick Start"))
    guide.topics.selectedSegment = 1
    guide.selectTopic()
    precondition(guide.article.string.contains("PostForge Technical Guide"))
    guide.refresh(spanish: true)
    precondition(guide.article.string.contains("Guía técnica de PostForge"))
    guide.topics.selectedSegment = 0
    guide.selectTopic()
    precondition(guide.article.string.contains("Inicio rápido de PostForge"))
    precondition(guide.article.string.contains("→"))
    delegate.showOperation("Checking…", updateCheck: true)
    delegate.maintenance = MaintenanceStatus(updatesAvailable: false, components: [], dockerStack: "test", checkComplete: true)
    delegate.maintenanceCheckInFlight = true
    delegate.finishUpdateCheckIfReady()
    precondition(delegate.operationSpinner?.isHidden == false, "Must wait for both checks")
    delegate.maintenanceCheckInFlight = false
    delegate.finishUpdateCheckIfReady()
    precondition(delegate.operationSpinner?.isHidden == true)
    precondition(delegate.operationCloseButton?.title == "Done")
    precondition(delegate.operationActionButton?.isHidden == true)
    precondition(delegate.operationLabel?.stringValue.contains("You’re up to date") == true)
    delegate.packageCheckFailing = true
    delegate.finishUpdateCheckIfReady()
    precondition(delegate.operationActionButton?.title == "Try Again")
    precondition(delegate.operationActionButton?.isHidden == false)
    delegate.packageCheckFailing = false
    delegate.maintenance = MaintenanceStatus(updatesAvailable: true, components: [MaintenanceComponent(name: "test", kind: "docker")], dockerStack: "test", checkComplete: true)
    delegate.finishUpdateCheckIfReady()
    precondition(delegate.operationActionButton?.title == "Update Components…")
    delegate.updateButton()
    delegate.menuNeedsUpdate(trayMenu)
    precondition(trayMenu.items.contains { $0.title == "Updates Available…" })
    precondition(delegate.newPost!.updatesButton.title == "Updates Available…")
    delegate.windowWork = 2
    precondition(NSApp.dockTile.badgeLabel == "2")
    precondition(delegate.statusItem.button?.title == " 2 •")
    precondition(delegate.statusItem.button?.image?.size.height == 18)
    precondition(delegate.statusItem.button?.imageScaling == .scaleNone)
    delegate.windowWork = 0
    precondition(NSApp.dockTile.badgeLabel == nil)

    defaults.setVolatileDomain(["uiLanguage": "es"], forName: UserDefaults.argumentDomain)
    delegate.maintenance = MaintenanceStatus(updatesAvailable: false, components: [], dockerStack: "test", checkComplete: true)
    delegate.finishUpdateCheckIfReady()
    precondition(delegate.operationLabel?.stringValue.contains("Todo está actualizado") == true)
    precondition(delegate.operationCloseButton?.title == "Listo")
    defaults.setVolatileDomain(["uiLanguage": "en"], forName: UserDefaults.argumentDomain)
    delegate.showAbout()
    // Collect recursively without translating the normative license text.
    func allLabels(_ view: NSView) -> [String] {
        var values = (view as? NSTextField).map { [$0.stringValue] } ?? []
        values += view.subviews.flatMap(allLabels)
        return values
    }
    let aboutCopy = allLabels(delegate.aboutWindow!.contentView!).joined(separator: "\n")
    precondition(aboutCopy.contains("Isaac Mateo Sarzosa Valencia"))
    precondition(aboutCopy.contains("GPL-3.0-or-later"))
    precondition(aboutCopy.contains("Version \(delegate.currentPostForgeVersion())"))
    delegate.showPublishingFlow()
    precondition(delegate.flowWindow != nil)
    delegate.showLicense()
    let legalScroll = delegate.licenseWindow!.contentView!.subviews.first as! NSScrollView
    let legalText = legalScroll.documentView as! NSTextView
    precondition(!legalText.isEditable)
    precondition(legalText.string.contains("GNU GENERAL PUBLIC LICENSE"))
    precondition(legalText.string.contains("SPDX-License-Identifier: GPL-3.0-or-later"))
    precondition(!legalText.string.contains(": unavailable"))
    defaults.setVolatileDomain(original, forName: UserDefaults.argumentDomain)
    print("PASS: bilingual offline Help, Shortcuts routes, tray layout, idle protection, badges and updates")
    exit(0)
}
app.run()
