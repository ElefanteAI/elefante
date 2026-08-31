import AppKit
import Foundation

private let stageMarkers = [
    "Purging bytecode",
    "PRE-FLIGHT CHECKS",
    "[Step 1]",
    "[Step 2]",
    "[Step 2a]",
    "[Step 3]",
    "[Step 3a]",
    "[Step 4]",
    "[Step 4a]",
    "[Step 5]",
    "Verifying MCP handshake",
    "[Step 5b]",
    "[Step 5c]",
]

private let installLogFileName = ".elefante-install.log"
private let installStatusFileName = ".elefante-install-status.txt"
private let installSummaryFileName = ".elefante-install-summary.txt"

private enum InstallState {
    case ready
    case installing
    case failed
    case complete
}

private struct HostOption {
    let id: String
    let title: String
    let detected: Bool
}

private struct PackageOperationDescription: Decodable {
    let schemaVersion: Int
    let operation: String
    let currentVersion: String?
    let targetVersion: String?
    let confirmationToken: String?
    let retainedRollback: RetainedRollbackDescription?

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case operation
        case currentVersion = "current_version"
        case targetVersion = "target_version"
        case confirmationToken = "confirmation_token"
        case retainedRollback = "retained_rollback"
    }
}

private struct RetainedRollbackDescription: Decodable {
    let available: Bool
    let currentVersion: String?
    let targetVersion: String?
    let confirmationToken: String?

    enum CodingKeys: String, CodingKey {
        case available
        case currentVersion = "current_version"
        case targetVersion = "target_version"
        case confirmationToken = "confirmation_token"
    }
}

private struct PackageUninstallDescription: Decodable {
    let schemaVersion: Int
    let operation: String
    let available: Bool
    let confirmationToken: String?
    let dataEffect: String

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case operation
        case available
        case confirmationToken = "confirmation_token"
        case dataEffect = "data_effect"
    }
}

final class InstallerApp: NSObject, NSApplicationDelegate, NSWindowDelegate {
    private let accentColor = NSColor(calibratedRed: 0.09, green: 0.50, blue: 0.47, alpha: 1.0)
    private let successColor = NSColor.systemGreen
    private let errorColor = NSColor.systemRed

    private var installerDir: URL = URL(fileURLWithPath: "/")
    private var window: NSWindow?
    private var pathField = NSTextField(string: "")
    private var browseButton = NSButton(title: "Browse…", target: nil, action: nil)
    private var installButton = NSButton(title: "Install Elefante", target: nil, action: nil)
    private var retainedRollbackButton = NSButton(
        title: "Roll Back Previous Version",
        target: nil,
        action: nil
    )
    private var uninstallButton = NSButton(title: "Uninstall Elefante", target: nil, action: nil)
    private var heroTitleLabel = NSTextField(labelWithString: "Install Elefante")
    private var progressBar = NSProgressIndicator()
    private var statusLabel = NSTextField(labelWithString: "Ready to install")
    private var outputView = NSTextView()
    private var outputScrollView = NSScrollView()
    private var summaryPathLabel = NSTextField(labelWithString: "")
    private var statusPathLabel = NSTextField(labelWithString: "")
    private var logPathLabel = NSTextField(labelWithString: "")
    private var backupPathLabel = NSTextField(labelWithString: "")
    private var openSummaryButton = NSButton(title: "Open Summary", target: nil, action: nil)
    private var openStatusButton = NSButton(title: "Open Status", target: nil, action: nil)
    private var openLogButton = NSButton(title: "Open Log", target: nil, action: nil)
    private var openInstallFolderButton = NSButton(title: "Open Install Folder", target: nil, action: nil)
    private var hostButtons: [String: NSButton] = [:]
    private var projectCard = NSView()
    private var projectSummaryLabel = NSTextField(labelWithString: "")
    private var addProjectButton = NSButton(title: "Add Project Folder…", target: nil, action: nil)
    private var removeProjectButton = NSButton(title: "Remove Last", target: nil, action: nil)
    private var projectURLs: [URL] = []

    private var process: Process?
    private var outputPipe: Pipe?
    private var pendingOutput = ""
    private var seenMarkers = Set<String>()
    private var state: InstallState = .ready
    private var cancelRequested = false
    private var activeOperation = "Install"
    private var activeOperationDescription: PackageOperationDescription?
    private var activeUninstallDescription: PackageUninstallDescription?
    private var requestedRetainedRollbackToken: String?
    private var requestedUninstallToken: String?

    func applicationDidFinishLaunching(_ notification: Notification) {
        do {
            installerDir = try Self.parseInstallerDir(from: CommandLine.arguments)
        } catch {
            showFatalAlert(message: error.localizedDescription)
            return
        }

        buildWindow()
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        guard state == .installing else {
            return true
        }

        let alert = NSAlert()
        alert.messageText = "Cancel installation?"
        alert.informativeText = "Elefante is still installing. Closing now will stop the installer."
        alert.alertStyle = .warning
        alert.addButton(withTitle: "Stop Installation")
        alert.addButton(withTitle: "Keep Installing")

        let response = alert.runModal()
        if response == .alertFirstButtonReturn {
            cancelRequested = true
            process?.terminate()
            return true
        }
        return false
    }

    private static func parseInstallerDir(from arguments: [String]) throws -> URL {
        let dir: URL
        if let index = arguments.firstIndex(of: "--installer-dir"), arguments.indices.contains(index + 1) {
            dir = URL(fileURLWithPath: arguments[index + 1], isDirectory: true)
        } else {
            let bundleRoot = Bundle.main.bundleURL.deletingLastPathComponent()
            dir = bundleRoot.appendingPathComponent(".elefante-installer", isDirectory: true)
        }

        let installScript = dir.appendingPathComponent("install.sh")
        guard FileManager.default.fileExists(atPath: installScript.path) else {
            throw NSError(domain: "ElefanteInstaller", code: 2, userInfo: [NSLocalizedDescriptionKey: "Installer payload not found at \(installScript.path)."])
        }
        return dir
    }

    private func buildWindow() {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 920, height: 880),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Install Elefante"
        window.minSize = NSSize(width: 820, height: 780)
        window.isReleasedWhenClosed = false
        window.delegate = self
        window.toolbarStyle = .unified
        window.titleVisibility = .hidden
        window.backgroundColor = .windowBackgroundColor
        window.collectionBehavior = [.moveToActiveSpace]

        if let icon = Bundle.main.image(forResource: "elefante") {
            NSApp.applicationIconImage = icon
        }

        let rootView = NSView()
        rootView.translatesAutoresizingMaskIntoConstraints = false
        window.contentView = rootView

        let stack = NSStackView()
        stack.orientation = .vertical
        stack.spacing = 16
        stack.alignment = .leading
        stack.translatesAutoresizingMaskIntoConstraints = false
        rootView.addSubview(stack)

        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: rootView.leadingAnchor, constant: 28),
            stack.trailingAnchor.constraint(equalTo: rootView.trailingAnchor, constant: -28),
            stack.topAnchor.constraint(equalTo: rootView.topAnchor, constant: 24),
            stack.bottomAnchor.constraint(equalTo: rootView.bottomAnchor, constant: -24),
        ])

        stack.addArrangedSubview(makeHeroSection())
        stack.addArrangedSubview(makeSeparator())
        stack.addArrangedSubview(makeHostCard())
        projectCard = makeProjectCard()
        stack.addArrangedSubview(projectCard)
        stack.addArrangedSubview(makeActionRow())
        stack.addArrangedSubview(makeProgressSection())
        stack.addArrangedSubview(makeOutputSection())

        installButton.target = self
        installButton.action = #selector(handlePrimaryAction)
        retainedRollbackButton.target = self
        retainedRollbackButton.action = #selector(handleRetainedRollback)
        uninstallButton.target = self
        uninstallButton.action = #selector(handleUninstall)
        browseButton.target = self
        browseButton.action = #selector(browseLocation)
        addProjectButton.target = self
        addProjectButton.action = #selector(addProjectFolder)
        removeProjectButton.target = self
        removeProjectButton.action = #selector(removeLastProject)
        openSummaryButton.target = self
        openSummaryButton.action = #selector(openSummaryFile)
        openStatusButton.target = self
        openStatusButton.action = #selector(openStatusFile)
        openLogButton.target = self
        openLogButton.action = #selector(openLogFile)
        openInstallFolderButton.target = self
        openInstallFolderButton.action = #selector(openInstallFolder)
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(pathFieldDidChange),
            name: NSControl.textDidChangeNotification,
            object: pathField
        )

        pathField.stringValue = defaultInstallPath().path
        outputView.string = ""
        appendLine("Live installer output will appear here once installation starts.", color: .secondaryLabelColor)
        refreshArtifactLabels()
        refreshProjectSummary()
        refreshOperationCopy()

        self.window = window
        positionWindow(window)
        window.orderFrontRegardless()
        window.makeKeyAndOrderFront(nil)
    }

    private func supportedHosts() -> [HostOption] {
        let home = FileManager.default.homeDirectoryForCurrentUser
        let applications = [
            URL(fileURLWithPath: "/Applications", isDirectory: true),
            home.appendingPathComponent("Applications", isDirectory: true),
        ]

        func pathExists(_ relativePath: String) -> Bool {
            FileManager.default.fileExists(
                atPath: home.appendingPathComponent(relativePath).path
            )
        }

        func appExists(_ names: [String]) -> Bool {
            names.contains { name in
                applications.contains {
                    FileManager.default.fileExists(atPath: $0.appendingPathComponent(name).path)
                }
            }
        }

        func commandExists(_ names: [String]) -> Bool {
            let roots = [
                URL(fileURLWithPath: "/opt/homebrew/bin", isDirectory: true),
                URL(fileURLWithPath: "/usr/local/bin", isDirectory: true),
                home.appendingPathComponent(".local/bin", isDirectory: true),
            ]
            return names.contains { name in
                roots.contains {
                    FileManager.default.isExecutableFile(atPath: $0.appendingPathComponent(name).path)
                }
            }
        }

        return [
            HostOption(
                id: "vscode-copilot",
                title: "VS Code + Copilot",
                detected: appExists(["Visual Studio Code.app", "Visual Studio Code - Insiders.app"])
                    || pathExists("Library/Application Support/Code")
            ),
            HostOption(
                id: "cursor",
                title: "Cursor",
                detected: appExists(["Cursor.app"]) || pathExists(".cursor")
            ),
            HostOption(
                id: "kiro",
                title: "Kiro",
                detected: appExists(["Kiro.app"]) || pathExists(".kiro")
            ),
            HostOption(
                id: "gemini",
                title: "Gemini CLI",
                detected: commandExists(["gemini"])
            ),
            HostOption(
                id: "claude-code",
                title: "Claude Code",
                detected: commandExists(["claude"]) || pathExists(".claude")
            ),
            HostOption(
                id: "codex",
                title: "Codex",
                detected: commandExists(["codex"]) || pathExists(".codex")
            ),
            HostOption(
                id: "openclaw",
                title: "OpenClaw",
                detected: commandExists(["openclaw"]) || pathExists(".openclaw")
            ),
            HostOption(
                id: "bob",
                title: "IBM Bob",
                detected: appExists(["Bob-IDE.app", "Bob.app"])
                    || pathExists("Library/Application Support/Bob-IDE")
                    || pathExists(".bob")
            ),
            HostOption(
                id: "antigravity",
                title: "Antigravity",
                detected: appExists(["Antigravity.app"]) || pathExists(".gemini/antigravity")
            ),
            HostOption(
                id: "zed",
                title: "Zed",
                detected: appExists(["Zed.app"]) || pathExists(".config/zed")
                    || commandExists(["zed"])
            ),
            HostOption(
                id: "continue",
                title: "Continue",
                detected: pathExists(".continue") || commandExists(["cn"])
            ),
        ]
    }

    private func makeHostCard() -> NSView {
        let cardStack = NSStackView()
        cardStack.orientation = .vertical
        cardStack.spacing = 10
        cardStack.alignment = .leading

        cardStack.addArrangedSubview(makeLabel(
            "Connect Elefante to Codex",
            font: .systemFont(ofSize: 15, weight: .semibold),
            color: .labelColor
        ))
        cardStack.addArrangedSubview(makeLabel(
            "Codex is the first certified connection and is required. Other detected hosts are optional compatibility previews that use the same private local memory.",
            font: .systemFont(ofSize: 12, weight: .regular),
            color: .secondaryLabelColor,
            wrapping: true
        ))

        let hosts = supportedHosts()
        let rows = stride(from: 0, to: hosts.count, by: 3).map { start -> [NSView] in
            (0..<3).map { offset -> NSView in
                let index = start + offset
                guard index < hosts.count else {
                    return NSView()
                }
                let host = hosts[index]
                let button = NSButton(
                    checkboxWithTitle: host.detected ? "\(host.title)  ·  Detected" : host.title,
                    target: nil,
                    action: nil
                )
                let isCertified = host.id == "codex"
                button.state = isCertified && host.detected ? .on : .off
                button.isEnabled = host.detected && !isCertified
                button.font = .systemFont(
                    ofSize: 12,
                    weight: isCertified && host.detected ? .semibold : .regular
                )
                button.toolTip = isCertified
                    ? host.detected
                        ? "Codex is required and selected for the certified setup"
                        : "Install Codex before running the certified setup"
                    : host.detected
                        ? "Optional compatibility preview; select to connect it"
                        : "Install this host first, then run Elefante again"
                button.translatesAutoresizingMaskIntoConstraints = false
                button.widthAnchor.constraint(equalToConstant: 255).isActive = true
                hostButtons[host.id] = button
                return button
            }
        }

        let grid = NSGridView(views: rows)
        grid.rowSpacing = 10
        grid.columnSpacing = 18
        grid.xPlacement = .leading
        grid.yPlacement = .center
        cardStack.addArrangedSubview(grid)

        cardStack.addArrangedSubview(makeLabel(
            "Codex defines release readiness. Optional host failures do not block the certified setup.",
            font: .systemFont(ofSize: 11, weight: .medium),
            color: accentColor,
            wrapping: true
        ))

        return wrapInCard(cardStack)
    }

    private func selectedHostIDs() -> [String] {
        supportedHosts().compactMap { host in
            hostButtons[host.id]?.state == .on ? host.id : nil
        }
    }

    private func makeProjectCard() -> NSView {
        let cardStack = NSStackView()
        cardStack.orientation = .vertical
        cardStack.spacing = 8
        cardStack.alignment = .leading

        cardStack.addArrangedSubview(makeLabel(
            "Choose where Elefante may remember",
            font: .systemFont(ofSize: 15, weight: .semibold),
            color: .labelColor
        ))
        cardStack.addArrangedSubview(makeLabel(
            "Select at least one real project folder. Each folder receives an isolated memory scope; Elefante never scans or changes the project files.",
            font: .systemFont(ofSize: 12, weight: .regular),
            color: .secondaryLabelColor,
            wrapping: true
        ))

        projectSummaryLabel.font = .monospacedSystemFont(ofSize: 11, weight: .regular)
        projectSummaryLabel.textColor = .labelColor
        projectSummaryLabel.lineBreakMode = .byTruncatingMiddle
        projectSummaryLabel.maximumNumberOfLines = 3
        projectSummaryLabel.translatesAutoresizingMaskIntoConstraints = false
        projectSummaryLabel.widthAnchor.constraint(equalToConstant: 820).isActive = true
        cardStack.addArrangedSubview(projectSummaryLabel)

        let buttonRow = NSStackView()
        buttonRow.orientation = .horizontal
        buttonRow.spacing = 10
        buttonRow.alignment = .centerY
        addProjectButton.bezelStyle = .rounded
        removeProjectButton.bezelStyle = .rounded
        buttonRow.addArrangedSubview(addProjectButton)
        buttonRow.addArrangedSubview(removeProjectButton)
        buttonRow.addArrangedSubview(makeLabel(
            "A disposable Recall check and verified local backup run automatically.",
            font: .systemFont(ofSize: 11, weight: .medium),
            color: accentColor,
            wrapping: true
        ))
        cardStack.addArrangedSubview(buttonRow)
        return wrapInCard(cardStack)
    }

    private func projectSpecs() -> [String] {
        var usedNames = Set<String>()
        return projectURLs.map { url in
            var base = url.lastPathComponent.replacingOccurrences(of: "=", with: "-")
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if base.isEmpty {
                base = "Project"
            }
            if base.count > 90 {
                base = String(base.prefix(90))
            }
            var name = base
            var suffix = 2
            while usedNames.contains(name.lowercased()) {
                name = "\(base) \(suffix)"
                suffix += 1
            }
            usedNames.insert(name.lowercased())
            return "\(name)=\(url.path)"
        }
    }

    private func refreshProjectSummary() {
        if projectURLs.isEmpty {
            projectSummaryLabel.stringValue = "No project folders selected"
            projectSummaryLabel.textColor = errorColor
        } else {
            projectSummaryLabel.stringValue = projectURLs.prefix(3).map {
                "• \($0.lastPathComponent) — \($0.path)"
            }.joined(separator: "\n") + (projectURLs.count > 3 ? "\n+ \(projectURLs.count - 3) more" : "")
            projectSummaryLabel.textColor = .labelColor
        }
        removeProjectButton.isEnabled = state != .installing && !projectURLs.isEmpty
        if state == .ready || state == .failed {
            installButton.isEnabled = activeOperation != "Install" || !projectURLs.isEmpty
        }
    }

    private func positionWindow(_ window: NSWindow) {
        let mouseLocation = NSEvent.mouseLocation
        let targetScreen = NSScreen.screens.first { NSMouseInRect(mouseLocation, $0.frame, false) }
            ?? NSScreen.main
            ?? NSScreen.screens.first

        guard let screen = targetScreen else {
            window.center()
            return
        }

        let visibleFrame = screen.visibleFrame
        let windowSize = window.frame.size
        let origin = NSPoint(
            x: visibleFrame.midX - (windowSize.width / 2),
            y: visibleFrame.midY - (windowSize.height / 2)
        )
        window.setFrameOrigin(origin)
    }

    private func makeHeroSection() -> NSView {
        let hero = NSStackView()
        hero.orientation = .horizontal
        hero.spacing = 18
        hero.alignment = .top

        if let badge = Bundle.main.image(forResource: "installer-badge") {
            let imageView = NSImageView()
            imageView.image = badge
            imageView.imageScaling = .scaleProportionallyUpOrDown
            imageView.translatesAutoresizingMaskIntoConstraints = false
            imageView.widthAnchor.constraint(equalToConstant: 132).isActive = true
            imageView.heightAnchor.constraint(equalToConstant: 132).isActive = true
            hero.addArrangedSubview(imageView)
        }

        let textStack = NSStackView()
        textStack.orientation = .vertical
        textStack.spacing = 8
        textStack.alignment = .leading

        heroTitleLabel = makeLabel(
            "Install Elefante",
            font: .systemFont(ofSize: 32, weight: .bold),
            color: .labelColor
        )
        textStack.addArrangedSubview(heroTitleLabel)

        textStack.addArrangedSubview(makeLabel(
            "Private local memory for your AI. Stored on this Mac.",
            font: .systemFont(ofSize: 14, weight: .regular),
            color: .secondaryLabelColor,
            wrapping: true
        ))

        let meta = NSStackView()
        meta.orientation = .horizontal
        meta.spacing = 16
        meta.alignment = .centerY
        meta.addArrangedSubview(makeLabel("Private by default", font: .systemFont(ofSize: 12, weight: .medium), color: .secondaryLabelColor))
        meta.addArrangedSubview(makeLabel("Recommended path", font: .systemFont(ofSize: 12, weight: .medium), color: .secondaryLabelColor))
        meta.addArrangedSubview(makeLabel("Live install log", font: .systemFont(ofSize: 12, weight: .medium), color: .secondaryLabelColor))
        textStack.addArrangedSubview(meta)

        hero.addArrangedSubview(textStack)
        return hero
    }

    private func makeRecommendedCard() -> NSView {
        let cardStack = NSStackView()
        cardStack.orientation = .vertical
        cardStack.spacing = 8
        cardStack.alignment = .leading

        cardStack.addArrangedSubview(makeLabel("Recommended setup", font: .systemFont(ofSize: 13, weight: .semibold), color: .labelColor))
        cardStack.addArrangedSubview(makeLabel(
            "For most people, keep the default location. Elefante installs into a hidden folder in your home directory, not into Documents.",
            font: .systemFont(ofSize: 12, weight: .regular),
            color: .secondaryLabelColor,
            wrapping: true
        ))
        cardStack.addArrangedSubview(makeLabel("App files:  \(defaultInstallPath().path)", font: .monospacedSystemFont(ofSize: 11, weight: .regular), color: .labelColor))
        cardStack.addArrangedSubview(makeLabel("Data:       \(defaultDataPath().path)", font: .monospacedSystemFont(ofSize: 11, weight: .regular), color: .labelColor))
        backupPathLabel = makeLabel(
            "Backups:    \(defaultBackupPath().path)",
            font: .monospacedSystemFont(ofSize: 11, weight: .regular),
            color: .labelColor
        )
        cardStack.addArrangedSubview(backupPathLabel)

        return wrapInCard(cardStack)
    }

    private func makeLocationCard() -> NSView {
        let cardStack = NSStackView()
        cardStack.orientation = .vertical
        cardStack.spacing = 10
        cardStack.alignment = .leading

        cardStack.addArrangedSubview(makeLabel("Install location", font: .systemFont(ofSize: 13, weight: .semibold), color: .labelColor))
        cardStack.addArrangedSubview(makeLabel(
            "Change this only if you want the app files somewhere else.",
            font: .systemFont(ofSize: 12, weight: .regular),
            color: .secondaryLabelColor,
            wrapping: true
        ))

        let row = NSStackView()
        row.orientation = .horizontal
        row.spacing = 10
        row.alignment = .centerY

        pathField.font = .monospacedSystemFont(ofSize: 12, weight: .regular)
        pathField.translatesAutoresizingMaskIntoConstraints = false
        pathField.widthAnchor.constraint(greaterThanOrEqualToConstant: 620).isActive = true
        browseButton.bezelStyle = .rounded

        row.addArrangedSubview(pathField)
        row.addArrangedSubview(browseButton)
        cardStack.addArrangedSubview(row)

        cardStack.addArrangedSubview(makeLabel(
            "Memories stay local on this Mac. Installation logs are written into the chosen install folder.",
            font: .systemFont(ofSize: 12, weight: .regular),
            color: .secondaryLabelColor,
            wrapping: true
        ))

        return wrapInCard(cardStack)
    }

    private func makeActionRow() -> NSView {
        let row = NSStackView()
        row.orientation = .horizontal
        row.spacing = 16
        row.alignment = .centerY

        installButton.isBordered = false
        installButton.wantsLayer = true
        installButton.layer?.backgroundColor = accentColor.cgColor
        installButton.layer?.cornerRadius = 14
        installButton.layer?.masksToBounds = true
        installButton.controlSize = .large
        installButton.keyEquivalent = "\r"
        installButton.contentTintColor = .white
        installButton.font = .systemFont(ofSize: 15, weight: .semibold)
        installButton.translatesAutoresizingMaskIntoConstraints = false
        installButton.widthAnchor.constraint(greaterThanOrEqualToConstant: 170).isActive = true
        installButton.heightAnchor.constraint(equalToConstant: 44).isActive = true

        retainedRollbackButton.bezelStyle = .rounded
        retainedRollbackButton.controlSize = .large
        retainedRollbackButton.isHidden = true

        uninstallButton.bezelStyle = .rounded
        uninstallButton.controlSize = .large
        uninstallButton.isHidden = true

        row.addArrangedSubview(installButton)
        row.addArrangedSubview(retainedRollbackButton)
        row.addArrangedSubview(uninstallButton)
        row.addArrangedSubview(makeLabel(
            "The installer will show real-time progress below and can be retried if something fails.",
            font: .systemFont(ofSize: 12, weight: .regular),
            color: .secondaryLabelColor,
            wrapping: true
        ))

        return row
    }

    private func makeRecoveryCard() -> NSView {
        let cardStack = NSStackView()
        cardStack.orientation = .vertical
        cardStack.spacing = 10
        cardStack.alignment = .leading

        cardStack.addArrangedSubview(makeLabel("Recovery files", font: .systemFont(ofSize: 13, weight: .semibold), color: .labelColor))
        cardStack.addArrangedSubview(makeLabel(
            "If installation fails or you stop this window, these files survive inside the chosen install folder.",
            font: .systemFont(ofSize: 12, weight: .regular),
            color: .secondaryLabelColor,
            wrapping: true
        ))

        for label in [summaryPathLabel, statusPathLabel, logPathLabel] {
            label.font = .monospacedSystemFont(ofSize: 11, weight: .regular)
            label.textColor = .labelColor
            label.lineBreakMode = .byTruncatingMiddle
            label.maximumNumberOfLines = 1
            label.translatesAutoresizingMaskIntoConstraints = false
            label.widthAnchor.constraint(equalToConstant: 820).isActive = true
            cardStack.addArrangedSubview(label)
        }

        let buttonRow = NSStackView()
        buttonRow.orientation = .horizontal
        buttonRow.spacing = 10
        buttonRow.alignment = .centerY

        for button in [openSummaryButton, openStatusButton, openLogButton, openInstallFolderButton] {
            button.bezelStyle = .rounded
            buttonRow.addArrangedSubview(button)
        }

        cardStack.addArrangedSubview(buttonRow)
        return wrapInCard(cardStack)
    }

    private func makeProgressSection() -> NSView {
        let stack = NSStackView()
        stack.orientation = .vertical
        stack.spacing = 8
        stack.alignment = .leading

        progressBar.isIndeterminate = false
        progressBar.minValue = 0
        progressBar.maxValue = Double(stageMarkers.count)
        progressBar.doubleValue = 0
        progressBar.controlSize = .large
        progressBar.style = .bar
        progressBar.translatesAutoresizingMaskIntoConstraints = false
        progressBar.widthAnchor.constraint(equalToConstant: 864).isActive = true

        statusLabel.font = .systemFont(ofSize: 12, weight: .regular)
        statusLabel.textColor = .secondaryLabelColor

        stack.addArrangedSubview(progressBar)
        stack.addArrangedSubview(statusLabel)
        return stack
    }

    private func makeOutputSection() -> NSView {
        let stack = NSStackView()
        stack.orientation = .vertical
        stack.spacing = 8
        stack.alignment = .leading

        stack.addArrangedSubview(makeLabel("Installer output", font: .systemFont(ofSize: 13, weight: .semibold), color: .labelColor))

        outputView.isEditable = false
        outputView.isRichText = false
        outputView.importsGraphics = false
        outputView.font = .monospacedSystemFont(ofSize: 11, weight: .regular)
        outputView.backgroundColor = .textBackgroundColor
        outputView.textColor = .labelColor
        outputView.textContainerInset = NSSize(width: 12, height: 12)

        outputScrollView.borderType = .bezelBorder
        outputScrollView.hasVerticalScroller = true
        outputScrollView.documentView = outputView
        outputScrollView.translatesAutoresizingMaskIntoConstraints = false
        outputScrollView.heightAnchor.constraint(greaterThanOrEqualToConstant: 160).isActive = true
        outputScrollView.widthAnchor.constraint(equalToConstant: 864).isActive = true

        stack.addArrangedSubview(outputScrollView)
        return stack
    }

    private func makeSeparator() -> NSView {
        let separator = NSBox()
        separator.boxType = .separator
        separator.translatesAutoresizingMaskIntoConstraints = false
        separator.widthAnchor.constraint(equalToConstant: 864).isActive = true
        return separator
    }

    private func normalizedInstallRoot() -> URL {
        let trimmed = pathField.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        let path = trimmed.isEmpty ? defaultInstallPath().path : NSString(string: trimmed).expandingTildeInPath
        return URL(fileURLWithPath: path, isDirectory: true).standardizedFileURL
    }

    private func summaryFileURL() -> URL {
        normalizedInstallRoot().appendingPathComponent(installSummaryFileName)
    }

    private func statusFileURL() -> URL {
        normalizedInstallRoot().appendingPathComponent(installStatusFileName)
    }

    private func logFileURL() -> URL {
        normalizedInstallRoot().appendingPathComponent(installLogFileName)
    }

    private func renderInstallArtifactPaths() -> [String] {
        [
            "Persistent installer files:",
            "Summary file: \(summaryFileURL().path)",
            "Status file: \(statusFileURL().path)",
            "Log file: \(logFileURL().path)",
        ]
    }

    private func renderFailedInstallGuidance() -> [String] {
        [
            "Read these persisted installer files in order:",
            "1. Summary file: \(summaryFileURL().path)",
            "2. Status file: \(statusFileURL().path)",
            "3. Log file: \(logFileURL().path)",
        ]
    }

    private func refreshArtifactLabels() {
        summaryPathLabel.stringValue = "Summary: \(summaryFileURL().path)"
        statusPathLabel.stringValue = "Status:  \(statusFileURL().path)"
        logPathLabel.stringValue = "Log:     \(logFileURL().path)"
    }

    private func packageOperationDescription(for installRoot: URL) -> PackageOperationDescription? {
        let scriptURL = installerDir.appendingPathComponent("install.sh")
        let process = Process()
        let pipe = Pipe()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = [
            scriptURL.path,
            "--install-root", installRoot.path,
            "--describe-operation",
        ]
        process.currentDirectoryURL = installerDir
        process.standardOutput = pipe
        process.standardError = Pipe()
        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            return nil
        }
        guard process.terminationStatus == 0 else {
            return nil
        }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard
            let description = try? JSONDecoder().decode(
                PackageOperationDescription.self,
                from: data
            ),
            description.schemaVersion == 1,
            ["install", "repair", "update", "rollback"].contains(description.operation),
            description.operation != "rollback" || description.confirmationToken != nil
        else {
            return nil
        }
        return description
    }

    private func packageManagedBackupPath(for installRoot: URL) -> URL? {
        let scriptURL = installerDir.appendingPathComponent("install.sh")
        let process = Process()
        let pipe = Pipe()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = [
            scriptURL.path,
            "--install-root", installRoot.path,
            "--print-managed-backup-path",
        ]
        process.currentDirectoryURL = installerDir
        process.standardOutput = pipe
        process.standardError = Pipe()
        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            return nil
        }
        guard process.terminationStatus == 0 else {
            return nil
        }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard
            let value = String(data: data, encoding: .utf8)?
                .trimmingCharacters(in: .whitespacesAndNewlines),
            !value.isEmpty,
            value.first == "/",
            !value.contains("\n")
        else {
            return nil
        }
        return URL(fileURLWithPath: value, isDirectory: true)
    }

    private func packageUninstallDescription(for installRoot: URL) -> PackageUninstallDescription? {
        let scriptURL = installerDir.appendingPathComponent("install.sh")
        let process = Process()
        let pipe = Pipe()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = [
            scriptURL.path,
            "--install-root", installRoot.path,
            "--describe-uninstall",
        ]
        process.currentDirectoryURL = installerDir
        process.standardOutput = pipe
        process.standardError = Pipe()
        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            return nil
        }
        guard process.terminationStatus == 0 else {
            return nil
        }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard
            let description = try? JSONDecoder().decode(
                PackageUninstallDescription.self,
                from: data
            ),
            description.schemaVersion == 1,
            description.operation == "uninstall",
            description.available,
            description.confirmationToken != nil,
            description.dataEffect == "preserved"
        else {
            return nil
        }
        return description
    }

    private func operationVerb(for installRoot: URL) -> String {
        activeOperationDescription = packageOperationDescription(for: installRoot)
        if let operation = activeOperationDescription?.operation {
            return [
                "install": "Install",
                "repair": "Repair",
                "update": "Update",
                "rollback": "Roll Back",
            ][operation] ?? "Install"
        }
        var isDirectory: ObjCBool = false
        let exists = FileManager.default.fileExists(
            atPath: installRoot.path,
            isDirectory: &isDirectory
        )
        return exists && isDirectory.boolValue ? "Repair" : "Install"
    }

    private func operationProgressTitle() -> String {
        switch activeOperation {
        case "Repair":
            return "Repairing…"
        case "Update":
            return "Updating…"
        case "Roll Back":
            return "Rolling back…"
        case "Uninstall":
            return "Uninstalling…"
        default:
            return "Installing…"
        }
    }

    private func refreshOperationCopy() {
        guard state != .installing && state != .complete else {
            return
        }
        activeOperation = operationVerb(for: normalizedInstallRoot())
        let backupPath = packageManagedBackupPath(for: normalizedInstallRoot())
            ?? defaultBackupPath()
        backupPathLabel.stringValue = "Backups:    \(backupPath.path)"
        activeUninstallDescription = packageUninstallDescription(for: normalizedInstallRoot())
        heroTitleLabel.stringValue = "\(activeOperation) Elefante"
        installButton.title = "\(activeOperation) Elefante"
        if let retained = activeOperationDescription?.retainedRollback,
           retained.available,
           retained.confirmationToken != nil {
            retainedRollbackButton.title = retained.targetVersion.map {
                "Roll Back to \($0)"
            } ?? "Roll Back Previous Version"
            retainedRollbackButton.isHidden = false
            retainedRollbackButton.isEnabled = true
        } else {
            retainedRollbackButton.isHidden = true
        }
        uninstallButton.isHidden = activeUninstallDescription == nil
        uninstallButton.isEnabled = activeUninstallDescription != nil
        projectCard.isHidden = activeOperation != "Install"
        addProjectButton.isEnabled = activeOperation == "Install"
        refreshProjectSummary()
        setStatus("Ready to \(activeOperation.lowercased())", color: .secondaryLabelColor)
    }

    private func openPathOrParent(_ url: URL, missingMessage: String) {
        let fileManager = FileManager.default
        if fileManager.fileExists(atPath: url.path) {
            NSWorkspace.shared.open(url)
            return
        }

        let fallbackURL = url.deletingLastPathComponent()
        NSWorkspace.shared.open(fallbackURL)
        setStatus(missingMessage, color: .secondaryLabelColor)
        appendLine("Not created yet: \(url.path)", color: .secondaryLabelColor)
    }

    private func wrapInCard(_ content: NSStackView) -> NSView {
        let box = NSBox()
        box.boxType = .custom
        box.borderWidth = 1
        box.cornerRadius = 14
        box.borderColor = .separatorColor
        box.fillColor = .controlBackgroundColor
        box.contentViewMargins = NSSize(width: 18, height: 14)
        box.translatesAutoresizingMaskIntoConstraints = false
        box.widthAnchor.constraint(equalToConstant: 864).isActive = true

        content.translatesAutoresizingMaskIntoConstraints = false
        box.contentView?.addSubview(content)

        if let cardContent = box.contentView {
            NSLayoutConstraint.activate([
                content.leadingAnchor.constraint(equalTo: cardContent.leadingAnchor),
                content.trailingAnchor.constraint(equalTo: cardContent.trailingAnchor),
                content.topAnchor.constraint(equalTo: cardContent.topAnchor),
                content.bottomAnchor.constraint(equalTo: cardContent.bottomAnchor),
            ])
        }

        return box
    }

    private func makeLabel(_ text: String, font: NSFont, color: NSColor, wrapping: Bool = false) -> NSTextField {
        let label = NSTextField(labelWithString: text)
        label.font = font
        label.textColor = color
        label.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        if wrapping {
            label.lineBreakMode = .byWordWrapping
            label.maximumNumberOfLines = 0
            label.preferredMaxLayoutWidth = 820
        }
        return label
    }

    @objc private func browseLocation() {
        guard state != .installing else {
            return
        }

        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = true
        panel.allowsMultipleSelection = false
        panel.prompt = "Choose Install Folder"

        let expandedPath = NSString(string: pathField.stringValue).expandingTildeInPath
        panel.directoryURL = URL(fileURLWithPath: expandedPath).deletingLastPathComponent()

        if panel.runModal() == .OK, let url = panel.url {
            pathField.stringValue = url.path
            refreshArtifactLabels()
            refreshOperationCopy()
        }
    }

    @objc private func addProjectFolder() {
        guard state != .installing && activeOperation == "Install" else {
            return
        }
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = false
        panel.allowsMultipleSelection = true
        panel.prompt = "Add Project"
        panel.message = "Choose the real project folders whose memories Elefante should keep isolated."
        if panel.runModal() == .OK {
            for url in panel.urls.map(\.standardizedFileURL)
                where !projectURLs.contains(where: { $0.path == url.path }) {
                projectURLs.append(url)
            }
            refreshProjectSummary()
        }
    }

    @objc private func removeLastProject() {
        guard state != .installing && !projectURLs.isEmpty else {
            return
        }
        projectURLs.removeLast()
        refreshProjectSummary()
    }

    @objc private func pathFieldDidChange() {
        requestedRetainedRollbackToken = nil
        refreshArtifactLabels()
        refreshOperationCopy()
    }

    @objc private func openSummaryFile() {
        openPathOrParent(summaryFileURL(), missingMessage: "Summary file will be written during installation.")
    }

    @objc private func openStatusFile() {
        openPathOrParent(statusFileURL(), missingMessage: "Status file will be written during installation.")
    }

    @objc private func openLogFile() {
        openPathOrParent(logFileURL(), missingMessage: "Log file will be written during installation.")
    }

    @objc private func openInstallFolder() {
        let installRoot = normalizedInstallRoot()
        let target = FileManager.default.fileExists(atPath: installRoot.path)
            ? installRoot
            : installRoot.deletingLastPathComponent()
        NSWorkspace.shared.open(target)
    }

    @objc private func handlePrimaryAction() {
        switch state {
        case .ready, .failed:
            startInstall()
        case .complete:
            NSApp.terminate(nil)
        case .installing:
            break
        }
    }

    private func confirmCodeRollback(currentVersion: String, targetVersion: String) -> Bool {
        let alert = NSAlert()
        alert.messageText = "Roll Back Elefante?"
        alert.informativeText = """
            Product code will change from \(currentVersion) to \(targetVersion).

            Your memories will not be restored or reversed. Elefante will create a verified data backup first and restore the current code automatically if the target fails verification.
            """
        alert.alertStyle = .warning
        alert.addButton(withTitle: "Roll Back Product Code")
        alert.addButton(withTitle: "Cancel")
        return alert.runModal() == .alertFirstButtonReturn
    }

    private func confirmUninstall() -> Bool {
        let alert = NSAlert()
        alert.messageText = "Uninstall Elefante?"
        alert.informativeText = """
            Elefante app files and unchanged Elefante-owned agent connections will be removed. A verified backup is created first.

            Your memories remain on this Mac for reinstall. Modified customer configuration is preserved. Create a support report first if you are uninstalling to diagnose a problem.
            """
        alert.alertStyle = .warning
        alert.addButton(withTitle: "Uninstall and Preserve Memories")
        alert.addButton(withTitle: "Cancel")
        return alert.runModal() == .alertFirstButtonReturn
    }

    @objc private func handleUninstall() {
        guard state != .installing else {
            return
        }
        activeUninstallDescription = packageUninstallDescription(for: normalizedInstallRoot())
        guard let token = activeUninstallDescription?.confirmationToken else {
            setStatus("Use the exact official package that installed Elefante", color: errorColor)
            refreshOperationCopy()
            return
        }
        guard confirmUninstall() else {
            setStatus("Uninstall cancelled; nothing changed", color: .secondaryLabelColor)
            return
        }
        requestedUninstallToken = token
        requestedRetainedRollbackToken = nil
        startInstall()
    }

    @objc private func handleRetainedRollback() {
        guard state != .installing else {
            return
        }
        _ = operationVerb(for: normalizedInstallRoot())
        guard let retained = activeOperationDescription?.retainedRollback,
              retained.available,
              let token = retained.confirmationToken else {
            setStatus("No exact verified previous product is available", color: errorColor)
            refreshOperationCopy()
            return
        }
        let currentVersion = retained.currentVersion ?? "current version"
        let targetVersion = retained.targetVersion ?? "previous version"
        guard confirmCodeRollback(
            currentVersion: currentVersion,
            targetVersion: targetVersion
        ) else {
            setStatus("Code rollback cancelled; nothing changed", color: .secondaryLabelColor)
            return
        }
        requestedRetainedRollbackToken = token
        requestedUninstallToken = nil
        startInstall()
    }

    private func startInstall() {
        let installRoot = normalizedInstallRoot()
        let installPath = installRoot.path
        guard !installPath.isEmpty else {
            setStatus("Please choose an install location", color: errorColor)
            return
        }
        let selectedHosts = selectedHostIDs()
        let retainedRollbackToken = requestedRetainedRollbackToken
        let uninstallToken = requestedUninstallToken
        if uninstallToken == nil && !selectedHosts.contains("codex") {
            setStatus("Install Codex before running the certified Elefante setup", color: errorColor)
            return
        }
        if uninstallToken != nil {
            activeOperation = "Uninstall"
        } else if retainedRollbackToken != nil {
            activeOperation = "Roll Back"
        } else {
            activeOperation = operationVerb(for: installRoot)
        }
        let selectedProjects = projectSpecs()
        if activeOperation == "Install" && selectedProjects.isEmpty {
            setStatus("Choose at least one project folder", color: errorColor)
            return
        }
        if uninstallToken == nil && retainedRollbackToken == nil && activeOperation == "Roll Back" {
            guard let description = activeOperationDescription,
                  description.confirmationToken != nil else {
                setStatus("Code rollback cannot be verified from this package", color: errorColor)
                return
            }
            let currentVersion = description.currentVersion ?? "current version"
            let targetVersion = description.targetVersion ?? "older version"
            guard confirmCodeRollback(
                currentVersion: currentVersion,
                targetVersion: targetVersion
            ) else {
                setStatus("Code rollback cancelled; nothing changed", color: .secondaryLabelColor)
                return
            }
        }

        state = .installing
        cancelRequested = false
        seenMarkers.removeAll()
        pendingOutput = ""
        progressBar.doubleValue = 0
        outputView.textStorage?.setAttributedString(NSAttributedString(string: ""))
        setStatus("Starting \(activeOperation.lowercased())…", color: .secondaryLabelColor)
        setControlsEnabled(false)
        installButton.title = operationProgressTitle()
        refreshArtifactLabels()
        if uninstallToken != nil {
            appendLine("A verified backup will be created before app removal.", color: .secondaryLabelColor)
            appendLine("Memories remain local and available for reinstall.", color: .secondaryLabelColor)
        } else {
            for line in renderInstallArtifactPaths() {
                appendLine(line, color: .secondaryLabelColor)
            }
            let previewHosts = selectedHosts.filter { $0 != "codex" }
            appendLine(
                "Certified host: Codex" + (
                    previewHosts.isEmpty
                        ? ""
                        : "; compatibility previews: \(previewHosts.joined(separator: ", "))"
                ),
                color: .secondaryLabelColor
            )
            if activeOperation == "Install" {
                appendLine(
                    "Projects: \(selectedProjects.count) isolated folder(s); disposable Recall and local backup included",
                    color: .secondaryLabelColor
                )
            }
        }
        appendLine("")

        let scriptURL = installerDir.appendingPathComponent("install.sh")
        let pipe = Pipe()
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        var processArguments: [String]
        if let uninstallToken {
            processArguments = [
                scriptURL.path,
                "--install-root", installPath,
                "--uninstall", uninstallToken,
            ]
        } else if let retainedRollbackToken {
            processArguments = [
                scriptURL.path,
                "--install-root", installPath,
                "--rollback-retained", retainedRollbackToken,
            ]
        } else {
            processArguments = [
                scriptURL.path,
                "--install-root", installPath,
                "--venv-mode", "fresh",
                "--verbose",
            ]
            for host in selectedHosts {
                processArguments.append(contentsOf: ["--host", host])
            }
            if activeOperation == "Install" {
                for project in selectedProjects {
                    processArguments.append(contentsOf: ["--project", project])
                }
            }
        }
        if uninstallToken == nil,
           retainedRollbackToken == nil,
           activeOperation == "Roll Back",
           let confirmationToken = activeOperationDescription?.confirmationToken {
            processArguments.append(contentsOf: ["--confirm-code-rollback", confirmationToken])
        }
        process.arguments = processArguments
        process.currentDirectoryURL = installerDir
        process.standardOutput = pipe
        process.standardError = pipe

        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else {
                return
            }
            let chunk = String(decoding: data, as: UTF8.self)
            DispatchQueue.main.async {
                self?.consumeOutput(chunk)
            }
        }

        process.terminationHandler = { [weak self] process in
            DispatchQueue.main.async {
                self?.outputPipe?.fileHandleForReading.readabilityHandler = nil
                self?.finishInstall(exitCode: process.terminationStatus)
            }
        }

        do {
            try process.run()
            self.outputPipe = pipe
            self.process = process
        } catch {
            appendLine("ERROR: \(error.localizedDescription)", color: errorColor)
            finishInstall(exitCode: 1)
        }
    }

    private func consumeOutput(_ chunk: String) {
        pendingOutput += chunk.replacingOccurrences(of: "\r\n", with: "\n")

        let pieces = pendingOutput.components(separatedBy: "\n")
        pendingOutput = pieces.last ?? ""

        for line in pieces.dropLast() {
            handleLine(line)
        }
    }

    private func handleLine(_ line: String) {
        guard !line.isEmpty else {
            appendLine("")
            return
        }

        appendLine(line, color: colorForOutput(line))

        for marker in stageMarkers where line.contains(marker) && !seenMarkers.contains(marker) {
            seenMarkers.insert(marker)
            progressBar.doubleValue = Double(seenMarkers.count)

            if line.hasPrefix("[Step") {
                let cleaned = line.replacingOccurrences(of: #"^\[Step [^\]]+\]\s*"#, with: "", options: .regularExpression)
                setStatus("Installing: \(cleaned)", color: .secondaryLabelColor)
            } else if line.contains("PRE-FLIGHT") {
                setStatus("Running pre-flight checks…", color: .secondaryLabelColor)
            } else if line.contains("Purging") {
                setStatus("Purging stale bytecode…", color: .secondaryLabelColor)
            } else if line.contains("MCP handshake") {
                setStatus("Verifying MCP handshake…", color: .secondaryLabelColor)
            }
            break
        }
    }

    private func finishInstall(exitCode: Int32) {
        process = nil
        outputPipe = nil

        if !pendingOutput.isEmpty {
            handleLine(pendingOutput)
            pendingOutput = ""
        }

        if exitCode == 0 {
            state = .complete
            progressBar.doubleValue = Double(stageMarkers.count)
            let completeMessage: String
            switch activeOperation {
            case "Repair":
                completeMessage = "Repair verified — Elefante, agent connection, and Recall are ready."
            case "Update":
                completeMessage = "Update verified — Elefante, agent connection, and Recall are ready."
            case "Roll Back":
                completeMessage = "Code rollback verified — Elefante, agent connection, and Recall are ready."
            case "Uninstall":
                completeMessage = "Uninstall verified — app removed and memories preserved for reinstall."
            default:
                completeMessage = "Installation verified — projects, Recall cleanup, and local backup are ready."
            }
            setStatus(completeMessage, color: successColor)
            appendLine("")
            appendLine(completeMessage, color: successColor)
            installButton.title = "Done"
            setControlsEnabled(false)
        } else {
            state = .failed
            let failureMessage = cancelRequested
                ? "\(activeOperation) stopped — use the recovery files below"
                : "\(activeOperation) failed — use the recovery files below"
            setStatus(failureMessage, color: errorColor)
            appendLine("")
            appendLine(
                cancelRequested
                    ? "\(activeOperation) stopped before completion."
                    : "\(activeOperation) failed.",
                color: errorColor
            )
            for line in renderFailedInstallGuidance() {
                appendLine(line, color: .secondaryLabelColor)
            }
            installButton.title = "Retry"
            setControlsEnabled(true)
        }
        cancelRequested = false
    }

    private func setControlsEnabled(_ enabled: Bool) {
        pathField.isEnabled = enabled
        browseButton.isEnabled = enabled
        for button in hostButtons.values {
            button.isEnabled = enabled
        }
        addProjectButton.isEnabled = enabled && activeOperation == "Install"
        removeProjectButton.isEnabled = enabled && !projectURLs.isEmpty && activeOperation == "Install"
        retainedRollbackButton.isEnabled = enabled && !retainedRollbackButton.isHidden
        uninstallButton.isEnabled = enabled && !uninstallButton.isHidden
        installButton.isEnabled = state == .complete
            || (enabled && (activeOperation != "Install" || !projectURLs.isEmpty))
    }

    private func setStatus(_ text: String, color: NSColor) {
        statusLabel.stringValue = text
        statusLabel.textColor = color
    }

    private func appendLine(_ line: String, color: NSColor = .labelColor) {
        let attributes: [NSAttributedString.Key: Any] = [
            .font: NSFont.monospacedSystemFont(ofSize: 11, weight: .regular),
            .foregroundColor: color,
        ]
        let attributed = NSAttributedString(string: line + "\n", attributes: attributes)
        outputView.textStorage?.append(attributed)
        outputView.scrollToEndOfDocument(nil)
    }

    private func colorForOutput(_ line: String) -> NSColor {
        if line.hasPrefix("OK:") {
            return successColor
        }
        if line.hasPrefix("ERROR") {
            return errorColor
        }
        if line.hasPrefix("WARN") {
            return NSColor.systemOrange
        }
        if line.hasPrefix("[Step") {
            return accentColor
        }
        return .labelColor
    }

    private func showFatalAlert(message: String) {
        let alert = NSAlert()
        alert.messageText = "Elefante Installer"
        alert.informativeText = message
        alert.alertStyle = .critical
        alert.addButton(withTitle: "OK")
        alert.runModal()
        NSApp.terminate(nil)
    }

    private func defaultInstallPath() -> URL {
        URL(fileURLWithPath: NSHomeDirectory())
            .appendingPathComponent(".elefante", isDirectory: true)
            .appendingPathComponent("app", isDirectory: true)
            .appendingPathComponent("current", isDirectory: true)
    }

    private func defaultDataPath() -> URL {
        URL(fileURLWithPath: NSHomeDirectory())
            .appendingPathComponent(".elefante", isDirectory: true)
            .appendingPathComponent("data", isDirectory: true)
    }

    private func defaultBackupPath() -> URL {
        URL(fileURLWithPath: NSHomeDirectory())
            .appendingPathComponent(".elefante", isDirectory: true)
            .appendingPathComponent("backups", isDirectory: true)
    }
}

@main
struct InstallerMain {
    static func main() {
        let app = NSApplication.shared
        let delegate = InstallerApp()
        app.setActivationPolicy(.regular)
        app.delegate = delegate
        app.run()
    }
}
