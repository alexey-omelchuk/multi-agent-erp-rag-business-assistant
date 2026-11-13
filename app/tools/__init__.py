"""Herramientas (tools) que los agentes pueden llamar.

Cada tool es una funcion fina: recibe argumentos sencillos, pide los datos a
app/data_sources y devuelve un resultado compacto. Lo que el modelo lee para
decidir cuando usarla es su nombre y su docstring.
"""
