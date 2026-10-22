"""Administrative commands.

python -m app.cli seed [--dev] [--fake N]
python -m app.cli create-user --name ... --email ... --role agente
python -m app.cli retry-notifications
python -m app.cli reset-demo --yes     # back to a clean demonstration (refused in production)
python -m app.cli send-digest          # daily summary to the messaging group (schedulable)
python -m app.cli import-sensitive-points [--dry-run]
python -m app.cli import-sectors setores.geojson [--replace]
python -m app.cli import-liraa liraa.csv
"""

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from sqlalchemy import select, text

from app.config import get_settings
from app.db import SessionLocal
from app.models import User, UserRole
from app.seeding import (
    create_user,
    seed_dev_users,
    seed_fake_occurrences,
    seed_fake_sectors,
    seed_reference_data,
)
from app.services import messaging
from app.services.liraa import LiraaCsvError, parse_liraa_csv, save_liraa
from app.services.notifications import deliver, retry_pending
from app.services.sectors import SectorImportError, import_sectors, parse_sectors_geojson
from app.services.sensitive_points import build_query, fetch_overpass, parse_overpass, sync_points


def cmd_seed(args: argparse.Namespace) -> int:
    settings = get_settings()
    with SessionLocal() as db:
        types, coeffs = seed_reference_data(db)
        print(f"Tipos inseridos: {types}; coeficientes inseridos: {coeffs}")
        if args.dev:
            users = seed_dev_users(db, settings)
            print(f"Usuários de teste criados: {users} (senha em SEED_PASSWORD)")
        if args.fake:
            lat, lon = (float(v) for v in settings.seed_center.split(","))
            created = seed_fake_occurrences(db, settings, (lat, lon), args.fake)
            if created:
                print(f"Ocorrências fictícias criadas: {created}")
            else:
                print("Já existem ocorrências; nenhuma ocorrência fictícia foi criada.")
            sectors, liraa = seed_fake_sectors(db, (lat, lon))
            if sectors:
                print(f"Setores fictícios: {sectors}; resultados LIRAa fictícios: {liraa}")
    return 0


def cmd_reset_demo(args: argparse.Namespace) -> int:
    """Back to a clean demonstration: wipes reports, users, sectors and settings, keeps the
    sensitive points imported from OpenStreetMap, and recreates the demo data."""
    settings = get_settings()
    if settings.app_env == "production":
        print("Recusado: APP_ENV=production. Este comando apaga todos os dados.", file=sys.stderr)
        return 1
    if not args.yes:
        print(
            "Isto apaga ocorrências, usuários, setores e configurações. Use --yes para confirmar."
        )
        return 1
    with SessionLocal() as db:
        db.execute(
            text(
                "TRUNCATE occurrences, area_alerts, notifications, occurrence_confirmations, "
                "occurrence_photos, occurrence_status_history, password_tokens, liraa_surveys, "
                "sectors, agent_sectors, agent_types, users, occurrence_types, risk_settings "
                "RESTART IDENTITY CASCADE"
            )
        )
        db.commit()
    removed = 0
    if settings.upload_dir.exists():
        for path in settings.upload_dir.rglob("*"):
            if path.is_file():
                path.unlink()
                removed += 1
    print(f"Dados apagados ({removed} foto(s) removida(s)). Recriando a demonstração...")
    return cmd_seed(argparse.Namespace(dev=True, fake=args.fake))


def cmd_create_user(args: argparse.Namespace) -> int:
    settings = get_settings()
    password = os.environ.get("NEW_USER_PASSWORD") or getpass.getpass("Senha: ")
    if len(password) < 8:
        print("A senha precisa ter pelo menos 8 caracteres.", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == args.email.lower())):
            print("Já existe um usuário com este e-mail.", file=sys.stderr)
            return 1
        user = create_user(
            db, args.name, args.email, UserRole(args.role), password, settings.terms_version
        )
        print(f"Usuário {user.email} criado com perfil {user.role.value}.")
    return 0


def cmd_retry_notifications(_: argparse.Namespace) -> int:
    with SessionLocal() as db:
        sent, failed = retry_pending(db)
    print(f"Notificações enviadas: {sent}; com falha: {failed}")
    return 0 if failed == 0 else 2


def cmd_send_digest(_: argparse.Namespace) -> int:
    """Daily summary to the messaging group: every active report not yet sent there.

    Schedule it once a day (e.g. 7h). Critical reports already went out immediately.
    """
    settings = get_settings()
    if not messaging.enabled(settings):
        print("Canal de mensagens desativado (MESSAGING_PROVIDER=none); nada a enviar.")
        return 0
    with SessionLocal() as db:
        notification = messaging.queue_daily_digest(db, settings)
        if notification is None:
            print("Nenhuma ocorrência nova para o resumo.")
            return 0
        db.commit()
        ok = deliver(db, notification)
    print("Resumo enviado." if ok else "Falha no envio; será reenviado por retry-notifications.")
    return 0 if ok else 2


def cmd_import_sensitive_points(args: argparse.Namespace) -> int:
    """Download schools, day-care centres and health units of the service area from OSM.

    Safe to schedule (e.g. weekly): it upserts by OSM id and removes points deleted in OSM.
    """
    settings = get_settings()
    area = settings.service_area()
    if area is None and not settings.service_area_osm_relation:
        print(
            "Defina SERVICE_AREA_OSM_RELATION ou SERVICE_AREA_BBOX para delimitar a importação.",
            file=sys.stderr,
        )
        return 1
    query = build_query(area, osm_relation=settings.service_area_osm_relation)
    print(f"Consultando Overpass ({settings.overpass_url}) para {settings.service_area_name}...")
    try:
        points = parse_overpass(fetch_overpass(settings.overpass_url, query))
    except OSError as exc:
        print(f"Falha ao consultar a Overpass: {exc}", file=sys.stderr)
        return 2
    print(f"Pontos sensíveis encontrados: {len(points)}")
    if not points and not args.allow_empty:
        # An empty answer is far more likely an Overpass hiccup than a city without schools.
        print("Nenhum ponto retornado; nada foi alterado (use --allow-empty para forçar).")
        return 3
    if args.dry_run:
        for p in points[:20]:
            print(f"  {p.kind:<28} {p.name}")
        return 0
    with SessionLocal() as db:
        inserted, updated, removed = sync_points(db, points)
        db.commit()
    print(f"Inseridos: {inserted}; atualizados: {updated}; removidos: {removed}")
    return 0


def cmd_import_sectors(args: argparse.Namespace) -> int:
    """Sectors from a GeoJSON FeatureCollection (polygons with code, name, population)."""
    path = Path(args.file)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        sectors = parse_sectors_geojson(
            payload,
            code_field=args.code_field,
            name_field=args.name_field,
            population_field=args.population_field,
        )
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Não foi possível ler {path}: {exc}", file=sys.stderr)
        return 1
    except SectorImportError as exc:
        print("Arquivo recusado:", *exc.errors[:30], sep="\n  ", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        inserted, updated, removed = import_sectors(db, sectors, path.name, replace=args.replace)
        db.commit()
    print(f"Setores inseridos: {inserted}; atualizados: {updated}; removidos: {removed}")
    return 0


def cmd_import_liraa(args: argparse.Namespace) -> int:
    path = Path(args.file)
    try:
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        with SessionLocal() as db:
            rows = parse_liraa_csv(text)
            inserted, updated = save_liraa(db, rows)
            db.commit()
    except OSError as exc:
        print(f"Não foi possível ler {path}: {exc}", file=sys.stderr)
        return 1
    except LiraaCsvError as exc:
        print("Arquivo recusado (nada foi gravado):", *exc.errors[:30], sep="\n  ", file=sys.stderr)
        return 1
    print(f"LIRAa: {inserted} inseridos, {updated} atualizados.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("seed", help="Insere tipos, pesos e coeficientes (idempotente)")
    seed.add_argument("--dev", action="store_true", help="Cria usuários de teste")
    seed.add_argument(
        "--fake", type=int, default=0, metavar="N", help="Cria N ocorrências fictícias"
    )
    seed.set_defaults(func=cmd_seed)

    user = sub.add_parser("create-user", help="Cria agente, gestor ou morador")
    user.add_argument("--name", required=True)
    user.add_argument("--email", required=True)
    user.add_argument("--role", required=True, choices=[r.value for r in UserRole])
    user.set_defaults(func=cmd_create_user)

    reset = sub.add_parser("reset-demo", help="Recomeça os dados de demonstração (apaga tudo)")
    reset.add_argument("--yes", action="store_true", help="Confirma a exclusão")
    reset.add_argument("--fake", type=int, default=60, metavar="N")
    reset.set_defaults(func=cmd_reset_demo)

    retry = sub.add_parser("retry-notifications", help="Reenvia e-mails pendentes ou com falha")
    retry.set_defaults(func=cmd_retry_notifications)

    digest = sub.add_parser("send-digest", help="Envia o resumo diário ao grupo de mensagens")
    digest.set_defaults(func=cmd_send_digest)

    imp = sub.add_parser(
        "import-sensitive-points", help="Importa escolas, creches e unidades de saúde da Overpass"
    )
    imp.add_argument("--dry-run", action="store_true", help="Só mostra o que seria importado")
    imp.add_argument("--allow-empty", action="store_true", help="Aceita resposta vazia")
    imp.set_defaults(func=cmd_import_sensitive_points)

    sectors = sub.add_parser("import-sectors", help="Importa setores de um GeoJSON")
    sectors.add_argument("file")
    sectors.add_argument("--code-field", default="codigo")
    sectors.add_argument("--name-field", default="nome")
    sectors.add_argument("--population-field", default="populacao")
    sectors.add_argument(
        "--replace", action="store_true", help="Remove setores que não estão no arquivo"
    )
    sectors.set_defaults(func=cmd_import_sectors)

    liraa = sub.add_parser("import-liraa", help="Importa resultados do LIRAa (CSV)")
    liraa.add_argument("file")
    liraa.set_defaults(func=cmd_import_liraa)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
