import io
import math
import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from PIL import Image, ImageDraw
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.status import QUEUE_STATUSES
from app.models import (
    Occurrence,
    OccurrenceConfirmation,
    OccurrencePhoto,
    OccurrenceStatus,
    OccurrenceStatusHistory,
    OccurrenceType,
    PhotoKind,
    RiskSetting,
    User,
    UserRole,
)
from app.security import hash_password, new_tracking_token
from app.seed_data import OCCURRENCE_TYPES, OTHER_TYPE_CODE, PREVENTION_TIPS, RISK_SETTINGS
from app.services.alerts import check_area_alert
from app.services.occurrences import make_point, make_protocol
from app.services.photos import ProcessedPhoto, store_photo
from app.services.risk import detect_chronic

DEV_USERS = [
    ("Moradora de Teste", "morador@sentinela.test", UserRole.RESIDENT),
    ("Agente de Teste", "agente@sentinela.test", UserRole.AGENT),
    ("Gestora de Teste", "gestor@sentinela.test", UserRole.MANAGER),
    # Neighbours who confirm some fake reports ("eu também vi").
    ("Vizinho de Teste", "vizinho1@sentinela.test", UserRole.RESIDENT),
    ("Vizinha de Teste", "vizinha2@sentinela.test", UserRole.RESIDENT),
]

# Status path used to build a coherent history for fake occurrences.
STATUS_PATHS: dict[OccurrenceStatus, list[OccurrenceStatus]] = {
    OccurrenceStatus.OPEN: [OccurrenceStatus.OPEN],
    OccurrenceStatus.IN_PROGRESS: [OccurrenceStatus.OPEN, OccurrenceStatus.IN_PROGRESS],
    OccurrenceStatus.RESOLVED_BY_AGENT: [
        OccurrenceStatus.OPEN,
        OccurrenceStatus.IN_PROGRESS,
        OccurrenceStatus.RESOLVED_BY_AGENT,
    ],
    OccurrenceStatus.CONFIRMED: [
        OccurrenceStatus.OPEN,
        OccurrenceStatus.IN_PROGRESS,
        OccurrenceStatus.RESOLVED_BY_AGENT,
        OccurrenceStatus.CONFIRMED,
    ],
    OccurrenceStatus.CONTESTED: [
        OccurrenceStatus.OPEN,
        OccurrenceStatus.IN_PROGRESS,
        OccurrenceStatus.RESOLVED_BY_AGENT,
        OccurrenceStatus.CONTESTED,
    ],
}
RESOLVED = {OccurrenceStatus.RESOLVED_BY_AGENT, OccurrenceStatus.CONFIRMED}


def seed_reference_data(db: Session) -> tuple[int, int]:
    """Insert missing types and settings. Existing rows keep their (possibly tuned) values."""
    existing_types = set(db.scalars(select(OccurrenceType.code)))
    new_types = 0
    for order, (code, name, description, weight, department, breeding) in enumerate(
        OCCURRENCE_TYPES
    ):
        if code in existing_types:
            continue
        db.add(
            OccurrenceType(
                code=code,
                name=name,
                description=description,
                weight=Decimal(weight),
                department=department,
                is_breeding_site=breeding,
                # "Outro" stays after any type the managers create later.
                sort_order=1000 if code == OTHER_TYPE_CODE else order,
                is_other=code == OTHER_TYPE_CODE,
            )
        )
        new_types += 1

    # Prevention advice: only fills empty texts, never overwrites the municipality's edits.
    db.flush()
    for otype in db.scalars(select(OccurrenceType).where(OccurrenceType.prevention_tips == "")):
        otype.prevention_tips = PREVENTION_TIPS.get(otype.code, "")

    existing_settings = set(db.scalars(select(RiskSetting.key)))
    new_settings = 0
    for key, value, description in RISK_SETTINGS:
        if key not in existing_settings:
            db.add(RiskSetting(key=key, value=Decimal(value), description=description))
            new_settings += 1
    db.commit()
    return new_types, new_settings


def create_user(db: Session, name: str, email: str, role: UserRole, password: str, terms: str):
    user = User(
        name=name,
        email=email.lower(),
        password_hash=hash_password(password),
        role=role,
        terms_version=terms,
        terms_accepted_at=datetime.now(UTC),
    )
    db.add(user)
    db.commit()
    return user


def seed_dev_users(db: Session, settings: Settings) -> int:
    created = 0
    for name, email, role in DEV_USERS:
        if db.scalar(select(User.id).where(User.email == email)) is None:
            create_user(db, name, email, role, settings.seed_password, settings.terms_version)
            created += 1
    return created


def _offset(lat: float, lon: float, north_m: float, east_m: float) -> tuple[float, float]:
    dlat = north_m / 111_320.0
    dlon = east_m / (111_320.0 * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


def _placeholder_photo(label: str, color: tuple[int, int, int]) -> ProcessedPhoto:
    img = Image.new("RGB", (800, 600), color)
    draw = ImageDraw.Draw(img)
    draw.rectangle((40, 230, 760, 370), fill=(255, 255, 255))
    draw.text((60, 260), "FOTO FICTICIA - SEED", fill=(0, 0, 0))
    draw.text((60, 300), label, fill=(0, 0, 0))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=70)
    return ProcessedPhoto(data=out.getvalue(), width=800, height=600)


def seed_fake_occurrences(
    db: Session, settings: Settings, center: tuple[float, float], count: int
) -> int:
    """Fictitious occurrences around `center`. Skipped when occurrences already exist.

    Includes a few spots with several resolved occurrences within a few metres of each
    other plus a new open one, so phase 2 has chronic points to detect.
    """
    if db.scalar(select(func.count(Occurrence.id))):
        return 0
    rng = random.Random(42)
    types = list(
        db.scalars(
            select(OccurrenceType)
            .where(OccurrenceType.is_other.is_(False))
            .order_by(OccurrenceType.sort_order)
        )
    )
    other = db.scalar(select(OccurrenceType).where(OccurrenceType.is_other))
    resident = db.scalar(select(User).where(User.email == DEV_USERS[0][1]))
    agent = db.scalar(select(User).where(User.email == DEV_USERS[1][1]))
    neighbours = list(db.scalars(select(User).where(User.email.in_([u[1] for u in DEV_USERS[3:]]))))
    now = datetime.now(UTC)
    colors = [
        (70, 130, 180),
        (139, 115, 85),
        (95, 158, 160),
        (107, 142, 35),
        (112, 128, 144),
        (160, 82, 45),
        (128, 128, 0),
        (178, 34, 34),
    ]

    def add(lat, lon, otype, status, created_at, from_resident):
        token, token_hash = new_tracking_token()
        occ = Occurrence(
            type=otype,
            location=make_point(lat, lon),
            description=f"Registro fictício gerado pelo seed ({otype.name.lower()}).",
            status=status,
            author_id=resident.id if (from_resident and resident) else None,
            is_anonymous=not from_resident and rng.random() < 0.5,
            reporter_name=None,
            tracking_token_hash=token_hash,
            notified_at=created_at + timedelta(minutes=1),
            created_at=created_at,
            updated_at=created_at,
        )
        db.add(occ)
        db.flush()
        occ.protocol = make_protocol(occ.id, created_at)
        color = colors[otype.sort_order % len(colors)]
        occ.photos.append(_photo_row(settings, PhotoKind.REPORT, otype.code, color))

        path = STATUS_PATHS[status]
        when = created_at
        previous = None
        for step in path:
            if previous is not None:
                when = min(when + timedelta(hours=rng.randint(6, 72)), now)
                if occ.first_response_at is None:
                    occ.first_response_at = when
            occ.history.append(
                OccurrenceStatusHistory(
                    from_status=previous,
                    to_status=step,
                    changed_by_id=None if previous is None else (agent.id if agent else None),
                    note="Registro fictício.",
                    created_at=when,
                )
            )
            if step == OccurrenceStatus.RESOLVED_BY_AGENT:
                occ.photos.append(
                    _photo_row(settings, PhotoKind.RESOLUTION, "resolvido", (34, 139, 34))
                )
            previous = step
        occ.updated_at = when
        # Some active reports were confirmed by neighbours, which lifts the risk cap.
        if status in QUEUE_STATUSES and neighbours and rng.random() < 0.35:
            for neighbour in rng.sample(neighbours, rng.randint(1, len(neighbours))):
                occ.confirmations.append(OccurrenceConfirmation(user_id=neighbour.id))
        return occ

    created = 0
    # Chronic spots: 3 resolved occurrences within ~15 m, then a new open one.
    chronic_spots = min(4, count // 10)
    for _ in range(chronic_spots):
        base = _offset(*center, rng.uniform(-1800, 1800), rng.uniform(-1800, 1800))
        otype = rng.choice(types[:4])
        for i in range(3):
            lat, lon = _offset(*base, rng.uniform(-12, 12), rng.uniform(-12, 12))
            created_at = now - timedelta(days=150 - i * 40 + rng.randint(0, 5))
            add(lat, lon, otype, OccurrenceStatus.CONFIRMED, created_at, rng.random() < 0.5)
            created += 1
        lat, lon = _offset(*base, rng.uniform(-10, 10), rng.uniform(-10, 10))
        add(lat, lon, otype, OccurrenceStatus.OPEN, now - timedelta(days=rng.randint(1, 10)), True)
        created += 1

    statuses = (
        [OccurrenceStatus.OPEN] * 12
        + [OccurrenceStatus.IN_PROGRESS] * 3
        + [OccurrenceStatus.RESOLVED_BY_AGENT] * 2
        + [OccurrenceStatus.CONFIRMED] * 2
        + [OccurrenceStatus.CONTESTED] * 1
    )
    while created < count:
        # Denser near the centre, sparser up to ~2.5 km.
        dist = 2500 * math.sqrt(rng.random())
        angle = rng.uniform(0, 2 * math.pi)
        lat, lon = _offset(*center, dist * math.cos(angle), dist * math.sin(angle))
        otype = rng.choices(types, weights=[6, 5, 3, 3, 2, 1, 1, 1][: len(types)])[0]
        status = rng.choice(statuses)
        created_at = now - timedelta(days=rng.randint(1, 60), hours=rng.randint(0, 23))
        add(lat, lon, otype, status, created_at, rng.random() < 0.4)
        created += 1

    # "Outro" reports described by residents, two of them alike, so the managers have a
    # suggestion to turn into an official type in the settings screen.
    if other is not None:
        for label in (
            "Caixa de isopor com água",
            "caixa de isopor com água",
            "Bebedouro de animais sujo",
        ):
            dist = 2000 * math.sqrt(rng.random())
            angle = rng.uniform(0, 2 * math.pi)
            lat, lon = _offset(*center, dist * math.cos(angle), dist * math.sin(angle))
            created_at = now - timedelta(days=rng.randint(1, 20), hours=rng.randint(0, 23))
            occ = add(lat, lon, other, OccurrenceStatus.OPEN, created_at, True)
            occ.custom_type_label = label
            created += 1

    # Demo scenario: three recent reports of standing water piling up in one block, so the
    # accumulation alert, the urgent messages and the queue have something to show.
    cluster = _offset(*center, 700, 650)
    water = types[0]
    for i, (north, east) in enumerate([(0, 0), (35, -25), (-30, 40)]):
        lat, lon = _offset(*cluster, north, east)
        add(lat, lon, water, OccurrenceStatus.OPEN, now - timedelta(days=2 - i, hours=5), True)
        created += 1

    # Fake reports that sit on an already-resolved spot are chronic, as real ones would be.
    db.flush()
    for occurrence in db.scalars(
        select(Occurrence).where(Occurrence.status.in_(QUEUE_STATUSES))
    ).unique():
        occurrence.is_chronic = detect_chronic(db, occurrence)
    # Everything older than a day already went out in earlier digests.
    yesterday = now - timedelta(days=1)
    for occurrence in db.scalars(select(Occurrence)).unique():
        if occurrence.created_at < yesterday:
            occurrence.messaged_at = occurrence.created_at
    db.flush()
    last = db.scalars(select(Occurrence).order_by(Occurrence.id.desc())).first()
    check_area_alert(db, last)
    db.commit()
    return created


def _photo_row(settings: Settings, kind: PhotoKind, label: str, color) -> OccurrencePhoto:
    photo = _placeholder_photo(label, color)
    return OccurrencePhoto(
        kind=kind,
        storage_key=store_photo(settings.upload_dir, photo),
        content_type=photo.content_type,
        width=photo.width,
        height=photo.height,
        size_bytes=len(photo.data),
    )


def seed_fake_sectors(db: Session, center: tuple[float, float]) -> tuple[int, int]:
    """Fictitious sectors around `center` and one fictitious LIRAa cycle, for demos only.

    Skipped when sectors already exist. Returns (sectors, LIRAa rows).
    """
    from app.models import Sector
    from app.services.liraa import LiraaRow, save_liraa
    from app.services.sectors import FICTITIOUS_SOURCE, fictitious_grid, import_sectors

    if db.scalar(select(func.count(Sector.id))):
        return 0, 0
    lat, lon = center
    bbox = (lon - 0.047, lat - 0.045, lon + 0.047, lat + 0.045)  # ~10 km × 10 km
    grid = fictitious_grid(bbox)
    import_sectors(db, grid, FICTITIOUS_SOURCE)

    rng = random.Random(11)
    survey_date = (datetime.now(UTC) - timedelta(days=10)).date()
    rows = [
        LiraaRow(
            line=i,
            sector_code=sector.code,
            period=f"{survey_date:%Y}-fictício",
            survey_date=survey_date,
            iip=Decimal(str(round(rng.uniform(0.2, 6.0), 1))),
            ib=Decimal(str(round(rng.uniform(0.3, 8.0), 1))),
        )
        for i, sector in enumerate(grid, start=2)
    ]
    save_liraa(db, rows)
    db.commit()
    return len(grid), len(rows)
