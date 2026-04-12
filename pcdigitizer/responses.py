"""`TypedDict` definitions for PubChem PUG-REST and PUG-View API responses.

This module provides a single source of truth for the JSON response shapes
returned by the PubChem REST APIs.

## Structure overview

PubChem responses follow two broad envelope shapes depending on the endpoint:

`InformationList` envelope (PUG-REST `/annotations/headings` and
`/annotations/sourcename`):

```json
{
"InformationList": {
    "Annotation": [ ... ]
    }
}
```

`Annotations` envelope (PUG-View `/annotations/heading`):

```json
{
    "Annotations": {
        "Annotation": [ ... ],
        "Page": 1,
        "TotalPages": 42
    }
}
```

Within both envelopes each `Annotation` element is an
[`AnnotationEntry`][pcdigitizer.responses.AnnotationEntry]. When the entry was fetched via
PUG-View (i.e. a specific heading), it additionally carries a `Data` list whose
elements are [`PubChemDatum`][pcdigitizer.responses.PubChemDatum] records containing the
deposited values.

## Hierarchy

The nesting from outermost to innermost is:

```text
InformationListEnvelope / AnnotationsEnvelope
    └── AnnotationEntry
        ├── LinkedRecords
        └── Data
                └── PubChemDatum
                    ├── DatumValue
                    │     └── StringWithMarkup
                    └── ExtendedReference
                            └── MatchedRecord
```

All classes use `total=False` where keys are optional in the real API
responses, and `total=True` (the default) where keys are always present.
"""

from typing import TypedDict


class MatchedRecord(TypedDict, total=False):
    """The `Matched` sub-object within an
    [`ExtendedReference`][pcdigitizer.responses.ExtendedReference] entry.

    Carries identifiers that link a specific deposited value to its
    corresponding record in PubChem's live data system.
    """

    PCLID: int
    """
    PubChem Live Data Identifier. Links the measurement to its canonical record.
    Not present for all depositors.
    """


class ExtendedReference(TypedDict, total=False):
    """A single element of the `ExtendedReference` list on a datum.

    Provides cross-references from a deposited data point to other PubChem
    record types. The `Matched` key is present only when PubChem has
    successfully linked the value to a live data record.
    """

    Matched: MatchedRecord
    """The matched record containing the PCLID, if available."""


class StringWithMarkup(TypedDict):
    """A single element of the `StringWithMarkup` list on a datum value.

    PubChem wraps all deposited string values in this container, which in
    the full API response can also carry markup annotations (bold, italic,
    subscript, etc.). Only the plain string is modelled here since markup
    is not used by this package.
    """

    String: str
    """The plain text content of the deposited value."""


class DatumValue(TypedDict, total=False):
    """The `Value` object on a single data point within an annotation.

    PubChem data points can carry several value types (numeric, boolean, binary).
    This class models only the [`StringWithMarkup`][pcdigitizer.responses.StringWithMarkup]
    variant, which is the form used for textual property data such as pKa strings.
    """

    StringWithMarkup: list[StringWithMarkup]
    """
    A list of string value containers. In practice this list contains exactly one
    element for property annotations.
    """


class PubChemDatum(TypedDict, total=False):
    """A single data point within a PubChem PUG-View annotation entry.

    Each [`AnnotationEntry`][pcdigitizer.responses.AnnotationEntry] fetched from a specific heading
    contains a `Data` list whose elements are `PubChemDatum` records. Each datum
    represents one deposited measurement or value from a single source.
    """

    Value: DatumValue
    """
    The deposited value, in [`StringWithMarkup`][pcdigitizer.responses.StringWithMarkup]
    form for textual properties.
    """

    ExtendedReference: list[ExtendedReference]
    """
    Cross-references linking this datum to other PubChem record types.
    Used to recover the PCLID when present.
    """


class LinkedRecords(TypedDict, total=False):
    """The `LinkedRecords` object on a PubChem annotation entry.

    Maps PubChem record type names to lists of integer identifiers for all
    records that are linked to this annotation entry. Additional record
    types beyond those listed here (e.g. `SID`, `AID`) may be present
    in real responses but are not modelled here.
    """

    CID: list[int]
    """
    List of PubChem Compound Identifiers linked to this entry. Typically contains
    exactly one element for compound annotations.
    """

    SID: list[int]
    """List of PubChem Substance Identifiers linked to this entry."""

    AID: list[int]
    """List of PubChem Assay Identifiers linked to this entry."""


class AnnotationEntry(TypedDict, total=False):
    """A single annotation record returned by the PubChem PUG-REST or
    PUG-View API.

    This type covers both the lightweight form returned by
    `/annotations/headings` (which carries only `Type` and `Heading`)
    and the full form returned by `/annotations/heading/<heading>` (which
    additionally carries `Data`, `LinkedRecords`, `SourceID`, etc.).

    Using `total=False` throughout reflects that the set of keys present
    varies significantly by endpoint and depositor.
    """

    SourceName: str
    """The human-readable name of the depositing organization."""

    SourceID: str
    """
    The depositor's own identifier for this record (e.g. a database accession
    number). Cast to `int` where a numeric ID is expected.
    """

    Name: str
    """The name of the compound or entity this annotation describes."""

    Description: list[str]
    """Free-text description lines provided by the depositor."""

    Reference: list[str]
    """Citation strings provided by the depositor."""

    ANID: int
    """
    PubChem Annotation Identifier, a unique integer assigned to this annotation record.
    """

    LinkedRecords: LinkedRecords
    """
    Identifiers linking this entry to PubChem compound, substance, and assay records.
    """

    Type: str
    """
    The broad category of this annotation heading (e.g. `"Compound"`,
    `"Gene"`, `"Assay"`).
    """

    Heading: str
    """
    The specific annotation heading name (e.g. `"Dissociation Constants"`,
    `"Boiling Point"`).
    """

    URL: str
    """A URL provided by the depositor pointing to the original source."""

    Data: list[PubChemDatum]
    """
    The list of individual deposited data points. Present only for entries fetched
    via a specific heading endpoint.
    """


class _InformationList(TypedDict, total=False):
    """The inner `InformationList` object in a PUG-REST response."""

    Annotation: list[AnnotationEntry]
    """The list of annotation records."""

    Page: int
    """The current page number when paginated results are returned."""

    TotalPages: int
    """The total number of available pages."""


class InformationListEnvelope(TypedDict):
    """Top-level envelope for PUG-REST responses that wrap an InformationList.

    Returned by endpoints such as:

    - `/rest/pug/annotations/headings/JSON`
    - `/rest/pug/annotations/sourcename/<source>/JSON`
    """

    InformationList: _InformationList
    """
    The inner object containing the annotation list and optional pagination metadata.
    """


class _AnnotationsList(TypedDict, total=False):
    """The inner `Annotations` object in a PUG-View response."""

    Annotation: list[AnnotationEntry]
    """The list of annotation records."""

    Page: int
    """The current page number when paginated results are returned."""

    TotalPages: int
    """The total number of available pages."""


class AnnotationsEnvelope(TypedDict):
    """Top-level envelope for PUG-View responses that wrap an Annotations list.

    Returned by endpoints such as:

    - `/rest/pug_view/annotations/heading/<heading>/JSON`
    """

    Annotations: _AnnotationsList
    """
    The inner object containing the annotation list and optional pagination metadata.
    """
