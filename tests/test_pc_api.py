import polars as pl

from pcdigitizer import Annotation, PubChemAPI


def test_source_df():
    df = PubChemAPI.get_sources()

    columns = df.columns
    assert len(columns) == 23
    assert columns[0] == "Source Name"
    assert columns[-3] == "License URL"

    source_name = "Hazardous Substances Data Bank"
    source_count = df.select(
        (pl.col("Source Name").str.contains(source_name)).sum()
    ).item()
    assert source_count == 1


def test_source_annotations():
    annotations = PubChemAPI.get_source_annotations(
        "Hazardous Substances Data Bank (HSDB)"
    )
    assert len(annotations["Compound"]) == 246


def test_annotations():
    annotations = PubChemAPI.get_annotations()
    annotation_types = sorted(annotations.keys())
    assert annotation_types == [
        "Assay",
        "Cell",
        "Compound",
        "Element",
        "Gene",
        "Pathway",
        "Protein",
        "Taxonomy",
    ]
    assert "Dissociation Constants" in annotations["Compound"]


def test_get_data(mock_session):
    data = PubChemAPI.get_data(
        Annotation.DISSOCIATION_CONSTANTS, 1, session=mock_session
    )
    assert len(data) == 1000
