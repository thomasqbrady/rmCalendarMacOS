"""TUI for selecting calendars and generating a planner PDF."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Center, Vertical
from textual.screen import Screen, ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    SelectionList,
    Static,
)
from textual.widgets.selection_list import Selection

from rmcal.calendar.macos import MacCalendar, list_macos_calendars, fetch_macos_events
from rmcal.models import DateRange, PlannerConfig
from rmcal.planner.generator import generate_planner, count_pages
from rmcal.state import (
    get_meeting_notes_calendar_ids,
    get_selected_calendar_ids,
    save_meeting_notes_calendar_ids,
    save_selected_calendar_ids,
)


class CalendarSelectionList(SelectionList[str]):
    """SelectionList that uses Space to toggle, not Enter."""

    def _on_key(self, event) -> None:
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            self.app.action_generate()
        else:
            super()._on_key(event)


class MeetingNotesSelectionList(SelectionList[str]):
    """SelectionList for meeting notes screen — Enter submits."""

    def _on_key(self, event) -> None:
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            screen = self.screen
            if isinstance(screen, MeetingNotesScreen):
                screen.action_submit()
        else:
            super()._on_key(event)


class MeetingNotesScreen(Screen):
    """Second screen: select which calendars generate meeting notes pages."""

    CSS = """
    #mn-title {
        dock: top;
        height: 3;
        content-align: center middle;
        background: $primary;
        color: $text;
        text-style: bold;
        padding: 0 2;
    }

    #mn-description {
        height: auto;
        max-height: 6;
        margin: 1 2 0 2;
        padding: 1 2;
        background: $surface;
        color: $text-muted;
    }

    #mn-list {
        height: 1fr;
        border: solid $primary;
        margin: 1 2;
    }

    #mn-button-bar {
        dock: bottom;
        height: 3;
        padding: 0 2;
        align: center middle;
        layout: horizontal;
    }

    #mn-button-bar Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("a", "select_all", "Select all"),
        Binding("n", "select_none", "Select none"),
        Binding("enter", "submit", "Continue"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(
        self,
        calendars: list[MacCalendar],
        selected_calendar_ids: set[str],
    ) -> None:
        super().__init__()
        self._calendars = calendars
        self._selected_calendar_ids = selected_calendar_ids

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static(
            "rmCalendarMacOS — Meeting Notes",
            id="mn-title",
        )
        yield Static(
            "Select calendars that should generate meeting notes pages. "
            "Each meeting from a checked calendar will get a dedicated notes page "
            "with the meeting time, name, attendees, and lined space for writing.",
            id="mn-description",
        )
        yield MeetingNotesSelectionList(id="mn-list")
        with Horizontal(id="mn-button-bar"):
            yield Button("Continue", id="mn-continue", variant="success")
            yield Button("Skip (no meeting notes)", id="mn-skip", variant="default")
            yield Button("Back", id="mn-back", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self._populate()

    def _populate(self) -> None:
        sel_list = self.query_one("#mn-list", MeetingNotesSelectionList)
        saved_ids = get_meeting_notes_calendar_ids()

        # Only show calendars that were selected on the first screen
        available = [c for c in self._calendars if c.calendar_id in self._selected_calendar_ids]

        sources: dict[str, list[MacCalendar]] = {}
        for cal in available:
            source = cal.source or "Local"
            sources.setdefault(source, []).append(cal)

        selections: list[Selection[str]] = []
        for source_name, cals in sorted(sources.items()):
            for cal in cals:
                checked = cal.calendar_id in saved_ids if saved_ids is not None else False
                label = f"[bold]{source_name}[/bold] / {cal.title}"
                selections.append(Selection(label, cal.calendar_id, checked))

        sel_list.add_options(selections)

    def action_select_all(self) -> None:
        self.query_one("#mn-list", MeetingNotesSelectionList).select_all()

    def action_select_none(self) -> None:
        self.query_one("#mn-list", MeetingNotesSelectionList).deselect_all()

    def action_submit(self) -> None:
        sel_list = self.query_one("#mn-list", MeetingNotesSelectionList)
        selected = set(sel_list.selected)
        save_meeting_notes_calendar_ids(selected)
        self.dismiss(selected)

    def action_back(self) -> None:
        self.dismiss(None)  # None = go back, don't generate

    @on(Button.Pressed, "#mn-continue")
    def on_continue(self) -> None:
        self.action_submit()

    @on(Button.Pressed, "#mn-skip")
    def on_skip(self) -> None:
        save_meeting_notes_calendar_ids(set())
        self.dismiss(set())  # empty set = no meeting notes

    @on(Button.Pressed, "#mn-back")
    def on_back(self) -> None:
        self.action_back()


class RegisterScreen(ModalScreen):
    """Modal for first-time reMarkable Cloud registration."""

    CSS = """
    RegisterScreen {
        align: center middle;
    }

    #register-dialog {
        width: 65;
        height: auto;
        max-height: 20;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #register-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #register-steps {
        margin-bottom: 1;
        color: $text-muted;
    }

    #register-input {
        margin-bottom: 1;
    }

    #register-status {
        height: auto;
        margin-bottom: 1;
    }

    #register-buttons {
        height: 3;
        align: center middle;
        layout: horizontal;
    }

    #register-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="register-dialog"):
            yield Static("reMarkable Cloud Registration", id="register-title")
            yield Static(
                "1. Go to: https://my.remarkable.com/device/remarkable?showOtp=true\n"
                "2. Log in and copy the 8-character code\n"
                "3. Paste it below and press Register",
                id="register-steps",
            )
            yield Input(placeholder="Enter 8-character code", id="register-input")
            yield Static("", id="register-status")
            with Horizontal(id="register-buttons"):
                yield Button("Register", id="register-submit", variant="success")
                yield Button("Cancel", id="register-cancel", variant="default")

    def on_mount(self) -> None:
        self.query_one("#register-input", Input).focus()

    @on(Input.Submitted, "#register-input")
    def on_input_submitted(self) -> None:
        self._do_register()

    @on(Button.Pressed, "#register-submit")
    def on_submit(self) -> None:
        self._do_register()

    @on(Button.Pressed, "#register-cancel")
    def on_cancel(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)

    @work(thread=True)
    def _do_register(self) -> None:
        code = self.app.call_from_thread(self._get_code)
        if not code:
            self.app.call_from_thread(self._set_status, "Please enter a code.")
            return

        self.app.call_from_thread(self._set_status, "Registering...")
        try:
            from rmcal.remarkable.cloud import RemarkableCloud
            with RemarkableCloud() as cloud:
                cloud.register_device(code)
            self.app.call_from_thread(self._set_status, "Success!")
            import time
            time.sleep(1)
            self.app.call_from_thread(self.dismiss, True)
        except Exception as e:
            self.app.call_from_thread(self._set_status, f"Error: {e}")

    def _get_code(self) -> str:
        return self.query_one("#register-input", Input).value.strip()

    def _set_status(self, msg: str) -> None:
        self.query_one("#register-status", Static).update(msg)


class DoneScreen(ModalScreen):
    """Modal confirmation dialog shown after generation/upload completes."""

    CSS = """
    DoneScreen {
        align: center middle;
    }

    #done-dialog {
        width: 60;
        height: auto;
        max-height: 12;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #done-message {
        text-align: center;
        margin-bottom: 1;
    }

    #done-ok {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("enter", "ok", "OK"),
        Binding("escape", "ok", "OK"),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="done-dialog"):
            yield Static(self._message, id="done-message")
            yield Button("OK", id="done-ok", variant="success")

    def action_ok(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#done-ok")
    def on_ok(self) -> None:
        self.dismiss(True)


class DaemonSetupScreen(ModalScreen):
    """Modal offering to enable auto-sync after first successful upload."""

    CSS = """
    DaemonSetupScreen {
        align: center middle;
    }

    #daemon-setup-dialog {
        width: 55;
        height: auto;
        max-height: 14;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #daemon-setup-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #daemon-setup-desc {
        margin-bottom: 1;
        color: $text-muted;
    }

    #daemon-setup-buttons {
        height: 3;
        align: center middle;
        layout: horizontal;
    }

    #daemon-setup-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("enter", "enable", "Enable"),
        Binding("escape", "skip", "No Thanks"),
    ]

    def __init__(self, document_name: str) -> None:
        super().__init__()
        self._document_name = document_name

    def compose(self) -> ComposeResult:
        with Vertical(id="daemon-setup-dialog"):
            yield Static("Enable auto-sync?", id="daemon-setup-title")
            yield Static(
                "rmCalendarMacOS can sync your planner to reMarkable "
                "automatically every 15 minutes in the background. "
                "No terminal needed.",
                id="daemon-setup-desc",
            )
            with Horizontal(id="daemon-setup-buttons"):
                yield Button("Enable Auto-Sync", id="daemon-enable", variant="success")
                yield Button("No Thanks", id="daemon-skip", variant="default")

    def action_enable(self) -> None:
        from rmcal.daemon import install_daemon
        install_daemon(document_name=self._document_name)
        self.dismiss(True)

    def action_skip(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#daemon-enable")
    def on_enable(self) -> None:
        self.action_enable()

    @on(Button.Pressed, "#daemon-skip")
    def on_skip(self) -> None:
        self.action_skip()


class DaemonStatusScreen(ModalScreen):
    """Modal showing daemon status with start/stop controls."""

    CSS = """
    DaemonStatusScreen {
        align: center middle;
    }

    #daemon-status-dialog {
        width: 55;
        height: auto;
        max-height: 14;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #daemon-status-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #daemon-status-info {
        margin-bottom: 1;
        color: $text-muted;
    }

    #daemon-status-buttons {
        height: 3;
        align: center middle;
        layout: horizontal;
    }

    #daemon-status-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        from rmcal.daemon import is_daemon_running, is_daemon_installed, get_daemon_log_path

        installed = is_daemon_installed()
        running = is_daemon_running()

        if running:
            status_text = "Status: Running (syncs every 15 min)"
            log_text = f"Log: {get_daemon_log_path()}"
            info = f"{status_text}\n{log_text}"
        elif installed:
            status_text = "Status: Installed but not running"
            info = status_text
        else:
            info = "Status: Not enabled"

        with Vertical(id="daemon-status-dialog"):
            yield Static("Auto-Sync Daemon", id="daemon-status-title")
            yield Static(info, id="daemon-status-info")
            with Horizontal(id="daemon-status-buttons"):
                if running or installed:
                    yield Button("Stop Auto-Sync", id="daemon-stop", variant="error")
                else:
                    yield Button("Enable Auto-Sync", id="daemon-start", variant="success")
                yield Button("Back", id="daemon-back", variant="default")

    def action_back(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#daemon-stop")
    def on_stop(self) -> None:
        from rmcal.daemon import uninstall_daemon
        uninstall_daemon()
        self.dismiss("stopped")

    @on(Button.Pressed, "#daemon-start")
    def on_start(self) -> None:
        from rmcal.daemon import install_daemon
        install_daemon()
        self.dismiss("started")

    @on(Button.Pressed, "#daemon-back")
    def on_back(self) -> None:
        self.action_back()


class CalendarSelector(App):
    """TUI app for selecting calendars and generating a reMarkable planner."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #title-bar {
        dock: top;
        height: 3;
        content-align: center middle;
        background: $primary;
        color: $text;
        text-style: bold;
        padding: 0 2;
    }

    #calendar-list {
        height: 1fr;
        border: solid $primary;
        margin: 1 2;
    }

    #status-bar {
        dock: bottom;
        height: 3;
        padding: 0 2;
        content-align: left middle;
        background: $surface;
    }

    #button-bar {
        dock: bottom;
        height: 3;
        padding: 0 2;
        align: center middle;
        layout: horizontal;
    }

    #button-bar Button {
        margin: 0 1;
    }

    #btn-generate {
        background: $success;
    }
    """

    BINDINGS = [
        Binding("a", "select_all", "Select all"),
        Binding("n", "select_none", "Select none"),
        Binding("enter", "generate", "Next"),
        Binding("d", "daemon", "Daemon"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        output_path: Path = Path("planner.pdf"),
        start_date: date | None = None,
        end_date: date | None = None,
        upload_cloud: bool = False,
        document_name: str = "rmCalendar",
    ):
        super().__init__()
        self.output_path = output_path
        self.calendars: list[MacCalendar] = []
        self._start = start_date
        self._end = end_date
        self._upload_cloud = upload_cloud
        self._document_name = document_name

    @property
    def date_range(self) -> DateRange:
        if self._start:
            start = self._start
        else:
            today = date.today()
            start = today.replace(day=1)

        if self._end:
            end = self._end
        else:
            year = start.year + (start.month + 11) // 12
            month = (start.month + 11) % 12 + 1
            end = date(year, month, 1) - timedelta(days=1)

        return DateRange(start=start, end=end)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("rmCalendarMacOS — Select calendars for your reMarkable planner", id="title-bar")
        yield CalendarSelectionList(id="calendar-list")
        with Horizontal(id="button-bar"):
            yield Button("Next", id="btn-generate", variant="success")
            yield Button("Daemon", id="btn-daemon", variant="default")
            yield Button("Quit", id="btn-quit", variant="default")
        yield Static("Loading calendars...", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        if self._upload_cloud:
            self._check_cloud_auth()
        else:
            self.load_calendars()

    def _check_cloud_auth(self) -> None:
        from rmcal.remarkable.cloud import TOKEN_FILE
        if TOKEN_FILE.exists():
            self.load_calendars()
        else:
            self.push_screen(RegisterScreen(), self._on_register_done)

    def _on_register_done(self, success: bool) -> None:
        if success:
            self.load_calendars()
        else:
            self._update_status("Registration cancelled. Cloud upload disabled.")
            self._upload_cloud = False
            self.load_calendars()

    @work(thread=True)
    def load_calendars(self) -> None:
        try:
            self.calendars = list_macos_calendars()
        except PermissionError as e:
            self.call_from_thread(self._show_error, str(e))
            return
        self.call_from_thread(self._populate_calendars)

    def _populate_calendars(self) -> None:
        sel_list = self.query_one("#calendar-list", CalendarSelectionList)
        sel_list.clear_options()

        if not self.calendars:
            self._update_status("No calendars available")
            return

        saved_ids = get_selected_calendar_ids()

        sources: dict[str, list[MacCalendar]] = {}
        for cal in self.calendars:
            source = cal.source or "Local"
            sources.setdefault(source, []).append(cal)

        selections: list[Selection[str]] = []
        for source_name, cals in sorted(sources.items()):
            for cal in cals:
                checked = cal.calendar_id in saved_ids if saved_ids is not None else True
                label = f"[bold]{source_name}[/bold] / {cal.title}"
                selections.append(Selection(label, cal.calendar_id, checked))

        sel_list.add_options(selections)

        dr = self.date_range
        selected = sel_list.selected
        total = len(self.calendars)
        self._update_status(
            f"{len(selected)}/{total} calendars selected  •  "
            f"Date range: {dr.start} → {dr.end}  •  "
            f"Press Enter to continue"
        )

    def _show_error(self, msg: str) -> None:
        status = self.query_one("#status-bar", Static)
        status.update(f"ERROR: {msg}")

    def _update_status(self, msg: str) -> None:
        status = self.query_one("#status-bar", Static)
        status.update(msg)

    def _show_done(self, msg: str) -> None:
        self.push_screen(DoneScreen(msg), callback=self._on_done_dismissed)

    def _on_done_dismissed(self, _result: object) -> None:
        """After Done dialog, offer daemon setup if applicable."""
        from rmcal.daemon import is_daemon_installed

        if self._upload_cloud and not is_daemon_installed():
            self.push_screen(
                DaemonSetupScreen(self._document_name),
                callback=lambda _: self.exit(),
            )
        else:
            self.exit()

    def _get_selected_ids(self) -> set[str]:
        sel_list = self.query_one("#calendar-list", CalendarSelectionList)
        return set(sel_list.selected)

    def action_select_all(self) -> None:
        sel_list = self.query_one("#calendar-list", CalendarSelectionList)
        sel_list.select_all()

    def action_select_none(self) -> None:
        sel_list = self.query_one("#calendar-list", CalendarSelectionList)
        sel_list.deselect_all()

    def action_daemon(self) -> None:
        self.push_screen(DaemonStatusScreen(), self._on_daemon_status_done)

    def _on_daemon_status_done(self, result: str | None) -> None:
        if result == "stopped":
            self._update_status("Auto-sync stopped")
        elif result == "started":
            self._update_status("Auto-sync enabled (every 15 min)")

    @on(SelectionList.SelectedChanged)
    def on_selection_changed(self) -> None:
        selected = self._get_selected_ids()
        total = len(self.calendars)
        dr = self.date_range
        self._update_status(
            f"{len(selected)}/{total} calendars selected  •  "
            f"Date range: {dr.start} → {dr.end}  •  "
            f"Press Enter to continue"
        )

    @on(Button.Pressed, "#btn-generate")
    def on_generate_pressed(self) -> None:
        self.action_generate()

    @on(Button.Pressed, "#btn-daemon")
    def on_daemon_pressed(self) -> None:
        self.action_daemon()

    @on(Button.Pressed, "#btn-quit")
    def on_quit_pressed(self) -> None:
        self.exit()

    def action_generate(self) -> None:
        selected = self._get_selected_ids()
        if not selected:
            self._update_status("No calendars selected!")
            return

        save_selected_calendar_ids(selected)

        # Show meeting notes screen
        screen = MeetingNotesScreen(self.calendars, selected)
        self.push_screen(screen, self._on_meeting_notes_done)

    def _on_meeting_notes_done(self, result: set[str] | None) -> None:
        """Callback when the meeting notes screen is dismissed."""
        if result is None:
            # User pressed Back — stay on calendar selection screen
            return

        selected = self._get_selected_ids()
        meeting_notes_ids = result  # may be empty set (skip)

        self._update_status("Generating...")
        self.do_generate(selected, meeting_notes_ids)

    @work(thread=True)
    def do_generate(self, calendar_ids: set[str], meeting_notes_ids: set[str]) -> None:
        try:
            dr = self.date_range
            self.call_from_thread(self._update_status, "Fetching events from macOS Calendar...")

            events = fetch_macos_events(dr, calendar_ids=calendar_ids)
            self.call_from_thread(
                self._update_status,
                f"Found {len(events)} events. Generating PDF..."
            )

            config = PlannerConfig(date_range=dr)
            pdf_path = generate_planner(
                config, events,
                output_path=self.output_path,
                meeting_notes_calendar_ids=meeting_notes_ids or None,
            )
            size_kb = pdf_path.stat().st_size / 1024
            pages = count_pages(config, events, meeting_notes_ids or None)

            if self._upload_cloud:
                self.call_from_thread(self._update_status, "Uploading to reMarkable Cloud...")
                from rmcal.remarkable.cloud import RemarkableCloud
                from rmcal.state import get_cloud_doc_id, save_cloud_doc_id

                with RemarkableCloud() as cloud:
                    if not cloud.is_authenticated:
                        self.call_from_thread(
                            self._update_status,
                            "ERROR: Not authenticated. Run 'python3 generate_my_planner.py register' first."
                        )
                        return

                    saved_id = get_cloud_doc_id()
                    if saved_id:
                        existing = cloud.find_document_by_id(saved_id)
                        if existing:
                            cloud.update_document(existing, pdf_path)
                        else:
                            doc_id = cloud.upload_new_document(self._document_name, pdf_path)
                            save_cloud_doc_id(doc_id)
                    else:
                        doc_id = cloud.upload_new_document(self._document_name, pdf_path)
                        save_cloud_doc_id(doc_id)

                msg = f"Synced to reMarkable Cloud!\n{size_kb:.0f} KB, {pages} pages, {len(events)} events"
                self.call_from_thread(self._show_done, msg)
            else:
                msg = f"Done! Saved to {pdf_path}\n{size_kb:.0f} KB, {pages} pages, {len(events)} events"
                self.call_from_thread(self._show_done, msg)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.call_from_thread(self._update_status, f"ERROR: {e}")

    def action_quit(self) -> None:
        self.exit()


def run_tui(
    output: Path = Path("planner.pdf"),
    start_date: date | None = None,
    end_date: date | None = None,
    upload_cloud: bool = False,
    document_name: str = "rmCalendar",
) -> None:
    """Launch the calendar selector TUI."""
    app = CalendarSelector(
        output_path=output,
        start_date=start_date,
        end_date=end_date,
        upload_cloud=upload_cloud,
        document_name=document_name,
    )
    app.run()
