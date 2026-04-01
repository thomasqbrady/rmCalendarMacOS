"""Multi-language translations for planner content."""

from __future__ import annotations

from rmcal.models import Language

TRANSLATIONS: dict[Language, dict[str, list[str] | str]] = {
    Language.EN: {
        "months": [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ],
        "months_short": [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ],
        "weekdays": [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        ],
        "weekdays_short": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "weekdays_letter": ["M", "T", "W", "T", "F", "S", "S"],
        "all_day": "All Day",
        "week": "Week",
        "no_events": "No events",
        "notes": "Notes",
        "year_overview": "Year Overview",
    },
    Language.FR: {
        "months": [
            "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
        ],
        "months_short": [
            "Jan", "Fév", "Mar", "Avr", "Mai", "Jun",
            "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc",
        ],
        "weekdays": [
            "Lundi", "Mardi", "Mercredi", "Jeudi",
            "Vendredi", "Samedi", "Dimanche",
        ],
        "weekdays_short": ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"],
        "weekdays_letter": ["L", "M", "M", "J", "V", "S", "D"],
        "all_day": "Toute la journée",
        "week": "Semaine",
        "no_events": "Aucun événement",
        "notes": "Notes",
        "year_overview": "Aperçu annuel",
    },
    Language.ES: {
        "months": [
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
        ],
        "months_short": [
            "Ene", "Feb", "Mar", "Abr", "May", "Jun",
            "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
        ],
        "weekdays": [
            "Lunes", "Martes", "Miércoles", "Jueves",
            "Viernes", "Sábado", "Domingo",
        ],
        "weekdays_short": ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
        "weekdays_letter": ["L", "M", "X", "J", "V", "S", "D"],
        "all_day": "Todo el día",
        "week": "Semana",
        "no_events": "Sin eventos",
        "notes": "Notas",
        "year_overview": "Resumen anual",
    },
    Language.IT: {
        "months": [
            "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
        ],
        "months_short": [
            "Gen", "Feb", "Mar", "Apr", "Mag", "Giu",
            "Lug", "Ago", "Set", "Ott", "Nov", "Dic",
        ],
        "weekdays": [
            "Lunedì", "Martedì", "Mercoledì", "Giovedì",
            "Venerdì", "Sabato", "Domenica",
        ],
        "weekdays_short": ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"],
        "weekdays_letter": ["L", "M", "M", "G", "V", "S", "D"],
        "all_day": "Tutto il giorno",
        "week": "Settimana",
        "no_events": "Nessun evento",
        "notes": "Note",
        "year_overview": "Panoramica annuale",
    },
    Language.DE: {
        "months": [
            "Januar", "Februar", "März", "April", "Mai", "Juni",
            "Juli", "August", "September", "Oktober", "November", "Dezember",
        ],
        "months_short": [
            "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
            "Jul", "Aug", "Sep", "Okt", "Nov", "Dez",
        ],
        "weekdays": [
            "Montag", "Dienstag", "Mittwoch", "Donnerstag",
            "Freitag", "Samstag", "Sonntag",
        ],
        "weekdays_short": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
        "weekdays_letter": ["M", "D", "M", "D", "F", "S", "S"],
        "all_day": "Ganztägig",
        "week": "Woche",
        "no_events": "Keine Termine",
        "notes": "Notizen",
        "year_overview": "Jahresübersicht",
    },
    Language.JA: {
        "months": [
            "1月", "2月", "3月", "4月", "5月", "6月",
            "7月", "8月", "9月", "10月", "11月", "12月",
        ],
        "months_short": [
            "1月", "2月", "3月", "4月", "5月", "6月",
            "7月", "8月", "9月", "10月", "11月", "12月",
        ],
        "weekdays": [
            "月曜日", "火曜日", "水曜日", "木曜日",
            "金曜日", "土曜日", "日曜日",
        ],
        "weekdays_short": ["月", "火", "水", "木", "金", "土", "日"],
        "weekdays_letter": ["月", "火", "水", "木", "金", "土", "日"],
        "all_day": "終日",
        "week": "週",
        "no_events": "予定なし",
        "notes": "メモ",
        "year_overview": "年間概要",
    },
}


def get_translation(language: Language) -> dict[str, list[str] | str]:
    """Get the translation dictionary for a language."""
    return TRANSLATIONS[language]


def month_name(language: Language, month: int) -> str:
    """Get the full month name (1-indexed)."""
    return TRANSLATIONS[language]["months"][month - 1]  # type: ignore[index]


def month_name_short(language: Language, month: int) -> str:
    """Get the abbreviated month name (1-indexed)."""
    return TRANSLATIONS[language]["months_short"][month - 1]  # type: ignore[index]


def weekday_name(language: Language, weekday: int) -> str:
    """Get the full weekday name (0=Monday)."""
    return TRANSLATIONS[language]["weekdays"][weekday]  # type: ignore[index]


def weekday_short(language: Language, weekday: int) -> str:
    """Get the abbreviated weekday name (0=Monday)."""
    return TRANSLATIONS[language]["weekdays_short"][weekday]  # type: ignore[index]


def weekday_letter(language: Language, weekday: int) -> str:
    """Get the single-letter weekday name (0=Monday)."""
    return TRANSLATIONS[language]["weekdays_letter"][weekday]  # type: ignore[index]


def label(language: Language, key: str) -> str:
    """Get a translated label string."""
    return TRANSLATIONS[language][key]  # type: ignore[return-value]
