"""Parsing and extraction utilities for PubChem dissociation constant data.

This module processes raw annotation entries from the PubChem PUG-View API
for the "Dissociation Constants" heading. Each entry contains one or more
free-text pKa strings deposited by data providers, which are highly
inconsistent in format. The parsing pipeline normalizes these strings into
structured records suitable for downstream analysis.

## Typical usage

Fetch data via [`PubChemAPI`][pcdigitizer.pubchem.PubChemAPI] and pass it
directly to
[`DissociationConstantData.from_page`][pcdigitizer.data.dissociation_constant.DissociationConstantData.from_page]

```python
from pcdigitizer import PubChemAPI, Annotation
from pcdigitizer.data import DissociationConstantData

raw = PubChemAPI.get_data(Annotation.DISSOCIATION_CONSTANTS)
df = DissociationConstantData.from_page(raw)
```
"""

import re
from typing import Iterable, TypedDict

import polars as pl
from loguru import logger

from pcdigitizer.data import AnnotationProcessor
from pcdigitizer.responses import AnnotationEntry, PubChemDatum


class ParsedPKa(TypedDict):
    """A single parsed pKa value extracted from a free-text string."""

    pka_label: str | None
    """The label identifying which ionization site this value belongs to
    (e.g. `"pKa1"`, `"pK2"`). `None` when the source text does not include a label.
    """

    pka_value: float
    """The numeric pKa value."""

    temperature_C: float | None
    """
    The temperature in degrees Celsius at which the measurement was made, if stated.
    `None` when not specified.
    """

    comment: str | None
    """
    The original source line with commas replaced by semicolons,
    retained for provenance. `None` for multi-value sentence parses.
    """


class FlatPKaRecord(TypedDict):
    """
    A fully resolved pKa record with compound and source identifiers.
    """

    cid: int
    """PubChem Compound Identifier."""

    sid: int
    """PubChem Substance Identifier for the depositing source record."""

    pclid: int | None
    """
    PubChem Live Data Identifier linking to the specific measurement record,
    if available.
    """

    pka_label: str | None
    """See [`ParsedPKa`][pcdigitizer.data.dissociation_constant.ParsedPKa.pka_label]."""

    pka_value: float
    """See [`ParsedPKa`][pcdigitizer.data.dissociation_constant.ParsedPKa.pka_value]."""

    temperature_C: float | None
    """See [`ParsedPKa`][pcdigitizer.data.dissociation_constant.ParsedPKa.temperature_C]."""

    comment: str | None
    """See [`ParsedPKa`][pcdigitizer.data.dissociation_constant.ParsedPKa.comment]."""


_OUTPUT_SCHEMA: dict[str, type[pl.DataType]] = {
    "cid": pl.Int64,
    "sid": pl.Int64,
    "pclid": pl.Int64,
    "pka_label": pl.String,
    "pka_value": pl.Float64,
    "temperature_C": pl.Float64,
    "comment": pl.String,
}
"""Expected output schema (used to return an empty DataFrame safely)"""


class DissociationConstantData(AnnotationProcessor):
    """Parse and assemble PubChem dissociation constant annotation data.

    All methods are static or class methods. The primary public interface is
    [`from_page`][pcdigitizer.data.dissociation_constant.DissociationConstantData.from_page],
    which converts a raw list of PubChem annotation
    entries into a tidy polars DataFrame.

    The parsing pipeline for free-text pKa strings is the following.

    1. [`parse_value`][pcdigitizer.data.dissociation_constant.DissociationConstantData.parse_value]
        is the top-level dispatcher. It first checks for
        the "pKa values are X, Y, and Z" sentence form via
        [`_parse_multi_value_sentence`][pcdigitizer.data.dissociation_constant.DissociationConstantData._parse_multi_value_sentence].
        If that does not match it splits the input on semicolons and delegates each
        segment to
        [`_parse_part`][pcdigitizer.data.dissociation_constant.DissociationConstantData._parse_part].

    2. [`_parse_part`][pcdigitizer.data.dissociation_constant.DissociationConstantData._parse_part]
        tries each compiled pattern in
        [`_PATTERNS`][pcdigitizer.data.dissociation_constant.DissociationConstantData._PATTERNS]
        in priority order via
        [`_try_patterns`][pcdigitizer.data.dissociation_constant.DissociationConstantData._try_patterns],
        returning the first successful
        [`ParsedPKa`][pcdigitizer.data.dissociation_constant.ParsedPKa] or `None`.

    3. Patterns are compiled once at class definition time and reused across all calls.

    The following free-text forms are recognized (case-insensitive):

    - `pKa values are 3.25, 4.76, and 6.17`  (multi-value sentence)
    - `pKa3 = -2.03`
    - `pK1 = 2.36 (SRC: carboxylic acid)`
    - `pKa = 10.4 at 40 °C (tertiary amine)`
    - `Weak acid. pK (25 °C): 3.35`
    - `pKa = 0.7 (caffeine cation)`
    - `pKa = 20`

    Lines that cannot be matched (e.g. density or solubility values
    mistakenly deposited under this heading) are logged at WARNING level
    and excluded from the output.
    """

    _PATTERN_LABELED: re.Pattern[str] = re.compile(
        r"""
        ^\s*
        (?P<label>pK(?:a)?\d*)  # pK, pKa, pK1, pKa2, etc.
        \s*(?:=|:)\s*
        (?P<value>-?[\d.]+)  # numeric value, allow negative
        (?:\s*\(SRC:\s*(?P<comment>[^)]+)\))?  # optional (SRC: ...)
        (?:\s+at\s+(?P<temp>[\d.]+)\s*°?C)?  # optional "at XX °C"
        """,
        re.IGNORECASE | re.VERBOSE,
    )
    """
    Labeled pKa with optional SRC comment and optional temperature.
    Matches:

    - `pKa3 = -2.03, pK1 = 2.36 (SRC: carboxylic acid), pKa = 10.4 at 40 °C`
    """

    _PATTERN_TEMP_PREFIX: re.Pattern[str] = re.compile(
        r"""
        (?P<label>pK(?:a)?)  # pK or pKa
        \s*
        (?:\(\s*(?P<temp>[\d.]+)\s*°?C\))?  # optional (25 °C)
        \s*[:=]\s*
        (?P<value>-?[\d.]+)  # numeric value
        """,
        re.IGNORECASE | re.VERBOSE,
    )
    """
    temperature-prefix form.
    Matches:

    - `Weak acid. pK (25 °C): 3.35, pK (25 °C) = 4.5`
    """

    # Pattern 3: fallback for bare numeric values in an environment context.
    # Matches: 4.24 in water, -1.34
    # Only used when a label group is present from one of the above patterns;
    # this pattern has no label group intentionally, so bare numbers without
    # any pK context are always rejected (see _parse_part for the label guard).
    _PATTERN_FALLBACK: re.Pattern[str] = re.compile(
        r"""
        ^\s*
        (?P<value>-?[\d.]+)
        (?:\s+in\s+(?P<env>.+))?        # optional "in water / solvent" context
        """,
        re.IGNORECASE | re.VERBOSE,
    )
    """
    Fallback for bare numeric values in an environment context.
    Matches:

    - `4.24 in water, -1.34`

    Only used when a label group is present from one of the above patterns;
    this pattern has no label group intentionally, so bare numbers without
    any pK context are always rejected (see
    [`_parse_part`][pcdigitizer.data.dissociation_constant.DissociationConstantData._parse_part]
    for the label guard).
    """

    _PATTERNS: list[re.Pattern[str]] = [
        _PATTERN_LABELED,
        _PATTERN_TEMP_PREFIX,
        _PATTERN_FALLBACK,
    ]
    """Ordered list used by _try_patterns; higher-specificity patterns first."""

    _PATTERN_MULTI_VALUE: re.Pattern[str] = re.compile(
        r"pKa values are\s+([\d\.,\sand-]+)",
        re.IGNORECASE,
    )
    """Pre-compiled pattern for the multi-value sentence form."""

    @classmethod
    def _parse_multi_value_sentence(cls, line: str) -> list[ParsedPKa] | None:
        """Attempt to parse the "pKa values are X, Y, and Z" sentence form.

        This form lists multiple unlabeled pKa values in a single prose
        sentence. When matched, individual values are extracted and returned
        without temperature or label information.

        Args:
            line: The raw input string to test.

        Returns:
            A list of [`ParsedPKa`][pcdigitizer.data.dissociation_constant.ParsedPKa] records,
                one per numeric value found in the sentence, or `None` if this
                sentence form is not present in `line`.
        """
        match = cls._PATTERN_MULTI_VALUE.search(line)
        if match is None:
            return None

        nums = re.findall(r"-?[\d.]+", match.group(1))
        return [
            ParsedPKa(
                pka_label=None,
                pka_value=float(val),
                temperature_C=None,
                comment=None,
            )
            for val in nums
        ]

    @classmethod
    def _try_patterns(cls, part: str, original_line: str) -> ParsedPKa | None:
        """Try each compiled pattern against a single text segment.

        Patterns are attempted in priority order. A match is only accepted
        when it captures a non-empty label group, which filters out numeric
        strings that are not actually pKa values (e.g. density or solubility
        values deposited under the wrong heading).

        Args:
            part: A single semicolon-split segment of the original input,
                with leading/trailing whitespace and quotes stripped.
            original_line: The full original input line, retained verbatim
                for the `comment` field (with commas replaced by
                semicolons).

        Returns:
            A [`ParsedPKa`][pcdigitizer.data.dissociation_constant.ParsedPKa] record if a pattern
                matches and a label is present, or `None` if no pattern yields
                a valid match.
        """
        for pattern in cls._PATTERNS:
            match = pattern.search(part)
            if match is None:
                continue

            groups = match.groupdict()
            label: str | None = groups.get("label") or None
            # Reject matches that did not capture a label: these are almost
            # always non-pKa numeric values (densities, concentrations, etc.)
            # that happen to match the loose fallback pattern.
            # See known false-positive examples:
            #   CID 13343: "2.02 g/cu cm at 20 °C"
            #   CID  2256: "1.1X10-4 at 25 °C"
            #   CID  6101: "-1.34"
            if label is None:
                continue

            temp_str: str | None = groups.get("temp")
            temperature: float | None = (
                float(temp_str) if temp_str is not None else None
            )

            return ParsedPKa(
                pka_label=label,
                pka_value=float(match.group("value")),
                temperature_C=temperature,
                comment=original_line.replace(",", ";"),
            )

        return None

    @classmethod
    def _parse_part(cls, part: str, original_line: str) -> ParsedPKa | None:
        """Parse a single semicolon-split segment of a pKa string.

        Delegates to
        [`_try_patterns`][pcdigitizer.data.dissociation_constant.DissociationConstantData._try_patterns]
        and logs a warning when no pattern matches, so that
        [`parse_value`][pcdigitizer.data.dissociation_constant.DissociationConstantData.parse_value]
        stays free of logging concerns.

        Args:
            part: A single segment, already stripped of leading/trailing
                whitespace and surrounding quotes.
            original_line: The full original input line, passed through to
                [`_try_patterns`][pcdigitizer.data.dissociation_constant.DissociationConstantData._try_patterns]
                for provenance.

        Returns:
            A [`ParsedPKa`][pcdigitizer.data.dissociation_constant.ParsedPKa] record, or
                `None` if the segment could not be matched to any known pKa format.
        """
        result = cls._try_patterns(part, original_line)
        if result is None:
            logger.warning("Failed to parse segment: '{}'", part)
        return result

    @staticmethod
    def _extract_ids(
        entry: AnnotationEntry,
    ) -> tuple[int, int] | None:
        """Extract the CID and SID from a PubChem annotation entry.

        Both identifiers must be present for the entry to be usable. If
        either is missing the entry is malformed and should be skipped.

        Args:
            entry: A single annotation entry dict as returned by the
                PUG-View API.

        Returns:
            A `(cid, sid)` tuple of integers, or `None` if either key
                is absent or the `CID` list is empty.
        """
        try:
            cid = int(entry["LinkedRecords"]["CID"][0])
            sid = int(entry["SourceID"])
            return cid, sid
        except (KeyError, IndexError, ValueError):
            return None

    @staticmethod
    def _extract_pclid(datum: PubChemDatum) -> int | None:
        """Extract the PCLID from a single datum's ExtendedReference.

        The PCLID (PubChem Live Data Identifier) links a specific measurement
        to its source record. It is optional: not all depositors provide it.

        Args:
            datum: A single data point dict from a PubChem annotation entry.

        Returns:
            The integer PCLID if present, or `None` if the key path does
                not exist.
        """
        try:
            return int(datum["ExtendedReference"][0]["Matched"]["PCLID"])
        except (KeyError, IndexError, TypeError, ValueError):
            return None

    @staticmethod
    def _extract_string_value(datum: PubChemDatum) -> str | None:
        """Extract the raw pKa string from a datum's Value field.

        Args:
            datum: A single data point dict from a PubChem annotation entry.

        Returns:
            The raw string value if present, or `None` if the expected
                key path does not exist or is empty.
        """
        try:
            return datum["Value"]["StringWithMarkup"][0]["String"]
        except (KeyError, IndexError, TypeError):
            return None

    @classmethod
    def parse_value(cls, line: str) -> list[ParsedPKa]:
        """Parse a free-text pKa string into a list of structured records.

        The input may contain one or more pKa values separated by
        semicolons, or a prose sentence listing multiple values. Each
        recognized value is returned as a
        [`ParsedPKa`][pcdigitizer.data.dissociation_constant.ParsedPKa]
        record. Segments that cannot be matched to any known format are logged at
        WARNING level and excluded from the output.

        Args:
            line: A raw pKa string as deposited in PubChem, for example:

                - `"pKa = 10.4 at 40 °C (tertiary amine)"`
                - `"pKa1 = 3.25; pKa2 = 4.76"`
                - `"pKa values are 3.25, 4.76, and 6.17"`
                - `"Weak acid. pK (25 °C): 3.35"`
                - `"pKa = 0.7 (caffeine cation)"`
                - `"pKa = 20"`

        Returns:
            A list of [`ParsedPKa`][pcdigitizer.data.dissociation_constant.ParsedPKa] records,
                one per recognized pKa value. Returns an empty list if no values
                could be parsed.
        """
        # Fast path: "pKa values are X, Y, and Z" prose sentence.
        multi = cls._parse_multi_value_sentence(line)
        if multi is not None:
            return multi

        # General path: split on semicolons, parse each segment.
        parts = [p.strip().strip("'\"") for p in line.split(";") if p.strip()]
        results: list[ParsedPKa] = []
        for part in parts:
            record = cls._parse_part(part, line)
            if record is not None:
                results.append(record)
        return results

    @classmethod
    def from_page(cls, annotation_data: list[AnnotationEntry]) -> pl.DataFrame:
        """Convert a list of PubChem annotation entries into a tidy DataFrame.

        Each entry in `annotation_data` corresponds to a single depositor
        record for one compound. This method extracts the compound and
        source identifiers, then parses every free-text pKa string within
        the entry into structured :class:`FlatPKaRecord` rows.

        Entries with missing CID or SID are skipped with a WARNING log.
        Individual data points whose string value cannot be extracted or
        parsed are skipped with a WARNING log. Broad exception types are
        never swallowed: only specific, expected failure modes are handled.

        Args:
            annotation_data: A list of annotation entry dicts as returned by
                [`get_data`][pcdigitizer.pubchem.PubChemAPI.get_data] for
                the `"Dissociation Constants"` heading. Each entry is
                expected to conform to [`AnnotationEntry`][pcdigitizer.responses.AnnotationEntry].

        Returns:
            A polars DataFrame with one row per parsed pKa value
                and the following columns:

                - `cid` (Int64): PubChem Compound Identifier.
                - `sid` (Int64): PubChem Substance Identifier.
                - `pclid` (Int64, nullable): PubChem Live Data Identifier.
                - `pka_label` (String, nullable): Ionisation-site label.
                - `pka_value` (Float64): The numeric pKa value.
                - `temperature_C` (Float64, nullable): Measurement temperature.
                - `comment` (String, nullable): Original source line.

                Returns an empty DataFrame with the above schema when no valid
                rows could be extracted from `annotation_data`.

        Raises:
            TypeError: If `annotation_data` is not a list.
        """
        rows: Iterable[FlatPKaRecord] = []

        for entry in annotation_data:
            logger.debug("Processing entry: {}", entry)

            ids = cls._extract_ids(entry)
            if ids is None:
                logger.warning(
                    "Skipping entry: could not extract CID and/or SID. Entry: {}",
                    entry,
                )
                continue
            cid, sid = ids
            logger.debug("Identified CID {} from SID {}", cid, sid)

            for datum in entry.get("Data", []):
                pclid = cls._extract_pclid(datum)

                raw_string = cls._extract_string_value(datum)
                if raw_string is None:
                    logger.warning(
                        "Skipping datum for CID {}: could not extract string value. "
                        "Datum: {}",
                        cid,
                        datum,
                    )
                    continue

                try:
                    parsed_values = cls.parse_value(raw_string)
                except (ValueError, re.error) as exc:
                    logger.warning(
                        "Skipping datum for CID {}: parse_value raised {}: {}. "
                        "Raw string: '{}'",
                        cid,
                        type(exc).__name__,
                        exc,
                        raw_string,
                    )
                    continue

                for pka in parsed_values:
                    rows.append(
                        FlatPKaRecord(
                            cid=cid,
                            sid=sid,
                            pclid=pclid,
                            pka_label=pka["pka_label"],
                            pka_value=pka["pka_value"],
                            temperature_C=pka["temperature_C"],
                            comment=pka["comment"],
                        )
                    )

        if not rows:
            return pl.DataFrame(schema=_OUTPUT_SCHEMA)

        return pl.from_dicts(rows)
