"""
Population trends of the Cilento comuni, from the combined ISTAT series
(popolazione_combinata_1982_2026.csv).

Linear and polynomial fit for each comune, summary table and plots.
Output goes to results/ (table) and results/png/ (plots).

Requires pandas, numpy, matplotlib, scipy. adjustText is optional.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import linregress

try:
    from adjustText import adjust_text
    HA_ADJUSTTEXT = True
except ImportError:
    HA_ADJUSTTEXT = False
    print("adjustText non installato, le etichette potrebbero sovrapporsi")


# --- config ---

CSV_INPUT = Path(
    "popolazione_combinata_1982_2026.csv"
)

# names must match the "Comune" column of the CSV (case doesn't matter)
COMUNI = [
    "Agropoli",
    "Alfano",
    "Aquara",
    "Ascea",
    "Atena Lucana",
    "Auletta",
    "Bellosguardo",
    "Buonabitacolo",
    "Camerota",
    "Campora",
    "Cannalonga",
    "Capaccio Paestum",
    "Casal Velino",
    "Casalbuono",
    "Casaletto Spartano",
    "Caselle in Pittari",
    "Castel San Lorenzo",
    "Castelcivita",
    "Castellabate",
    "Castelnuovo Cilento",
    "Celle di Bulgheria",
    "Centola",
    "Ceraso",
    "Cicerale",
    "Controne",
    "Corleto Monforte",
    "Cuccaro Vetere",
    "Felitto",
    "Futani",
    "Gioi",
    "Giungano",
    "Ispani",
    "Laureana Cilento",
    "Laurino",
    "Laurito",
    "Lustra",
    "Magliano Vetere",
    "Moio della Civitella",
    "Montano Antilia",
    "Monte San Giacomo",
    "Montecorice",
    "Monteforte Cilento",
    "Montesano sulla Marcellana",
    "Morigerati",
    "Novi Velia",
    "Ogliastro Cilento",
    "Omignano",
    "Orria",
    "Ottati",
    "Padula",
    "Perdifumo",
    "Perito",
    "Pertosa",
    "Petina",
    "Piaggine",
    "Pisciotta",
    "Polla",
    "Pollica",
    "Postiglione",
    "Prignano Cilento",
    "Roccadaspide",
    "Roccagloriosa",
    "Rofrano",
    "Roscigno",
    "Rutino",
    "Sacco",
    "Salento",
    "San Giovanni a Piro",
    "San Mauro Cilento",
    "San Mauro La Bruca",
    "San Pietro al Tanagro",
    "San Rufo",
    "Sant'Angelo a Fasanella",
    "Sant'Arsenio",
    "Santa Marina",
    "Sanza",
    "Sapri",
    "Sassano",
    "Serramezzana",
    "Sessa Cilento",
    "Sicignano degli Alburni",
    "Stella Cilento",
    "Stio",
    "Teggiano",
    "Torchiara",
    "Torre Orsaia",
    "Tortorella",
    "Trentinara",
    "Valle dell'Angelo",
    "Vallo della Lucania",
    "Vibonati",
]

#COMUNI = ['Laurito', 'Alfano', 'Montano Antilia', 'Vallo della Lucania', 'Rofrano', 'Centola', 'Ascea', 'Sapri', 'Roccagloriosa', 'Celle di Bulgheria', 'Sanza']

CARTELLA_OUTPUT = Path("results")
CARTELLA_PNG = CARTELLA_OUTPUT / "png"
TABELLA_OUTPUT = CARTELLA_OUTPUT / "tabella_comuni.csv"

# polynomial fit used for the projection. Degree 2 is enough to catch a
# trend that speeds up or slows down, higher degrees extrapolate badly
GRADO_POLINOMIO = 2
ANNI_PROIEZIONE_FUTURA = 20  # years after the last available one

COLORE_PRINCIPALE = "#2E5C8A"
COLORE_NEGATIVO = "#B23A48"
COLORE_MASCHI = "#2E5C8A"
COLORE_FEMMINE = "#C77B24"


# --- data ---

def normalizza_comune(nome: str) -> str:
    return str(nome).strip().title()


def carica_dati() -> pd.DataFrame:
    df = pd.read_csv(CSV_INPUT, dtype={"Codice comune": str})
    df["Comune"] = df["Comune"].map(normalizza_comune)

    comuni_richiesti = [normalizza_comune(c) for c in COMUNI]
    mancanti = sorted(set(comuni_richiesti) - set(df["Comune"].unique()))
    if mancanti:
        raise ValueError(f"Comuni non trovati nel CSV: {mancanti}")

    return df[df["Comune"].isin(comuni_richiesti)].copy()


def popolazione_annua_per_comune(df: pd.DataFrame) -> pd.DataFrame:
    # only Sesso == "Totale", otherwise M/F rows get counted twice
    totale = df[df["Sesso"].astype(str).str.strip().str.lower() == "totale"]
    return (
        totale.groupby(["Comune", "Anno"])["Popolazione"]
        .sum()
        .reset_index()
        .sort_values(["Comune", "Anno"])
    )


# --- stats per comune ---

def fit_polinomiale(pop_comune: pd.DataFrame, grado: int) -> dict:
    # t = Anno - first year, polyfit on raw years is badly conditioned.
    # Degree gets lowered if there aren't enough points
    anno_min = pop_comune["Anno"].min()
    t = (pop_comune["Anno"] - anno_min).to_numpy(dtype=float)
    y = pop_comune["Popolazione"].to_numpy(dtype=float)

    grado_effettivo = min(grado, len(t) - 1)
    if grado_effettivo < grado:
        print(f"  ATTENZIONE: solo {len(t)} punti disponibili, grado "
              f"del polinomio ridotto da {grado} a {grado_effettivo}.")
    if grado_effettivo < 1:
        return {"anno_min": anno_min, "polinomio": np.poly1d([y[0] if len(y) else 0.0]),
                "grado": 0, "r2": np.nan, "rmse": np.nan}

    coeff = np.polyfit(t, y, grado_effettivo)
    polinomio = np.poly1d(coeff)

    y_pred = polinomio(t)
    residui = y - y_pred
    ss_res = np.sum(residui ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    rmse = np.sqrt(np.mean(residui ** 2))

    return {
        "anno_min": anno_min, "polinomio": polinomio,
        "grado": grado_effettivo, "r2": r2, "rmse": rmse,
    }


def proietta_popolazione(modello_poly: dict, anno: int) -> float:
    # clipped at 0, the fit can go negative far from the data
    t = anno - modello_poly["anno_min"]
    return max(0.0, float(modello_poly["polinomio"](t)))


def calcola_statistiche_comune(
    pop_comune: pd.DataFrame,
    grado_polinomio: int = GRADO_POLINOMIO,
    anni_proiezione: int = ANNI_PROIEZIONE_FUTURA,
) -> dict:
    x = pop_comune["Anno"].to_numpy(dtype=float)
    y = pop_comune["Popolazione"].to_numpy(dtype=float)

    reg = linregress(x, y)
    y_pred = reg.slope * x + reg.intercept
    rmse = np.sqrt(np.mean((y - y_pred) ** 2))

    pop_iniziale = y[0]
    pop_finale = y[-1]
    variazione_assoluta = pop_finale - pop_iniziale
    variazione_percentuale = (
        variazione_assoluta / pop_iniziale * 100 if pop_iniziale else np.nan
    )

    modello_poly = fit_polinomiale(pop_comune, grado_polinomio)
    anno_proiezione = int(x[-1]) + anni_proiezione
    pop_proiettata = proietta_popolazione(modello_poly, anno_proiezione)

    return {
        "Anno iniziale": int(x[0]),
        "Anno finale": int(x[-1]),
        "Popolazione iniziale": int(pop_iniziale),
        "Popolazione finale": int(pop_finale),
        "Variazione totale": int(variazione_assoluta),
        "Variazione %": variazione_percentuale,
        "Pendenza (ab./anno)": reg.slope,
        "Errore standard pendenza": reg.stderr,
        "Errore medio (RMSE)": rmse,
        "R2": reg.rvalue ** 2,
        "R2 polinomio": modello_poly["r2"],
        "RMSE polinomio": modello_poly["rmse"],
        "Grado polinomio usato": modello_poly["grado"],
        "Anno proiezione": anno_proiezione,
        "Popolazione stimata (proiezione)": round(pop_proiettata),
    }


def costruisci_tabella(pop_annua: pd.DataFrame) -> pd.DataFrame:
    righe = []
    for comune in [normalizza_comune(c) for c in COMUNI]:
        sotto = pop_annua[pop_annua["Comune"] == comune]
        if sotto.empty:
            print(f"  ATTENZIONE: nessun dato per {comune}, salto.")
            continue
        if len(sotto) < 2:
            print(f"  ATTENZIONE: {comune} ha un solo anno di dati, "
                  f"non è possibile calcolare una regressione: salto.")
            continue
        stats = calcola_statistiche_comune(sotto)
        stats["Comune"] = comune
        righe.append(stats)

    if not righe:
        raise RuntimeError("Nessun comune elaborato correttamente.")

    colonne_ordinate = [
        "Comune", "Anno iniziale", "Anno finale",
        "Popolazione iniziale", "Popolazione finale",
        "Variazione totale", "Variazione %",
        "Pendenza (ab./anno)", "Errore standard pendenza",
        "Errore medio (RMSE)", "R2",
        "R2 polinomio", "RMSE polinomio", "Grado polinomio usato",
        "Anno proiezione", "Popolazione stimata (proiezione)",
    ]
    return pd.DataFrame(righe)[colonne_ordinate].sort_values("Variazione %").reset_index(drop=True)


# --- plots ---

def grafico_variazione_percentuale(tabella: pd.DataFrame, path: Path) -> None:
    dati = tabella.sort_values("Variazione %")
    colori = [COLORE_NEGATIVO if v < 0 else COLORE_PRINCIPALE for v in dati["Variazione %"]]

    plt.figure(figsize=(9, max(4, 0.4 * len(dati))))
    plt.barh(dati["Comune"], dati["Variazione %"], color=colori)
    plt.axvline(0, color="black", linewidth=0.8)
    plt.xlabel("Variazione % rispetto alla popolazione iniziale")
    plt.title("Variazione percentuale della popolazione per comune")
    plt.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def grafico_variazione_assoluta(tabella: pd.DataFrame, bilancio_totale: float, path: Path) -> None:
    # absolute change (last year - first year), total balance in the corner
    dati = tabella.sort_values("Variazione totale")
    colori = [COLORE_NEGATIVO if v < 0 else COLORE_PRINCIPALE for v in dati["Variazione totale"]]

    plt.figure(figsize=(9, max(4, 0.4 * len(dati))))
    plt.barh(dati["Comune"], dati["Variazione totale"], color=colori)
    plt.axvline(0, color="black", linewidth=0.8)
    plt.xlabel("Variazione assoluta (abitanti)")
    plt.title("Variazione assoluta della popolazione per comune")
    plt.grid(axis="x", alpha=0.3)

    segno = "+" if bilancio_totale >= 0 else "\u2212"
    plt.gcf().text(
        0.98, 0.02,
        f"Bilancio totale del gruppo: {segno}{abs(bilancio_totale):,.0f} abitanti",
        ha="right", va="bottom", fontsize=10, fontweight="bold",
        bbox=dict(boxstyle="round", facecolor="#FBF3E7", edgecolor="#C77B24"),
    )

    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def grafico_pendenza(tabella: pd.DataFrame, path: Path) -> None:
    dati = tabella.sort_values("Pendenza (ab./anno)")
    colori = [COLORE_NEGATIVO if v < 0 else COLORE_PRINCIPALE for v in dati["Pendenza (ab./anno)"]]

    plt.figure(figsize=(max(8, 0.55 * len(dati)), 6))
    plt.bar(
        dati["Comune"], dati["Pendenza (ab./anno)"], color=colori,
        yerr=dati["Errore standard pendenza"], capsize=3,
    )
    plt.axhline(0, color="black", linewidth=0.8)
    plt.ylabel("Variazione media (abitanti/anno)")
    plt.title("Trend annuo della popolazione per comune (con errore standard)")
    plt.xticks(rotation=60, ha="right")
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def grafico_traiettorie_normalizzate(pop_annua: pd.DataFrame, path: Path) -> None:
    # every series indexed to 100 in its first year.
    # Labels at the end of the lines, a legend doesn't work with this many comuni
    fig, ax = plt.subplots(figsize=(11, 6.5))
    cmap = plt.get_cmap("tab20" if len(COMUNI) > 10 else "tab10")
    comuni = [normalizza_comune(c) for c in COMUNI]

    testi = []
    for i, comune in enumerate(comuni):
        sotto = pop_annua[pop_annua["Comune"] == comune].sort_values("Anno")
        if sotto.empty:
            continue
        base = sotto["Popolazione"].iloc[0]
        indice = sotto["Popolazione"] / base * 100
        colore = cmap(i % cmap.N)
        ax.plot(sotto["Anno"], indice, color=colore, linewidth=1.6)
        testi.append(ax.text(
            sotto["Anno"].iloc[-1], indice.iloc[-1], comune,
            color=colore, fontsize=8, fontweight="bold", va="center",
        ))

    ax.axhline(100, color="black", linewidth=0.8, linestyle=":")
    ax.set_xlabel("Anno")
    ax.set_ylabel("Popolazione (indice, anno iniziale = 100)")
    ax.set_title("Traiettorie demografiche a confronto (normalizzate)")
    ax.grid(True, alpha=0.3)

    # some room on the right for the labels
    xmin, xmax = ax.get_xlim()
    ax.set_xlim(xmin, xmax + (xmax - xmin) * 0.10)

    if testi:
        if HA_ADJUSTTEXT:
            adjust_text(
                testi, ax=ax,
                only_move={"text": "y", "static": "y", "explode": "y", "pull": "y"},
                arrowprops=dict(arrowstyle="-", color="grey", lw=0.5, alpha=0.6),
            )
        else:
            # no adjustText: push overlapping labels apart vertically
            testi.sort(key=lambda t: t.get_position()[1])
            min_gap_px = 10
            trans = ax.transData
            for prev, cur in zip(testi, testi[1:]):
                _, y_prev = trans.transform(prev.get_position())
                x_cur, y_cur = cur.get_position()
                _, y_cur_px = trans.transform((x_cur, y_cur))
                if y_cur_px - y_prev < min_gap_px:
                    y_cur_px = y_prev + min_gap_px
                    _, y_new = trans.inverted().transform((0, y_cur_px))
                    cur.set_position((x_cur, y_new))

    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def grafico_proiezione_polinomiale(pop_annua: pd.DataFrame, comuni: list[str], path: Path) -> None:
    # observed series (solid) + polynomial projection (dashed)
    fig, ax = plt.subplots(figsize=(12, 7))
    cmap = plt.get_cmap("tab20" if len(comuni) > 10 else "tab10")

    testi = []
    for i, comune in enumerate(comuni):
        sotto = pop_annua[pop_annua["Comune"] == comune].sort_values("Anno")
        if len(sotto) < 2:
            continue

        colore = cmap(i % cmap.N)
        ax.plot(sotto["Anno"], sotto["Popolazione"], color=colore, linewidth=1.8)

        modello_poly = fit_polinomiale(sotto, GRADO_POLINOMIO)
        anno_ultimo = int(sotto["Anno"].max())
        anni_futuri = np.arange(anno_ultimo, anno_ultimo + ANNI_PROIEZIONE_FUTURA + 1)
        pop_futura = [proietta_popolazione(modello_poly, a) for a in anni_futuri]

        ax.plot(anni_futuri, pop_futura, color=colore, linewidth=1.8,
                linestyle="--", alpha=0.85)
        testi.append(ax.text(
            anni_futuri[-1], pop_futura[-1], comune,
            color=colore, fontsize=8, fontweight="bold", va="center",
        ))

    ax.set_xlabel("Anno")
    ax.set_ylabel("Popolazione")
    ax.set_title(
        f"Proiezione della popolazione — regressione polinomiale di grado "
        f"{GRADO_POLINOMIO} ({ANNI_PROIEZIONE_FUTURA} anni oltre l'ultimo dato, "
        f"tratteggio = stima)"
    )
    ax.grid(True, alpha=0.3)

    xmin, xmax = ax.get_xlim()
    ax.set_xlim(xmin, xmax + (xmax - xmin) * 0.10)

    if testi and HA_ADJUSTTEXT:
        adjust_text(
            testi, ax=ax,
            only_move={"text": "y", "static": "y", "explode": "y", "pull": "y"},
            arrowprops=dict(arrowstyle="-", color="grey", lw=0.5, alpha=0.6),
        )

    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def grafico_pendenza_vs_dimensione(tabella: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.scatter(
        tabella["Popolazione iniziale"], tabella["Pendenza (ab./anno)"],
        s=70, color=COLORE_PRINCIPALE, alpha=0.85, edgecolors="white", zorder=3,
    )

    testi = [
        ax.text(
            riga["Popolazione iniziale"], riga["Pendenza (ab./anno)"],
            riga["Comune"], fontsize=8,
        )
        for _, riga in tabella.iterrows()
    ]

    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Popolazione nell'anno iniziale")
    ax.set_ylabel("Pendenza (abitanti/anno)")
    ax.set_title("Velocità di declino/crescita in funzione della dimensione")
    ax.grid(True, alpha=0.3)

    if testi:
        if HA_ADJUSTTEXT:
            adjust_text(
                testi, ax=ax,
                arrowprops=dict(arrowstyle="-", color="grey", lw=0.5, alpha=0.6),
            )

    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def _piramide_per_anno(df_anno: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    piramide = (
        df_anno.groupby(["Età", "Sesso"])["Popolazione"]
        .sum()
        .unstack(fill_value=0)
        .sort_index()
    )
    maschi = piramide.get("Maschi", pd.Series(0, index=piramide.index))
    femmine = piramide.get("Femmine", pd.Series(0, index=piramide.index))
    return maschi, femmine


def grafico_piramide_eta(df: pd.DataFrame, path: Path) -> None:
    # first vs last year with the M/F split (not every source has it)
    con_sesso = df[df["Sesso"].isin(["Maschi", "Femmine"])]
    if con_sesso.empty:
        print("  Nessun dato con scomposizione per sesso disponibile: salto la piramide.")
        return

    anni_disponibili = sorted(con_sesso["Anno"].unique())
    anno_primo, anno_ultimo = anni_disponibili[0], anni_disponibili[-1]

    maschi_p, femmine_p = _piramide_per_anno(con_sesso[con_sesso["Anno"] == anno_primo])
    maschi_u, femmine_u = _piramide_per_anno(con_sesso[con_sesso["Anno"] == anno_ultimo])

    # same x scale on both panels
    limite = max(maschi_p.max(), femmine_p.max(), maschi_u.max(), femmine_u.max()) * 1.05

    fig, (ax_sx, ax_dx) = plt.subplots(1, 2, figsize=(13, 10), sharey=True)

    ax_sx.barh(maschi_p.index, -maschi_p, color=COLORE_MASCHI, label="Maschi")
    ax_sx.barh(femmine_p.index, femmine_p, color=COLORE_FEMMINE, label="Femmine")
    ax_sx.set_xlim(-limite, limite)
    ax_sx.axvline(0, color="black", linewidth=0.8)
    ax_sx.set_title(f"{anno_primo}")
    ax_sx.set_xlabel("Popolazione")
    ax_sx.set_ylabel("Età")
    ax_sx.xaxis.set_major_formatter(lambda v, _pos: f"{abs(int(v)):,}")
    ax_sx.legend(loc="upper left", fontsize=9)

    ax_dx.barh(maschi_u.index, -maschi_u, color=COLORE_MASCHI)
    ax_dx.barh(femmine_u.index, femmine_u, color=COLORE_FEMMINE)
    ax_dx.set_xlim(-limite, limite)
    ax_dx.axvline(0, color="black", linewidth=0.8)
    ax_dx.set_title(f"{anno_ultimo}")
    ax_dx.set_xlabel("Popolazione")
    ax_dx.xaxis.set_major_formatter(lambda v, _pos: f"{abs(int(v)):,}")

    # names only for small selections, a long list runs off the figure
    comuni = sorted(df["Comune"].unique())
    if len(comuni) <= 10:
        dettaglio = ",\n".join(", ".join(comuni[i:i + 5]) for i in range(0, len(comuni), 5))
    else:
        dettaglio = f"{len(comuni)} comuni"
    fig.suptitle(
        f"Piramide dell'età: {anno_primo} vs {anno_ultimo}\n({dettaglio})",
        fontsize=11,
    )
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


# --- main ---

def main() -> None:
    CARTELLA_PNG.mkdir(parents=True, exist_ok=True)

    print(f"Comuni richiesti ({len(COMUNI)}): {COMUNI}\n")
    df = carica_dati()

    pop_annua = popolazione_annua_per_comune(df)
    tabella = costruisci_tabella(pop_annua)

    print("\n=== TABELLA RIEPILOGATIVA ===")
    with pd.option_context("display.width", 160, "display.max_columns", None):
        print(tabella.to_string(index=False))

    tabella.to_csv(TABELLA_OUTPUT, index=False, encoding="utf-8-sig")
    print(f"\nTabella salvata in: {TABELLA_OUTPUT.resolve()}")

    bilancio_totale = tabella["Variazione totale"].sum()
    segno = "+" if bilancio_totale >= 0 else ""
    print(f"\n=== BILANCIO TOTALE ===")
    print(
        f"Somma della variazione assoluta sui {len(tabella)} comuni "
        f"selezionati: {segno}{bilancio_totale:,.0f} abitanti"
    )

    grafico_variazione_percentuale(tabella, CARTELLA_PNG / "variazione_percentuale.png")
    grafico_variazione_assoluta(tabella, bilancio_totale, CARTELLA_PNG / "variazione_assoluta.png")
    grafico_pendenza(tabella, CARTELLA_PNG / "pendenza.png")
    grafico_traiettorie_normalizzate(pop_annua, CARTELLA_PNG / "traiettorie_normalizzate.png")
    grafico_proiezione_polinomiale(
        pop_annua, [normalizza_comune(c) for c in COMUNI],
        CARTELLA_PNG / "proiezione_polinomiale.png",
    )
    grafico_pendenza_vs_dimensione(tabella, CARTELLA_PNG / "pendenza_vs_dimensione.png")
    grafico_piramide_eta(df, CARTELLA_PNG / "piramide_eta.png")

    print(f"\nGrafici salvati in: {CARTELLA_PNG.resolve()}")


if __name__ == "__main__":
    main()