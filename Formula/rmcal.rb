class Rmcal < Formula
  include Language::Python::Virtualenv

  desc "Sync macOS Calendar to reMarkable tablets as interactive PDF planners"
  homepage "https://github.com/thomasqbrady/rmCalendarMacOS"
  url "https://github.com/thomasqbrady/rmCalendarMacOS/archive/refs/tags/v0.1.1.tar.gz"
  sha256 "084eef7c621813f2b5409ddc5fe453dd0de5edfc717751c42ede41450eb13e62"
  license "MIT"
  head "https://github.com/thomasqbrady/rmCalendarMacOS.git", branch: "main"

  depends_on :macos
  depends_on "python@3.12"

  def install
    venv = virtualenv_create(libexec, "python3.12")
    system libexec/"bin/pip", "install", buildpath
    (bin/"rmcal").write_env_script libexec/"bin/rmcal", PATH: "#{libexec}/bin:${PATH}"
  end

  def caveats
    <<~EOS
      To get started:
        1. Register your reMarkable: rmcal register
        2. Launch the TUI:           rmcal

      macOS will prompt for calendar access on first run.

      To enable auto-sync (every 15 min):
        rmcal daemon install
    EOS
  end

  test do
    assert_match "rmCalendarMacOS", shell_output("#{bin}/rmcal --help")
  end
end
