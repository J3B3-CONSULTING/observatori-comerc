# Marges per branca — font INE (`cache/marges_branca_ine.csv`)

## Què és

Marge brut d'explotació sobre vendes (%) per branca del comerç minorista
espanyol (CNAE 47 a 3 dígits), sèrie anual 2018–2024. Font primària oficial,
descarregable per API. **Substitueix** l'estimació de PATECO
(`marges_branca.csv`).

## Generació (auto-actualitzable)

Es genera al workflow diari via `processor.py::process_marges_branca()`, que
crida `ine.fetch_marges_branca()` i desa `data/cache/marges_branca_ine.csv`
(+ `.parquet`). Mateix patró que la resta de fonts anuals (EAS, DIRCE...): quan
l'INE publica un any nou, la propera execució l'incorpora; si l'API falla, es
manté la cache anterior. Està vigilat a `DATASETS_VIGILATS` (bloc Novetats).

## Definició

```
marge_vendes_pct = Excedente bruto de explotación (EBE) / Cifra de negocios × 100
```

És el *gross operating rate* estàndard de les estadístiques estructurals
d'empreses (SBS): quant de cada euro venut queda com a excedent brut
d'explotació, abans d'amortitzacions i del resultat financer. Tant l'EBE com la
xifra de negoci provenen directament de l'INE per branca; el marge es calcula, no
s'estima.

## Font

- **INE — Estadística Estructural d'Empreses: Sector Comercio** (evolució de
  l'antiga *Encuesta Anual de Comercio*), taula **76818**, Total Nacional.
- API JSON: `https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/76818`
- Reproduïble amb `data/fetchers/ine.py::fetch_marges_branca()`. La generació al
  cache la fa `processor.py::process_marges_branca()` (vegeu apartat anterior);
  s'executa sola al workflow diari.

## Cobertura

- **Branques**: 471, 472, 473, 474, 475, 476, 477, 479 (8 de 9).
- **478** (punts de venda i mercadillos): l'INE **sí** la publica a la 76818
  (revisat 2026-10-23; abans es creia que no per un error de mapatge del nom,
  "en puestos de venta y en mercadillos"). Es descarta expressament: el 2024
  tenia 40.009 empreses i 37.706 persones ocupades, menys d'una per empresa.
  L'EBE hi inclou la remuneració del titular i el marge (22,2% el 2024, el
  doble de la branca següent) no és comparable amb la resta. Les altres
  magnituds de la 478 sí que són a `subsectors_eas.csv`.
- **Anys**: 2018–2024.

### Esquema

| Camp | Tipus | Descripció |
|------|-------|------------|
| `any` | int | Any de referència (2018–2024) |
| `cnae` | int | Codi de branca INE a 3 dígits (471–479) |
| `branca` | str | Nom legible de la branca |
| `marge_vendes_pct` | float | EBE / xifra de negoci × 100, a 1 decimal |
| `font` | str | Referència INE + URL de l'API |
| `verificat` | bool | `True` — dada oficial descarregada de font primària |

## Diferència amb l'estimació de PATECO

Els valors de l'INE **no coincideixen** amb els que PATECO publica al seu
informe (`marges_branca.csv`): p.ex. moda INE ~11,8% vs PATECO ~13,5% (2024);
internet INE ~5,0% vs PATECO ~18%. És esperable per dos motius:

1. **Metodologia pròpia de PATECO**: PATECO parteix de l'INE però hi aplica
   ajustos i una definició de marge possiblement diferent (marge comercial brut
   vendes−compres, o perímetre d'empreses distint).
2. Els valors de PATECO al fitxer antic eren, a més, una lectura aproximada de
   captura de pantalla sense verificar.

Aquest fitxer és la **font oficial i verificable**; és la que s'ha de fer servir.
El mapeig conceptual amb les branques que PATECO anomena N470–N479:

| PATECO | INE |
|--------|-----|
| N470 Supermercats i grans superfícies | 471 Establiments no especialitzats |
| N471 Especialistes en alimentació | 472 Aliments, begudes i tabac |
| N472 Gasolineres | 473 Combustible |
| N474 Tecnologia | 474 Equips TIC |
| N475 Equipament de la llar | 475 Equipament de la llar |
| N476 Cultural/esportiu | 476 Articles culturals i recreatius |
| N477 Moda/calçat | 477 Altres articles |
| N478 Mercadillos | 478 (descartada: EBE amb remuneració del titular) |
| N479 Internet | 479 Comerç no en establiment |
