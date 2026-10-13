# observatori-comerc
Observatori del Comerç Minorista a Espanya

## Provar canvis al workflow diari

El workflow `update_data.yml` instal·la `requirements.txt` (versions fixades) amb Python 3.11 a GitHub Actions. Per provar-hi canvis en local s'usa un venv amb les mateixes versions de pandas, pyarrow i duckdb, **fora** del repo i de OneDrive:

```bash
/opt/homebrew/bin/python3.11 -m venv ~/.venvs/observatori-ci
~/.venvs/observatori-ci/bin/pip install -r requirements.txt openpyxl
~/.venvs/observatori-ci/bin/python data/sql/migrate.py
```

El venv usa Python 3.11 (`brew install python@3.11`), el mateix que el CI, i les versions de pandas, pyarrow i duckdb de `requirements.txt`. `migrate.py` escriu `observatori.duckdb` i `data/cache/fets.csv`: executar-lo en una còpia neta si no es vol tocar el repo.

Regla: tot canvi al workflow diari es prova en aquest venv i amb un `workflow_dispatch` el mateix dia.

## Pendent (prioritat baixa): validació de salts

`_is_valid_series` (`data/processor.py`) avisa cada dia de dos fals positius per ràtio: `confianza_consumidor/index_confianca` (34,5×, abril del 2020, base propera a zero) i `cdmge/valor` (995,0×, base de pocs dècimes els primers dies del mes). Proposta: diferència absoluta només per a les sèries de taxes. Detall al ROADMAP del repo `j3b3-newsletter`.
