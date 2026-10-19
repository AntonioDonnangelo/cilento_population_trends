"""
Maps of the Cilento comuni: population in 1982 and 2026, inhabitants per km2,
% change of the population and change of the mean age.

Reads results/tabella_comuni.csv (written by analisi_comuni.py), the yearly
series popolazione_combinata_1982_2026.csv (for the ages) and the municipal
boundaries of the province of Salerno (ISTAT, redistributed by
github.com/guglielmo/geojson-italy), downloaded once into data/.

Output in results/png/: one map per variable and an infographic with the
population change and the age change side by side.

Requires geopandas, matplotlib, pandas, numpy. adjustText is optional.
"""

import urllib.request
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

try:
    from adjustText import adjust_text
    HA_ADJUSTTEXT = True
except ImportError:
    HA_ADJUSTTEXT = False
    print("adjustText non installato, le etichette potrebbero sovrapporsi")


# --- config ---

TABELLA_INPUT = Path("results/tabella_comuni.csv")
CSV_COMBINATO = Path("popolazione_combinata_1982_2026.csv")  # only for the age map
CARTELLA_PNG = Path("results/png")
CARTELLA_DATI = Path("data")

URL_GEOJSON = "https://raw.githubusercontent.com/guglielmo/geojson-italy/main/geojson/"
CONFINI_COMUNI = CARTELLA_DATI / "limits_P_65_municipalities.geojson"  # province of Salerno
CONFINI_REGIONI = CARTELLA_DATI / "limits_IT_regions.geojson"  # only for the small map of Italy

CRS_METRICO = "EPSG:32633"  # UTM 33N, units in metres

AUTORE = "Antonio Donnangelo"

# the 1982 source puts everyone from 85 up in one class, so both years are
# capped at 85 to keep the mean age comparable
ETA_MASSIMA = 85

# same classes for 1982 and 2026, so the two maps can be compared
CLASSI_POP = [0, 1000, 2000, 5000, 10000, np.inf]
COLORI_POP = ["#efa665", "#dd8433", "#bf661f", "#8f4914", "#5c2d0b"]

# inhabitants per km2 in 2026, the area comes from the boundaries
CLASSI_DENSITA = [0, 25, 50, 100, 200, np.inf]
COLORI_DENSITA = ["#94c27f", "#67a24f", "#437f30", "#2b5f1e", "#173f10"]

# four classes per side, plus a grey one for the comuni that stayed within +-5%
CLASSI_VAR = [-np.inf, -45, -30, -15, -5, 5, 15, 30, 45, np.inf]
COLORI_VAR = [
    "#80192a", "#b53a47", "#d8695f", "#eb9f90",
    "#d6d5d0",
    "#94b8e0", "#6196cd", "#3469a8", "#16467f",
]

# age change: classes from the quintiles, the range isn't known in advance
COLORI_ETA = ["#7fc3b8", "#4aa597", "#2b8378", "#196159", "#0c403b"]

COLORE_ESCLUSI = "#ffffff"  # comuni of the province that are not in the table
BORDO_ESCLUSI = "#c4c3be"
COLORE_TESTO = "#222222"
COLORE_TESTO_2 = "#5c5b57"

N_ETICHETTE_POP = 5  # largest comuni labelled on the population maps
N_ETICHETTE = 3  # comuni labelled at each end of the change maps

# legend boxes in inches, so they look the same in every figure
LATO_BOX = 0.44
ALTEZZA_LEGENDA = 0.65
SPAZIO_EXTRA_LEGENDA = 3.6  # room for the "non incluso" box, in box units

FONTI = (
    "Fonte: ISTAT, ricostruzioni della popolazione 1982-2019 e POSAS 2020-2026 (2026 stima). "
    "Confini comunali ISTAT via geojson-italy (CC BY 4.0)."
)
NOTA_ETA = (
    f"Età media calcolata contando come {ETA_MASSIMA} anni tutte le età dagli {ETA_MASSIMA} in su, "
    "come nella fonte del 1982."
)


# --- data ---

def scarica(url: str, path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Scarico {url}")
    urllib.request.urlretrieve(url, path)


def normalizza_comune(nome: str) -> str:
    # same as in analisi_comuni.py, otherwise the names don't match
    return str(nome).strip().title()


def carica_comuni() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    scarica(URL_GEOJSON + CONFINI_COMUNI.name, CONFINI_COMUNI)
    confini = gpd.read_file(CONFINI_COMUNI).to_crs(CRS_METRICO)
    confini["Comune"] = confini["name"].map(normalizza_comune)

    tabella = pd.read_csv(TABELLA_INPUT)
    mancanti = sorted(set(tabella["Comune"]) - set(confini["Comune"]))
    if mancanti:
        raise ValueError(f"Comuni senza confini nel GeoJSON: {mancanti}")

    comuni = confini.merge(tabella, on="Comune")
    comuni["km2"] = comuni.geometry.area / 1e6  # CRS in metres
    comuni["Densità"] = comuni["Popolazione finale"] / comuni["km2"]
    altri = confini[~confini["Comune"].isin(tabella["Comune"])]
    return comuni, altri


def aggiungi_eta_media(comuni: gpd.GeoDataFrame) -> gpd.GeoDataFrame | None:
    # mean age in the first and last year of each comune, from the yearly series
    if not CSV_COMBINATO.exists():
        print(f"  {CSV_COMBINATO} non trovato, salto la mappa dell'età e l'infografica")
        return None

    df = pd.read_csv(CSV_COMBINATO, usecols=["Comune", "Anno", "Età", "Sesso", "Popolazione"])
    df["Comune"] = df["Comune"].map(normalizza_comune)
    df = df[df["Sesso"].astype(str).str.strip().str.lower() == "totale"].copy()
    df["Età"] = pd.to_numeric(df["Età"], errors="coerce").clip(upper=ETA_MASSIMA)
    df = df.dropna(subset=["Età"])

    df["anni_persona"] = df["Età"] * df["Popolazione"]
    somme = df.groupby(["Comune", "Anno"])[["anni_persona", "Popolazione"]].sum().reset_index()

    for colonna_anno, nome in [("Anno iniziale", "iniziale"), ("Anno finale", "finale")]:
        parte = somme.rename(columns={
            "Anno": colonna_anno,
            "anni_persona": f"anni_persona {nome}",
            "Popolazione": f"pop eta {nome}",
        })
        comuni = comuni.merge(parte, on=["Comune", colonna_anno], how="left")
        comuni[f"Età media {nome}"] = comuni[f"anni_persona {nome}"] / comuni[f"pop eta {nome}"]

    senza_eta = comuni.loc[comuni[["Età media iniziale", "Età media finale"]].isna().any(axis=1),
                           "Comune"].tolist()
    if senza_eta:
        raise ValueError(f"Comuni senza dati per età nel CSV: {senza_eta}")

    comuni["Variazione età"] = comuni["Età media finale"] - comuni["Età media iniziale"]
    return comuni


def carica_italia() -> gpd.GeoDataFrame:
    scarica(URL_GEOJSON + CONFINI_REGIONI.name, CONFINI_REGIONI)
    regioni = gpd.read_file(CONFINI_REGIONI).to_crs(CRS_METRICO)
    # one shape for the whole country, simplified: it's drawn very small
    return gpd.GeoDataFrame(geometry=[regioni.union_all().simplify(2000)], crs=CRS_METRICO)


def classifica(valori: pd.Series, classi: list[float]) -> np.ndarray:
    return pd.cut(valori, bins=classi, labels=False, right=False).to_numpy()


def classi_eta(valori: pd.Series) -> tuple[list[float], list[str]]:
    # quintiles rounded to whole years; classes that collapse are merged
    limiti = sorted(set(np.round(np.quantile(valori, [0.2, 0.4, 0.6, 0.8]))))
    classi = [-np.inf, *limiti, np.inf]
    n = len(classi) - 1
    colori = [COLORI_ETA[round(i * (len(COLORI_ETA) - 1) / max(1, n - 1))] for i in range(n)]
    return classi, colori


def nota_fonti(comuni) -> str:
    righe = [FONTI]
    tardivi = comuni[comuni["Anno iniziale"] != 1982].sort_values("name")
    asterisco = "".join(f"* {r['name']}: primo dato disponibile {int(r['Anno iniziale'])}. "
                        for _, r in tardivi.iterrows())
    righe.append(asterisco + "In bianco i comuni della provincia non inclusi nell'analisi.")
    return "\n".join(righe)


# --- formatting (Italian style: 1.000 and 7,5%) ---

def fmt_int(n: float) -> str:
    return f"{n:,.0f}".replace(",", ".")


def fmt_pct(x: float) -> str:
    return f"{x:+.1f}%".replace(".", ",")


def fmt_anni(x: float) -> str:
    return f"{x:+.1f} anni".replace(".", ",")


def fmt_densita(x: float) -> str:
    return f"{fmt_int(x)} ab/km²"


# --- drawing ---

def disegna_base(ax, comuni, altri, colori_comuni) -> None:
    altri.plot(ax=ax, color=COLORE_ESCLUSI, edgecolor=BORDO_ESCLUSI, linewidth=0.4)
    comuni.plot(ax=ax, color=colori_comuni, edgecolor="white", linewidth=0.5)

    # zoom on the analysed comuni, the rest of the province is only context
    x0, y0, x1, y1 = comuni.total_bounds
    margine = 0.03 * (x1 - x0)
    ax.set_xlim(x0 - margine, x1 + margine)
    ax.set_ylim(y0 - margine, y1 + margine)
    ax.set_aspect("equal")
    ax.set_axis_off()

    mare = gpd.GeoSeries.from_xy([14.99], [40.11], crs="EPSG:4326").to_crs(CRS_METRICO)
    ax.text(mare.x[0], mare.y[0], "Mar Tirreno", fontsize=9, style="italic",
            color="#8a9bb0", ha="center", va="center")


def etichetta_comuni(ax, comuni, testi: list[str]) -> None:
    punti = comuni.geometry.representative_point()
    alone = [pe.withStroke(linewidth=2.5, foreground="white")]
    oggetti = [
        ax.text(p.x, p.y, t, fontsize=13, ha="center", va="center",
                color=COLORE_TESTO, path_effects=alone, zorder=5)
        for p, t in zip(punti, testi)
    ]
    if HA_ADJUSTTEXT and oggetti:
        adjust_text(oggetti, ax=ax, expand=(1.2, 1.4),
                    arrowprops=dict(arrowstyle="-", color=COLORE_TESTO_2, lw=0.5))


def nome_comune(riga) -> str:
    # flag the comuni whose series doesn't start in 1982
    return riga["name"] + ("*" if riga["Anno iniziale"] != 1982 else "")


def etichetta_estremi(ax, comuni, colonna: str, formato) -> None:
    estremi = pd.concat([comuni.nsmallest(N_ETICHETTE, colonna),
                         comuni.nlargest(N_ETICHETTE, colonna)])
    testi = [f"{nome_comune(r)}\n{formato(r[colonna])}" for _, r in estremi.iterrows()]
    etichetta_comuni(ax, estremi, testi)


def barra_scala(ax, km: int = 10) -> None:
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    x = x1 - 0.04 * (x1 - x0) - km * 1000
    y = y0 + 0.03 * (y1 - y0)
    ax.plot([x, x + km * 1000], [y, y], color=COLORE_TESTO, linewidth=2, solid_capstyle="butt")
    ax.text(x + km * 500, y + 0.012 * (y1 - y0), f"{km} km", ha="center", va="bottom",
            fontsize=8, color=COLORE_TESTO)


def legenda(fig, x: float, y: float, colori: list[str], confini: list[str], titolo: str) -> None:
    # one row of class boxes with the class limits underneath
    n = len(colori)
    larghezza_fig, altezza_fig = fig.get_size_inches()
    ax = fig.add_axes((x, y, (n + SPAZIO_EXTRA_LEGENDA) * LATO_BOX / larghezza_fig,
                       ALTEZZA_LEGENDA / altezza_fig))
    for i, colore in enumerate(colori):
        ax.add_patch(Rectangle((i, 0), 1, 1, facecolor=colore, edgecolor="white", linewidth=1))
    for i, testo in enumerate(confini, start=1):
        ax.text(i, -0.3, testo, ha="center", va="top", fontsize=8, color=COLORE_TESTO)

    ax.add_patch(Rectangle((n + 0.7, 0), 1, 1, facecolor=COLORE_ESCLUSI,
                           edgecolor=BORDO_ESCLUSI, linewidth=0.8))
    ax.text(n + 1.9, 0.5, "non incluso", va="center", fontsize=8, color=COLORE_TESTO)
    ax.text(0, 1.4, titolo, fontsize=9, color=COLORE_TESTO, va="bottom")

    ax.set_xlim(0, n + SPAZIO_EXTRA_LEGENDA)
    ax.set_ylim(-1.3, 2.4)
    ax.set_axis_off()


def mappa_popolazione(ax, comuni, altri, colonna: str) -> None:
    classi = classifica(comuni[colonna], CLASSI_POP)
    disegna_base(ax, comuni, altri, [COLORI_POP[i] for i in classi])

    piu_grandi = comuni.nlargest(N_ETICHETTE_POP, colonna)
    testi = []
    for _, r in piu_grandi.iterrows():
        # the * only matters where the 1982 value is shown
        nome = nome_comune(r) if colonna == "Popolazione iniziale" else r["name"]
        testi.append(f"{nome}\n{fmt_int(r[colonna])}")
    etichetta_comuni(ax, piu_grandi, testi)
    barra_scala(ax)


def mappa_densita(ax, comuni, altri) -> None:
    classi = classifica(comuni["Densità"], CLASSI_DENSITA)
    disegna_base(ax, comuni, altri, [COLORI_DENSITA[i] for i in classi])
    etichetta_estremi(ax, comuni, "Densità", fmt_densita)
    barra_scala(ax)


def mappa_variazione(ax, comuni, altri) -> None:
    classi = classifica(comuni["Variazione %"], CLASSI_VAR)
    disegna_base(ax, comuni, altri, [COLORI_VAR[i] for i in classi])
    etichetta_estremi(ax, comuni, "Variazione %", fmt_pct)
    barra_scala(ax)


def mappa_eta(ax, comuni, altri, classi: list[float], colori: list[str]) -> None:
    indici = classifica(comuni["Variazione età"], classi)
    disegna_base(ax, comuni, altri, [colori[i] for i in indici])
    etichetta_estremi(ax, comuni, "Variazione età", fmt_anni)
    barra_scala(ax)


# each map: what to draw, its legend, its title
def pannelli(comuni, altri) -> dict[str, dict]:
    nota = nota_fonti(comuni)
    superficie = comuni["km2"].sum()
    densita_iniziale = comuni["Popolazione iniziale"].sum() / superficie
    densita_finale = comuni["Popolazione finale"].sum() / superficie
    p = {
        "pop_1982": dict(
            nome="mappa_popolazione_1982.png", titolo="Popolazione nel 1982",
            sottotitolo="Abitanti residenti per comune",
            disegna=lambda ax: mappa_popolazione(ax, comuni, altri, "Popolazione iniziale"),
            colori=COLORI_POP, confini=[fmt_int(c) for c in CLASSI_POP[1:-1]],
            legenda="Abitanti", note=nota),
        "pop_2026": dict(
            nome="mappa_popolazione_2026.png", titolo="Popolazione nel 2026",
            sottotitolo="Abitanti residenti per comune (stima ISTAT)",
            disegna=lambda ax: mappa_popolazione(ax, comuni, altri, "Popolazione finale"),
            colori=COLORI_POP, confini=[fmt_int(c) for c in CLASSI_POP[1:-1]],
            legenda="Abitanti", note=nota),
        "densita": dict(
            nome="mappa_densita.png", titolo="Abitanti per km² nel 2026",
            sottotitolo=(f"Media dell'area: {fmt_int(densita_finale)} ab/km² "
                         f"({fmt_int(densita_iniziale)} nel 1982)"),
            disegna=lambda ax: mappa_densita(ax, comuni, altri),
            colori=COLORI_DENSITA, confini=[fmt_int(c) for c in CLASSI_DENSITA[1:-1]],
            legenda="Abitanti per km²",
            note=f"{nota}\nSuperficie dei comuni calcolata dai confini ISTAT."),
        "variazione": dict(
            nome="mappa_variazione.png", titolo="Variazione della popolazione 1982-2026",
            sottotitolo="Rosso: comuni in calo. Blu: comuni in crescita",
            disegna=lambda ax: mappa_variazione(ax, comuni, altri),
            colori=COLORI_VAR, confini=[f"{c:+d}%" for c in CLASSI_VAR[1:-1]],
            legenda="Variazione della popolazione", note=nota),
    }
    if "Variazione età" in comuni:
        classi, colori = classi_eta(comuni["Variazione età"])
        p["eta"] = dict(
            nome="mappa_eta.png", titolo="Variazione dell'età media 1982-2026",
            sottotitolo="Di quanti anni è cresciuta l'età media dei residenti",
            disegna=lambda ax: mappa_eta(ax, comuni, altri, classi, colori),
            colori=colori, confini=[f"{c:+.0f}" for c in classi[1:-1]],
            legenda="Variazione dell'età media (anni)", note=f"{nota}\n{NOTA_ETA}")
    return p


def salva_mappa_singola(p: dict) -> None:
    fig = plt.figure(figsize=(8, 9))
    ax = fig.add_axes((0.02, 0.17, 0.96, 0.72))
    p["disegna"](ax)
    fig.text(0.04, 0.965, p["titolo"], fontsize=15, fontweight="bold", color=COLORE_TESTO, va="top")
    fig.text(0.04, 0.925, p["sottotitolo"], fontsize=12, color=COLORE_TESTO_2, va="top")
    legenda(fig, 0.04, 0.075, p["colori"], p["confini"], p["legenda"])
    fig.text(0.04, 0.012, p["note"], fontsize=10, color=COLORE_TESTO_2, va="bottom")
    fig.savefig(CARTELLA_PNG / p["nome"], dpi=200, facecolor="white")
    plt.close(fig)


# --- infographic ---

def riquadro_numero(fig, x: float, numero: str, testo: str) -> None:
    fig.text(x, 0.86, numero, fontsize=26, fontweight="bold", color=COLORE_TESTO, va="top")
    fig.text(x, 0.80, testo, fontsize=15, color=COLORE_TESTO_2, va="top", linespacing=1.4)


def salva_infografica(comuni, altri, italia, mappe: list[dict]) -> None:
    pop_iniziale = comuni["Popolazione iniziale"].sum()
    pop_finale = comuni["Popolazione finale"].sum()
    variazione = (pop_finale - pop_iniziale) / pop_iniziale * 100
    n_calo = int((comuni["Variazione %"] < 0).sum())
    eta_iniziale = comuni["anni_persona iniziale"].sum() / comuni["pop eta iniziale"].sum()
    eta_finale = comuni["anni_persona finale"].sum() / comuni["pop eta finale"].sum()

    fig = plt.figure(figsize=(16, 11))
    fig.text(0.03, 0.965, "Cilento 1982-2026: meno abitanti, più anziani",
             fontsize=24, fontweight="bold", color=COLORE_TESTO, va="top")
    fig.text(0.03, 0.91,
             f"Residenti in {len(comuni)} comuni della provincia di Salerno, dati ISTAT",
             fontsize=12, color=COLORE_TESTO_2, va="top")

    riquadro_numero(fig, 0.03, fmt_pct(variazione).replace("+", ""),
                    f"abitanti nel complesso,\nda {fmt_int(pop_iniziale)} a {fmt_int(pop_finale)}")
    riquadro_numero(fig, 0.26, f"{n_calo} su {len(comuni)}",
                    "comuni hanno meno\nabitanti del 1982")
    riquadro_numero(fig, 0.49, fmt_anni(eta_finale - eta_iniziale),
                    f"età media dei residenti,\nda {eta_iniziale:.1f} a {eta_finale:.1f} anni".replace(".", ","))

    # where the Cilento is, for readers who don't know
    ax_italia = fig.add_axes((0.79, 0.69, 0.18, 0.29))
    italia.plot(ax=ax_italia, color="#e4e3df", edgecolor="none")
    gpd.GeoSeries([comuni.union_all()], crs=CRS_METRICO).plot(ax=ax_italia, color=COLORE_TESTO)
    ax_italia.set_aspect("equal")
    ax_italia.set_axis_off()

    for i, p in enumerate(mappe):
        x = 0.03 + i * 0.49
        ax = fig.add_axes((x, 0.15, 0.46, 0.54))
        p["disegna"](ax)
        ax.set_anchor("W")  # map on the left edge, lined up with its title and legend
        ax.set_title(p["titolo"], fontsize=13, fontweight="bold", color=COLORE_TESTO, loc="left")
        legenda(fig, x, 0.075, p["colori"], p["confini"], p["legenda"])

    fig.text(0.03, 0.012, f"{nota_fonti(comuni)}\n{NOTA_ETA}", fontsize=12, color=COLORE_TESTO_2, va="bottom")
    fig.text(0.97, 0.012, f"Elaborazione: {AUTORE}", fontsize=12, color=COLORE_TESTO_2,
             va="bottom", ha="right")
    fig.savefig(CARTELLA_PNG / "infografica_mappe.png", dpi=300, facecolor="white")
    plt.close(fig)


# --- main ---

def main() -> None:
    CARTELLA_PNG.mkdir(parents=True, exist_ok=True)
    comuni, altri = carica_comuni()
    print(f"{len(comuni)} comuni con confini, {len(altri)} altri comuni della provincia")

    con_eta = aggiungi_eta_media(comuni)
    if con_eta is not None:
        comuni = con_eta

    mappe = pannelli(comuni, altri)
    for p in mappe.values():
        salva_mappa_singola(p)

    if "eta" in mappe:
        salva_infografica(comuni, altri, carica_italia(), [mappe["variazione"], mappe["eta"]])

    print(f"Mappe salvate in: {CARTELLA_PNG.resolve()}")


if __name__ == "__main__":
    main()