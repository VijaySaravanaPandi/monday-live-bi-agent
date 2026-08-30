"""
Data Quality Report
--------------------
Tracks and summarizes data issues encountered during normalization,
so the agent can communicate caveats to the user instead of silently
producing numbers from incomplete data.
"""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class DataQualityReport:
    board_name: str
    total_items: int = 0
    items_with_missing_fields: int = 0
    missing_field_counts: Dict[str, int] = field(default_factory=dict)
    malformed_dates: int = 0
    malformed_numbers: int = 0
    unrecognized_sector_values: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def record_missing_field(self, field_name: str):
        self.missing_field_counts[field_name] = (
            self.missing_field_counts.get(field_name, 0) + 1
        )

    def record_malformed_date(self):
        self.malformed_dates += 1

    def record_malformed_number(self):
        self.malformed_numbers += 1

    def record_unrecognized_sector(self, raw_value: str):
        if raw_value not in self.unrecognized_sector_values:
            self.unrecognized_sector_values.append(raw_value)

    def add_note(self, note: str):
        self.notes.append(note)

    def has_issues(self) -> bool:
        return (
            self.items_with_missing_fields > 0
            or self.malformed_dates > 0
            or self.malformed_numbers > 0
            or len(self.unrecognized_sector_values) > 0
        )

    def to_dict(self) -> dict:
        return {
            "board_name": self.board_name,
            "total_items": self.total_items,
            "items_with_missing_fields": self.items_with_missing_fields,
            "missing_field_counts": self.missing_field_counts,
            "malformed_dates": self.malformed_dates,
            "malformed_numbers": self.malformed_numbers,
            "unrecognized_sector_values": self.unrecognized_sector_values,
            "notes": self.notes,
        }

    def summary_text(self) -> str:
        """Human-readable caveat summary, suitable for showing to the founder."""
        if not self.has_issues():
            return f"{self.board_name}: data looks clean ({self.total_items} items checked)."

        parts = [f"{self.board_name}: {self.total_items} items checked."]
        if self.items_with_missing_fields:
            parts.append(
                f"{self.items_with_missing_fields} item(s) had missing fields "
                f"({', '.join(f'{k}: {v}' for k, v in self.missing_field_counts.items())})."
            )
        if self.malformed_dates:
            parts.append(f"{self.malformed_dates} date value(s) could not be parsed.")
        if self.malformed_numbers:
            parts.append(f"{self.malformed_numbers} numeric value(s) could not be parsed.")
        if self.unrecognized_sector_values:
            parts.append(
                f"Unrecognized sector labels found: {', '.join(self.unrecognized_sector_values)}."
            )
        return " ".join(parts)