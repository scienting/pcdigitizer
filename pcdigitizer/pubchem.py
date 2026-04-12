import json
import re
from collections import defaultdict
from urllib.parse import quote, urlencode, urljoin, urlparse

import polars as pl
import requests
from loguru import logger

from pcdigitizer.data import Annotation
from pcdigitizer.responses import (
    AnnotationEntry,
    AnnotationsEnvelope,
    InformationListEnvelope,
)


class PubChemAPI:
    """Client for the PubChem PUG-REST and PUG-View APIs.

    All methods are class methods or static methods; no instance state is
    required. Network access is centralized in
    [`make_request`][pubchem.PubChemAPI.make_request] so that it can
    be replaced with a mock session during testing.
    """

    BASE_URL: str = "https://pubchem.ncbi.nlm.nih.gov/rest/"

    ALLOWED_NAMESPACES: dict[str, set[str]] = {
        "compound": {
            "cid",
            "name",
            "smiles",
            "inchi",
            "inchikey",
            "formula",
            "listkey",
        },
        "substance": {"sid", "sourceid", "sourceall", "name", "xref", "listkey"},
        "assay": {"aid", "listkey", "type", "sourceall", "target", "activity"},
        "gene": {"geneid", "genesymbol", "synonym"},
        "protein": {"accession", "gi", "synonym"},
        "pathway": {"pwacc"},
        "taxonomy": {"taxid", "synonym"},
        "cell": {"cellacc", "synonym"},
        "annotations": {"sourcename", "headings", "heading"},
    }

    _IDENTIFIER_PATTERN: re.Pattern[str] = re.compile(r"^[\w,\.\- ]+$")
    _VALID_PUG_ENDPOINTS: frozenset[str] = frozenset(("pug", "pug_view", "pug_soap"))

    @staticmethod
    def make_request(url: str, session: requests.Session | None = None) -> bytes:
        """Perform an HTTP GET and return the raw response body.

        Args:
            url: The fully constructed PubChem REST URL to fetch.
            session: An optional [`Session`][requests.Session] to use for the
                request. When `None` the module-level `requests.get`
                function is used. Pass a session (or a mock) during testing
                to avoid live network calls.

        Returns:
            The raw response body.

        Raises:
            RuntimeError: If the server returns a non-200 HTTP status code.
        """
        get = session.get if session is not None else requests.get
        response = get(url)
        if response.status_code == 200:
            logger.debug("Successful response for {}", url)
            return response.content
        raise RuntimeError(f"Request failed ({response.status_code}) for {url}")

    @classmethod
    def make_json(
        cls, url: str, session: requests.Session | None = None
    ) -> dict[str, object]:
        """Fetch a URL and parse the response body as JSON.

        Args:
            url: The fully constructed PubChem REST URL to fetch.
            session: An optional [`Session`][requests.Session] forwarded to
                [`make_request`][pubchem.PubChemAPI.make_request].
                See that method for details.

        Returns:
            The top-level JSON object as a plain `dict`.

        Raises:
            RuntimeError: If the HTTP request fails (propagated from
                [`make_request`][pubchem.PubChemAPI.make_request]).
            json.JSONDecodeError: If the response body is not valid JSON.
        """
        text = cls.make_request(url, session=session)
        return json.loads(text)

    @classmethod
    def _validate_url(cls, url: str) -> None:
        """Verify that a URL is a safe, well-formed PubChem PUG endpoint.

        Args:
            url: The URL string to validate.

        Raises:
            ValueError: If the URL does not use HTTPS, does not point to
                `pubchem.ncbi.nlm.nih.gov`, or whose path does not start
                with `/rest/pug`.
        """
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise ValueError(f"URL must use HTTPS; got scheme '{parsed.scheme}'.")
        if parsed.netloc != "pubchem.ncbi.nlm.nih.gov":
            raise ValueError(
                f"URL must point to pubchem.ncbi.nlm.nih.gov; got '{parsed.netloc}'."
            )
        if not parsed.path.startswith("/rest/pug"):
            raise ValueError(
                f"URL path must start with /rest/pug; got '{parsed.path}'."
            )

    @classmethod
    def _validate_components(
        cls, domain: str, namespace: str, identifiers: str
    ) -> None:
        """Validate the domain, namespace key, and identifier string.

        The namespace may contain a `/` separator (e.g. `sourcename/ChEBI`);
        only the portion before the first `/` is checked against the allowed
        set for the given domain.

        Args:
            domain: The PubChem domain (e.g. `"compound"`, `"annotations"`).
            namespace: The namespace string, optionally including a `/`-separated
                value (e.g. `"sourcename/ChEBI"`).
            identifiers: The identifier string to look up. May be empty only
                for the `"annotations"` domain.

        Raises:
            ValueError: If `domain` is not in
                [`ALLOWED_NAMESPACES`][pubchem.PubChemAPI.ALLOWED_NAMESPACES].
            ValueError: If the namespace key is not valid for the given domain.
            ValueError: If `identifiers` is empty for a domain that requires it.
            ValueError: If `identifiers` contains characters outside the
                allowed set `[A-Za-z0-9_,.-_ ]`.
        """
        if domain not in cls.ALLOWED_NAMESPACES:
            raise ValueError(
                f"Domain '{domain}' is not supported. "
                f"Choose from: {sorted(cls.ALLOWED_NAMESPACES)}."
            )

        key = namespace.split("/", 1)[0]
        if key not in cls.ALLOWED_NAMESPACES[domain]:
            raise ValueError(
                f"Namespace '{key}' is not valid for domain '{domain}'. "
                f"Choose from: {sorted(cls.ALLOWED_NAMESPACES[domain])}."
            )

        if domain != "annotations" and not identifiers:
            raise ValueError(f"Identifiers cannot be empty for domain '{domain}'.")

        if identifiers and not cls._IDENTIFIER_PATTERN.match(identifiers):
            raise ValueError(
                f"Identifiers '{identifiers}' contain invalid characters. "
                "Only alphanumerics, commas, dots, hyphens, underscores, and "
                "spaces are permitted."
            )

    @classmethod
    def _encode_namespace(cls, namespace: str) -> tuple[str, str]:
        """Split and percent-encode a namespace string.

        A namespace may be a bare key (e.g. `"cid"`) or a key with a
        `/`-separated value (e.g. `"sourcename/ChEBI"`). Both segments
        are percent-encoded for safe inclusion in a URL path.

        Args:
            namespace: The namespace string to encode, with an optional
                `/`-separated value component.

        Returns:
            A two-tuple `(encoded_key, encoded_value)` where
                `encoded_value` is an empty string when no value component
                is present.
        """
        if "/" in namespace:
            key, val = namespace.split("/", 1)
        else:
            key, val = namespace, ""
        return quote(key, safe=""), quote(val, safe="") if val else ""

    @classmethod
    def _build_path(
        cls,
        domain: str,
        encoded_key: str,
        encoded_val: str,
        encoded_identifiers: str,
        operation: str | None,
        output_format: str,
    ) -> str:
        """Assemble the URL path segments into a single slash-joined string.

        Args:
            domain: The PubChem domain (e.g. `"compound"`).
            encoded_key: The percent-encoded namespace key.
            encoded_val: The percent-encoded namespace value, or an empty
                string when absent.
            encoded_identifiers: The percent-encoded identifier string, or
                an empty string when absent.
            operation: An optional operation string (e.g. `"property/MolecularWeight"`).
                Slashes within this string are preserved as path separators.
            output_format: The desired output format (e.g. `"JSON"`, `"CSV"`).

        Returns:
            A slash-joined path string ending with the output format segment,
                suitable for appending to a PUG base URL.
        """
        parts: list[str] = [domain, encoded_key]
        if encoded_val:
            parts.append(encoded_val)
        if encoded_identifiers:
            parts.append(encoded_identifiers)
        if operation:
            parts.extend(operation.split("/"))
        parts.append(output_format)
        return "/".join(parts)

    @classmethod
    def build_url(
        cls,
        domain: str,
        namespace: str,
        pug: str = "pug",
        identifiers: str = "",
        operation: str | None = None,
        output_format: str = "JSON",
        options: dict[str, str | int] | None = None,
    ) -> str:
        """Construct, validate, and return a fully formed PUG-REST URL.

        Args:
            domain: The PubChem domain to query (e.g. `"compound"`,
                `"annotations"`). Must be a key in
                [`ALLOWED_NAMESPACES`][pubchem.PubChemAPI.ALLOWED_NAMESPACES].
            namespace: The namespace within the domain, optionally with a
                `/`-separated value (e.g. `"name"`, `"sourcename/ChEBI"`).
            pug: The PUG endpoint variant to use. Must be one of `"pug"`,
                `"pug_view"`, or `"pug_soap"`. Defaults to `"pug"`.
            identifiers: The record identifier(s) to look up, as a
                comma-separated string. May be empty for the
                `"annotations"` domain only.
            operation: An optional operation to perform on the matched
                records (e.g. `"property/MolecularWeight"`). Slashes are
                treated as path separators.
            output_format: The response format requested from PubChem.
                Defaults to `"JSON"`.
            options: Optional query-string parameters appended to the URL
                (e.g. `{"page": 2}`).

        Returns:
            A fully constructed, validated HTTPS URL string ready to pass to
                [`make_request`][pubchem.PubChemAPI.make_request].

        Raises:
            ValueError: If `pug` is not a recognized endpoint variant.
            ValueError: If `domain`, `namespace`, or `identifiers` fail
                validation (propagated from
                [`_validate_components`][pubchem.PubChemAPI._validate_components]).
            ValueError: If the resulting URL fails the safety check
                (propagated from [`_validate_url`][pubchem.PubChemAPI._validate_url]).
        """
        if pug not in cls._VALID_PUG_ENDPOINTS:
            raise ValueError(
                f"Invalid PUG endpoint '{pug}'. "
                f"Choose from: {sorted(cls._VALID_PUG_ENDPOINTS)}."
            )

        cls._validate_components(domain, namespace, identifiers)

        encoded_key, encoded_val = cls._encode_namespace(namespace)
        encoded_identifiers = quote(identifiers, safe=",") if identifiers else ""

        path = cls._build_path(
            domain,
            encoded_key,
            encoded_val,
            encoded_identifiers,
            operation,
            output_format,
        )

        pug_base = pug if pug.endswith("/") else pug + "/"
        url = urljoin(cls.BASE_URL, pug_base)
        url = urljoin(url, path)

        if options:
            qs = urlencode(options, doseq=True, quote_via=quote)
            url = f"{url}?{qs}"

        cls._validate_url(url)
        return url

    @classmethod
    def get_sources(cls, session: requests.Session | None = None) -> pl.DataFrame:
        """Fetch the full PubChem depositor source table as a DataFrame.

        Retrieves the CSV source table from
        `/rest/pug/sourcetable/all/CSV`, which lists every organization
        that has deposited data into PubChem along with associated metadata.

        Args:
            session: An optional [`Session`][requests.Session] forwarded to
                [`make_request`][pubchem.PubChemAPI.make_request]. Pass a mock during
                testing to avoid live network calls.

        Returns:
            A `polars.DataFrame` with one row per depositor source.

        Raises:
            RuntimeError: If the HTTP request fails.
        """
        url = urljoin(cls.BASE_URL, "pug/sourcetable/all/CSV")
        raw = cls.make_request(url, session=session)
        return pl.read_csv(raw)

    @staticmethod
    def _process_annotations(
        raw_annotations: list[AnnotationEntry],
    ) -> dict[str, list[str]]:
        """Group annotation names by their type.

        Args:
            raw_annotations: A list of annotation records as returned by the
                PubChem API, each containing at minimum a `"Type"` key and
                a `"Heading"` key.

        Returns:
            A dict mapping each annotation type (e.g. `"Compound"`) to a
                list of heading names belonging to that type, in the order they
                were encountered.
        """
        grouped: dict[str, list[str]] = defaultdict(list)
        for entry in raw_annotations:
            grouped[entry["Type"]].append(entry["Heading"])
        return grouped

    @classmethod
    def get_source_annotations(
        cls,
        source_name: str,
        session: requests.Session | None = None,
    ) -> dict[str, list[str]]:
        """Fetch all annotation headings deposited by a specific source.

        Retrieves annotations from the `annotations/sourcename/<source>`
        endpoint and groups them by type via
        [`_process_annotations`][pubchem.PubChemAPI._process_annotations].

        Note:
            `output_format` is not exposed as a parameter here because
            [`make_json`][pubchem.PubChemAPI.make_json] always expects a JSON response.
            To retrieve raw non-JSON data from this endpoint, use
            [`build_url`][pubchem.PubChemAPI.build_url] and
            [`make_request`][pubchem.PubChemAPI.make_request] directly.

        Args:
            source_name: The PubChem depositor source name to query
                (e.g. `"ChEBI"`). Forward slashes are replaced with
                periods as required by the PubChem API.
            session: An optional [`Session`][requests.Session] forwarded to
                [`make_request`][pubchem.PubChemAPI.make_request]. Pass a mock during
                testing to avoid live network calls.

        Returns:
            A dict mapping annotation type strings (e.g. `"Compound"`) to
                lists of heading names provided by the given source.

        Raises:
            RuntimeError: If the HTTP request fails.
            KeyError: If the response does not contain the expected
                `InformationList.Annotation` structure.
        """
        safe_source = source_name.replace("/", ".")
        namespace = f"sourcename/{safe_source}"

        url = cls.build_url(
            domain="annotations",
            namespace=namespace,
            identifiers="",
            operation=None,
            output_format="JSON",
        )
        raw: InformationListEnvelope = cls.make_json(
            url, session=session
        )  # ty:ignore[invalid-assignment]
        raw_annotations: list[AnnotationEntry] = raw["InformationList"]["Annotation"]
        return cls._process_annotations(raw_annotations)

    @classmethod
    def get_annotations(
        cls, session: requests.Session | None = None
    ) -> dict[str, list[str]]:
        """Retrieve all annotation headings available in PubChem.

        Fetches and processes the results of
        `/rest/pug/annotations/headings/JSON`. The returned dict normally
        contains the following type keys: `Assay`, `Cell`, `Compound`,
        `Element`, `Gene`, `Pathway`, `Protein`, `Taxonomy`.

        Args:
            session: An optional [`Session`][requests.Session] forwarded to
                [`make_request`][pubchem.PubChemAPI.make_request]. Pass a mock during
                testing to avoid live network calls.

        Returns:
            A dict mapping annotation type strings to lists of heading names
                belonging to that type.

        Raises:
            RuntimeError: If the HTTP request fails.
            KeyError: If the response does not contain the expected
                `InformationList.Annotation` structure.
        """
        url = cls.build_url(
            domain="annotations",
            namespace="headings",
            identifiers="",
            operation=None,
            output_format="JSON",
        )
        raw: InformationListEnvelope = cls.make_json(
            url, session=session
        )  # ty:ignore[invalid-assignment]
        raw_annotations: list[AnnotationEntry] = raw["InformationList"]["Annotation"]
        return cls._process_annotations(raw_annotations)

    @classmethod
    def get_data(
        cls,
        annotation: Annotation,
        page: int | None = None,
        session: requests.Session | None = None,
    ) -> list[AnnotationEntry]:
        """Retrieve all records for a specific annotation.

        Fetches data from the PUG-View `annotations/heading/<heading>`
        endpoint. Without a `page` argument this returns every result,
        which can be slow for popular headings.

        Args:
            annotation: The PubChem annotation heading to download
                (e.g. `Annotation.DISSOCIATION_CONSTANTS`).
            page: If provided, fetch only this specific page of results.
                Must be a positive integer. If `None`, all results are
                returned.
            session: An optional [`Session`][requests.Session]Session` forwarded to
                [`make_request`][pubchem.PubChemAPI.make_request]. Pass a mock during
                testing to avoid live network calls.

        Returns:
            A list of [`AnnotationEntry`][responses.AnnotationEntry] dicts for the
                requested data, in the order returned by the API.

        Raises:
            ValueError: If `page` is provided but is less than 1.
            RuntimeError: If the HTTP request fails.
            KeyError: If the response does not contain the expected
                Annotations structure.
        """
        if page is not None and page < 1:
            raise ValueError(f"page must be a positive integer; got {page}.")

        options: dict[str, str | int] | None = (
            {"page": page} if page is not None else None
        )

        url = cls.build_url(
            pug="pug_view",
            domain="annotations",
            namespace="heading",
            identifiers=annotation,
            operation=None,
            output_format="JSON",
            options=options,
        )
        raw: AnnotationsEnvelope = cls.make_json(
            url, session=session
        )  # ty:ignore[invalid-assignment]
        return raw["Annotations"]["Annotation"]
