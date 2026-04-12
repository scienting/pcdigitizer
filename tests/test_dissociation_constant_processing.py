import polars as pl

from pcdigitizer import Annotation, GetAnnotationPage


def test_process_dissociation_data(test_dir, mock_session):
    """Makes request for the first page of the `"Dissociation Constants"` and
    processes the data into a polars DataFrame.

    Makes the following request:
    [pubchem.ncbi.nlm.nih.gov/rest/pug_view/annotations/heading/Dissociation%20Constants/JSON?page=1](https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/annotations/heading/Dissociation%20Constants/JSON?page=1).
    """
    task = GetAnnotationPage()
    df = task.do(
        item=1, annotation=Annotation.DISSOCIATION_CONSTANTS, session=mock_session
    )

    # TODO: Need to implement actual tests
    assert not df.is_empty()
    assert df.columns == [
        "cid",
        "sid",
        "pclid",
        "pka_label",
        "pka_value",
        "temperature_C",
        "comment",
    ]
    assert df.schema["pka_value"] == pl.Float64
    assert df.schema["cid"] == pl.Int64

    csv_path = test_dir / "tmp" / "test_process_dissociation_data.csv"
    df.write_csv(csv_path)
