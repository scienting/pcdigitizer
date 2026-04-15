from pcdigitizer.data import Annotation, AnnotationProcessor, DissociationConstantData

ANNOTATION_REGISTRY: dict[Annotation, type[AnnotationProcessor]] = {
    Annotation.DISSOCIATION_CONSTANTS: DissociationConstantData,
}
"""Maps PubChem annotation strings to their processor class."""


def get_processor(annotation: Annotation) -> type[AnnotationProcessor]:
    """Look up the processor for an annotation, or raise an error."""
    try:
        return ANNOTATION_REGISTRY[annotation]
    except KeyError:
        supported = ", ".join(sorted(h.value for h in ANNOTATION_REGISTRY))
        raise ValueError(
            f"No processor registered for '{annotation}'. "
            f"Supported annotations: {supported}"
        )
