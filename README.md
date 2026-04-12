<h1 align="center">pcdigitizer</h1>

<h4 align="center">Turn raw PubChem data into clean, ML-ready chemical datasets</h4>

`pcdigitizer` is a Python toolkit for building ML-ready chemical datasets from [PubChem](https://pubchem.ncbi.nlm.nih.gov/).
It handles the full pipeline: downloading raw data through PubChem's [PUG-REST API](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest), parsing nested and inconsistent response formats, and cleaning the results into structured [Polars](https://pola.rs/) DataFrames ready for analysis or model training.

PubChem is the largest open chemical database in the world, but its data comes from thousands of depositors with varying formats, conventions, and quality levels.
Turning that into something you can feed to a machine learning model takes substantial data engineering.
`pcdigitizer` does that work for you.

> [!CAUTION]
> `pcdigitizer` is under active development and not yet ready for production use.
> APIs, data formats, and cleaning methodology may change without notice.

## Installation

Install directly from GitHub:

```bash
pip install git+https://github.com/scienting/pcdigitizer.git
```

Or clone and install locally:

```bash
git clone git@github.com:scienting/pcdigitizer.git
cd pcdigitizer
pip install .
```

## Quick start

`pcdigitizer` can also download and parse specific annotation headings into structured polars DataFrames.
Use the `Annotation` enum to select a supported annotation and `GetAnnotationPage` to fetch and process the first page of results.

```python
from pcdigitizer import Annotation, GetAnnotationPage

df = GetAnnotationPage().do(item=1, annotation=Annotation.DISSOCIATION_CONSTANTS)
```

This downloads the first page of dissociation constant data from PubChem, parses the free-text pKa strings, and returns a DataFrame with columns for `cid`, `sid`, `pka_value`, `temperature_C`, and more.
For example, here are the first five columns from the example above.

```text
shape: (5, 7)
┌──────┬─────┬───────────┬───────────┬───────────┬───────────────┬─────────────────────────────────┐
│ cid  ┆ sid ┆ pclid     ┆ pka_label ┆ pka_value ┆ temperature_C ┆ comment                         │
│ ---  ┆ --- ┆ ---       ┆ ---       ┆ ---       ┆ ---           ┆ ---                             │
│ i64  ┆ i64 ┆ i64       ┆ str       ┆ f64       ┆ f64           ┆ str                             │
╞══════╪═════╪═══════════╪═══════════╪═══════════╪═══════════════╪═════════════════════════════════╡
│ 2519 ┆ 36  ┆ 900032672 ┆ pKa       ┆ 14.0      ┆ 25.0          ┆ pKa = 14.0 at 25 °C             │
│ 2519 ┆ 36  ┆ 906276393 ┆ pKa       ┆ 10.4      ┆ 40.0          ┆ pKa = 10.4 at 40 °C (tertiary … │
│ 2519 ┆ 36  ┆ 900025588 ┆ pKa       ┆ 0.7       ┆ null          ┆ pKa = 0.7 (caffeine cation)     │
│ 176  ┆ 40  ┆ 900084372 ┆ pKa       ┆ 4.76      ┆ 25.0          ┆ pKa = 4.76 at 25 °C             │
│ 180  ┆ 41  ┆ 900027470 ┆ pKa       ┆ 20.0      ┆ null          ┆ pKa = 20                        │
└──────┴─────┴───────────┴───────────┴───────────┴───────────────┴─────────────────────────────────┘
```

`pcdigitizer` (will eventually) supports lookups across compounds, substances, assays, genes, proteins, pathways, taxonomies, cells, and annotations.
You can query by name, identifier, structure (SMILES, InChI, InChIKey), formula, or accession number depending on the domain.
See the [API documentation](https://scienting.github.io/pcdigitizer/) for the full reference.

## Development

We use [Pixi](https://pixi.sh/latest/) to manage environments and dependencies.
After installing [Pixi](https://pixi.sh/latest/), clone the repo and run:

```bash
pixi install
pixi shell -e dev
```

This gives you a fully configured environment with testing, linting, formatting, and build tools.
See the [development guide](https://scienting.github.io/pcdigitizer/development) for the complete walkthrough, including how to run tests, build the package, and publish releases.

## License

`pcdigitizer` is licensed under the [Prosperity Public License 3.0.0](https://github.com/scienting/pcdigitizer/blob/main/LICENSE.md).

**Noncommercial use is free.**
Academic researchers, university labs, nonprofits, and individual learners can use, modify, and distribute this software and any datasets it generates at no cost.
If you use `pcdigitizer` in published research, a citation is appreciated.

**Commercial use requires a paid license.**
The Prosperity Public License includes a 30-day trial period for commercial evaluation.
After that, for-profit companies using `pcdigitizer` or its outputs in commercial products, services, or internal operations need a commercial license.
This includes using the generated datasets in proprietary ML pipelines, commercial drug discovery workflows, or products built on the cleaned data.

Revenue from commercial licenses funds continued development, data validation, and maintenance of this project.
To purchase a commercial license, contact [us@scient.ing](mailto:us@scient.ing).
