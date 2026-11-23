
from dataclasses import asdict, dataclass, field


@dataclass
class FunctionSymbol:
    id: str
    file: str
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    calls: list[str]
    source: str
    imports: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
