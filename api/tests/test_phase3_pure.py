"""Pure tests for phase 3: response deadline, Spearman, LIRAa CSV and sector GeoJSON."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.services.deadlines import response_clock
from app.services.liraa import LiraaCsvError, liraa_class, parse_liraa_csv
from app.services.sectors import SectorImportError, fictitious_grid, parse_sectors_geojson
from app.services.stats import average_ranks, describe_correlation, spearman

NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)


def days_ago(n: float) -> datetime:
    return NOW - timedelta(days=n)


# --- "X dias sem resposta" ----------------------------------------------------------------


def test_counter_starts_at_the_notification_and_becomes_overdue_at_the_deadline():
    clock = response_clock(
        created_at=days_ago(20),
        notified_at=days_ago(15.2),
        first_response_at=None,
        deadline_days=15,
        now=NOW,
    )
    assert clock.days_without_response == 15
    assert clock.overdue is True and clock.days_left == 0


def test_counter_before_the_deadline_shows_days_left():
    clock = response_clock(
        created_at=days_ago(3.5),
        notified_at=days_ago(3.4),
        first_response_at=None,
        deadline_days=15,
        now=NOW,
    )
    assert clock.days_without_response == 3 and clock.days_left == 12
    assert clock.overdue is False


def test_without_notification_the_counter_starts_at_registration():
    clock = response_clock(
        created_at=days_ago(16),
        notified_at=None,
        first_response_at=None,
        deadline_days=15,
        now=NOW,
    )
    assert clock.days_without_response == 16 and clock.overdue is True


def test_first_response_stops_the_counter():
    clock = response_clock(
        created_at=days_ago(30),
        notified_at=days_ago(30),
        first_response_at=days_ago(26),
        deadline_days=15,
        now=NOW,
    )
    assert clock.days_without_response is None and clock.overdue is False
    assert clock.responded_after_days == 4


def test_deadline_is_configurable():
    clock = response_clock(
        created_at=days_ago(8),
        notified_at=days_ago(8),
        first_response_at=None,
        deadline_days=7,
        now=NOW,
    )
    assert clock.overdue is True


# --- Spearman -----------------------------------------------------------------------------


def test_average_ranks_share_ties():
    assert average_ranks([10, 20, 20, 30]) == [1, 2.5, 2.5, 4]


def test_spearman_perfect_monotonic_and_inverse():
    assert spearman([1, 2, 3, 4], [10, 100, 1000, 10_000]) == pytest.approx(1)
    assert spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1)


def test_spearman_is_undefined_for_too_few_or_constant_values():
    assert spearman([1, 2], [1, 2]) is None
    assert spearman([1, 1, 1], [1, 2, 3]) is None


def test_correlation_text():
    assert "forte" in describe_correlation(0.85, 16)
    assert "cautela" in describe_correlation(0.85, 5)
    assert "não há concordância" in describe_correlation(0.05, 16)
    assert "insuficientes" in describe_correlation(None, 2)


# --- LIRAa CSV ----------------------------------------------------------------------------


def test_liraa_classes_follow_the_ministry_of_health():
    assert liraa_class(0.9) == "satisfatorio"
    assert liraa_class(1.0) == "alerta"
    assert liraa_class(3.9) == "alerta"
    assert liraa_class(4.0) == "risco"


def test_parses_semicolon_csv_with_brazilian_numbers_and_dates():
    text = "﻿Setor;Período;Data;IIP;IB\nS01;2026-1;15/01/2026;1,8;2,4\nS02;2026-1;15/01/2026;0,5;\n"
    rows = parse_liraa_csv(text)
    assert [r.sector_code for r in rows] == ["S01", "S02"]
    assert rows[0].iip == Decimal("1.8") and rows[0].ib == Decimal("2.4")
    assert rows[0].survey_date == date(2026, 1, 15)
    assert rows[1].ib is None


def test_parses_comma_csv_with_aliases_and_iso_dates():
    rows = parse_liraa_csv(
        "codigo_setor,ciclo,data_levantamento,iip\nS01,out/2026,2026-10-01,4.2\n"
    )
    assert rows[0].period == "out/2026" and rows[0].iip == Decimal("4.2")


@pytest.mark.parametrize(
    "text, message",
    [
        ("", "vazio"),
        ("setor;periodo;iip\nS01;1;2\n", "Coluna obrigatória ausente: data"),
        ("setor;periodo;data;iip\nS01;1;31/02/2026;2\n", "Linha 2: data inválida"),
        ("setor;periodo;data;iip\nS01;1;01/02/2026;150\n", "Linha 2: IIP deve estar entre 0 e 100"),
        ("setor;periodo;data;iip\nS01;1;01/02/2026;abc\n", "Linha 2: IIP inválido"),
        (
            "setor;periodo;data;iip\nS01;1;01/02/2026;1\nS01;1;01/02/2026;2\n",
            "Linha 3: setor S01 repetido",
        ),
        ("setor;periodo;data;iip\n;1;01/02/2026;1\n", "Linha 2: setor e período"),
    ],
)
def test_rejects_invalid_files_with_line_numbers(text, message):
    with pytest.raises(LiraaCsvError) as error:
        parse_liraa_csv(text)
    assert any(message in e for e in error.value.errors)


def test_one_bad_line_rejects_the_whole_file():
    text = "setor;periodo;data;iip\nS01;1;01/02/2026;1\nS02;1;xx;2\nS03;1;01/02/2026;3\n"
    with pytest.raises(LiraaCsvError) as error:
        parse_liraa_csv(text)
    assert len(error.value.errors) == 1


# --- sectors GeoJSON ----------------------------------------------------------------------

SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}


def feature(**props):
    return {"type": "Feature", "geometry": SQUARE, "properties": props}


def test_parses_sectors_with_custom_field_names():
    payload = {
        "type": "FeatureCollection",
        "features": [feature(CD_SETOR="A", NM="Centro", POP="12000")],
    }
    sectors = parse_sectors_geojson(
        payload, code_field="CD_SETOR", name_field="NM", population_field="POP"
    )
    assert sectors[0].code == "A" and sectors[0].population == 12000


@pytest.mark.parametrize(
    "props, message",
    [
        ({"nome": "x", "populacao": 10}, "campo 'codigo' ausente"),
        ({"codigo": "A", "populacao": 0}, "maior que zero"),
        ({"codigo": "A", "populacao": "muita"}, "população inválida"),
    ],
)
def test_rejects_sectors_without_code_or_valid_population(props, message):
    with pytest.raises(SectorImportError) as error:
        parse_sectors_geojson({"type": "FeatureCollection", "features": [feature(**props)]})
    assert message in error.value.errors[0]


def test_fictitious_grid_is_clearly_labelled():
    grid = fictitious_grid((-43.9, -16.8, -43.8, -16.7), rows=2, cols=3)
    assert len(grid) == 6
    assert grid[0].code == "F01" and "fictício" in grid[0].name
    assert all(s.population > 0 for s in grid)
