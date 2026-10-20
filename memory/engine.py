"""Unified Memory Manager (Engine Facade API) orchestrating the 3 tiers and 4 stitches."""

from typing import Any, Dict, List, Optional
from uuid import uuid4

from config import MemoryConfig, default_config, WorkingMemoryBackend, FactStoreBackend, VectorStoreBackend
from core.models import (
    ContextPackage,
    FactItem,
    MemoryRecord,
    Turn,
    TurnRole,
    utc_now,
)
from core.interfaces import (
    BaseWorkingMemory,
    BaseFactStore,
    BaseVectorStore,
    BaseEmbedder,
)
from tiers.working.in_memory import InMemoryWorkingMemory
from tiers.working.redis_adapter import RedisWorkingMemory
from tiers.facts.sqlite_adapter import SQLiteFactStore
from tiers.facts.postgres_adapter import PostgreSQLFactStore
from tiers.semantic.qdrant_adapter import QdrantAdapter
from tiers.semantic.chroma_adapter import ChromaAdapter
from embeddings.embedder import get_embedder
from stitches.extractor import FactExtractor
from stitches.conflict_resolver import ConflictResolver
from stitches.synthesizer import ContextSynthesizer
from stitches.consolidation import ConsolidationEngine, ConsolidationResult


class MemoryEngine:
    """Unified Facade API for the Fused Dynamic Memory Layer."""

    def __init__(
        self,
        config: Optional[MemoryConfig] = None,
        working_memory: Optional[BaseWorkingMemory] = None,
        fact_store: Optional[BaseFactStore] = None,
        vector_store: Optional[BaseVectorStore] = None,
        embedder: Optional[BaseEmbedder] = None,
    ):
        self.config = config or default_config

        # Embedder
        self.embedder = embedder or get_embedder(self.config)

        # Tier 1: Working Memory
        if working_memory is not None:
            self.working = working_memory
        elif self.config.working_backend == WorkingMemoryBackend.REDIS:
            self.working = RedisWorkingMemory(
                redis_url=self.config.redis_url,
                ttl_seconds=self.config.session_ttl_seconds,
            )
        else:
            self.working = InMemoryWorkingMemory(wal_dir=self.config.wal_dir)

        # Tier 2: Fact Store
        if fact_store is not None:
            self.facts = fact_store
        elif self.config.fact_backend == FactStoreBackend.POSTGRES and self.config.postgres_url:
            self.facts = PostgreSQLFactStore(connection_url=self.config.postgres_url)
        else:
            self.facts = SQLiteFactStore(db_path=self.config.sqlite_path)

        # Tier 3: Semantic Vector Store
        if vector_store is not None:
            self.vectors = vector_store
        elif self.config.vector_backend == VectorStoreBackend.CHROMA:
            self.vectors = ChromaAdapter(
                persist_dir=self.config.chroma_path,
                collection_name=self.config.collection_name,
            )
        else:
            self.vectors = QdrantAdapter(
                location=self.config.qdrant_location,
                collection_name=self.config.collection_name,
                dim=self.embedder.dimension,
            )

        # Stitches
        self.extractor = FactExtractor(config=self.config)
        self.resolver = ConflictResolver(fact_store=self.facts)
        self.synthesizer = ContextSynthesizer(config=self.config)
        self.consolidation = ConsolidationEngine(
            working_memory=self.working,
            fact_store=self.facts,
            vector_store=self.vectors,
            embedder=self.embedder,
            config=self.config,
        )

    def remember(
        self,
        user_id: str,
        text: str,
        session_id: Optional[str] = None,
        role: TurnRole = TurnRole.USER,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record an incoming agent/user interaction into the memory hierarchy.
        
        Orchestration flow:
        1. Logs turn to Tier 1 Working Memory (if session_id provided).
        2. Stitch 1: Triage and extract atomic facts & summaries.
        3. Stitch 2: Cross-referencing UUID linked across SQL and vector payloads.
        4. Stitch 3: Conflict resolution & deduplication against active Tier 2 state.
        5. Writes archival memory to Tier 3 with dense vector embedding.
        """
        metadata = metadata or {}
        event_id = uuid4()

        # Step 1: Append turn to Tier 1 Working Memory
        if session_id:
            turn = Turn(
                id=event_id,
                session_id=session_id,
                user_id=user_id,
                role=role,
                content=text,
                tokens=self.synthesizer.count_tokens(text),
                metadata=metadata,
            )
            self.working.append_turn(turn)

        # Step 2: Stitch 1 (Extraction)
        plan = self.extractor.extract_memory_plan(text=text, user_id=user_id)

        # Step 3 & 4: Stitch 3 (Conflict resolution against Tier 2)
        saved_facts: List[FactItem] = []
        if plan.facts_to_add or plan.keys_to_invalidate:
            for fact in plan.facts_to_add:
                fact.source_event_id = event_id
            saved_facts = self.resolver.resolve_and_apply(
                candidate_facts=plan.facts_to_add,
                keys_to_invalidate=plan.keys_to_invalidate,
            )

        # Step 5: Upsert archival memory to Tier 3
        archival_record_id = None
        if plan.archival_text:
            emb = self.embedder.embed_text(plan.archival_text)
            archival_record = MemoryRecord(
                id=event_id,
                user_id=user_id,
                session_id=session_id,
                text=plan.archival_text,
                embedding=emb,
                metadata={
                    "entities": plan.entities,
                    "event_type": role.value,
                    **metadata,
                },
            )
            self.vectors.upsert_vectors([archival_record])
            archival_record_id = str(event_id)

        return {
            "event_id": str(event_id),
            "user_id": user_id,
            "session_id": session_id,
            "facts_saved": [f.model_dump() for f in saved_facts],
            "archival_record_id": archival_record_id,
            "entities": plan.entities,
        }

    def recall(
        self,
        user_id: str,
        query: str,
        session_id: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> ContextPackage:
        """Recall concentrated context (< 500 tokens) for system prompt injection.
        
        Synthesizes:
        - Tier 1: Most recent conversation window for active session.
        - Tier 2: Ground-truth active user facts and preferences.
        - Tier 3: Top-K semantic archival matches.
        """
        k = top_k or self.config.top_k_semantic_matches

        # Tier 1: Working memory window
        working_turns: List[Turn] = []
        if session_id:
            working_turns = self.working.get_active_window(
                session_id=session_id,
                limit=self.config.working_window_turns,
            )

        # Tier 2: Active structured facts
        core_facts = self.facts.get_facts(user_id=user_id, active_only=True)
        # Touch facts to reinforce access frequency
        for f in core_facts:
            self.facts.touch_fact(f.id)

        # Tier 3: Semantic archival matches
        query_emb = self.embedder.embed_text(query)
        archival_hits = self.vectors.query_similar(
            user_id=user_id,
            query_embedding=query_emb,
            top_k=k,
            active_only=True,
        )

        # Stitch 4: Dynamic Synthesis with token budget limit
        return self.synthesizer.synthesize(
            user_id=user_id,
            session_id=session_id,
            working_turns=working_turns,
            core_facts=core_facts,
            archival_memories=archival_hits,
        )

    def consolidate(self, user_id: str, session_id: str) -> ConsolidationResult:
        """Execute REM Sleep consolidation cycle on a session."""
        return self.consolidation.consolidate_session(user_id=user_id, session_id=session_id)

    def get_active_facts(self, user_id: str) -> List[FactItem]:
        """Fetch all currently active ground-truth facts for a user."""
        return self.facts.get_facts(user_id=user_id, active_only=True)
