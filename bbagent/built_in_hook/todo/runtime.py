from dataclasses import dataclass


@dataclass
class TodoRuntime:
    dirty: bool = False
    version: int = 0
    last_emitted_version: int = -1
    stream_count_since_inject: int = 0

    def mark_dirty(self) -> None:
        self.version += 1
        self.dirty = True

    def mark_emitted(self) -> None:
        self.last_emitted_version = self.version
        self.dirty = False

    def mark_status_shown(self) -> None:
        self.stream_count_since_inject = 0

    def tick_stream(self) -> None:
        self.stream_count_since_inject += 1
