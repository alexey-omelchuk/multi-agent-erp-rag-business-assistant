"""RAG: indexar documentos PDF y buscar en ellos por significado.

    ingest.py      PDF -> paginas -> trozos -> vectores -> Chroma
    retrieval.py   pregunta -> vector -> trozos mas parecidos
    embeddings.py  el modelo que convierte texto en vectores
    store.py       la base vectorial (Chroma)
"""
