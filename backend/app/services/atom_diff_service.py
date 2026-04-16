"""
P5B-01: BRD Delta Diffing — atom-level comparison between document versions.

Computes ADDED / MODIFIED / UNCHANGED / DELETED for requirement atoms when a
document is re-uploaded. Enables:
  - Skipping re-validation for UNCHANGED atoms (Gemini cost savings ~40-60%)
  - Auto-closing mismatches for DELETED atoms (triage history preserved)
  - Targeted re-validation for ADDED + MODIFIED atoms only
"""
import hashlib
import difflib
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from app.core.logging import logger


def _normalize_content(text: str) -> str:
    """Normalize atom content for stable hashing (strip whitespace, lowercase)."""
    return " ".join(text.lower().strip().split())


def _hash_content(text: str) -> str:
    """SHA-256 of normalized content."""
    return hashlib.sha256(_normalize_content(text).encode()).hexdigest()


def _levenshtein_similarity(s1: str, s2: str) -> float:
    """Normalized Levenshtein similarity (0.0–1.0) using SequenceMatcher."""
    return difflib.SequenceMatcher(None, s1, s2).ratio()


@dataclass
class AtomDelta:
    """Result of comparing one new atom against prior version atoms."""
    new_atom_content: str
    new_atom_type: str
    status: str  # "added" | "modified" | "unchanged"
    previous_atom_id: Optional[int] = None
    previous_content: Optional[str] = None
    content_hash: str = field(default="")

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = _hash_content(self.new_atom_content)


@dataclass
class DocumentAtomDiff:
    """Full diff result for a document re-atomization."""
    document_id: int
    previous_version: Optional[str]
    new_version: str
    added: List[AtomDelta] = field(default_factory=list)
    modified: List[AtomDelta] = field(default_factory=list)
    unchanged: List[AtomDelta] = field(default_factory=list)
    deleted_atom_ids: List[int] = field(default_factory=list)

    @property
    def needs_validation(self) -> List[AtomDelta]:
        """Atoms that require a Gemini validation pass (new + changed only)."""
        return self.added + self.modified

    @property
    def total_prior_atoms(self) -> int:
        return len(self.modified) + len(self.unchanged) + len(self.deleted_atom_ids)

    def summary(self) -> dict:
        return {
            "added": len(self.added),
            "modified": len(self.modified),
            "unchanged": len(self.unchanged),
            "deleted": len(self.deleted_atom_ids),
            "previous_version": self.previous_version,
            "new_version": self.new_version,
        }


class AtomDiffService:
    """
    Computes atom-level diffs between document versions.
    Called by validation_service.atomize_document() INSTEAD of delete-all
    when re-atomizing an existing document.

    Matching strategy:
      Primary:   exact content_hash match (identical requirement)
      Secondary: same atom_type + Levenshtein similarity ≥ 0.75 (minor wording edits)
    """

    FUZZY_MATCH_THRESHOLD = 0.75

    def compute_diff(
        self,
        db: Session,
        document_id: int,
        new_atoms_data: List[dict],
        new_version: str,
        tenant_id: int,
    ) -> DocumentAtomDiff:
        """
        Compare new atoms (from fresh Gemini atomization) against prior atoms in DB.

        Algorithm:
        1. Load all prior atoms for this document from DB
        2. Build hash → atom_id + type → atoms lookups
        3. For each new atom:
           a. Exact hash match → UNCHANGED (carry previous_atom_id)
           b. Same-type fuzzy match ≥ 0.75 → MODIFIED
           c. No match → ADDED
        4. Unmatched prior atom IDs → DELETED
        """
        from app.crud.crud_requirement_atom import requirement_atom as crud_atom

        prior_atoms = crud_atom.get_by_document(db, document_id=document_id)
        prior_version = prior_atoms[0].document_version if prior_atoms else None

        diff = DocumentAtomDiff(
            document_id=document_id,
            previous_version=prior_version,
            new_version=new_version,
        )

        if not prior_atoms:
            # First upload — all atoms are ADDED
            for atom_data in new_atoms_data:
                diff.added.append(AtomDelta(
                    new_atom_content=atom_data["content"],
                    new_atom_type=atom_data.get("atom_type", "FUNCTIONAL_REQUIREMENT"),
                    status="added",
                ))
            return diff

        # Build lookup maps
        prior_by_hash: Dict[str, object] = {}
        prior_by_type: Dict[str, list] = {}
        for atom in prior_atoms:
            h = _hash_content(atom.content)
            prior_by_hash[h] = atom
            prior_by_type.setdefault(atom.atom_type, []).append(atom)

        matched_prior_ids: set = set()

        for atom_data in new_atoms_data:
            content = atom_data["content"]
            atom_type = atom_data.get("atom_type", "FUNCTIONAL_REQUIREMENT")
            new_hash = _hash_content(content)

            # ── Exact hash match → UNCHANGED ──
            if new_hash in prior_by_hash:
                prior = prior_by_hash[new_hash]
                matched_prior_ids.add(prior.id)
                diff.unchanged.append(AtomDelta(
                    new_atom_content=content,
                    new_atom_type=atom_type,
                    status="unchanged",
                    previous_atom_id=prior.id,
                    previous_content=prior.content,
                    content_hash=new_hash,
                ))
                continue

            # ── Fuzzy match: same type, high similarity → MODIFIED ──
            best_match = None
            best_score = 0.0
            normalized_new = _normalize_content(content)
            for candidate in prior_by_type.get(atom_type, []):
                if candidate.id in matched_prior_ids:
                    continue
                score = _levenshtein_similarity(
                    normalized_new,
                    _normalize_content(candidate.content)
                )
                if score > best_score:
                    best_score = score
                    best_match = candidate

            if best_match and best_score >= self.FUZZY_MATCH_THRESHOLD:
                matched_prior_ids.add(best_match.id)
                diff.modified.append(AtomDelta(
                    new_atom_content=content,
                    new_atom_type=atom_type,
                    status="modified",
                    previous_atom_id=best_match.id,
                    previous_content=best_match.content,
                    content_hash=new_hash,
                ))
            else:
                # ── No match → ADDED ──
                diff.added.append(AtomDelta(
                    new_atom_content=content,
                    new_atom_type=atom_type,
                    status="added",
                    content_hash=new_hash,
                ))

        # Prior atoms not matched by any new atom → DELETED
        for atom in prior_atoms:
            if atom.id not in matched_prior_ids:
                diff.deleted_atom_ids.append(atom.id)

        logger.info(
            f"[P5B-01] Diff for doc {document_id}: "
            f"+{len(diff.added)} added, ~{len(diff.modified)} modified, "
            f"={len(diff.unchanged)} unchanged, -{len(diff.deleted_atom_ids)} deleted"
        )

        # GAP-P4-07: Decay BOE confidence for concepts whose atoms changed/deleted.
        # Forces the validation engine to re-verify them via Gemini instead of
        # blindly auto-approving stale high-confidence mappings.
        if diff.modified or diff.deleted_atom_ids:
            try:
                from app.services.boe_context import BOEContext
                affected_names = [d.new_atom_content[:60] for d in diff.modified]
                # Fetch content of deleted atoms for their concept names
                for atom in prior_atoms:
                    if atom.id in set(diff.deleted_atom_ids):
                        affected_names.append(atom.content[:60])
                BOEContext.apply_staleness_decay(
                    db=db,
                    tenant_id=tenant_id,
                    affected_concept_names=affected_names,
                )
            except Exception as decay_err:
                logger.warning(f"[GAP-P4-07] Decay hook failed (non-fatal): {decay_err}")

        return diff


# Singleton
atom_diff_service = AtomDiffService()
