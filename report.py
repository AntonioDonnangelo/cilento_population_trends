"""
Report on the depopulation of the Cilento comuni (Markdown -> PDF with pandoc).

Input:
  - results/tabella_comuni.csv, written by analisi_comuni.py
  - popolazione_combinata_1982_2026.csv (optional), the yearly series.
    Without it the trajectories figure is skipped.

Output: plots in results/png/, report.md in results/, PDF in results/pdf/.

Requires pandas, numpy, matplotlib (adjustText optional) and pandoc with
a PDF engine (xelatex, pdflatex, lualatex, wkhtmltopdf or weasyprint).
"""

import shutil
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from adjustText import adjust_text
    HA_ADJUSTTEXT = True
except ImportError:
    HA_ADJUSTTEXT = False
    print("adjustText non installato, le etichette potrebbero sovrapporsi")


# --- config ---

CARTELLA_OUTPUT = Path("results")
CARTELLA_PNG = CARTELLA_OUTPUT / "png"
CARTELLA_PDF = CARTELLA_OUTPUT / "pdf"

TABELLA_INPUT = CARTELLA_OUTPUT / "tabella_comuni.csv"
CSV_COMBINATO = Path("popolazione_combinata_1982_2026.csv")  # optional

AUTORE = "Antonio Donnangelo"
NOME_AREA = "Cilento"

MD_PATH = CARTELLA_OUTPUT / "report.md"
CSS_PATH = CARTELLA_OUTPUT / "report.css"
PDF_PATH = CARTELLA_PDF / "report_cilento.pdf"

# comuni facing the sea. Rough geographic split, not an official ISTAT one
COMUNI_COSTIERI = [
    "Agropoli", "Castellabate", "Casal Velino", "Ascea", "Pisciotta",
    "Centola", "Camerota", "San Giovanni A Piro", "Vibonati", "Sapri",
    "Montecorice", "Pollica", "Ispani", "Santa Marina", "Capaccio Paestum",
]

N_TOP = 10  # comuni shown in the top/bottom rankings

COLORE_PRINCIPALE = "#2E5C8A"
COLORE_NEGATIVO = "#B23A48"
COLORE_COSTA = "#2E86AB"
COLORE_INTERNO = "#A0522D"


# --- data ---

def carica_tabella() -> pd.DataFrame:
    df = pd.read_csv(TABELLA_INPUT)
    df["Costiero"] = df["Comune"].isin(COMUNI_COSTIERI)
    # intercept of the linear fit, needed to rebuild the aggregate trend
    df["Intercetta"] = df["Popolazione finale"] - df["Pendenza (ab./anno)"] * df["Anno finale"]
    # projected change, last observed year -> projection year (e.g. 2026 -> 2046)
    df["Variazione % proiettata"] = (
        (df["Popolazione stimata (proiezione)"] - df["Popolazione finale"])
        / df["Popolazione finale"] * 100
    )
    return df


def calcola_statistiche_aggregate(df: pd.DataFrame) -> dict:
    pop_iniziale_tot = df["Popolazione iniziale"].sum()
    pop_finale_tot = df["Popolazione finale"].sum()
    variazione_tot = pop_finale_tot - pop_iniziale_tot
    variazione_pct_pesata = variazione_tot / pop_iniziale_tot * 100

    n_comuni = len(df)
    n_declino = int((df["Variazione %"] < 0).sum())
    n_crescita = n_comuni - n_declino

    costa = df[df["Costiero"]]
    interno = df[~df["Costiero"]]

    n_zero_proiezione = int((df["Popolazione stimata (proiezione)"] == 0).sum())

    return {
        "n_comuni": n_comuni,
        "anno_min": int(df["Anno iniziale"].min()),
        "anno_max": int(df["Anno finale"].max()),
        "anno_proiezione": int(df["Anno proiezione"].max()),
        "pop_iniziale_tot": int(pop_iniziale_tot),
        "pop_finale_tot": int(pop_finale_tot),
        "variazione_tot": int(variazione_tot),
        "variazione_pct_pesata": variazione_pct_pesata,
        "variazione_pct_media": df["Variazione %"].mean(),
        "variazione_pct_mediana": df["Variazione %"].median(),
        "n_declino": n_declino,
        "pct_declino": n_declino / n_comuni * 100,
        "n_crescita": n_crescita,
        "n_oltre50": int((df["Variazione %"] <= -50).sum()),
        "n_oltre30": int((df["Variazione %"] <= -30).sum()),
        "n_zero_proiezione": n_zero_proiezione,
        "n_costa": len(costa),
        "n_interno": len(interno),
        "media_costa": costa["Variazione %"].mean(),
        "mediana_costa": costa["Variazione %"].median(),
        "media_interno": interno["Variazione %"].mean(),
        "mediana_interno": interno["Variazione %"].median(),
        "corr_dimensione_variazione": df["Popolazione iniziale"].corr(df["Variazione %"]),
    }


# --- yearly series (optional) ---

def normalizza_comune(nome: str) -> str:
    return str(nome).strip().title()


def carica_pop_annua_storica(comuni: list[str]) -> pd.DataFrame | None:
    # yearly totals for the given comuni, None if the CSV isn't there
    if not CSV_COMBINATO.exists():
        print(f"  {CSV_COMBINATO} non trovato, salto il grafico delle traiettorie")
        return None

    grezzo = pd.read_csv(CSV_COMBINATO, dtype={"Codice comune": str})
    grezzo["Comune"] = grezzo["Comune"].map(normalizza_comune)
    grezzo = grezzo[grezzo["Comune"].isin(comuni)]
    totale = grezzo[grezzo["Sesso"].astype(str).str.strip().str.lower() == "totale"]
    return (
        totale.groupby(["Comune", "Anno"])["Popolazione"]
        .sum()
        .reset_index()
        .sort_values(["Comune", "Anno"])
    )


def fit_polinomiale(pop_comune: pd.DataFrame, grado: int) -> dict:
    # same fit as in analisi_comuni.py
    anno_min = pop_comune["Anno"].min()
    t = (pop_comune["Anno"] - anno_min).to_numpy(dtype=float)
    y = pop_comune["Popolazione"].to_numpy(dtype=float)
    grado_effettivo = max(1, min(grado, len(t) - 1))
    coeff = np.polyfit(t, y, grado_effettivo)
    return {"anno_min": anno_min, "polinomio": np.poly1d(coeff)}


def proietta_popolazione(modello_poly: dict, anno: int) -> float:
    t = anno - modello_poly["anno_min"]
    return max(0.0, float(modello_poly["polinomio"](t)))


# --- plots ---

def fig_distribuzione_variazione(df: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(df["Variazione %"], bins=20, color=COLORE_PRINCIPALE, edgecolor="white")
    ax.axvline(0, color="black", linewidth=1)
    ax.axvline(df["Variazione %"].median(), color=COLORE_NEGATIVO, linewidth=1.5,
               linestyle="--", label=f"Mediana ({df['Variazione %'].median():.1f}%)")
    ax.set_xlabel("Variazione % della popolazione (1982\u20132026)")
    ax.set_ylabel("Numero di comuni")
    ax.set_title(f"Distribuzione della variazione percentuale della popolazione (n={len(df)})")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_classifica_estremi(df: pd.DataFrame, n: int, path: Path) -> None:
    peggiori = df.nsmallest(n, "Variazione %")
    migliori = df.nlargest(n, "Variazione %")
    combinato = pd.concat([peggiori, migliori]).sort_values("Variazione %")
    colori = [COLORE_NEGATIVO if v < 0 else COLORE_PRINCIPALE for v in combinato["Variazione %"]]

    fig, ax = plt.subplots(figsize=(9, max(6, 0.4 * len(combinato))))
    ax.barh(combinato["Comune"], combinato["Variazione %"], color=colori)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Variazione % (1982\u20132026)")
    ax.set_title(f"I {n} comuni con il calo maggiore e i {n} con la crescita maggiore")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_classifica_proiezione(df: pd.DataFrame, n: int, anno_proiezione: int, path: Path) -> None:
    # same as fig_classifica_estremi but on the projected change.
    # Ties at -100% (projected to 0) are sorted by current population
    a_rischio = df.sort_values(
        ["Variazione % proiettata", "Popolazione finale"], ascending=[True, False]
    ).head(n)
    crescita = df.sort_values("Variazione % proiettata", ascending=False).head(n)
    combinato = pd.concat([a_rischio, crescita]).drop_duplicates("Comune").sort_values("Variazione % proiettata")
    colori = [COLORE_NEGATIVO if v < 0 else COLORE_PRINCIPALE for v in combinato["Variazione % proiettata"]]

    fig, ax = plt.subplots(figsize=(9, max(6, 0.4 * len(combinato))))
    ax.barh(combinato["Comune"], combinato["Variazione % proiettata"], color=colori)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel(f"Variazione % proiettata (ultimo anno osservato \u2192 {anno_proiezione})")
    ax.set_title(f"I {n} comuni più a rischio e i {n} con le migliori prospettive (proiezione polinomiale)")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_traiettorie_rischio_crescita(
    pop_annua: pd.DataFrame, comuni_rischio: list[str], comuni_crescita: list[str],
    grado: int, anno_proiezione: int, path: Path
) -> None:
    # observed (solid) + projection (dashed). Two panels because the at-risk
    # comuni are much smaller than the growing ones, on one axis they'd be flat
    fig, (ax_r, ax_c) = plt.subplots(1, 2, figsize=(14, 7.5))

    for ax, comuni_gruppo, cmap, titolo in [
        (ax_r, comuni_rischio, plt.get_cmap("Reds"), "Comuni più a rischio"),
        (ax_c, comuni_crescita, plt.get_cmap("Blues"), "Comuni con le migliori prospettive"),
    ]:
        testi = []
        for i, comune in enumerate(comuni_gruppo):
            sotto = pop_annua[pop_annua["Comune"] == comune].sort_values("Anno")
            if len(sotto) < 2:
                continue
            colore = cmap(0.35 + 0.55 * i / max(1, len(comuni_gruppo) - 1))

            ax.plot(sotto["Anno"], sotto["Popolazione"], color=colore, linewidth=1.6)

            modello = fit_polinomiale(sotto, grado)
            anno_ultimo = int(sotto["Anno"].max())
            anni_futuri = np.arange(anno_ultimo, anno_proiezione + 1)
            pop_futura = [proietta_popolazione(modello, a) for a in anni_futuri]
            ax.plot(anni_futuri, pop_futura, color=colore, linewidth=1.6,
                    linestyle="--", alpha=0.85)

            testi.append(ax.text(
                anni_futuri[-1], pop_futura[-1], comune,
                color=colore, fontsize=7.5, fontweight="bold", va="center",
            ))

        ax.set_xlabel("Anno")
        ax.set_ylabel("Popolazione")
        ax.set_title(titolo, fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(bottom=0)

        xmin, xmax = ax.get_xlim()
        ax.set_xlim(xmin, xmax + (xmax - xmin) * 0.16)

        if testi and HA_ADJUSTTEXT:
            adjust_text(
                testi, ax=ax,
                only_move={"text": "y", "static": "y", "explode": "y", "pull": "y"},
                arrowprops=dict(arrowstyle="-", color="grey", lw=0.5, alpha=0.6),
            )

    fig.suptitle(
        "Traiettorie storiche (linea continua) e proiezione polinomiale (tratteggio)",
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_costa_vs_interno(df: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 6))
    gruppi = [df[~df["Costiero"]]["Variazione %"], df[df["Costiero"]]["Variazione %"]]
    bp = ax.boxplot(gruppi, tick_labels=["Entroterra", "Costa"], patch_artist=True, widths=0.5)
    for patch, colore in zip(bp["boxes"], [COLORE_INTERNO, COLORE_COSTA]):
        patch.set_facecolor(colore)
        patch.set_alpha(0.7)
    for i, g in enumerate(gruppi, start=1):
        x = np.random.normal(i, 0.05, size=len(g))
        ax.scatter(x, g, color="black", alpha=0.4, s=15, zorder=3)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("Variazione % (1982\u20132026)")
    ax.set_title("Variazione della popolazione: comuni costieri vs. dell'entroterra")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_dimensione_vs_variazione(df: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 6))
    for costiero, colore, etichetta in [(False, COLORE_INTERNO, "Entroterra"),
                                          (True, COLORE_COSTA, "Costa")]:
        sotto = df[df["Costiero"] == costiero]
        ax.scatter(sotto["Popolazione iniziale"], sotto["Variazione %"],
                   color=colore, alpha=0.75, s=45, label=etichetta, edgecolors="white")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xscale("log")
    ax.set_xlabel("Popolazione nell'anno iniziale (scala log)")
    ax.set_ylabel("Variazione % (1982\u20132026)")
    ax.set_title("Variazione percentuale in funzione della dimensione del comune")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_andamento_aggregato(df: pd.DataFrame, stats: dict, path: Path) -> None:
    # sum of the single linear fits, not of the raw yearly data
    anno_min = int(df["Anno iniziale"].min())
    anno_max_proiezione = int(df["Anno proiezione"].max())
    anni = np.arange(anno_min, anno_max_proiezione + 1)

    somma_slope = df["Pendenza (ab./anno)"].sum()
    somma_intercetta = df["Intercetta"].sum()
    stima = somma_slope * anni + somma_intercetta

    fig, ax = plt.subplots(figsize=(10, 5.5))
    storico = anni <= stats["anno_max"]
    ax.plot(anni[storico], stima[storico], color=COLORE_PRINCIPALE, linewidth=2.2,
            label="Andamento aggregato stimato (somma delle rette individuali)")
    ax.plot(anni[~storico], stima[~storico], color=COLORE_PRINCIPALE, linewidth=2.2,
            linestyle="--", label="Proiezione oltre l'ultimo anno osservato")
    ax.scatter([stats["anno_min"], stats["anno_max"]],
               [stats["pop_iniziale_tot"], stats["pop_finale_tot"]],
               color=COLORE_NEGATIVO, zorder=4, s=50,
               label="Somma reale della popolazione (inizio/fine periodo)")
    ax.set_xlabel("Anno")
    ax.set_ylabel(f"Popolazione totale ({stats['n_comuni']} comuni)")
    ax.set_title(f"Andamento aggregato della popolazione dei comuni analizzati")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --- markdown tables ---

def tabella_markdown(df: pd.DataFrame, colonne: dict) -> str:
    # colonne: {df column: header in the table}
    intestazioni = " | ".join(colonne.values())
    separatori = " | ".join("---:" if i > 0 else "---" for i in range(len(colonne)))
    righe = []
    for _, r in df.iterrows():
        valori = []
        for col in colonne:
            v = r[col]
            if isinstance(v, float):
                valori.append(f"{v:,.1f}")
            elif isinstance(v, (int, np.integer)):
                valori.append(f"{v:,}")
            else:
                valori.append(str(v))
        righe.append("| " + " | ".join(valori) + " |")
    return f"| {intestazioni} |\n| {separatori} |\n" + "\n".join(righe)


# --- report text ---

def genera_markdown(
    df: pd.DataFrame, stats: dict, nomi_grafici: dict, traiettorie_disponibili: bool
) -> str:
    oggi = pd.Timestamp.today().strftime("%d/%m/%Y")

    peggiori = df.nsmallest(N_TOP, "Variazione %")[
        ["Comune", "Popolazione iniziale", "Popolazione finale", "Variazione %"]
    ]
    migliori = df.nlargest(N_TOP, "Variazione %")[
        ["Comune", "Popolazione iniziale", "Popolazione finale", "Variazione %"]
    ]
    colonne_ranking = {
        "Comune": "Comune", "Popolazione iniziale": f"Pop. {stats['anno_min']}",
        "Popolazione finale": f"Pop. {stats['anno_max']}", "Variazione %": "Var. %",
    }

    if traiettorie_disponibili:
        sezione_traiettorie = f"""
La Figura 7 mostra le stesse {2 * N_TOP} traiettorie in forma di serie
storica (linea continua) con la relativa proiezione polinomiale (linea
tratteggiata), anziché come singolo valore aggregato: permette di
apprezzare sia la forma dell'andamento storico di ciascun comune sia dove
la proiezione lo colloca al {stats['anno_proiezione']}.

![Traiettorie storiche e proiezione, comuni a rischio e in crescita]({nomi_grafici.get('traiettorie_rischio', '')})
"""
    else:
        sezione_traiettorie = """
> *Nota: il grafico delle traiettorie storiche complete non è disponibile.*
"""

    return f"""---
title: "Lo spopolamento del {NOME_AREA} interno: un'analisi quantitativa dell'andamento demografico comunale ({stats['anno_min']}-{stats['anno_max']})"
author: "{AUTORE}"
date: "{oggi}"
geometry: margin=2.5cm
fontsize: 11pt
---

# Abstract {{-}}

Questo lavoro analizza l'andamento della popolazione residente di
**{stats['n_comuni']} comuni** dell'area del {NOME_AREA} (provincia di
Salerno) nel periodo **{stats['anno_min']}-{stats['anno_max']}**, integrando
fonti storiche ISTAT eterogenee (ricostruzioni intercensuarie e bilanci
demografici POSAS) in un'unica serie temporale armonizzata. Nel periodo
considerato la popolazione aggregata dei comuni analizzati è passata da
**{stats['pop_iniziale_tot']:,}** a **{stats['pop_finale_tot']:,}** abitanti
(**{stats['variazione_pct_pesata']:+.1f}%**), con il
**{stats['pct_declino']:.0f}%** dei comuni in calo. Emerge una netta
divergenza tra i comuni costieri (variazione mediana
**{stats['mediana_costa']:+.1f}%**) e quelli dell'entroterra (variazione
mediana **{stats['mediana_interno']:+.1f}%**), che discutiamo alla luce
della letteratura esistente sullo spopolamento delle aree interne italiane.

# Introduzione

Lo spopolamento dei piccoli comuni dell'entroterra meridionale è un
fenomeno ampiamente documentato a livello nazionale. Circa la metà dei
comuni italiani ricade nelle cosiddette "aree interne" secondo la
classificazione della Strategia Nazionale per le Aree Interne (SNAI),
territori caratterizzati da difficile accesso ai servizi essenziali; ISTAT
stima che nei prossimi anni la quasi totalità dei comuni interni del
Mezzogiorno continuerà a perdere popolazione, con un recente aggiornamento
del Piano Strategico Nazionale che ha introdotto per alcune di queste aree
l'ipotesi di uno "spopolamento irreversibile" [1, 2].

Il fenomeno non ha risparmiato il {NOME_AREA}: un'analisi del GAL {NOME_AREA}
Regeneratio, che dal 2012 monitora l'andamento demografico ed economico dei
comuni dell'area attraverso periodiche indagini ("Il {NOME_AREA}: tra
desertificazione sociale e prospettive di sviluppo sostenibile"), ha
documentato la persistenza del declino tra il 2002 e il 2017 [3]; fonti di
stampa che citano dati ISTAT più recenti riportano che circa i tre quarti
dei comuni del {NOME_AREA} risulterebbero in fase di spopolamento [4].

Questo lavoro si propone come **complemento quantitativo e di più lungo
periodo** a queste analisi, non come primo studio del fenomeno. Il
contributo specifico è duplice: (i) l'estensione dell'orizzonte temporale a
**{stats['anno_max'] - stats['anno_min']} anni** ({stats['anno_min']}-{stats['anno_max']}), ottenuta armonizzando
fonti ISTAT storicamente eterogenee tra loro per struttura e non
direttamente confrontabili senza un lavoro preliminare di pulizia e
normalizzazione; (ii) un confronto sistematico, comune per comune, basato
su modelli statistici espliciti (regressione lineare e polinomiale) con
relative metriche di bontà di adattamento, anziché sulla sola variazione
percentuale grezza tra due anni. Dato il carattere strutturale e non
transitorio del fenomeno, riteniamo utile affiancare alle analisi
esistenti uno strumento quantitativo di questo tipo, riproducibile e
aggiornabile.

# Materiali e Metodi

## Fonti dei dati

I dati di popolazione residente per comune, età e sesso provengono da tre
famiglie di fonti ISTAT, integrate in un'unica serie {stats['anno_min']}-{stats['anno_max']}:

1. **Ricostruzione della popolazione 1982-1991**: formato aggregato
   multi-anno con classi di età fino a "85 e oltre".
2. **Ricostruzione intercensuaria della popolazione 1992-2019**: serie
   annuali per età e sesso.
3. **POSAS (Popolazione per età, sesso e stato civile) 2020-2026**: bilanci
   demografici annuali più recenti, per il {stats['anno_max']} basati su stima.

L'integrazione ha richiesto un lavoro preliminare non banale: le tre
famiglie di fonti usano separatori, quotazioni e granularità differenti, e
due di esse contengono righe di totale identificate da codici età
convenzionali (rispettivamente "99" e "999") che, se non individuate ed
escluse esplicitamente, portano a un doppio conteggio della popolazione
totale. Tutti i valori riportati in questo lavoro fanno riferimento alla
sola componente "Totale" (somma di maschi e femmine su tutte le età),
verificata per coerenza interna (Maschi + Femmine = Totale) dove la
scomposizione per sesso è disponibile.

## Selezione dei comuni

L'analisi copre **{stats['n_comuni']} comuni** dell'area del {NOME_AREA},
selezionati come sottoinsieme dei comuni della provincia di Salerno
ricadenti nell'area storico-geografica del {NOME_AREA} (Alto e Basso
{NOME_AREA}, Vallo di Diano, Alburni). Per **{stats['n_comuni'] - 1}**
comuni la serie copre l'intero periodo {stats['anno_min']}-{stats['anno_max']};
per Capaccio Paestum, per limiti della fonte disponibile, la serie inizia
nel 2002.

Per un sottoinsieme dell'analisi, i comuni sono stati classificati come
**costieri** (n={stats['n_costa']}) se il loro territorio comunale si
affaccia sul Mar Tirreno, **dell'entroterra** (n={stats['n_interno']})
altrimenti. La classificazione è geografica indicativa (non una
categorizzazione ISTAT/SNAI ufficiale) e include i comuni con frazioni
costiere note (es. Marina di Casal Velino, Villammare di Vibonati) anche
quando il capoluogo comunale è collinare, come è la norma per gran parte
della costa cilentana [5].

## Metodi statistici

Per ciascun comune, la popolazione totale annua è stata modellata con:

- una **regressione lineare** (OLS) rispetto all'anno, da cui si ricavano
  la pendenza (variazione media annua, abitanti/anno), l'errore standard
  della pendenza, l'errore quadratico medio (RMSE) e il coefficiente di
  determinazione (R\u00b2);
- una **regressione polinomiale di secondo grado**, usata per stimare una
  proiezione della popolazione a {df['Anno proiezione'].iloc[0] - stats['anno_max']}
  anni oltre l'ultimo dato disponibile ({df['Anno proiezione'].iloc[0]}),
  con tempo centrato sul primo anno di ciascuna serie per stabilità
  numerica.

L'andamento aggregato del gruppo di comuni (Figura 5) è stato ricostruito
sommando le rette di regressione individuali di ciascun comune, **non**
sommando dati grezzi anno per anno; è quindi una stima basata sui modelli
lineari individuali, coerente per costruzione con la somma reale della
popolazione nell'anno finale, ma non con eventuali oscillazioni di breve
periodo non catturate dal modello lineare.

> **Nota metodologica.** Tutte le proiezioni presentate (sia individuali
> sia aggregate) sono estrapolazioni statistiche di modelli semplici e non
> tengono conto di flussi migratori, politiche di sviluppo locale,
> interventi della Strategia Nazionale per le Aree Interne o cambiamenti
> nei tassi di natalità e mortalità. Vanno lette come indicazioni di
> tendenza, non come previsioni puntuali.

# Risultati

## Quadro d'insieme

Nel periodo {stats['anno_min']}-{stats['anno_max']} la popolazione
aggregata dei {stats['n_comuni']} comuni analizzati è passata da
**{stats['pop_iniziale_tot']:,}** a **{stats['pop_finale_tot']:,}**
abitanti, una variazione di **{stats['variazione_tot']:+,}** unità
({stats['variazione_pct_pesata']:+.1f}% sul totale). Il
**{stats['n_declino']} su {stats['n_comuni']}** dei comuni
({stats['pct_declino']:.0f}%) ha registrato una perdita di popolazione;
**{stats['n_oltre50']}** comuni hanno perso oltre il 50% della popolazione
iniziale e **{stats['n_oltre30']}** oltre il 30%. La Figura 1 mostra la
distribuzione completa della variazione percentuale, con una mediana del
**{stats['variazione_pct_mediana']:+.1f}%**.

![Distribuzione della variazione percentuale]({nomi_grafici['distribuzione']})

## Comuni agli estremi

La Figura 2 e le Tabelle 1-2 riportano i {N_TOP} comuni con il calo
maggiore e i {N_TOP} con la crescita maggiore. Il comune con la perdita
relativa più marcata è **{peggiori.iloc[0]['Comune']}**
({peggiori.iloc[0]['Variazione %']:+.1f}%, da
{peggiori.iloc[0]['Popolazione iniziale']:,} a
{peggiori.iloc[0]['Popolazione finale']:,} abitanti); il comune con la
crescita maggiore è **{migliori.iloc[0]['Comune']}**
({migliori.iloc[0]['Variazione %']:+.1f}%).

![Comuni agli estremi della distribuzione]({nomi_grafici['estremi']})

**Tabella 1.** I {N_TOP} comuni con il calo maggiore.

{tabella_markdown(peggiori.sort_values('Variazione %'), colonne_ranking)}

**Tabella 2.** I {N_TOP} comuni con la crescita maggiore.

{tabella_markdown(migliori.sort_values('Variazione %', ascending=False), colonne_ranking)}

## Costa vs. entroterra

La divergenza più marcata emersa dai dati non è tra comuni piccoli e
grandi in sé (correlazione tra popolazione iniziale e variazione %:
r={stats['corr_dimensione_variazione']:.2f}, debole), ma tra comuni
costieri e dell'entroterra. I comuni costieri mostrano una variazione
mediana di **{stats['mediana_costa']:+.1f}%** (n={stats['n_costa']}),
contro **{stats['mediana_interno']:+.1f}%** dei comuni dell'entroterra
(n={stats['n_interno']}) — una differenza di oltre
**{abs(stats['mediana_costa'] - stats['mediana_interno']):.0f} punti
percentuali** (Figura 3, Figura 4).

![Costa vs entroterra]({nomi_grafici['costa_interno']})

![Dimensione vs variazione, per gruppo]({nomi_grafici['dimensione']})

## Andamento aggregato e proiezione

La Figura 5 mostra l'andamento aggregato ricostruito per l'intero gruppo
di comuni (si veda Materiali e Metodi per i limiti di questa stima), con
l'estrapolazione lineare aggregata fino al {int(df['Anno proiezione'].max())}.

![Andamento aggregato]({nomi_grafici['aggregato']})

## Comuni più a rischio e con le migliori prospettive

Oltre alla variazione storica {stats['anno_min']}-{stats['anno_max']}, il
modello polinomiale di secondo grado descritto in Materiali e Metodi è
stato usato per stimare una **variazione % proiettata** tra l'ultimo anno
osservato e l'anno di proiezione ({stats['anno_max']}\u2192{stats['anno_proiezione']}), distinta dalla variazione
storica: dà un'indicazione — da trattare con cautela ancora maggiore
rispetto alla proiezione storica, trattandosi di un'estrapolazione di
un'estrapolazione — di quali comuni il modello indica come più a rischio
nel breve-medio periodo e quali con le prospettive migliori.

**{stats['n_zero_proiezione']} comuni** ({', '.join(sorted(df[df['Popolazione stimata (proiezione)'] == 0]['Comune']))})
risultano proiettati a **zero abitanti** entro il {stats['anno_proiezione']}
secondo il modello: sono classificati a pari merito (-100%) e ordinati per
popolazione attuale, così il comune con più abitanti da perdere compare
per primo nella classifica. La Figura 6 riassume i valori proiettati per
i {N_TOP} comuni più a rischio e i {N_TOP} con le prospettive migliori.

![Comuni a rischio e in crescita (proiezione)]({nomi_grafici['proiezione_rischio']})
{sezione_traiettorie}
**Tabella 3.** I {N_TOP} comuni più a rischio secondo la proiezione polinomiale.

{tabella_markdown(
    df.sort_values(['Variazione % proiettata', 'Popolazione finale'], ascending=[True, False]).head(N_TOP),
    {"Comune": "Comune", "Popolazione finale": f"Pop. {stats['anno_max']}",
     "Popolazione stimata (proiezione)": f"Pop. stimata {stats['anno_proiezione']}",
     "Variazione % proiettata": "Var. % proiettata"}
)}

**Tabella 4.** I {N_TOP} comuni con le migliori prospettive secondo la proiezione polinomiale.

{tabella_markdown(
    df.sort_values('Variazione % proiettata', ascending=False).head(N_TOP),
    {"Comune": "Comune", "Popolazione finale": f"Pop. {stats['anno_max']}",
     "Popolazione stimata (proiezione)": f"Pop. stimata {stats['anno_proiezione']}",
     "Variazione % proiettata": "Var. % proiettata"}
)}

> **Attenzione a un artefatto della curvatura polinomiale.** Alcuni dei
> comuni con la crescita storica {stats['anno_min']}-{stats['anno_max']} più
> marcata — Agropoli (storica {df[df.Comune=="Agropoli"]["Variazione %"].iloc[0]:+.1f}%) e
> Torchiara (storica {df[df.Comune=="Torchiara"]["Variazione %"].iloc[0]:+.1f}%) tra
> gli altri — **non compaiono** nella classifica delle migliori prospettive:
> il fit polinomiale di secondo grado, pur descrivendo bene i dati storici
> (R\u00b2 > 0.97 per entrambi), proietta per Agropoli una variazione
> negativa ({df[df.Comune=="Agropoli"]["Variazione % proiettata"].iloc[0]:+.1f}%
> al {stats['anno_proiezione']}). Questo è con ogni probabilità un artefatto
> dell'estrapolazione quadratica — una parabola che si adatta bene a una
> crescita che rallenta negli anni recenti può curvare verso il basso una
> volta proiettata fuori dal periodo osservato — più che un segnale reale
> di inversione di tendenza, ed è la ragione per cui queste proiezioni
> vanno lette come indicazioni di massima e non come previsioni.

# Discussione e limiti

I risultati confermano, su una finestra temporale più ampia e con un
confronto quantitativo esplicito tra comuni, il quadro già delineato dalle
fonti ISTAT/SNAI e dalle indagini del GAL {NOME_AREA} Regeneratio: il
declino demografico dell'entroterra cilentano è strutturale, non
episodico, e riguarda la maggioranza dei comuni analizzati. Il dato più
rilevante emerso da questa analisi è la nettezza della divergenza
costa/entroterra, che suggerisce come le dinamiche economiche legate al
turismo costiero (occupazione stagionale, mercato immobiliare,
accessibilità infrastrutturale) stiano producendo due traiettorie
demografiche sostanzialmente diverse all'interno della stessa area
geografica, un aspetto meno enfatizzato nelle sintesi a livello di intera
area SNAI.

Alcuni limiti vanno tenuti presenti. Primo, la classificazione
costa/entroterra qui adottata è una semplificazione geografica, non
un'analisi di accessibilità o di distanza dai servizi come quella usata
dalla SNAI. Secondo, i modelli usati (lineare e polinomiale di secondo
grado) sono deliberatamente semplici: non incorporano dinamiche di
natalità/mortalità, flussi migratori o effetti di policy, e le proiezioni
al {int(df['Anno proiezione'].max())} vanno lette come estrapolazioni di
tendenza, non come previsioni demografiche in senso proprio. Terzo,
l'andamento aggregato di Figura 5 è ricostruito dai modelli individuali e
non da dati grezzi sommati anno per anno, il che ne limita l'affidabilità
per la lettura di eventuali inversioni di tendenza recenti. Quarto, come
mostrato dal caso di Agropoli (Sezione 3.5), l'estrapolazione polinomiale
può curvare vistosamente al di fuori del periodo osservato anche quando il
fit è eccellente sui dati storici: la classifica dei comuni "a rischio" o
"in crescita" per il {stats['anno_proiezione']} va quindi interpretata come
un'indicazione di massima, non come una graduatoria affidabile comune per
comune.

# Bibliografia {{-}}

1. ISTAT, *Statistica Focus: la demografia delle aree interne*, 2024/2025.
2. Scienza in rete, *Oltre lo spopolamento: le aree interne tra crisi e
   possibilità*, 2025.
3. GAL {NOME_AREA} Regeneratio, *Il {NOME_AREA}: tra desertificazione
   sociale e prospettive di sviluppo sostenibile* (indagine demografica,
   ed. 2012 e aggiornamento 2010-2017).
4. Fonte di stampa locale, dati ISTAT su comuni del {NOME_AREA} in fase di
   spopolamento (73-75 comuni su 80), 2021.
5. Wikipedia, *Costiera cilentana*: elenco dei comuni con affaccio sul
   Mar Tirreno.
"""


# --- CSS, only used with the HTML engines ---

CSS_REPORT = """
@page { margin: 2.2cm; }
body { font-family: Georgia, "DejaVu Serif", serif; font-size: 11pt; line-height: 1.5; color: #222; }
header#title-block-header { text-align: center; border-bottom: 2px solid #2E5C8A; padding-bottom: 14px; margin-bottom: 24px; }
h1.title { font-family: Helvetica, Arial, sans-serif; color: #2E5C8A; font-size: 20pt; }
p.subtitle { font-size: 12pt; color: #555; }
h2 { font-family: Helvetica, Arial, sans-serif; color: #2E5C8A; font-size: 14pt; margin-top: 26px; border-bottom: 1px solid #d8e2ec; padding-bottom: 4px; }
h3 { font-family: Helvetica, Arial, sans-serif; color: #3a5f80; font-size: 12pt; margin-top: 18px; }
figure { text-align: center; margin: 16px 0; }
figure img { max-width: 90%; }
p { page-break-inside: avoid; }
table { border-collapse: separate; border-spacing: 0; width: 100%; margin: 12px 0; font-size: 9.5pt; page-break-inside: avoid; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #ccc; padding: 5px 8px; text-align: left; }
th { background-color: #EAF1F8; color: #2E5C8A; }
tr:nth-child(even) { background-color: #F7F9FB; }
blockquote { background-color: #FBF3E7; border-left: 4px solid #C77B24; margin: 14px 0; padding: 8px 16px; color: #444; }
strong { color: #1a3a5c; }
"""


# --- PDF ---

MOTORI_HTML = {"wkhtmltopdf", "weasyprint", "prince"}
ORDINE_MOTORI_PREFERITI = ["xelatex", "pdflatex", "lualatex", "wkhtmltopdf", "weasyprint"]


def trova_motore_pdf() -> str:
    for motore in ORDINE_MOTORI_PREFERITI:
        if shutil.which(motore):
            return motore
    raise RuntimeError(
        "Nessun motore PDF trovato tra: " + ", ".join(ORDINE_MOTORI_PREFERITI) + ".\n"
        "Installane uno, ad esempio una distribuzione LaTeX (texlive-xetex),\n"
        "oppure: sudo apt install wkhtmltopdf"
    )


def converti_in_pdf(cartella: Path, nome_md: str, nome_pdf: str, nome_css: str) -> None:
    motore = trova_motore_pdf()
    print(f"Uso il motore PDF: {motore}")
    comando = ["pandoc", nome_md, "-o", nome_pdf, f"--pdf-engine={motore}",
               "--toc", "--number-sections"]
    if motore in MOTORI_HTML:
        comando += ["-c", nome_css]
    risultato = subprocess.run(comando, cwd=cartella, capture_output=True, text=True)
    if risultato.returncode != 0:
        print("Errore nella conversione PDF:")
        print(risultato.stderr)
        raise RuntimeError("Conversione pandoc fallita, vedi errore sopra.")


# --- main ---

def main() -> None:
    CARTELLA_PNG.mkdir(parents=True, exist_ok=True)
    CARTELLA_PDF.mkdir(parents=True, exist_ok=True)

    df = carica_tabella()
    stats = calcola_statistiche_aggregate(df)

    print(f"Comuni: {stats['n_comuni']}, periodo {stats['anno_min']}-{stats['anno_max']}")
    print(f"Popolazione: {stats['pop_iniziale_tot']:,} -> {stats['pop_finale_tot']:,} "
          f"({stats['variazione_pct_pesata']:+.1f}%)")

    # paths relative to results/, that's where pandoc runs
    nomi_grafici = {
        "distribuzione": "png/distribuzione_variazione.png",
        "estremi": "png/classifica_estremi.png",
        "costa_interno": "png/costa_vs_interno.png",
        "dimensione": "png/dimensione_vs_variazione.png",
        "aggregato": "png/andamento_aggregato.png",
        "proiezione_rischio": "png/proiezione_rischio_crescita.png",
    }
    fig_distribuzione_variazione(df, CARTELLA_OUTPUT / nomi_grafici["distribuzione"])
    fig_classifica_estremi(df, N_TOP, CARTELLA_OUTPUT / nomi_grafici["estremi"])
    fig_costa_vs_interno(df, CARTELLA_OUTPUT / nomi_grafici["costa_interno"])
    fig_dimensione_vs_variazione(df, CARTELLA_OUTPUT / nomi_grafici["dimensione"])
    fig_andamento_aggregato(df, stats, CARTELLA_OUTPUT / nomi_grafici["aggregato"])
    fig_classifica_proiezione(
        df, N_TOP, stats["anno_proiezione"], CARTELLA_OUTPUT / nomi_grafici["proiezione_rischio"]
    )

    # trajectories figure: same comuni as Tables 3 and 4, needs the yearly series
    comuni_rischio = df.sort_values(
        ["Variazione % proiettata", "Popolazione finale"], ascending=[True, False]
    ).head(N_TOP)["Comune"].tolist()
    comuni_crescita = df.sort_values(
        "Variazione % proiettata", ascending=False
    ).head(N_TOP)["Comune"].tolist()

    pop_annua_storica = carica_pop_annua_storica(comuni_rischio + comuni_crescita)
    traiettorie_disponibili = pop_annua_storica is not None
    if traiettorie_disponibili:
        nomi_grafici["traiettorie_rischio"] = "png/traiettorie_rischio_crescita.png"
        grado_polinomio = int(df["Grado polinomio usato"].mode().iloc[0])
        fig_traiettorie_rischio_crescita(
            pop_annua_storica, comuni_rischio, comuni_crescita,
            grado_polinomio, stats["anno_proiezione"],
            CARTELLA_OUTPUT / nomi_grafici["traiettorie_rischio"],
        )

    markdown = genera_markdown(df, stats, nomi_grafici, traiettorie_disponibili)
    MD_PATH.write_text(markdown, encoding="utf-8")
    CSS_PATH.write_text(CSS_REPORT, encoding="utf-8")
    print(f"\nMarkdown salvato in: {MD_PATH.resolve()}")

    converti_in_pdf(
        CARTELLA_OUTPUT, MD_PATH.name,
        PDF_PATH.relative_to(CARTELLA_OUTPUT).as_posix(), CSS_PATH.name,
    )
    print(f"PDF salvato in: {PDF_PATH.resolve()}")


if __name__ == "__main__":
    main()