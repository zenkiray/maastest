# MaaS Benchmark Web Runner

## Contents
- `web_app/`: FastAPI + Jinja2 + HTMX benchmark portal.
- `config/config.example.yaml`: central config template for LLM, embedding, reranker, and Qdrant.
- `scripts/`: generation, validation, Qdrant indexing, UC1 RAG, and UC2 multi-agent runners.
- `requirements-web.txt`: Python dependencies for the web runner.

Generated benchmark data, uploaded datasets, run logs, local secrets, Excel review files, and screenshots are intentionally ignored by Git. Generate or upload datasets locally before running live tests.

## Latest Scope
The dataset follows the latest customer answer:
- Product content is limited to CardX and AutoX only.
- Product details and collection disclosures are plausible synthetic content, not exact regulatory replication.
- Formal JSONL data is Thai-dominant with English banking loanwords.
- Each use case uses the full ~100-item workload per run.
- Harness runs should sweep concurrency levels, for example `1 / 4 / 16 / 64`, and record per-call raw logs plus p50/p95 summary metrics.

## Generate And Validate
```bash
python3 scripts/generate_maas_dataset.py
python3 scripts/validate_dataset.py
python3 scripts/validate_config.py --config config/config.example.yaml --allow-placeholders
```

The generated files are written under `benchmark_data/`, which is ignored by Git.

## Create Local Runtime Config
```bash
cp config/config.example.yaml config/config.local.yaml
```

Fill `config.local.yaml` with real API endpoints, API keys, model names, Qdrant URL, and Qdrant credentials. Do not share real secrets.
Put provider-specific embedding request parameters under `embedding.params`. For example, Alibaba Cloud `text-embedding-v4` can use `dimensions: 1024`. If `embedding.params.dimensions` is set, it must match `runtime.qdrant_vector_size`, which is used when creating the Qdrant collection.
Reranker calls are configurable with `reranker.path`, `reranker.request_format`, and `reranker.params`. Use `request_format: "dashscope"` for Alibaba Cloud's native text-rerank endpoint, where the request body is `model + input + parameters`.

## Dry Run
```bash
python3 scripts/build_qdrant_index.py --config config/config.example.yaml --dry-run --allow-example-placeholders
python3 scripts/run_uc1_rag.py --config config/config.example.yaml --dry-run --allow-example-placeholders --limit 2
python3 scripts/run_uc2_agents.py --config config/config.example.yaml --dry-run --allow-example-placeholders --limit 2
```

## Interactive Runner
```bash
python3 scripts/run_benchmark.py
```

The interactive runner lists YAML files under `config/`, then asks for the test case, config file, run mode, concurrency levels, run count, limit, and optional UC1 reranker switch. Every menu has a numbered choice and pressing Enter selects the default option. After each successful run, it prints a readable result table directly in the shell.

## Web Runner
```bash
./start_web.sh
```

The script creates `.venv_web` when needed, installs dependencies, stops any existing web runner, and starts it again in the background. Use `PORT=8001 ./start_web.sh` to run on another port. Open `http://localhost:8000` or the cloud-host address. To stop the web runner without restarting it, run `./stop_web.sh`. The web runner supports login, English/Chinese/Thai UI switching, ZIP dataset upload, Qdrant initialization, Qdrant point browsing, UC1/UC2 execution, live job progress, historical reports, PDF export, and token-cost calculation. The default login is `admin/admin`; change it in Settings before sharing the service.

## Live Run Order
```bash
python3 scripts/validate_config.py --config config/config.local.yaml
python3 scripts/build_qdrant_index.py --config config/config.local.yaml
python3 scripts/run_uc1_rag.py --config config/config.local.yaml
python3 scripts/run_uc2_agents.py --config config/config.local.yaml
```

The live runners write raw per-call JSONL logs and summary JSON files under `runtime.output_dir/platform_label/uc*/`. Streaming mode records TTFT/TPOT when the endpoint supports OpenAI-compatible streaming and usage metadata.
If Qdrant already has a collection with the same name and a different vector size, either change `qdrant.collection_name` or rebuild it with `python3 scripts/build_qdrant_index.py --config config/config.local.yaml --batch-size 10 --recreate-collection`.

All records are synthetic. The formal benchmark JSONL is Thai-dominant with English banking terms. The Chinese workbook is for review only.
