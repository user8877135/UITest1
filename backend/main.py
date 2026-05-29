from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Float, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DB_PATH = "/data/vocab.db"
engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
DEFAULT_SET_ID = "default"


class Base(DeclarativeBase):
    pass


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    front: Mapped[str] = mapped_column(String(500), nullable=False)
    back: Mapped[str] = mapped_column(String(500), nullable=False)
    example: Mapped[str] = mapped_column(Text, default="")
    example_es: Mapped[str] = mapped_column(Text, default="")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval: Mapped[float] = mapped_column(Float, default=0)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    next_review: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_review: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    set_id: Mapped[str] = mapped_column(String(64), default=DEFAULT_SET_ID, nullable=False, index=True)


class LearningSet(Base):
    __tablename__ = "learning_sets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    cards_per_session: Mapped[int] = mapped_column(Integer, default=20)
    language_direction: Mapped[str] = mapped_column(String(16), default="de-en")
    auto_flip_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_flip_seconds: Mapped[int] = mapped_column(Integer, default=10)
    timer_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    timer_seconds: Mapped[int] = mapped_column(Integer, default=30)
    bidirectional_cards: Mapped[bool] = mapped_column(Boolean, default=True)
    sound_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    tts_spanish_voice: Mapped[str] = mapped_column(String(255), default="")
    tts_spanish_rate: Mapped[float] = mapped_column(Float, default=0.9)
    set_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)


class CardIn(BaseModel):
    id: Optional[str] = None
    front: str = Field(min_length=1, max_length=500)
    back: str = Field(min_length=1, max_length=500)
    example: str = ""
    exampleEs: str = ""
    tags: list[str] = Field(default_factory=list)
    ease: float = 2.5
    interval: float = 0
    repetitions: int = 0
    nextReview: Optional[str] = None
    lastReview: Optional[str] = None
    createdAt: Optional[str] = None
    setId: Optional[str] = None


class SettingsIn(BaseModel):
    cardsPerSession: int = 20
    languageDirection: str = "de-en"
    autoFlipEnabled: bool = False
    autoFlipSeconds: int = 10
    timerEnabled: bool = False
    timerSeconds: int = 30
    bidirectionalCards: bool = True
    soundEnabled: bool = False
    ttsSpanishVoice: str = ""
    ttsSpanishRate: float = 0.9
    setId: Optional[str] = None


class SetIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class BulkCardsIn(BaseModel):
    cards: list[CardIn] = Field(default_factory=list)
    setId: Optional[str] = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def card_to_dict(card: Card) -> dict:
    return {
        "id": card.id,
        "front": card.front,
        "back": card.back,
        "example": card.example,
        "exampleEs": card.example_es,
        "tags": json.loads(card.tags_json or "[]"),
        "ease": card.ease,
        "interval": card.interval,
        "repetitions": card.repetitions,
        "nextReview": card.next_review,
        "lastReview": card.last_review,
        "createdAt": card.created_at,
        "setId": card.set_id,
    }


def setting_to_dict(setting: Setting) -> dict:
    return {
        "cardsPerSession": setting.cards_per_session,
        "languageDirection": setting.language_direction,
        "autoFlipEnabled": setting.auto_flip_enabled,
        "autoFlipSeconds": setting.auto_flip_seconds,
        "timerEnabled": setting.timer_enabled,
        "timerSeconds": setting.timer_seconds,
        "bidirectionalCards": setting.bidirectional_cards,
        "soundEnabled": setting.sound_enabled,
        "ttsSpanishVoice": setting.tts_spanish_voice,
        "ttsSpanishRate": setting.tts_spanish_rate,
    }


def set_to_dict(item: LearningSet, card_count: int = 0) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "createdAt": item.created_at,
        "cardCount": card_count,
    }


SPANISH_EXAMPLE_BY_BACK = {
    "ser": "Yo soy estudiante.",
    "estar": "Estoy cansado hoy.",
    "tener": "Tengo un libro.",
    "hacer": "Hago la tarea.",
    "poder": "Puedo ayudar ahora.",
    "querer": "Quiero agua, por favor.",
    "decir": "Digo la verdad.",
    "ir": "Voy a casa.",
    "venir": "Vengo de Madrid.",
    "hablar": "Hablo con Ana.",
    "comer": "Como pan cada dia.",
    "beber": "Bebo agua fria.",
    "vivir": "Vivo en Berlin.",
    "ver": "Veo la tele.",
    "dar": "Doy un regalo.",
    "saber": "No se la respuesta.",
    "conocer": "Conozco a tu hermano.",
    "pensar": "Pienso en ti.",
    "necesitar": "Necesito tiempo.",
    "trabajar": "Trabajo en un hotel.",
    "lunes": "El lunes trabajo en casa.",
    "martes": "El martes tengo clase.",
    "miercoles": "El miercoles estudio espanol.",
    "jueves": "El jueves voy al gimnasio.",
    "viernes": "El viernes salgo con amigos.",
    "sabado": "El sabado descanso.",
    "domingo": "El domingo cocino con mi familia.",
    "enero": "En enero hace frio.",
    "febrero": "En febrero leo mas.",
    "marzo": "En marzo empieza la primavera.",
    "abril": "En abril llueve mucho.",
    "mayo": "En mayo viajo a Madrid.",
    "junio": "En junio termina el curso.",
    "julio": "En julio hace calor.",
    "agosto": "En agosto estoy de vacaciones.",
    "septiembre": "En septiembre vuelvo al trabajo.",
    "octubre": "En octubre llevo chaqueta.",
    "noviembre": "En noviembre estudio cada dia.",
    "diciembre": "En diciembre celebro la Navidad.",
}


def infer_spanish_example(front: str, back: str) -> str:
    for candidate in (back, front):
        key = str(candidate or "").strip().lower()
        if key in SPANISH_EXAMPLE_BY_BACK:
            return SPANISH_EXAMPLE_BY_BACK[key]
    return ""


def slugify_set_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "set"


def generate_set_id(session: Session, set_name: str) -> str:
    base = slugify_set_name(set_name)
    candidate = base
    idx = 2
    while session.get(LearningSet, candidate) is not None:
        candidate = f"{base}-{idx}"
        idx += 1
    return candidate


def ensure_default_set(session: Session) -> None:
    default_set = session.get(LearningSet, DEFAULT_SET_ID)
    if default_set is None:
        session.add(LearningSet(id=DEFAULT_SET_ID, name="Default", created_at=now_iso()))


def get_or_create_setting_for_set(session: Session, set_id: str) -> Setting:
    setting = session.scalars(select(Setting).where(Setting.set_id == set_id)).first()
    if setting is not None:
        return setting

    legacy = session.get(Setting, 1)
    if legacy is not None and legacy.set_id is None:
        legacy.set_id = set_id
        return legacy

    setting = Setting(set_id=set_id)
    session.add(setting)
    return setting


def ensure_cards_schema() -> None:
    with engine.begin() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(cards)")}
        if "example_es" not in columns:
            conn.exec_driver_sql("ALTER TABLE cards ADD COLUMN example_es TEXT DEFAULT ''")
        if "set_id" not in columns:
            conn.exec_driver_sql(f"ALTER TABLE cards ADD COLUMN set_id VARCHAR(64) DEFAULT '{DEFAULT_SET_ID}'")
        conn.exec_driver_sql(f"UPDATE cards SET set_id = '{DEFAULT_SET_ID}' WHERE set_id IS NULL OR set_id = ''")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_cards_set_id ON cards(set_id)")


def ensure_settings_schema() -> None:
    with engine.begin() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(settings)")}
        if "tts_spanish_voice" not in columns:
            conn.exec_driver_sql("ALTER TABLE settings ADD COLUMN tts_spanish_voice VARCHAR(255) DEFAULT ''")
        if "tts_spanish_rate" not in columns:
            conn.exec_driver_sql("ALTER TABLE settings ADD COLUMN tts_spanish_rate FLOAT DEFAULT 0.9")
        if "set_id" not in columns:
            conn.exec_driver_sql("ALTER TABLE settings ADD COLUMN set_id VARCHAR(64)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_settings_set_id ON settings(set_id)")


DEFAULT_VOCAB = [
    {"front": "sein (dauerhaft)", "back": "ser", "example": "Ich bin Student.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "sein (Zustand)", "back": "estar", "example": "Ich bin heute muede.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "haben", "back": "tener", "example": "Ich habe ein Buch.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "machen, tun", "back": "hacer", "example": "Ich mache die Hausaufgaben.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "koennen", "back": "poder", "example": "Ich kann jetzt helfen.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "wollen", "back": "querer", "example": "Ich will bitte Wasser.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "sagen", "back": "decir", "example": "Ich sage die Wahrheit.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "gehen, fahren", "back": "ir", "example": "Ich gehe nach Hause.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "kommen", "back": "venir", "example": "Ich komme aus Madrid.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "sprechen", "back": "hablar", "example": "Ich spreche mit Ana.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "essen", "back": "comer", "example": "Ich esse jeden Tag Brot.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "trinken", "back": "beber", "example": "Ich trinke kaltes Wasser.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "leben, wohnen", "back": "vivir", "example": "Ich wohne in Berlin.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "sehen", "back": "ver", "example": "Ich sehe fern.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "geben", "back": "dar", "example": "Ich gebe ein Geschenk.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "wissen", "back": "saber", "example": "Ich weiss die Antwort nicht.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "kennen", "back": "conocer", "example": "Ich kenne deinen Bruder.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "denken", "back": "pensar", "example": "Ich denke an dich.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "brauchen", "back": "necesitar", "example": "Ich brauche Zeit.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "arbeiten", "back": "trabajar", "example": "Ich arbeite in einem Hotel.", "tags": ["Spanisch", "Verb", "A1"]},
    {"front": "Montag", "back": "lunes", "example": "Am Montag arbeite ich zu Hause.", "tags": ["Spanisch", "Wochentag", "A1"]},
    {"front": "Dienstag", "back": "martes", "example": "Am Dienstag habe ich Unterricht.", "tags": ["Spanisch", "Wochentag", "A1"]},
    {"front": "Mittwoch", "back": "miercoles", "example": "Am Mittwoch lerne ich Spanisch.", "tags": ["Spanisch", "Wochentag", "A1"]},
    {"front": "Donnerstag", "back": "jueves", "example": "Am Donnerstag gehe ich ins Fitnessstudio.", "tags": ["Spanisch", "Wochentag", "A1"]},
    {"front": "Freitag", "back": "viernes", "example": "Am Freitag treffe ich Freunde.", "tags": ["Spanisch", "Wochentag", "A1"]},
    {"front": "Samstag", "back": "sabado", "example": "Am Samstag ruhe ich mich aus.", "tags": ["Spanisch", "Wochentag", "A1"]},
    {"front": "Sonntag", "back": "domingo", "example": "Am Sonntag koche ich mit meiner Familie.", "tags": ["Spanisch", "Wochentag", "A1"]},
    {"front": "Januar", "back": "enero", "example": "Im Januar ist es kalt.", "tags": ["Spanisch", "Monat", "A1"]},
    {"front": "Februar", "back": "febrero", "example": "Im Februar lese ich mehr.", "tags": ["Spanisch", "Monat", "A1"]},
    {"front": "Maerz", "back": "marzo", "example": "Im Maerz beginnt der Fruehling.", "tags": ["Spanisch", "Monat", "A1"]},
    {"front": "April", "back": "abril", "example": "Im April regnet es viel.", "tags": ["Spanisch", "Monat", "A1"]},
    {"front": "Mai", "back": "mayo", "example": "Im Mai reise ich nach Madrid.", "tags": ["Spanisch", "Monat", "A1"]},
    {"front": "Juni", "back": "junio", "example": "Im Juni endet der Kurs.", "tags": ["Spanisch", "Monat", "A1"]},
    {"front": "Juli", "back": "julio", "example": "Im Juli ist es warm.", "tags": ["Spanisch", "Monat", "A1"]},
    {"front": "August", "back": "agosto", "example": "Im August habe ich Urlaub.", "tags": ["Spanisch", "Monat", "A1"]},
    {"front": "September", "back": "septiembre", "example": "Im September beginne ich wieder mit der Arbeit.", "tags": ["Spanisch", "Monat", "A1"]},
    {"front": "Oktober", "back": "octubre", "example": "Im Oktober trage ich eine Jacke.", "tags": ["Spanisch", "Monat", "A1"]},
    {"front": "November", "back": "noviembre", "example": "Im November lerne ich jeden Tag.", "tags": ["Spanisch", "Monat", "A1"]},
    {"front": "Dezember", "back": "diciembre", "example": "Im Dezember feiere ich Weihnachten.", "tags": ["Spanisch", "Monat", "A1"]},
]


app = FastAPI(title="Vocab API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(engine)
    ensure_cards_schema()
    ensure_settings_schema()
    with Session(engine) as session:
        ensure_default_set(session)
        get_or_create_setting_for_set(session, DEFAULT_SET_ID)

        count = session.scalar(select(func.count()).select_from(Card).where(Card.set_id == DEFAULT_SET_ID))
        if count == 0:
            for idx, item in enumerate(DEFAULT_VOCAB, start=1):
                session.add(
                    Card(
                        id=f"seed-{idx}",
                        front=item["front"],
                        back=item["back"],
                        example=item["example"],
                        example_es=item.get("exampleEs") or infer_spanish_example(item["front"], item["back"]),
                        tags_json=json.dumps(item["tags"]),
                        created_at=now_iso(),
                        set_id=DEFAULT_SET_ID,
                    )
                )
        else:
            cards = session.scalars(select(Card)).all()
            for card in cards:
                if card.example_es:
                    continue
                tags = json.loads(card.tags_json or "[]")
                if "Spanisch" not in tags:
                    continue
                inferred = infer_spanish_example(card.front, card.back)
                if inferred:
                    card.example_es = inferred
        session.commit()


@app.get("/api/sets")
def list_sets() -> list[dict]:
    with Session(engine) as session:
        ensure_default_set(session)
        session.commit()

        sets = session.scalars(select(LearningSet).order_by(LearningSet.name.asc())).all()
        count_rows = session.execute(select(Card.set_id, func.count()).group_by(Card.set_id)).all()
        counts = {set_id: count for set_id, count in count_rows}

        sets.sort(key=lambda item: (item.id != DEFAULT_SET_ID, item.name.lower()))
        return [set_to_dict(item, counts.get(item.id, 0)) for item in sets]


@app.post("/api/sets")
def create_set(data: SetIn) -> dict:
    with Session(engine) as session:
        ensure_default_set(session)
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Set name is required")

        name_exists = session.scalar(
            select(func.count()).select_from(LearningSet).where(func.lower(LearningSet.name) == name.lower())
        )
        if name_exists:
            raise HTTPException(status_code=409, detail="Set name already exists")

        set_id = generate_set_id(session, name)
        item = LearningSet(id=set_id, name=name, created_at=now_iso())
        session.add(item)
        get_or_create_setting_for_set(session, set_id)
        session.commit()
        return set_to_dict(item, 0)


@app.delete("/api/sets/{set_id}")
def delete_set(set_id: str) -> dict:
    with Session(engine) as session:
        item = session.get(LearningSet, set_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Set not found")
        if set_id == DEFAULT_SET_ID:
            raise HTTPException(status_code=400, detail="Default set cannot be deleted")

        set_count = session.scalar(select(func.count()).select_from(LearningSet)) or 0
        if set_count <= 1:
            raise HTTPException(status_code=400, detail="At least one set must remain")

        session.query(Card).filter(Card.set_id == set_id).delete()
        session.query(Setting).filter(Setting.set_id == set_id).delete()
        session.delete(item)
        session.commit()
        return {"deleted": True}


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/cards")
def list_cards(set_id: str = DEFAULT_SET_ID) -> list[dict]:
    with Session(engine) as session:
        cards = session.scalars(select(Card).where(Card.set_id == set_id).order_by(Card.created_at.asc())).all()
        return [card_to_dict(c) for c in cards]


@app.post("/api/cards")
def create_card(card_in: CardIn) -> dict:
    card_id = card_in.id or f"card-{int(datetime.now().timestamp() * 1000)}"
    with Session(engine) as session:
        set_id = (card_in.setId or DEFAULT_SET_ID).strip() or DEFAULT_SET_ID
        if session.get(LearningSet, set_id) is None:
            raise HTTPException(status_code=400, detail="Invalid set_id")

        existing = session.get(Card, card_id)
        if existing is not None:
            raise HTTPException(status_code=409, detail="Card ID already exists")

        card = Card(
            id=card_id,
            front=card_in.front.strip(),
            back=card_in.back.strip(),
            example=card_in.example.strip(),
            example_es=card_in.exampleEs.strip() or infer_spanish_example(card_in.front, card_in.back),
            tags_json=json.dumps(card_in.tags),
            ease=card_in.ease,
            interval=card_in.interval,
            repetitions=card_in.repetitions,
            next_review=card_in.nextReview,
            last_review=card_in.lastReview,
            created_at=card_in.createdAt or now_iso(),
            set_id=set_id,
        )
        session.add(card)
        session.commit()
        return card_to_dict(card)


@app.put("/api/cards/{card_id}")
def update_card(card_id: str, card_in: CardIn) -> dict:
    with Session(engine) as session:
        card = session.get(Card, card_id)
        if card is None:
            raise HTTPException(status_code=404, detail="Card not found")

        set_id = (card_in.setId or card.set_id or DEFAULT_SET_ID).strip() or DEFAULT_SET_ID
        if session.get(LearningSet, set_id) is None:
            raise HTTPException(status_code=400, detail="Invalid set_id")

        card.front = card_in.front.strip()
        card.back = card_in.back.strip()
        card.example = card_in.example.strip()
        card.example_es = card_in.exampleEs.strip() or infer_spanish_example(card_in.front, card_in.back)
        card.tags_json = json.dumps(card_in.tags)
        card.ease = card_in.ease
        card.interval = card_in.interval
        card.repetitions = card_in.repetitions
        card.next_review = card_in.nextReview
        card.last_review = card_in.lastReview
        card.set_id = set_id
        session.commit()
        return card_to_dict(card)


@app.delete("/api/cards/{card_id}")
def delete_card(card_id: str) -> dict:
    with Session(engine) as session:
        card = session.get(Card, card_id)
        if card is None:
            raise HTTPException(status_code=404, detail="Card not found")
        session.delete(card)
        session.commit()
        return {"deleted": True}


@app.put("/api/cards-bulk")
def replace_cards(data: BulkCardsIn) -> dict:
    with Session(engine) as session:
        set_id = (data.setId or DEFAULT_SET_ID).strip() or DEFAULT_SET_ID
        if session.get(LearningSet, set_id) is None:
            raise HTTPException(status_code=400, detail="Invalid set_id")

        session.query(Card).filter(Card.set_id == set_id).delete()
        for card_in in data.cards:
            card_id = card_in.id or f"card-{int(datetime.now().timestamp() * 1000)}"
            session.add(
                Card(
                    id=card_id,
                    front=card_in.front.strip(),
                    back=card_in.back.strip(),
                    example=card_in.example.strip(),
                    example_es=card_in.exampleEs.strip() or infer_spanish_example(card_in.front, card_in.back),
                    tags_json=json.dumps(card_in.tags),
                    ease=card_in.ease,
                    interval=card_in.interval,
                    repetitions=card_in.repetitions,
                    next_review=card_in.nextReview,
                    last_review=card_in.lastReview,
                    created_at=card_in.createdAt or now_iso(),
                    set_id=set_id,
                )
            )
        session.commit()
        return {"ok": True, "count": len(data.cards)}


@app.get("/api/settings")
def get_settings(set_id: str = DEFAULT_SET_ID) -> dict:
    with Session(engine) as session:
        if session.get(LearningSet, set_id) is None:
            raise HTTPException(status_code=404, detail="Set not found")
        setting = get_or_create_setting_for_set(session, set_id)
        session.commit()
        return setting_to_dict(setting)


@app.put("/api/settings")
def update_settings(data: SettingsIn) -> dict:
    with Session(engine) as session:
        set_id = (data.setId or DEFAULT_SET_ID).strip() or DEFAULT_SET_ID
        if session.get(LearningSet, set_id) is None:
            raise HTTPException(status_code=404, detail="Set not found")
        setting = get_or_create_setting_for_set(session, set_id)

        setting.cards_per_session = data.cardsPerSession
        setting.language_direction = data.languageDirection
        setting.auto_flip_enabled = data.autoFlipEnabled
        setting.auto_flip_seconds = data.autoFlipSeconds
        setting.timer_enabled = data.timerEnabled
        setting.timer_seconds = data.timerSeconds
        setting.bidirectional_cards = data.bidirectionalCards
        setting.sound_enabled = data.soundEnabled
        setting.tts_spanish_voice = data.ttsSpanishVoice
        setting.tts_spanish_rate = max(0.6, min(1.4, data.ttsSpanishRate))
        setting.set_id = set_id

        session.commit()
        return {"ok": True}
