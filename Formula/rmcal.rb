class Rmcal < Formula
  include Language::Python::Virtualenv

  desc "Sync macOS Calendar to reMarkable tablets as interactive PDF planners"
  # TODO: Update these after creating the GitHub repo
  homepage "https://github.com/OWNER/rmCalendarMacOS"
  url "https://github.com/OWNER/rmCalendarMacOS/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "PLACEHOLDER_SHA256"
  license "MIT"
  head "https://github.com/OWNER/rmCalendarMacOS.git", branch: "main"

  depends_on :macos
  depends_on "python@3.12"

  def install
    venv = virtualenv_create(libexec, "python3.12")
    venv.pip_install_and_link buildpath
  end

  def caveats
    <<~EOS
      To get started:
        1. Grant calendar access:   python3 #{libexec}/grant_calendar_access.py
        2. Register your reMarkable: rmcal register
        3. Launch the TUI:           rmcal

      To enable auto-sync (every 15 min):
        rmcal daemon install
    EOS
  end

  test do
    assert_match "rmCalendarMacOS", shell_output("#{bin}/rmcal --help")
  end
end
