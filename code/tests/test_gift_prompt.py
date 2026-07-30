from __future__ import annotations

import json

import httpx
import pytest
from medrag_eval import db
from medrag_eval.prompting import BENCHMARK_PROMPT_VERSION
from medrag_eval.providers.base import ProviderRequest, ProviderStatus
from medrag_eval.providers.tailscale_medical_rag import (
    GIFT_MCQ_PROMPT_ID,
    TailScaleMedicalRAGProvider,
)
from medrag_eval.runner import ProviderModel, plan_calls, run_benchmark


def _seed_dataset(db_path) -> None:
    db.init_db(db_path)
    with db.connect(db_path) as conn:
        dataset = db.upsert_dataset(
            conn,
            name="test_dataset",
            source_xlsx_path="questions.xlsx",
            row_count=1,
        )
        db.insert_question(
            conn,
            dataset,
            {
                "question_id": "q1",
                "region": "Galicia",
                "year": 2026,
                "specialty": "Digestivo",
                "exam_part": "test",
                "question_number": 1,
                "question_text": "Pregunta",
                "option_a": "A",
                "option_b": "B",
                "option_c": "C",
                "option_d": "D",
                "correct_letter": "a",
                "correct_option_text": "A",
            },
        )


def test_gift_plan_defaults_to_prompt_13(tmp_path) -> None:
    db_path = tmp_path / "benchmark.sqlite"
    _seed_dataset(db_path)

    with db.connect(db_path) as conn:
        experiment_id, planned = plan_calls(
            conn,
            dataset="test_dataset",
            experiment_name="gift_prompt_13",
            provider_models=[ProviderModel("tailscale", "model")],
            runs=1,
            limit=None,
            offset=0,
            question_id=None,
            prompt_version=BENCHMARK_PROMPT_VERSION,
            force=False,
        )
        experiment = conn.execute(
            "SELECT config_json FROM experiments WHERE id = ?", (experiment_id,)
        ).fetchone()

    assert len(planned) == 1
    assert json.loads(experiment["config_json"])["tailscale_prompt_id"] == 13


def test_live_run_defaults_to_provider_specific_prompt_regime(tmp_path) -> None:
    db_path = tmp_path / "benchmark.sqlite"
    _seed_dataset(db_path)

    summary = run_benchmark(
        db_path=db_path,
        dataset="test_dataset",
        experiment_name="provider_specific_prompt",
        provider_models=[ProviderModel("tailscale", "model")],
        runs=1,
        limit=None,
        dry_run=True,
    )

    with db.connect(db_path) as conn:
        experiment = conn.execute(
            "SELECT prompt_version, config_json FROM experiments WHERE name = ?",
            ("provider_specific_prompt",),
        ).fetchone()

    assert summary.dry_run is True
    assert experiment["prompt_version"] == BENCHMARK_PROMPT_VERSION
    assert json.loads(experiment["config_json"])["tailscale_prompt_id"] == 13


def test_gift_plan_rejects_any_other_prompt(tmp_path) -> None:
    db_path = tmp_path / "benchmark.sqlite"
    _seed_dataset(db_path)

    with db.connect(db_path) as conn:
        with pytest.raises(ValueError, match="must use --tailscale-prompt-id 13"):
            plan_calls(
                conn,
                dataset="test_dataset",
                experiment_name="wrong_prompt",
                provider_models=[ProviderModel("tailscale", "model")],
                runs=1,
                limit=None,
                offset=0,
                question_id=None,
                prompt_version=BENCHMARK_PROMPT_VERSION,
                force=False,
                tailscale_prompt_id=7,
            )
        experiment_count = conn.execute(
            "SELECT COUNT(*) FROM experiments"
        ).fetchone()[0]

    assert experiment_count == 0


def test_gift_provider_sends_prompt_13_when_request_omits_it() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["prompt_id"] = request.headers["X-Prompt-ID"]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"answer":"a"}'}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TailScaleMedicalRAGProvider(
        base_url="http://gift.test",
        email="admin@gift.ai",
        password="secret",
        client=client,
    )
    provider._token = "test-token"

    response = provider.chat(
        ProviderRequest(
            provider="tailscale_medical_rag",
            model="model",
            messages=[{"role": "user", "content": "Pregunta"}],
        ),
        retry=False,
    )

    assert response.status == ProviderStatus.OK
    assert captured["prompt_id"] == str(GIFT_MCQ_PROMPT_ID)
    assert response.prompt_id == GIFT_MCQ_PROMPT_ID
    assert response.request_headers == {"X-Prompt-ID": "13"}


def test_gift_provider_rejects_any_other_prompt() -> None:
    provider = TailScaleMedicalRAGProvider(
        base_url="http://gift.test",
        email="admin@gift.ai",
        password="secret",
        client=httpx.Client(transport=httpx.MockTransport(lambda _: None)),
    )

    with pytest.raises(ValueError, match="must use prompt_id=13"):
        provider.chat(
            ProviderRequest(
                provider="tailscale_medical_rag",
                model="model",
                messages=[{"role": "user", "content": "Pregunta"}],
                prompt_id=7,
            ),
            retry=False,
        )
