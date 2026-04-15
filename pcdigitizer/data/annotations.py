from enum import StrEnum
from typing import Protocol

import polars as pl

from pcdigitizer.responses import AnnotationEntry


class Annotation(StrEnum):
    """PubChem annotation headings supported by this package.

    Each member corresponds to a heading in the PubChem PUG-View
    `/annotations/heading/<heading>` endpoint and maps to a registered
    processor class that knows how to parse the raw API response for that
    heading into a tidy polars DataFrame.

    Because `Annotation` extends `StrEnum`, members can be passed
    directly to any function expecting a `str` (e.g.
    `PubChemAPI.get_data`) without accessing `.value`.

    To add support for a new heading, add a member here and register its
    processor in the heading registry.
    """

    DISSOCIATION_CONSTANTS = "Dissociation Constants"


class AnnotationProcessor(Protocol):
    """Interface that any annotation-specific data processor must satisfy."""

    @classmethod
    def from_page(cls, annotation_data: list[AnnotationEntry]) -> pl.DataFrame: ...
