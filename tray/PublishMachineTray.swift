// Publish Machine menu bar app: turn the stack on and off, see what is waiting to be sent, and
// get warned before anything turns it off with work pending.
//
// It holds no state of its own: it polls `scripts/lib/machine_state.py --json` and runs
// `publish-machine.sh start` / `stop --force` (after its own warning). Build with tray/build.sh.
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
    let viewerNames: [String]?  // up to 15, the bakery phone left out
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
        switch reason {
        case "expires soon": return "Reconnect \(network) by \(expires.map { shortDay(iso: $0) } ?? "soon")"
        case "expired": return "\(network) stopped working"
        case "disconnected": return "\(network) is disconnected"
        default: return "\(network) setup isn't finished"
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

struct MaintenanceStatus: Decodable {
    let updatesAvailable: Bool
    let components: [MaintenanceComponent]
    let dockerStack: String
}

struct MachineState: Decodable {
    let state: String  // off | starting | stopping | on | partial
    let activity: String?  // idle | active, only while on
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
    f.dateFormat = Calendar.current.isDateInToday(date) ? "'today' HH:mm" : "EEE d MMM HH:mm"
    return f.string(from: date)
}

func shortDate(iso: String) -> String {
    guard let date = isoParser.date(from: iso) else { return iso }
    return shortDate(date)
}

func shortDay(iso: String) -> String {
    guard let date = isoParser.date(from: iso) else { return iso }
    let f = DateFormatter()
    f.dateFormat = "EEE d MMM"
    return f.string(from: date)
}

func plural(_ n: Int, _ word: String) -> String { "\(n) \(word)\(n == 1 ? "" : "s")" }

func fourCC(_ s: String) -> UInt32 { s.utf8.reduce(0) { ($0 << 8) | UInt32($1) } }

func postForgeImage(active: Bool) -> NSImage {
    let image = NSImage(size: NSSize(width: 20, height: 20))
    image.lockFocus()
    let plane = NSBezierPath()
    plane.move(to: NSPoint(x: 2, y: 10))
    plane.line(to: NSPoint(x: 17, y: 18))
    plane.line(to: NSPoint(x: 12, y: 3))
    plane.line(to: NSPoint(x: 9, y: 9))
    plane.close()
    (active ? NSColor.labelColor : NSColor.secondaryLabelColor).setFill()
    plane.fill()
    let spark = NSBezierPath()
    spark.move(to: NSPoint(x: 16, y: 19))
    spark.line(to: NSPoint(x: 17, y: 17))
    spark.line(to: NSPoint(x: 19, y: 16))
    spark.line(to: NSPoint(x: 17, y: 15))
    spark.line(to: NSPoint(x: 16, y: 13))
    spark.line(to: NSPoint(x: 15, y: 15))
    spark.line(to: NSPoint(x: 13, y: 16))
    spark.line(to: NSPoint(x: 15, y: 17))
    spark.close()
    NSColor.systemOrange.setFill()
    spark.fill()
    image.unlockFocus()
    image.isTemplate = false
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
    var busy: String?  // "Turning on…" while a lifecycle command runs
    var pollTimer: Timer?
    var polling = false
    var menuOpen = false
    var newPost: NewPostWindow?
    var notifications: UNAuthorizationStatus?  // nil until macOS answers
    var quittingFromMenu = false
    var sleepAssertion: IOPMAssertionID = 0
    var remindedPosts = Set<String>()
    var openPostizWhenUp = false  // "Turn On and Open Postiz" from a reconnect warning
    var maintenance: MaintenanceStatus?
    var maintenanceCheckInFlight = false
    var maintenanceTimer: Timer?
    var updateNoticeShown = false
    var idleTimer: Timer?
    var telegramHeartbeatTimer: Timer?
    var lastInteraction = Date()
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
            ?? (NSHomeDirectory() + "/publish-machine")
        super.init()
    }

    /// publishmachine://new-post (Shortcuts, Siri, a link) opens the New Post window.
    func application(_ application: NSApplication, open urls: [URL]) {
        if urls.contains(where: { $0.scheme == "publishmachine" && $0.host == "new-post" }) { openNewPost() }
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        if let index = CommandLine.arguments.firstIndex(of: "--snapshot-new-post"), index + 1 < CommandLine.arguments.count {
            snapshotNewPost(to: CommandLine.arguments[index + 1])  // debugging: renders the window to a PNG, then quits
        }
        let dumping = CommandLine.arguments.contains("--dump-menu")
        if !dumping && NSRunningApplication.runningApplications(withBundleIdentifier: Bundle.main.bundleIdentifier ?? "").count > 1 {
            NSApp.terminate(nil)  // already running
            return
        }
        defaults.register(defaults: ["keepAwake": true, "remindWhenOff": true, "remindMinutes": 30,
                                     "uiLanguage": "en", "autoStopWhenIdle": true, "idleStopMinutes": 60])

        let menu = NSMenu()
        menu.autoenablesItems = false
        menu.delegate = self
        statusItem.menu = menu
        updateButton()

        let center = UNUserNotificationCenter.current()
        center.delegate = self
        let turnOn = UNNotificationAction(identifier: "TURN_ON", title: "Turn On", options: [])
        center.setNotificationCategories([
            UNNotificationCategory(identifier: "OFF_WITH_WORK", actions: [turnOn], intentIdentifiers: [], options: [])
        ])
        center.requestAuthorization(options: [.alert, .sound]) { _, _ in self.refreshNotificationStatus() }

        NSWorkspace.shared.notificationCenter.addObserver(
            self, selector: #selector(didWake), name: NSWorkspace.didWakeNotification, object: nil)
        idleTimer = Timer.scheduledTimer(withTimeInterval: 300, repeats: true) { [weak self] _ in
            self?.stopWhenIdleIfNeeded()
        }
        sendTelegramHeartbeat()
        telegramHeartbeatTimer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            self?.sendTelegramHeartbeatIfDue()
        }
        poll()
        scheduleMaintenanceCheck()
        checkForUpdates(notifyIfAvailable: true)
    }

    func telegramHeartbeatInterval() -> TimeInterval {
        guard let contents = try? String(contentsOfFile: project + "/.env", encoding: .utf8) else { return 1800 }
        let value = contents.split(separator: "\n").first { $0.hasPrefix("PM_TELEGRAM_HEARTBEAT_MINUTES=") }
            .flatMap { Int($0.dropFirst("PM_TELEGRAM_HEARTBEAT_MINUTES=".count)) } ?? 30
        return value <= 0 ? 0 : TimeInterval(value * 60)
    }

    func sendTelegramHeartbeatIfDue() {
        guard telegramHeartbeatInterval() > 0 else { return }
        let last = defaults.object(forKey: "lastTelegramHeartbeat") as? Date ?? .distantPast
        guard Date().timeIntervalSince(last) >= telegramHeartbeatInterval() else { return }
        sendTelegramHeartbeat()
    }

    func sendTelegramHeartbeat() {
        guard telegramHeartbeatInterval() > 0 else { return }
        let dir = project
        DispatchQueue.global(qos: .utility).async {
            let result = runCommand(["/usr/bin/python3", dir + "/scripts/notify-pending.py", "--heartbeat"],
                                    in: dir, timeout: 20)
            DispatchQueue.main.async {
                if result.0 == 0 { self.defaults.set(Date(), forKey: "lastTelegramHeartbeat") }
                else { self.log("Telegram heartbeat failed (exit \(result.0))\n\(result.1)") }
                if let menu = self.statusItem.menu { self.menuNeedsUpdate(menu) }
            }
        }
    }

    // MARK: Polling

    @objc func didWake() {
        wokeFromSleep = true
        poll()
    }

    func poll() {
        if polling { return }
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
        scheduleNextPoll()
    }

    /// `PublishMachineTray --snapshot-new-post out.png`: the New Post window as an image (no screen capture).
    func snapshotNewPost(to path: String) {
        let window = NewPostWindow(project: project).window
        window.appearance = NSAppearance(named: .aqua)  // readable on the PNG's white
        let view = window.contentView!
        view.layoutSubtreeIfNeeded()
        if let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) {
            view.cacheDisplay(in: view.bounds, to: rep)
            try? rep.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: path))
        }
        exit(0)
    }

    /// `PublishMachineTray --dump-menu`: print the button and menu after one poll, then quit.
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
            seconds = soon ? 30 : 120
        }

        pollTimer = Timer.scheduledTimer(withTimeInterval: seconds, repeats: false) { [weak self] _ in self?.poll() }
    }

    func scheduleMaintenanceCheck() {
        maintenanceTimer?.invalidate()
        maintenanceTimer = Timer.scheduledTimer(withTimeInterval: 21600, repeats: false) { [weak self] _ in
            self?.checkForUpdates(notifyIfAvailable: true)
        }
    }

    func checkForUpdates(notifyIfAvailable: Bool = false) {
        if maintenanceCheckInFlight { return }
        maintenanceCheckInFlight = true
        let dir = project
        DispatchQueue.global(qos: .utility).async {
            let result = runCommand(["/bin/bash", dir + "/scripts/maintenance.sh", "check", "--json"],
                                    in: dir, timeout: 180, quietErrors: true)
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
                    if let menu = self.statusItem.menu { self.menuNeedsUpdate(menu) }
                } else {
                    self.log("maintenance check failed (exit \(result.0))\n\(result.1)")
                }
                self.scheduleMaintenanceCheck()
            }
        }
    }

    // MARK: Notifications

    func notify(_ title: String, _ body: String, turnOnButton: Bool = false) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        if turnOnButton { content.categoryIdentifier = "OFF_WITH_WORK" }
        UNUserNotificationCenter.current().add(
            UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil))
    }

    /// Whether macOS lets the app show its warnings; the menu offers "Allow Notifications…" when it doesn't.
    func refreshNotificationStatus() {
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            DispatchQueue.main.async { self.notifications = settings.authorizationStatus }
        }
    }

    func nextPostLine(_ st: MachineState) -> String {
        guard let next = st.pending.next else { return "" }
        return "Next: \(shortDate(iso: next.at)) on \(next.provider)."
    }

    func announceChanges(from old: MachineState, to new: MachineState) {
        if !old.isUp && new.state == "on" {
            notify("Publish Machine is on", "Postiz, WhatsApp and the tunnel are up.")
        }
        if openPostizWhenUp && new.state == "on" {
            openPostizWhenUp = false
            openPostizChannels()
        }
        if new.channelsFromCache == false {
            let open = Set((new.channelAlerts ?? []).map(\.key))
            for alert in old.channelAlerts ?? [] where !open.contains(alert.key) {
                guard let ch = new.channels?.first(where: { $0.key == alert.key }) else { continue }
                let until = ch.renews ? "It renews itself." : ch.expires.map { "Good until \(shortDay(iso: $0))." } ?? ""
                notify("\(alert.network) works again", "\(alert.channel) is reconnected. \(until)")
            }
        }
        if old.isUp && new.state == "off" {
            if new.pending.total > 0 {
                notify("Publish Machine is off with \(plural(new.pending.total, "item")) waiting",
                       "Scheduled posts go out late, when it is on again. \(nextPostLine(new))", turnOnButton: true)
                sendPendingExternalAlert(new)
            } else {
                notify("Publish Machine is off", "Nothing was waiting to be sent.")
            }
        }
        if old.state == "on" && new.state == "on" && old.pending.total > 0 && new.pending.total == 0 {
            notify("Everything is sent", "Nothing is waiting. You can turn Publish Machine off.")
        }
        if (new.failedPosts ?? 0) > (old.failedPosts ?? 0) {
            notify("A post failed", "Open Postiz to see what went wrong.")
        }
        if old.services.scheduler && new.isUp && !new.services.scheduler {
            notify("Scheduler stopped", "Scheduled posts won't publish. Turn Publish Machine off and on again.")
        }
        if old.services.whatsapp == "open" && new.isUp && new.services.whatsapp != "open" && new.services.evolution {
            notify("WhatsApp disconnected", "State: \(new.services.whatsapp ?? "unknown"). It may need to be linked again.")
        }
    }

    func sendPendingExternalAlert(_ st: MachineState) {
        let message = "Publish Machine is offline with \(st.pending.total) item(s) waiting. "
            + (st.pending.next.map { "Next: \($0.at) \($0.provider)." } ?? "Some work is overdue.")
        let dir = project
        DispatchQueue.global(qos: .utility).async {
            let result = runCommand(["/usr/bin/python3", dir + "/scripts/notify-pending.py", "--message", message],
                                    in: dir, timeout: 20)
            if result.0 != 0 { self.log("external pending alert failed (exit \(result.0))\n\(result.1)") }
        }
    }

    /// While off, remind before each scheduled post (cached at the last stop).
    func remindIfOff(_ st: MachineState) {
        guard st.state == "off", defaults.bool(forKey: "remindWhenOff") else { return }
        let lead = TimeInterval(defaults.integer(forKey: "remindMinutes") * 60)
        for post in st.scheduled where !remindedPosts.contains(post.id) {
            guard let at = isoParser.date(from: post.at), at.timeIntervalSinceNow < lead else { continue }
            remindedPosts.insert(post.id)
            let when = at.timeIntervalSinceNow < 0 ? "was due \(shortDate(at))" : "is scheduled for \(shortDate(at))"
            notify("Publish Machine is off", "A \(post.provider) post \(when). Turn it on to publish it.", turnOnButton: true)
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
            notify(alert.headline, "\(alert.channel). Open the Publish Machine menu → Reconnect for the steps.")
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
                                        "Publish Machine has posts waiting to be sent" as CFString, &sleepAssertion)
        } else if !want && sleepAssertion != 0 {
            IOPMAssertionRelease(sleepAssertion)
            sleepAssertion = 0
        }
    }

    // MARK: Menu bar button

    func updateButton() {
        guard let button = statusItem.button else { return }
        var symbol = "paperplane"
        var count = 0
        var tip = "Publish Machine"
        if let busy = busy {
            symbol = "hourglass"
            tip = busy
        } else if let st = state {
            count = st.pending.total
            switch st.state {
            case "on":
                symbol = "paperplane.fill"
                tip = st.activity == "active" ? "On: \(plural(count, "item")) waiting" : "On: nothing waiting (idle)"
            case "starting", "stopping":
                symbol = "hourglass"
                tip = st.state.capitalized + "…"
            case "partial":
                symbol = "exclamationmark.triangle"
                tip = "Partly running: use Turn On to restore all services"
            default:
                tip = count > 0 ? "Off: \(plural(count, "scheduled post")) waiting" : "Off"
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
            image = postForgeImage(active: symbol == "paperplane.fill")
        } else {
            image = NSImage(systemSymbolName: symbol, accessibilityDescription: "PostForge")
            image?.isTemplate = true
        }
        button.image = image
        button.imagePosition = .imageLeading
        button.title = count > 0 ? " \(count)" : ""
        button.toolTip = "Publish Machine: " + tip
    }

    // MARK: Menu

    /// Opening the menu checks again, so views and sends show up without waiting for the timer.
    func menuWillOpen(_ menu: NSMenu) {
        menuOpen = true
        lastInteraction = Date()
        refreshNotificationStatus()
        poll()
    }

    func menuDidClose(_ menu: NSMenu) { menuOpen = false }

    func stopWhenIdleIfNeeded() {
        guard defaults.bool(forKey: "autoStopWhenIdle"),
              !menuOpen, busy == nil, state?.state == "on",
              state?.pending.total == 0 else { return }
        let minutes = max(1, defaults.integer(forKey: "idleStopMinutes"))
        guard Date().timeIntervalSince(lastInteraction) >= TimeInterval(minutes * 60) else { return }
        lastInteraction = Date()
        notify("Publish Machine is idle", "The stack is turning off to save resources. Docker Desktop and Ollama stay running.")
        stop()
    }

    func scheduleWake(for post: ScheduledPost?) {
        guard let post = post else { return }
        let dir = project
        DispatchQueue.global(qos: .utility).async {
            let result = runCommand(["/usr/bin/python3", dir + "/scripts/schedule-wake.py", "--at", post.at],
                                    in: dir, timeout: 20)
            if result.0 != 0 { self.log("wake scheduling failed (exit \(result.0))\n\(result.1)") }
        }
    }

    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        let st = state

        let header: String
        if let busy = busy {
            header = busy
        } else if let st = st {
            switch st.state {
            case "on": header = st.activity == "active" ? "On · Active" : "On · Idle"
            case "partial": header = "Partly running"
            case "starting": header = "Turning on…"
            case "stopping": header = "Turning off…"
            default: header = st.docker ? "Off" : "Off (Docker Desktop not running)"
            }
        } else {
            header = stateError == nil ? "Checking…" : "State unavailable"
        }
        let title = NSMenuItem(title: "", action: nil, keyEquivalent: "")
        title.attributedTitle = NSAttributedString(
            string: text("Publish Machine: ", "Publish Machine: ") + header,
            attributes: [.font: NSFont.boldSystemFont(ofSize: 13)])
        title.isEnabled = false
        menu.addItem(title)
        if let error = stateError { menu.addItem(info("⚠︎ " + String(error.prefix(80)))) }

        if let st = st {
            if st.isUp {
                let mark = { (ok: Bool) in ok ? "✓" : "✗" }
                let svc = st.services
                menu.addItem(info(text("Postiz \(mark(svc.postiz))   Scheduler \(mark(svc.scheduler))   WhatsApp \(mark(svc.whatsapp == "open"))   Tunnel \(mark(svc.tunnel))",
                                  "Postiz \(mark(svc.postiz))   Programador \(mark(svc.scheduler))   WhatsApp \(mark(svc.whatsapp == "open"))   Túnel \(mark(svc.tunnel))")))
                if !svc.scheduler && svc.postiz {
                    menu.addItem(info(text("⚠︎ Scheduled posts won't publish until the scheduler is back",
                                          "⚠︎ Las publicaciones programadas no saldrán hasta que vuelva el programador")))
                }
            }
            for alert in st.channelAlerts ?? [] {
                let item = action((alert.urgent ? "✗ " : "⚠︎ ") + alert.headline + "…", #selector(reconnectChannel(_:)),
                                  enabled: busy == nil)
                item.representedObject = alert.key
                menu.addItem(item)
            }
            menu.addItem(.separator())
            addWorkItems(st, to: menu)
        }

        menu.addItem(.separator())
        let isOff = st?.state == "off" || st?.state == "partial" || st == nil
        let canAct = busy == nil && st?.state != "starting" && st?.state != "stopping"
        if isOff {
            menu.addItem(action(st?.state == "partial" ? text("Restore All Services", "Restaurar todos los servicios") :
                                text("Turn On", "Encender"),
                                #selector(turnOn), enabled: canAct && st != nil))
        } else {
            menu.addItem(action(text("Turn Off…", "Apagar…"), #selector(turnOff), enabled: canAct))
        }
        menu.addItem(action(text("Restart Everything…", "Reiniciar todo…"), #selector(restartEverything), enabled: canAct))
        if let maintenance = maintenance, maintenance.updatesAvailable {
            menu.addItem(action(text("Stable Updates Available…", "Actualizaciones estables disponibles…"),
                                #selector(applyStableUpdates), enabled: canAct))
        } else if maintenance != nil {
            menu.addItem(action(text("No Stable Updates Available", "No hay actualizaciones estables"),
                                #selector(checkUpdatesFromMenu), enabled: false))
        } else {
            menu.addItem(action(text("Check for Stable Updates…", "Buscar actualizaciones estables…"),
                                #selector(checkUpdatesFromMenu), enabled: !maintenanceCheckInFlight))
        }
        menu.addItem(action(text("Tunnel URL…", "URL del túnel…"), #selector(editTunnelURL), enabled: busy == nil))

        menu.addItem(.separator())
        let up = st?.isUp ?? false
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
        menu.addItem(info(text("Current audience: \(audience == "all" ? "public" : "private test")",
                              "Audiencia actual: \(audience == "all" ? "público" : "prueba privada")")))
        let telegramConfigured = telegramHeartbeatInterval() > 0 && telegramCredentialsConfigured()
        menu.addItem(info(text("Telegram heartbeat: \(telegramConfigured ? "connected" : "not configured")",
                              "Heartbeat de Telegram: \(telegramConfigured ? "conectado" : "no configurado")")))
        menu.addItem(action(text("Future: bot/account identity…", "Futuro: identidad del bot/cuenta…"),
                            #selector(futureBotIdentity), enabled: false))
        menu.addItem(action(text("New Post…", "Nueva publicación…"), #selector(openNewPost), enabled: up))
        menu.addItem(action(text("Open Postiz", "Abrir Postiz"), #selector(openPostiz), enabled: up))
        menu.addItem(action(text("Open WhatsApp Manager (Evolution)", "Abrir WhatsApp (Evolution)"), #selector(openEvolution), enabled: up))
        menu.addItem(action(text("Open Log", "Abrir registro"), #selector(openLog), enabled: true))

        menu.addItem(.separator())
        if let status = notifications, status != .authorized && status != .provisional {
            // The off/on warnings and "everything is sent" only reach you with notifications allowed.
            menu.addItem(action(status == .notDetermined ? "Allow Notifications…" : "Allow Notifications (off in System Settings)…",
                                #selector(allowNotifications), enabled: true))
        }
        menu.addItem(toggle(text("Keep Mac Awake While Posts Wait", "Mantener Mac activa mientras espera"), key: "keepAwake"))
        menu.addItem(toggle(text("Remind Me Before Posts When Off", "Recordarme antes de publicar apagado"), key: "remindWhenOff"))
        let language = NSMenuItem(title: text("Language", "Idioma"), action: nil, keyEquivalent: "")
        let languageMenu = NSMenu()
        languageMenu.addItem(languageChoice("English", code: "en"))
        languageMenu.addItem(languageChoice("Español", code: "es"))
        language.submenu = languageMenu
        menu.addItem(language)
        let login = action(text("Open at Login", "Abrir al iniciar sesión"), #selector(toggleLogin), enabled: true)
        login.state = SMAppService.mainApp.status == .enabled ? .on : .off
        menu.addItem(login)

        menu.addItem(.separator())
        menu.addItem(action(up ? text("Quit Menu Bar App (stack keeps running)", "Salir (la máquina sigue activa)") :
                            text("Quit Menu Bar App", "Salir de la aplicación"),
                            #selector(quitApp), enabled: true))
    }

    func addWorkItems(_ st: MachineState, to menu: NSMenu) {
        let pending = st.pending
        if pending.scheduled > 0 {
            var label = "Scheduled posts: \(pending.scheduled)"
            if pending.overdue > 0 { label += " (\(pending.overdue) overdue)" }
            if pending.fromCache, let cached = pending.cachedAt { label += " · as of \(shortDate(iso: cached))" }
            let item = info(label)
            let sub = NSMenu()
            for post in st.scheduled {
                sub.addItem(info("\(shortDate(iso: post.at))  ·  \(post.provider)  ·  \(post.text.prefix(48))"))
            }
            if pending.scheduled > st.scheduled.count {
                sub.addItem(info("… and \(pending.scheduled - st.scheduled.count) more"))
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
            if wa.confirmations > 0 {
                menu.addItem(action(text("Review WhatsApp Plans…", "Revisar planes de WhatsApp…"), #selector(reviewWhatsAppPlans), enabled: true))
                menu.addItem(info(text("\(wa.confirmations) WhatsApp plan(s) awaiting confirmation", "\(wa.confirmations) plan(es) de WhatsApp esperando confirmación")))
            }
            if wa.pending > 0 {
                var parts: [String] = []
                if wa.awaitingApproval > 0 { parts.append(text("\(wa.awaitingApproval) awaiting approval", "\(wa.awaitingApproval) esperando aprobación")) }
                if wa.approved > 0 { parts.append(text("\(wa.approved) approved", "\(wa.approved) aprobados")) }
                menu.addItem(info(text("WhatsApp Status: " + parts.joined(separator: ", "), "Estado de WhatsApp: " + parts.joined(separator: ", "))))
                if let next = wa.next { menu.addItem(info(text("Next WhatsApp Status: \(shortDate(iso: next))", "Siguiente estado de WhatsApp: \(shortDate(iso: next))"))) }
            }
        }
        if let errors = st.failedPosts, errors > 0 { menu.addItem(info(text("Failed posts (24 h): \(errors)", "Publicaciones fallidas (24 h): \(errors)"))) }
        if let last = st.lastStatus {
            let when = shortDate(Date(timeIntervalSince1970: TimeInterval(last.ts)))
            let item = info(text("Last WhatsApp status: \(when) · \(last.viewed) viewed",
                                "Último estado de WhatsApp: \(when) · \(last.viewed) vistos"))
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
                if last.viewed > names.count { sub.addItem(info("… and \(last.viewed - names.count) more")) }
            }
            item.submenu = sub
            menu.addItem(item)
        }
    }

    func info(_ text: String) -> NSMenuItem {
        let item = NSMenuItem(title: text, action: nil, keyEquivalent: "")
        item.isEnabled = false
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

    func telegramCredentialsConfigured() -> Bool {
        guard let contents = try? String(contentsOfFile: project + "/.env", encoding: .utf8) else { return false }
        let token = contents.split(separator: "\n").first { $0.hasPrefix("PM_TELEGRAM_BOT_TOKEN=") }
        let chat = contents.split(separator: "\n").first { $0.hasPrefix("PM_TELEGRAM_CHAT_ID=") }
        return token?.split(separator: "=", maxSplits: 1).last?.isEmpty == false
            && chat?.split(separator: "=", maxSplits: 1).last?.isEmpty == false
    }

    @objc func futureBotIdentity() {}

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
                                      "Introduce números con código de país separados por comas, sin signos +.\nEjemplo: 593991234567,593998765432")
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
            alert(text("Could not save test numbers", "No se pudieron guardar los números de prueba"),
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
            if code != 0 { self.notify("Publish Machine didn't start", "See Open Log in the menu bar app.") }
        }
    }

    @objc func turnOff() {
        busy = "Checking what's waiting…"
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
            if ask("Can't check what's waiting", "Turn Publish Machine off anyway?",
                   safe: "Keep Running", risky: "Turn Off Anyway") { stop() }
            return
        }
        if st.pending.total == 0 { stop(); return }
        var lines: [String] = st.scheduled.prefix(6).map { "• \(shortDate(iso: $0.at)) · \($0.provider) · \($0.text.prefix(40))" }
        if st.pending.scheduled > 6 { lines.append("• … and \(st.pending.scheduled - 6) more") }
        lines += st.pending.jobs.map { "• Sending now: \($0.label.prefix(50))" }
        if let wa = st.pending.whatsapp {
            if wa.confirmations > 0 { lines.append("• \(wa.confirmations) WhatsApp plan(s) awaiting confirmation") }
            if wa.approved > 0, let next = wa.next {
                lines.append("• \(wa.approved) approved WhatsApp Status(es), next \(shortDate(iso: next))")
            }
        }
        var text = lines.joined(separator: "\n")
        if st.pending.scheduled > 0 || !st.pending.jobs.isEmpty || (st.pending.whatsapp?.approved ?? 0) > 0 {
            text += "\n\nIf you turn it off now, scheduled posts go out late, as soon as "
                + "Publish Machine is on again. A WhatsApp status that is still sending may reach only part of its audience."
        } else {
            text += "\n\nPending WhatsApp plans will remain saved, but drafts and statuses will wait until you turn it on again."
        }
        if ask("\(plural(st.pending.total, "item")) still waiting to be sent", text,
               safe: "Keep Running", risky: "Turn Off Anyway") { stop() }
    }

    func stop() {
        runLifecycle(["stop", "--force"], busyText: "Turning off…") { code, _ in
            if code != 0 { self.notify("Publish Machine didn't stop cleanly", "See Open Log in the menu bar app.") }
        }
    }

    @objc func restartEverything() {
            let count = state?.pending.total ?? 0
            let detail = count > 0
                ? "\(plural(count, "item")) is waiting. It will remain saved, but scheduled work may be delayed while the stack restarts."
                : "The Publish Machine stack will restart. Docker Desktop and other containers will remain running."
            if ask("Restart Publish Machine?", detail,
                   safe: "Cancel", risky: "Restart Now") {
                runLifecycle(["restart"], busyText: "Restarting everything…") { code, _ in
                    if code != 0 {
                        self.notify("Publish Machine didn't restart cleanly", "See Open Log in the menu bar app.")
                    }
                }

            }
        }

    @objc func checkUpdatesFromMenu() {
        checkForUpdates(notifyIfAvailable: true)
    }

    @objc func applyStableUpdates() {
        let host = maintenance?.components.map(\.name).joined(separator: ", ") ?? "none"
        let detail = "A rollback snapshot will be created before the declared Docker stack is refreshed and restarted.\n\n"
            + (host == "none" ? "No Homebrew updates were reported." :
               "Homebrew updates also exist (\(host)); those host updates are not applied automatically.")
        guard ask("Apply stable Docker updates?", detail, safe: "Cancel", risky: "Update and Restart") else { return }
        runLifecycle(["maintenance", "update", "--apply", "--yes"], busyText: "Updating safely…") { code, output in
            if code != 0 {
                self.notify("Update did not complete", output.isEmpty ? "See Open Log in the menu bar app." : String(output.suffix(180)))
            } else {
                self.maintenance = nil
                self.updateNoticeShown = false
                self.notify("Publish Machine updated", "The Docker stack was refreshed and health was checked.")
            }
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
        dialog.informativeText = text("Enter the HTTPS domain used by ngrok or your custom domain. The related Postiz URLs will be updated together; restart afterward.",
                                      "Escribe el dominio HTTPS de ngrok o tu dominio personalizado. Las URL relacionadas de Postiz se actualizarán juntas; reinicia después.")
        dialog.accessoryView = field
        dialog.addButton(withTitle: text("Save", "Guardar"))
        dialog.addButton(withTitle: text("Cancel", "Cancelar"))
        NSApp.activate(ignoringOtherApps: true)
        guard dialog.runModal() == .alertFirstButtonReturn else { return }
        let value = field.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        let result = runCommand(["/bin/bash", project + "/publish-machine.sh", "tunnel-url", value],
                                in: project, timeout: 30)
        if result.0 == 0 {
            alert(text("Tunnel URL saved", "URL del túnel guardada"),
                  text("Restart Publish Machine to apply it.", "Reinicia Publish Machine para aplicarla."))
        } else {
            alert(text("Couldn't save tunnel URL", "No se pudo guardar la URL del túnel"),
                  result.1.isEmpty ? text("Use an HTTPS domain without a path.", "Usa un dominio HTTPS sin ruta.") : result.1)
        }
    }

    @objc func reviewWhatsAppPlans() {
        let folder = project + "/run/wa-confirmations"
        let files = ((try? FileManager.default.contentsOfDirectory(atPath: folder))?
            .filter { $0.hasSuffix(".json") } ?? []).sorted {
                let left = (try? FileManager.default.attributesOfItem(atPath: folder + "/" + $0)[.modificationDate] as? Date) ?? .distantPast
                let right = (try? FileManager.default.attributesOfItem(atPath: folder + "/" + $1)[.modificationDate] as? Date) ?? .distantPast
                return left > right
            }
        if files.isEmpty {
            alert(text("No WhatsApp plans awaiting confirmation", "No hay planes de WhatsApp esperando confirmación"),
                  text("New plans will appear here after a WhatsApp request is analyzed.",
                       "Los planes nuevos aparecerán aquí después de analizar una solicitud de WhatsApp."))
            return
        }
        for (index, file) in files.enumerated() {
            let path = folder + "/" + file
            guard let data = FileManager.default.contents(atPath: path),
                  let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { continue }
            let id = (json["id"] as? String) ?? file.replacingOccurrences(of: ".json", with: "")
            let result = json["result"] as? [String: Any]
            let when = result?["when_local"] as? String ?? "time unavailable"
            let targets = (result?["targets"] as? [[String: Any]] ?? []).compactMap {
                let network = $0["network"] as? String ?? ""
                let channel = $0["channel"] as? String ?? ""
                return channel.isEmpty ? network : "\(network) — \(channel)"
            }.joined(separator: ", ")
            let caption = result?["caption"] as? String ?? "(caption is not available in this older plan)"
            let warnings = (result?["warnings"] as? [String] ?? []).map { "⚠ " + $0 }.joined(separator: "\n")
            var section = "ID: \(id)\nWhen: \(when)\nWhere: \(targets.isEmpty ? "WhatsApp Status" : targets)"
            section += "\n\nCaption:\n\(caption)"
            if !warnings.isEmpty { section += "\n\n\(warnings)" }
            let reference = "\(index + 1)"
            section += "\n\n" + text("Approval or rejection: approve plan \(reference) / reject plan \(reference)",
                                       "Aprobar o rechazar: aprobar plan \(reference) / rechazar plan \(reference)")
            let dialog = NSAlert()
            dialog.messageText = text("WhatsApp plan \(reference)", "Plan de WhatsApp \(reference)")
            dialog.informativeText = section
            dialog.addButton(withTitle: text("Reject Plan", "Rechazar plan"))
            dialog.addButton(withTitle: text("Send Approval to WhatsApp", "Enviar aprobación a WhatsApp"))
            dialog.addButton(withTitle: text("Skip", "Omitir"))
            NSApp.activate(ignoringOtherApps: true)
            switch dialog.runModal() {
            case .alertFirstButtonReturn:
                let result = runCommand(["/usr/bin/python3", project + "/scripts/lib/wa_inbox.py",
                                         "--reject-plan", id], in: project, timeout: 30)
                log("reject plan \(id) -> exit \(result.0)\n\(result.1)")
            case .alertSecondButtonReturn:
                let result = runCommand(["/usr/bin/python3", project + "/scripts/lib/wa_inbox.py",
                                         "--send-plan-approval", id], in: project, timeout: 60)
                if result.0 != 0 {
                    alert(text("Couldn't send approval", "No se pudo enviar la aprobación"),
                          result.1.isEmpty ? text("See Open Log in the menu bar app.", "Consulta Abrir registro en la aplicación de la barra.") : result.1)
                } else {
                    log("send approval plan \(id) -> exit \(result.0)\n\(result.1)")
                }
            default:
                break
            }
        }
        poll()
    }

    func runLifecycle(_ args: [String], busyText: String, done: @escaping (Int32, String) -> Void) {
        busy = busyText
        updateButton()
        updateSleepAssertion()
        scheduleNextPoll()
        let dir = project
        DispatchQueue.global(qos: .userInitiated).async {
            let (code, output) = runCommand(["/bin/bash", dir + "/publish-machine.sh"] + args, in: dir, timeout: 900)
            DispatchQueue.main.async {
                self.log("publish-machine.sh \(args.joined(separator: " ")) -> exit \(code)\n\(output)")
                self.busy = nil
                done(code, output)
                self.poll()
            }
        }
    }

    /// Drop media, say where and when: drafts land on the Postiz calendar (scripts/plan-post.sh).
    @objc func openNewPost() {
        if newPost == nil { newPost = NewPostWindow(project: project) }
        newPost?.show()
    }

    @objc func openPostiz() {
        if let url = URL(string: state?.postizUrl ?? "http://localhost:4200") { NSWorkspace.shared.open(url) }
    }

    /// The steps for one channel, then Postiz (turning the stack on first if needed) or the guide.
    /// `publish-machine.sh channels --reconnect` is the same walk-through in Terminal.
    @objc func reconnectChannel(_ sender: NSMenuItem) {
        guard let key = sender.representedObject as? String,
              let alert = state?.channelAlerts?.first(where: { $0.key == key }) else { return }
        let up = state?.isUp ?? false
        let steps = up ? Array(alert.steps.dropFirst()) : alert.steps
        let dialog = NSAlert()
        dialog.messageText = alert.headline
        dialog.informativeText = "\(alert.channel)\n\n"
            + steps.enumerated().map { "\($0.offset + 1). \($0.element)" }.joined(separator: "\n")
        dialog.addButton(withTitle: up ? "Open Postiz" : "Turn On and Open Postiz")
        dialog.addButton(withTitle: "Open Guide")
        dialog.addButton(withTitle: "Later")
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
        let text = "\(nextPostLine(st)) If the Mac shuts down now, scheduled posts go out late, "
            + "as soon as Publish Machine is on again."
        let proceed = ask("Publish Machine has \(plural(st.pending.total, "item")) waiting", text,
                          safe: "Cancel Shutdown", risky: "Shut Down Anyway")
        return proceed ? .terminateNow : .terminateCancel
    }

    // MARK: Dialogs and log

    /// Warning dialog whose default (Return) button is the safe choice. True if the user picks `risky`.
    func ask(_ title: String, _ text: String, safe: String, risky: String) -> Bool {
        let alert = NSAlert()
        alert.alertStyle = .warning
        alert.messageText = title
        alert.informativeText = text
        alert.addButton(withTitle: safe)
        alert.addButton(withTitle: risky)
        NSApp.activate(ignoringOtherApps: true)
        return alert.runModal() == .alertSecondButtonReturn
    }

    func alert(_ title: String, _ text: String) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = text
        NSApp.activate(ignoringOtherApps: true)
        alert.runModal()
    }

    func logPath() -> String { project + "/logs/tray.log" }

    func log(_ text: String) {
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

/// Takes photos and videos dragged in from Finder (or exported from Photos).
final class DropView: NSView {
    var onFiles: (([URL]) -> Void)?

    override init(frame: NSRect) {
        super.init(frame: frame)
        registerForDraggedTypes([.fileURL])
        wantsLayer = true
        layer?.cornerRadius = 10
        layer?.borderWidth = 1.5
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

/// "New Post…": files plus one sentence (typed or dictated) become one Postiz draft per network at
/// that time. Preview shows the plan; Create Drafts makes them. Nothing publishes until approved in
/// Postiz (HITL). The work is done by scripts/plan-post.sh --json.
final class NewPostWindow: NSObject, NSTextViewDelegate {
    let project: String
    let window: NSWindow
    let files = NSTextField(wrappingLabelWithString: "No files yet.")
    let instruction = NSTextView()
    let result = NSTextView()
    let preview = NSButton(title: "Preview", target: nil, action: nil)
    let create = NSButton(title: "Create Drafts", target: nil, action: nil)
    let calendar = NSButton(title: "Open Postiz Calendar", target: nil, action: nil)
    let spinner = NSProgressIndicator()
    var media: [URL] = []
    var reviewURL: URL?
    var previewed = false

    init(project: String) {
        self.project = project
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 560, height: 640),
                          styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        super.init()
        window.title = "New Post"
        window.isReleasedWhenClosed = false
        build()
        window.center()
    }

    func show() {
        window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(instruction)
        NSApp.activate(ignoringOtherApps: true)
    }

    func heading(_ text: String) -> NSTextField {
        let label = NSTextField(labelWithString: text)
        label.font = .boldSystemFont(ofSize: 13)
        return label
    }

    func scroll(_ view: NSTextView, height: CGFloat, editable: Bool) -> NSScrollView {
        let box = NSScrollView()
        box.hasVerticalScroller = true
        box.borderType = .bezelBorder
        box.documentView = view
        view.isEditable = editable
        view.isRichText = false
        view.font = .systemFont(ofSize: 13)
        view.textContainerInset = NSSize(width: 6, height: 6)
        view.autoresizingMask = [.width]
        view.isVerticallyResizable = true
        box.heightAnchor.constraint(equalToConstant: height).isActive = true
        return box
    }

    func build() {
        let drop = DropView()
        drop.onFiles = { [weak self] urls in self?.add(urls) }
        drop.heightAnchor.constraint(equalToConstant: 92).isActive = true
        let choose = NSButton(title: "Choose Files…", target: self, action: #selector(chooseFiles))
        let clear = NSButton(title: "Clear", target: self, action: #selector(clearFiles))
        files.textColor = .secondaryLabelColor
        files.maximumNumberOfLines = 3
        let dropRow = NSStackView(views: [NSTextField(labelWithString: "Drop photos or videos here, or"), choose, clear])
        let dropStack = NSStackView(views: [dropRow, files])
        dropStack.orientation = .vertical
        dropStack.alignment = .leading
        dropStack.translatesAutoresizingMaskIntoConstraints = false
        drop.addSubview(dropStack)
        NSLayoutConstraint.activate([
            dropStack.leadingAnchor.constraint(equalTo: drop.leadingAnchor, constant: 12),
            dropStack.trailingAnchor.constraint(lessThanOrEqualTo: drop.trailingAnchor, constant: -12),
            dropStack.centerYAnchor.constraint(equalTo: drop.centerYAnchor),
        ])

        let hint = NSTextField(wrappingLabelWithString:
            "Example: Instagram y TikTok el viernes a las 6 de la tarde; idea: guaguas de higo solo hasta el domingo. "
            + "Your exact words: texto: \"…\". To speak instead of typing, click Dictate (or press the dictation key).")
        hint.font = .systemFont(ofSize: 11)
        hint.textColor = .secondaryLabelColor
        let dictate = NSButton(title: "Dictate", target: self, action: #selector(startDictation))
        instruction.delegate = self

        preview.target = self
        preview.action = #selector(runPreview)
        create.target = self
        create.action = #selector(runCreate)
        create.isEnabled = false
        calendar.target = self
        calendar.action = #selector(openCalendar)
        calendar.isHidden = true
        spinner.style = .spinning
        spinner.controlSize = .small
        spinner.isDisplayedWhenStopped = false
        let buttons = NSStackView(views: [dictate, NSView(), spinner, preview, create])
        result.string = "Nothing is published from here: drafts wait on the Postiz calendar for your approval."
        result.textColor = .secondaryLabelColor

        let stack = NSStackView(views: [
            heading("1. Photos or videos"), drop,
            heading("2. Where, when, and your idea"), scroll(instruction, height: 96, editable: true), hint,
            buttons, scroll(result, height: 190, editable: false), calendar,
        ])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 8
        stack.edgeInsets = NSEdgeInsets(top: 16, left: 18, bottom: 16, right: 18)
        for view in [drop, hint, buttons] + stack.arrangedSubviews.filter({ $0 is NSScrollView }) {
            view.widthAnchor.constraint(equalTo: stack.widthAnchor, constant: -36).isActive = true
        }
        window.contentView = stack
    }

    func add(_ urls: [URL]) {
        media += urls.filter { !media.contains($0) }
        files.stringValue = media.isEmpty ? "No files yet." : media.map { $0.lastPathComponent }.joined(separator: ", ")
        previewed = false
        create.isEnabled = false
    }

    @objc func chooseFiles() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = true
        panel.allowedContentTypes = [.image, .movie]
        if panel.runModal() == .OK { add(panel.urls) }
    }

    @objc func clearFiles() {
        media = []
        add([])
    }

    func textDidChange(_ notification: Notification) {
        previewed = false
        create.isEnabled = false
    }

    @objc func startDictation() {
        window.makeFirstResponder(instruction)
        if !NSApp.sendAction(Selector(("startDictation:")), to: nil, from: self) {
            show("Dictation isn't on. Turn it on in System Settings → Keyboard → Dictation, then press the dictation key.")
        }
    }

    @objc func runPreview() { run(dryRun: true) }
    @objc func runCreate() {
        guard previewed else {
            show("Preview the plan first. Nothing will be created until you confirm it.")
            return
        }
        run(dryRun: false)
    }

    @objc func openCalendar() {
        if let url = reviewURL { NSWorkspace.shared.open(url) }
    }

    func show(_ text: String) {
        result.string = text
        result.textColor = .labelColor
    }

    func run(dryRun: Bool) {
        let text = instruction.string.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return show("Say where, when, and your idea first.") }
        var args = [project + "/scripts/plan-post.sh", "--json"]
        if dryRun { args.append("--dry-run") }
        for url in media { args += ["--media", url.path] }
        args.append(text)
        preview.isEnabled = false
        create.isEnabled = false
        if dryRun { previewed = false }
        spinner.startAnimation(nil)
        show(dryRun ? "Reading your plan and writing the caption…" : "Creating drafts…")
        DispatchQueue.global(qos: .userInitiated).async {
            let (code, output) = runCommand(args, in: self.project, timeout: 900, quietErrors: true)
            DispatchQueue.main.async {
                self.spinner.stopAnimation(nil)
                self.preview.isEnabled = true
                self.create.isEnabled = true
                self.report(output, dryRun: dryRun, exitCode: code)
            }
        }
    }

    func report(_ output: String, dryRun: Bool, exitCode: Int32) {
        guard let json = (try? JSONSerialization.jsonObject(with: Data(output.utf8))) as? [String: Any] else {
            return show("✖ \(dryRun ? "Preview" : "Draft creation") failed (exit \(exitCode)).\n"
                        + String(output.suffix(800)))
        }
        if let error = json["error"] as? String {
            return show("✖ \(dryRun ? "Preview" : "Draft creation") failed:\n" + error
                        + "\n\nNothing was created. Correct the request or retry.")
        }
        let names = ["instagram": "Instagram", "facebook": "Facebook", "tiktok": "TikTok", "youtube": "YouTube"]
        var lines = [(dryRun ? "Plan (nothing created yet) for " : "Drafts created for ")
                     + (json["when_local"] as? String ?? "") + " (bakery time)"]
        for target in json["targets"] as? [[String: Any]] ?? [] {
            let network = target["network"] as? String ?? ""
            let short = network == "youtube" && (json["short"] as? Bool ?? false) ? " (Short)" : ""
            lines.append("  • \(names[network] ?? network): \(target["channel"] as? String ?? "")\(short)")
        }
        if let caption = json["caption"] as? String {
            lines.append("\nCaption (\(json["caption_source"] as? String ?? "")):\n\(caption)")
        }
        for note in json["notes"] as? [String] ?? [] { lines.append("· assumed: " + note) }
        for warning in json["warnings"] as? [String] ?? [] { lines.append("⚠ " + warning) }
        if !dryRun {
            lines.append("\nNothing is published yet: review, edit and approve them on the Postiz calendar.")
            reviewURL = (json["review_url"] as? String).flatMap(URL.init(string:))
            calendar.isHidden = reviewURL == nil
        } else {
            previewed = true
            create.isEnabled = true
            lines.append("\nPlan verified. Click Create Drafts to continue, or edit and Preview again.")
        }
        show(lines.joined(separator: "\n"))
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
