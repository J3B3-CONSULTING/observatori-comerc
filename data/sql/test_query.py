"""
Tests basics de la capa de consulta (data/sql/query.py): una crida real per
funcio contra observatori.duckdb, verificant forma de la resposta i que no
hi hagi errors silenciosos. No son tests exhaustius — validen que les 7
funcions retornen dades reals abans de passar a la capa API.

Execucio: python3 data/sql/test_query.py (cal observatori.duckdb generat,
veure data/sql/migrate.py)
"""
from data.sql import query as q


def _check(label, cond, extra=""):
    status = "OK" if cond else "FAIL"
    print(f"  [{status}] {label} {extra}")
    assert cond, f"FALLIDA: {label} {extra}"


def test_list_series():
    print("1. list_series(keyword='icm')")
    r = q.list_series(keyword="icm")
    _check("retorna series", r["count"] > 0, f"(count={r['count']})")
    _check("conte icm_nominal", any(s["serie_id"] == "icm_nominal" for s in r["series"]))

    r2 = q.list_series(is_derived=True)
    _check("nomes derivades", all(s["is_derived"] for s in r2["series"]) and r2["count"] > 0,
           f"(count={r2['count']})")


def test_get_series():
    print("2. get_series('ipc_coicop', dim_1='Índex general', limit=5)")
    r = q.get_series("ipc_coicop", dim_1="Índex general", limit=5)
    _check("sense error", "error" not in r)
    _check("retorna <=5 punts", len(r["points"]) <= 5)
    _check("total_available > returned", r["total_available"] >= r["returned"])
    _check("metadata amb source", r["metadata"]["source"] == "INE")

    print("   get_series('cdmge_nonexistent') -> error amb suggestions")
    r_err = q.get_series("cdmge_nonexistent")
    _check("error detectat", "error" in r_err)
    _check("suggestions no buit", len(r_err["suggestions"]) > 0, f"({r_err['suggestions']})")


def test_get_growth():
    print("3. get_growth('pib_vab_vab_cnae47_corrents', '2015', '2023')")
    r = q.get_growth("pib_vab_vab_cnae47_corrents", "2015", "2023")
    _check("sense error", "error" not in r, r.get("error", ""))
    _check("pct_change calculat", r["pct_change"] is not None)
    print(f"      {r['value_start']:.0f} -> {r['value_end']:.0f} ({r['pct_change']:.1f}%)")


def test_compare_dimension():
    print("4. compare_dimension('empreses_count', '2023', fixed_dims=None)")
    r = q.compare_dimension("empreses_count", "2023", limit=5)
    _check("sense error", "error" not in r, r.get("error", ""))
    _check("items ordenats desc", r["items"][0]["value"] >= r["items"][-1]["value"])
    _check("rank comença a 1", r["items"][0]["rank"] == 1)
    _check("total_available >= returned", r["total_available"] >= r["returned"])
    print(f"      top1: {r['items'][0]}")


def test_get_margins():
    print("5. get_margins()")
    r = q.get_margins()
    _check("sense error", "error" not in r, r.get("error", ""))
    _check("any resolt", isinstance(r["any"], int))
    _check("items no buit", len(r["items"]) > 0)
    print(f"      any={r['any']}, {len(r['items'])} branques, top1={r['items'][0]}")


def test_get_epa_indicators():
    print("6. get_epa_indicators(date_start='2024', date_end='2025')")
    r = q.get_epa_indicators(date_start="2024", date_end="2025")
    _check("caveat present", "secció G" in r["caveat"])
    _check("points no buit", len(r["points"]) > 0)
    sexes = {p["sexe"] for p in r["points"]}
    _check("3 sexes presents (sense filtre)", sexes == {"total", "homes", "dones"}, sexes)
    print(f"      {len(r['points'])} punts, sexes={sexes}")


def test_get_macro_context():
    print("7. get_macro_context(date_start='2025-01', date_end='2025-06')")
    r = q.get_macro_context(date_start="2025-01", date_end="2025-06")
    _check("ipc general no buit", len(r["ipc"]["general"]) > 0)
    _check("ipc alimentacio no buit", len(r["ipc"]["alimentacio"]) > 0)
    _check("confianza index no buit", len(r["confianza"]["index_confianca"]) > 0)
    _check("confianza situacio_actual estructurat", "financera" in r["confianza"]["situacio_actual"])
    print(f"      ipc general: {len(r['ipc']['general'])} punts, "
          f"confianza: {len(r['confianza']['index_confianca'])} punts")


def test_get_facts():
    print("8. get_facts()")
    r = q.get_facts(limit=5)
    _check("sense error", "error" not in r, r.get("error", ""))
    _check("ordenats per rellevància",
           r["facts"][0]["rellevancia"] >= r["facts"][-1]["rellevancia"])
    _check("cada fet porta fonts", all(f["fonts"] for f in r["facts"]))
    _check("avisos amb text", all(a["text"] for f in r["facts"] for a in f["avisos"]))
    print(f"      {r['total_available']} fets; top1: {r['facts'][0]['enunciat']}")

    r2 = q.get_facts(regla="saturacio", geo_codi="ccaa:09")
    _check("filtre per regla i territori", r2["returned"] == 1, r2.get("error"))
    r3 = q.get_facts(serie_id="marges_branca_ine", limit=50)
    _check("filtre per sèrie", r3["returned"] > 0
           and all(f["regla"] == "quadrant_branca" for f in r3["facts"]))
    r4 = q.get_facts(regla="inexistent")
    _check("filtre buit -> error amb regles", "error" in r4 and r4["regles_disponibles"])


def test_get_derived():
    print("9. get_derived()")
    r = q.get_derived()
    _check("catàleg no buit", r["count"] >= 12, f"(count={r['count']})")
    _check("tots amb fórmula", all(d["formula"] for d in r["derived"]))
    r2 = q.get_derived("der_vendes_per_habitant_real", geo_codi="ccaa:09")
    _check("filtre per clau comuna", r2["returned"] > 0
           and all(p["geo_codi"] == "ccaa:09" for p in r2["points"]), r2.get("error"))
    _check("avisos a la metadata", len(r2["metadata"]["avisos"]) > 0)
    _check("sèrie de base -> error", "error" in q.get_derived("icm_real"))


if __name__ == "__main__":
    tests = [test_list_series, test_get_series, test_get_growth, test_compare_dimension,
              test_get_margins, test_get_epa_indicators, test_get_macro_context,
              test_get_facts, test_get_derived]
    for t in tests:
        t()
    print("\nTotes les funcions OK.")
