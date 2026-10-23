#!/usr/bin/env python3
"""Actualiza convocatorias.json para «Qué me corresponde».

Descarga de la Base de Datos Nacional de Subvenciones (infosubvenciones.es)
las convocatorias dirigidas a personas físicas sin actividad económica, del
Estado y de cada comunidad autónoma (incluidos sus ayuntamientos y
diputaciones), y guarda solo las que siguen en plazo.

Se ejecuta una vez al día (ver .github/workflows/actualizar.yml). Usa solo la
biblioteca estándar de Python 3.9 o superior. Reutiliza el archivo anterior
como caché, así que solo pide el detalle de las convocatorias nuevas.
"""
import json, os, re, sys, time, urllib.parse, urllib.request
from datetime import date, timedelta

API = "https://www.infosubvenciones.es/bdnstrans/api"
SALIDA = os.environ.get("QMC_SALIDA", "convocatorias.json")
DIAS_ATRAS = int(os.environ.get("QMC_DIAS", "365"))   # antigüedad máxima de publicación
PAUSA = float(os.environ.get("QMC_PAUSA", "0.3"))      # segundos entre peticiones
MAX_DETALLES = int(os.environ.get("QMC_MAX_DETALLES", "4000"))
HOY = date.today()

# id de región en la BDNS -> nombre tal como aparece en el formulario de la página
REGIONES = {
    63: "Andalucía", 21: "Aragón", 8: "Asturias", 58: "Baleares", 79: "Canarias",
    10: "Cantabria", 39: "Castilla-La Mancha", 29: "Castilla y León", 49: "Cataluña",
    74: "Ceuta", 54: "Comunidad Valenciana", 45: "Extremadura", 3: "Galicia",
    25: "Madrid", 76: "Melilla", 72: "Murcia", 17: "Navarra", 13: "País Vasco",
    19: "La Rioja",
}

# Convocatorias que no son para el público en general aunque figuren como «personas físicas»
EXCLUIR = re.compile(
    r"conveni|nominad|nominativ|premio|concurso|certamen|adenda|transferencia a|aportaci[oó]n a|instrumental|"
    r"asociaci[oó]n|associaci[oó]|fundaci[oó]|federaci[oó]|\bclub\b|\bampa\b|\bafa\b|entitat|parr[oò]quia|cofrad|hermandad|"
    r"subvenci[oó]n directa (a|al) (la |el |los |las )?(universidad|ayuntamiento|colegio|c[aá]mara|instituto|consorcio|sociedad|entidad)|"
    r"gastos de funcionamiento|consejo de la juventud|cooperaci[oó]n internacional|aecid|alianza mundial|"
    r"financiaci[oó]n (del )?transporte p[uú]blico|sanidad vegetal|indemnizaci|"
    r"flota|parada temporal|pesquer|apicultur|ganader|cineg|forestal|deportistas? de alto|"
    r"modificaci[oó]n de (la )?convocatoria|correcci[oó]n de errores|ampliaci[oó]n del? (plazo|cr[eé]dito|presupuesto)|"
    r"resoluci[oó]n de concesi[oó]n|desistimiento|lista (provisional|definitiva)",
    re.I,
)


def clave(x):
    """Título normalizado + organismo, para juntar convocatorias repetidas (lotes, ficheros, códigos)."""
    t = re.sub(r"\(.*?\)|\d+", " ", (x.get("t") or "").lower())
    t = re.sub(r"[^a-záéíóúüñç ]+", " ", t)
    return (" ".join(t.split()), (x.get("org") or "").lower())


def pedir(ruta, params, intentos=4):
    url = f"{API}/{ruta}?" + urllib.parse.urlencode(params)
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "QueMeCorresponde/1.0 (actualizacion diaria; datos publicos BDNS)",
                "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # red, 429, 5xx...
            espera = 5 * (i + 1)
            print(f"  aviso: {e} en {ruta}; reintento en {espera}s", file=sys.stderr)
            time.sleep(espera)
    raise RuntimeError(f"No se pudo descargar {url}")


def listar(extra):
    """Devuelve todas las convocatorias de una búsqueda, página a página."""
    base = {"vpd": "GE", "pageSize": 100, "order": "fechaRecepcion", "direccion": "desc",
            "tiposBeneficiario": 1, "fechaDesde": (HOY - timedelta(days=DIAS_ATRAS)).strftime("%d/%m/%Y")}
    base.update(extra)
    pagina, total = 0, []
    while True:
        d = pedir("convocatorias/busqueda", dict(base, page=pagina))
        total += d.get("content") or []
        if d.get("last", True) or not d.get("content"):
            return total
        pagina += 1
        time.sleep(PAUSA)


def fecha(v):
    return v[:10] if isinstance(v, str) and re.match(r"\d{4}-\d{2}-\d{2}", v) else None


def limpiar_url(v):
    v = (v or "").strip()
    if not v or v.lower() in ("no aplica", "null"):
        return None
    if not v.lower().startswith("http"):
        v = "https://" + v.lstrip("/")
    return v


def main():
    previo, caducadas = {}, set()
    if os.path.exists(SALIDA):
        try:
            viejo = json.load(open(SALIDA, encoding="utf-8"))
            for x in viejo.get("items", []):
                previo[x["n"]] = x
            caducadas = set(viejo.get("caducadas", []))
        except Exception:
            print("aviso: no se pudo leer el archivo anterior; empiezo de cero", file=sys.stderr)

    vistos = {}  # numeroConvocatoria -> (fila del listado, set de comunidades)
    for rid, nombre in REGIONES.items():
        filas = listar({"regiones": rid})
        print(f"{nombre}: {len(filas)} convocatorias")
        for f in filas:
            n = f["numeroConvocatoria"]
            vistos.setdefault(n, (f, set()))[1].add(nombre)
        time.sleep(PAUSA)
    estatales = listar({"tipoAdministracion": "C"})
    print(f"Estado: {len(estatales)} convocatorias")
    for f in estatales:
        vistos.setdefault(f["numeroConvocatoria"], (f, set()))

    items, detalles, nuevas_cad = [], 0, set()
    for n, (f, ccaas) in vistos.items():
        desc = (f.get("descripcion") or "").strip()
        if not desc or EXCLUIR.search(desc):
            continue
        if n in caducadas:  # ya sabemos que está fuera de plazo: no se vuelve a pedir
            nuevas_cad.add(n)
            continue
        x = previo.get(n)
        if x is None:
            if detalles >= MAX_DETALLES:
                continue  # se completará en la siguiente ejecución
            try:
                d = pedir("convocatorias", {"vpd": "GE", "numConv": n})
            except RuntimeError as e:
                print(f"  aviso: {e}", file=sys.stderr)
                continue
            detalles += 1
            time.sleep(PAUSA)
            org = d.get("organo") or {}
            x = {
                "n": n,
                "t": re.sub(r"\s+", " ", d.get("descripcion") or desc).strip()[:300],
                "nivel": org.get("nivel1") or f.get("nivel1"),
                "lugar": org.get("nivel2") or f.get("nivel2"),
                "org": org.get("nivel3") or f.get("nivel3"),
                "pub": fecha(f.get("fechaRecepcion")),
                "ini": fecha(d.get("fechaInicioSolicitud")),
                "fin": fecha(d.get("fechaFinSolicitud")),
                "plazo": " ".join(filter(None, [d.get("textInicio"), d.get("textFin")])) or None,
                "sede": limpiar_url(d.get("sedeElectronica")),
                "bases": limpiar_url(d.get("urlBasesReguladoras")),
                "pres": d.get("presupuestoTotal"),
            }
        # Ámbito: Estado si es de la Administración General o aparece en muchas comunidades
        if x.get("nivel") == "ESTADO" and (not ccaas or len(ccaas) >= 3):
            x["ccaa"] = ["ESTADO"]
        else:
            x["ccaa"] = sorted(ccaas) or ["ESTADO"]
        # Plazo: fuera si ya terminó; sin fecha de fin, se mantiene 90 días desde su publicación
        if x.get("fin"):
            if x["fin"] < HOY.isoformat():
                nuevas_cad.add(n)
                continue
        elif not x.get("pub") or x["pub"] < (HOY - timedelta(days=90)).isoformat():
            nuevas_cad.add(n)
            continue
        items.append(x)

    # Una sola entrada por convocatoria repetida (p. ej. 30 lotes de «ayuda de emergencia social»): la que cierra más tarde
    unicos = {}
    for x in items:
        k = clave(x)
        if k not in unicos or (x.get("fin") or "9999") > (unicos[k].get("fin") or "9999"):
            unicos[k] = x
    items = list(unicos.values())
    items.sort(key=lambda x: (x.get("fin") or "9999", x["n"]))
    tmp = SALIDA + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"generado": HOY.isoformat(), "fuente": "Base de Datos Nacional de Subvenciones (infosubvenciones.es)",
                   "items": items, "caducadas": sorted(nuevas_cad)}, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, SALIDA)
    print(f"Guardadas {len(items)} convocatorias vigentes ({detalles} detalles nuevos) en {SALIDA}")


if __name__ == "__main__":
    main()
