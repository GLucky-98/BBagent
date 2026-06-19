from dataclasses import dataclass


@dataclass
class TodoRuntime:
    dirty: bool = False
    version: int = 0
    last_emitted_version: int = -1
    last_injected_version: int = -1
    stream_count_since_inject: int = 0
    inject_next_stream: bool = False

    def mark_dirty(self) -> None:
        self.version += 1
        self.dirty = True

    def mark_emitted(self) -> None:
        self.last_emitted_version = self.version
        self.dirty = False

    def mark_injected(self) -> None:
        self.last_injected_version = self.version
        self.stream_count_since_inject = 0
        self.inject_next_stream = False

    def request_injection(self) -> None:
        self.inject_next_stream = True

    def clear_injection_request(self) -> None:
        self.inject_next_stream = False

    def tick_stream(self) -> None:
        self.stream_count_since_inject += 1
