"""
Capa comuna de lectura dels datasets de data/cache/.

read_dataset() no depèn de Streamlit: la poden fer servir el motor (data/sql),
l'API del xatbot o l'Observatori Catalunya. Les pàgines fan servir
load_dataset(), que és la mateixa funció amb @st.cache_data.

Si un dia les dades venen d'una API en lloc dels fitxers, el canvi es fa aquí
i cap pàgina no s'ha de tocar.
"""
import os

import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")


def dataset_path(name, ext="csv"):
    """Ruta de data/cache/{name}.{ext}."""
    return os.path.join(CACHE_DIR, f"{name}.{ext}")


def read_dataset(name, fmt="csv", dtype=None):
    """
    Llegeix data/cache/{name}.

    fmt: "csv", "parquet" o "auto" (parquet si existeix, si no CSV).
    dtype: tipus de columna per al CSV (p. ex. {"cnae": str}); el parquet ja
    els porta desats.
    Retorna un DataFrame buit si el fitxer no hi és.
    """
    if fmt in ("parquet", "auto"):
        pq = dataset_path(name, "parquet")
        if os.path.exists(pq):
            return pd.read_parquet(pq)
        if fmt == "parquet":
            return pd.DataFrame()
    csv = dataset_path(name, "csv")
    if os.path.exists(csv):
        return pd.read_csv(csv, dtype=dtype)
    return pd.DataFrame()


def signatura(name, fmt):
    """Mida i data dels fitxers candidats: entra a la clau de la cache perquè
    un fitxer nou (workflow diari) no esperi que caduqui el ttl."""
    sig = []
    for ext in ("parquet", "csv"):
        p = dataset_path(name, ext)
        if os.path.exists(p):
            sig.append((ext, os.path.getsize(p), int(os.path.getmtime(p))))
    return tuple(sig)


try:
    import streamlit as st

    @st.cache_data(ttl=3600)
    def _read_cached(name, fmt, dtype, sig):  # sense "_": Streamlit no hasheja els args amb "_"
        return read_dataset(name, fmt=fmt, dtype=dtype)

    def load_dataset(name, fmt="csv", dtype=None):
        """read_dataset() amb cache de Streamlit, renovada quan canvia el fitxer."""
        return _read_cached(name, fmt, dtype, signatura(name, fmt))
except ImportError:  # fora del dashboard (motor, API)
    load_dataset = read_dataset
