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

final class InstallerApp: NSObject, NSApplicationDelegate, NSWindowDelegate {
    private let accentColor = NSColor(calibratedRed: 0.09, green: 0.50, blue: 0.47, alpha: 1.0)
    private let successColor = NSColor.systemGreen
    private let errorColor = NSColor.systemRed

    private var installerDir: URL = URL(fileURLWithPath: "/")
    private var window: NSWindow?
    private var pathField = NSTextField(string: "")
    private var browseButton = NSButton(title: "Browse…", target: nil, action: nil)
    private var installButton = NSButton(title: "Install Elefante", target: nil, action: nil)
    private var progressBar = NSProgressIndicator()
    private var statusLabel = NSTextField(labelWithString: "Ready to install")
    private var outputView = NSTextView()
    private var outputScrollView = NSScrollView()
    private var summaryPathLabel = NSTextField(labelWithString: "")
    private var statusPathLabel = NSTextField(labelWithString: "")
    private var logPathLabel = NSTextField(labelWithString: "")
    private var openSummaryButton = NSButton(title: "Open Summary", target: nil, action: nil)
    private var openStatusButton = NSButton(title: "Open Status", target: nil, action: nil)
    private var openLogButton = NSButton(title: "Open Log", target: nil, action: nil)
    private var openInstallFolderButton = NSButton(title: "Open Install Folder", target: nil, action: nil)
    private var hostButtons: [String: NSButton] = [:]

    private var process: Process?
    private var outputPipe: Pipe?
    private var pendingOutput = ""
    private var seenMarkers = Set<String>()
    private var state: InstallState = .ready
    private var cancelRequested = false

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
            contentRect: NSRect(x: 0, y: 0, width: 920, height: 760),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Install Elefante"
        window.minSize = NSSize(width: 820, height: 700)
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
        stack.addArrangedSubview(makeActionRow())
        stack.addArrangedSubview(makeProgressSection())
        stack.addArrangedSubview(makeOutputSection())

        installButton.target = self
        installButton.action = #selector(handlePrimaryAction)
        browseButton.target = self
        browseButton.action = #selector(browseLocation)
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
        ]
    }

    private func makeHostCard() -> NSView {
        let cardStack = NSStackView()
        cardStack.orientation = .vertical
        cardStack.spacing = 10
        cardStack.alignment = .leading

        cardStack.addArrangedSubview(makeLabel(
            "Connect Elefante to your agent hosts",
            font: .systemFont(ofSize: 15, weight: .semibold),
            color: .labelColor
        ))
        cardStack.addArrangedSubview(makeLabel(
            "Every compatible host detected on this Mac is connected automatically to one private local memory.",
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
                button.state = host.detected ? .on : .off
                button.isEnabled = false
                button.font = .systemFont(ofSize: 12, weight: host.detected ? .semibold : .regular)
                button.toolTip = host.detected
                    ? "Elefante will configure this detected host automatically"
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
            "One installation. No editor plug-in, copied command, or duplicate memory database.",
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

        textStack.addArrangedSubview(makeLabel(
            "Install Elefante",
            font: .systemFont(ofSize: 32, weight: .bold),
            color: .labelColor
        ))

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

        row.addArrangedSubview(installButton)
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
        }
    }

    @objc private func pathFieldDidChange() {
        refreshArtifactLabels()
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

    private func startInstall() {
        let installRoot = normalizedInstallRoot()
        let installPath = installRoot.path
        guard !installPath.isEmpty else {
            setStatus("Please choose an install location", color: errorColor)
            return
        }
        let selectedHosts = selectedHostIDs()

        state = .installing
        cancelRequested = false
        seenMarkers.removeAll()
        pendingOutput = ""
        progressBar.doubleValue = 0
        outputView.textStorage?.setAttributedString(NSAttributedString(string: ""))
        setStatus("Starting installation…", color: .secondaryLabelColor)
        setControlsEnabled(false)
        installButton.title = "Installing…"
        refreshArtifactLabels()
        for line in renderInstallArtifactPaths() {
            appendLine(line, color: .secondaryLabelColor)
        }
        appendLine(
            selectedHosts.isEmpty
                ? "Agent hosts: none detected; generic MCP bridge installed"
                : "Agent hosts: all detected (\(selectedHosts.joined(separator: ", ")))",
            color: .secondaryLabelColor
        )
        appendLine("")

        let scriptURL = installerDir.appendingPathComponent("install.sh")
        let pipe = Pipe()
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        let processArguments = [
            scriptURL.path,
            "--install-root", installPath,
            "--venv-mode", "fresh",
            "--verbose",
        ]
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
            setStatus("Installation complete!", color: successColor)
            appendLine("")
            appendLine("Installation complete! Restart your IDE to activate Elefante.", color: successColor)
            installButton.title = "Done"
            setControlsEnabled(false)
        } else {
            state = .failed
            let failureMessage = cancelRequested
                ? "Installation stopped — use the recovery files below"
                : "Installation failed — use the recovery files below"
            setStatus(failureMessage, color: errorColor)
            appendLine("")
            appendLine(cancelRequested ? "Installation stopped before completion." : "Installation failed.", color: errorColor)
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
        installButton.isEnabled = true
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
