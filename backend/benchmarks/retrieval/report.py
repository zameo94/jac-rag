"""Structured textual report for the retrieval baseline."""

from __future__ import annotations

from benchmarks.retrieval.analysis import FailureAnalysis, FailureCase, StructureCheck
from benchmarks.retrieval.index import BenchmarkConfig, IndexedChunk
from benchmarks.retrieval.runner import Report

SNIPPET = 160


def _snippet(text: str) -> str:
    flat = " ".join(text.split())
    return flat[:SNIPPET] + ("..." if len(flat) > SNIPPET else "")


def _render_hit(position: int, hit) -> str:
    metadata = hit.metadata
    section = metadata.get("section")
    section_repr = " > ".join(section) if section else "-"
    row_indices = metadata.get("row_indices")
    return (
        f"      #{position} score={metadata.get('score', 0.0):.4f} "
        f"doc={hit.document_id} chunk={metadata.get('chunk_index')} "
        f"page={metadata.get('page')} block_type={metadata.get('block_type')} "
        f"table_id={metadata.get('table_id')} rows={row_indices} section={section_repr}\n"
        f"        text: {_snippet(hit.text)}"
    )


def _render_failure(failure: FailureCase) -> str:
    lines = [
        f"  - [{failure.category}] {failure.case_id}: {failure.query}",
        f"      classification: {failure.classification}  "
        f"rank={failure.rank}  indexed_matches={failure.indexed_matches}",
        f"      ground truth: {failure.ground_truth}",
        "      top results:",
    ]
    for position, hit in enumerate(failure.hits, start=1):
        lines.append(_render_hit(position, hit))
    return "\n".join(lines)


def render_inventory(
    *,
    config: BenchmarkConfig,
    dataset_name: str,
    dataset_hash: str,
    chunks: list[IndexedChunk],
) -> str:
    """Report the chunks produced by the real pipeline (no queries required)."""
    lines: list[str] = []
    lines.append("Retrieval Baseline - chunk inventory (no queries provided)")
    lines.append("")
    lines.extend(_config_lines(config, dataset_name, dataset_hash))
    lines.append(f"Chunks: {len(chunks)}")
    lines.append("")

    seen: list[str] = []
    for chunk in chunks:
        if chunk.document_id not in seen:
            seen.append(chunk.document_id)

    for document_id in seen:
        document_chunks = [c for c in chunks if c.document_id == document_id]
        lines.append(f"[{document_id}] chunks={len(document_chunks)}")
        for chunk in document_chunks:
            metadata = chunk.metadata
            section = metadata.get("section")
            section_repr = " > ".join(section) if section else "-"
            lines.append(
                f"  #{chunk.chunk_index} block_type={metadata.get('block_type')} "
                f"page={metadata.get('page')} table_id={metadata.get('table_id')} "
                f"rows={metadata.get('row_indices')} section={section_repr} "
                f"oversized={metadata.get('oversized')}"
            )
            lines.append(f"      {_snippet(chunk.text)}")
        lines.append("")

    return "\n".join(lines)


def _config_lines(config: BenchmarkConfig, dataset_name: str, dataset_hash: str) -> list[str]:
    return [
        "Embedding:",
        f"  Model: {config.embedding_model}",
        f"  Dimension: {config.embedding_dim}",
        f"  Distance: {config.distance}",
        "Chunk configuration:",
        (
            f"  target={config.chunk_target_size} max={config.chunk_max_size} "
            f"overlap={config.chunk_overlap} table_context={config.table_context} "
            f"section_context={config.section_context} metadata={config.include_metadata}"
        ),
        "Retrieval:",
        (
            f"  collection={config.collection} limit={config.retrieval_limit} "
            f"threshold={config.relevance_threshold}"
        ),
        f"Dataset: {dataset_name} (sha256 {dataset_hash})",
        "",
    ]


def render_report(
    *,
    config: BenchmarkConfig,
    dataset_name: str,
    dataset_hash: str,
    report: Report,
    analysis: FailureAnalysis,
    structure: list[StructureCheck] | None = None,
) -> str:
    lines: list[str] = []
    lines.append("Retrieval Baseline")
    lines.append("")
    lines.extend(_config_lines(config, dataset_name, dataset_hash))
    lines.append("Overall")
    lines.append(f"  Queries: {len(report.outcomes)}")
    for key, value in report.overall.items():
        lines.append(f"  {key}: {value:.4f}")
    lines.append("")
    lines.append("By category")
    for category in sorted(report.per_category):
        count = report.per_category_counts.get(category, 0)
        lines.append(f"  {category} (queries={count})")
        for key, value in report.per_category[category].items():
            lines.append(f"    {key}: {value:.4f}")
    lines.append("")
    lines.append("Rank distribution (first relevant chunk)")
    total = len(report.outcomes) or 1
    for bucket, count in report.rank_distribution.items():
        lines.append(f"  rank {bucket}: {count} ({count / total:.4f})")
    lines.append("")
    lines.append("Failure analysis")
    for key, value in analysis.counts().items():
        lines.append(f"  {key}: {value}")
    lines.append("")

    if analysis.ingestion:
        lines.append("Ingestion / chunking failures")
        for failure in analysis.ingestion:
            lines.append(_render_failure(failure))
        lines.append("")
    if analysis.retrieval:
        lines.append("Retrieval failures")
        for failure in analysis.retrieval:
            lines.append(_render_failure(failure))
        lines.append("")
    if analysis.ranking:
        lines.append("Ranking failures")
        for failure in analysis.ranking:
            lines.append(_render_failure(failure))
        lines.append("")
    if analysis.ambiguous:
        lines.append("Ambiguous / weak ground truth")
        for failure in analysis.ambiguous:
            lines.append(
                f"  - [{failure.category}] {failure.case_id}: {failure.query} "
                f"(indexed_matches={failure.indexed_matches})"
            )
        lines.append("")

    if structure:
        lines.append("Structure checks (retrieved chunk metadata)")
        for check in structure:
            page = check.page if check.page is not None else "n/a"
            lines.append(
                f"  - [{check.category}] {check.case_id} retrieved={check.retrieved} "
                f"table_id={check.table_id} rows={check.row_indices} "
                f"source_block_ids={check.source_block_ids} page={page} section={check.section}"
            )
        lines.append("")

    return "\n".join(lines)
