class Rmcal < Formula
  include Language::Python::Virtualenv

  desc "Sync macOS Calendar to reMarkable tablets as interactive PDF planners"
  homepage "https://github.com/thomasqbrady/rmCalendarMacOS"
  url "https://github.com/thomasqbrady/rmCalendarMacOS/archive/refs/tags/v0.1.29.tar.gz"
  sha256 "59c7277d84c006d2ca21344aa775bf6ca6b96317f6d4d4408c30a2c65109b593"
  license "MIT"
  head "https://github.com/thomasqbrady/rmCalendarMacOS.git", branch: "main"

  depends_on :macos
  depends_on "python@3.12"

  def install
    python3 = "python3.12"
    venv = libexec

    # Create venv WITH pip
    system python3, "-m", "venv", venv
    system venv/"bin/pip", "install", "--upgrade", "pip"
    system venv/"bin/pip", "install", "hatchling"
    system venv/"bin/pip", "install", "--no-build-isolation", buildpath

    # Link the binary
    (bin/"rmcal").write_env_script venv/"bin/rmcal", PATH: "#{venv}/bin:${PATH}"
  end

  def post_install
    plist = Pathname.new("#{Dir.home}/Library/LaunchAgents/com.rmcal.daemon.plist")
    return unless plist.exist?

    # Fix stale versioned Cellar paths if present.
    # Do NOT unload/load the daemon here — launchctl load silently fails in
    # Homebrew's post_install context, leaving the daemon permanently dead.
    # Instead, leave launchd's job registration intact. The daemon may crash
    # once after reinstall (code signature invalidation), but launchd will
    # retry at the next 5-minute interval with the new binaries.
    return unless plist.read.include?("Cellar")

    stable_bin = "#{HOMEBREW_PREFIX}/bin/rmcal"
    stable_path_dir = "#{HOMEBREW_PREFIX}/bin"
    quiet_system "sed", "-i", "",
      "-e", "s|/opt/homebrew/Cellar/rmcal/[^/]*/libexec/bin/rmcal|#{stable_bin}|g",
      "-e", "s|/opt/homebrew/Cellar/rmcal/[^/]*/libexec/bin|#{stable_path_dir}|g",
      plist.to_s
  end

  def caveats
    <<~EOS
      To get started, just run:
        rmcal

      You'll be guided through setup on first launch.

      To enable auto-sync (every 5 min):
        rmcal daemon install
    EOS
  end

  test do
    assert_match "rmCalendarMacOS", shell_output("#{bin}/rmcal --help")
  end
end
