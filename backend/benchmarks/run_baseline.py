"""Retrieval baseline runner.

Input (``--input``) can be:

* a dataset directory containing ``dataset.json`` (full benchmark mode), or
* a single document (PDF/DOCX/Markdown/TXT), or
* a directory of documents (the supported extensions are scanned).

Ground truth is optional: with ``--queries FILE`` (JSONL) the tool computes
Recall@k and MRR; without it, it prints a chunk inventory so you can inspect how
a document was parsed and chunked. If no arguments are given, the built-in
sample dataset is used and the report is written to the default output path.

A queries file has one JSON object per line:

    {"case_id": "...", "category": "...", "query": "...",
     "relevant_document_ids": [...], "expected_substrings": [...]}

``category`` is one of: prose, heading, table, numbers, codes, proper_nouns,
semantic, legal, technical. A chunk counts as relevant when it belongs to a
document in ``relevant_document_ids`` AND contains one of ``expected_substrings``;
with only ``relevant_document_ids`` the judgment is document-level.

The index runs in-memory through the real application pipeline; no external
Qdrant/Postgres/Redis is required.
"""

import argparse
import asyncio
import hashlib
from dataclasses import replace
from pathlib import Path

from app.core.config import get_settings
from app.services.rag.parsers import EXTENSION_MIME, resolve_mime
from benchmarks.retrieval.analysis import analyze, structure_checks
from benchmarks.retrieval.index import QdrantRetrievalIndex
from benchmarks.retrieval.rerank import RerankedIndex
from benchmarks.retrieval.report import render_inventory, render_report
from benchmarks.retrieval.runner import evaluate_async
from benchmarks.retrieval.schema import (
    BenchmarkDataset,
    Category,
    DocumentSpec,
    load_dataset,
    load_queries,
)

DEFAULT_INPUT = Path(__file__).resolve().parent / "retrieval" / "data" / "sample"
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent / "retrieval" / "results" / "baseline.txt"
)


def dataset_hash(dataset: BenchmarkDataset) -> str:
    digest = hashlib.sha256()
    for document in dataset.documents:
        path = dataset.base_dir / document.path
        if path.is_file():
            digest.update(document.document_id.encode())
            digest.update(path.read_bytes())
    for case in dataset.queries:
        digest.update(
            repr(
                (
                    case.case_id,
                    case.query,
                    case.category.value,
                    case.relevant_document_ids,
                    case.expected_substrings,
                )
            ).encode()
        )
    return digest.hexdigest()[:16]


def _collect_documents(input_path: Path) -> tuple[Path, tuple[DocumentSpec, ...]]:
    if input_path.is_file():
        mime = resolve_mime(input_path.name)
        if mime is None:
            raise SystemExit(f"unsupported file type: {input_path.name}")
        return (
            input_path.parent,
            (DocumentSpec(document_id=input_path.stem, mime=mime, path=input_path.name),),
        )

    if input_path.is_dir():
        documents: list[DocumentSpec] = []
        for path in sorted(input_path.rglob("*")):
            if path.is_file() and path.suffix.lower() in EXTENSION_MIME:
                relative = path.relative_to(input_path)
                document_id = str(relative.with_suffix("")).replace("/", "_")
                documents.append(
                    DocumentSpec(
                        document_id=document_id,
                        mime=EXTENSION_MIME[path.suffix.lower()],
                        path=str(relative),
                    )
                )
        if not documents:
            supported = ", ".join(sorted(EXTENSION_MIME))
            raise SystemExit(f"no supported documents found in {input_path} ({supported})")
        return input_path, tuple(documents)

    raise SystemExit(f"input not found: {input_path}")


def resolve_dataset(input_path: Path, queries_path: Path | None) -> BenchmarkDataset:
    if input_path.is_dir() and (input_path / "dataset.json").exists():
        dataset = load_dataset(input_path)
        if queries_path is not None:
            dataset = replace(dataset, queries=load_queries(queries_path))
        return dataset

    base_dir, documents = _collect_documents(input_path)
    queries = load_queries(queries_path) if queries_path is not None else ()
    return BenchmarkDataset(
        name=input_path.stem or input_path.name,
        base_dir=base_dir,
        documents=documents,
        queries=queries,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m benchmarks.run_baseline",
        description=(
            "Run the retrieval baseline using the real application pipeline. With no "
            "arguments it uses the built-in sample dataset and the default output path."
        ),
        epilog=(
            "--input accepts a dataset directory (with dataset.json), a single document "
            "or a directory of documents. Without --queries the tool prints a chunk "
            "inventory instead of metrics."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        dest="input_path",
        type=Path,
        default=DEFAULT_INPUT,
        metavar="PATH",
        help="dataset directory, single document, or directory of documents",
    )
    parser.add_argument(
        "--queries",
        dest="queries_path",
        type=Path,
        default=None,
        metavar="FILE",
        help="optional queries JSONL; without it only the chunk inventory is shown",
    )
    parser.add_argument(
        "--output",
        dest="output_file",
        type=Path,
        default=DEFAULT_OUTPUT,
        metavar="FILE",
        help="report output file; if omitted the default path is used",
    )
    parser.add_argument(
        "--max-k",
        type=int,
        default=10,
        metavar="N",
        help="number of results retrieved per query",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        metavar="N",
        help="top-k used to decide pass/fail in the failure analysis",
    )
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="over-fetch candidates and reorder them with a cross-encoder reranker",
    )
    parser.add_argument(
        "--rerank-candidates",
        type=int,
        default=30,
        metavar="N",
        help="candidate window passed to the reranker (with --rerank)",
    )
    parser.add_argument(
        "--rerank-model",
        type=str,
        default=None,
        metavar="MODEL",
        help="fastembed cross-encoder model (default: RERANK_MODEL)",
    )
    return parser


def _rerank_summary(*, model: str, candidates: int, latencies: list[float]) -> str:
    if latencies:
        ordered = sorted(latencies)
        average = sum(latencies) / len(latencies)
        p50 = ordered[len(ordered) // 2]
        p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    else:
        average = p50 = p95 = 0.0
    return (
        "\nRerank\n"
        f"  model: {model}\n"
        f"  candidates: {candidates}\n"
        f"  latency per query: avg={average:.3f}s p50={p50:.3f}s p95={p95:.3f}s"
    )


async def main() -> None:
    args = build_parser().parse_args()
    dataset = resolve_dataset(args.input_path.resolve(), args.queries_path)
    k_values = (1, 5, 10)
    max_k = max(args.max_k, max(k_values))

    index = await QdrantRetrievalIndex.build(dataset, retrieval_limit=max_k)
    if args.rerank:
        index = RerankedIndex(
            index,
            model=args.rerank_model or get_settings().rerank_model,
            candidates=args.rerank_candidates,
        )
    try:
        if not dataset.queries:
            text = render_inventory(
                config=index.config,
                dataset_name=dataset.name,
                dataset_hash=dataset_hash(dataset),
                chunks=index.indexed_chunks,
            )
        else:
            report = await evaluate_async(
                list(dataset.queries), index, k_values=k_values, limit=max_k
            )
            analysis = analyze(
                list(dataset.queries),
                report,
                index.indexed_chunks,
                k=args.top_k,
                max_k=max_k,
            )
            text = render_report(
                config=index.config,
                dataset_name=dataset.name,
                dataset_hash=dataset_hash(dataset),
                report=report,
                analysis=analysis,
                structure=structure_checks(
                    list(dataset.queries),
                    report,
                    index.indexed_chunks,
                    categories=(Category.TABLE,),
                ),
            )
    finally:
        await index.close()

    if args.rerank:
        text += _rerank_summary(
            model=args.rerank_model or get_settings().rerank_model,
            candidates=args.rerank_candidates,
            latencies=index.latencies,
        )

    print(text)
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_text(text, encoding="utf-8")
    print(f"\n[report written to {args.output_file.resolve()}]")


if __name__ == "__main__":
    asyncio.run(main())
