
import hashlib
import re
import time
import uuid
from typing import Dict, List, Optional, Tuple

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from transformers import AutoTokenizer

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


class ChunkingError(Exception):
    """Raised when document chunking fails."""
    pass



_BLOCK_TYPE_TABLE = "table"
_BLOCK_TYPE_CODE = "code"


class ChunkingService:
    """
    Splits a Markdown ``Document`` into retrieval-optimised chunks.

    - Header-aware parent / child splitting (H1 → H3).
    - Atomic protection for Markdown tables and fenced code blocks.
    - Vietnamese-optimised recursive character separators.
    - Deterministic, content-based chunk IDs for idempotent upserts.
    - Post-split token-count validation and context-header budget.
    - Deduplication of identical chunks.
    - Structured logging with processing metrics.

    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        tokenizer_model: Optional[str] = None,
        context_reserved_tokens: Optional[int] = None,
    ):
        # ---- resolve config (explicit arg > settings > default) ----
        self._chunk_size = chunk_size or settings.CHUNK_SIZE
        self._chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        self._tokenizer_model = tokenizer_model or settings.TOKENIZER_MODEL
        self._context_reserved = context_reserved_tokens or settings.CHUNK_CONTEXT_RESERVED_TOKENS

        # ---- tokenizer (loaded once, thread-safe for encode) ----
        self._tokenizer = AutoTokenizer.from_pretrained(self._tokenizer_model)

        # ---- header splitter ----
        self._header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "H1"),
                ("##", "H2"),
                ("###", "H3"),
            ],
            strip_headers=False,
        )

        # ---- child splitter with Vietnamese-optimised separators ----
        self._child_splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
            tokenizer=self._tokenizer,
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
            separators=[
                "\n\n",   # paragraph break
                "\n",     # line break
                ". ",     # sentence boundary (safe — won't split "3.14")
                "; ",     # clause boundary
                ", ",     # sub-clause
                " ",      # word boundary
                "",       # character fallback
            ],
        )

        logger.info(
            "ChunkingService initialised — chunk_size=%d, overlap=%d, tokenizer=%s",
            self._chunk_size,
            self._chunk_overlap,
            self._tokenizer_model,
        )

    def process_document(self, input_doc: Document) -> List[Document]:
        """
        Split *input_doc* into retrieval-ready chunks.

        Args:
            input_doc: A LangChain ``Document`` whose ``page_content`` is
                Markdown text and whose ``metadata`` carries at least a
                ``source`` key.

        Returns:
            Deduplicated list of child ``Document`` objects, each annotated
            with ``chunk_id``, ``parent_id``, ``chunk_type``, and the
            original metadata.

        Raises:
            ChunkingError: If any stage of the pipeline fails.
        """
        t0 = time.perf_counter()
        source = input_doc.metadata.get("source", "<unknown>")

        try:
            original_metadata = input_doc.metadata.copy()
            text = input_doc.page_content

            # 1) Protect atomic blocks (tables, code) with placeholders
            text, protected_blocks = self._protect_blocks(text)

            # 2) Split by Markdown headers → parent sections
            parent_docs = self._header_splitter.split_text(text)

            all_chunks: List[Document] = []
            table_count = 0

            for parent_idx, parent in enumerate(parent_docs):
                # --- build header context breadcrumb ---
                headers = [
                    parent.metadata[h]
                    for h in ("H1", "H2", "H3")
                    if h in parent.metadata
                ]
                headers_context = " > ".join(headers)

                clean_parent_text = self._strip_placeholders(
                    parent.page_content, protected_blocks
                )
                parent_id = hashlib.sha256(
                    f"{source}:{parent_idx}:{clean_parent_text}".encode("utf-8")
                ).hexdigest()[:16]

                merged_meta = {
                    **original_metadata,
                    **parent.metadata,
                    "parent_id": parent_id,
                }

                remaining_text = parent.page_content
                for block_id, (block_type, block_content) in protected_blocks.items():
                    if block_id not in remaining_text:
                        continue
                    remaining_text = remaining_text.replace(block_id, "")

                    if block_type == _BLOCK_TYPE_TABLE:
                        table_count += 1
                        table_preview = self._get_table_preview(
                            block_content, max_tokens=self._chunk_size
                        )
                        contextualized = (
                            f"[Bối cảnh: {headers_context} — Bảng dữ liệu]\n{table_preview}"
                            if headers_context
                            else table_preview
                        )
                        chunk_id = self._make_chunk_id(source, parent_idx, "tbl", block_id)
                        all_chunks.append(
                            Document(
                                page_content=self._truncate_to_token_limit(contextualized),
                                metadata={
                                    **merged_meta,
                                    "chunk_type": "table",
                                    "chunk_id": chunk_id,
                                },
                            )
                        )

                    elif block_type == _BLOCK_TYPE_CODE:
                        contextualized = (
                            f"[Bối cảnh: {headers_context} — Code block]\n{block_content}"
                            if headers_context
                            else block_content
                        )
                        chunk_id = self._make_chunk_id(source, parent_idx, "code", block_id)
                        all_chunks.append(
                            Document(
                                page_content=self._truncate_to_token_limit(contextualized),
                                metadata={
                                    **merged_meta,
                                    "chunk_type": "code",
                                    "chunk_id": chunk_id,
                                },
                            )
                        )

                # --- split the remaining text into child chunks ---
                remaining_text = remaining_text.strip()
                if remaining_text:
                    child_splits = self._child_splitter.split_text(remaining_text)
                    for child_idx, child_text in enumerate(child_splits):
                        contextualized = (
                            f"[Bối cảnh: {headers_context}]\n{child_text}"
                            if headers_context
                            else child_text
                        )
                        chunk_id = self._make_chunk_id(
                            source, parent_idx, "txt", str(child_idx)
                        )
                        all_chunks.append(
                            Document(
                                page_content=self._truncate_to_token_limit(contextualized),
                                metadata={
                                    **merged_meta,
                                    "chunk_type": "text",
                                    "chunk_id": chunk_id,
                                },
                            )
                        )

            # 3) Deduplicate by content hash
            deduped = self._deduplicate(all_chunks)

            # 4) Metrics
            elapsed_ms = (time.perf_counter() - t0) * 1000
            token_counts = [
                len(self._tokenizer.encode(c.page_content)) for c in deduped
            ]
            avg_tokens = sum(token_counts) / len(token_counts) if token_counts else 0
            max_tokens = max(token_counts) if token_counts else 0

            logger.info(
                "Chunking completed — source=%s | parents=%d | raw_chunks=%d | "
                "deduped=%d | tables=%d | avg_tokens=%.0f | max_tokens=%d | "
                "elapsed=%.1fms",
                source,
                len(parent_docs),
                len(all_chunks),
                len(deduped),
                table_count,
                avg_tokens,
                max_tokens,
                elapsed_ms,
            )

            return deduped

        except Exception as exc:
            logger.error(
                "Chunking failed — source=%s | error=%s",
                source,
                exc,
                exc_info=True,
            )
            raise ChunkingError(
                f"Failed to chunk document '{source}': {exc}"
            ) from exc

    

    def _protect_blocks(
        self, text: str
    ) -> Tuple[str, Dict[str, Tuple[str, str]]]:
        """
        Replace Markdown tables and fenced code blocks with unique
        placeholders so they are not split by the recursive splitter.

        Returns:
            (safe_text, mapping)  where *mapping* maps placeholder →
            ``(block_type, original_content)``.
        """
        protected: Dict[str, Tuple[str, str]] = {}

        # --- fenced code blocks (``` … ```) ---
        code_pattern = r"(```[\s\S]*?```)"

        def _replace_code(match: re.Match) -> str:
            bid = f"__PROTECTED_CODE_{uuid.uuid4().hex[:8]}__"
            protected[bid] = (_BLOCK_TYPE_CODE, match.group(1).strip())
            return f"\n\n{bid}\n\n"

        text = re.sub(code_pattern, _replace_code, text)

        # --- Markdown tables (consecutive lines starting & ending with |) ---
        table_pattern = r"((?:^\|.*\|$\n?)+)"

        def _replace_table(match: re.Match) -> str:
            bid = f"__PROTECTED_TABLE_{uuid.uuid4().hex[:8]}__"
            protected[bid] = (_BLOCK_TYPE_TABLE, match.group(1).strip())
            return f"\n\n{bid}\n\n"

        text = re.sub(table_pattern, _replace_table, text, flags=re.MULTILINE)

        return text, protected

    # ------------------------------------------------------------------
    # Table preview (token-aware)
    # ------------------------------------------------------------------

    def _get_table_preview(self, table_str: str, max_tokens: int = 500, min_rows: int = 2) -> str:
        lines = table_str.strip().split("\n")
        if not lines:
            return table_str

        effective_limit = max_tokens - self._context_reserved
        
        tokens = self._tokenizer.encode(table_str)
        
        if len(tokens) <= effective_limit:
            return table_str
            
        truncated_text = self._tokenizer.decode(tokens[:effective_limit], skip_special_tokens=True)
        
        last_newline = truncated_text.rfind('\n')
        if last_newline != -1:
            truncated_text = truncated_text[:last_newline]
            
        return truncated_text + "\n| … | (bảng còn tiếp) |"
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_placeholders(text: str, blocks: Dict[str, Tuple[str, str]]) -> str:
        """Remove all placeholder tokens from *text*."""
        for bid in blocks:
            text = text.replace(bid, "")
        return text.strip()

    @staticmethod
    def _make_chunk_id(
        source: str, parent_idx: int, kind: str, discriminator: str
    ) -> str:
        """
        Deterministic chunk ID based on position + content discriminator.

        Format: ``sha256(source:parent_idx:kind:discriminator)[:16]``
        """
        raw = f"{source}:{parent_idx}:{kind}:{discriminator}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _truncate_to_token_limit(self, text: str) -> str:
        """Truncate *text* so it never exceeds ``_chunk_size`` tokens."""
        tokens = self._tokenizer.encode(text)
        if len(tokens) <= self._chunk_size:
            return text
        return self._tokenizer.decode(
            tokens[: self._chunk_size],
            skip_special_tokens=True,
        )

    @staticmethod
    def _deduplicate(chunks: List[Document]) -> List[Document]:
        seen = set()
        unique = []
        for chunk in chunks:
            # Nhóm hash = Nội dung + Parent ID (Context)
            parent_id = chunk.metadata.get("parent_id", "")
            h = hashlib.sha256(f"{parent_id}:{chunk.page_content}".encode("utf-8")).hexdigest()
            if h not in seen:
                seen.add(h)
                unique.append(chunk)
        return unique