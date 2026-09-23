import logging
from typing import List, Dict, Tuple

from services.llm_service import (
    MeetingIntelligence,
    Participant,
    ActionItem,
    CHUNK_PROMPT,
    MERGE_PROMPT,
    split_transcript,
    call_structured_llm
)

logger = logging.getLogger(__name__)

def find_matching_canonical_name(name: str, existing_names: List[str]) -> Tuple[str, str]:
    """
    Finds if a name matches an existing participant name (e.g., 'Ravi' and 'Ravi Kumar').
    Returns (canonical_name, matched_existing_name_or_empty).
    """
    clean = " ".join(name.split()).strip()
    if not clean or clean.lower() == "unknown":
        return "Unknown", ""

    clean_lower = clean.lower()
    for existing in existing_names:
        existing_lower = existing.lower()
        if clean_lower == existing_lower:
            return existing, existing

        clean_parts = clean_lower.split()
        existing_parts = existing_lower.split()

        # e.g., 'Ravi' vs 'Ravi Kumar'
        if len(clean_parts) == 1 and len(existing_parts) > 1 and clean_parts[0] == existing_parts[0]:
            return existing, existing  # Keep the longer existing name
        if len(existing_parts) == 1 and len(clean_parts) > 1 and clean_parts[0] == existing_parts[0]:
            return clean, existing     # Upgrade existing short name to the fuller name

    return clean, ""

def canonicalize_participant_name(name: str, existing_names: List[str]) -> str:
    """Helper that returns the canonical name for a given input name."""
    canon, _ = find_matching_canonical_name(name, existing_names)
    return canon

def normalize_intelligence(data: MeetingIntelligence) -> MeetingIntelligence:
    """
    Performs data cleaning, participant deduplication, responsibility aggregation,
    and cross-linking of action items to canonical participants.
    """
    # 1. Deduplicate and canonicalize participants
    participants_map: Dict[str, Participant] = {}
    known_names: List[str] = []

    for p in data.participants:
        canon_name, matched_old = find_matching_canonical_name(p.name, known_names)

        # If we upgraded an existing shorter name (e.g. 'Ravi' -> 'Ravi Kumar')
        if matched_old and matched_old != canon_name and matched_old in participants_map:
            old_p = participants_map.pop(matched_old)
            known_names.remove(matched_old)
            known_names.append(canon_name)
            participants_map[canon_name] = Participant(
                name=canon_name,
                responsibilities=list(dict.fromkeys(old_p.responsibilities + p.responsibilities))
            )
        else:
            if canon_name not in known_names:
                known_names.append(canon_name)
            if canon_name not in participants_map:
                participants_map[canon_name] = Participant(name=canon_name, responsibilities=[])

            for r in p.responsibilities:
                r_clean = r.strip()
                if r_clean and r_clean not in participants_map[canon_name].responsibilities:
                    participants_map[canon_name].responsibilities.append(r_clean)

    # 2. Canonicalize action items assignees
    normalized_action_items: List[ActionItem] = []
    for item in data.action_items:
        raw_assignee = item.assigned_to.strip()
        canon_assignee, matched_old = find_matching_canonical_name(raw_assignee, known_names)

        if canon_assignee not in known_names and canon_assignee != "Unknown":
            known_names.append(canon_assignee)
            participants_map[canon_assignee] = Participant(name=canon_assignee, responsibilities=[item.task])
        elif canon_assignee in participants_map and item.task not in participants_map[canon_assignee].responsibilities:
            participants_map[canon_assignee].responsibilities.append(item.task)

        item.assigned_to = canon_assignee if canon_assignee else "Unknown"
        normalized_action_items.append(item)

    # 3. Deduplicate string lists preserving order
    clean_key_points = list(dict.fromkeys(p.strip() for p in data.key_points if p.strip()))
    clean_decisions = list(dict.fromkeys(d.strip() for d in data.decisions if d.strip()))
    clean_deadlines = list(dict.fromkeys(d.strip() for d in data.deadlines if d.strip()))
    clean_priorities = list(dict.fromkeys(p.strip() for p in data.priorities if p.strip()))

    return MeetingIntelligence(
        summary=data.summary.strip(),
        key_points=clean_key_points,
        decisions=clean_decisions,
        action_items=normalized_action_items,
        participants=list(participants_map.values()),
        deadlines=clean_deadlines,
        priorities=clean_priorities
    )

def process_transcript_intelligence(transcript: str) -> MeetingIntelligence:
    """
    Main orchestration service for Milestone 2:
    Takes raw transcript -> handles chunking (if long) -> runs LLM extraction -> normalizes intelligence.
    """
    chunks = split_transcript(transcript)
    logger.info("Transcript length: %d chars, split into %d chunk(s).", len(transcript), len(chunks))

    if len(chunks) == 1:
        raw_intelligence = call_structured_llm(CHUNK_PROMPT.format(transcript=chunks[0]))
        return normalize_intelligence(raw_intelligence)

    chunk_analyses: List[str] = []
    for idx, chunk in enumerate(chunks, 1):
        logger.info("Processing transcript chunk %d/%d...", idx, len(chunks))
        partial_intel = call_structured_llm(CHUNK_PROMPT.format(transcript=chunk))
        chunk_analyses.append(f"--- Chunk {idx} ---\n{partial_intel.model_dump_json(indent=2)}")

    logger.info("Merging %d chunk analyses with LLM merge prompt...", len(chunk_analyses))
    merged_intelligence = call_structured_llm(MERGE_PROMPT.format(analyses="\n\n".join(chunk_analyses)))
    return normalize_intelligence(merged_intelligence)