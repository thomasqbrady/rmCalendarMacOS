class Rmcal < Formula
  include Language::Python::Virtualenv

  desc "Sync macOS Calendar to reMarkable tablets as interactive PDF planners"
  homepage "https://github.com/thomasqbrady/rmCalendarMacOS"
  url "https://github.com/thomasqbrady/rmCalendarMacOS/archive/refs/tags/v0.1.5.tar.gz"
  sha256 "1e51d8d0170b618d7cdea7489e37a2d6deea5bfa4cec0c2f1ecd81344578be63"
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
