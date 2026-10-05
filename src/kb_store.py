"""Workshop helper：每篇筆記存成 Markdown 檔，目錄存 JSON；關鍵字搜尋，不呼叫 LLM。"""

from pathlib import Path

from pydantic import BaseModel, Field


class Note(BaseModel):
    id: str
    title: str
    category: str
    content: str


class Catalog(BaseModel):
    version: int = 0
    notes: list[Note] = Field(default_factory=list)


class _SavedNote(BaseModel):
    """目錄只記錄中繼資料；內文在同資料夾的 Markdown 檔。"""

    id: str
    title: str
    category: str


class _SavedCatalog(BaseModel):
    version: int = 0
    notes: list[_SavedNote] = Field(default_factory=list)


def _check_filename(note_id: str) -> None:
    if not note_id.endswith(".md") or "/" in note_id or "\\" in note_id:
        raise ValueError("檔名必須是單一 Markdown 檔名，例如 meeting.md")


def _write_atomic(path: Path, text: str) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


class NoteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.catalog = self._load()

    def _load(self) -> Catalog:
        if not self.path.exists():
            return Catalog()
        saved = _SavedCatalog.model_validate_json(self.path.read_text(encoding="utf-8"))
        notes = []
        for meta in saved.notes:
            _check_filename(meta.id)
            content = (self.path.parent / meta.id).read_text(encoding="utf-8")
            notes.append(Note(**meta.model_dump(), content=content))
        return Catalog(version=saved.version, notes=notes)

    @property
    def version(self) -> int:
        return self.catalog.version

    def overview(self) -> dict[str, int | list[dict[str, str]]]:
        return {
            "version": self.version,
            "notes": [
                {"id": n.id, "title": n.title, "category": n.category}
                for n in self.catalog.notes
            ],
        }

    def _save(self, notes: list[Note]) -> None:
        """先寫 Markdown，再寫目錄，最後刪掉已移除的筆記檔。"""
        catalog = Catalog(version=self.version + 1, notes=notes)
        folder = self.path.parent
        folder.mkdir(parents=True, exist_ok=True)
        for note in notes:
            _write_atomic(folder / note.id, note.content)
        saved = _SavedCatalog.model_validate(catalog.model_dump())
        _write_atomic(self.path, saved.model_dump_json(indent=2))
        kept_ids = {note.id for note in notes}
        for old in self.catalog.notes:
            if old.id not in kept_ids:
                (folder / old.id).unlink(missing_ok=True)
        self.catalog = catalog

    def create(self, note_id: str, content: str, category: str = "筆記") -> Note:
        note_id = note_id.strip()
        _check_filename(note_id)
        if not content.strip():
            raise ValueError("筆記不能空白")
        if not category.strip():
            raise ValueError("分類不能空白")
        if any(note.id == note_id for note in self.catalog.notes):
            raise ValueError(f"筆記已存在：{note_id}")
        note = Note(
            id=note_id,
            title=content.splitlines()[0].lstrip("# ").strip() or Path(note_id).stem,
            category=category.strip(),
            content=content,
        )
        self._save([*self.catalog.notes, note])
        return note

    def search(self, query: str) -> list[Note]:
        if not query.strip():
            raise ValueError("搜尋詞不能空白")
        term = query.strip().casefold()
        return [
            n
            for n in self.catalog.notes
            if term in f"{n.title}\n{n.content}".casefold()
        ]

    def get_note(self, note_id: str) -> Note:
        note = next((n for n in self.catalog.notes if n.id == note_id), None)
        if note is None:
            raise ValueError(f"找不到筆記：{note_id}")
        return note

    def update(self, note_id: str, content: str) -> Note:
        if not content.strip():
            raise ValueError("筆記不能空白")
        existing = self.get_note(note_id)
        note = existing.model_copy(
            update={
                "title": content.splitlines()[0].lstrip("# ").strip() or note_id,
                "content": content,
            }
        )
        self._save([note if n.id == note_id else n for n in self.catalog.notes])
        return note

    def delete(self, note_id: str) -> None:
        _check_filename(note_id)
        self.get_note(note_id)
        self._save([note for note in self.catalog.notes if note.id != note_id])
