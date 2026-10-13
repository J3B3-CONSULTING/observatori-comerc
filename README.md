# observatori-comerc
Observatori del Comerç Minorista a Espanya

## Provar canvis al workflow diari

El workflow `update_data.yml` instal·la `requirements.txt` (versions fixades) amb Python 3.11 a GitHub Actions. Per provar-hi canvis en local s'usa un venv amb les mateixes versions de pandas, pyarrow i duckdb, **fora** del repo i de OneDrive:

```bash
/opt/homebrew/bin/python3.14 -m venv ~/.venvs/observatori-ci
~/.venvs/observatori-ci/bin/pip install -r requirements.txt openpyxl
~/.venvs/observatori-ci/bin/python data/sql/migrate.py
```

Diferència coneguda: el CI fa servir Python 3.11 i aquest venv el 3.14 (és l'únic que hi ha al Mac; amb `brew install python@3.11` es pot igualar). Les versions de les llibreries sí que coincideixen. `migrate.py` escriu `observatori.duckdb` i `data/cache/fets.csv`: executar-lo en una còpia neta si no es vol tocar el repo.

Regla: tot canvi al workflow diari es prova en aquest venv i amb un `workflow_dispatch` el mateix dia.
