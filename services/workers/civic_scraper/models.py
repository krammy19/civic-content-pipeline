from dataclasses import dataclass, asdict, field
from typing import List, Optional


@dataclass
class Meeting:
    source: str
    jurisdiction: str
    body: str
    date: str
    time: Optional[str]
    location: Optional[str]
    meeting_details_url: Optional[str]
    agenda_url: Optional[str]
    minutes_url: Optional[str]
    video_url: Optional[str]

    def to_dict(self):
        return asdict(self)


@dataclass
class Attachment:
    name: str
    url: str

    def to_dict(self):
        return asdict(self)


@dataclass
class LegislationDetails:
    legislation_url: str
    status: Optional[str]
    text: Optional[str]
    recommendations: Optional[str]
    attachments: List[Attachment] = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        d["attachments"] = [a.to_dict() for a in self.attachments]
        return d


@dataclass
class AgendaItem:
    file_number: Optional[str]
    title: str
    type: Optional[str]
    agenda_note: Optional[str]
    legislation_url: Optional[str]
    action: Optional[str]
    result: Optional[str]
    version: Optional[str]

    @property
    def is_consent(self) -> bool:
        return bool(self.type and "consent" in self.type.lower())

    def to_dict(self):
        d = asdict(self)
        d["is_consent"] = self.is_consent
        return d
