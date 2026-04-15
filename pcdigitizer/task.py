import polars as pl
from raygent import Task

from pcdigitizer import PubChemAPI
from pcdigitizer.data import Annotation, get_processor


class GetAnnotationPage(Task):
    """Get a page of annotated data from PubChem."""

    def do(self, item: int, annotation: Annotation, **kwargs) -> pl.DataFrame:
        """Download and process a single page of data from an annotation.

        Args:
            item: Which page to fetch from `annotation`.
            annotation: What data to fetch.

        Returns:
            Processed data in a polars DataFrame.
        """
        session = kwargs.get("session", None)
        processor = get_processor(annotation)

        annotation_data = PubChemAPI.get_data(annotation, item, session=session)
        df = processor.from_page(annotation_data)
        return df
