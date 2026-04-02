class Rmcal < Formula
  include Language::Python::Virtualenv

  desc "Sync macOS Calendar to reMarkable tablets as interactive PDF planners"
  homepage "https://github.com/thomasqbrady/rmCalendarMacOS"
  url "https://github.com/thomasqbrady/rmCalendarMacOS/archive/refs/tags/v0.1.25.tar.gz"
  sha256 "a2b7baf0429263e3ec711822ad65f270f02195cae3eb3316f8825ca85b163db3"
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

    content = plist.read
    return unless content.include?("Cellar")

    # Fix stale versioned Cellar paths in-place. Only runs when the plist
    # still has a hardcoded Cellar path — otherwise the stable symlink at
    # /opt/homebrew/bin/rmcal already points to the new version and
    # launchd will pick it up on the next scheduled run automatically.
    stable_bin = "#{HOMEBREW_PREFIX}/bin/rmcal"
    stable_path_dir = "#{HOMEBREW_PREFIX}/bin"
    quiet_system "sed", "-i", "",
      "-e", "s|/opt/homebrew/Cellar/rmcal/[^/]*/libexec/bin/rmcal|#{stable_bin}|g",
      "-e", "s|/opt/homebrew/Cellar/rmcal/[^/]*/libexec/bin|#{stable_path_dir}|g",
      plist.to_s

    # Reload so launchd picks up the rewritten paths
    quiet_system "launchctl", "unload", plist
    quiet_system "launchctl", "load", plist
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
